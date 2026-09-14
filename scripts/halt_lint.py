#!/usr/bin/env python3
"""Fail if a reply or bot log is a mid-lane halt.

claim_lint catches greener-than-facts claims. This catches the other miss:
the agent stopped (or the harness said "brief the user") while the lane
is still open.

  halt_lint.py --ticket 8510 --text-file /tmp/reply.md
  halt_lint.py --bot-log /tmp/local-review-claude.md
  halt_lint.py --self-check
  halt_lint.py --strict-advance
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from claim_lint import live_row  # noqa: E402
from advance_lane import scan  # noqa: E402

# Status-essay closers. A match without a resume verb is a halt.
HALT = re.compile(
    r"briefly inform|those background jobs were|l3 did not clear|"
    r"ask rishi.{0,60}(/login|claude)|oauth expired|"
    r"not this head.{0,80}(after|once|when)|"
    r"claude never (produced|ran|started)|"
    r"l1 spawned|fixer running|waiting on instance|"
    r"codex cr\b|claude 401|cloud (claude )?(401|skip)",
    re.I | re.S,
)
RESUME = re.compile(
    r"\b(re-?run (tv-fullstack|local-bot-review)|"
    r"resum(e|ing) .{0,60}([0-9a-f]{8}-[0-9a-f-]+|L1|L3|6a|6b)|"
    r"keep(ing)? (going|working) .{0,20}(L1|L3|6a|6b|tv-fullstack)|"
    r"spawn(ing)? .{0,40}(Task|L1|L3|finish))\b",
    re.I,
)
CLAUDE_START = re.compile(r"^>>> claude\b", re.M)
VERDICT = re.compile(r"^VERDICT:", re.M)


def lint_reply(text: str, done: bool) -> list[str]:
    if done or not HALT.search(text):
        return []
    if RESUME.search(text):
        return []
    return ["HALT status-essay · FACT next still open — resume, do not inform-and-stop"]


def lint_unread() -> list[str]:
    unread = [r for r in scan() if r["action"].startswith("ingest")]
    if not unread:
        return []
    tickets = ", ".join(str(r["ticket"]) for r in unread)
    return [f"HALT unread artifacts on {tickets} — open + --ingest this turn"]


def lint_bot_log(text: str) -> list[str]:
    misses: list[str] = []
    if CLAUDE_START.search(text):
        last_claude = text.rfind(">>> claude")
        tail = text[last_claude:]
        if not VERDICT.search(tail):
            misses.append(
                "HALT claude_abrupt — claude started, no VERDICT. "
                "Resume the bot. Do not treat L3 as reported."
            )
    elif ">>> claude" in text.lower() and not VERDICT.search(text):
        misses.append("HALT claude_abrupt — no VERDICT")
    return misses


def self_check() -> int:
    assert lint_reply("working the lock", False) == []
    assert lint_reply("L3 did not clear. Ask Rishi claude /login.", False)
    assert not lint_reply(
        "L3 did not clear. Re-run local-bot-review after login.", False
    )
    assert lint_reply("L3 did not clear. Re-run later.", False)
    assert lint_reply("all four green", True) == []
    assert lint_reply("L1 spawned. Codex CR, fixer running.", False)
    assert not lint_reply(
        "L1 spawned. Re-run tv-fullstack on this HEAD.", False
    )
    log = ">>> claude (opus) prompt: 12 bytes\n\nexit_code: 1\n"
    assert lint_bot_log(log)
    ok = ">>> claude (opus)\n## VERDICT\nVERDICT: APPROVE\n"
    assert lint_bot_log(ok) == []
    print("self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket")
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--bot-log")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--strict-advance", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    misses: list[str] = []
    if args.strict_advance or args.ticket:
        misses.extend(lint_unread())
    if args.bot_log:
        misses.extend(lint_bot_log(Path(args.bot_log).read_text(errors="replace")))
    text = args.text or ""
    if args.text_file:
        text = Path(args.text_file).read_text()
    if text.strip() and args.ticket:
        row = live_row(args.ticket)
        misses.extend(lint_reply(text, bool(row.get("done"))))
    elif text.strip() and not args.ticket:
        misses.extend(lint_reply(text, False))
    if not (args.bot_log or text.strip() or args.strict_advance):
        raise SystemExit("pass --text, --text-file, --bot-log, or --strict-advance")
    if misses:
        print("HALT")
        for miss in misses:
            print(f"- {miss}")
        return 1
    print("ok — not a halt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
