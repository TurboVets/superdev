#!/usr/bin/env python3
"""Review coverage contract for SuperDev's L2 rung.

The problem this solves: with ~15 review surfaces installed, a prose report
cannot distinguish "this axis was reviewed and is clean" from "nobody looked."
This script makes coverage an assertion instead of a feeling.

Flow per shipping head:

    plan     → which axes the diff forces on (path AND content gated), and the
               single surface that owns each one
    ingest   → read turbo-eyes' `review-feedback` JSON; its subskill_status maps
               onto the axes it owns (ok / skipped-* / failed all carry through)
    record   → SuperDev logs the axes it owns itself (profile lenses, product
               law, AI runtime, concurrency, verdict channel)
    assert   → exit 1 if any planned axis is unaccounted; `clean` is only legal
               when status is `ran`
    miss     → attribute a finding a GitHub human/bot raised to the axis that
               owned it
    yield    → per-axis hit rate over the ledger, so dead surfaces get pruned

Ownership follows the delegation decision (Rishi, 2026-08-12): on the crowded
axes the machine sweep is `turbo-eyes:review-code`, which is content-gated,
model-tiered and keeps an arbitration audit log. SuperDev owns only the axes no
other surface covers.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from lib_paths import INTENT, ensure_state

ensure_state()
LEDGER = INTENT / "review-coverage-ledger.jsonl"
RUN_DIR = Path("/tmp")

# Axis registry — the single source of truth for "who owns what".
#   owner        surface that emits findings for this axis; everyone else is
#                attribution only (turbo-eyes arbitration rule 15)
#   paths        gate 1: the diff must touch a path matching this
#   content      gate 2: the diff body must contain this (None = path is enough)
#   tier         model floor when SuperDev runs the axis itself
AXES = [
    # ── delegated to turbo-eyes:review-code ───────────────────────────────
    dict(id="red-flags", owner="turbo-eyes:q1", paths=r".", content=None, tier="T4"),
    dict(id="regressions", owner="turbo-eyes:q2", paths=r".", content=None, tier="T4"),
    dict(id="tests", owner="turbo-eyes:q3", paths=r"\.(ts|tsx|py)$",
         content=r"(describe\(|it\(|test\(|expect\()", tier="T3"),
    dict(id="ui-tds", owner="turbo-eyes:q4", paths=r"\.(html|scss|css)$", content=None, tier="T2"),
    dict(id="standards", owner="turbo-eyes:q5", paths=r"\.(ts|tsx)$", content=None, tier="T3"),
    dict(id="ci-signal", owner="turbo-eyes:q6", paths=r".", content=None, tier="T4"),
    dict(id="e2e-ci", owner="turbo-eyes:q7", paths=r"(acceptance/|\.feature$|e2e)", content=None, tier="T3"),
    dict(id="performance", owner="turbo-eyes:q8", paths=r"\.(ts|tsx)$", content=None, tier="T3"),
    dict(id="type-safety", owner="turbo-eyes:q12", paths=r"\.(ts|tsx)$",
         content=r"(\bas unknown as\b|\bas any\b|:\s*any\b|!\.)", tier="T2"),
    dict(id="migrations", owner="turbo-eyes:q13", paths=r"(migrations?/|entit|\.sql$|seed)",
         content=None, tier="T4"),
    dict(id="tenancy-authz", owner="turbo-eyes:q14",
         paths=r"(guard|permission|policy|ownership|authoriz|\brole\b|resolver|repositor)",
         content=None, tier="T4"),
    dict(id="workflow-infra", owner="turbo-eyes:q15",
         paths=r"(\.github/|Dockerfile|docker-compose|nx\.json|project\.json|scripts/)",
         content=None, tier="T4"),
    # ── SuperDev-owned: no other installed surface covers these ───────────
    dict(id="profile-lenses", owner="superdev:pr-review-lens", paths=r".", content=None, tier="T4"),
    dict(id="sibling-sweep", owner="superdev:review-bar-F3", paths=r".", content=None, tier="T4"),
    dict(id="concurrency-tx", owner="superdev:review-bar-F2",
         paths=r".", content=r"(transaction|advisory|FOR UPDATE|lock_timeout|Promise\.all|setInterval)",
         tier="T4"),
    dict(id="product-law", owner="superdev:standing-product",
         paths=r"(share|invite|consent|poa|claim|identity|profile)", content=None, tier="T4"),
    dict(id="ai-runtime", owner="superdev:review-bar-F10",
         paths=r"(libs/ai/|assistant|agent-tools|calls-service)",
         content=r"(prompt|tool|embedding|bedrock|stream)", tier="T4"),
    dict(id="copy-truthfulness", owner="superdev:review-bar-F6",
         paths=r"\.(html|ts)$",
         content=r"(toast|snackbar|banner|success|dialog|Notification|helperText|subtitle|tooltip|seamlessly|effortlessly)",
         tier="T3"),
    dict(id="security-bar", owner="superdev:security-bar",
         paths=r"(auth|token|session|invite|login|upload|webhook|hmac|presign|sanitiz|url|secret)",
         content=None, tier="T4"),
    dict(id="verdict-channel", owner="superdev:review-bar-verdict", paths=r".", content=None, tier="T4"),
    dict(id="over-engineering", owner="superdev:ponytail-review",
         paths=r"\.(ts|tsx|html|scss|css|py)$", content=None, tier="T2"),
]

# turbo-eyes subskill_status → our coverage status.
TE_STATUS = {
    "ok": "ran",
    "skipped": "na",
    "skipped-no-matching-files": "na",
    "skipped-no-trigger-match": "na",
    "failed": "failed",
}

ALWAYS = {"red-flags", "regressions", "profile-lenses", "sibling-sweep", "verdict-channel", "ci-signal"}


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def head_sha() -> str:
    return (sh(["git", "rev-parse", "--short", "HEAD"]) or "nohead").strip()


def run_path(sha: str) -> Path:
    return RUN_DIR / f"review-coverage-{sha}.json"


def load_run(sha: str) -> dict:
    p = run_path(sha)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save_run(sha: str, data: dict) -> None:
    run_path(sha).write_text(json.dumps(data, indent=2))


CODE = re.compile(r"\.(ts|tsx|js|mjs|py|sh|sql|html|scss|css|yml|yaml|json|feature|dart)$", re.I)
DOCS = re.compile(r"(\.md$|\.mdc$|^docs/|\.claude/skills/|\.cursor/)", re.I)


def diff_added_by_file(base: str) -> dict[str, str]:
    """{path: added lines}. Content gating must see a concern in a file the axis
    owns — a `setInterval` inside a Markdown skill doc is not a concurrency diff."""
    body = sh(["git", "diff", f"{base}...HEAD"]) or sh(["git", "diff", "HEAD"])
    out: dict[str, list[str]] = {}
    cur = None
    for line in body.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            out.setdefault(cur, [])
        elif line.startswith("+") and not line.startswith("+++") and cur:
            out[cur].append(line[1:])
    return {f: "\n".join(v) for f, v in out.items()}


def plan_axes(added_by_file: dict[str, str]) -> list[dict]:
    """An axis is planned only when some changed file both matches its paths and
    (if it has a content trigger) carries that concern in its own added lines."""
    files = list(added_by_file)
    code = [f for f in files if CODE.search(f) and not DOCS.search(f)]
    docs_only = not code
    planned = []
    for ax in AXES:
        if docs_only and ax["id"] not in ("profile-lenses", "verdict-channel"):
            continue  # a docs/skills-only diff has no runtime surface to review
        if ax["id"] in ALWAYS:
            planned.append(dict(ax, gated_by="always"))
            continue
        owned = [f for f in code if re.search(ax["paths"], f, re.I)]
        if not owned:
            continue
        if ax["content"] and not any(re.search(ax["content"], added_by_file[f], re.I)
                                     for f in owned):
            continue
        planned.append(dict(ax, gated_by="path+content" if ax["content"] else "path"))
    return planned


def cmd_plan(args) -> int:
    added_by_file = diff_added_by_file(args.base)
    files = list(added_by_file)
    if not files:
        print("no diff against", args.base, "— nothing to plan")
        return 0
    planned = plan_axes(added_by_file)
    sha = head_sha()
    run = {
        "head_sha": sha,
        "base": args.base,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "files": len(files),
        "planned": {ax["id"]: {"owner": ax["owner"], "tier": ax["tier"],
                               "gated_by": ax["gated_by"], "status": None,
                               "verdict": None, "findings": None, "note": None}
                    for ax in planned},
    }
    prev = load_run(sha)
    for aid, rec in (prev.get("planned") or {}).items():  # keep statuses on re-plan
        if aid in run["planned"] and rec.get("status"):
            run["planned"][aid].update({k: rec[k] for k in ("status", "verdict", "findings", "note")})
    save_run(sha, run)

    te = [a for a in planned if a["owner"].startswith("turbo-eyes")]
    sd = [a for a in planned if a["owner"].startswith("superdev")]
    print(f"head {sha} · {len(files)} files · {len(planned)} axes planned "
          f"({len(AXES) - len(planned)} gated out)\n")
    print(f"turbo-eyes:review-code owns {len(te)} — run it once, then `ingest`:")
    for a in te:
        print(f"  {a['id']:<16} {a['owner']:<22} [{a['gated_by']}]")
    print(f"\nSuperDev owns {len(sd)} — run these lenses, then `record` each:")
    for a in sd:
        print(f"  {a['id']:<16} {a['owner']:<28} {a['tier']} [{a['gated_by']}]")
    print(f"\nstate: {run_path(sha)}")
    return 0


def cmd_ingest(args) -> int:
    fb = json.loads(Path(args.feedback).read_text())
    sha = args.sha or head_sha()
    run = load_run(sha)
    if not run:
        print("no plan for", sha, "— run `plan` first", file=sys.stderr)
        return 2
    statuses = fb.get("subskill_status") or {}
    findings_by_cat: dict[str, int] = {}
    for f in fb.get("findings") or []:
        for q in f.get("flagged_by") or []:
            findings_by_cat[q] = findings_by_cat.get(q, 0) + 1
    touched = 0
    for aid, rec in run["planned"].items():
        owner = rec["owner"]
        if not owner.startswith("turbo-eyes:"):
            continue
        q = owner.split(":", 1)[1]
        raw = statuses.get(q)
        if raw is None:
            rec["status"], rec["note"] = "missing", f"{q} absent from subskill_status"
        else:
            rec["status"] = TE_STATUS.get(raw, "failed")
            rec["note"] = raw
            n = findings_by_cat.get(q, 0)
            rec["findings"] = n
            rec["verdict"] = ("clean" if n == 0 else "findings") if rec["status"] == "ran" else None
        touched += 1
    run["turbo_eyes_run_id"] = fb.get("run_id")
    run["turbo_eyes_verdict"] = fb.get("verdict")
    save_run(sha, run)
    print(f"ingested {touched} turbo-eyes axes (run {fb.get('run_id')}, verdict {fb.get('verdict')})")
    return 0


def cmd_record(args) -> int:
    sha = args.sha or head_sha()
    run = load_run(sha)
    if not run:
        print("no plan for", sha, "— run `plan` first", file=sys.stderr)
        return 2
    if args.axis not in run["planned"]:
        print(f"axis '{args.axis}' was not planned for this diff. Planned: "
              f"{', '.join(run['planned'])}", file=sys.stderr)
        return 2
    rec = run["planned"][args.axis]
    rec["status"] = args.status
    rec["findings"] = args.findings
    rec["note"] = args.note
    if args.status == "ran":
        rec["verdict"] = "clean" if (args.findings or 0) == 0 else "findings"
    else:
        rec["verdict"] = None
        if args.status == "na" and not args.note:
            print("`na` needs --note with the reason", file=sys.stderr)
            return 2
    save_run(sha, run)
    print(f"{args.axis}: {args.status}" + (f" · {rec['verdict']}" if rec["verdict"] else "")
          + (f" · {args.findings} finding(s)" if args.findings else ""))
    return 0


def cmd_assert(args) -> int:
    sha = args.sha or head_sha()
    run = load_run(sha)
    if not run:
        print("COVERAGE FAIL — no plan recorded for", sha, file=sys.stderr)
        return 1
    bad = []
    print(f"coverage for {sha} ({run['files']} files, base {run['base']})\n")
    print(f"  {'axis':<18}{'owner':<30}{'status':<14}verdict")
    for aid, rec in run["planned"].items():
        st = rec["status"] or "UNACCOUNTED"
        v = rec["verdict"] or "-"
        n = f" ({rec['findings']})" if rec.get("findings") else ""
        print(f"  {aid:<18}{rec['owner']:<30}{st:<14}{v}{n}")
        if rec["status"] in (None, "missing", "failed"):
            bad.append((aid, st))
        elif rec["status"] == "ran" and rec["verdict"] not in ("clean", "findings"):
            bad.append((aid, "ran-without-verdict"))
        elif rec["status"] == "na" and not rec["note"]:
            bad.append((aid, "na-without-reason"))
    if bad:
        print("\nCOVERAGE FAIL — L2 is not complete:")
        for aid, why in bad:
            print(f"  - {aid}: {why}")
        print("\nA skipped axis is not a clean axis. Run the owner, or record `na` with a reason.")
        return 1
    ran = sum(1 for r in run["planned"].values() if r["status"] == "ran")
    print(f"\nCOVERAGE OK — {ran} axes ran, "
          f"{len(run['planned']) - ran} explicitly n/a. L2 may pass.")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "coverage",
                             "head_sha": sha, "pr": args.pr,
                             "axes": {a: {"status": r["status"], "findings": r["findings"]}
                                      for a, r in run["planned"].items()}}) + "\n")
    return 0


def cmd_miss(args) -> int:
    known = {ax["id"] for ax in AXES}
    if args.axis not in known:
        print(f"unknown axis '{args.axis}'. Known: {', '.join(sorted(known))}", file=sys.stderr)
        return 2
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    owner = next(ax["owner"] for ax in AXES if ax["id"] == args.axis)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "miss",
                             "axis": args.axis, "owner": owner, "source": args.source,
                             "pr": args.pr, "note": args.note}) + "\n")
    print(f"gate miss logged: {args.axis} (owner {owner}) — raised by {args.source}")
    return 0


def cmd_yield(args) -> int:
    if not LEDGER.exists():
        print("no ledger yet — run `assert` on a few heads first")
        return 0
    rows = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    cov = [r for r in rows if r["kind"] == "coverage"][-args.last:]
    miss = [r for r in rows if r["kind"] == "miss"]
    stats: dict[str, dict] = {}
    for r in cov:
        for aid, rec in r["axes"].items():
            s = stats.setdefault(aid, {"planned": 0, "ran": 0, "found": 0, "missed": 0})
            s["planned"] += 1
            if rec["status"] == "ran":
                s["ran"] += 1
            s["found"] += rec.get("findings") or 0
    for m in miss:
        stats.setdefault(m["axis"], {"planned": 0, "ran": 0, "found": 0, "missed": 0})["missed"] += 1
    print(f"per-axis yield over the last {len(cov)} head(s), {len(miss)} logged gate miss(es)\n")
    print(f"  {'axis':<18}{'owner':<30}{'ran/planned':<13}{'found':<8}{'missed':<8}verdict")
    for aid, s in sorted(stats.items(), key=lambda kv: (-kv[1]["found"], kv[0])):
        owner = next((ax["owner"] for ax in AXES if ax["id"] == aid), "?")
        if s["missed"]:
            v = f"LEAKING ({s['missed']}) — tighten or re-own it"
        elif s["found"]:
            v = "earning its slot"
        elif s["ran"] >= args.prune_after:
            # Clean-and-never-leaked is ambiguous: it may be prevention, or it may
            # be dead weight. Flag it for a human call, don't declare it useless.
            v = f"no signal in {s['ran']} runs — candidate to fold in (judgment)"
        else:
            v = "too early to judge"
        print(f"  {aid:<18}{owner:<30}{str(s['ran']) + '/' + str(s['planned']):<13}"
              f"{s['found']:<8}{s['missed']:<8}{v}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="gate the diff into axes + owners")
    p.add_argument("--base", default="origin/main")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("ingest", help="read turbo-eyes review-feedback JSON")
    p.add_argument("--feedback", required=True)
    p.add_argument("--sha")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("record", help="record a SuperDev-owned axis")
    p.add_argument("--axis", required=True)
    p.add_argument("--status", required=True, choices=["ran", "na", "failed"])
    p.add_argument("--findings", type=int, default=0)
    p.add_argument("--note")
    p.add_argument("--sha")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("assert", help="fail unless every planned axis is accounted")
    p.add_argument("--sha")
    p.add_argument("--pr")
    p.set_defaults(fn=cmd_assert)

    p = sub.add_parser("miss", help="attribute a GitHub-raised finding to its axis")
    p.add_argument("--axis", required=True)
    p.add_argument("--source", required=True,
                   choices=["github-bot", "github-human", "production"])
    p.add_argument("--pr")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_miss)

    p = sub.add_parser("yield", help="per-axis hit rate; names surfaces to prune")
    p.add_argument("--last", type=int, default=50)
    p.add_argument("--prune-after", type=int, default=8)
    p.set_defaults(fn=cmd_yield)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
