#!/usr/bin/env python3
"""Cursor stop hook: resume SuperDev if the focus ticket is still open."""

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

from turn_gate import (  # noqa: E402
    STALE_S,
    focus_path,
    load_json,
    receipt_age_s,
    receipt_path,
    row_from_store,
    superdev_session_on,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("{}")
        return 0
    if payload.get("status") == "aborted":
        print("{}")
        return 0
    if int(payload.get("loop_count") or 0) >= 8:
        print("{}")
        return 0
    if not superdev_session_on():
        print("{}")
        return 0
    focus = load_json(focus_path(), {})
    ticket = str(focus.get("ticket") or "")
    if not ticket:
        print("{}")
        return 0
    row = row_from_store(ticket, focus.get("worktree") or "")
    if row.get("done"):
        print("{}")
        return 0
    age = receipt_age_s()
    rec = load_json(receipt_path(), {})
    stale = age is None or age > STALE_S or not rec.get("ok")
    if not stale and str(rec.get("ticket")) == ticket:
        print("{}")
        return 0
    nxt = row.get("next") or "L1"
    msg = (
        f"TURN_GATE stale. #{ticket} next {nxt}. "
        "Resume that step. Do not write a status essay. "
        "After the next draft run turn_gate.py --ticket "
        f"{ticket} --text-file <draft>."
    )
    print(json.dumps({"followup_message": msg}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
