#!/usr/bin/env python3
"""Record / tag / distill user prompt intentions for SuperDev + local-memory.

Stores a rolling window of the last N user prompts (default 200) with
structured intention tags. Distills recurring themes into intention-model.md
so every SuperDev / local-memory invoke can adapt delivery to what the operator
actually wants.

Usage:
  # Tag + append one prompt (from current turn)
  python3 record_intention.py --prompt "..." [--affect frustrated] [--goal meta]

  # Bootstrap from Cursor agent transcripts (newest first, up to --limit)
  python3 record_intention.py --bootstrap [--limit 200]

  # Re-distill living model from existing history only
  python3 record_intention.py --distill-only

  # Print the last N tagged prompts (for REPLAY)
  python3 record_intention.py --replay [--limit 20]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from lib_paths import (
    INTENT,
    STATE as MEMORY,
    WORK_HISTORY,
    default_repo,
    ensure_state,
    github_login,
    operator_name,
    workspace,
)

ensure_state()

INTENT_DIR = INTENT
HISTORY_PATH = INTENT_DIR / "prompt-history.jsonl"
MODEL_PATH = INTENT_DIR / "intention-model.md"
LEARN_LEDGER_PATH = INTENT_DIR / "learn-ledger.jsonl"
DEFAULT_CAP = 200
REPLAY_DEFAULT = 50

# Heuristic keyword banks — agent still overrides with explicit --affect/--goal.
AFFECT_RULES: list[tuple[str, list[str]]] = [
    (
        "mad",
        [
            r"\bfurious\b",
            r"\bangry\b",
            r"\bunacceptable\b",
            r"\bthis is ridiculous\b",
            r"\bwaste of time\b",
        ],
    ),
    (
        "frustrated",
        [
            r"\bfrustrat",
            r"\bstill not\b",
            r"\byou (already|still|keep|didn'?t|have not)\b",
            r"\bi (already|told|asked|said)\b",
            r"\bwhy (can'?t|didn'?t|won'?t|isn'?t)\b",
            r"\bagain\b.*\b(fix|do|post|update)\b",
            r"\bnot working\b",
            r"\bi think you (have not|didn'?t|forgot)\b",
        ],
    ),
    (
        "urgent",
        [
            r"\basap\b",
            r"\bright now\b",
            r"\bimmediately\b",
            r"\bbefore (standup|demo|launch)\b",
            r"\bblocker\b",
            r"\burgent\b",
        ],
    ),
    (
        "corrective",
        [
            r"\bno[,.]?\s+(do not|don'?t|stop)\b",
            r"\bdon'?t\b",
            r"\bnever\b",
            r"\bstop\b",
            r"\bwrong\b",
            r"\bnot what i (asked|wanted|meant)\b",
            r"\bi said\b",
        ],
    ),
]

GOAL_RULES: list[tuple[str, list[str]]] = [
    ("meta_skill", [r"\bskill\b", r"\bsuperdev\b", r"\blocal-memory\b", r"\bintention\b", r"\blearn(ing)?\b.*\b(user|prompt)"]),
    ("ship_pr", [r"\bpush\b", r"\bopen (the )?pr\b", r"\bmerge\b", r"\bsmoke\b", r"\bre-?request\b"]),
    ("prove_qa", [r"tv-qa", r"live qa", r"not covered", r"leftover"]),
    ("review_pr", [r"\breview\b", r"\bapprove\b", r"\bchanges.?requested\b", r"/pr\b", r"pull/\d+"]),
    ("fix_bug", [r"\bfix\b", r"\bbug\b", r"\bflake\b", r"\bbreaking\b", r"\bred\b"]),
    ("implement", [r"\bimplement\b", r"\bbuild\b", r"\bcode\b", r"\bwork on\b", r"\badd\b"]),
    ("diagnose", [r"\bwhy\b", r"\bwhat'?s wrong\b", r"\bdiagnos", r"\bfailing\b", r"\binvestigat"]),
    ("pick_work", [r"\bwhat should i (work on|do)\b", r"\bnext\b.*\b(ticket|issue)\b", r"/daily-brief\b"]),
    ("status", [r"\bstatus\b", r"\bwhere are we\b", r"\bis everything\b", r"\bupdate me\b"]),
]

STANDING_THEME_RULES: list[tuple[str, list[str]]] = [
    ("audit_first", [r"tv-fullstack", r"audit.?first", r"path 5\.5", r"before (smoke|codex|push)"]),
    ("smoke_proof", [r"smoke", r"recording", r"subtitle", r"pr-asset"]),
    ("mine_only_github", [r"never.*(else|other).*pr", r"mine only", r"don'?t touch.*(their|someone)"]),
    ("superdev_lifecycle", [r"superdev", r"grill", r"path \d"]),
    ("dbq_lane", [r"\bdbq\b", r"#8966", r"#8967", r"#9054", r"seed-documents"]),
    ("provenance_stack", [r"#9055", r"#9131", r"#9036", r"provenance", r"author"]),
    ("e2e_infra", [r"e2e", r"flake", r"turbonumber", r"analysis-tray"]),
    ("gh_link_continue", [r"github\.com/.+/(pull|issues)/\d+", r"#issuecomment-", r"#pullrequestreview-", r"github link", r"attached (github|pr|issue|comment)", r"/turbovets-superdev.*https?://github"]),
    ("intention_memory", [r"intention", r"prompt history", r"learn.*(user|me)", r"previous \d+ prompts"]),
    ("skill_self_improve", [r"modify.*(skill|superdev)", r"update.*(skill|behavior)", r"self.?learn"]),
    ("leftover_qa", [r"not covered", r"leftover"]),
    ("push_reconcile", [r"what is pushed", r"from the push", r"reconcile", r"extract intention"]),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify(prompt: str) -> dict:
    text = prompt.lower()
    affect = "neutral"
    for label, patterns in AFFECT_RULES:
        if any(re.search(p, text) for p in patterns):
            affect = label
            break

    goals: list[str] = []
    for label, patterns in GOAL_RULES:
        if any(re.search(p, text) for p in patterns):
            goals.append(label)
    if not goals:
        goals = ["general"]

    themes: list[str] = []
    for label, patterns in STANDING_THEME_RULES:
        if any(re.search(p, text) for p in patterns):
            themes.append(label)

    # Delivery contract hints from affect
    if affect in {"mad", "frustrated"}:
        delivery = "acknowledge_miss → fix_exact_ask → no_scope_creep → prove_done"
    elif affect == "corrective":
        delivery = "obey_constraint → update_preferences → never_repeat"
    elif affect == "urgent":
        delivery = "shortest_path → ship_artifact → skip_essay"
    else:
        delivery = "stage_detect → deliver_artifact → stamp"

    return {
        "affect": affect,
        "goals": goals,
        "themes": themes,
        "delivery": delivery,
        "summary": summarize_prompt(prompt),
    }


def summarize_prompt(prompt: str, max_len: int = 160) -> str:
    clean = re.sub(r"\s+", " ", prompt).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1] + "…"


def load_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    rows: list[dict] = []
    with HISTORY_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_history(rows: list[dict], cap: int = DEFAULT_CAP) -> None:
    INTENT_DIR.mkdir(parents=True, exist_ok=True)
    # Keep newest last in file for append-friendliness; cap trims oldest.
    if len(rows) > cap:
        rows = rows[-cap:]
    with HISTORY_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_record(
    prompt: str,
    *,
    affect: str | None = None,
    goals: list[str] | None = None,
    source: str = "live",
    transcript_id: str | None = None,
    ts: str | None = None,
    cap: int = DEFAULT_CAP,
) -> dict:
    tags = classify(prompt)
    if affect:
        tags["affect"] = affect
    if goals:
        tags["goals"] = goals

    record = {
        "id": f"{(ts or utc_now())}-{abs(hash(prompt[:80])) % 10_000_000:07d}",
        "ts": ts or utc_now(),
        "source": source,
        "transcript_id": transcript_id,
        "prompt": prompt[:4000],
        "summary": tags["summary"],
        "affect": tags["affect"],
        "goals": tags["goals"],
        "themes": tags["themes"],
        "delivery": tags["delivery"],
    }

    rows = load_history()
    # Dedupe near-identical recent prompts
    key = re.sub(r"\s+", " ", prompt[:300]).lower()
    for existing in rows[-20:]:
        if re.sub(r"\s+", " ", (existing.get("prompt") or "")[:300]).lower() == key:
            return existing
    rows.append(record)
    write_history(rows, cap=cap)
    return record


def distill(rows: list[dict], lookback: int = 200) -> str:
    window = rows[-lookback:] if rows else []
    n = len(window)
    affect_counts = Counter(r.get("affect", "neutral") for r in window)
    goal_counts = Counter(g for r in window for g in r.get("goals") or ["general"])
    theme_counts = Counter(t for r in window for t in r.get("themes") or [])

    # Standing asks: themes that appear in ≥3 of last 50, or ≥5 overall
    recent = window[-50:]
    recent_themes = Counter(t for r in recent for t in r.get("themes") or [])
    standing = []
    for theme, count in theme_counts.most_common():
        if count >= 5 or recent_themes.get(theme, 0) >= 3:
            standing.append((theme, count, recent_themes.get(theme, 0)))

    frustrated_ratio = (
        (affect_counts.get("frustrated", 0) + affect_counts.get("mad", 0) + affect_counts.get("corrective", 0))
        / max(n, 1)
    )

    lines = [
        "# User intention model (Hrishi)",
        "",
        "Living distill of the rolling prompt-history window. SuperDev and",
        "`/local-memory` **must** REPLAY this before ACT so delivery matches",
        "what the user has been asking across the last 50–200 prompts.",
        "",
        f"_Last distilled: {utc_now()}_",
        f"_Window size: {n} prompts (cap {DEFAULT_CAP})_",
        "",
        "## Current read",
        "",
    ]

    if frustrated_ratio >= 0.2:
        lines.append(
            f"- **Affect pressure is elevated** ({frustrated_ratio:.0%} frustrated/mad/corrective "
            "in window). Prefer acknowledge → exact fix → proof. No essays, no scope creep."
        )
    else:
        lines.append("- Affect mostly neutral/operational. Still tag every prompt; escalate delivery when affect flips.")

    if standing:
        lines.append("- **Standing themes** (keep delivering these until explicitly dropped):")
        for theme, total, recent_n in standing[:12]:
            lines.append(f"  - `{theme}` — {total} in window, {recent_n} in last 50")
    else:
        lines.append("- No strong standing themes yet — keep tagging.")

    top_goals = ", ".join(f"`{g}`×{c}" for g, c in goal_counts.most_common(8))
    lines.extend(
        [
            f"- Top goals in window: {top_goals or 'n/a'}",
            "",
            "## Delivery defaults (from history)",
            "",
            "1. Tag every user prompt (goal / affect / themes / delivery contract).",
            "2. If the same ask appears in the last 5–20 prompts, treat it as **still open** — do not rediscover; finish it.",
            "3. Frustrated/mad/corrective ⇒ obey the constraint, update `preferences.md` / skills, never repeat the miss.",
            "4. Meta-skill asks (SuperDev / memory / intention) ⇒ modify the skill files in the same turn; STAMP.",
            "5. Ship-lane asks with a PR/branch ⇒ Path 5.5 audit-first before smoke/push/reply.",
            "6. Owned issue ship lane ⇒ open the PR after Path 5.5 Ship without a second ask "
            "(#9036 miss). Merge still needs an explicit ask; pause words override.",
            "7. After every push/PR-create, `reconcile_push_intention.py`. Gaps ⇒ learn-kind "
            "`miss` and Path 6 is not done. Chat tags lose to the commit + files + PR body.",
            "",
            "## Affect histogram (window)",
            "",
        ]
    )
    for label, count in affect_counts.most_common():
        lines.append(f"- {label}: {count}")

    lines.extend(["", "## Goal histogram (window)", ""])
    for label, count in goal_counts.most_common():
        lines.append(f"- {label}: {count}")

    lines.extend(["", "## Theme histogram (window)", ""])
    if theme_counts:
        for label, count in theme_counts.most_common():
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- (none yet)")

    # Last 10 summaries for quick REPLAY
    lines.extend(["", "## Last 10 prompts (summary)", ""])
    for r in window[-10:]:
        lines.append(
            f"- [{r.get('affect', '?')}] {','.join(r.get('goals') or [])} — {r.get('summary', '')}"
        )

    lines.extend(
        [
            "",
            "## Skill adaptation rule",
            "",
            "When a prompt teaches a durable preference or repeatedly missed",
            "behavior, update the owning skill **in the same turn**:",
            "",
            "| Signal | Write to |",
            "| ------ | -------- |",
            "| How Rishi wants agents to behave | `local-memory/preferences.md` |",
            "| SuperDev lifecycle / Path gates | `turbovets-superdev/SKILL.md` |",
            "| Memory loop / ROUTE / INTENT | `local-memory/SKILL.md` |",
            "| Ticket/lane fit | `hrishi-memory/learned.md` |",
            "| Recurring intention themes | this file (`intention-model.md`) |",
            "",
            "Never store private (non-@turbovets.com) mail or secrets in prompt history.",
            "",
        ]
    )
    return "\n".join(lines)


def write_model(rows: list[dict]) -> None:
    INTENT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(distill(rows), encoding="utf-8")


def bootstrap(limit: int = DEFAULT_CAP, cap: int = DEFAULT_CAP) -> int:
    roots = list(Path.home().joinpath(".cursor/projects").glob("*/agent-transcripts"))
    user_query_re = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.S)
    ts_re = re.compile(r"<timestamp>(.*?)</timestamp>")
    skip_prefixes = (
        "Briefly inform the user about the task result",
        "Perform any necessary follow-up actions",
        "The user has manually attached",
    )

    collected: list[dict] = []
    for root in roots:
        for jf in root.rglob("*.jsonl"):
            try:
                mtime = jf.stat().st_mtime
            except OSError:
                continue
            with jf.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("role") != "user":
                        continue
                    content = obj.get("message", {}).get("content")
                    if isinstance(content, list):
                        texts = [
                            c.get("text") or ""
                            for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        ]
                        text = "\n".join(texts)
                    elif isinstance(content, str):
                        text = content
                    else:
                        continue
                    m = user_query_re.search(text)
                    prompt = (m.group(1).strip() if m else text.strip())
                    if not m:
                        prompt = re.sub(
                            r"<manually_attached_skills>.*?</manually_attached_skills>",
                            "",
                            prompt,
                            flags=re.S,
                        ).strip()
                        prompt = re.sub(r"<timestamp>.*?</timestamp>", "", prompt, flags=re.S).strip()
                    if not prompt or len(prompt) < 12:
                        continue
                    if any(prompt.startswith(p) for p in skip_prefixes):
                        continue
                    ts_m = ts_re.search(text)
                    ts = ts_m.group(1) if ts_m else datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
                    collected.append(
                        {
                            "mtime": mtime,
                            "ts": ts,
                            "prompt": prompt,
                            "transcript_id": jf.parent.name,
                        }
                    )

    collected.sort(key=lambda e: e["mtime"])  # oldest → newest for append order
    # Deduplicate preserving newest
    seen: set[str] = set()
    ordered: list[dict] = []
    for e in reversed(collected):
        key = re.sub(r"\s+", " ", e["prompt"][:300]).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(e)
    ordered = list(reversed(ordered))[-limit:]

    rows: list[dict] = []
    for e in ordered:
        tags = classify(e["prompt"])
        rows.append(
            {
                "id": f"{e['ts']}-{abs(hash(e['prompt'][:80])) % 10_000_000:07d}",
                "ts": e["ts"],
                "source": "transcript_bootstrap",
                "transcript_id": e["transcript_id"],
                "prompt": e["prompt"][:4000],
                "summary": tags["summary"],
                "affect": tags["affect"],
                "goals": tags["goals"],
                "themes": tags["themes"],
                "delivery": tags["delivery"],
            }
        )
    write_history(rows, cap=cap)
    write_model(rows)
    return len(rows)


def replay(limit: int = REPLAY_DEFAULT) -> str:
    rows = load_history()
    window = rows[-limit:]
    lines = [f"## Intention replay (last {len(window)} of {len(rows)})", ""]
    for r in window:
        goals = ",".join(r.get("goals") or [])
        themes = ",".join(r.get("themes") or []) or "-"
        lines.append(
            f"- [{r.get('affect')}] goals={goals} themes={themes} :: {r.get('summary')}"
        )
    if MODEL_PATH.exists():
        lines.extend(["", "---", "", MODEL_PATH.read_text(encoding="utf-8")])
    return "\n".join(lines)


def append_learning(
    learned: str,
    files: list[str] | None,
    kind: str,
    prompt_summary: str | None,
) -> dict:
    """Principle 0: every turn ends with a written learning delta (or an
    explicit no-learning row with the reason in `learned`, kind=none)."""
    INTENT_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "learned": learned[:600],
        "files_changed": files or [],
        "prompt_summary": (prompt_summary or "")[:200],
    }
    with LEARN_LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def learn_replay(limit: int) -> str:
    if not LEARN_LEDGER_PATH.exists():
        return "learn ledger empty"
    rows = [
        json.loads(line)
        for line in LEARN_LEDGER_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][-limit:]
    lines = [f"## Learn ledger (last {len(rows)})", ""]
    for r in rows:
        files = ",".join(r.get("files_changed") or []) or "-"
        lines.append(f"- {r['ts']} [{r['kind']}] {r['learned']} (files: {files})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", help="User prompt text to tag and append")
    parser.add_argument("--source", default="live", help="live | push — push = classify the shipped artifact")
    parser.add_argument("--affect", help="Override affect tag")
    parser.add_argument("--goal", action="append", dest="goals", help="Override/add goal tag (repeatable)")
    parser.add_argument("--bootstrap", action="store_true", help="Seed history from agent transcripts")
    parser.add_argument("--distill-only", action="store_true", help="Rebuild intention-model.md only")
    parser.add_argument("--replay", action="store_true", help="Print recent tagged prompts + model")
    parser.add_argument("--limit", type=int, default=DEFAULT_CAP, help="Bootstrap/replay limit")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP, help="Max prompts retained")
    parser.add_argument("--learn", help="Append a learning delta to the learn ledger (Principle 0)")
    parser.add_argument(
        "--learn-file",
        action="append",
        dest="learn_files",
        help="File changed by this learning (repeatable)",
    )
    parser.add_argument(
        "--learn-kind",
        default="skill_update",
        choices=["skill_update", "preference", "memory", "model_entry", "script", "miss", "none"],
        help="Kind of learning delta (use 'none' with the reason in --learn)",
    )
    parser.add_argument("--learn-replay", action="store_true", help="Print recent learn-ledger rows")
    args = parser.parse_args()

    if args.learn_replay:
        print(learn_replay(limit=min(args.limit, 100)))
        return 0

    if args.learn:
        row = append_learning(args.learn, args.learn_files, args.learn_kind, args.prompt)
        print(json.dumps(row, ensure_ascii=False))
        if not args.prompt:
            return 0

    if args.bootstrap:
        n = bootstrap(limit=args.limit, cap=args.cap)
        print(f"bootstrapped {n} prompts → {HISTORY_PATH}")
        print(f"distilled model → {MODEL_PATH}")
        return 0

    if args.distill_only:
        rows = load_history()
        write_model(rows)
        print(f"distilled {len(rows)} prompts → {MODEL_PATH}")
        _refresh_context_pack()
        return 0

    if args.replay:
        sys.stdout.write(replay(limit=min(args.limit, args.cap)) + "\n")
        return 0

    if not args.prompt:
        parser.error("provide --prompt, or use --bootstrap / --distill-only / --replay")

    record = append_record(
        args.prompt,
        affect=args.affect,
        goals=args.goals,
        source=args.source,
        cap=args.cap,
    )
    write_model(load_history())
    _refresh_context_pack()
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def _refresh_context_pack() -> None:
    """Keep active-context.md fresh so SuperDev can boot without session-log."""
    script = MEMORY / "scripts" / "emit_context_pack.py"
    if not script.exists():
        return
    import subprocess

    try:
        subprocess.run(
            [sys.executable, str(script), "--write", "--budget", "2200"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
