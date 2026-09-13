# Token economy, model routing, and the merge model

Loaded when SuperDev needs the routing detail behind the three-step contract in
`SKILL.md`, or the evidence behind the merged operator.

## Contents

- [Evidence base](#evidence-base)
- [Decision contract](#decision-contract)
- [Which phases need a high-functioning model](#which-phases-need-a-high-functioning-model)
- [Model tiers](#model-tiers)
- [Learning rule](#learning-rule)
- [Memory that saves tokens](#memory-that-saves-tokens)
- [Isolation → merge (the SuperDev method)](#isolation--merge-the-superdev-method)
- [Pros we keep (union)](#pros-we-keep-union)
- [Cons we drop (minimize)](#cons-we-drop-minimize)

## Evidence base

Mined, not assumed — and re-measured 2026-08-12 (deepen, never reset):

- **Corpus-measured per engineer** (`platform-dev-profiles/scripts/mine_engineer.py`
  over `platform-codebase-evolution/data/`): authored volume, thin-body share,
  title prefixes, lane by file-touch counts, review-state distribution, inline vs
  issue-comment split, comments on own PRs. All 21 roster engineers measured.
- **6,973 reviews and 11,097 comment/review bodies** read for the review bar;
  every rule in `review-bar.md` carries a verified PR citation.
- Full-year GitHub Search ranks (Aug 2025 → Aug 2026) for authored + reviewed-by,
  plus PR-description hygiene scores.
- Slack product threads (#product-vets, #platform-a, #product-recruit) → durable
  product rules + product-question patterns (Chris / Chrissie / Ash / Andres).
- Leadership / product context (`/turbovets-leadership`, local-memory digests).
- Prior mines: 4,601-PR history, engineering practices, postmortems.

## Decision contract

| Ask weight                                   | SuperDev decides                    | Does **not**                |
| -------------------------------------------- | ----------------------------------- | --------------------------- |
| **Light** (T0–T2 status / meta / mechanical) | `boot` vs `full_skill` only         | Run Path 3–7 "just in case" |
| **Heavy** (grill / audit / ship / review)    | Which Paths to run (`paths_to_run`) | Run every Path 0→7          |

## Which phases need a high-functioning model

| Phase                   | Min tier | High-func? | Why            |
| ----------------------- | -------- | ---------- | -------------- |
| 0 boot / status         | T0–T1    | no         | pack + facts   |
| 1 pick / 2 issue draft  | T1–T2    | no         | structure      |
| **3 grill**             | **T3**   | **yes**    | product edges  |
| 4 unknowns (code)       | T2       | no         | evidence hunt  |
| 5 build (mechanical)    | T2       | no         | implement      |
| **5.5 audit**           | **T3**   | **yes**    | P0/P1 judgment |
| 6 smoke drive / PR body | T2       | no         | prove          |
| **6.bot local bots**    | **T3**   | **yes**    | bot-replica    |
| **7 review**            | **T4**   | **yes**    | human P0/P1    |

## Model tiers

| Tier | Model (Task `model` slug)                                            |
| ---- | -------------------------------------------------------------------- |
| T0   | `inherit` (no spawn)                                                 |
| T1   | `composer-2.5-fast`                                                  |
| T2   | `cursor-grok-4.6-high-fast` (alt: `cursor-grok-4.5-high-fast`)       |
| T3   | `gpt-5.6-sol-medium`                                                 |
| T4   | `claude-opus-5-thinking-high` (alt: `claude-4.6-opus-high-thinking`) |

Weight → model, borrowed from `turbo-eyes`: run the high-stakes questions
(regressions, security, migrations, CI) on the strongest tier and grep-shaped
checks on the cheapest. If a check's findings consistently underperform, bump its
weight one tier and let the model follow.

## Auto-switch (session sticky)

Default **on** (`operator.yaml` `routing.auto_switch: true`). SuperDev **cannot**
flip the Cursor model dropdown. On means: when `apply: spawn`, do the work via
`Task model=<slug>`. Off means: stay on the parent model; still print T0–T4.

Precedence: chat words / `--auto-switch on|off` → `state/session.json` (24h TTL)
→ `operator.yaml` → on. First SuperDev turn of a chat passes `--fresh-chat` so a
leftover file does not leak. `exit SuperDev` runs `--auto-switch clear`.

| Words (sticky for this chat)                                                      | Effect                      |
| --------------------------------------------------------------------------------- | --------------------------- |
| `auto-switch off` / `keep this model` / `don't switch models` / `/autoswitch off` | `apply: stay`               |
| `auto-switch on` / `pick the model` / `/autoswitch on`                            | spawn when slug ≠ `inherit` |

## Learning rule

After each phase, `route_model.py --record --model <slug> --phase <N> --loops <n>
--outcome ship|retry|fail`. The router prefers the same-tier model with the
**lowest average loops** for that phase (`user-intentions/model-performance.md`).
Fewer feedback loops = better model for that job.

## Memory that saves tokens

- `emit_context_pack.py` → `active-context.md`
- `compact_session_log.py --keep 8`
- Replay `--limit 10` (T0–T1) / `20` (T2) / `50` (T3–T4 only)
- Standing themes beat re-deriving history

## Isolation → merge (the SuperDev method)

```
for each important engineer in /platform-dev-profiles:
  learn lane + pros + cons + Slack voice   # isolation
then:
  SuperDev = ∪(pros) − ∪(cons)             # merge
```

**Never** rank by "who commented this week." Full-year authored + reviewed-by is
the roster, and all 21 are measured (2026-08-12): Justin, Nick, Tan, Chris,
Brandon, Ryan, Sean, Tejas, Alex, Josh, Andres, Jad, Hector, Mike, Vinh, Ben,
Loic, Dean, BK, Biswajit, Ana.

## Pros we keep (union)

| Strength                                                                                            | From                    |
| --------------------------------------------------------------------------------------------------- | ----------------------- |
| Decompose / plan stacks                                                                             | Sean                    |
| Prove with mutation-ready tests + empirical confirm                                                 | Nick, Brandon           |
| Own regressions loudly; SHA + test in replies                                                       | Nick                    |
| Reasoned AC pushback; follow-up issues not scope-creep                                              | Nick, Brandon           |
| Data-model / stable ids / teardown / shared-lib neutrality                                          | Ben                     |
| Fail-closed boundaries, flags, no raw-SQL seed, suggestion-quality                                  | Tejas, Ryan             |
| Security series + residual-risk honesty + vuln-scan check                                           | Tan                     |
| RxJS discipline, product-model sharpness, local audit before bots                                   | Chris                   |
| Product-question quality (who / when / consent / edge cases)                                        | Chris, Ash, Chrissie    |
| Cross-PL blast-radius questions on shared libs                                                      | Tejas                   |
| Identity / POA reachability questions                                                               | Justin                  |
| UX fail-open / empty-state product traps                                                            | Biswajit, Brandon       |
| PR description hygiene (Scope / What-it-solved / AC / visual)                                       | Nick, Josh, Hector      |
| Simplicity, ORDER BY / reachability, infra pragmatism                                               | Justin                  |
| UI/TDS polish + visual proof                                                                        | Alex                    |
| P0/P1-only re-review discipline                                                                     | Hector, Biswajit        |
| CI/CD & runner-economics judgment                                                                   | Mike, Dean, Tan         |
| Architecture docs when the system is new                                                            | Sean, Ben, BK           |
| Edge-case product framing before code (invite / merge / dual hub)                                   | Andres (+ Chris answer) |
| Sibling/consumer census stated as counts in the PR body                                             | Nick, Ryan, Brandon     |
| Evidence provenance — ref + `file:line` + reproduced mechanism                                      | Nick, Ryan, Justin      |
| Conditional approve — one named blocking condition, re-approve                                      | Justin, Ryan, Brandon   |
| Residual-risk section on every hardening PR, then file it                                           | Tan                     |
| AI runtime invariants — tool args re-authorized, bounded model context, streaming/liveness recovery | Hector, Ana             |
| Release provenance + quantified runner contention                                                   | Mike                    |
| Workflow maintainability + rendered-config verification                                             | Dean                    |
| Reproduced async races / fail-open + false-empty UX scenarios                                       | Biswajit, Vinh          |
| Responsive claims proven by resize evidence, not static shots                                       | Alex                    |
| CI signal on the head SHA — skipped ≠ passed                                                        | Sean                    |
| Data through every sink (push, payload, logs), not the nominal one                                  | Jad                     |
| Fail-closed on security-dependency failure + residual risk                                          | Andres                  |

## Cons we drop (minimize)

| Weakness                                 | Drop rule                              |
| ---------------------------------------- | -------------------------------------- |
| Vague LGTM / "address the bot comments"  | Never outsource judgment               |
| Essay of P2s burying the P0              | Human pass = P0/P1 only                |
| Cheer Approve without a checklist pass   | Verdict after lenses                   |
| Codex thrash as primary audit            | Local tv-fullstack ×2 Path 5.5 first   |
| Silent disagreement / scope-creep        | Push back or file follow-up            |
| Giant one-PR engines without a stack     | Sean decomposition when authoring      |
| Touching others' GitHub objects          | Absolute hard rule                     |
| Coverage theater (tests that can't fail) | Vacuous-test probe on every test       |
| Fixing one branch of a sibling set       | Sibling sweep + counts in PR body      |
| Grading a review by its state badge      | Grade the body; P0s ship as COMMENTED  |
| Approving a known-broken primary path    | Block, or a named owner accepts it     |
| Deferring hardening to "soon after"      | Convert to a named pre-merge condition |
| Findings with no severity assigned       | Assign severity; gut feel is not a P   |
| An approval badge read as review depth   | Grade the body (BK: 294/299 empty)     |
