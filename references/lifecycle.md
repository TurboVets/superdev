# Lifecycle paths — full detail

`SKILL.md` carries the path table, the mandatory gates, and the ladder. This file
carries each path's steps verbatim, including the issue template, the grill
checklist, the unknowns gate, the Path 6 objective gates + exit checklist + smoke
subtitle rules, and the Path 7 review draft format. Load the path you are in.

## Contents

- [Path 1 — Pick](#path-1--pick)
- [Path 2 — Issue craft](#path-2--issue-craft)
- [Path 3 — Dissect / Grill](#path-3--dissect--grill)
- [Path 4 — Unknowns gate](#path-4--unknowns-gate)
- [Path 5 — Build](#path-5--build)
- [Path 6 — Prove & ship](#path-6--prove--ship)
- [Path 7 — Review](#path-7--review)

### Link resolution

| Link resolves to (examples)                | Stage            | Completion means (summary)                                                                                                           |
| ------------------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Unassigned issue (nobody assigned)         | Ship lane        | Assign to `$github.login`, then the issue row below. SuperDev+link authorizes this. Not a `hard_stop`.                               |
| **N issue/PR URLs in one prompt**          | N ship lanes     | N worktrees in parallel. One ticket per tree. Do not serialize "smallest first."                                                     |
| Issue, no AC / unclear                     | Path 3 → 4       | Grill Ready + unknowns cleared, then build through Path 6                                                                            |
| Issue, AC ready, no PR                     | Path 5 → 5.5 → 6 | Implement → L1 fullstack ×2 → L3 Codex+Claude → **open PR** → 6a browser QA → **green** 6b smoke → merge-when-asked                  |
| Issue with open own PR                     | Follow the PR    | Re-resolve on that PR URL; no duplicate PR                                                                                           |
| Own draft PR                               | Path 5 / 5.5     | Finish AC → audit → ready for review → Path 6                                                                                        |
| Own PR, CHANGES_REQUESTED / review comment | Path 5.5 → 6     | Fix P0/P1 → audit Ship → 6a leftover cases → 6b if needed → APPROVED                                                                 |
| Own PR, checks failing                     | Path 5.5 or 6    | Root-cause code vs infra (route repo `ci-failure-analysis` / `cd-failure-analysis`) → green or evidenced triage → continue ship lane |
| Own PR, APPROVED + green                   | Path 6           | Intensity-scaled 6a/6b if still owed; merge **only** when explicitly asked                                                           |
| Teammate PR / comment                      | Path 7           | Chat-only P0/P1 draft; never write their GitHub objects                                                                              |

### Path 1 — Pick

Use when the operator asks what to work on or the ask has no concrete ticket.

0. **Meetings (optional).** If Fathom MCP is configured (`operator.yaml` `mcp.fathom`),
   use it for transcripts the operator names. Never open with `list_meetings`.
   Skip this step entirely if Fathom is unset.
1. **Ticket source is GitHub issues** (`operator.yaml` `github.default_repo`).
   Do not use Jira / Atlassian MCP unless `ticket_source` is explicitly changed.
   `gh issue list --repo $github.default_repo --assignee $github.login --state open`
2. Prefer issues assigned to `$github.login` that are not already in-flight
   (an assigned issue with an open own PR is in-flight, not a new pick). Skip
   issues the operator did not name when they asked for "what's assigned to me
   and not started."
3. Lead with **2 concrete GitHub issue URLs**, priority, and why.
4. Do not self-assign while higher-priority owned work is open.
   **Exception:** SuperDev + a link to an unassigned issue is a ship order —
   assign to `$github.login` and take it to Path 6. `hard_stop` is only
   teammate-owned (someone else is assigned).
5. Update `state/focus.md` only when the active lane actually changes.

### Path 2 — Issue craft

Use when creating or sharpening a GitHub issue. Draft in chat by default;
create with `gh issue create` only when the operator explicitly asks, and only
when the issue will belong to `$github.login`.

```markdown
## Scope

<one small user/business outcome>

## Problem

<current behavior, who it hurts, why now>

## Acceptance criteria

- [ ] <happy path, testable>
- [ ] <fail-closed / empty / unauthorized path, testable>
- [ ] <data or audit behavior, testable>

## Non-goals

- <explicitly out of scope>

## Risks

- <data model / authZ / product / rollout risk>

## Unknowns to resolve before code

- U1 — <question> (owner: code | Mark | Chris | Tan)

## Spike / implementation shape

<spike first or feature PR; expected decomposition>

## Done when

- [ ] acceptance/BDD included
- [ ] local tv-fullstack ×2 green
- [ ] user-visible smoke embedded, if applicable

## Labels / assignment

Assignee: $github.login
Labels: <product/priority/type>
```

### Path 3 — Dissect / Grill

Use on any issue/idea before coding. The grill is the main guardrail against
building the wrong thing.

**Ask like the best question-askers (year mine + Slack):** Chris Carsey
(domain edges), Ash Chaurasia (workflow gut-checks with options), Tejas
(cross-PL blast radius), Justin (identity/POA reachability), Brandon
(claimant-relevant + AC coverage), Biswajit (UX fail-open). Steal their
_question shape_, not their tickets.

Checklist:

- User-visible behavior: what changes, for whom, and what does not change?
- AC: happy path, fail-closed/authZ, empty/error states, audit/logging.
- Product truth: any ITF/claim/VSO/session/share rule that needs Mark/Chris?
  **Grep the rulings corpus first** —
  `rg -i '<topic>' ~/.cursor/skills/superdev/state/slack/product-rulings.jsonl`
  (193+ dated, cited decisions; `settled/high` = product law, `in_flux` =
  verify with owner). Index: local-memory `slack/product-rulings.md`.
- Data model: stable ids vs labels, migrations, teardown registration.
- Boundaries: product-line scope, shared-lib neutrality, TurboDB `studio`.
- Decomposition: one PR, spike PR, or Sean-style `[plan 0..n]` stack?
- Acceptance: feature/scenario names that must ship in the same PR.
- Smoke: surfaces and subtitle script outline.
- **Live surface check:** `product-surface-map.md` (this folder — E2E-verified
  map of every vets surface + failure ledger + rerun commands). Does the
  target area have acceptance coverage? Which spec file guards it?
- Open unknowns: every question has owner + evidence path.
- **Run applicable SuperDev scales below** (score each 1–5; escalate ≤2).
- **2PRD (Hector / Matt Pocock, 2026-08-11):** the grill report **is** the
  PRD. Persist it (issue-body draft and/or work-unit notes) — chat is not the
  artifact. Do **not** emit a giant plan-mode dump; ask, then write decisions.
  Side-thread deep questions so the main grill stays the decision log.
- **UI:** TDS Artifacts proto (existing TDS HTML/CSS) before production Angular.
- **2Issues:** if the PRD is bigger than one PR, split into tickets that copy
  the relevant grill decisions. Do not implement a mega-plan.

#### Grill detail (on-demand — token saver)

Load only on Path 3: `references/grill-and-scales.md`
(scales S1–S13 + product grill bank + grill report template).
Do **not** inline that file into every turn.

### Path 4 — Unknowns gate

No implementation until unknowns are **Resolved** or **Escalated**, unless
Rishi explicitly chooses a spike PR.

```markdown
| ID  | Question   | Status    | Evidence                        | Owner |
| --- | ---------- | --------- | ------------------------------- | ----- |
| U1  | <question> | Resolved  | <code/PR/doc/slack digest cite> | code  |
| U2  | <question> | Escalated | <draft for Rishi to send>       | Mark  |
```

Resolution rules:

- Code unknowns → inspect code/history; cite file/PR.
- Product unknowns → draft outreach to Mark/Chris; never invent.
- Security unknowns → check #cursor-vuln-scan / Tan lane; draft residual risk.
- Slack is read-only; all outreach is chat text for the operator to send.

### Path 5 — Build (Battle Rhythm)

Use after Grill is Ready or a spike is explicitly chosen. Operator stays
**Cursor SuperDev** (do not switch to Codex-as-IDE). Load
`references/ponytail.md`. Mechanical I/O:

```bash
BR=~/.cursor/skills/superdev/scripts/battle_rhythm.py
```

Five human gates (Varun). Automate adjacent (setup/review/CI/smoke) harder
than core coding (Nick). Each gate has deterministic I/O — not a chat blob.

**K1 Kickoff (scope)** — this ticket is the only work in this worktree.

```bash
python3 ~/.cursor/skills/superdev/state/scripts/work_history.py --open \
  --unit issue-<N> --issue <N> [--pr <P>] --branch <b> \
  --worktree <name> [--instance <id>] [--coder-box <name>] \
  --stage 5 --summary "<one line>"
python3 $BR kickoff --unit issue-<N> --prd <2prd.md>
python3 $BR setup-green            # or --skip-reason "<why logs are green>"
```

Re-run `check_contradictions.py`; fix HIGH before touching code. Multi-ticket
epic: `python3 $BR harness --unit issue-<N>` then **one ticket per worktree**.
UI: TDS Artifacts proto (existing TDS HTML/CSS) before Angular.

**K2 Recon (read-only plan)** — no code yet. Human approves the plan.

```bash
python3 ~/.cursor/skills/platform-codebase-evolution/scripts/precedent_lookup.py
python3 $BR recon --prd <2prd.md>
```

Side-chat deep unknowns; this thread stays the decision log. Lessons are an
**index** (`file:line`) into live code, not a second codebase.

**K3 Implement** — LLM + human owns the how (un-debuggable agent code is a
defect). **Hard gate before the first write:** climb the ponytail ladder
(`references/ponytail.md`) and name the rung in one line. No rung named =
do not write (same miss as skipping L1). Always on; `/ponytail off` is
illegal here. Reuse `@turbovets/shared/utils` (rung 2). Never `ultra` on
auth / money / migrations / copy. Route FE/BE/TDS/domain skills. After each
failed auto-fix:

```bash
python3 $BR fail --unit issue-<N> --key lint|test|peer-review
```

Exit 1 at 3 → **stop and ask**. Local peer-review ×3 before L1; if the same
finding stays high-confidence, ask. Before Path 5.5:

```bash
python3 $BR deviate --prd <2prd.md> --base origin/main   # add --strict to fail
```

Architectural drift is a human decision. Acceptance/BDD in the same PR
(`acceptance-test` / `e2e` / `test`). Pre-push scan: `review-bar.md` F1–F11
(F11 = ponytail-review delete-list on this diff).

**K4 Test** — generate the human smoke checklist, then Path 5.5 (local audit
= Brandon Pre-flight). Never tag/request reviewers unless the operator names them.

```bash
python3 $BR smoke-script --prd <2prd.md>
```

Enter Path 5.5 immediately once a coherent diff exists. Local lint/build are
DoD — run, never eyeball.

**K5 Capture** — STAMP is this gate, not an afterthought.

```bash
python3 $BR capture --unit issue-<N>
python3 $BR miss --pattern "<new failure family>" --axis F3
python3 $BR promote    # SKILL.md only after >2 learn-ledger hits
```

Follow-up tickets inherit the 2PRD via separate worktrees (`harness` work log).

### Path 6 — Prove & ship

Use when a branch is approaching reviewability **and Path 5.5 is green**.

Classify intensity first (`prove_intensity.py --pretty`). Then **6a live QA**
(`references/live-qa.md`) then **6b smoke**. Attaching SuperDev runs both —
do not wait for a QA or fullstack skill tag.

> **Completeness bar.** SuperDev's job is **one GitHub issue → ready for
> human review.** Path 6 is **not done** when the PR is dirty, L1/L3
> unfinished, 6a still has unclicked planned cases, smoke is **red**, or
> (when smoke is required) there is no inline player / titles. SuperDev
> records 6b; a leftover **Not covered** list, "L1 spawned", or "say the
> word" stop is a miss. A mid-lane stop or hallucinated gate is the
> **parent's** to unstick. The artifacts (L1, L3 Codex **and** Claude,
> 6a, green 6b, E2E) are one unit.

1. Confirm Path 5.5 artifact for **this SHA**, scaled by intensity (lite: one
   pass or skip docs; standard/full: ×2 Ship; full: + stability). Stale after
   new commits ⇒ re-run 5.5. Do not QA or film on an unaudited head.
2. Objective gates: lint 0 errors / 0 new warnings, tests, format, schema,
   migrations, no `studio`. Plus the house gates below — rules and citations
   live in `references/review-bar.md` F7/F9, not restated here:
   - **Generated artifacts committed** — GraphQL schema; new route ⇒ route
     metadata **and** regenerated sitemap.
   - **One migration per branch**, present for every product line a shared
     entity touches — generate them with the house `gen-migrations` skill
     (throwaway Postgres baselined to prod/main, TypeORM emits the diff), never
     by hand: `references/external-skills.md` § 1.
   - **Dead-surface check** — knip green for the right reason: delete new
     methods whose only callers are their own specs.
   - **Reviewability** — correct base branch, no stray files, no committed
     smoke scripts or MP4s. A 1k-file diff gets dismissed unread.
   - **Body hygiene** — house format, no AI attribution; the body becomes the
     squash commit message.
   - **Flagged behavior verified with the flag on** before the PR claims it.
3. **Mergeable first:** stacked/base conflicts must be **resolved before**
   smoke and before calling Path 6 done. Rebase (or merge) onto the current
   stack parent; `gh pr view --json mergeable,mergeStateStatus` must show
   `MERGEABLE` / not `DIRTY`/`CONFLICTING`. Updating a rebased own branch
   with `--force-with-lease` is authorized when the user asked for conflict
   resolution or PR completeness on that owned PR — still never force-push
   `main`/`master`.
4. **Commit → push → open PR** on the owned ship lane when no open PR exists
   yet (or update the existing own PR) — **only once the local review ladder
   L1–L3 has passed on this head** (audit ×2 Ship · `/pr-review-lens`
   multi-profile pass · both bot replicas APPROVE). No PR is created off an
   unreviewed head. Given the ladder is green this is part of
   `completion_means` — **not** a separate user confirmation gate. Stacked bases are OK; retarget
   `main` when parents land. Assign yourself; house PR body; **zero requested
   reviewers** unless the operator named them this turn. Do **not** `gh pr comment`
   while work remains (smoke, CI, MCP, audit). A comment is only for a
   finished unit — short bullets, never a timeline essay or "still need X"
   (#9373, #9562). Remaining-work status stays in Agent chat.
5. **6a live QA** — click the plan (`references/live-qa.md`). Intensity
   scales both-sides vs one control. Never post **Not covered**. P0/P1 ⇒
   Path 5, not 6b.
6. **6b smoke** (`skills.smoke` + upload) when intensity requires it
   (lite aria/docs: skip; else one clip; full: both sides). Hold the result;
   login off-camera; replace the old player. Skip only when the PR documents
   “N/A — no user-visible UI change” **or** intensity says skip:
   - MP4, **before vs after** (real checkout of base/`main` + branch — never
     fake), real product-line usage, slow, synthetic cursor.
   - **Titles + subtitles burned into the video** (not just the PR table):
     every major step gets a readable on-screen title card / subtitle
     (surface, action, expected result). A silent click-through without
     titles does **not** count.
   - **Cloned-voice audio (additive):** after the H.264 encode, run
     `tv-smoke-voice encode --video --script --out`. On-screen titles stay.
     Missing profile or TTS error → silent titled MP4 (`SILENT_FALLBACK`).
     Never stock-TTS labeled as Rishi. Script table needs a `Narration`
     column; Playwright holds come from `tv-smoke-voice pace`.
   - Embed the inline `user-attachments` player in the **PR description**
     (and in review replies that cite the clip). Prose Visual before-after
     alone is incomplete — the player must be present.
   - Fill the house **Visual before-after** table **and** link/embed the
     recording under it so reviewers see both.
   - Treat recording as a review; fix UX defects and re-record.
   - Never commit smoke scripts or MP4s.
   - **Session / upload (2026-08-11):** mint `user-attachments` via
     `pr-asset-upload` using a github.com web session captured with **Cursor
     Browser** (`cursor-ide-browser`) — never Brave / system-browser Keychain
     decrypt. If that MCP is not in the session catalog, stop and ask the operator
     to enable Browser rather than improvising another browser.
7. **Shepherd** (Brandon/Nick): drive CI + bot comments to green. **Never
   assign/request reviewers** unless the operator names them this turn. Route
   `cd-failure-analysis` / `pr-merge-watcher` — do not improvise
   TurboDispatch. **Merge only when explicitly asked.** Bot triage by
   evidence, then STAMP.
   On ship/abandon close the work unit:
   ```bash
   python3 ~/.cursor/skills/superdev/state/scripts/work_history.py --close \
     --unit issue-<N> --status shipped|abandoned --summary "<why>"
   python3 ~/.cursor/skills/superdev/state/scripts/resource_status.py
   ```
   If the local stack/worktree is done, route `/teardown-worktree` (or
   `instance:idle-stop` to keep). If a `/coder-box` was used, teardown the
   box — EC2 leak otherwise.

**Path 6 exit checklist** (scaled by `prove_intensity.py`):

- [ ] Intensity declared from the diff (not the title)
- [ ] Path 5.5 Ship on current head (or lite skip said out loud)
- [ ] `mergeable: MERGEABLE` (conflicts resolved)
- [ ] 6a: every planned case clicked; no **Not covered**
- [ ] 6b: smoke + player + Visual table **unless** intensity says skip
- [ ] Objective gates green

Smoke subtitle script (drive the recording from this — burn titles on screen):

```markdown
| Step | On-screen title   | Subtitle               | Narration                         | Kind   | Action         | Expected result  |
| ---- | ----------------- | ---------------------- | --------------------------------- | ------ | -------------- | ---------------- |
| 1    | Before: <surface> | Current behavior shown | Before the change, <what we see>. | action | Navigate/click | Baseline visible |
| 2    | After: <surface>  | New behavior shown     | After the change, <what we see>.  | action | Navigate/click | Fix visible      |
| 3    | NAV               | Next surface           |                                   | nav    | Navigate       |                  |
| 4    | Edge state        | Empty/error/auth state | Unauthorized / empty as shown.    | action | Trigger edge   | No regression    |
```

### Path 7 — Review

Use when asked to review teammates or own PRs.

**Default voice = Biswajit low-noise (operator, 2026-08-12 — absolute):**
P0/P1 only. No brand headers, no round essays on own PRs, no lens inventory.
Process/meta stays in the Agent reply — never on the GitHub timeline.

1. Hard rule: **teammate PR ⇒ chat draft only** (no gh write).
2. **Own PR / review-follow-up:** Path 5.5 full-stack audit **first** on
   the latest head (most reviewers do this; SuperDev must too). Fix P0/P1,
   re-audit, then draft or post the human reply.
3. **Route the profiles, then load their lenses.** Run
   `profile_lens_router.py --base <base>` (or `--paths`) to get every profile
   whose measured lane the diff touches, plus the forced `review-bar` families
   and the depth floor. `/pr-review-lens` is a **required** pass on every
   review — teammate PR or own. Load the cards for _judgment_ only; never dump
   lens names or author fingerprints into the draft (Path 7 voice rule).
4. Run merged checklist (data-model, boundaries, proof/races, security,
   RxJS/product, simplicity, decomposition, UI, CI) — for teammate chat
   drafts, `tv-fullstack` posture is the spine of that checklist. Load
   `references/review-bar.md` (F1–F10) as the defect taxonomy, and
   `references/security-bar.md` when the diff touches auth, outbound URLs,
   uploads, webhooks, HTML rendering, tokens, or PII.
   4b. **State how you verified.** Name the ref/merge-base you reviewed, cite
   `file:line` from source rather than inferring from the diff, and reproduce
   mechanisms instead of asserting them. Dispose "pre-existing" findings with
   out-of-diff `file:line` proof, never with scope framing. If a claim of
   yours turns out wrong, retract it in public with the reasoning that failed.
5. If AC is wrong or missing, use Path 3 Grill and Nick-style reasoned
   pushback instead of silently reviewing against bad requirements.

```markdown
**CHANGES_REQUESTED** | **Approve, blocking on <one thing>** | **LGTM**

### P0

- `file:line` — defect + why + fix shape

### P1

- `file:line` — defect + why + fix shape
```

**Verdict model** (measured rates + citations: `references/review-bar.md`):

- **Conditional approve is first-class** and the house's real blocking channel:
  approve, name exactly one blocking condition, offer to re-approve. Prefer it
  over `CHANGES_REQUESTED` when one defect stands between the PR and merge.
- **Never read severity off review state** — the corpus's hardest reviews ship
  as `COMMENTED` with a `## Critical` header. Grade the body, not the badge.
- **Bots discover; the human owns severity.** Forwarding a bot finding is fine
  if you triage it; rejecting one means fixing its cause, with a SHA.

Omit empty sections. Skip P2/nit/optional unless the operator asks for noise.
If the only human gate is visual proof, one line is enough.

**Post once (Rishi corrective, #9268 thrice — 2026-08-12):** On explicit
“post review”, submit **one** GitHub review, then verify
`$github.login` has exactly one new review id for that body. Do **not**
retry because `gh pr review` looked silent — it often exits 0 after
succeeding. Never fire `gh api .../reviews` as a “backup” of a prior
post. Submitted reviews cannot be deleted.

5. If own PR and user asks to post: use house reply format with SHAs
   (only after Path 5.5 is green on that head).
6. STAMP durable review patterns back to profiles/lens when new.
