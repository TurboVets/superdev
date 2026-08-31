#!/usr/bin/env bash
# Local replica of the @codex-tv / @claude-tv GitHub PR reviewers.
#
# Assembles the SAME prompt stack the auto-review workflows build
# (.github/workflows/codex-auto-review.yml / claude-auto-review.yml) and runs
# it through the same engines locally, so a local APPROVE predicts the GitHub
# bots' verdicts before a PR ever exists.
#
# Differences from CI (unavoidable, kept minimal):
#   - Diff scope is the local branch vs a base ref (default origin/main),
#     read via git — CI reads the PR merge ref / `gh pr diff`.
#   - Output is a markdown review + explicit VERDICT line on stdout/file —
#     CI posts JSON (codex-publish-review.cjs) / GitHub comments.
#   - Gates stay "deferred" exactly like CI (bots never run nx/npm there).
#
# Usage (run from the repo root of the branch under review):
#   local-bot-review.sh [--base origin/main] [--title "PR title"] \
#       [--body-file /tmp/pr-body.md] [--only codex|claude] [--out-dir /tmp]
set -euo pipefail

BASE="origin/main"
TITLE="(local pre-PR review)"
BODY_FILE=""
ONLY=""
OUT_DIR="/tmp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --body-file) BODY_FILE="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# Bots review the committed base...HEAD diff only. Uncommitted WIP makes a local
# APPROVE lie about what GitHub Codex will see (and what CI will check out).
if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree is dirty. Commit (or stash) before local-bot-review —" >&2
  echo "       GitHub @codex-tv / @claude-tv only see committed base...HEAD." >&2
  git status -sb >&2
  exit 1
fi

HEAD_SHA=$(git rev-parse --short HEAD)
BODY=""
[[ -n "$BODY_FILE" && -f "$BODY_FILE" ]] && BODY=$(cat "$BODY_FILE")

require() { [[ -f "$1" ]] || { echo "missing prompt source: $1" >&2; exit 1; }; }
for f in .github/prompts/codex-review-shared.md .github/prompts/claude-review-shared.md \
         .github/prompts/tv-fullstack-review.md .github/prompts/github-issue-bdd-review.md \
         docs/ai/pr-review.md docs/ai/coding-standards.md docs/ai/styling.md \
         .claude/skills/tv-fullstack/SKILL.md; do
  require "$f"
done

local_adapter() {
  # Local-mode deltas from the CI harness, stated up front for the model.
  cat <<EOF
=== LOCAL PRE-PR MODE (deltas from the CI harness) ===
You are running LOCALLY as a pre-PR gate replica of the GitHub auto-reviewer.
- Review the changes of the current branch vs ${BASE}. Discover them with:
    git log --oneline ${BASE}..HEAD
    git diff ${BASE}...HEAD
  (Use git directly; 'gh pr diff' / PR refs do not exist yet.)
- Do NOT post to GitHub, do not edit files, do not run nx/npm gate commands
  (mark gates "deferred to CI" exactly as the CI instructions say).
- Ignore CI-only output plumbing (JSON schema, inline-comment publishing,
  update_claude_comment, formal 'gh pr review'). Instead, END your response
  with the review in this markdown shape:
    ## Review summary
    <summary incl. Gates + Half coverage + Stability pass lines>
    ## Findings
    - [P0|P1|P2] [FE|BE|SEAM] file:line — issue / why / fix
    ## VERDICT
    exactly one line: "VERDICT: APPROVE" or "VERDICT: CHANGES_REQUESTED — <reason>"
- Mandatory: execute the **stability / fix-path pass** in
  .claude/skills/tv-fullstack/SKILL.md before APPROVE (sibling writers of any
  new lock/invariant; on re-reviews that pass is the primary job). Report
  \`Stability pass: ran | n/a — …\` in the summary.
- Everything else in the inlined instructions applies unchanged (severity
  bars, confidence bar, full-stack audit adapter, BDD rules).
EOF
}

codex_prompt() {
  local out="$1"
  {
    printf 'You are reviewing a local pre-PR branch in ${SUPERDEV_DEFAULT_REPO:-this-repo}.\n\n'
    local_adapter
    printf '\nThe following instructions are inlined from project files.\n'
    printf 'Originals are also available in the repo for additional context.\n\n'
    printf '=== REVIEW INSTRUCTIONS (from .github/prompts/codex-review-shared.md) ===\n'
    cat .github/prompts/codex-review-shared.md
    printf '\n=== FULL-STACK AUDIT ADAPTER (from .github/prompts/tv-fullstack-review.md) ===\n'
    cat .github/prompts/tv-fullstack-review.md
    printf '\n=== PR REVIEW RULES (from docs/ai/pr-review.md) ===\n'
    cat docs/ai/pr-review.md
    printf '\n=== CODING STANDARDS (from docs/ai/coding-standards.md) ===\n'
    cat docs/ai/coding-standards.md
    printf '\n=== BDD REVIEW RULES (from .github/prompts/github-issue-bdd-review.md) ===\n'
    cat .github/prompts/github-issue-bdd-review.md
    printf '\n=== STYLING CATALOG (from docs/ai/styling.md) ===\n'
    cat docs/ai/styling.md
    printf '\nThis is a full PR review: execute the full-stack audit adapter above.\n'
    printf 'Read .claude/skills/tv-fullstack/SKILL.md and the required domain/leaf skills from disk.\n\n'
    printf 'Pull request title: %s\n' "$TITLE"
    printf 'Pull request body:\n---\n%s\n' "$BODY"
  } > "$out"
}

claude_prompt() {
  local out="$1"
  {
    printf 'You are reviewing a local pre-PR branch in ${SUPERDEV_DEFAULT_REPO:-this-repo} (head %s).\n\n' "$HEAD_SHA"
    local_adapter
    printf '\nRead and follow ALL instructions in .github/prompts/claude-review-shared.md\n'
    printf '(apply the LOCAL PRE-PR MODE deltas above where it references gh/GitHub).\n'
    printf 'This is a full PR review: also Read and execute\n'
    printf '.github/prompts/tv-fullstack-review.md (loads /tv-fullstack and the\n'
    printf 'domain audits). Merge FE/BE/SEAM findings into the review output.\n\n'
    printf 'Pull request title: %s\n' "$TITLE"
    printf 'Pull request body:\n---\n%s\n---\n' "$BODY"
  } > "$out"
}

run_codex() {
  local prompt="$OUT_DIR/local-review-codex-prompt.md"
  local outfile="$OUT_DIR/local-review-codex.md"
  codex_prompt "$prompt"
  echo ">>> codex (gpt-5.6-sol, xhigh — parity with codex-auto-review.yml) prompt: $(wc -c < "$prompt") bytes"
  local codex_bin=(codex)
  command -v codex >/dev/null 2>&1 || codex_bin=(npx --yes @openai/codex)
  "${codex_bin[@]}" exec --sandbox read-only --cd "$REPO_ROOT" \
    -m gpt-5.6-sol -c model_reasoning_effort='"xhigh"' \
    --output-last-message "$outfile" - < "$prompt" || {
      echo "codex run with pinned model failed; retrying with default model" >&2
      "${codex_bin[@]}" exec --sandbox read-only --cd "$REPO_ROOT" \
        --output-last-message "$outfile" - < "$prompt"
    }
  echo ">>> codex review saved: $outfile"
  rg -n '^VERDICT:' "$outfile" || echo "codex: no VERDICT line found — inspect $outfile"
}

run_claude() {
  local prompt="$OUT_DIR/local-review-claude-prompt.md"
  local outfile="$OUT_DIR/local-review-claude.md"
  claude_prompt "$prompt"
  echo ">>> claude (opus — parity with claude-auto-review.yml) prompt: $(wc -c < "$prompt") bytes"
  claude -p --model opus \
    --allowedTools "Read,Glob,Grep,Bash(git log:*),Bash(git diff:*),Bash(git show:*),Bash(git status:*)" \
    < "$prompt" > "$outfile"
  echo ">>> claude review saved: $outfile"
  rg -n '^VERDICT:' "$outfile" || echo "claude: no VERDICT line found — inspect $outfile"
}

case "$ONLY" in
  codex) run_codex ;;
  claude) run_claude ;;
  '') run_codex; run_claude ;;
  *) echo "--only must be codex or claude" >&2; exit 2 ;;
esac
