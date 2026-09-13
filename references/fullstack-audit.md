# Path 5.5 — bundled fullstack audit (L1)

Integral SuperDev L1. Load a team `skills.audit` leaf (e.g. `tv-fullstack`)
when `operator.yaml` sets one — it routes FE/BE leaves. This file is the
**seam + stop condition** SuperDev always runs, even when that leaf is empty.

Split the diff, then audit only what it touches plus the contract between
halves:

```bash
git diff origin/main...HEAD --name-only
```

- Frontend: `apps/*/ui`, `libs/ui`, `*.component.*`, `*.routes.*`
- Backend: `apps/*/backend`, `libs/` except UI, `*.graphql`, `migrations/`
- Single-sided ⇒ skip the other half and skip seam checks that do not apply

## Seam (the bugs that pass both halves)

- **Contract** — every UI field/arg/enum exists in the regenerated schema. Drift = P0.
- **Auth continuity** — UI hide ≠ authorization. Matching guard / ownership on the mutation = required. UI-only gate = P0.
- **Client-only abuse** — disabled button / UI cooldown is not a server cap. None at all = P0; weak throttle = P1.
- **Public/pre-auth** — public flow uses the public client + allowlist.
- **Error propagation** — typed backend error surfaces in the UI, not a silent toast.
- **E2E flow** — one button → resolver → DB → render, plus one failure path.

## Stop condition

Stop when **all** are true on the **same SHA**:

1. Verdict **Ship** with zero P0/P1
2. Stability pass `ran` (or `n/a` — docs / display-only)
3. Better-solution pass `ran` (or `n/a`)
4. A second pass on that SHA also Ships

Also stop on identical actionable-findings hash, or 5 rounds. Do not re-run for P2s.

**Stability** is mandatory when the diff has locks, multiple writers of one
invariant, or FE eligibility from a page of data. List sibling writers; same
lock order; re-validate after lock.

Intensity (`prove_intensity.py`) cuts L1 only:

- **lite** — one pass; skip if docs-only
- **standard** — ×2 Ship
- **full** — ×2 Ship + stability (never skip stability on a full trigger)

## Report (one merged)

Gates · half coverage · Stability · Better-solution · P0 / P1 / P2 · Verdict
(`Ship` / `Ship after P0–P1` / `Not ready`). Tag `[FE]` `[BE]` `[SEAM]`.
