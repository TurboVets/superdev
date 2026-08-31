#!/usr/bin/env python3
"""Detect contradictions across SuperDev local memory stores.

Compares focus.md, work-history units, live instance/worktree state, and
(optionally light) session claims. Prints WARN lines; exit 0 always unless
--strict (then exit 1 when severity=high).

Usage:
  python3 check_contradictions.py [--pretty] [--strict] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib_paths import STATE as MEMORY, WORK_HISTORY, ensure_state, workspace

ensure_state()
HOME = Path.home()
FOCUS = MEMORY / "focus.md"
SESSION = MEMORY / "session-log.md"
UNITS = WORK_HISTORY / "units.jsonl"
ACTIVE = WORK_HISTORY / "active.md"
WORKSPACE = workspace()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_units() -> list[dict]:
    if not UNITS.exists():
        return []
    rows = []
    for line in UNITS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _latest_open(rows: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for r in rows:
        uid = r.get("unit_id")
        if uid:
            latest[uid] = r
    return [
        u
        for u in latest.values()
        if u.get("status") in ("active", "blocked", "idle")
    ]


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or WORKSPACE),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"__error__:{e}"


def _parse_instances(text: str) -> list[dict]:
    # lines like: "  23  locked                    /Users/.../platform-9036"
    out = []
    for line in text.splitlines():
        m = re.match(
            r"^\s*(\d+)\s+(\S+(?:\s+\([^)]+\))?)\s+(\S.+)?\s*$",
            line,
        )
        if not m:
            continue
        iid = int(m.group(1))
        status = m.group(2).strip()
        wt = (m.group(3) or "").strip() or None
        if status.startswith("ID") or status.startswith("--"):
            continue
        out.append({"id": iid, "status": status, "worktree": wt})
    return out


def _worktree_paths() -> set[str]:
    text = _run(["git", "worktree", "list", "--porcelain"])
    paths = set()
    for line in text.splitlines():
        if line.startswith("worktree "):
            paths.add(line.split(" ", 1)[1].strip())
    return paths


def _focus_issue_states() -> dict[int, str]:
    """Map issue numbers mentioned in focus Active lane to coarse state."""
    if not FOCUS.exists():
        return {}
    states: dict[int, str] = {}
    text = FOCUS.read_text()
    # table rows
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        low = line.lower()
        nums = [int(n) for n in re.findall(r"#(\d{3,5})\b", line)]
        if not nums:
            continue
        state = "open"
        if any(x in low for x in ("**merged**", "merged ", "squash")):
            state = "merged"
        elif any(x in low for x in ("**closed**", "abandoned", "closed ")):
            state = "closed"
        elif "awaiting" in low:
            state = "awaiting"
        for n in nums:
            # keep strongest terminal state if duplicated
            prev = states.get(n)
            if prev in ("merged", "closed") and state == "open":
                continue
            states[n] = state
    return states


def _session_mentions_closed(issue: int) -> bool:
    if not SESSION.exists():
        return False
    # only scan last ~80 lines for token budget
    lines = SESSION.read_text().splitlines()[-80:]
    blob = "\n".join(lines).lower()
    patterns = [
        rf"#{issue}\b.*\b(merged|closed|shipped)\b",
        rf"\b(merged|closed|shipped)\b.*#{issue}\b",
        rf"pr #{issue}\b.*\b(merged|closed)\b",
    ]
    return any(re.search(p, blob) for p in patterns)


def collect() -> list[dict]:
    warnings: list[dict] = []
    rows = _load_units()
    open_units = _latest_open(rows)
    focus_states = _focus_issue_states()
    instances = _parse_instances(_run(["npm", "run", "instance:list"]))
    locked = {
        i["id"]: i
        for i in instances
        if "locked" in (i.get("status") or "").lower()
    }
    wt_paths = _worktree_paths()
    wt_by_name = {Path(p).name: p for p in wt_paths}

    # 1) Active work unit marked merged/closed in focus
    for u in open_units:
        issue = u.get("issue")
        pr = u.get("pr")
        for ref, kind in ((issue, "issue"), (pr, "pr")):
            if not ref:
                continue
            fs = focus_states.get(int(ref))
            if fs in ("merged", "closed"):
                warnings.append(
                    {
                        "severity": "high",
                        "code": "unit_open_but_focus_terminal",
                        "msg": (
                            f"work-history unit `{u.get('unit_id')}` is "
                            f"{u.get('status')} but focus.md marks #{ref} as {fs}"
                        ),
                        "fix": f"work_history.py --close --unit {u.get('unit_id')} --status shipped",
                    }
                )
            if kind == "issue" and _session_mentions_closed(int(ref)) and fs != "merged":
                warnings.append(
                    {
                        "severity": "medium",
                        "code": "session_says_closed_focus_lag",
                        "msg": (
                            f"session-log recent tail implies #{ref} merged/closed "
                            "but focus.md is not terminal — trust session-log, update focus"
                        ),
                        "fix": "update focus.md from newest session-log entry",
                    }
                )

    # 2) Worktree missing for active unit
    for u in open_units:
        wt = u.get("worktree")
        if not wt:
            continue
        name = Path(wt).name if "/" in str(wt) else str(wt)
        if name not in wt_by_name and str(wt) not in wt_paths:
            warnings.append(
                {
                    "severity": "high",
                    "code": "unit_worktree_missing",
                    "msg": (
                        f"unit `{u.get('unit_id')}` references worktree `{wt}` "
                        "which is not in `git worktree list`"
                    ),
                    "fix": (
                        f"recreate worktree or close unit "
                        f"(work_history.py --close --unit {u.get('unit_id')})"
                    ),
                }
            )

    # 3) Instance mismatch
    for u in open_units:
        inst = u.get("instance")
        if inst is None:
            continue
        live = locked.get(int(inst)) or next(
            (i for i in instances if i["id"] == int(inst)), None
        )
        if live is None:
            warnings.append(
                {
                    "severity": "medium",
                    "code": "unit_instance_unknown",
                    "msg": f"unit `{u.get('unit_id')}` claims instance {inst} but instance:list has no row",
                    "fix": "refresh instance binding or close unit",
                }
            )
            continue
        if "available" in (live.get("status") or "").lower() and u.get("status") == "active":
            warnings.append(
                {
                    "severity": "medium",
                    "code": "unit_instance_available",
                    "msg": (
                        f"unit `{u.get('unit_id')}` is active but instance {inst} "
                        f"is `{live.get('status')}`"
                    ),
                    "fix": "re-claim instance or mark unit idle/blocked",
                }
            )

    # 4) Multiple open units sharing the same worktree
    by_wt: dict[str, list[str]] = {}
    for u in open_units:
        wt = u.get("worktree")
        if not wt:
            continue
        by_wt.setdefault(str(wt), []).append(u.get("unit_id") or "?")
    for wt, uids in by_wt.items():
        if len(uids) > 1:
            warnings.append(
                {
                    "severity": "high",
                    "code": "shared_worktree_collision",
                    "msg": f"multiple open units on worktree `{wt}`: {', '.join(uids)}",
                    "fix": "serialize work or use separate worktrees (stash mid-session risk)",
                }
            )

    # 5) Locked instance with no open work-history (orphan resource)
    claimed_instances = {
        int(u["instance"]) for u in open_units if u.get("instance") is not None
    }
    for iid, live in locked.items():
        if iid == 0:
            continue
        if iid not in claimed_instances:
            wt = live.get("worktree") or "?"
            warnings.append(
                {
                    "severity": "medium",
                    "code": "orphan_locked_instance",
                    "msg": (
                        f"instance {iid} is locked ({wt}) with no open work-history unit"
                    ),
                    "fix": (
                        "attach via work_history.py --open … --instance "
                        f"{iid} OR /teardown-worktree (needs explicit approval for bulk)"
                    ),
                    "skill": "teardown-worktree",
                }
            )

    # 6) Focus hygiene note vs live sprawl (informational)
    if FOCUS.exists() and "worktrees" in FOCUS.read_text().lower():
        wt_count = len(wt_paths)
        if wt_count >= 40:
            warnings.append(
                {
                    "severity": "low",
                    "code": "worktree_sprawl",
                    "msg": (
                        f"{wt_count} git worktrees present — see machine-performance.md; "
                        "bulk teardown needs Rishi approval"
                    ),
                    "fix": "npm run instance:list + propose teardown list; do not delete without ask",
                    "skill": "teardown-worktree",
                }
            )

    return warnings


def render(warnings: list[dict], pretty: bool) -> str:
    if not warnings:
        return f"# Contradictions\n\n_None at {now_iso()}_\n"
    lines = [f"# Contradictions ({len(warnings)})", "", f"_Checked {now_iso()}_", ""]
    order = {"high": 0, "medium": 1, "low": 2}
    for w in sorted(warnings, key=lambda x: order.get(x.get("severity", "low"), 9)):
        sev = (w.get("severity") or "low").upper()
        lines.append(f"- **{sev}** `{w.get('code')}` — {w.get('msg')}")
        if w.get("fix"):
            lines.append(f"  - fix: {w['fix']}")
        if w.get("skill"):
            lines.append(f"  - skill: `/{w['skill']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    warnings = collect()
    if args.json:
        json.dump({"checked_at": now_iso(), "warnings": warnings}, sys.stdout, indent=2)
        print()
    else:
        sys.stdout.write(render(warnings, args.pretty))
    if args.strict and any(w.get("severity") == "high" for w in warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
