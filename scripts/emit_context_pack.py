#!/usr/bin/env python3
"""Emit a tiny SuperDev / local-memory context pack (token saver).

Replaces reading session-log.md (1000+ lines), full intention-model, and
focus.md wall-of-text on every turn. Agents should run this FIRST and only
open larger files when the pack says a field is missing / stale.

Usage:
  python3 emit_context_pack.py              # print markdown to stdout
  python3 emit_context_pack.py --write      # also write user-intentions/active-context.md
  python3 emit_context_pack.py --json       # machine-readable
  python3 emit_context_pack.py --budget 1200  # soft char budget for body
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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

FOCUS = MEMORY / "focus.md"
PREFS = MEMORY / "preferences.md"
MODEL = INTENT / "intention-model.md"
HISTORY = INTENT / "prompt-history.jsonl"
ACTIVE = INTENT / "active-context.md"
STATE_JSON = MEMORY / "state.json"
WORK_ACTIVE = WORK_HISTORY / "active.md"


def _clip(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _focus_digest(limit_chars: int = 900) -> str:
    if not FOCUS.exists():
        return "(no focus.md)"
    text = FOCUS.read_text()
    # Prefer "## Do next" block + Active lane header rows that are not MERGED/CLOSED
    do_next = ""
    m = re.search(r"## Do next\n(.*?)(?=\n## |\Z)", text, re.S)
    if m:
        do_next = m.group(1).strip()
    active_bits: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        low = line.lower()
        if any(x in low for x in ("priority", "---")):
            continue
        if any(
            x in low
            for x in (
                "**merged**",
                "merged ",
                "**closed**",
                "abandoned",
                "queued to merge",
            )
        ):
            # skip terminal noise unless it's "awaiting" / open / ship
            if not any(y in low for y in ("awaiting", "open", "ship", "gap", "path 6")):
                continue
        # keep open / awaiting / gap rows
        if any(
            y in low
            for y in (
                "awaiting",
                "open",
                "ship",
                "gap",
                "path 6",
                "**02**",
                "**03**",
                "stacked",
                "hygiene",
            )
        ):
            # compress cells
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3:
                active_bits.append(
                    f"- [{_clip(cells[0], 24)}] {_clip(cells[1], 28)} — {_clip(cells[2], 160)}"
                )
        if len(active_bits) >= 6:
            break
    parts = []
    if active_bits:
        parts.append("### Open / awaiting\n" + "\n".join(active_bits))
    if do_next:
        parts.append("### Do next\n" + _clip(do_next, 500))
    body = "\n\n".join(parts) if parts else _clip(text, limit_chars)
    return _clip(body, limit_chars)


def _standing_themes(limit: int = 6) -> list[str]:
    if not MODEL.exists():
        return []
    text = MODEL.read_text()
    themes = re.findall(r"`([a-z0-9_]+)`\s+—\s+(\d+)\s+in window", text)
    themes.sort(key=lambda x: int(x[1]), reverse=True)
    return [f"{name} ({count})" for name, count in themes[:limit]]


def _delivery_defaults(limit: int = 6) -> list[str]:
    if not MODEL.exists():
        return []
    text = MODEL.read_text()
    m = re.search(r"## Delivery defaults.*?\n((?:(?:\d+\.|-).*\n)+)", text, re.S)
    if not m:
        return []
    lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip()]
    return lines[:limit]


def _recent_prompts(limit: int = 8) -> list[dict]:
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text().splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "affect": o.get("affect"),
                "goals": o.get("goals") or [],
                "themes": o.get("themes") or [],
                "summary": _clip(o.get("summary") or o.get("prompt") or "", 140),
            }
        )
    return list(reversed(rows))


def _prefs_hard_rules(limit: int = 8) -> list[str]:
    if not PREFS.exists():
        return []
    text = PREFS.read_text()
    bullets = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- **") or s.startswith("- **"):
            bullets.append(_clip(re.sub(r"\s+", " ", s), 160))
        elif s.startswith("- ") and any(
            k in s.lower()
            for k in ("never", "hard", "always", "browser", "slack", "audit", "bot")
        ):
            bullets.append(_clip(re.sub(r"\s+", " ", s), 160))
        if len(bullets) >= limit:
            break
    return bullets


def _work_units_digest(limit: int = 4) -> str:
    if not WORK_ACTIVE.exists():
        return "(no work-history yet — run work_history.py --active)"
    lines = []
    for line in WORK_ACTIVE.read_text().splitlines():
        if line.startswith("|") and "unit |" not in line and "----" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6:
                lines.append(
                    f"- `{cells[0]}` [{cells[1]}/{cells[2]}] {cells[3]} · {cells[4]} — {_clip(cells[5], 72)}"
                )
        if len(lines) >= limit:
            break
    return "\n".join(lines) if lines else "(none open)"


def _state_freshness() -> dict:
    if not STATE_JSON.exists():
        return {}
    try:
        return json.loads(STATE_JSON.read_text())
    except json.JSONDecodeError:
        return {}


def build_pack(budget: int = 2600) -> dict:
    pack = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "token-saver boot context — prefer this over session-log / full skills",
        "focus": _focus_digest(900),
        "work_units": _work_units_digest(4),
        "standing_themes": _standing_themes(),
        "delivery_defaults": _delivery_defaults(),
        "recent_prompts": _recent_prompts(8),
        "hard_rules": _prefs_hard_rules(8),
        "state_keys": sorted(_state_freshness().keys())[:12],
        "load_next_only_if_needed": {
            "grill_product": "turbovets-superdev/references/grill-and-scales.md + rulings rg",
            "vets_product_law": "turbovets-superdev/references/standing-product.md",
            "session_detail": "local-memory/session-log.md (tail only)",
            "full_focus": "local-memory/focus.md",
            "work_history": "local-memory/work-history/active.md + work_history.py",
            "contradictions": "check_contradictions.py (warn before ACT)",
            "resources": "resource_status.py → /teardown-worktree or /coder-box",
            "superdev_boot": "turbovets-superdev/BOOT.md (prefer over full SKILL)",
            "full_superdev": "turbovets-superdev/SKILL.md (path section only; no reread if attached)",
        },
    }
    # Soft budget: shrink recent_prompts if over
    md = render_md(pack)
    while len(md) > budget and pack["recent_prompts"]:
        pack["recent_prompts"].pop()
        md = render_md(pack)
    pack["approx_chars"] = len(md)
    return pack


def render_md(pack: dict) -> str:
    lines = [
        "# Active context pack (token-saver)",
        "",
        f"_Generated: {pack['generated_at']}_ · ~{pack.get('approx_chars', '?')} chars",
        "",
        "## Focus (compressed)",
        pack["focus"],
        "",
        "## Open work units",
        pack.get("work_units") or "(none)",
        "",
        "## Standing themes",
        ", ".join(pack["standing_themes"]) or "(none)",
        "",
        "## Delivery defaults",
    ]
    for d in pack["delivery_defaults"]:
        lines.append(f"- {d}")
    lines += ["", "## Recent prompts (newest first)"]
    for r in pack["recent_prompts"]:
        goals = ",".join(r.get("goals") or [])
        themes = ",".join(r.get("themes") or []) or "-"
        lines.append(
            f"- [{r.get('affect')}] goals={goals} themes={themes} :: {r.get('summary')}"
        )
    lines += ["", "## Hard rules (compressed)"]
    for h in pack["hard_rules"]:
        lines.append(h if h.startswith("-") else f"- {h}")
    lines += [
        "",
        "## Load next ONLY if needed",
    ]
    for k, v in pack["load_next_only_if_needed"].items():
        lines.append(f"- `{k}` → {v}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--budget", type=int, default=2400)
    args = ap.parse_args()
    pack = build_pack(budget=args.budget)
    if args.json:
        json.dump(pack, sys.stdout, indent=2)
        print()
    else:
        md = render_md(pack)
        # recompute chars after final render
        pack["approx_chars"] = len(md)
        md = render_md(pack)
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
        if args.write:
            INTENT.mkdir(parents=True, exist_ok=True)
            ACTIVE.write_text(md)
            print(f"# wrote {ACTIVE} ({len(md)} chars)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
