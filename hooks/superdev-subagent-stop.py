#!/usr/bin/env python3
"""Cursor subagentStop: parent keeps going if the focus ticket is open."""

from __future__ import annotations

import json
import sys
from pathlib import Path

for cand in (
    Path.home() / ".cursor/skills/superdev/scripts",
    Path.home() / ".cursor/skills/turbovets-superdev/scripts",
):
    if (cand / "turn_gate.py").exists():
        sys.path.insert(0, str(cand))
        break

from claim_lint import lint as claim_lint  # noqa: E402
from turn_gate import focus_path, load_json, row_from_store, superdev_session_on  # noqa: E402


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("{}")
        return 0
    if not superdev_session_on():
        print("{}")
        return 0
    if int(payload.get("loop_count") or 0) >= 8:
        print("{}")
        return 0
    focus = load_json(focus_path(), {})
    ticket = str(focus.get("ticket") or "")
    if not ticket:
        print("{}")
        return 0
    row = row_from_store(ticket, focus.get("worktree") or "")
    summary = payload.get("summary") or ""
    misses = claim_lint(summary, row) if summary else []
    status = payload.get("status") or ""
    if row.get("done") and not misses and status == "completed":
        print("{}")
        return 0
    nxt = row.get("next") or "L1"
    extra = f" CLAIM≠FACT: {misses[0]}." if misses else ""
    if status in {"error", "aborted"}:
        extra = f" Subagent {status}.{extra}"
    msg = (
        f"Subagent returned on #{ticket}. NEXT {nxt}.{extra} "
        "Open the artifact or resume. Do not --record. Do not ask."
    )
    print(json.dumps({"followup_message": msg}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
