#!/usr/bin/env python3
"""The only legal end of a SuperDev turn.

Runs claim_lint + halt_lint on the draft, writes a receipt. No
TURN_GATE: PASS in this turn's tool output ⇒ do not send the reply.

  turn_gate.py --ticket 8510 --text-file /tmp/reply.md [--bot-log <log>]
  turn_gate.py --status [--fail-stale]
  turn_gate.py --set-focus 8510 --worktree /path/to/worktree
  turn_gate.py --adopt-focus
  turn_gate.py --self-check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from claim_lint import lint as claim_lint  # noqa: E402
from halt_lint import lint_bot_log, lint_leftover_prove, lint_reply  # noqa: E402
from lib_paths import SESSION, WORK_HISTORY, lane_dir, worktree_parent  # noqa: E402

STALE_S = 20 * 60
ARTIFACTS = ("l1", "l3", "qa", "smoke", "e2e")
NAMES = {"l1": "L1", "l3": "L3", "qa": "6a", "smoke": "6b", "e2e": "e2e"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return fallback


def short(sha: str) -> str:
    return (sha or "")[:12]


def git_head(wt: str) -> str:
    if not wt:
        return ""
    try:
        return subprocess.check_output(
            ["git", "-C", wt, "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return ""


def focus_path() -> Path:
    return lane_dir() / "focus.json"


def receipt_path() -> Path:
    return lane_dir() / "turn-gate.json"


def row_from_store(ticket: str, wt: str = "") -> dict:
    stored = load_json(lane_dir() / "truth.json", {})
    rec = stored.get(str(ticket)) or {}
    head = git_head(wt) or rec.get("head") or ""
    bound = {k: rec.get(f"{k}_sha") or "" for k in ARTIFACTS}
    next_art = ""
    for k in ARTIFACTS:
        if short(bound[k]) != short(head) or not head:
            next_art = k
            break
    pr = rec.get("pr") or ""
    if not pr:
        next_art = next_art if next_art and next_art != "e2e" else "pr"
    done = bool(head and pr and not next_art)
    return {
        "ticket": ticket,
        "head": head,
        "next": NAMES.get(next_art, next_art or "done"),
        "done": done,
        "pr": pr,
        "l1_sha": bound["l1"],
        "l3_sha": bound["l3"],
        "qa_sha": bound["qa"],
        "smoke_sha": bound["smoke"],
        "e2e_sha": bound["e2e"],
        "worktree": wt,
    }


def write_focus(ticket: str, worktree: str = "") -> dict:
    path = focus_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ticket": str(ticket),
        "worktree": worktree,
        "updatedAt": now_iso(),
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data


def adopt_focus() -> dict | None:
    latest: dict[str, dict] = {}
    units = WORK_HISTORY / "units.jsonl"
    if not units.exists():
        return None
    for line in units.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        uid = ev.get("unit_id")
        if uid:
            latest[uid] = ev
    best = None
    for ev in latest.values():
        if ev.get("status") not in {"active", "idle"}:
            continue
        if not ev.get("issue") or not ev.get("worktree"):
            continue
        best = ev
    if not best:
        return None
    wt = best.get("worktree") or ""
    if wt and not Path(wt).is_absolute():
        guess = worktree_parent() / Path(wt).name
        wt = str(guess) if guess.is_dir() else wt
    return write_focus(str(best["issue"]), wt)


def receipt_age_s() -> float | None:
    rec = load_json(receipt_path(), {})
    raw = rec.get("ts")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds()


def superdev_session_on() -> bool:
    return SESSION.exists() or focus_path().exists()


def write_receipt(ticket: str, text: str, ok: bool, misses: list[str]) -> None:
    path = receipt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ts": now_iso(),
                "ticket": str(ticket),
                "ok": ok,
                "draft_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
                "misses": misses,
            },
            indent=2,
        )
        + "\n"
    )


def gate(ticket: str, text: str, bot_log: str = "") -> list[str]:
    focus = load_json(focus_path(), {})
    wt = focus.get("worktree") or ""
    row = row_from_store(ticket, wt)
    misses = claim_lint(text, row)
    misses.extend(lint_reply(text, bool(row.get("done"))))
    misses.extend(
        lint_leftover_prove(text, str(row.get("next") or ""), bool(row.get("done")))
    )
    if bot_log:
        misses.extend(lint_bot_log(bot_log))
    return misses


def self_check() -> int:
    row = {
        "head": "aaaaaaaaaaaa",
        "next": "L1",
        "done": False,
        "l1_sha": "",
        "l3_sha": "",
        "qa_sha": "",
        "smoke_sha": "",
        "e2e_sha": "",
        "pr": "",
    }
    assert claim_lint("working the lock", row) == []
    assert claim_lint("L1 Ship on this HEAD", row)
    assert lint_reply("L3 did not clear. Ask Rishi claude /login.", False)
    print("self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket")
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--bot-log")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--fail-stale", action="store_true")
    ap.add_argument("--set-focus")
    ap.add_argument("--worktree", default="")
    ap.add_argument("--adopt-focus", action="store_true")
    ap.add_argument("--clear-focus", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if args.clear_focus:
        focus_path().unlink(missing_ok=True)
        print("focus cleared")
        return 0
    if args.set_focus:
        print(json.dumps(write_focus(args.set_focus, args.worktree)))
        return 0
    if args.adopt_focus:
        data = adopt_focus()
        print(json.dumps(data or {"focus": None}))
        return 0 if data else 1
    if args.status:
        age = receipt_age_s()
        rec = load_json(receipt_path(), {})
        stale = age is None or age > STALE_S or not rec.get("ok")
        print(
            json.dumps(
                {
                    "age_s": None if age is None else int(age),
                    "stale": stale,
                    "ok": rec.get("ok"),
                    "ticket": rec.get("ticket"),
                }
            )
        )
        return 1 if args.fail_stale and stale else 0
    text = args.text or ""
    if args.text_file:
        text = Path(args.text_file).read_text()
    bot = Path(args.bot_log).read_text(errors="replace") if args.bot_log else ""
    if not text.strip():
        raise SystemExit("pass --text or --text-file")
    ticket = str(args.ticket or load_json(focus_path(), {}).get("ticket") or "")
    if not ticket:
        raise SystemExit("pass --ticket or --set-focus first")
    misses = gate(ticket, text, bot)
    write_receipt(ticket, text, not misses, misses)
    if misses:
        print("TURN_GATE: FAIL")
        for miss in misses:
            print(f"- {miss}")
        return 1
    print("TURN_GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
