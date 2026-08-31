#!/usr/bin/env python3
"""Battle Rhythm gates for SuperDev Path 5 (Agentic Coding corpus 2026).

Deterministic I/O per gate. Exit 1 = stop and ask the human.
Does not clone Codex-as-IDE — Cursor SuperDev stays the operator.

  kickoff       require 2PRD file; stamp unit
  recon         print read-only recon checklist (no code)
  harness       scaffold epic prd.md + task_flow.md + work log
  setup-green   prove stack is up (or --skip-reason)
  fail          record a failed auto-fix; exit 1 at 3
  fail-status   print counts for a unit
  deviate       diff vs 2PRD; warn/fail on architectural drift
  smoke-script  emit human smoke checklist from 2PRD
  miss          append a dated failure-pattern
  patterns      list active / archived patterns
  capture       remind Capture gate (STAMP + file:line index)
  promote       lessons with >2 learn-ledger hits (SKILL.md candidates)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

from lib_paths import INTENT, SKILL_HOME, WORK_HISTORY, ensure_state

ensure_state()
HOME = pathlib.Path.home()
SD = SKILL_HOME
MEM = SKILL_HOME / "state"
FAIL_PATH = WORK_HISTORY / "fail-counts.json"
EPICS = WORK_HISTORY / "epics"
ARCHIVE = SD / "references" / "pattern-archive.jsonl"
LEDGER = INTENT / "learn-ledger.jsonl"
MAX_FAIL = 3


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: pathlib.Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def require_prd(path: str | None) -> pathlib.Path:
    if not path:
        sys.exit("need --prd (2PRD file — Path 3 grill report, not a chat dump)")
    p = pathlib.Path(path).expanduser()
    if not p.is_file() or p.stat().st_size < 80:
        sys.exit(f"2PRD missing or too thin: {p}")
    return p


def cmd_kickoff(args: argparse.Namespace) -> int:
    prd = require_prd(args.prd)
    print(f"KICKOFF ok · unit={args.unit} · 2PRD={prd}")
    print("Human gate: confirm this ticket is the only work in this worktree.")
    print("UI? TDS Artifacts proto before Angular (Brandon Jul 17).")
    return 0


def cmd_recon(args: argparse.Namespace) -> int:
    prd = require_prd(args.prd)
    print("RECON (read-only — no code yet)")
    print(f"2PRD: {prd}")
    print("- precedent_lookup.py on target files / --subsystem")
    print("- live code + lessons as an INDEX (file:line), not a second codebase")
    print("- side-chat deep unknowns; this thread stays the decision log")
    print("Human gate: approve the plan before Implement.")
    return 0


def cmd_harness(args: argparse.Namespace) -> int:
    unit = args.unit
    if not unit:
        sys.exit("need --unit")
    dest = EPICS / unit
    dest.mkdir(parents=True, exist_ok=True)
    prd = dest / "prd.md"
    flow = dest / "task_flow.md"
    log = dest / "work-log.md"
    if not prd.exists():
        prd.write_text(
            f"# 2PRD — {unit}\n\nPaste the Path 3 grill report here. Chat is not the artifact.\n"
        )
    if not flow.exists():
        flow.write_text(
            f"# Task flow — {unit}\n\n"
            "- [ ] ticket A (this worktree)\n"
            "- [ ] ticket B (separate worktree; inherits this 2PRD)\n"
        )
    if not log.exists():
        log.write_text(f"# Work log — {unit}\n\nAppend after each ticket so the next agent inherits decisions.\n")
    print(f"HARNESS {dest}")
    print("One ticket per worktree. Do not fold ticket B into this tree.")
    return 0


def cmd_setup_green(args: argparse.Namespace) -> int:
    if args.skip_reason:
        print(f"SETUP-GREEN skipped · {args.skip_reason}")
        return 0
    url = args.url or "https://local.turbo.io/"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:
            code = resp.status
    except Exception as exc:
        print(f"SETUP-GREEN fail · {url} · {exc}")
        print("Prove stack green from logs, or re-run with --skip-reason.")
        return 1
    if code >= 500:
        print(f"SETUP-GREEN fail · {url} → {code}")
        return 1
    print(f"SETUP-GREEN ok · {url} → {code}")
    return 0


def cmd_fail(args: argparse.Namespace) -> int:
    unit = args.unit or "_"
    key = args.key
    data = load_json(FAIL_PATH, {})
    slot = data.setdefault(unit, {})
    n = int(slot.get(key, 0)) + 1
    slot[key] = n
    slot["_updated"] = now()
    save_json(FAIL_PATH, data)
    print(f"FAIL {unit}/{key} = {n}/{MAX_FAIL}")
    if n >= MAX_FAIL:
        print("3-failure: stop auto-fixing. Ask the human.")
        return 1
    return 0


def cmd_fail_status(args: argparse.Namespace) -> int:
    data = load_json(FAIL_PATH, {})
    slot = data.get(args.unit or "_", {})
    print(json.dumps(slot, indent=2) if slot else "{}")
    return 0


def cmd_deviate(args: argparse.Namespace) -> int:
    prd = require_prd(args.prd)
    base = args.base or "origin/main"
    body = prd.read_text().lower()
    r = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(r.stderr.strip() or "git diff failed")
        return 1
    files = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    mentioned = set(re.findall(r"[a-z0-9_./-]+\.(?:ts|html|scss|json|md|yml)", body))
    surprise = [
        f
        for f in files
        if not any(m in f.lower() or f.lower().endswith(m) for m in mentioned)
        and "/spec." not in f
        and f.endswith((".ts", ".html", ".scss"))
    ]
    print(f"DEVIATE · {len(files)} files vs 2PRD · surprise={len(surprise)}")
    for f in surprise[:20]:
        print(f"  surprise: {f}")
    if surprise and args.strict:
        print("Plan-deviation: architectural drift is a human decision.")
        return 1
    if surprise:
        print("Warn only (pass --strict to fail). Confirm 2PRD still holds.")
    return 0


def cmd_smoke_script(args: argparse.Namespace) -> int:
    prd = require_prd(args.prd)
    print("# Human smoke checklist (generate before push; Path 6 records it)")
    print("| Step | On-screen title | Action | Expected |")
    print("| ---- | --------------- | ------ | -------- |")
    print("| 1 | Before | Navigate to surface in 2PRD | Baseline |")
    print("| 2 | After | Exercise the AC happy path | Fix visible |")
    print("| 3 | Edge | Empty / deny / error | No 500, copy true |")
    print(f"\n2PRD: {prd}")
    print("Never tag/request reviewers unless the operator names them this turn.")
    return 0


def append_jsonl(path: pathlib.Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row) + "\n")


def cmd_miss(args: argparse.Namespace) -> int:
    if not args.pattern:
        sys.exit("need --pattern")
    row = {
        "ts": now(),
        "pattern": args.pattern,
        "axis": args.axis or "",
        "status": "active",
        "source": args.source or "path-5-capture",
    }
    append_jsonl(ARCHIVE, row)
    print(f"PATTERN archived · {args.pattern}")
    return 0


def cmd_patterns(_args: argparse.Namespace) -> int:
    if not ARCHIVE.exists():
        print("(empty)")
        return 0
    counts: dict[str, int] = {}
    for line in ARCHIVE.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row.get("pattern", "")
        counts[key] = counts.get(key, 0) + 1
    for pat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{n:3}  {pat}")
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    print("CAPTURE gate")
    print("- STAMP session-log + record_intention.py --learn")
    print("- lessons point at file:line (KB is an index, not a second codebase)")
    print("- battle_rhythm.py miss --pattern '…' for a new failure family")
    print("- battle_rhythm.py promote  → SKILL.md only after >2 hits")
    if args.unit:
        print(f"unit={args.unit}")
    return 0


def normalize(s: str) -> str:
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return s[:96]


def cmd_promote(_args: argparse.Namespace) -> int:
    if not LEDGER.exists():
        print("(no learn-ledger)")
        return 0
    counts: dict[str, int] = {}
    samples: dict[str, str] = {}
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        learned = row.get("learned") or ""
        if not learned:
            continue
        key = normalize(learned)
        counts[key] = counts.get(key, 0) + 1
        samples[key] = learned
    hits = [(n, samples[k]) for k, n in counts.items() if n >= 3]
    hits.sort(reverse=True)
    if not hits:
        print("No lesson has >2 hits yet. STAMP every turn; promote on recurrence.")
        return 0
    print("Promote to SKILL.md (replace prose, don't accrete):")
    for n, text in hits:
        print(f"{n:3}  {text[:160]}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("kickoff")
    k.add_argument("--unit")
    k.add_argument("--prd")
    k.set_defaults(func=cmd_kickoff)

    r = sub.add_parser("recon")
    r.add_argument("--prd")
    r.set_defaults(func=cmd_recon)

    h = sub.add_parser("harness")
    h.add_argument("--unit", required=True)
    h.set_defaults(func=cmd_harness)

    s = sub.add_parser("setup-green")
    s.add_argument("--url")
    s.add_argument("--skip-reason")
    s.set_defaults(func=cmd_setup_green)

    f = sub.add_parser("fail")
    f.add_argument("--unit")
    f.add_argument("--key", required=True, help="lint | test | peer-review | ci")
    f.set_defaults(func=cmd_fail)

    fs = sub.add_parser("fail-status")
    fs.add_argument("--unit")
    fs.set_defaults(func=cmd_fail_status)

    d = sub.add_parser("deviate")
    d.add_argument("--prd")
    d.add_argument("--base", default="origin/main")
    d.add_argument("--strict", action="store_true")
    d.set_defaults(func=cmd_deviate)

    sm = sub.add_parser("smoke-script")
    sm.add_argument("--prd")
    sm.set_defaults(func=cmd_smoke_script)

    m = sub.add_parser("miss")
    m.add_argument("--pattern", required=True)
    m.add_argument("--axis")
    m.add_argument("--source")
    m.set_defaults(func=cmd_miss)

    sub.add_parser("patterns").set_defaults(func=cmd_patterns)

    c = sub.add_parser("capture")
    c.add_argument("--unit")
    c.set_defaults(func=cmd_capture)

    sub.add_parser("promote").set_defaults(func=cmd_promote)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
