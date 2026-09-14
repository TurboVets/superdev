# Why tv-fullstack / Codex keeps finding new P0s

**Canonical in-repo copy (cite this, not this private file):**
`docs/ai/audit-convergence.md` in $github.default_repo — also
`.claude/skills/tv-fullstack/SKILL.md` **Stop condition**. Private SuperDev
copy stays as operator detail; never cite this path on GitHub.

Evidence: Slack Chris↔Hrishi 2026-08-12 on #9272; Chris: _"Codex runs
the tv-fullstack skills"_ + _"rerunning often finds more… it is not
complete"_ + PR approve note _"Not sure if they will ever stop."_
Codex rounds 1–6 on #9272 + Chris human audit after Codex LGTM.

## Contents

- [The short answer](#the-short-answer)
- [What Chris meant by "Codex runs the tv-fullstack skills"](#what-chris-meant-by-codex-runs-the-tv-fullstack-skills)
- [Why a local pass still loses to Codex / the next re-run](#why-a-local-pass-still-loses-to-codex--the-next-re-run)
- [The #9272 pattern (concrete)](#the-9272-pattern-concrete)
- [Convergent audit protocol (mandatory)](#convergent-audit-protocol-mandatory)
- [What a bot verdict can and cannot vouch for](#what-a-bot-verdict-can-and-cannot-vouch-for-corpus-2026-08-12)
- [Gates the house refused (do not add ceremony)](#gates-the-house-refused-do-not-add-ceremony)
- [What local-bot-review is for](#what-local-bot-review-is-for)

## The short answer

**Local "Ship" ≠ exhausted audit.** `tv-fullstack` is a **judgment skill
executed by an LLM**, not a deterministic checker. Each run samples a
different slice of the state space. Fixing one P0 often **creates new
edges** the next run explores. That is expected — not a broken gate.

## What Chris meant by "Codex runs the tv-fullstack skills"

GitHub `@codex-tv` does **not** run a separate secret checklist. CI
(`.github/workflows/codex-auto-review.yml`) assembles:

1. `codex-review-shared.md`
2. `tv-fullstack-review.md` (adapter → read `tv-fullstack` + domain leaves)
3. `docs/ai/pr-review.md` + coding-standards + styling + BDD

…then `codex exec` at **effort: xhigh** on the PR merge ref.

Claude odd-PR A/B does the same adapter. So Codex **is** tv-fullstack —
with a stronger model/effort and a fatter inlined context than a casual
local skim.

## Why a local pass still loses to Codex / the next re-run

| Gap                | Local SuperDev miss                                           | What Codex / next pass does                                  |
| ------------------ | ------------------------------------------------------------- | ------------------------------------------------------------ |
| Effort             | Task often T2–T3, one pass, token-economy skips leaf Reads    | `xhigh` + forced in-process FE+BE+seam                       |
| Completeness       | One "Ship" treated as done                                    | Chris: re-run finds more — skill has no "done bit"           |
| Fix-path blindness | Audit the _original_ bug; miss sibling paths the fix inverted | Next round finds lock-order / race on the _new_ code (#9272) |
| Head skew          | Uncommitted / wrong worktree / stale base                     | Reviews **committed** `base...HEAD`                          |
| Multiple judges    | One agent                                                     | Codex × N rounds + human Chris ≠ same sample                 |

## The #9272 pattern (concrete)

1. Codex round N flags race A → fix A.
2. Round N+1 flags race B **on the fix** (or a sibling path that still
   uses the old lock order).
3. Codex eventually LGTM (0.97).
4. Chris runs tv-fullstack again → **new** P0s (unlocked POA read,
   org-wide sibling vs per-requestor unique index, product-line copy).
5. Local fix of Chris P0s → re-audit finds **fix-path** issues
   (alternate revoke paths wrote POA before advisory; sticky CTA clear
   while sibling still open).

So P0s "keep showing up" because each round is a **new search**, not a
replay of a fixed test suite.

## Convergent audit protocol (mandatory)

Do **not** claim Path 5.5 Ship after a single green pass on concurrency-
heavy / multi-writer PRs.

1. Audit₁ → fix all P0/P1.
2. **Fix-path re-audit (Audit₂):** deliberately hunt sibling call sites
   that take **opposite lock order**, new advisory keys, FE sticky state
   after CONFLICT, product-line copy in shared libs. This is the pass
   that catches what Codex round N+1 would find.
3. Audit₃ (clean head) must also be **Ship with zero new P0/P1**.
4. Then `local-bot-review.sh` (Codex xhigh CLI + Cursor Claude opus Task).
5. Only then push / re-request GitHub bots.

**Stop condition:** two consecutive Ship verdicts on the **same SHA**
with no new P0/P1 between them, **plus** local bot APPROVE both.
Chris is right they may never hit absolute zero forever — the bar is
**convergence under that stop condition**, not infinite re-runs.

**Forever-loop ban (#9353 / Rishi 2026-08-12):** After the stop condition
hits, **exit the audit/bot loop**. Do not re-run Codex/Claude replicas
“just in case,” chase P2s, or invent speculative races. GitHub re-reviews
re-enter only for evidenced P0/P1 on the **fix path** (stability pass),
then re-apply the same stop. `#9353` wires that stability pass into the
in-repo skill/prompt stack bots load so local and GitHub share one
convergent contract.

## What a bot verdict can and cannot vouch for (corpus, 2026-08-12)

Bots are legitimate discovery — Chris routinely forwards their findings
verbatim ("Grok found the following", #8756) and then triages them
("Disagree that this is a ship-blocking P0 for the current UX", #8312). What
they cannot do is certify their own checks:

- **A bot checkmark is not evidence.** "The autoreviewer marked this
  'P0 #2 — ownership guard still intact ✅' on the basis that the decorator is
  present" — while the mutation returned `true` before ever calling the
  ownership check (Nick #8394). Re-verify any ✅ that claims enforcement.
- **Specs can hide what the bot trusts.** The same PR's rollback defect was
  invisible because the spec stubbed `manager.transaction` as a pass-through
  with no rollback semantics. When a bot cites a passing test as proof, check
  the harness can express the failure.
- **Rejecting a finding means fixing its cause.** When a bot finding is a false
  positive, fix the artifact that produced it and say so with a SHA
  (Ryan #8818) — otherwise the same finding returns every round and burns the
  convergence budget.

## Gates the house refused (do not add ceremony)

Chris's #8648 ruling: a rule lives in **exactly one leaf**; supersets point at
it. Two consequences for SuperDev:

- **Don't add a checklist gate for something CI already enforces** — the
  migration-drift check is CI's job, not a new manual step in a skill.
- **Don't restate a rule in a second skill file.** New rules land in the owning
  leaf (`review-bar.md` / `security-bar.md`); `SKILL.md` gets a pointer and the
  scan trigger, not a copy. This is the same "refactor, don't accrete"
  principle Principle 0 already states, with a house precedent behind it.

## What local-bot-review is for

`local-bot-review.sh` closes the model/effort gap: same prompt stack as
CI, Codex at high effort, before GitHub burn. A lone Cursor Task saying
"Ship" without that script is **not** predictive of `@codex-tv`.
