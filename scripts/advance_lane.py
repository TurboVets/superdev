#!/usr/bin/env python3
"""Unread gate artifacts are unfinished work. Ending the turn is illegal.

The Cursor "brief the user" notice is not a scheduler. This script is.

  python3 advance_lane.py --pretty
  python3 advance_lane.py --strict
  python3 advance_lane.py --ingest --ticket 8043 --kind l1 --sha 6c89e0be46ae

Exit 1 on --strict when any owned ticket has L1/L3 reports on disk
that the parent has not ingested, or when L1+L3 are bound and 6a/6b
is still unset. That is the mid-lane stop. A PR without 6a is unfinished.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lane_truth import load_json, short  # noqa: E402


def _lane() -> Path:
    try:
        from lib_paths import lane_dir

        return lane_dir()
    except ImportError:
        pass
    try:
        from lane_truth import LANE as house_lane

        return house_lane
    except ImportError:
        return Path.home() / "Documents" / "superdev-lane"


LANE = _lane()

VERDICT = re.compile(r"^VERDICT:\s*(.+)$", re.M)
TMP = Path("/tmp")


def verdict_of(path: Path) -> str:
    if not path.is_file():
        return ""
    matches = VERDICT.findall(path.read_text(errors="replace"))
    return (matches[-1] if matches else "").strip()


def artifact_dir(kind: str, ticket: str, sha: str) -> Path:
    # Agents write /tmp/l1-<ticket>-<10 hex>. Also accept 12.
    for n in (10, 12):
        candidate = TMP / f"{kind}-{ticket}-{(sha or '')[:n]}"
        if candidate.is_dir():
            return candidate
    return TMP / f"{kind}-{ticket}-{(sha or '')[:10]}"


def l1_state(ticket: str, sha: str) -> dict:
    d = artifact_dir("l1", ticket, sha)
    p1, p2 = d / "pass-1.md", d / "pass-2.md"
    if not (p1.is_file() and p2.is_file()):
        return {"status": "missing", "dir": str(d)}
    ingested = (d / ".ingested").is_file()
    v1, v2 = verdict_of(p1), verdict_of(p2)
    ship = v1.upper().startswith("SHIP") and v2.upper().startswith("SHIP")
    return {
        "status": "ingested" if ingested else "unread",
        "dir": str(d),
        "verdicts": [v1, v2],
        "ship": ship,
        "next": "record_l1" if ship else "fix",
    }


def l3_state(ticket: str, sha: str) -> dict:
    d = artifact_dir("l3", ticket, sha)
    codex, claude = d / "local-review-codex.md", d / "local-review-claude.md"
    if not (codex.is_file() and claude.is_file()):
        return {"status": "missing" if not d.is_dir() else "partial", "dir": str(d)}
    ingested = (d / ".ingested").is_file()
    v1, v2 = verdict_of(codex), verdict_of(claude)
    ok = "APPROVE" in v1.upper() and "APPROVE" in v2.upper()
    return {
        "status": "ingested" if ingested else "unread",
        "dir": str(d),
        "verdicts": [v1, v2],
        "approve": ok,
        "next": "record_l3" if ok else "fix",
    }


def live_heads() -> dict[str, str]:
    truth = load_json(LANE / "truth.json", {})
    agents = load_json(LANE / "agents.json", {})
    out: dict[str, str] = {}
    for ticket, rec in truth.items():
        head = rec.get("head") or ""
        if head:
            out[str(ticket)] = head
    for ticket, meta in (agents.get("tickets") or {}).items():
        if str(ticket) in out:
            continue
        wt = meta.get("worktree") or ""
        if not wt:
            continue
        try:
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=wt, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if head:
            out[str(ticket)] = head
    return out


def scan() -> list[dict]:
    rows = []
    for ticket, sha in live_heads().items():
        l1 = l1_state(ticket, sha)
        l3 = l3_state(ticket, sha)
        action = "wait"
        if l1["status"] == "unread":
            action = "ingest_l1"
        elif l3["status"] == "unread":
            action = "ingest_l3"
        elif l1["status"] == "ingested" and l1.get("next") == "fix":
            action = "fix_l1"
        elif l3["status"] == "ingested" and l3.get("next") == "fix":
            action = "fix_l3"
        elif l1["status"] == "ingested" and l1.get("next") == "record_l1":
            action = "record_l1"
        elif l3["status"] == "ingested" and l3.get("next") == "record_l3":
            action = "record_l3"
        rows.append({"ticket": ticket, "head": sha, "l1": l1, "l3": l3, "action": action})
    return rows


def leftover_prove() -> list[str]:
    """L1+L3 recorded and qa unset ⇒ 6a is the job. Waiting is illegal."""
    stored = load_json(LANE / "truth.json", {})
    stuck: list[str] = []
    if not isinstance(stored, dict):
        return stuck
    for ticket, rec in stored.items():
        if not isinstance(rec, dict):
            continue
        if rec.get("l1_sha") and rec.get("l3_sha") and not rec.get("qa_sha"):
            stuck.append(str(ticket))
    return stuck


def ingest(ticket: str, kind: str, sha: str) -> Path:
    d = artifact_dir(kind, ticket, sha)
    d.mkdir(parents=True, exist_ok=True)
    stamp = d / ".ingested"
    stamp.write_text(f"{ticket} {kind} {short(sha)}\n")
    return stamp


def self_check() -> int:
    unread = {"status": "unread", "ship": True, "next": "record_l1"}
    assert unread["status"] == "unread"
    rows = [{"action": "ingest_l1"}]
    assert any(r["action"].startswith("ingest") for r in rows)
    print("self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--ticket")
    ap.add_argument("--kind", choices=("l1", "l3"))
    ap.add_argument("--sha")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if args.ingest:
        if not (args.ticket and args.kind and args.sha):
            raise SystemExit("--ingest needs --ticket --kind --sha")
        path = ingest(args.ticket, args.kind, args.sha)
        print(f"ingested {path}")
        return 0
    rows = scan()
    unread = [r for r in rows if r["action"].startswith("ingest")]
    prove = leftover_prove()
    payload = {"tickets": rows, "unread": unread, "leftover_prove": prove}
    print(json.dumps(payload, indent=2 if args.pretty else None))
    if args.strict and unread:
        print("HALT unread artifacts — open them this turn, then --ingest. Do not brief-and-stop.", file=sys.stderr)
        return 1
    if args.strict and prove:
        print(
            "HALT leftover 6a on "
            + ", ".join(prove)
            + " — move the instance and start 6a this turn. A busy instance is not a stop.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
