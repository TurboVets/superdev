# Review coverage contract (L2)

Why this exists: with ~15 review surfaces installed, a prose report cannot
distinguish **"this axis was reviewed and is clean"** from **"nobody looked."**
Coverage is therefore an assertion, not a feeling — `scripts/review_coverage.py`
plans the axes a diff forces on, records who covered each one, and **fails L2**
if any planned axis is unaccounted.

## Contents

- [The four commands](#the-four-commands)
- [Ownership — one surface per axis](#ownership--one-surface-per-axis)
- [Gating: path AND content, in a file the axis owns](#gating-path-and-content-in-a-file-the-axis-owns)
- [Status vocabulary](#status-vocabulary)
- [Yield: surfaces must earn their slot](#yield-surfaces-must-earn-their-slot)
- [Adding or moving an axis](#adding-or-moving-an-axis)

## The four commands

````bash
S=~/.cursor/skills/superdev/scripts/review_coverage.py
python3 $S plan --base origin/main         # axes + owners for this head
# run turbo-eyes:review-code once, save its ```json review-feedback block:
python3 $S ingest --feedback /tmp/review-feedback.json
python3 $S record --axis product-law --status na --note "<why>"   # per SuperDev axis
python3 $S assert --pr <N>                 # exit 1 blocks L2
````

Then, whenever a GitHub human or bot raises something the local ladder should
have caught, attribute it and let the yield table judge the surface:

```bash
python3 $S miss --axis tenancy-authz --source github-bot --pr 9272 --note "<what>"
python3 $S yield
```

## Ownership — one surface per axis

Delegation decision (operator, 2026-08-12): on the crowded axes the machine sweep is
**`turbo-eyes:review-code`** — it is content-gated, model-tiered, carries an
`owns_to` map and a `suppressions[]` arbitration log, and reports
`subskill_status` per check. SuperDev stopped hand-rolling those and kept only the
axes nothing else covers.

| Axis                  | Owner                         | Why this owner                                                                         |
| --------------------- | ----------------------------- | -------------------------------------------------------------------------------------- |
| red-flags             | `turbo-eyes:q1`               | always-on sweep, opus                                                                  |
| regressions           | `turbo-eyes:q2`               | edits to existing files                                                                |
| tests                 | `turbo-eyes:q3`               | content-gated on assertions                                                            |
| ui-tds                | `turbo-eyes:q4`               | templates/styles                                                                       |
| standards             | `turbo-eyes:q5`               | repo coding standards + antipatterns                                                   |
| ci-signal             | `turbo-eyes:q6`               | head-SHA signal, PR mode                                                               |
| e2e-ci                | `turbo-eyes:q7`               | acceptance/E2E in CI                                                                   |
| performance           | `turbo-eyes:q8`               | perf + scaling with a horizon field                                                    |
| type-safety           | `turbo-eyes:q12`              | casts / `any` / `!` (content-gated)                                                    |
| migrations            | `turbo-eyes:q13`              | migration + deploy safety                                                              |
| tenancy-authz         | `turbo-eyes:q14`              | multi-tenant scoping + guards                                                          |
| workflow-infra        | `turbo-eyes:q15`              | workflows, Docker, Nx                                                                  |
| **profile-lenses**    | `superdev:pr-review-lens`     | the 21 measured human lanes — ours alone                                               |
| **sibling-sweep**     | `superdev:review-bar-F3`      | the house's #1 defect family                                                           |
| **concurrency-tx**    | `superdev:review-bar-F2`      | tx shape + lease invariants, no analogue                                               |
| **product-law**       | `superdev:standing-product`   | Vets share/consent/POA rulings                                                         |
| **ai-runtime**        | `superdev:review-bar-F10`     | tool-arg authorization; turbo-eyes has none                                            |
| **copy-truthfulness** | `superdev:review-bar-F6`      | success copy true in every mode + copy density (no filler / restated headings; #10954) |
| **security-bar**      | `superdev:security-bar`       | Tan's S-1…S-11 taxonomy                                                                |
| **verdict-channel**   | `superdev:review-bar-verdict` | conditional approve; grade body not badge                                              |
| **over-engineering**  | `superdev:ponytail-review`    | F11 delete-list; turbo-eyes has no analogue                                            |

Everyone else who _could_ speak to an axis is attribution only — the same rule as
turbo-eyes arbitration rule 15. That is what stops seven surfaces re-reading one
authZ guard while performance gets a third of the attention.

## Gating: path AND content, in a file the axis owns

An axis is planned only when a changed file **matches its path pattern** and — if
it has a content trigger — **that concern appears in that file's own added
lines**. The per-file scoping matters: an early version planned `concurrency-tx`
because `setInterval` appeared in a Markdown skill doc. A diff with no code files
at all (docs, skills, rules) plans only `profile-lenses` and `verdict-channel`.

Measured effect on real diffs: a 5-file docs change plans 2 of 20 axes; a
203-file, 25-commit range plans all 20 (correctly — it touches everything).

## Status vocabulary

| Status        | Meaning                                       | Legal verdicts        |
| ------------- | --------------------------------------------- | --------------------- |
| `ran`         | the owner actually executed                   | `clean` \| `findings` |
| `na`          | not applicable — **`--note` reason required** | none                  |
| `failed`      | the owner errored (turbo-eyes `failed`, etc.) | none — **blocks L2**  |
| `UNACCOUNTED` | planned, never recorded                       | none — **blocks L2**  |

`clean` is only reachable through `ran`. A failed subagent blocks the ladder
rather than quietly reading as clean — this is the specific hole the contract was
built to close.

## Yield: surfaces must earn their slot

`yield` joins the coverage rows with the gate-miss rows per axis:

- **LEAKING** — a GitHub human/bot caught something this axis owned. Tighten the
  lens or move the axis to a different owner.
- **earning its slot** — it finds real things.
- **no signal in N runs** — a candidate to fold into a neighbouring axis. This one
  needs judgment, not automation: a clean axis may be prevention rather than dead
  weight.

## Adding or moving an axis

Edit `AXES` in `scripts/review_coverage.py` — id, owner, path pattern, optional
content trigger, tier. Adding a _surface_ without claiming an axis is how we got
here in the first place: if a new review skill does not own an axis in that table,
it does not run in L2.
