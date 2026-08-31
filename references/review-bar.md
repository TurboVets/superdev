# SuperDev review bar — the merged house bar (load on Path 5.5 / Path 7)

Mined 2026-08-12 from the offline all-PR corpus (`platform-codebase-evolution/
data/`) across the six highest-volume engineers: Justin Lambert, Nick Gray,
Tan Kucukoglu, Chris Carsey, Brandon Nance, Ryan Doan — 1,950 authored PRs,
**6,973 reviews**, and **11,097 bodies** (7,187 inline
comments + 2,500 issue comments + 1,410 non-empty review bodies) — counted, not
estimated.

**Organized by failure family, not by person.** A diff is scanned against
families; attribution is kept only as provenance. This also honors Chris's
#8648 ruling that a rule lives in exactly one leaf and supersets only point.

**How a rule earns a line here:** it was enforced or accepted in the house on
a real PR, and the citation was verified against the corpus body text —
**91/91 quotes machine-verified** (PR number + author + phrase) before this
file shipped. Some rules were first surfaced by
a bot and then triaged by a human — that still counts. What does **not** count
is a habit asserted without a frequency: if you cite a format as someone's
standard, count its occurrences first.

---

## Contents

- [F1 — AuthZ enforcement](#f1--authz-enforcement-usually-p0)
- [F2 — Transactions and concurrency](#f2--transactions-and-concurrency-usually-p0)
- [F3 — Silent divergence and the sibling sweep](#f3--silent-divergence-and-the-sibling-sweep-the-houses-dominant-family)
- [F4 — Vacuous tests and proof](#f4--vacuous-tests-and-proof)
- [F5 — Contract change and reachability](#f5--contract-change-and-reachability)
- [F6 — Truthfulness of what the user sees](#f6--truthfulness-of-what-the-user-sees)
- [F7 — Data, queries and migrations](#f7--data-queries-and-migrations)
- [F8 — Evidence provenance](#f8--evidence-provenance-how-to-state-a-claim)
- [F9 — Reviewability and ship mechanics](#f9--reviewability-and-ship-mechanics)
- [F10 — AI runtime: a model that can act](#f10--ai-runtime-a-model-that-can-act-usually-p0)
- [F11 — Over-engineering](#f11--over-engineering-ponytail-review)
- [Quick line scan](#quick-line-scan-run-over-every-diff-after-the-four-family-scans)
- [Verdict model](#verdict-model-applies-to-every-review-superdev-writes-or-reads)

## F1 — AuthZ enforcement (usually P0)

- **A guard decorator is not enforcement.** Trace the guard's first statement
  for _this_ operation type before calling authZ satisfied: a `@Mutation`
  "returns `true` before ever calling `canAccessSubmission`… Presence ≠
  enforcement" (Nick #8394).
- **Never accept a bot's checkmark as proof.** "The autoreviewer marked this
  'P0 #2 — ownership guard still intact ✅' on the basis that the decorator is
  present" (Nick #8394).
- **Any user id in a mutation arg is a hole until proven otherwise.** "so I can
  hit the Twilio endpoint (which is public anyway) with any user id and disable
  their notifications" (Tan #5946).
- **Prefer the ownership-aware repository call** — "Why not
  `findWithOwnership`?" (Tan #7119).
- **Re-prove authorization when a query moves.** A replacement mutation lost
  the `FeatureGuard` its predecessor sat behind: "this mutation has no
  entitlement check at all… was dropping that deliberate?" (Brandon #8761).
  Subscriptions count: any actor could subscribe to another veteran's cues.
- **Permission-shaped Angular inputs default `false`.** "The new permission
  inputs default fail-open (`input<boolean>(true)`)… A future caller that
  forgets to bind the input renders edit controls to a view-only role"
  (Ryan #7304).

## F2 — Transactions and concurrency (usually P0)

These are additive to the standing rule (`SET LOCAL lock_timeout='3s'` +
`statement_timeout`, hoist pooled reads, never need a second pool connection
while holding a lock).

- **No awaited external HTTP inside a row-locking transaction.** "The VA call
  is awaited inside the transaction, while we hold FOR UPDATE… a connection
  pinned idle-in-transaction with a lock held for up to three minutes per
  submit" (Brandon #8602). Do the remote call outside the lock and reconcile.
- **Count-then-insert ceilings must share one transaction and connection.**
  "The count and the insert ran on two different connections, so two submits
  carrying the same handle could each read the same stale total and both
  commit" (Brandon #8721).
- **Advisory lock any delete-and-rewrite of shared draft rows** with the same
  key publish and discard take — `pg_advisory_xact_lock(hashtext(...))` —
  "otherwise an import racing a publish can pull the draft rows out from under
  it" (Brandon #4581).
- **Failure-path status writes must not live inside the transaction that
  throws.** "The throw aborts the transaction and discards the write… Specs
  can't catch this — they stub `manager.transaction` as a pass-through with no
  rollback semantics" (Nick #8394). Commit the failure status outside, and
  classify from the persisted status rather than the half-mutated entity.
- **`findOne` + `pessimistic_write` on an entity with eager relations** breaks
  at runtime: Postgres rejects `FOR UPDATE cannot be applied to the nullable
side of an outer join` (Tan #8713).

### F2a — Lease / mutex tooling invariants (#9159)

Scan these on any worktree-lease, mutex, or multi-process claim diff:
mkdir-then-write mutex publish (use atomic staging + rename) · over-broad
safety drops keyed on `isResumingLease` that also fire on teardown ownership
renew · token-less PGID clear or signal · claim released before survivor
verify · "alive PID ⇒ same owner" without start-identity · treating UNKNOWN
identity the same for mutexes (must park, I1) and cleanup claims (must
age-expire, I3) · happy-path-only tests for a race finding — every invariant
fix needs a multi-process interleaving test.

## F3 — Silent divergence and the sibling sweep (the house's dominant family)

After any fix, enumerate the siblings and call sites of what you changed and
**state the counts in the PR body**. Every finding below is the same defect
wearing different clothes.

**Census method:** enumerate with a **counted** grep (`rg -c`, or `| wc -l`) and
read every hit. A `| head -N` on a "prove zero callers" sweep fabricates the
answer you were hoping for — that is exactly how a base-class member deletion
shipped a TS4113 build break (#9373). A file whose count is 1 usually means the
symbol is _declared and unused_ there too: sweep that level rather than restoring
what you just removed.

- **A guard added to one branch must be added to every sibling branch.** The
  `fields` branch got `!isDisplayOnlyFieldType(field.type)`; "the `repeater`
  branch below was not given the same guard" (Ryan #5007). Same shape where a
  third query missed `generalCaseUuid: IsNull()` "so the three now disagree
  about the same rows" (Ryan #8655).
- **Two code paths computing one verdict will drift.** Three authZ adapters
  diverged: one ANDs `dataPermissions` onto the whole EXISTS, the others
  attach it to only two branches (Ryan #7210). Distinct from "local
  redefinition of shared utils" — this is duplicated _judgment_, not
  duplicated code.
- **Residual sweep: a hardening fix must name what it did not cover.**
  `buildAuthorizationWhere` scoped Client and Agent while Admin "fell through
  with no ownership filter, so `allPOAs` returned every POA row" — a residual
  of the previous fix (Tan #9079, following #8896). Same pattern for
  "remaining connector SSRF surfaces left uncovered" (Tan #9187 after #8897).
- **Sentinel, discriminator, pipe, or shared-constant change ⇒ consumer
  census.** "The marker moved from one obviously-illegal value that a reviewer
  would notice, to a well-formed payload that looks like real data to every
  consumer that wasn't updated. Five were updated. There are roughly
  thirty-five" (Nick #8446). A shared pipe change "regresses consumers the PR
  doesn't modify" (Nick #6108).
- **A column on a shared-lib entity needs a migration for every product
  line.** `OrgMember` lives in `libs/auth` but the migration existed only
  under `apps/vets`, so "recruit and active-duty will boot with an entity
  expecting `previousOrgRoleId` on a table that doesn't have it"
  (Brandon #9207). Keep this as a scan item — CI enforces migration drift, and
  Chris refused a ceremony gate for it (#8648).
- **Two sources of truth for one config drift silently.** A seed task declared
  `cron` and `cooldownMs` in both the decorator and `vets.yaml`, "and YAML
  wins… the decorator values are a copy that will silently go stale"
  (Brandon #8921).

## F4 — Vacuous tests and proof

The probe, in Ryan's formulation: **what deletion of production code would
make this test fail?** If nothing, it is not coverage.

- **Expectation computed by the code under test** — "Expected value is computed
  with the same helper + zero-arg `Intl` idiom `todayIso()` uses, so this can't
  fail" (Ryan #8827).
- **Assertion that does not prove its own name** — "The sync calls delete once
  on every run regardless of dedup, so this assertion still passes even if
  nothing got deduped… can we assert the prune set excludes their ids?"
  (Justin #8903).
- **Every positive scenario ships its negative twin** — "the positive alone
  passes just as well against a scheduler that warns unconditionally"
  (Nick #8999).
- **Assert both the zero and the non-zero denominator** so "a sweep that
  wanted nothing at all cannot report zero for the wrong reason"
  (Nick #8999).
- **Harness fidelity — can the fake even express the state under test?** A
  fake that "fans a single per-veteran status out to every provider" means "a
  scenario written against it would pass for the wrong reason"
  (Brandon #8999).
- **A test that cannot fail at all** — a helper "leaves `createInstance`
  without a return value, so it's been passing through the catch block since
  it was written" (Brandon #9164).
- **`as unknown as X` in a spec disables the only check that matters** —
  "TypeScript never checks the mock against the real shape" (Ryan #7102).
- **Tier honesty.** A Gherkin scenario must assert an observable outcome, not
  a call graph; a client-side AC that the server already enforces cannot be
  proven in an API-only run; a gap the acceptance tier cannot close honestly
  gets filed rather than faked (Nick #8999, Ryan #8818).
- **Test economics.** Framework behavior gets a unit test: "This seems like a
  waste of an E2E test (which are expensive). A unit test should suffice. It is
  testing basic angular behavior (routing)" (Chris #8539). Acceptance covers
  AC-level observable behavior; the two rules are complementary, not in
  conflict.
- **Verify behind the flag before approving** — "enable the
  `VETS_DOCUMENT_UPLOAD_ANALYSIS` feature flag and make sure that uploading
  those files triggers the document analysis" (Chris #8405).

## F5 — Contract change and reachability

- **Flag deletion re-enables the branch the flag suppressed.** Removing it
  meant "a member with zero active assignments falls back to reading
  `OrgMember.role`… would silently regain that role's permissions the moment
  their group-role assignment is revoked — a fail-open on revocation"
  (Ryan #7210).
- **Removing a workflow step needs a version bump plus an in-flight-execution
  migration** — "version stays 1.0.0 and there's no migration for in-flight
  executions. Anyone currently parked on one of those steps ends up with a
  blank step body… and can't advance either" (Brandon #8756).
- **A state machine that gains A→B must gain B→A**, or escalation dies
  silently: a missing `SUBMITTED → NEEDS_ATTENTION` meant "no status change, no
  alert, no log line at all" (Nick #8394).
- **Schema-shape assumptions backed only by a seeder are deploy regressions**
  — "prod runs migrations, not seeders… Every unassigned applicant self-upload
  400s on deploy" (Ryan #7210).
- **`@Optional()` cross-module inject silently resolves to `undefined`.** A
  token "only provided by `VaAccreditationModule`, but `IdmeStrategy` is
  declared in `AuthenticationModule`, which doesn't import it… Nest quietly
  passes `undefined` instead of failing at boot" (Brandon #9206) — the feature
  boots green and is dead forever.
- **Limits applied at the wrong granularity.** `MAX_REPAIRS_PER_TICK` was
  enforced per status, so "a tick can repair up to 800 notifications… and logs
  nothing while work is silently dropped. The spec masks this"
  (Brandon #8750).
- **Retry and reschedule must read the run summary**, not fire blindly — "a
  single transient failure on the weekly tier costs seven days of staleness
  with nothing logged" (Brandon #8921).
- **Dead code left reachable-looking is a regression vector** — methods with
  "no production callers left after this PR. Knip stays green only because the
  specs" (Brandon #8761). Grep for callers before accepting new surface
  (Ryan #8827, #8655).

## F6 — Truthfulness of what the user sees

- **Success copy must be true in every mode.** Mock mode told a veteran their
  ITF "was submitted to the VA" where the honest pre-change message was that
  no submission was sent (Nick #8446). Untruthful copy is a correctness defect,
  not a wording nit.
- **No contradictory states at once** — "the veteran sees the green success
  toast and the yellow 'partially connected, please reconnect' banner
  simultaneously — which is the main case this PR targets" (Brandon #8971).
- **No stacked dialogs.** "the 'Switch to Claim for Increase?' dialog is on top
  of another dialog - an anti-pattern. Change it to pop up after the 'Change
  path' dialog closes" (Chris #8286); a side panel over a centered dialog is
  the same defect (Chris #8982).
- **Consent and disclosure copy renders from the same map the action uses**, so
  "the consent list can't drift from what the sync actually sends"
  (Brandon #6359).
- **A clean deny must not regress into a 500** — "A caller without a
  publicProfile used to fall through to the registry and get a clean deny
  here; now this throws a 500 instead" (Justin #9106).
- **Copy shipped behind a flag must agree across every surface**, including
  vector-embedding text used by search (Ryan #8240).
- **Copy density — default to less text** (#10954, `tv-ux-review`). Delete copy
  that restates the heading, label, button, or visible UI. No subtitles, helper
  text, tooltips, or intro paragraphs unless the user would make a mistake
  without them. No marketing filler (`seamlessly`, `effortlessly`, `powerful`,
  `robust`, `intuitive`, `unlock`, `elevate`, `streamline`, `comprehensive`,
  `designed to`). Deletion test: if removing the string would not confuse the
  user or cause a mistake, remove it. Preserve density when editing an existing
  screen. Owner skill: repo `tv-ux-review`; campaign arm: `tv-frontend-cleanup`.

## F7 — Data, queries and migrations

- **One migration per branch.** "Please merge the migrations - no need to add
  `creationProvenance` and then remove it immediately" (Chris #9055); "Please
  combine the migrations into 1" (Chris #8051).
- **Catalog and reference data belongs in the existing CSV datasets**, not a
  new JSON or TS constant file, because "eventually we want to be able to have
  ISA users upload these csvs into live environments" (Chris #8863, #8051).
- **Provenance is polymorphic, never a role enum** — `authorType: 'USER' |
'ORGANIZATION' | 'GROUP'` with per-type relations, because "we would want to
  know what the name of the org is who created it, not just that they are VSO"
  (Chris #9055).
- **`findOne` without `ORDER BY` binds an arbitrary row.** With an ACCEPTED and
  a DRAFT POA coexisting it "picks arbitrarily. Which can bind the wrong rep
  and reject a legitimate one" (Justin #9107). Prefer the ACCEPTED (live)
  record and fall back to draft only when none is accepted.
- **`?? []` / `?? ''` on an upstream body is a silent-success bug**, not a
  default — a 200 lacking the `titles` key "returns success with zero titles"
  (Nick #4594).
- **Dedupe by content hash, not filename** — "we check for duplicate files
  based on the file hash. Can we do that here? … preferable to file name
  (untitled.png, untitled.png)" (Chris #8363).
- **In-memory pagination is a defect** — `getRawMany()` then
  `slice(offset, offset + limit)`; "Prefer SQL `LIMIT`/`OFFSET`"
  (Chris #8484).
- **Create-and-link must be one transaction**, or a failed attach leaves an
  orphan record (Chris #8286).
- **Terminal-state writes need a conditional update plus an `affected` check**
  (Chris #8756); participant inserts need a unique constraint plus
  `ON CONFLICT DO NOTHING` to be idempotent (Chris #7903).
- **Server-side cooldown, not UI busy state** — "UI `busyUuid` is not an abuse
  control — add a server cooldown or `@Throttle`" (Chris #8051).
- **Reuse the shared utils and the shared logger** — prefer `capitalize` /
  `toTitleCase` from `@turbovets/shared/utils` over re-inlined casing
  (Chris #8484); raw Nest `Logger` "skips the shared PII-redacting logger"
  (Chris #8051).

## F8 — Evidence provenance (how to state a claim)

- **Name the ref you reviewed and how you verified.** "Reviewed locally at
  `origin/feat/7139-mock-completion`, merge-base `4e14df5a`. 49 files,
  +541/−290. Every claim below verified against source, not inferred from the
  diff" (Nick #8446). **Frequency, measured: 3 times across his 83 non-empty
  review bodies (`merge-base` in 5).** This is the house's best _formulation_
  of provenance, not anyone's standing habit — SuperDev adopts it as a standard
  precisely because nobody applies it consistently. Verify a frequency before
  calling anything an engineer's habit; the first draft of this line claimed
  12 of 444 and was wrong on both numbers.
- **Reproduce mechanisms instead of asserting them** — "Reproduced the
  mechanism rather than taking it on faith" with the runnable snippet inline
  (Nick #8915); "true by construction rather than by assertion" (Nick #9221).
- **Verify config semantics against installed source, with file:line.**
  `connectionTimeoutMillis` is also the pool-checkout timeout
  (`pg-pool/index.js:198-217`) and a `DEFAULT_POOL_MAX = 10` is a runtime
  no-op because pg-pool already defaults to 10 (Ryan #8353).
- **Enumerate the full env cascade before attributing a value to the shell.**
  Nx loads `.env.local`, `.local.env`, `.env`, plus project and per-target
  variants via `getEnvFileVariants`; parsing `.env` alone misreads a file value
  as shell-set (Brandon #8915).
- **A grep against a stale base is not evidence** — "my earlier grep was
  against this branch's base (`4e14df5a83`), which predated #8428. I've rebased
  onto current main" (Justin #7475).
- **Proof must vouch for the claim it is making.** "The whole flatten rests on
  the before/after catalog proving the two schemas are identical, but the
  catalog doesn't compare permissions, so the folded `REVOKE`s are the one
  thing it can't actually vouch for" (Justin #8799).
- **Dispose 'pre-existing' findings with file:line, not with scope framing** —
  "Confirmed as pre-existing behavior, not introduced by this PR
  (`condition-builder.component.ts:194, 226`)" (Justin #8319).
- **Retract your own review comment in public when it was wrong**, including
  why the reasoning failed (Nick #8971; Brandon #8674).

## F9 — Reviewability and ship mechanics

- **The diff must be reviewable.** A 1k+ file diff gets dismissed —
  "This PR has 1k+ file changes. This a base issue?" (Justin #7253); set the
  base branch so only new code shows — "Can you change the base branch in
  GitHub to clean up the diff so I can review the new code in isolation?"
  (Justin #2482); no stray files — "Does this script have anything to do with
  the VPC flow logs / resolver query logs change? Did you mean to check it in?"
  (Justin #1354).
- **The PR body becomes the squash commit message**, so body quality outlives
  review (Justin #4616).
- **Never commit throwaway harnesses** — "lots of smoke tests were committed
  that we don't need" (Chris #8051); recorder scripts "shouldn't be committed.
  maybe we need to gitignore this directory" (Chris #8732). Attach the
  recording, ignore the script.
- **New route ⇒ route metadata plus regenerated sitemap** (Chris #8416).
- **Strip AI attribution from PR bodies** — "removed 'Made with Cursor' from
  the PR description" (Chris #8599).
- **Bot re-review is an explicit ping after each fix**, not a passive wait
  (Chris #8328). Authors clear bots, tests and conflicts before a human spends
  review time — "please address codex, e2e tests, and conflicts before I
  review" (Chris #7788).
- **Deferral is legitimate when it is named.** Merge with follow-up tickets
  once P0–P2 are dispositioned (Chris #8982); state the tradeoff when you
  defer — "Not folding this into this PR. The two ways to fix it pull opposite
  directions" (Justin #8695).
- **Reply format:** `Fixed in <sha>. <what changed>. <why it is now correct>.
Covered by a test.` — the house convention, 344 uses in the corpus, 267 of
  them Nick's.

---

## F10 — AI runtime: a model that can act (usually P0)

Measured 2026-08-12 from the only two engineers who own this lane: Hector
Castellanos (`libs/vets/assistant` at a 93% touch share, plus `libs/ai`,
`libs/vets/agent-tools`, `apps/calls-service`) and Ana Tomboulian
(integrations/connectors + RAG).

- **A tool schema is documentation, not authorization.** Re-authorize every tool
  argument server-side; a hallucinated or prompt-injected argument must not reach
  a privileged read. Provider-validation failures must not be swallowed
  (Hector #4273).
- **Private runtime context ≠ model-visible projection.** Bound what the model
  can see as a distinct type rather than handing it the runtime context
  (Hector #7698).
- **Anything prompt-reachable is untrusted input** — a user-controlled filename
  carried an injection into the system prompt (Josh #5523).
- **Streaming failure semantics:** already-streamed output survives the error,
  and human turns stay distinguishable from tool-result messages (Hector #3826).
  Multi-pod recovery keys off **positive liveness**, never elapsed silence
  (Hector #5511).
- **RAG ingestion is a durability problem:** interruption, orphan cleanup,
  idempotency, overlapping chunks, and embedding invalidation when the model or
  a field's semantics version (Ana #2756, #8863). Destructive local-only
  operations must stay local-only (Ana #8511).
- **Telemetry redaction is audited separately from model safety.** A redacted
  prompt is not a safe prompt, and a safe prompt is not a redacted log
  (Hector #7297).
- **Flag reach:** a flag guarding AI behavior must actually reach boot processors
  **and** every sibling product line — verify, don't assume (Hector #8511).
- **Connector hygiene:** no unauthenticated health checks, no fabricated upstream
  identity, validate response shapes, bound pagination, preserve first-page
  totals (Ana #4592, #4597).

## F11 — Over-engineering (ponytail-review)

Least-code bar adopted from [ponytail](http://ponytail.dev). Full ladder,
intensity, and house overrides: `references/ponytail.md`. L2 axis
`over-engineering` (`superdev:ponytail-review`).

Scan the working diff for code that does not need to exist. One line per
finding: `file:L12-38: tag: what to cut. What replaces it.` Tags: `delete:`
`stdlib:` `native:` `yagni:` `shrink:`. End `net: -N lines possible.` or
`Lean already. Ship.`

**P0** only when the extra code is a new unused abstraction, a new dependency,
or a reinvented `@turbovets/shared/utils` / stdlib helper on a path that already
has the one-liner. **P1** for shrink-in-place. Never delete AuthZ, a sibling
sweep guard, a mutation-aware test, a trust-boundary validator, or
`SET LOCAL lock_timeout` to look lean — those are F1–F4, not F11.

This family is **not** in the 91-quote house corpus. It is an operator
standard (operator, 2026-08-21), complementary to F1–F10.

## Quick line scan (run over every diff, after the four family scans)

Cheap pattern-level checks that have each caught a real defect in this corpus:
nested or service-owned `subscribe` · logic inside `subscribe` · `findOne`
without `ORDER BY` · `[].every()` on an empty array · unstable `track` · N+1
authZ · missing teardown registration · labels used as ids · unscoped mutations ·
tests that pass for the wrong reason · silently swallowed FE/BE errors · a UI
cooldown with no server throttle · post-commit poison · local redefinition of a
shared util · data fetching in a constructor · plaintext secrets in Redis.

## Verdict model (applies to every review SuperDev writes or reads)

**Severity is never read off review state.** Changes-requested rates, measured:
Ryan 6/538 (1.1%), Nick 21/1356 (1.5%), Tan 26/1392 (1.9%), Justin 23/1167
(2.0%), Brandon 8/112 with 6 of those empty. Only Chris blocks by state
(222/2205). Nick's hardest reviews ship as `COMMENTED` with a `## Critical`
header; Ryan's substantive bot triage lives in author-side comments on his own
PRs, not in verdicts.

**Conditional approve is a first-class verdict** and the house's real blocking
channel: approve, name exactly one blocking condition, offer to re-approve.
"Approved but please address the nested subscription before merging"
(Justin #7036); "we should address the `any` cast before merging. ping me when
changes are in and ill approve it" (Ryan #7304); "Could we add
`start_period: 60s` … Happy to approve as soon as" (Brandon #9261).

**Bots discover; the human owns severity and disposition.** Chris routinely
forwards bot findings verbatim ("Grok found the following", #8756) and then
triages them ("Disagree that this is a ship-blocking P0 for the current UX",
#8312). When you reject a bot finding, fix the artifact that produced it and
say so with a SHA (Ryan #8818).
