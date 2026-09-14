#!/usr/bin/env python3
"""SHA-bound facts for every open own PR + lane issues.

  python3 lane_truth.py --pretty
  python3 lane_truth.py --facts-block --ticket 12039
  python3 lane_truth.py --record --ticket 12039 --l1 <sha>

Ready for human review only when L1, L3, 6a, 6b, and E2E bind THIS HEAD.
Agent prose is not state. Reads do not write. Only `--record` writes <lane.dir>/truth.json.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import time
from pathlib import Path

from lib_paths import (
    WORK_HISTORY,
    default_repo,
    github_login,
    lane_dir,
    worktree_parent,
    worktree_prefix,
)

ARTIFACTS = ("l1", "l3", "qa", "smoke", "e2e")
NAMES = {"l1": "L1", "l3": "L3", "qa": "6a", "smoke": "6b", "e2e": "e2e"}


def sh(cmd: str, cwd: str | None = None) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=cwd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return fallback


def short(sha: str) -> str:
    return (sha or "")[:12]


def repo() -> str:
    return default_repo() or "UNKNOWN/repo"


def prs_by_author() -> list:
    login = github_login()
    if not login or repo() == "UNKNOWN/repo":
        return []
    raw = sh(
        f"gh pr list --repo {repo()} --author {login} "
        "--state open --limit 100 "
        "--json number,url,headRefName,headRefOid,mergeable,body,title,labels"
    )
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []


def ticket_from_pr(pr: dict) -> str:
    ref = pr.get("headRefName") or ""
    m = re.search(r"(\d{4,5})", ref)
    if m:
        return m.group(1)
    title = pr.get("title") or ""
    m = re.search(r"#(\d{4,5})", title)
    return m.group(1) if m else str(pr.get("number") or "")


def worktree_for(ticket: str, agents: dict) -> str:
    meta = (agents.get("tickets") or {}).get(ticket) or {}
    wt = meta.get("worktree") or ""
    if wt and Path(wt).is_dir():
        return wt
    prefix = worktree_prefix()
    if not prefix:
        return ""
    p = worktree_parent() / f"{prefix}{ticket}"
    return str(p) if p.is_dir() else ""


def e2e_on_sha(sha: str) -> str:
    if not sha or repo() == "UNKNOWN/repo":
        return ""
    raw = sh(
        f"gh api repos/{repo()}/commits/{sha}/check-runs "
        "--paginate --jq '.check_runs[] | [.name,.conclusion] | @tsv'"
    )
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, conclusion = parts[0].lower(), (parts[1] or "").lower()
        if "e2e" in name and conclusion == "success":
            return sha
    return ""


def live_row(ticket: str, stored: dict, pr: dict | None, wt: str) -> dict:
    head = (
        (sh("git rev-parse HEAD", wt) if wt else "")
        or (pr or {}).get("headRefOid")
        or ""
    )
    ahead = (
        int(sh("git rev-list --count origin/main..HEAD 2>/dev/null || echo 0", wt) or 0)
        if wt
        else 0
    )
    dirty = (
        len([ln for ln in sh("git status --porcelain", wt).splitlines() if ln])
        if wt
        else 0
    )
    last = sh("git log -1 --format=%s", wt) if wt else (pr or {}).get("title") or ""
    pr_sha = (pr or {}).get("headRefOid") or ""
    player = "user-attachments/assets" in ((pr or {}).get("body") or "")
    rec = stored.get(ticket) or {}
    bound = {k: rec.get(f"{k}_sha") or "" for k in ARTIFACTS}
    if player and pr_sha and short(pr_sha) == short(head):
        bound["smoke"] = bound["smoke"] or head
    if short(bound["e2e"]) != short(head):
        bound["e2e"] = e2e_on_sha(pr_sha or head)
    next_art = ""
    for k in ARTIFACTS:
        if short(bound[k]) != short(head) or not head:
            next_art = k
            break
    if not pr:
        next_art = next_art if next_art and next_art != "e2e" else "pr"
    done = bool(head and pr and not next_art)
    return {
        "ticket": int(ticket) if str(ticket).isdigit() else ticket,
        "head": head,
        "ahead": ahead,
        "dirty": dirty,
        "last": last,
        "pr": (pr or {}).get("url") or "",
        "pr_sha": pr_sha,
        "mergeable": (pr or {}).get("mergeable") or "",
        "player": player,
        "l1_sha": bound["l1"],
        "l3_sha": bound["l3"],
        "qa_sha": bound["qa"],
        "smoke_sha": bound["smoke"],
        "e2e_sha": bound["e2e"],
        "next": NAMES.get(next_art, next_art or "done"),
        "done": done,
        "worktree": wt,
    }


def facts_block(row: dict) -> str:
    return "\n".join(
        [
            "FACTS (do not contradict; do not invent a greener state):",
            f"HEAD {short(row['head'])} · {row['ahead']} ahead · {row['dirty']} dirty · {row['last']}",
            f"PR {row['pr'] or 'NONE'} · mergeable {row['mergeable'] or 'n/a'} · player {row['player']}",
            f"L1 {short(row['l1_sha']) or 'unset'} · L3 {short(row['l3_sha']) or 'unset'} · "
            f"6a {short(row['qa_sha']) or 'unset'} · 6b {short(row['smoke_sha']) or 'unset'} · "
            f"e2e {short(row['e2e_sha']) or 'unset'}",
            f"NEXT {row['next']}. Ready for human review only when next is done. "
            "Do not boot SuperDev. Do not merge. Stamp after each step.",
        ]
    )


def persist_live(stored: dict, rows: list) -> dict:
    out = dict(stored)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in rows:
        key = str(row["ticket"])
        prev = out.get(key) or {}
        out[key] = {**prev, "head": row["head"], "pr": row["pr"], "updatedAt": now}
        if row.get("e2e_sha"):
            out[key]["e2e_sha"] = row["e2e_sha"]
        if row.get("smoke_sha"):
            out[key]["smoke_sha"] = row["smoke_sha"]
    return out


def _lock_truth(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path.with_suffix(path.suffix + ".lock"), "a+")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    return fh


def write_truth(path: Path, stored: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(stored, indent=2) + "\n")
    tmp.replace(path)


def work_history_tickets() -> dict[str, str]:
    """Active/blocked issue units so a no-PR ship is still on the tab."""
    latest: dict[str, dict] = {}
    units = WORK_HISTORY / "units.jsonl"
    if not units.exists():
        return {}
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
    out: dict[str, str] = {}
    parent = worktree_parent()
    for ev in latest.values():
        if ev.get("status") not in {"active", "blocked", "idle"}:
            continue
        issue = ev.get("issue")
        if not issue:
            continue
        wt = ev.get("worktree") or ""
        if wt and not Path(wt).is_absolute():
            guess = parent / Path(wt).name
            wt = str(guess) if guess.is_dir() else wt
        if wt and not Path(wt).is_dir():
            wt = ""
        out[str(issue)] = wt
    return out


def propose_ingest(ticket: str, head: str) -> list[tuple[str, str, str]]:
    """Bind L1/L3 only when a file names this HEAD and the gate phrase."""
    if not head:
        return []
    h = short(head).lower()
    found: list[tuple[str, str, str]] = []
    l1_paths = list(Path("/tmp").glob("tv-fullstack*.md"))
    art = lane_dir() / "artifacts"
    if art.is_dir():
        l1_paths.extend(art.glob(f"*{ticket}*"))
    for path in l1_paths:
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if h not in text.lower():
            continue
        if len(re.findall(r"\bShip\b", text)) >= 2:
            found.append(("l1", head, str(path)))
            break
    reviews = []
    for name in ("codex", "claude"):
        path = Path(f"/tmp/local-review-{name}.md")
        if not path.exists():
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if not re.search(r"^VERDICT:\s*APPROVE\b", text, re.M):
            continue
        if h not in text.lower():
            continue
        reviews.append(name)
    if {"codex", "claude"} <= set(reviews):
        found.append(("l3", head, "both /tmp/local-review-*.md APPROVE + HEAD"))
    return found


def collect_rows(agents: dict, stored: dict, pulls: list) -> list:
    seen: set[str] = set()
    rows: list[dict] = []
    for pr in pulls:
        ticket = ticket_from_pr(pr)
        if not ticket or ticket in seen:
            continue
        seen.add(ticket)
        rows.append(live_row(ticket, stored, pr, worktree_for(ticket, agents)))
    for ticket, meta in (agents.get("tickets") or {}).items():
        if ticket in seen:
            continue
        seen.add(ticket)
        rows.append(
            live_row(ticket, stored, None, meta.get("worktree") or worktree_for(ticket, agents))
        )
    for ticket, wt in work_history_tickets().items():
        if ticket in seen:
            continue
        seen.add(ticket)
        rows.append(live_row(ticket, stored, None, wt or worktree_for(ticket, agents)))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--facts-block", action="store_true")
    ap.add_argument("--ticket")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--l1")
    ap.add_argument("--l3")
    ap.add_argument("--qa")
    ap.add_argument("--smoke")
    ap.add_argument("--e2e")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    lane = lane_dir()
    truth = lane / "truth.json"
    agents = load_json(lane / "agents.json", {})
    stored = load_json(truth, {})
    if args.record and args.ticket:
        lock = _lock_truth(truth)
        try:
            stored = load_json(truth, {})
            rec = stored.get(args.ticket) or {}
            for key, val in (
                ("l1_sha", args.l1),
                ("l3_sha", args.l3),
                ("qa_sha", args.qa),
                ("smoke_sha", args.smoke),
                ("e2e_sha", args.e2e),
            ):
                if val:
                    rec[key] = val
            stored[args.ticket] = rec
            pulls = prs_by_author()
            rows = collect_rows(agents, stored, pulls)
            write_truth(truth, persist_live(stored, rows))
        finally:
            lock.close()
    else:
        pulls = prs_by_author()
        rows = collect_rows(agents, stored, pulls)

    if args.facts_block:
        if not rows:
            print("FACTS: no open own PRs and no lane tickets.")
            return 0
        ticket = str(args.ticket or rows[0]["ticket"])
        row = next(r for r in rows if str(r["ticket"]) == ticket)
        print(facts_block(row))
        return 0

    leftover = [r for r in rows if not r["done"]]
    if args.ingest and args.ticket:
        row = next((r for r in rows if str(r["ticket"]) == str(args.ticket)), None)
        if not row:
            raise SystemExit(f"ticket {args.ticket} not in lane_truth")
        proposals = propose_ingest(str(args.ticket), row["head"])
        if args.apply and proposals:
            lock = _lock_truth(truth)
            try:
                stored = load_json(truth, {})
                rec = stored.get(str(args.ticket)) or {}
                for art, sha, _why in proposals:
                    rec[f"{art}_sha"] = sha
                stored[str(args.ticket)] = rec
                write_truth(truth, persist_live(stored, rows))
            finally:
                lock.close()
        print(json.dumps([{"artifact": a, "sha": short(s), "why": w} for a, s, w in proposals]))
        return 0
    print(
        json.dumps(
            {"tickets": rows, "open": leftover, "ready": [r for r in rows if r["done"]]},
            indent=2 if args.pretty else None,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
