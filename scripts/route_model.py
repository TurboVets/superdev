#!/usr/bin/env python3
"""SuperDev decides: skill surface + paths + cheapest capable model.

SuperDev (not the user) chooses:
  - LIGHT asks → `boot` vs `full_skill` (almost never full paths)
  - HEAVY asks → which Paths to run (not all Paths every time) + model tier
  - Model pick biased by measured feedback-loop cost (fewer loops = better)

Usage:
  # Decide for this turn
  python3 route_model.py --prompt "..." --path 5.5 --goal ship_pr --pretty

  # Record outcome after a phase finishes (loops = fix/retry rounds needed)
  python3 route_model.py --record --model gpt-5.6-sol-medium --phase 5.5 \\
      --loops 2 --outcome ship --note "tv-fullstack ×2"

  # Show learned rankings
  python3 route_model.py --leaderboard

  # Session-sticky auto-switch (Task spawn). Cannot flip the Cursor picker.
  python3 route_model.py --auto-switch on|off|status|clear
  python3 route_model.py --fresh-chat --prompt "..."   # first SuperDev turn
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from lib_paths import (
    INTENT,
    auto_switch,
    clear_session,
    ensure_state,
    set_auto_switch,
)

ensure_state()
OUTCOMES = INTENT / "model-outcomes.jsonl"
LEADERBOARD = INTENT / "model-performance.md"

MODELS = {
    "inherit": {"tier": 0, "cost": "parent", "label": "Parent model — auto-switch off only"},
    "composer-2.5-fast": {"tier": 1, "cost": "low", "label": "Fast mechanical — simple Qs / status"},
    "cursor-grok-4.5-high-fast": {"tier": 2, "cost": "mid-low", "label": "Grok 4.5 standard"},
    "cursor-grok-4.6-high-fast": {"tier": 2, "cost": "mid-low", "label": "Grok 4.6 — build / smoke"},
    "gpt-5.6-sol-medium": {"tier": 3, "cost": "mid", "label": "GPT mid — audit / bots"},
    "claude-4.6-opus-high-thinking": {"tier": 4, "cost": "high", "label": "Claude 4.6 thinking"},
    "claude-fable-5-thinking-high": {"tier": 4, "cost": "highest", "label": "Claude Fable 5 thinking"},
    "claude-opus-5-thinking-high": {"tier": 4, "cost": "highest", "label": "Claude Opus 5 thinking"},
}

# T0 used to be inherit (= stay on the expensive picker). Simple Qs then
# burned Grok High Fast. T0/T1 both spawn Composer unless parent is already it.
TIER_DEFAULT_MODEL = {
    0: "composer-2.5-fast",
    1: "composer-2.5-fast",
    2: "cursor-grok-4.6-high-fast",
    3: "gpt-5.6-sol-medium",
    4: "claude-opus-5-thinking-high",
}

# Phase → minimum tier + whether high-functioning is required
# SuperDev skips phases not listed in paths_to_run.
PHASE_MIN_TIER = {
    "0": 0,  # token boot / status
    "1": 1,  # pick
    "2": 2,  # issue craft
    "3": 3,  # grill — needs strong product reasoning
    "4": 2,  # unknowns (code) / 3 if product
    "5": 2,  # build mechanical; bump if architecture
    "5.5": 3,  # full-stack audit — high functioning
    "6": 2,  # prove/smoke drive; bot gate substep = 3
    "6.bot": 3,  # local bot gate
    "7": 4,  # human review — highest
}

HIGH_FUNCTIONING_PHASES = {"3", "5.5", "6.bot", "7"}

HARD_KEYWORDS = [
    r"\b(authz|authorization|security|vuln|race|deadlock|concurrency|lease)\b",
    r"\b(path\s*7|human review|changes.?requested)\b",
    r"\b(migration|turbo-?db|studio schema)\b",
    r"\b(tv-fullstack|full-?stack audit|path\s*5\.5)\b",
]
MED_KEYWORDS = [
    r"\b(implement|build|fix|pr\b|smoke|acceptance|bdd)\b",
    r"\b(path\s*[56]|ship|grill|unknowns)\b",
    r"\b(refactor|graphql|resolver|entity)\b",
]
EASY_KEYWORDS = [
    r"\b(typo|rename|lint|format|status|remind|what is|where is|who is)\b",
    r"\b(why is|why are|how come|what does|what do)\b",
    r"\b(check again|re-?check|summarize|list)\b",
]
WRITE_HINTS = [
    r"\b(implement|build|fix|ship|audit|migrate|refactor|commit|push)\b",
    r"\b(you should (make|change|update|add|fix))\b",
    r"\b(change|update|add|edit|rewrite)\b.+\b(skill|router|routing)\b",
]


def _is_simple_question(prompt: str, text: str) -> bool:
    """Cheap Q&A — not a write, not a high-func path."""
    if any(re.search(k, text, re.I) for k in HARD_KEYWORDS):
        return False
    if any(re.search(k, text, re.I) for k in WRITE_HINTS):
        return False
    p = (prompt or "").strip()
    if not p or len(p) > 900:
        return False
    if "?" in p:
        return True
    return bool(re.match(r"(why|what|how|who|when|where|is|are|do|does|can|should)\b", p, re.I))

SWITCH_OFF = (
    r"\bauto-?switch\s+off\b",
    r"\bkeep this model\b",
    r"\bdon'?t switch models\b",
    r"/autoswitch\s+off",
)
SWITCH_ON = (
    r"\bauto-?switch\s+on\b",
    r"\bpick the model\b",
    r"/autoswitch\s+on",
)


def _normalize_phase(path: str) -> str:
    p = (path or "").strip().lower()
    p = p.replace("path", "").strip()
    if "5.5" in p or p in {"audit", "fullstack"}:
        return "5.5"
    if "bot" in p:
        return "6.bot"
    if p.startswith("7") or "review" in p:
        return "7"
    if p.startswith("6") or "smoke" in p or "ship" in p:
        return "6"
    if p.startswith("5") and "5.5" not in p:
        return "5"
    if "grill" in p or p.startswith("3"):
        return "3"
    if "unknown" in p or p.startswith("4"):
        return "4"
    if p.startswith("2") or "issue" in p:
        return "2"
    if p.startswith("1") or "pick" in p:
        return "1"
    if p.startswith("0") or "boot" in p or "status" in p:
        return "0"
    return ""


def _load_outcomes(limit: int = 200) -> list[dict]:
    if not OUTCOMES.exists():
        return []
    rows = []
    for line in OUTCOMES.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:]


def _avg_loops(phase: str, model: str | None = None) -> dict[str, float]:
    """Lower avg loops ⇒ model works better for this phase."""
    rows = [
        r
        for r in _load_outcomes()
        if r.get("phase") == phase and r.get("outcome") in {"ship", "ok", "approve"}
    ]
    if model:
        rows = [r for r in rows if r.get("model") == model]
    buckets: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        m = r.get("model")
        loops = r.get("loops")
        if m in MODELS and isinstance(loops, (int, float)):
            buckets[m].append(int(loops))
    return {m: sum(v) / len(v) for m, v in buckets.items() if v}


def _pick_model_for_tier(tier: int, phase: str) -> tuple[str, str]:
    """Prefer learned low-loop models in the same tier; else default."""
    default = TIER_DEFAULT_MODEL[tier]
    avgs = _avg_loops(phase)
    same_tier = [
        (m, avg)
        for m, avg in avgs.items()
        if MODELS[m]["tier"] == tier and m != "inherit"
    ]
    if not same_tier:
        return default, "tier_default"
    same_tier.sort(key=lambda x: x[1])
    best, avg = same_tier[0]
    if best != default and avg + 0.25 < avgs.get(default, 99):
        return best, f"learned_lower_loops({avg:.1f} vs default)"
    return default, "tier_default_or_tied"


def _skill_surface(tier: int, phase: str, heavy: bool) -> dict:
    """
    LIGHT: decide boot vs full_skill only.
    HEAVY: decide which full paths to run (not every path).
    """
    if not heavy and tier <= 2:
        surface = "boot" if tier <= 1 or phase in {"", "0", "1"} else "full_skill"
        # T2 implement/smoke still often boot+path section, not entire lifecycle
        if phase in {"5", "6"} and tier == 2:
            surface = "full_skill"
        paths = []
        if phase:
            paths = [phase]
        return {
            "skill_surface": surface,
            "skill_reason": (
                "light ask — SuperDev chooses boot vs full_skill only; "
                "do not run unused lifecycle paths"
            ),
            "paths_to_run": paths or (["0"] if surface == "boot" else []),
            "attach": (
                "superdev-boot"
                if surface == "boot"
                else "superdev (path section only)"
            ),
        }

    # Heavy: pick required paths from phase + implied gates
    paths: list[str] = []
    if phase:
        paths.append(phase)
    # Implied predecessors only when needed for completion
    if phase == "6":
        paths = ["5.5", "6"]  # never smoke without audit gate
    if phase == "6.bot":
        paths = ["5.5", "6.bot"]
    if phase == "7":
        paths = ["7"]  # teammate = chat draft; own PR may need 5.5 first
    if phase == "5":
        paths = ["5", "5.5"]  # build implies audit next
    if phase == "3":
        paths = ["3", "4"]  # grill → unknowns

    # Dedupe preserve order
    seen = set()
    ordered = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    return {
        "skill_surface": "full_paths",
        "skill_reason": (
            "heavy ask — SuperDev chooses which Paths to run "
            f"({', '.join(ordered) or 'none'}); skip the rest"
        ),
        "paths_to_run": ordered,
        "attach": "superdev (only listed path sections + refs on demand)",
    }


def score(
    prompt: str = "",
    path: str = "",
    goal: str = "",
    affect: str = "",
) -> dict:
    text = f"{prompt} {path} {goal} {affect}".lower()
    phase = _normalize_phase(path)
    if not phase:
        # Infer phase from goals/keywords
        if "review_pr" in (goal or "") or re.search(r"\breview\b", text):
            phase = "7"
        elif "ship_pr" in (goal or "") or "smoke" in text:
            phase = "6"
        elif "audit" in text or "5.5" in text or "tv-fullstack" in text:
            phase = "5.5"
        elif "grill" in text or "acceptance criteria" in text:
            phase = "3"
        elif "implement" in (goal or "") or "fix_bug" in (goal or "") or "build" in text:
            phase = "5"
        elif "meta_skill" in (goal or ""):
            phase = "5"  # skill edits = build on skills
        elif "status" in (goal or "") or "check again" in text:
            phase = "0"
        else:
            phase = "0"

    tier = PHASE_MIN_TIER.get(phase, 2)
    reasons = [f"phase={phase} min_tier={tier}"]

    if phase in HIGH_FUNCTIONING_PHASES:
        reasons.append("high_functioning_required")

    g = (goal or "").lower()
    if "review_pr" in g:
        tier = max(tier, 4 if phase == "7" else 3)
        reasons.append("goal=review_pr")
    if "ship_pr" in g or "implement" in g or "fix_bug" in g:
        tier = max(tier, 2)
    easy = (
        phase not in HIGH_FUNCTIONING_PHASES
        and (
            any(re.search(k, text, re.I) for k in EASY_KEYWORDS)
            or _is_simple_question(prompt, text)
        )
    )
    if "meta_skill" in g and phase not in HIGH_FUNCTIONING_PHASES:
        if easy:
            tier = min(tier, 1)
            reasons.append("meta_skill question → T1")
        else:
            tier = min(max(tier, 2), 2)
            reasons.append("meta_skill → T2 cap unless high-func phase")
    if "status" in g or "general" == g:
        if not any(re.search(k, text) for k in HARD_KEYWORDS):
            tier = min(tier, 1)
            reasons.append("status/general → cheap")

    if any(re.search(k, text, re.I) for k in HARD_KEYWORDS):
        tier = max(tier, 4 if re.search(r"authz|race|concurrency|security", text) else 3)
        reasons.append("hard keywords")
    elif easy:
        tier = min(tier, 1)
        reasons.append("easy / simple question → Composer")
    elif any(re.search(k, text, re.I) for k in MED_KEYWORDS):
        tier = max(tier, 2)
        reasons.append("medium keywords")

    if affect in {"mad", "frustrated", "corrective"} and not easy:
        tier = max(tier, 2)
        reasons.append(f"affect={affect}")

    tier = max(0, min(4, tier))
    model, model_why = _pick_model_for_tier(tier, phase)
    heavy = tier >= 3 or phase in HIGH_FUNCTIONING_PHASES or phase in {"5", "6", "3", "7"}
    # Light meta/status stays light even if phase inferred as 5 for skill edit
    if "meta_skill" in g and phase == "5" and not any(re.search(k, text) for k in HARD_KEYWORDS):
        heavy = False
        surface = _skill_surface(tier, phase, heavy=False)
    else:
        surface = _skill_surface(tier, phase, heavy=heavy)

    avgs = _avg_loops(phase)
    learned = (
        sorted(avgs.items(), key=lambda x: x[1])[:3]
        if avgs
        else []
    )

    return {
        "phase": phase,
        "high_functioning_required": phase in HIGH_FUNCTIONING_PHASES,
        "tier": tier,
        "tier_name": ["T0_trivial", "T1_easy", "T2_standard", "T3_hard", "T4_critical"][tier],
        "model": model,
        "model_meta": MODELS[model],
        "model_why": model_why,
        "alternates": [
            m
            for m, meta in MODELS.items()
            if meta["tier"] == tier and m != model and m != "inherit"
        ],
        **surface,
        "learned_best_for_phase": [
            {"model": m, "avg_loops": round(a, 2)} for m, a in learned
        ],
        "reasons": reasons,
        "decision_contract": (
            "SuperDev decides skill_surface + paths_to_run + recommended model. "
            "auto_switch on → Task-spawn on that slug (cannot flip the Cursor picker). "
            "auto_switch off → stay on the parent model; still print the recommendation. "
            "Light → boot vs full_skill only. "
            "Heavy → listed paths only (skip the rest). "
            "Record --loops after each phase so routing learns."
        ),
        "token_rules": [
            "emit_context_pack.py before session-log / full focus",
            "Do not re-Read SKILL.md if already attached",
            "Spawn ≤1 Task unless parallel explore is a clear win",
            "After phase: route_model.py --record --loops N --outcome ship|retry|fail",
        ],
    }


def detect_switch_words(prompt: str) -> str | None:
    text = prompt or ""
    if any(re.search(p, text, re.I) for p in SWITCH_OFF):
        return "off"
    if any(re.search(p, text, re.I) for p in SWITCH_ON):
        return "on"
    return None


PARENT_ALIASES = {
    "inherit": "inherit",
    "parent": "inherit",
    "cursor-grok-4.6-high-fast": "cursor-grok-4.6-high-fast",
    "cursor-grok-4.6": "cursor-grok-4.6-high-fast",
    "grok-4.6": "cursor-grok-4.6-high-fast",
    "cursor-grok-4.5-high-fast": "cursor-grok-4.5-high-fast",
    "cursor-grok-4.5": "cursor-grok-4.5-high-fast",
    "grok-4.5": "cursor-grok-4.5-high-fast",
    "composer-2.5-fast": "composer-2.5-fast",
    "composer": "composer-2.5-fast",
    "gpt-5.6-sol-medium": "gpt-5.6-sol-medium",
    "gpt-5.6": "gpt-5.6-sol-medium",
    "claude-opus-5-thinking-high": "claude-opus-5-thinking-high",
    "claude-opus-5": "claude-opus-5-thinking-high",
    "claude-fable-5-thinking-high": "claude-fable-5-thinking-high",
    "claude-fable-5": "claude-fable-5-thinking-high",
    "fable": "claude-fable-5-thinking-high",
    "claude-4.6-opus-high-thinking": "claude-4.6-opus-high-thinking",
    "claude-4.6-opus": "claude-4.6-opus-high-thinking",
}


def normalize_model_slug(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if s in MODELS:
        return s
    key = re.sub(r"[\s_]+", "-", s.lower())
    return PARENT_ALIASES.get(key)


def apply_auto_switch(
    rec: dict,
    on: bool,
    source: str,
    parent: str | None = None,
) -> dict:
    recommended = rec.get("recommended_model") or rec["model"]
    rec["recommended_model"] = recommended
    rec["auto_switch"] = "on" if on else "off"
    rec["auto_switch_source"] = source
    rec["parent_model"] = parent
    rec["picker"] = "unchanged"

    def stay(reason: str, action: str, model: str = "inherit") -> dict:
        rec["model"] = model
        rec["model_meta"] = MODELS[model]
        rec["apply"] = "stay"
        rec["did"] = reason
        rec["spawn_model"] = "inherit"
        rec["model_action"] = action
        return rec

    if not on:
        return stay(
            "off",
            "auto-switch off — stay on parent. "
            f"Recommended: {recommended} (T{rec['tier']}). Picker unchanged.",
        )
    if recommended == "inherit":
        return stay("t0", "T0 — stay on parent; no Task spawn. Picker unchanged.")
    if parent and parent == recommended:
        return stay(
            "same_parent",
            f"already on {recommended} — no Task spawn. Picker unchanged.",
            model=recommended,
        )
    rec["model"] = recommended
    rec["model_meta"] = MODELS[recommended]
    rec["apply"] = "spawn"
    rec["did"] = "spawn"
    rec["spawn_model"] = recommended
    rec["model_action"] = (
        f"FIRST tool: Task model={recommended}. "
        "SuperDev + auto-switch on is the user requesting that slug — "
        "do not pass inherit. Do not do this turn's Path work on the parent. "
        "Picker stays on the parent."
    )
    return rec


def _self_check() -> int:
    rec = score("fix the graphql resolver", "5", "implement")
    on = apply_auto_switch(dict(rec), True, "default")
    assert on["apply"] == "spawn", on
    assert on["spawn_model"] != "inherit", on
    off = apply_auto_switch(dict(rec), False, "session")
    assert off["apply"] == "stay" and off["model"] == "inherit", off
    assert off["recommended_model"] == rec["model"], off
    t0 = apply_auto_switch(score("what is the status"), True, "default")
    assert t0["apply"] == "spawn" and t0["spawn_model"] == "composer-2.5-fast", t0
    cheap = apply_auto_switch(
        score("what is the status"),
        True,
        "default",
        parent="cursor-grok-4.6-high-fast",
    )
    assert cheap["apply"] == "spawn" and cheap["spawn_model"] == "composer-2.5-fast", cheap
    t0_same = apply_auto_switch(
        score("what is the status"), True, "default", parent="composer-2.5-fast"
    )
    assert t0_same["apply"] == "stay" and t0_same["did"] == "same_parent", t0_same
    why = score("why are we using grok for simple questions?")
    assert why["tier"] <= 1 and why["model"] == "composer-2.5-fast", why
    same = apply_auto_switch(dict(rec), True, "default", parent=rec["model"])
    assert same["apply"] == "stay" and same["did"] == "same_parent", same
    t3 = apply_auto_switch(
        score("run tv-fullstack audit", "5.5", "audit"),
        True,
        "default",
        parent="cursor-grok-4.6-high-fast",
    )
    assert t3["apply"] == "spawn" and t3["spawn_model"] == "gpt-5.6-sol-medium", t3
    assert normalize_model_slug("Cursor Grok 4.6") == "cursor-grok-4.6-high-fast"
    assert detect_switch_words("auto-switch off please") == "off"
    assert detect_switch_words("keep this model") == "off"
    assert detect_switch_words("/autoswitch on") == "on"
    print("self-check ok")
    return 0


def record_outcome(
    model: str,
    phase: str,
    loops: int,
    outcome: str,
    note: str = "",
) -> dict:
    phase = _normalize_phase(phase) or phase
    if model not in MODELS:
        raise SystemExit(f"unknown model {model}; allowed: {', '.join(MODELS)}")
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "phase": phase,
        "loops": int(loops),
        "outcome": outcome,
        "note": note[:200],
        "tier": MODELS[model]["tier"],
    }
    INTENT.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_leaderboard()
    return row


def write_leaderboard() -> None:
    rows = _load_outcomes(500)
    by_phase: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("outcome") not in {"ship", "ok", "approve"}:
            continue
        by_phase[r["phase"]][r["model"]].append(int(r["loops"]))

    lines = [
        "# Model performance (by feedback loops)",
        "",
        "_Lower avg loops = better for that SuperDev phase. "
        "Updated by `route_model.py --record`._",
        "",
        f"_Last distill: {datetime.now(timezone.utc).isoformat()}_",
        "",
    ]
    if not by_phase:
        lines.append("_No outcomes yet. Record after each phase._\n")
    for phase in sorted(by_phase.keys(), key=lambda p: (len(p), p)):
        lines.append(f"## Phase {phase}")
        lines.append("")
        lines.append("| Model | n | avg loops | best |")
        lines.append("| ----- | - | --------- | ---- |")
        ranked = []
        for model, vals in by_phase[phase].items():
            avg = sum(vals) / len(vals)
            ranked.append((avg, model, len(vals), min(vals)))
        ranked.sort()
        for i, (avg, model, n, best) in enumerate(ranked):
            mark = "← prefer" if i == 0 else ""
            lines.append(f"| `{model}` | {n} | {avg:.2f} | {best} {mark}|")
        lines.append("")
    LEADERBOARD.write_text("\n".join(lines) + "\n")


def leaderboard_text() -> str:
    if not LEADERBOARD.exists():
        write_leaderboard()
    return LEADERBOARD.read_text() if LEADERBOARD.exists() else "(empty)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--path", default="")
    ap.add_argument("--goal", default="")
    ap.add_argument("--affect", default="neutral")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--model", default="")
    ap.add_argument("--phase", default="")
    ap.add_argument("--loops", type=int, default=1)
    ap.add_argument("--outcome", default="ship", help="ship|ok|approve|retry|fail")
    ap.add_argument("--note", default="")
    ap.add_argument("--leaderboard", action="store_true")
    ap.add_argument(
        "--auto-switch",
        dest="auto_switch_cmd",
        choices=("on", "off", "status", "clear"),
        help="Session-sticky switch. on|off writes state/session.json.",
    )
    ap.add_argument(
        "--fresh-chat",
        action="store_true",
        help="First SuperDev turn of a chat — drop leftover session.json.",
    )
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument(
        "--parent-model",
        default=os.environ.get("SUPERDEV_PARENT_MODEL", ""),
        help="This chat's picker slug. Same-as-parent → stay, not a fake spawn.",
    )
    args = ap.parse_args()

    if args.self_check:
        return _self_check()

    if args.leaderboard:
        print(leaderboard_text())
        return 0

    if args.record:
        row = record_outcome(
            model=args.model or TIER_DEFAULT_MODEL[2],
            phase=args.phase or args.path or "0",
            loops=args.loops,
            outcome=args.outcome,
            note=args.note,
        )
        print(json.dumps(row, indent=2))
        return 0

    if args.fresh_chat:
        clear_session()

    words = detect_switch_words(args.prompt)
    cmd = args.auto_switch_cmd
    if cmd in {"on", "off"} or words in {"on", "off"}:
        on_val = (cmd or words) == "on"
        set_auto_switch(on_val, source="chat")
        cli = "on" if on_val else "off"
    elif cmd == "clear":
        clear_session()
        cli = None
    else:
        cli = None

    on, source = auto_switch(cli)

    if cmd == "status" and not args.prompt and not args.path and not args.goal:
        print(f"auto_switch: {'on' if on else 'off'} ({source})")
        return 0
    if cmd == "clear" and not args.prompt and not args.path and not args.goal:
        print("auto_switch: cleared session — next score uses operator.yaml / default")
        return 0

    rec = apply_auto_switch(
        score(args.prompt, args.path, args.goal, args.affect),
        on,
        source,
        parent=normalize_model_slug(args.parent_model),
    )
    if args.json:
        json.dump(rec, sys.stdout, indent=2)
        print()
        return 0

    print(f"phase: {rec['phase']}  high_functioning={rec['high_functioning_required']}")
    print(f"skill_surface: {rec['skill_surface']}  → {rec['attach']}")
    print(f"paths_to_run: {', '.join(rec['paths_to_run']) or '(none)'}")
    print(f"tier: {rec['tier_name']} (T{rec['tier']})")
    print(f"auto_switch: {rec['auto_switch']} ({rec['auto_switch_source']})")
    print(f"apply: {rec['apply']}  spawn={rec['spawn_model']}  did={rec['did']}")
    print("picker: unchanged")
    print(
        f"model: {rec['model']}  [{rec['model_meta']['cost']}] — "
        f"{rec['model_meta']['label']} ({rec['model_why']})"
    )
    if rec["apply"] == "stay" and rec["recommended_model"] != rec["model"]:
        print(f"recommended: {rec['recommended_model']}")
    print(f"action: {rec['model_action']}")
    if rec["alternates"]:
        print(f"alternates: {', '.join(rec['alternates'])}")
    if rec["learned_best_for_phase"]:
        print(
            "learned: "
            + ", ".join(
                f"{x['model']}@{x['avg_loops']}loops"
                for x in rec["learned_best_for_phase"]
            )
        )
    print(f"why: {'; '.join(rec['reasons'])}")
    print(f"contract: {rec['decision_contract']}")
    if args.pretty:
        print("token_rules:")
        for t in rec["token_rules"]:
            print(f"  - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
