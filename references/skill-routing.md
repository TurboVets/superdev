# Skill routing — when to load what

Rated 2026-08-12 from prompt-history (200) + learn-ledger +
`platform-dev-profiles` isolation cards. Recompute:

```bash
python3 ~/.cursor/skills/superdev/state/scripts/rate_skills.py --write
python3 ~/.cursor/skills/superdev/state/scripts/recommend_skills.py --query "<task>"
```

**Rule:** load the **hub** for the family. Leaves load only when that hub
routes them. Do not stack sibling review / audit / memory skills.

## Rubric

| Dimension    | Pts | What it measures                                       |
| ------------ | --- | ------------------------------------------------------ |
| Delivery     | 30  | learn-ledger `skill_update` hits + successful mentions |
| Unchallenged | 25  | inverse of corrective/frustrated mentions              |
| Profile      | 20  | maps to a measured engineer lens                       |
| Uniqueness   | 15  | owns a SuperDev path step or a coverage.md axis        |
| Accuracy     | 10  | SuperDev already knows when to load it                 |

- **Promote** — proven delivery **and** challenge rate < 25%. Default-on at the path that owns it.
- **Tighten** — unique owner, but Rishi has challenged delivery. Still run it; obey the miss in `lessons.md`.
- **Keep leaf** — real skill; only when its hub routes here.
- **Demote** — overlap or unused. Load only if the user names it.
- **Never** — conflicts with SuperDev (teammate PR writes, unattended autopilot).

## Path → skill (one owner)

| Path / gate           | Load these                                                                                                                                            | Do **not** also load                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| 0 boot                | `superdev` + `operator.yaml`                                                                                                                          | a second memory skill; SuperDev-boot SKILL                                                  |
| 1 pick                | `focus.md` + GH issues                                                                                                                                | `sprint-priorities` unless board≠git                                                        |
| 2 issue               | house template; `user-story-writing` for Gherkin AC                                                                                                   | a second issue-writer                                                                       |
| 3 grill               | `grill-and-scales.md` + product rulings                                                                                                               | `turbovets-leadership` unless strategy ask                                                  |
| 5 K2 recon            | `platform-codebase-evolution` (`precedent_lookup`)                                                                                                    | ad-hoc PR archaeology                                                                       |
| 5 K3 write            | `references/ponytail.md` (**always on**; name the rung)                                                                                               | a second "be simple" skill; `/ponytail off` illegal; never `ultra` on auth/money/migrations |
| 5 K1 / stack down     | `start-app`                                                                                                                                           | assuming nginx is up                                                                        |
| 5 entity change       | `gen-migrations`                                                                                                                                      | hand-written TypeORM                                                                        |
| 5 BDD in-PR           | `acceptance-test`                                                                                                                                     | `e2e` as a second hub                                                                       |
| 5 Angular             | `tv-frontend` (it routes `styling` / `tds` / `tv-ux-review` copy density / angular-\*)                                                                | `angular-*` or `tv-frontend-audit` directly                                                 |
| 5 FE cleanup campaign | **`tv-frontend-cleanup`** (one dir → `tds-superset` Mode C). Rank dirs first; never the whole app in one run. Copy slop is a UX P1 on the same sweep. | `tv-frontend-audit` (judge, not fix); sweeping `apps/<pl>/ui` as one PR                     |
| 5 NestJS              | `tv-backend` (it routes `tv-backend-*`)                                                                                                               | `tv-backend-audit` / `nestjs-review` as L1                                                  |
| 5 TDS                 | `tds` hub                                                                                                                                             | `tds-component*` unless creating/migrating                                                  |
| **5.5 L1**            | **bundled `fullstack-audit.md`** (+ team `skills.audit` if set), scaled by `prove_intensity.py`                                                       | extra `tv-*-audit` skills; tagging `/tv-fullstack` when SuperDev is attached                |
| **L2 human**          | **`pr-review-lens` + cards the router names**                                                                                                         | `platform-a-human-pass`, `human-review`, `no-ai-slop`                                       |
| **L2 lean**           | **`references/ponytail.md`** (F11 delete-list)                                                                                                        | a second "simplify" skill; never cut F1–F10 to look lean                                    |
| **L2 coverage**       | **`review_coverage.py`** plan → record → assert                                                                                                       | `turbo-eyes:review-code` (dropped); any third parallel review skill                         |
| **6 intensity**       | **`prove_intensity.py`** — lite / standard / full from the diff                                                                                       | trusting the PR title; asking the operator how deep                                         |
| **6a live QA**        | **bundled `live-qa.md`** (+ team `skills.qa` if set)                                                                                                  | posting **Not covered**; filming over open P0/P1                                            |
| **6b smoke**          | `skills.smoke` then upload — after 6a, scaled by intensity                                                                                            | recording before L1 on this SHA; login in clip; cut on the dialog; stacked players          |
| **6 stamp**           | **`reconcile_push_intention.py --write-learn`** then `--source push`                                                                                  | calling Path 6 done on chat tags alone; waiting for the operator to notice a miss           |
| 6 CI red              | `ci-failure-analysis` / `cd-failure-analysis`                                                                                                         | improvising from logs                                                                       |
| 6 merge babysit       | `pr-merge-watcher` after explicit merge ask                                                                                                           | `merge-pr` without the ask                                                                  |
| 7 teammate review     | SuperDev Path 7 draft (chat)                                                                                                                          | `turbo-eyes:pr-review`, GitHub writes                                                       |
| orphan instances      | `teardown-worktree` (local) / `coder-box` (remote)                                                                                                    | `instance:teardown` on a live INSTANCE_ID                                                   |

## Profile endorsement (why these hubs)

| Skill                                | Engineer lens (measured)                             |
| ------------------------------------ | ---------------------------------------------------- |
| `tv-fullstack`                       | Chris — local audit before bots                      |
| `pr-review-lens`                     | Chris house gate + all 21 lanes via the router       |
| `review-code`                        | Tejas — turbo-eyes; crowded axes                     |
| `tv-backend-security`                | Tan S-1…S-11 (via `tv-backend` / security-bar)       |
| `tds` / `tv-frontend`                | Alex TDS + visual proof                              |
| `tv-frontend-cleanup`                | Alex campaign arm — one dir, then `tds-superset`     |
| `tv-ux-review` (copy density)        | Default-to-less-text; deletion test (#10954)         |
| `tv-smoke-test`                      | Alex visual proof — **tighten** (live UI, not decks) |
| `acceptance-test`                    | Justin acceptance suites                             |
| `tv-backend-data` / `gen-migrations` | Nick prove-don't-assert, Brandon gates               |
| `ci` / `cd-failure-analysis`         | Sean CI signal, Mike runner economics, Tejas deploys |
| `platform-codebase-evolution`        | Nick evidence provenance                             |

## Challenged skills (keep, but obey the miss)

| Skill               | What failed                                                   | Correct use                                            |
| ------------------- | ------------------------------------------------------------- | ------------------------------------------------------ |
| `tv-smoke-test`     | title-card decks, GAP labels, wrong subject, smoke-before-fix | Live scenario demos after the product is fixed         |
| `pr-asset-upload`   | cookie/MCP chase, second ask for github.com login             | Cursor Browser session; in-page upload if cookie stale |
| `tv-fullstack`      | forever-loop, treating Ship as exhaustion                     | ×2 same SHA + no-progress hash; then stop              |
| `teardown-worktree` | `instance:teardown` stole a live INSTANCE_ID                  | Neutralize `.env.instance` first                       |
| `start-app`         | SuperDev assumed the stack was up                             | K1 setup-green from logs                               |

## Do not invoke from Cursor SuperDev

**Never invoke** `bug-net` / `autopilot` / `discover` / `fix` / `ship`
(unattended Coder) — do not route, resume, or steal from their workers.
Also skip `turbo-eyes:pr-review` on teammate PRs, `merge-pr` without "merge it",
`vets-staging-deploy` unless asked, Cursor marketplace fluff
(`frontend-design`, `skill-creator`, …). Ponytail is not a Cursor plugin —
do not marketplace-install it; SuperDev already owns the adapter.
