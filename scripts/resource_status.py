#!/usr/bin/env python3
"""Local + remote resource status for SuperDev.

Inventories multi-instance locks, worktrees, agent-resource sessions, and
(optionally) coder-box list. Warns on sprawl / orphans and points at the
owning skills (`teardown-worktree`, `coder-box`) — never destructs.

Usage:
  python3 resource_status.py [--pretty] [--json] [--with-coder]
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
WORKSPACE = workspace()
UNITS = WORK_HISTORY / "units.jsonl"
AGENT_SESSIONS = WORKSPACE / ".agent-resource-sessions"
MACHINE = MEMORY / "machine-performance.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or WORKSPACE),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, f"__error__:{e}"


def _latest_open_units() -> list[dict]:
    if not UNITS.exists():
        return []
    latest: dict[str, dict] = {}
    for line in UNITS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        uid = r.get("unit_id")
        if uid:
            latest[uid] = r
    return [
        u
        for u in latest.values()
        if u.get("status") in ("active", "blocked", "idle")
    ]


def _parse_instances(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s+(\S+(?:\s+\([^)]+\))?)\s+(\S.+)?\s*$", line)
        if not m:
            continue
        status = m.group(2).strip()
        if status.startswith("ID") or status.startswith("--"):
            continue
        out.append(
            {
                "id": int(m.group(1)),
                "status": status,
                "worktree": (m.group(3) or "").strip() or None,
            }
        )
    return out


def _worktrees() -> list[dict]:
    code, text = _run(["git", "worktree", "list", "--porcelain"])
    if code != 0 and text.startswith("__error__"):
        return []
    items: list[dict] = []
    cur: dict = {}
    for line in text.splitlines():
        if line.startswith("worktree "):
            if cur:
                items.append(cur)
            cur = {"path": line.split(" ", 1)[1], "bare": False}
        elif line.startswith("branch "):
            cur["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line.startswith("HEAD "):
            cur["head"] = line.split(" ", 1)[1]
        elif line == "bare":
            cur["bare"] = True
        elif line == "detached":
            cur["detached"] = True
    if cur:
        items.append(cur)
    return items


def _agent_sessions() -> list[dict]:
    if not AGENT_SESSIONS.exists():
        return []
    out = []
    for p in sorted(AGENT_SESSIONS.glob("*.json")):
        try:
            out.append({"file": p.name, **json.loads(p.read_text())})
        except (OSError, json.JSONDecodeError):
            out.append({"file": p.name, "error": "unreadable"})
    return out


def _coder_boxes() -> dict:
    script = WORKSPACE / "scripts" / "coder-box" / "coder-box.sh"
    if not script.exists():
        return {"available": False, "reason": "script missing"}
    code, text = _run([str(script), "list"], timeout=30)
    if code != 0:
        return {
            "available": False,
            "reason": "coder CLI / auth unavailable",
            "detail": text[:400],
        }
    return {"available": True, "raw": text[:2000]}


def build(with_coder: bool = False) -> dict:
    open_units = _latest_open_units()
    _, inst_text = _run(["npm", "run", "instance:list"])
    instances = _parse_instances(inst_text)
    locked = [i for i in instances if "locked" in (i.get("status") or "").lower()]
    worktrees = _worktrees()
    sessions = _agent_sessions()
    claimed_inst = {
        int(u["instance"]) for u in open_units if u.get("instance") is not None
    }
    claimed_wt = {
        Path(str(u["worktree"])).name
        for u in open_units
        if u.get("worktree")
    }
    orphans = [
        i
        for i in locked
        if i["id"] != 0 and i["id"] not in claimed_inst
    ]
    suggestions: list[dict] = []
    if orphans:
        suggestions.append(
            {
                "severity": "medium",
                "skill": "teardown-worktree",
                "msg": (
                    f"{len(orphans)} locked instance(s) with no open work-history unit: "
                    + ", ".join(f"{o['id']}→{Path(o.get('worktree') or '?').name}" for o in orphans[:8])
                ),
                "action": "Propose idle-stop or teardown per instance; bulk delete needs explicit approval",
            }
        )
    if len(worktrees) >= 40:
        suggestions.append(
            {
                "severity": "high",
                "skill": "teardown-worktree",
                "msg": (
                    f"{len(worktrees)} worktrees on disk — see machine-performance.md "
                    "(baseline was 96 ≈ 143 GB). Do NOT bulk-delete without Rishi ask."
                ),
                "action": "Build candidate list from PR-merged state + work-history; ask before teardown",
            }
        )
    if with_coder:
        boxes = _coder_boxes()
        if boxes.get("available") and "NAME" in (boxes.get("raw") or ""):
            # heuristic: any non-header line ⇒ live boxes
            live_lines = [
                ln
                for ln in (boxes.get("raw") or "").splitlines()
                if ln.strip() and not ln.lower().startswith("name")
            ]
            if live_lines:
                suggestions.append(
                    {
                        "severity": "medium",
                        "skill": "coder-box",
                        "msg": f"{len(live_lines)} coder-box workspace(s) listed — teardown when task done (EC2 leak)",
                        "action": "scripts/coder-box/coder-box.sh teardown <name> via /coder-box",
                    }
                )
    else:
        boxes = {"available": None, "skipped": True}

    return {
        "checked_at": now_iso(),
        "counts": {
            "worktrees": len(worktrees),
            "instances_total": len(instances),
            "instances_locked": len(locked),
            "open_work_units": len(open_units),
            "orphan_locked_instances": len(orphans),
            "agent_resource_sessions": len(sessions),
        },
        "open_work_units": [
            {
                "unit_id": u.get("unit_id"),
                "status": u.get("status"),
                "stage": u.get("stage"),
                "issue": u.get("issue"),
                "pr": u.get("pr"),
                "worktree": u.get("worktree"),
                "instance": u.get("instance"),
                "coder_box": u.get("coder_box"),
                "summary": u.get("summary"),
            }
            for u in open_units
        ],
        "locked_instances": locked,
        "orphan_locked_instances": orphans,
        "agent_resource_sessions": sessions,
        "coder_boxes": boxes,
        "suggestions": suggestions,
        "playbook": str(MACHINE) if MACHINE.exists() else None,
        "skills": {
            "local_teardown": "teardown-worktree",
            "remote_box": "coder-box",
            "playbook": "local-memory/machine-performance.md",
        },
    }


def render(report: dict) -> str:
    c = report["counts"]
    lines = [
        "# Resource status",
        "",
        f"_Checked {report['checked_at']}_",
        "",
        (
            f"- worktrees: **{c['worktrees']}** · locked instances: "
            f"**{c['instances_locked']}** · open work units: **{c['open_work_units']}** · "
            f"orphan locks: **{c['orphan_locked_instances']}** · "
            f"agent sessions: **{c['agent_resource_sessions']}**"
        ),
        "",
    ]
    if report["open_work_units"]:
        lines.append("## Open work units")
        for u in report["open_work_units"]:
            bits = [u.get("unit_id") or "?"]
            if u.get("issue"):
                bits.append(f"#{u['issue']}")
            if u.get("pr"):
                bits.append(f"PR#{u['pr']}")
            if u.get("worktree"):
                bits.append(f"wt:{u['worktree']}")
            if u.get("instance") is not None:
                bits.append(f"inst:{u['instance']}")
            if u.get("coder_box"):
                bits.append(f"box:{u['coder_box']}")
            lines.append(f"- {' · '.join(bits)} — {u.get('summary') or ''}")
        lines.append("")
    if report["suggestions"]:
        lines.append("## Warnings / next skills")
        for s in report["suggestions"]:
            lines.append(
                f"- **{(s.get('severity') or 'low').upper()}** `/{s.get('skill')}` — {s.get('msg')}"
            )
            if s.get("action"):
                lines.append(f"  - {s['action']}")
        lines.append("")
    else:
        lines.append("_No resource warnings._\n")
    lines.append(
        "Skills: `/teardown-worktree` (local) · `/coder-box` (remote EC2) · "
        "`machine-performance.md` (safe reclaim)."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--with-coder", action="store_true")
    args = ap.parse_args()
    report = build(with_coder=args.with_coder)
    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        sys.stdout.write(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
