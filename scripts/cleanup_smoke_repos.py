#!/usr/bin/env python3
"""Delete stale smoke-staging repos on the operator's GitHub user.

Keeps `tv-smoke-tmp`. Per-PR leftovers look like tv-smoke-5912-assets.

Usage:
  python3 cleanup_smoke_repos.py              # dry-run
  python3 cleanup_smoke_repos.py --apply      # delete stale
  python3 cleanup_smoke_repos.py --self-check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

KEEP = frozenset({"tv-smoke-tmp"})
PATTERN = re.compile(r"^tv-smoke-")
STALE_DAYS = 7


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify(name: str, updated_at: str, now: datetime, stale_days: int) -> str:
    """keep | fresh | stale | skip."""
    if not PATTERN.match(name or ""):
        return "skip"
    if name in KEEP:
        return "keep"
    ts = _parse_ts(updated_at)
    if ts is None:
        return "stale"
    if now - ts < timedelta(days=stale_days):
        return "fresh"
    return "stale"


def _gh_json(args: list[str]) -> Any:
    p = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if p.returncode != 0:
        raise SystemExit(p.stderr.strip() or p.stdout.strip() or "gh failed")
    return json.loads(p.stdout) if p.stdout.strip() else None


def login() -> str:
    p = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if p.returncode != 0:
        raise SystemExit(p.stderr.strip() or "gh api user failed")
    return p.stdout.strip().strip('"')


def list_user_repos(owner: str) -> list[dict]:
    return _gh_json(
        [
            "repo",
            "list",
            owner,
            "--limit",
            "200",
            "--json",
            "name,updatedAt,url,isPrivate",
        ]
    ) or []


def delete_repo(owner: str, name: str) -> None:
    p = subprocess.run(
        ["gh", "repo", "delete", f"{owner}/{name}", "--yes"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if p.returncode != 0:
        raise SystemExit(p.stderr.strip() or f"delete failed: {owner}/{name}")


def plan(repos: list[dict], now: datetime, stale_days: int) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "keep": [],
        "fresh": [],
        "stale": [],
        "skip": [],
    }
    for r in repos:
        buckets[classify(r.get("name") or "", r.get("updatedAt") or "", now, stale_days)].append(r)
    return buckets


def _self_check() -> int:
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    assert classify("platform", "2026-01-01T00:00:00Z", now, 7) == "skip"
    assert classify("tv-smoke-tmp", "2026-01-01T00:00:00Z", now, 7) == "keep"
    assert classify("tv-smoke-5912-assets", "2026-09-02T00:00:00Z", now, 7) == "stale"
    assert classify("tv-smoke-tmp-8488", "2026-09-12T00:00:00Z", now, 7) == "fresh"
    assert classify("tv-smoke-5236", "2026-07-02T00:00:00Z", now, 7) == "stale"
    print("self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Delete stale repos. Default is dry-run.")
    ap.add_argument("--stale-days", type=int, default=STALE_DAYS)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return _self_check()

    owner = login()
    now = datetime.now(timezone.utc)
    buckets = plan(list_user_repos(owner), now, args.stale_days)
    print(f"owner: {owner}")
    print(f"keep: {', '.join(r['name'] for r in buckets['keep']) or '(none)'}")
    print(f"fresh (<{args.stale_days}d): {', '.join(r['name'] for r in buckets['fresh']) or '(none)'}")
    stale = buckets["stale"]
    print(f"stale: {', '.join(r['name'] for r in stale) or '(none)'}")
    if not stale:
        return 0
    if not args.apply:
        print("dry-run — pass --apply to delete stale")
        return 0
    for r in stale:
        delete_repo(owner, r["name"])
        print(f"deleted {owner}/{r['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
