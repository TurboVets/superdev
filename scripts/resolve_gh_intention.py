#!/usr/bin/env python3
"""Resolve a GitHub PR / issue / comment URL into a SuperDev stage + completion plan.

When the user pastes only a GitHub link (or a link plus SuperDev), SuperDev must
infer intention from the object itself — not ask "what should I do?"

Usage:
  python3 resolve_gh_intention.py <github-url-or-number>
  python3 resolve_gh_intention.py --url https://github.com/TurboVets/platform/pull/9055#issuecomment-...
  python3 resolve_gh_intention.py 9055          # defaults to operator.yaml github.default_repo, falls back to issue

Exit 0 always when resolution succeeds; prints JSON to stdout.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from lib_paths import default_repo, github_login, operator_name

DEFAULT_REPO = default_repo()
OWNER_LOGIN = github_login()

# URL shapes we accept
PR_RE = re.compile(
    r"https?://github\.com/(?P<repo>[^/]+/[^/]+)/pull/(?P<num>\d+)"
    r"(?:#(?P<frag>[\w-]+))?",
    re.I,
)
ISSUE_RE = re.compile(
    r"https?://github\.com/(?P<repo>[^/]+/[^/]+)/issues/(?P<num>\d+)"
    r"(?:#(?P<frag>[\w-]+))?",
    re.I,
)
COMMENT_FRAG_RE = re.compile(
    r"^(?:issuecomment|pullrequestreview|discussion_r|commits?)-?(?P<id>\d+)$",
    re.I,
)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def gh_json(cmd: list[str]) -> Any | None:
    result = run(cmd)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def parse_ref(raw: str) -> dict[str, Any]:
    text = raw.strip()
    m = PR_RE.search(text)
    if m:
        frag = m.group("frag") or ""
        kind = "pr"
        comment_kind = None
        comment_id = None
        if frag:
            cm = COMMENT_FRAG_RE.match(frag)
            if cm:
                comment_id = cm.group("id")
                if frag.lower().startswith("issuecomment"):
                    comment_kind = "issue_comment"
                elif frag.lower().startswith("pullrequestreview"):
                    comment_kind = "pr_review"
                elif frag.lower().startswith("discussion"):
                    comment_kind = "review_thread"
                else:
                    comment_kind = "fragment"
            else:
                comment_kind = "fragment"
        return {
            "input": text,
            "kind": kind,
            "repo": m.group("repo"),
            "number": int(m.group("num")),
            "fragment": frag or None,
            "comment_kind": comment_kind,
            "comment_id": comment_id,
        }

    m = ISSUE_RE.search(text)
    if m:
        frag = m.group("frag") or ""
        comment_kind = None
        comment_id = None
        if frag:
            cm = COMMENT_FRAG_RE.match(frag)
            if cm:
                comment_id = cm.group("id")
                comment_kind = "issue_comment"
            else:
                comment_kind = "fragment"
        return {
            "input": text,
            "kind": "issue",
            "repo": m.group("repo"),
            "number": int(m.group("num")),
            "fragment": frag or None,
            "comment_kind": comment_kind,
            "comment_id": comment_id,
        }

    # Bare number — try PR first, then issue
    if re.fullmatch(r"#?\d+", text):
        num = int(text.lstrip("#"))
        return {
            "input": text,
            "kind": "ambiguous_number",
            "repo": DEFAULT_REPO,
            "number": num,
            "fragment": None,
            "comment_kind": None,
            "comment_id": None,
        }

    raise SystemExit(f"unrecognized GitHub ref: {raw!r}")


def is_mine(author: str | None, assignees: list[str] | None = None) -> bool:
    if author and author.lower() == OWNER_LOGIN.lower():
        return True
    if assignees and any(a.lower() == OWNER_LOGIN.lower() for a in assignees):
        return True
    return False


def checks_summary(repo: str, number: int) -> dict[str, Any]:
    data = gh_json(
        [
            "gh",
            "pr",
            "checks",
            str(number),
            "--repo",
            repo,
            "--json",
            "name,state,bucket,workflow",
        ]
    )
    if not isinstance(data, list):
        return {"raw": None, "failing": [], "pending": [], "passing": 0}
    failing = [c for c in data if c.get("bucket") == "fail" or c.get("state") in {"FAILURE", "ERROR"}]
    pending = [c for c in data if c.get("bucket") == "pending" or c.get("state") in {"PENDING", "QUEUED", "IN_PROGRESS"}]
    passing = [c for c in data if c.get("bucket") == "pass" or c.get("state") in {"SUCCESS", "NEUTRAL", "SKIPPED"}]
    return {
        "total": len(data),
        "passing": len(passing),
        "failing": [{"name": c.get("name"), "state": c.get("state")} for c in failing[:12]],
        "pending": [{"name": c.get("name"), "state": c.get("state")} for c in pending[:12]],
    }


def latest_review_state(reviews: list[dict]) -> str | None:
    if not reviews:
        return None
    # Prefer newest by submittedAt
    ordered = sorted(reviews, key=lambda r: r.get("submittedAt") or "", reverse=True)
    return ordered[0].get("state")


def find_comment(
    repo: str,
    number: int,
    *,
    is_pr: bool,
    comment_kind: str | None,
    comment_id: str | None,
) -> dict[str, Any] | None:
    if not comment_id:
        return None

    if comment_kind == "pr_review":
        reviews = gh_json(
            [
                "gh",
                "api",
                f"repos/{repo}/pulls/{number}/reviews",
                "--paginate",
            ]
        )
        if isinstance(reviews, list):
            for r in reviews:
                if str(r.get("id")) == str(comment_id):
                    return {
                        "kind": "pr_review",
                        "id": r.get("id"),
                        "author": (r.get("user") or {}).get("login"),
                        "state": r.get("state"),
                        "body": (r.get("body") or "")[:4000],
                        "submitted_at": r.get("submitted_at"),
                    }

    # issue comments work for both issues and PRs
    comments = gh_json(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{number}/comments",
            "--paginate",
        ]
    )
    if isinstance(comments, list):
        for c in comments:
            if str(c.get("id")) == str(comment_id):
                return {
                    "kind": "issue_comment",
                    "id": c.get("id"),
                    "author": (c.get("user") or {}).get("login"),
                    "body": (c.get("body") or "")[:4000],
                    "created_at": c.get("created_at"),
                }

    if is_pr:
        # review comments (inline)
        rcs = gh_json(
            [
                "gh",
                "api",
                f"repos/{repo}/pulls/{number}/comments",
                "--paginate",
            ]
        )
        if isinstance(rcs, list):
            for c in rcs:
                if str(c.get("id")) == str(comment_id):
                    return {
                        "kind": "review_thread",
                        "id": c.get("id"),
                        "author": (c.get("user") or {}).get("login"),
                        "body": (c.get("body") or "")[:4000],
                        "path": c.get("path"),
                        "created_at": c.get("created_at"),
                    }
    return {"kind": comment_kind or "unknown", "id": comment_id, "missing": True}


def classify_pr(pr: dict[str, Any], checks: dict[str, Any], focus_comment: dict | None) -> dict[str, Any]:
    author = (pr.get("author") or {}).get("login")
    assignees = [a.get("login") for a in (pr.get("assignees") or []) if a.get("login")]
    mine = is_mine(author, assignees)
    state = (pr.get("state") or "").upper()  # OPEN / MERGED / CLOSED
    review = (pr.get("reviewDecision") or "").upper()  # CHANGES_REQUESTED / APPROVED / REVIEW_REQUIRED / ""
    is_draft = bool(pr.get("isDraft"))
    mergeable = pr.get("mergeable")  # MERGEABLE / CONFLICTING / UNKNOWN
    url = pr.get("url")
    title = pr.get("title")
    head = ((pr.get("headRefName") or ""), (pr.get("headRefOid") or "")[:12])
    latest = latest_review_state(pr.get("reviews") or [])

    # Comment-focused overrides
    comment_signals: list[str] = []
    if focus_comment and not focus_comment.get("missing"):
        body = (focus_comment.get("body") or "").lower()
        author_c = (focus_comment.get("author") or "").lower()
        if focus_comment.get("state") == "CHANGES_REQUESTED" or "changes requested" in body:
            comment_signals.append("changes_requested_comment")
        if any(k in body for k in ("lgtm", "approved", "ship it")):
            comment_signals.append("approve_signal")
        if any(k in body for k in ("fail", "broken", "flake", "e2e")) or re.search(
            r"\bci\b", body
        ):
            comment_signals.append("ci_diagnose")
        if any(k in body for k in ("smoke", "recording", "video", "screenshot")):
            comment_signals.append("smoke_gap")
        if author_c and author_c != OWNER_LOGIN.lower() and mine:
            comment_signals.append("human_review_reply")

    stage = "Path 7 Review"
    goal = "review_pr"
    completion: list[str] = []
    next_actions: list[str] = []
    hard_stop: str | None = None

    if not mine:
        stage = "Path 7 Review"
        goal = "review_pr"
        completion = [
            "Draft P0/P1 human review in chat only (never write to their GitHub objects)",
            "STAMP session-log",
        ]
        next_actions = [
            "Load /pr-review-lens + author isolation card",
            "Run tv-fullstack posture checklist against the diff (read-only)",
            "Emit SuperDev review draft for the operator to paste if he asks",
        ]
        hard_stop = "Teammate-owned PR — chat draft only; no gh write"
    elif state == "MERGED":
        stage = "Path 6 Prove & ship"
        goal = "status"
        completion = [
            "Confirm linked issues closed / hygiene updated in focus.md",
            "STAMP — no further ship work unless follow-up issue needed",
        ]
        next_actions = [f"Update focus.md / close shipped issues assigned to {OWNER_LOGIN or 'github.login'} if still open"]
    elif state == "CLOSED":
        stage = "Path 7 Review"
        goal = "diagnose"
        completion = ["Explain why closed; propose reopen or follow-up only if the operator owns it"]
        next_actions = ["Summarize close reason from timeline"]
    elif review == "CHANGES_REQUESTED" or "changes_requested_comment" in comment_signals or latest == "CHANGES_REQUESTED":
        stage = "Path 5.5 Full-stack audit"
        goal = "fix_bug"
        completion = [
            "Address each human P0/P1 on the OWN PR",
            "Local tv-fullstack ×2+ Ship",
            "Push + reply with SHAs (only when the operator asks to post)",
            "Re-request human review",
            "Then Path 6 prove (smoke if user-visible) until APPROVED + mergeable",
        ]
        next_actions = [
            "Fetch review threads / CHANGES_REQUESTED body",
            "Fix locally",
            "Path 5.5 audit gate",
            "Draft reply; post only if asked",
        ]
    elif is_draft:
        stage = "Path 5 Build" if not checks.get("failing") else "Path 5.5 Full-stack audit"
        goal = "implement"
        completion = [
            "Finish remaining AC / acceptance",
            "Path 5.5 Ship",
            "Mark ready for review when gates green",
            "Path 6 smoke + house PR body",
        ]
        next_actions = ["Diff against AC", "Build remaining gaps", "Enter Path 5.5"]
    elif mergeable == "CONFLICTING" and mine:
        # #9272 miss: Path 6 incomplete while dirty — resolve before smoke/embed
        stage = "Path 6 Prove & ship"
        goal = "ship_pr"
        completion = [
            "Resolve stack/base conflicts (rebase/merge → MERGEABLE)",
            "Force-with-lease own feature branch when needed for conflict fix",
            "Path 5.5 Ship on rebased head if commits changed",
            "User-visible ⇒ subtitled before/after smoke + inline player in PR body",
            "Fill Visual before-after table paired with the player",
        ]
        next_actions = [
            "Rebase onto current stack parent",
            "Push --force-with-lease",
            "Confirm mergeable:MERGEABLE",
            "Run tv-smoke-test + pr-asset-upload with on-screen titles",
        ]
    elif review == "APPROVED" and mergeable == "MERGEABLE" and not checks.get("failing") and not checks.get("pending"):
        stage = "Path 6 Prove & ship"
        goal = "ship_pr"
        completion = [
            "Confirm subtitled smoke embedded if user-visible (before/after + titles)",
            "Confirm Visual before-after table filled",
            "Merge (or enqueue) only when the operator explicitly asks",
            "Update focus.md + close linked issues",
        ]
        next_actions = ["Report ready-to-merge status", "Wait for explicit merge ask"]
    elif review == "APPROVED" and (checks.get("failing") or checks.get("pending") or "ci_diagnose" in comment_signals):
        # Approved but not green — finish the prove/ship lane, don't restart build
        stage = "Path 6 Prove & ship"
        goal = "diagnose" if checks.get("failing") or "ci_diagnose" in comment_signals else "status"
        completion = [
            "Root-cause failing/pending checks (code vs infra)",
            "If code: fix → re-audit → push (only if asked) → green checks",
            "If infra: report evidence in Agent chat only; do not post a GitHub comment until the unit is complete",
            "Merge only when the operator explicitly asks and checks are acceptable",
        ]
        next_actions = [
            "Inspect failing/pending check logs",
            "Decide code fix vs infra flake",
            "Stay on Path 6 until merge-ready (or blocked on explicit ask)",
        ]
    elif checks.get("failing") or "ci_diagnose" in comment_signals:
        stage = "Path 5.5 Full-stack audit"
        goal = "diagnose"
        completion = [
            "Root-cause failing checks (code vs infra)",
            "If code: fix → re-audit → push (only if asked) → green checks",
            "If infra: report evidence in Agent chat only; do not post a GitHub comment until the unit is complete",
            "Then continue Path 6 prove → human review → merge-when-asked",
        ]
        next_actions = [
            "Inspect failing check logs",
            "Decide code fix vs infra flake",
            "Continue Path 5.5 → Path 6 when green",
        ]
    elif review == "REVIEW_REQUIRED" or review == "":
        # Open PR awaiting review — own ship lane
        stage = "Path 5.5 Full-stack audit"
        goal = "ship_pr"
        completion = [
            "Local tv-fullstack ×2+ Ship",
            "Objective gates green",
            "PR mergeable (resolve CONFLICTING/DIRTY first)",
            "User-visible ⇒ subtitled before/after smoke + inline player in PR body",
            "Visual before-after table filled (paired with player)",
            "House PR description",
            "Request human review / address bots by evidence",
            "Reach APPROVED + mergeable (merge only when asked)",
        ]
        next_actions = [
            "Path 5.5 first",
            "Then Path 6 prove (conflicts → subtitled smoke → embed)",
            "Do not stop at 'status report' — continue toward completion",
        ]
    else:
        stage = "Path 5.5 Full-stack audit"
        goal = "ship_pr"
        completion = ["Audit → prove → human review → merge-when-asked"]
        next_actions = ["Inspect PR state deeply", "Continue lifecycle"]

    if "smoke_gap" in comment_signals and mine:
        if "User-visible ⇒ subtitled smoke embedded" not in completion:
            completion.insert(0, "Record + embed subtitled smoke (tv-smoke-test + pr-asset-upload)")
        next_actions.insert(0, "Path 6 smoke proof for the comment ask")

    if "human_review_reply" in comment_signals and mine:
        next_actions.insert(0, "Draft reply to the linked comment with SHA + evidence")

    return {
        "object": "pr",
        "repo": pr.get("url", "").split("github.com/")[-1].split("/pull")[0] if pr.get("url") else None,
        "number": pr.get("number"),
        "url": url,
        "title": title,
        "author": author,
        "assignees": assignees,
        "mine": mine,
        "state": state,
        "is_draft": is_draft,
        "review_decision": review,
        "latest_review_state": latest,
        "mergeable": mergeable,
        "head_ref": head[0],
        "head_sha": head[1],
        "checks": checks,
        "focus_comment": focus_comment,
        "comment_signals": comment_signals,
        "stage": stage,
        "goal": goal,
        "completion_means": completion,
        "next_actions": next_actions,
        "hard_stop": hard_stop,
        "intention_summary": f"PR #{pr.get('number')} ({title}): {stage} → complete when: {completion[0] if completion else 'n/a'}",
    }


def classify_issue(issue: dict[str, Any], focus_comment: dict | None) -> dict[str, Any]:
    author = (issue.get("author") or {}).get("login")
    assignees = [a.get("login") for a in (issue.get("assignees") or []) if a.get("login")]
    mine = is_mine(author, assignees)
    state = (issue.get("state") or "").upper()
    title = issue.get("title")
    body = issue.get("body") or ""
    labels = [l.get("name") for l in (issue.get("labels") or []) if l.get("name")]
    url = issue.get("url")

    ac_markers = len(re.findall(r"^\s*[-*]\s*\[[ xX]\]", body, re.M))
    has_ac = ac_markers >= 2 or "acceptance criteria" in body.lower()
    open_prs = []
    # linked PRs via timeline is expensive; use search
    search = gh_json(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            DEFAULT_REPO if "repo" not in (issue or {}) else (issue.get("url") or "").split("github.com/")[-1].split("/issues")[0] or DEFAULT_REPO,
            "--search",
            f"{issue.get('number')} in:title,body",
            "--state",
            "open",
            "--json",
            "number,title,author,url,reviewDecision,isDraft",
            "--limit",
            "10",
        ]
    )
    if isinstance(search, list):
        open_prs = search

    hard_stop = None
    if not mine and state == "OPEN":
        hard_stop = f"Issue not assigned to {OWNER_LOGIN or 'github.login'} — chat advice only; no gh write"
        stage = "Path 3 Grill"
        goal = "status"
        completion = ["Explain fit/ownership in chat; do not self-assign unless asked"]
        next_actions = ["Compare to sprint waterfall + lane; draft recommendation"]
    elif state == "CLOSED":
        stage = "Path 1 Pick"
        goal = "status"
        completion = ["Confirm closed correctly; update focus hygiene if needed"]
        next_actions = ["Check closing PR; stamp focus.md"]
    elif open_prs:
        # Prefer continuing the open PR that implements this issue
        own = [p for p in open_prs if (p.get("author") or {}).get("login") == OWNER_LOGIN]
        target = own[0] if own else open_prs[0]
        stage = "Path 5.5 Full-stack audit"
        goal = "ship_pr"
        completion = [
            f"Continue via open PR #{target.get('number')} to ship completion",
            "Path 5.5 → Path 6 → human review → merge-when-asked",
            "Close this issue when the shipping PR merges",
        ]
        next_actions = [
            f"Re-resolve intention on {target.get('url')}",
            "Do not start a duplicate PR",
        ]
    elif not has_ac:
        stage = "Path 3 Grill"
        goal = "implement"
        completion = [
            "Grill report Ready with testable AC",
            "Unknowns cleared (Path 4)",
            "Then Path 5 build on a branch",
            "Ship through Path 5.5 → commit+push+open PR (no second ask) → Path 6 proof",
        ]
        next_actions = ["Run SuperDev grill on the issue body", "Fill missing AC before code"]
    else:
        stage = "Path 5 Build"
        goal = "implement"
        completion = [
            "Implement AC on a branch",
            "Acceptance/BDD in same PR",
            "Path 5.5 Ship → commit+push+open PR (no second ask) → Path 6 prove/smoke → human review → merge-when-asked",
            "Close issue when shipping PR merges",
        ]
        next_actions = [
            "Confirm no open PR already covers this",
            "Path 5 build → immediately enter Path 5.5 when diff exists",
            "After Path 5.5 Ship: open the PR before status-only wrap-up",
        ]

    if focus_comment and not focus_comment.get("missing") and mine:
        next_actions.insert(0, "Incorporate the linked comment into grill/build plan")

    return {
        "object": "issue",
        "number": issue.get("number"),
        "url": url,
        "title": title,
        "author": author,
        "assignees": assignees,
        "mine": mine,
        "state": state,
        "labels": labels,
        "has_testable_ac": has_ac,
        "ac_checkbox_count": ac_markers,
        "open_related_prs": open_prs[:5],
        "focus_comment": focus_comment,
        "stage": stage,
        "goal": goal,
        "completion_means": completion,
        "next_actions": next_actions,
        "hard_stop": hard_stop,
        "intention_summary": f"Issue #{issue.get('number')} ({title}): {stage} → complete when: {completion[0] if completion else 'n/a'}",
    }


def resolve(raw: str) -> dict[str, Any]:
    ref = parse_ref(raw)
    repo = ref["repo"]
    number = ref["number"]

    if ref["kind"] in {"pr", "ambiguous_number"}:
        pr = gh_json(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "number,title,url,state,isDraft,reviewDecision,mergeable,author,assignees,headRefName,headRefOid,reviews,body",
            ]
        )
        if pr:
            focus = find_comment(
                repo,
                number,
                is_pr=True,
                comment_kind=ref.get("comment_kind"),
                comment_id=ref.get("comment_id"),
            )
            checks = checks_summary(repo, number)
            result = classify_pr(pr, checks, focus)
            result["resolved_from"] = ref
            result["resolved_at"] = datetime.now(timezone.utc).isoformat()
            return result
        if ref["kind"] == "pr":
            return {
                "error": f"PR #{number} not found in {repo}",
                "resolved_from": ref,
            }

    # Issue path (or ambiguous fallback)
    issue = gh_json(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,url,state,author,assignees,labels,body",
        ]
    )
    if not issue:
        return {"error": f"Could not resolve {raw} as PR or issue in {repo}", "resolved_from": ref}

    focus = find_comment(
        repo,
        number,
        is_pr=False,
        comment_kind=ref.get("comment_kind"),
        comment_id=ref.get("comment_id"),
    )
    # Fix repo for PR search inside classify_issue
    result = classify_issue(issue, focus)
    # patch open PR search to use correct repo
    if result.get("open_related_prs") == []:
        search = gh_json(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                repo,
                "--search",
                f"{number} in:title,body",
                "--state",
                "open",
                "--json",
                "number,title,author,url,reviewDecision,isDraft",
                "--limit",
                "10",
            ]
        )
        if isinstance(search, list) and search:
            result["open_related_prs"] = search[:5]
            own = [p for p in search if (p.get("author") or {}).get("login") == OWNER_LOGIN]
            target = own[0] if own else search[0]
            result["stage"] = "Path 5.5 Full-stack audit"
            result["goal"] = "ship_pr"
            result["completion_means"] = [
                f"Continue via open PR #{target.get('number')} to ship completion",
                "Path 5.5 → Path 6 → human review → merge-when-asked",
                "Close this issue when the shipping PR merges",
            ]
            result["next_actions"] = [
                f"Re-resolve intention on {target.get('url')}",
                "Do not start a duplicate PR",
            ]
            result["intention_summary"] = (
                f"Issue #{number} has open PR #{target.get('number')}: continue that PR to completion"
            )
    result["repo"] = repo
    result["resolved_from"] = ref
    result["resolved_at"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="GitHub PR/issue/comment URL or number")
    parser.add_argument("--url", dest="url_flag", help="GitHub URL (alternative to positional)")
    parser.add_argument("--pretty", action="store_true", help="Indent JSON")
    args = parser.parse_args()
    raw = args.url_flag or args.url
    if not raw:
        parser.error("provide a GitHub URL or number")
    result = resolve(raw)
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
