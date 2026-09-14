#!/usr/bin/env python3
"""Fail if prose claims a greener lane state than lane_truth.

Zero hallucination is a system property. This script is the non-LLM check
(HALO layer 3 / Anthropic "ground truth from the environment").

  python3 claim_lint.py --ticket 11206 --text-file /tmp/summary.md
  python3 claim_lint.py --ticket 11206 --text "L1 Ship. Ready for review."
  python3 claim_lint.py --self-check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

GREENER = (
    (re.compile(r"ready for human review|path 6 complete|all (four|five) green|\bdone:\s*true", re.I), "done"),
    (re.compile(r"\bL1\b.{0,40}\b(ship|recorded|stamped|green)\b|\brecorded L1\b", re.I), "l1"),
    (re.compile(r"\bL3\b.{0,40}\b(approve|recorded|stamped|green)\b|\brecorded L3\b", re.I), "l3"),
    (re.compile(r"\b6a\b.{0,40}\b(done|recorded|clicked|green)\b|\brecorded 6a\b", re.I), "qa"),
    (re.compile(r"\b6b\b.{0,40}\b(done|recorded|green|player)\b|\bsmoke (done|recorded|green)\b", re.I), "smoke"),
)


def short(sha: str) -> str:
    return (sha or "")[:12].lower()


def live_row(ticket: str) -> dict:
    raw = subprocess.check_output(
        [sys.executable, str(HERE / "lane_truth.py")],
        text=True,
    )
    data = json.loads(raw or "{}")
    for row in data.get("tickets") or []:
        if str(row.get("ticket")) == str(ticket):
            return row
    raise SystemExit(f"ticket {ticket} not in lane_truth")


def bound(row: dict, key: str) -> bool:
    head = short(row.get("head") or "")
    if key == "done":
        return bool(row.get("done"))
    return bool(head and short(row.get(f"{key}_sha") or "") == head)


def lint(text: str, row: dict) -> list[str]:
    misses: list[str] = []
    for pat, key in GREENER:
        if pat.search(text) and not bound(row, key):
            nxt = row.get("next") or "unset"
            misses.append(f"CLAIM {key} green · FACT next={nxt} head={short(row.get('head') or '')}")
    head = short(row.get("head") or "")
    for m in re.finditer(r"\bHEAD\b.{0,20}([0-9a-f]{7,40})", text, re.I):
        if head and short(m.group(1)) != head:
            misses.append(f"CLAIM HEAD {m.group(1)} · FACT {head}")
    return misses


def self_check() -> int:
    stale = {
        "head": "aaaaaaaaaaaa",
        "next": "L1",
        "done": False,
        "l1_sha": "bbbbbbbbbbbb",
        "l3_sha": "",
        "qa_sha": "",
        "smoke_sha": "",
        "e2e_sha": "",
        "pr_sha": "aaaaaaaaaaaa",
    }
    assert lint("working the lock", stale) == []
    assert lint("L1 Ship on this HEAD", stale)
    assert lint("Ready for human review", stale)
    fresh = {**stale, "l1_sha": "aaaaaaaaaaaa", "next": "L3"}
    assert lint("L1 recorded", fresh) == []
    assert lint("L1 Ship on HEAD bbbbbbbbbbbb", stale)
    print("self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket")
    ap.add_argument("--text")
    ap.add_argument("--text-file")
    ap.add_argument("--facts-json", help="Skip live lane_truth (tests)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    text = args.text or ""
    if args.text_file:
        text = Path(args.text_file).read_text()
    if not text.strip():
        raise SystemExit("pass --text or --text-file")
    row = json.loads(Path(args.facts_json).read_text()) if args.facts_json else live_row(args.ticket or "")
    misses = lint(text, row)
    if misses:
        print("CLAIM ≠ FACT")
        for miss in misses:
            print(f"- {miss}")
        return 1
    print("ok — no greener-than-facts claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
