#!/usr/bin/env python3
"""Gate every GitHub comment SuperDev posts against the house cap.

P0/P1 + file:line, one line each, <=1200 chars and <=10 non-empty lines.
Exempt: a smoke/screenshot evidence comment (before/after table + player)
and a direct question to a named teammate — pass --exempt with the reason.

    gh_comment_lint.py body.md [more.md ...]   # exit 1 if any body is over
    gh_comment_lint.py --exempt evidence b.md  # cap waived, still reports
    gh_comment_lint.py --selfcheck             # runnable check for this gate

Banned-phrase scan is advisory (reported, does not fail): round-by-round
narration, gate tallies and self-correction essays belong in Agent chat.
"""

from __future__ import annotations

import re
import sys

MAX_CHARS = 1200
MAX_LINES = 10
BANNED = [
    r"[Rr]eview round \d",
    r"\b\d+ checks?,? (green|pass)",
    r"\bCI (is )?green\b",
    r"two (independent )?Ship verdicts",
    r"\bmutation prob(e|ing) log",
    r"^#+ Verification$",
]


def measure(body: str) -> tuple[int, int, list[str]]:
    lines = [ln for ln in body.splitlines() if ln.strip()]
    flagged = [p for p in BANNED if re.search(p, body, re.MULTILINE)]
    return len(body), len(lines), flagged


def report(name: str, body: str, exempt: str | None) -> bool:
    chars, lines, flagged = measure(body)
    over = chars > MAX_CHARS or lines > MAX_LINES
    verdict = "EXEMPT" if (over and exempt) else ("OVER" if over else "ok")
    print(f"{verdict:6} {name}  {chars} chars / {lines} lines" + (f"  ({exempt})" if exempt else ""))
    for pattern in flagged:
        print(f"       advisory: banned phrase /{pattern}/ -- move it to Agent chat")
    return over and not exempt


def selfcheck() -> None:
    assert measure("x" * 1201)[0] > MAX_CHARS
    assert measure("\n\n".join(f"line {i}" for i in range(11)))[1] == 11
    assert measure("a\n\n\nb")[1] == 2, "blank lines must not count toward the cap"
    assert report("t", "x" * 1201, None) is True, "over-cap body must fail"
    assert report("t", "x" * 1201, "evidence") is False, "exempt body must pass"
    assert report("t", "short", None) is False
    assert measure("Review round 4 went well")[2], "banned phrase must be flagged"
    print("selfcheck ok")


def main(argv: list[str]) -> int:
    if "--selfcheck" in argv:
        selfcheck()
        return 0
    exempt = None
    if argv and argv[0] == "--exempt":
        exempt, argv = argv[1], argv[2:]
    paths = argv or ["-"]
    failed = False
    for path in paths:
        body = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
        failed |= report(path, body, exempt)
    if failed:
        print("\nOver the house cap. Cut it -- never post the long one.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
