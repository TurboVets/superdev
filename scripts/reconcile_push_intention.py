#!/usr/bin/env python3
"""Reconcile asked intention vs what the push actually is.

Chat tags lie. The commit + files + PR body are the intention that shipped.
If SuperDev missed a prove rung the user asked for — or lowballed a full
diff — this script exits 1 and writes a learn-ledger `miss`. Path 6 is not
done until it exits 0.

    python3 reconcile_push_intention.py --asked "…" --files a.ts --body "…"
    python3 reconcile_push_intention.py --base origin/main --pr 1 --write-learn
    python3 reconcile_push_intention.py --self-check
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prove_intensity import classify as classify_diff  # noqa: E402

QA_ASK = re.compile(r"\b(tv-qa|live qa|6a|not covered|leftover)\b", re.I)
SMOKE_ASK = re.compile(r"\b(smoke|recording|player|subtitle)\b", re.I)
SKILL_ASK = re.compile(r"\b(superdev|intention|skill|self-?learn)\b", re.I)
QUICK_ASK = re.compile(r"\b(quick fix|nit|chore only|easy fix)\b", re.I)
THOROUGH_ASK = re.compile(r"\b(thorough|end to end|both sides?|do not lowball|lowball)\b", re.I)
NOT_COVERED = re.compile(r"\bnot covered\b", re.I)
QA_EVIDENCE = re.compile(r"(QA findings|live QA|6a|clicked as)\b", re.I)
SMOKE_EVIDENCE = re.compile(r"user-attachments|Visual before-after|before.?after", re.I)
BOTH_SIDES = re.compile(r"\b(both sides?|as Janet|as Tamara|Veteran login|org B)\b", re.I)
SKILL_FILE = re.compile(r"(SKILL\.md|prove_intensity|live-qa|fullstack-audit|intention|reconcile_push)", re.I)


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def extract_asked(text: str) -> dict:
    return {
        "text": text,
        "wants_qa": bool(QA_ASK.search(text)),
        "wants_smoke": bool(SMOKE_ASK.search(text)),
        "wants_skill": bool(SKILL_ASK.search(text)),
        "said_quick": bool(QUICK_ASK.search(text)),
        "said_thorough": bool(THOROUGH_ASK.search(text)),
    }


def extract_pushed(files: list[str], commits: str, body: str) -> dict:
    blob = f"{commits}\n{body}\n" + "\n".join(files)
    # Filenames-only: a .ts/.html is not aria-lite. Give classify a non-lite line
    # so an empty added-map cannot collapse a real code file to lite.
    added = {
        f: (
            ""
            if not re.search(r"\.(ts|tsx|html|py)$", f) or ".spec." in f
            else "placeholder();"
        )
        for f in files
    }
    intensity = classify_diff(files, added)
    return {
        "files": files,
        "commits": commits,
        "intensity": intensity["intensity"],
        "reasons": intensity["reasons"],
        "has_qa": bool(QA_EVIDENCE.search(body)),
        "has_not_covered": bool(NOT_COVERED.search(body)),
        "has_smoke": bool(SMOKE_EVIDENCE.search(blob)),
        "has_both_sides": bool(BOTH_SIDES.search(body)),
        "touched_skill": any(SKILL_FILE.search(f) for f in files),
        "summary": (commits.splitlines()[0] if commits.strip() else "")[:160],
    }


def gaps(asked: dict, pushed: dict) -> list[str]:
    out: list[str] = []
    user_visible = any(re.search(r"(apps/.+/ui|\.html$|\.component\.)", f) for f in pushed.get("files") or [])
    if asked["wants_qa"] and pushed["has_not_covered"]:
        out.append("not_covered_posted")
    if (asked["wants_qa"] or (user_visible and pushed["intensity"] in {"standard", "full"})) and not pushed["has_qa"]:
        out.append("asked_qa_not_evidenced")
    if asked["wants_smoke"] or (user_visible and pushed["intensity"] in {"standard", "full"}):
        if not pushed["has_smoke"]:
            out.append("smoke_player_missing")
    if pushed["intensity"] == "full" and not pushed["has_both_sides"]:
        if asked["wants_qa"] or asked["said_thorough"] or asked["wants_smoke"]:
            out.append("full_missing_both_sides")
    if asked["said_quick"] and pushed["intensity"] == "full":
        out.append("title_lowball_push_is_full")
    if asked["wants_skill"] and asked["said_thorough"] is False:
        # skill-change ask without a skill file in the push
        if SKILL_ASK.search(asked["text"]) and "land" in asked["text"].lower():
            if not pushed["touched_skill"]:
                out.append("asked_skill_change_not_in_push")
        elif re.search(r"\b(update|improvise|modify|land)\b.*\b(superdev|intention|skill)", asked["text"], re.I):
            if not pushed["touched_skill"]:
                out.append("asked_skill_change_not_in_push")
    return out


def reconcile(asked_text: str, files: list[str], commits: str, body: str) -> dict:
    asked = extract_asked(asked_text)
    pushed = extract_pushed(files, commits, body)
    found = gaps(asked, pushed)
    return {
        "asked": {k: v for k, v in asked.items() if k != "text"},
        "pushed_intensity": pushed["intensity"],
        "pushed_reasons": pushed["reasons"],
        "pushed_summary": pushed["summary"],
        "evidence": {
            "qa": pushed["has_qa"],
            "not_covered": pushed["has_not_covered"],
            "smoke": pushed["has_smoke"],
            "both_sides": pushed["has_both_sides"],
            "skill_files": pushed["touched_skill"],
        },
        "gaps": found,
        "verdict": "match" if not found else "miss",
    }


def write_learn(result: dict) -> Path | None:
    candidates = [
        Path.home() / ".cursor/skills/local-memory/user-intentions/learn-ledger.jsonl",
        HERE.parent / "state" / "user-intentions" / "learn-ledger.jsonl",
    ]
    dest = next((p for p in candidates if p.parent.exists() or p == candidates[-1]), candidates[-1])
    dest.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": "miss" if result["verdict"] == "miss" else "none",
        "learned": (
            "push matched asked intention"
            if result["verdict"] == "match"
            else "push missed: " + ", ".join(result["gaps"])
        )[:600],
        "files_changed": [],
        "prompt_summary": (result.get("pushed_summary") or "")[:200],
        "source": "reconcile_push_intention",
        "gaps": result["gaps"],
        "intensity": result["pushed_intensity"],
    }
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return dest


def live_inputs(base: str, pr: int | None) -> tuple[str, list[str], str, str]:
    files = [ln for ln in sh(["git", "diff", "--name-only", f"{base}...HEAD"]).splitlines() if ln]
    commits = sh(["git", "log", "--oneline", f"{base}...HEAD"])
    body = ""
    if pr:
        raw = sh(["gh", "pr", "view", str(pr), "--json", "title,body"])
        try:
            data = json.loads(raw)
            body = f"{data.get('title') or ''}\n{data.get('body') or ''}"
        except json.JSONDecodeError:
            body = raw
    asked = ""
    hist = Path.home() / ".cursor/skills/local-memory/user-intentions/prompt-history.jsonl"
    if hist.exists():
        rows = [json.loads(ln) for ln in hist.read_text().splitlines() if ln.strip()][-8:]
        asked = "\n".join(r.get("prompt") or r.get("summary") or "" for r in rows)
    return asked, files, commits, body


def self_check() -> int:
    cases = [
        (
            "do a tv-qa pass, no not covered, then smoke",
            ["apps/vets/ui/x.ts"],
            "feat: case refresh",
            "## QA findings\nclicked as Janet\nuser-attachments/assets/aaa\nVisual before-after",
            "match",
        ),
        (
            "do a tv-qa pass, i don't want a not covered section",
            ["apps/vets/ui/x.ts"],
            "feat: case refresh",
            "### Not covered\nStrengthen Remove",
            "miss",
        ),
        (
            "record smoke tests end to end",
            ["apps/vets/ui/x.ts"],
            "feat: case refresh",
            "Opened the PR. Smoke pending.",
            "miss",
        ),
        (
            "quick fix please",
            ["libs/auth/src/foo.guard.ts"],
            "fix: guard",
            "tiny nit",
            "miss",
        ),
        (
            "improvise SuperDev intention and land it",
            ["README.md"],
            "docs: typo",
            "typo",
            "miss",
        ),
        (
            "improvise SuperDev intention and land it",
            ["SKILL.md", "scripts/reconcile_push_intention.py"],
            "feat: reconcile push intention",
            "landed",
            "match",
        ),
    ]
    failed = 0
    for asked, files, commits, body, expect in cases:
        got = reconcile(asked, files, commits, body)["verdict"]
        if got != expect:
            print(f"FAIL {asked[:40]!r} expected {expect} got {got}", file=sys.stderr)
            failed += 1
    if failed:
        print(f"{failed} self-check(s) failed", file=sys.stderr)
        return 1
    print("reconcile_push_intention self-check ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asked", default="")
    ap.add_argument("--files", nargs="*", default=[])
    ap.add_argument("--commits", default="")
    ap.add_argument("--body", default="")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--write-learn", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()

    if args.self_check:
        return self_check()

    asked, files, commits, body = args.asked, args.files, args.commits, args.body
    if not files and not commits and not body:
        asked2, files, commits, body = live_inputs(args.base, args.pr)
        asked = asked or asked2

    result = reconcile(asked, files, commits, body)
    if args.write_learn:
        write_learn(result)
    if args.json:
        json.dump(result, sys.stdout, indent=2)
        print()
    else:
        gaps_s = ",".join(result["gaps"]) or "none"
        print(
            f"push_intention: {result['verdict']} · intensity: {result['pushed_intensity']} "
            f"· gaps: {gaps_s}"
        )
        if args.pretty:
            print(f"  asked qa/smoke/skill: {result['asked']}")
            print(f"  evidence: {result['evidence']}")
    return 0 if result["verdict"] == "match" else 1


if __name__ == "__main__":
    sys.exit(main())
