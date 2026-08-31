#!/usr/bin/env python3
"""Rolling local work-unit history for SuperDev / local-memory.

Tracks issue/PR/worktree/instance/coder-box units across sessions so agents
do not rediscover state, and so contradiction + resource checks have a
single append-only ledger.

Store: local-memory/work-history/units.jsonl (cap 200)
Index: local-memory/work-history/active.md (derived open units)

Usage:
  python3 work_history.py --open --unit issue-9036 --issue 9036 --pr 9272 \\
    --branch feat/x --worktree platform-9036 --instance 23 --stage 5.5 \\
    --summary "sharing recovery paths"
  python3 work_history.py --update --unit issue-9036 --stage 6 --status active
  python3 work_history.py --close --unit issue-9036 --status shipped --summary "merged"
  python3 work_history.py --stamp --unit meta-superdev --kind meta \\
    --summary "added work-history + contradiction gate"
  python3 work_history.py --list [--status active] [--pretty]
  python3 work_history.py --active   # rewrite active.md + print
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib_paths import (
    INTENT,
    STATE as MEMORY,
    WORK_HISTORY,
    default_repo,
    ensure_state,
    github_login,
    operator_name,
    workspace,
)

ensure_state()

STORE_DIR = WORK_HISTORY
UNITS = STORE_DIR / "units.jsonl"
ACTIVE = STORE_DIR / "active.md"
CAP = 200

VALID_STATUS = {"active", "blocked", "shipped", "abandoned", "idle"}
VALID_KIND = {"issue", "pr", "chore", "meta", "resource"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    if not UNITS.exists():
        return []
    rows: list[dict] = []
    for line in UNITS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write(rows: list[dict]) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    if len(rows) > CAP:
        rows = rows[-CAP:]
    UNITS.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    _rewrite_active(rows)


def _latest_by_unit(rows: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for r in rows:
        uid = r.get("unit_id")
        if uid:
            latest[uid] = r
    return latest


def _rewrite_active(rows: list[dict] | None = None) -> str:
    rows = rows if rows is not None else _load()
    latest = _latest_by_unit(rows)
    open_units = [
        u
        for u in latest.values()
        if u.get("status") in ("active", "blocked", "idle")
    ]
    open_units.sort(key=lambda u: u.get("ts") or "", reverse=True)
    lines = [
        "# Active work units",
        "",
        f"_Derived from units.jsonl · {now_iso()}_",
        "",
    ]
    if not open_units:
        lines.append("(none)")
    else:
        lines.append("| unit | status | stage | issue/PR | resources | summary |")
        lines.append("| ---- | ------ | ----- | -------- | --------- | ------- |")
        for u in open_units:
            refs = []
            if u.get("issue"):
                refs.append(f"#{u['issue']}")
            if u.get("pr"):
                refs.append(f"PR#{u['pr']}")
            res = []
            if u.get("worktree"):
                res.append(f"wt:{u['worktree']}")
            if u.get("instance") is not None:
                res.append(f"inst:{u['instance']}")
            if u.get("coder_box"):
                res.append(f"box:{u['coder_box']}")
            lines.append(
                "| {unit} | {status} | {stage} | {refs} | {res} | {sum} |".format(
                    unit=u.get("unit_id", "?"),
                    status=u.get("status", "?"),
                    stage=u.get("stage") or "-",
                    refs=" ".join(refs) or "-",
                    res=", ".join(res) or "-",
                    sum=(u.get("summary") or "")[:80],
                )
            )
    lines.append("")
    md = "\n".join(lines)
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(md)
    return md


def _normalize_unit(unit: str | None, issue: int | None, pr: int | None) -> str:
    if unit:
        return unit.strip()
    if issue:
        return f"issue-{issue}"
    if pr:
        return f"pr-{pr}"
    raise SystemExit("need --unit or --issue/--pr")


def _merge_event(
    prev: dict | None,
    *,
    op: str,
    unit_id: str,
    kind: str | None,
    status: str | None,
    stage: str | None,
    issue: int | None,
    pr: int | None,
    branch: str | None,
    worktree: str | None,
    instance: int | None,
    coder_box: str | None,
    summary: str | None,
) -> dict:
    base = dict(prev) if prev else {}
    event = {
        "ts": now_iso(),
        "op": op,
        "unit_id": unit_id,
        "kind": kind or base.get("kind") or ("issue" if issue else "pr" if pr else "chore"),
        "status": status or base.get("status") or "active",
        "stage": stage if stage is not None else base.get("stage"),
        "issue": issue if issue is not None else base.get("issue"),
        "pr": pr if pr is not None else base.get("pr"),
        "branch": branch if branch is not None else base.get("branch"),
        "worktree": worktree if worktree is not None else base.get("worktree"),
        "instance": instance if instance is not None else base.get("instance"),
        "coder_box": coder_box if coder_box is not None else base.get("coder_box"),
        "summary": summary if summary is not None else base.get("summary"),
    }
    if event["kind"] not in VALID_KIND:
        raise SystemExit(f"invalid kind: {event['kind']}")
    if event["status"] not in VALID_STATUS:
        raise SystemExit(f"invalid status: {event['status']}")
    return event


def cmd_mutate(args: argparse.Namespace, op: str) -> int:
    rows = _load()
    latest = _latest_by_unit(rows)
    unit_id = _normalize_unit(args.unit, args.issue, args.pr)
    if op == "open" and unit_id in latest and latest[unit_id].get("status") in (
        "active",
        "blocked",
        "idle",
    ):
        op = "update"
    if op == "close":
        status = args.status or "shipped"
    elif op == "stamp":
        status = args.status or "shipped"
    else:
        status = args.status
    event = _merge_event(
        latest.get(unit_id),
        op=op,
        unit_id=unit_id,
        kind=args.kind,
        status=status,
        stage=args.stage,
        issue=args.issue,
        pr=args.pr,
        branch=args.branch,
        worktree=args.worktree,
        instance=args.instance,
        coder_box=args.coder_box,
        summary=args.summary,
    )
    rows.append(event)
    _write(rows)
    if args.pretty:
        print(json.dumps(event, indent=2))
    else:
        print(json.dumps(event))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = _load()
    latest = list(_latest_by_unit(rows).values())
    if args.status:
        latest = [u for u in latest if u.get("status") == args.status]
    latest.sort(key=lambda u: u.get("ts") or "", reverse=True)
    if args.pretty:
        print(json.dumps(latest, indent=2))
    else:
        for u in latest:
            print(json.dumps(u))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--close", action="store_true")
    ap.add_argument("--stamp", action="store_true", help="one-shot closed stamp")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--active", action="store_true")
    ap.add_argument("--unit")
    ap.add_argument("--kind", choices=sorted(VALID_KIND))
    ap.add_argument("--status", choices=sorted(VALID_STATUS))
    ap.add_argument("--stage")
    ap.add_argument("--issue", type=int)
    ap.add_argument("--pr", type=int)
    ap.add_argument("--branch")
    ap.add_argument("--worktree")
    ap.add_argument("--instance", type=int)
    ap.add_argument("--coder-box", dest="coder_box")
    ap.add_argument("--summary")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    modes = [args.open, args.update, args.close, args.stamp, args.list, args.active]
    if sum(1 for m in modes if m) != 1:
        ap.error("pick exactly one of --open/--update/--close/--stamp/--list/--active")

    if args.active:
        md = _rewrite_active()
        sys.stdout.write(md if md.endswith("\n") else md + "\n")
        return 0
    if args.list:
        return cmd_list(args)
    if args.open:
        return cmd_mutate(args, "open")
    if args.update:
        return cmd_mutate(args, "update")
    if args.close:
        return cmd_mutate(args, "close")
    if args.stamp:
        return cmd_mutate(args, "stamp")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
