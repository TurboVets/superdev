#!/usr/bin/env python3
"""Rebase own CONFLICTING PRs onto origin/main.

Path 0 lists them. Standing: --apply in the same turn. Feature branch
only. --force-with-lease. Dirty trees and main/master are refused.

  python3 conflict_sweep.py --pretty
  python3 conflict_sweep.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    from lib_paths import default_repo, github_login, workspace
except ImportError:

    def github_login() -> str:
        return _sh("gh api user --jq .login") or os.environ.get(
            "SUPERDEV_GITHUB_LOGIN", ""
        )

    def default_repo() -> str:
        return os.environ.get("SUPERDEV_DEFAULT_REPO", "TurboVets/platform")

    def workspace() -> Path:
        raw = os.environ.get("SUPERDEV_WORKSPACE", "")
        return Path(raw).expanduser() if raw else Path.cwd()

PROTECTED = {"main", "master", "dev"}


def _sh(cmd: str, cwd: str | None = None) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, cwd=cwd, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        return ""


def _run(cmd: list[str], cwd: str | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, out


def repo_root() -> str:
    ws = str(workspace())
    if (Path(ws) / ".git").exists() or _sh("git rev-parse --show-toplevel", ws):
        return _sh("git rev-parse --show-toplevel", ws) or ws
    return _sh("git rev-parse --show-toplevel") or ws


def open_prs() -> list[dict]:
    login = github_login()
    repo = default_repo()
    if not login or not repo:
        return []
    raw = _sh(
        f"gh pr list --repo {repo} --author {login} --state open --limit 100 "
        "--json number,title,url,mergeable,headRefName,isDraft"
    )
    try:
        return json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []


def conflicting(prs: list[dict]) -> list[dict]:
    return [p for p in prs if (p.get("mergeable") or "") == "CONFLICTING"]


def worktree_for_branch(root: str, branch: str) -> str:
    raw = _sh("git worktree list --porcelain", root)
    current = ""
    for line in raw.splitlines():
        if line.startswith("worktree "):
            current = line.split(" ", 1)[1]
        if line.startswith("branch ") and line.endswith("/" + branch):
            return current
    return ""


def _is_lock(out: str) -> bool:
    return "index.lock" in out or "Another git process" in out


def _rebase_with_lock_retry(wt: str) -> tuple[int, str]:
    last = (1, "")
    for _ in range(8):
        code, out = _run(["git", "rebase", "origin/main"], cwd=wt)
        if code == 0:
            return code, out
        if _is_lock(out):
            last = (code, out)
            time.sleep(2)
            code, out = _run(["git", "rebase", "--continue"], cwd=wt)
            if code == 0:
                return code, out
            last = (code, out)
            if _is_lock(out):
                continue
        return code, out
    return last


def rebase_one(pr: dict, root: str) -> dict:
    branch = pr.get("headRefName") or ""
    number = pr.get("number")
    if not branch or branch in PROTECTED:
        return {"pr": number, "ok": False, "reason": f"protected branch {branch}"}
    _run(["git", "fetch", "origin", "main", branch], cwd=root)
    wt = worktree_for_branch(root, branch)
    created = ""
    if not wt:
        created = tempfile.mkdtemp(prefix=f"superdev-rebase-{number}-")
        code, out = _run(
            ["git", "worktree", "add", "--detach", created, f"origin/{branch}"],
            cwd=root,
        )
        if code != 0:
            return {"pr": number, "ok": False, "reason": out or "worktree add failed"}
        _run(["git", "checkout", "-B", branch], cwd=created)
        wt = created
    if _sh("git status --porcelain", wt):
        if created:
            _run(["git", "worktree", "remove", "--force", created], cwd=root)
        return {"pr": number, "ok": False, "reason": f"dirty {wt}"}
    code, out = _rebase_with_lock_retry(wt)
    if code != 0:
        unmerged = _sh("git diff --name-only --diff-filter=U", wt)
        if _is_lock(out) and not unmerged:
            return {
                "pr": number,
                "ok": False,
                "reason": "index.lock — retry, do not abort as a conflict",
                "log": out[-400:],
            }
        _run(["git", "rebase", "--abort"], cwd=wt)
        if created:
            _run(["git", "worktree", "remove", "--force", created], cwd=root)
        return {
            "pr": number,
            "ok": False,
            "reason": "rebase conflicts — abort, resolve in this turn",
            "files": unmerged.splitlines(),
            "log": out[-800:],
        }
    head = _sh("git rev-parse --short HEAD", wt)
    code, out = _run(
        ["git", "push", "--force-with-lease", "origin", f"HEAD:refs/heads/{branch}"],
        cwd=wt,
    )
    if created:
        _run(["git", "worktree", "remove", "--force", created], cwd=root)
    if code != 0:
        return {"pr": number, "ok": False, "reason": out or "push failed"}
    return {"pr": number, "ok": True, "branch": branch, "head": head}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    prs = open_prs()
    hits = conflicting(prs)
    out = {
        "repo": default_repo(),
        "login": github_login(),
        "conflicting": [
            {"number": p["number"], "title": p.get("title"), "url": p.get("url"), "branch": p.get("headRefName")}
            for p in hits
        ],
        "unknown": [p["number"] for p in prs if (p.get("mergeable") or "") == "UNKNOWN"],
    }
    if args.apply and hits:
        root = repo_root()
        out["results"] = [rebase_one(p, root) for p in hits]
    print(json.dumps(out, indent=2 if args.pretty else None))
    if args.apply:
        return 0 if all(r.get("ok") for r in out.get("results") or []) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
