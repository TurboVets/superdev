#!/usr/bin/env python3
"""Classify Path 6 prove intensity from the diff — never from the PR title.

lite     — do not spend a full ladder on an aria/CSS/docs fix
standard — default user-visible change
full     — cannot lowball: auth, money, two-party, migrations, shared lib, …

When torn, return full. Title words like "quick fix" are ignored.

    python3 prove_intensity.py --base origin/main
    python3 prove_intensity.py --paths a.ts b.html --pretty
    python3 prove_intensity.py --self-check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DOCS = re.compile(
    r"(\.md$|\.mdc$|^docs/|\.claude/|\.cursor/skills/|README|LICENSE)", re.I
)
TEST = re.compile(r"(\.spec\.|\.test\.|\.feature$|/__tests__/)", re.I)
STYLE = re.compile(r"\.(scss|css)$", re.I)
CODE = re.compile(r"\.(ts|tsx|js|mjs|py|html|graphql|sql|dart)$", re.I)

FULL_PATH = [
    ("authz", r"(guard|permission|policy|ownership|authoriz|\brole\.ts)"),
    ("money", r"(payment|billing|invoice|payout|stripe|ledger)"),
    ("migration", r"(migrations?/|\.sql$)"),
    ("schema", r"(\.graphql$|schema\.graphql)"),
    ("shared_lib", r"^libs/(auth|shared|ui/|tds/|client|cases|documents|integrations)/"),
    ("two_party", r"(share|disconnect|poa|invite|org-switch|transfer|revoke|connection|my-representative)"),
    ("new_route", r"(\.routes\.ts$|/routes\.ts$)"),
    ("pii", r"(redact|audit-log|audit.snapshot)"),
    ("ai_runtime", r"(libs/ai/|agent-tools|calls-service)"),
]

FULL_CONTENT = [
    ("authz", r"(@Permissions|CanActivate|assertOwner|FORBIDDEN)"),
    ("concurrency", r"(FOR UPDATE|pg_advisory|lock_timeout|manager\.transaction)"),
    ("pii", r"(ssnLastFour|\balienNumber\b|serviceNumber|redactPii)"),
    ("two_party", r"(disconnect|revokeShare|dataShare|endConnection|poaRevok)"),
    ("money", r"(amountCents|payout|invoiceId)"),
]

LITE_ONLY = re.compile(
    r"(aria-|ariaLabel|i18n|class=|className|style=|tooltip|"
    r"import |from '|from \"|^\s*$|^\s*//|^\s*\*)",
    re.I,
)

LADDER = {
    "lite": {
        "review_depth": "D1",
        "l1": "one_pass_or_skip_docs",
        "l3": "skip",
        "qa": "changed_control",
        "smoke": "skip_if_aria_or_docs_else_one_clip",
        "e2e": "skip",
    },
    "standard": {
        "review_depth": "D2",
        "l1": "x2_ship",
        "l3": "required",
        "qa": "claimed_surfaces",
        "smoke": "one_clip_hold_result",
        "e2e": "if_labeled",
    },
    "full": {
        "review_depth": "D3",
        "l1": "x2_ship_stability",
        "l3": "required",
        "qa": "both_sides",
        "smoke": "both_sides_hold_result",
        "e2e": "if_user_visible",
    },
}


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def added_by_file(base: str) -> dict[str, str]:
    body = sh(["git", "diff", f"{base}...HEAD"]) or sh(["git", "diff", "HEAD"])
    out: dict[str, list[str]] = {}
    cur = None
    for line in body.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            out.setdefault(cur, [])
        elif line.startswith("+") and not line.startswith("+++") and cur:
            out[cur].append(line[1:])
    merged = {f: "\n".join(v) for f, v in out.items()}
    for f in sh(["git", "ls-files", "--others", "--exclude-standard"]).splitlines():
        if not f:
            continue
        try:
            merged.setdefault(f, Path(f).read_text(errors="ignore"))
        except OSError:
            merged.setdefault(f, "")
    return merged


def reasons_for(files: list[str], added: dict[str, str]) -> list[str]:
    found: list[str] = []
    joined = "\n".join(files)
    for name, pat in FULL_PATH:
        if re.search(pat, joined, re.I):
            found.append(name)
    for path, text in added.items():
        if DOCS.search(path):
            continue
        for name, pat in FULL_CONTENT:
            if re.search(pat, text):
                found.append(f"{name}:content")
    runtime = [f for f in files if CODE.search(f) and not DOCS.search(f) and not TEST.search(f)]
    if len(runtime) > 20:
        found.append("size")
    # unique, stable order
    seen = []
    for r in found:
        if r not in seen:
            seen.append(r)
    return seen


def is_lite_surface(files: list[str], added: dict[str, str]) -> bool:
    runtime = [
        f
        for f in files
        if not DOCS.search(f) and not TEST.search(f) and (CODE.search(f) or STYLE.search(f))
    ]
    if len(runtime) > 3:
        return False
    for path in runtime:
        if STYLE.search(path):
            continue
        text = added.get(path, "")
        code_lines = [ln for ln in text.splitlines() if ln.strip()]
        if not code_lines:
            continue
        if any(not LITE_ONLY.search(ln) for ln in code_lines):
            return False
    return True


def classify(files: list[str], added: dict[str, str] | None = None) -> dict:
    added = added or {f: "" for f in files}
    docs_only = bool(files) and all(DOCS.search(f) for f in files)
    reasons = reasons_for(files, added)
    runtime = [
        f
        for f in files
        if CODE.search(f) and not DOCS.search(f) and not TEST.search(f)
    ]

    if reasons:
        intensity = "full"
        why = "full trigger — cannot lowball"
    elif docs_only or (not runtime and is_lite_surface(files, added)):
        intensity = "lite"
        why = "docs/chore only"
    elif is_lite_surface(files, added):
        intensity = "lite"
        why = "≤3 files, copy/CSS/aria only"
    else:
        intensity = "standard"
        why = "default — no full trigger, not a lite surface"

    row = dict(LADDER[intensity])
    if docs_only:
        row["l1"] = "skip_docs"
        row["smoke"] = "skip"
        row["qa"] = "skip"
    return {
        "intensity": intensity,
        "why": why,
        "reasons": reasons,
        "files": len(files),
        "runtime_files": len(runtime),
        **row,
    }


def self_check() -> int:
    cases = [
        (
            ["apps/vets/ui/ssn.html"],
            {"apps/vets/ui/ssn.html": '[aria-label]="Edit SSN"'},
            "lite",
        ),
        (
            ["libs/vets/poa/src/disconnect.provider.ts"],
            {"libs/vets/poa/src/disconnect.provider.ts": "endConnection()"},
            "full",
        ),
        (
            ["apps/vets/ui/x.ts", "apps/vets/ui/x.spec.ts"],
            {"apps/vets/ui/x.ts": "onClick() { this.save(); }"},
            "standard",
        ),
        (["docs/ai/foo.md"], {"docs/ai/foo.md": "# note"}, "lite"),
        (
            ["libs/auth/src/foo.guard.ts"],
            {"libs/auth/src/foo.guard.ts": "canActivate() {}"},
            "full",
        ),
        (
            [f"apps/vets/ui/a{i}.scss" for i in range(21)],
            {f"apps/vets/ui/a{i}.scss": ".x{}" for i in range(21)},
            "standard",  # scss is not CODE runtime; size counts CODE runtime only
        ),
    ]
    # 21 style files: no CODE runtime, no full path → lite surface? runtime style
    # count is 21 > 3 so is_lite_surface False → standard. Good (not full).
    failed = 0
    for files, added, expect in cases:
        got = classify(files, added)["intensity"]
        if got != expect:
            print(f"FAIL {files[0]}… expected {expect} got {got}", file=sys.stderr)
            failed += 1
    # one-file auth must be full even if tiny
    tiny_guard = classify(
        ["apps/vets/backend/x.guard.ts"],
        {"apps/vets/backend/x.guard.ts": "export class X {}"},
    )
    if tiny_guard["intensity"] != "full":
        print("FAIL tiny guard must be full", file=sys.stderr)
        failed += 1
    # title-shaped files do not matter — no title input exists
    if failed:
        print(f"{failed} self-check(s) failed", file=sys.stderr)
        return 1
    print("prove_intensity self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--paths", nargs="*", default=[])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        return self_check()

    if args.paths:
        files = args.paths
        added = {f: "" for f in files}
    else:
        added = added_by_file(args.base)
        files = list(added) or [
            ln
            for ln in sh(["git", "diff", "--name-only", f"{args.base}...HEAD"]).splitlines()
            if ln
        ]
    result = classify(files, added)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
        return 0
    reasons = ",".join(result["reasons"]) or "none"
    line = (
        f"prove_intensity: {result['intensity']} · review_depth: {result['review_depth']} "
        f"· reasons: {reasons} · {result['why']}"
    )
    print(line)
    if args.pretty:
        print(
            f"  L1 {result['l1']} · L3 {result['l3']} · "
            f"QA {result['qa']} · smoke {result['smoke']} · e2e {result['e2e']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
