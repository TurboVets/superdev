#!/usr/bin/env python3
"""Detect ship subagents that went quiet before Path 6 completion.

Reads <lane.dir>/agents.json + worktrees + Cursor transcripts.
Prints JSON actions: wait | resume | spawn | done.

  python3 unstick_subagents.py --pretty
  python3 unstick_subagents.py --quiet-min 5
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from lib_paths import default_repo, github_login, lane_dir

NOISE = ("boot", "superdev session", "booting superdev")
TRANSCRIPTS = Path.home() / ".cursor" / "projects"


def sh(cmd: str, cwd: str | None = None) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=cwd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def find_jsonl(agent_id: str) -> Path | None:
    hits = list(TRANSCRIPTS.glob(f"*/agent-transcripts/**/{agent_id}.jsonl"))
    hits += list(TRANSCRIPTS.glob(f"*/agent-transcripts/{agent_id}.jsonl"))
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def last_step(path: Path) -> str:
    step = ""
    try:
        for line in path.read_text(errors="replace").splitlines():
            if "UpdateCurrentStep" in line and "current_step" in line:
                i = line.find("current_step")
                step = line[i : i + 80]
    except OSError:
        return ""
    return step


def pr_for(ticket: str) -> str:
    login = github_login()
    repo = default_repo()
    if not login or not repo:
        return ""
    raw = sh(
        f"gh pr list --repo {repo} --author {login} "
        "--state open --json number,url,headRefName,body,title"
    )
    try:
        prs = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ""
    for pr in prs:
        ref = pr.get("headRefName") or ""
        body = pr.get("body") or ""
        title = pr.get("title") or ""
        if ticket in ref or f"#{ticket}" in title or f"Closes #{ticket}" in body:
            return f"https://github.com/{repo}/pull/{pr['number']}"
    return ""


def continue_prompt(ticket: str, wt: str, reason: str, facts: str) -> str:
    return (
        f"{facts}\n"
        "You may not state HEAD, L1, L3, 6a, 6b, e2e, mergeable, or done unless "
        "you just ran git/gh/lane_truth and quote that output. No tool output ⇒ "
        "UNVERIFIED. You may not run lane_truth.py --record. Do not invent a SHA "
        "or a tool result.\n"
        f"Unstick #{ticket}. {reason} Continue in {wt}. "
        "Do not boot SuperDev. Do not merge. Do not claim a gate green "
        "unless lane_truth.py binds it to THIS HEAD."
    )


def diagnose(ticket: str, meta: dict, quiet_s: float, truth: dict) -> dict:
    wt = meta.get("worktree") or ""
    agents = meta.get("agents") or []
    now = time.time()
    newest: Path | None = None
    newest_id = ""
    for aid in agents:
        p = find_jsonl(aid)
        if not p:
            continue
        step = last_step(p).lower()
        if "stopped as requested" in step or "do no more work" in step:
            continue
        if newest is None or p.stat().st_mtime > newest.stat().st_mtime:
            newest, newest_id = p, aid
    age = (now - newest.stat().st_mtime) if newest else 10**9
    step = last_step(newest) if newest else ""
    boot = any(n in step.lower() for n in NOISE)
    ahead = sh("git rev-list --count origin/main..HEAD 2>/dev/null || echo 0", wt)
    dirty = len([ln for ln in sh("git status --porcelain", wt).splitlines() if ln])
    last = sh("git log -1 --format=%s", wt)
    pr = truth.get("pr") or pr_for(ticket)
    facts = (
        sh(
            f"python3 {Path(__file__).resolve().parent}/lane_truth.py "
            f"--facts-block --ticket {ticket}"
        )
        if truth.get("head")
        else ""
    )
    claimed_done = any(
        w in step.lower()
        for w in (
            "shipped",
            "reporting ship",
            "path 6 complete",
            "path 6 on",
            "finishing path 6",
            "all four green",
        )
    )
    skipping = truth.get("next") == "L1" and "l3" in step.lower()
    if truth.get("done"):
        status, action, reason = "done", "none", "lane_truth done on HEAD"
    elif (claimed_done or skipping) and not truth.get("done"):
        status, action, reason = (
            "stuck",
            "resume" if newest_id else "spawn",
            (
                "skipping to L3; lane_truth next L1"
                if skipping
                else f"claimed done; lane_truth next {truth.get('next') or 'L1'}"
            ),
        )
    elif boot and age > 120:
        status, action, reason = "stuck", "spawn", "stuck on SuperDev boot"
    elif age > quiet_s:
        status, action, reason = (
            "stuck",
            "resume" if newest_id else "spawn",
            f"quiet {int(age / 60)}m"
            + ("" if pr else ", no PR")
            + (f", {ahead} ahead" if ahead not in {"", "0"} else ""),
        )
    else:
        status, action, reason = "running", "wait", f"active {int(age)}s ago"
    return {
        "ticket": int(ticket) if str(ticket).isdigit() else ticket,
        "status": status,
        "action": action,
        "reason": reason,
        "agent": newest_id,
        "age_s": int(age if age < 10**8 else -1),
        "pr": pr,
        "ahead": int(ahead or 0),
        "dirty": dirty,
        "last": last,
        "step": step[:80],
        "worktree": wt,
        "prompt": continue_prompt(ticket, wt, reason, facts),
        "next": truth.get("next") or "",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--quiet-min", type=float, default=5)
    args = ap.parse_args()
    lane = lane_dir()
    agents_path = lane / "agents.json"
    agents = json.loads(agents_path.read_text()) if agents_path.exists() else {"tickets": {}}
    truth_raw = sh(f"python3 {Path(__file__).resolve().parent}/lane_truth.py")
    try:
        truth_rows = {
            str(r["ticket"]): r
            for r in json.loads(truth_raw or "{}").get("tickets", [])
        }
    except json.JSONDecodeError:
        truth_rows = {}
    rows = [
        diagnose(t, meta, args.quiet_min * 60, truth_rows.get(t) or {})
        for t, meta in (agents.get("tickets") or {}).items()
    ]
    out = {
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tickets": rows,
        "unstick": [r for r in rows if r["action"] in {"resume", "spawn"}],
    }
    (lane / "unstick.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
