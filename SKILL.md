---
name: superdev
description: >-
  Issue-to-ship operator for Cursor Agent. One GitHub issue → ready for
  human review before any PR (L1 audit ×2, L3 Codex + Cursor Claude, live
  QA, green smoke, E2E). N pasted issue/PR URLs = N parallel lanes (one
  worktree each). Parent finishes mid-lane stops (lane_truth / claim_lint
  / halt_lint). Token-economy boot T0–T4: Composer / Grok / GPT / Claude.
  Auto-switch Task-spawns — cannot flip the picker. L3 Claude is Cursor
  Task claude-opus-5-thinking-high (no claude CLI login). Sticky until
  exit SuperDev. Invoke for pick / build / review / reply / ship. Requires
  operator.yaml and gh CLI; Cursor Browser MCP for Path 6. Never writes
  teammate PRs.
disable-model-invocation: true
---

# SuperDev

Composition layer above a team's learned skills. It does **not** clone one
reviewer. It runs a **fixed lifecycle** (pick → grill → build → local audit
ladder → prove → PR → review) and loads the team's leaf skills from
`operator.yaml`.

Operator identity lives in `operator.yaml` (copy from `operator.example.yaml`).
Empty `github.login` ⇒ SuperDev will not touch GitHub objects.

## Token economy + model routing (mandatory)

**SuperDev decides** skill surface and model tier — not the user.
Auto-switch is **on by default** (`operator.yaml` `routing.auto_switch`).
It is a **Task spawn** on the routed slug. SuperDev **cannot** flip the Cursor
picker (the dropdown never moves). Off = stay on the parent; still print the
recommendation. Banner must show `apply` + `did`, not only `auto-switch: on`.

```bash
S=~/.cursor/skills/superdev
python3 $S/scripts/emit_context_pack.py --write
python3 $S/scripts/route_model.py --prompt "<ask>" --path "<stage>" --goal "<goals>" --pretty \
  --parent-model "<this chat's slug>"
# First SuperDev turn of this chat only: add --fresh-chat
# T1+: work history + contradictions + resources (warn before ACT)
python3 $S/scripts/work_history.py --active
python3 $S/scripts/check_contradictions.py
python3 $S/scripts/resource_status.py
# After a phase finishes:
python3 $S/scripts/route_model.py --record --model <slug> --phase <N> --loops <n> --outcome ship|retry|fail
```

Session switch (sticky until `exit SuperDev` or `--fresh-chat`):
`auto-switch off` / `keep this model` / `don't switch models` / `/autoswitch off`
`auto-switch on` / `pick the model` / `/autoswitch on`
or `route_model.py --auto-switch on|off`. Durable default: `routing.auto_switch`.

`apply: spawn` ⇒ **first tool is** `Task model=<slug>`. SuperDev + auto-switch
on **is** the user requesting that slug — do not pass `inherit`. Do not do this
turn's Path work on the parent. `apply: stay` ⇒ parent (`did`: `t0` /
`same_parent` / `off`). Same-as-parent is stay, not a fake spawn.
Declare once: `phase` · `skill_surface` · `paths_to_run` · **auto-switch: on|off** ·
**apply: stay|spawn** · **did** · `tier` · `model` · **ponytail: full|lite|ultra**.

Never route below T3 on: **3 grill · 5.5 audit · local bots · 7 review** (7 is T4).
Detail: `references/routing.md`. `--record` is not optional.

### Context upgrade (only if paths_to_run needs it)

| Need                     | Load                                                            |
| ------------------------ | --------------------------------------------------------------- |
| Exact path steps         | `references/lifecycle.md` (the path you are in)                 |
| Path 3 grill             | `operator.yaml` `skills.grill_scales` if set                    |
| Product law              | `operator.yaml` `skills.product_law` if set                     |
| Path 5.5                 | `references/fullstack-audit.md` (+ team `skills.audit` if set)  |
| Path 6 prove intensity   | `scripts/prove_intensity.py` + `references/prove-intensity.md`  |
| Path 6a live QA          | `references/live-qa.md` (+ team `skills.qa` if set)             |
| Path 5 least-code        | `references/ponytail.md`                                        |
| Path 5.5 / 7             | `references/review-bar.md` (F1–F11)                             |
| Auth/URL/upload/HTML/PII | `references/security-bar.md`                                    |
| L2 coverage              | `references/coverage.md` + `review_coverage.py`                 |
| Which leaf skill         | `references/skill-routing.md`                                   |
| Intention loop           | `references/intention.md`                                       |
| Agent / subagent state   | `references/agent-truth.md` + `lane_truth.py` + `claim_lint.py` |

If this SKILL is already attached, **do not Read it again**.

## The job

SuperDev's job is **one GitHub issue, start → ready for human review**.
That is the only `done`. Hallucination control is how we refuse a fake
done — it is not a substitute for finishing.

**Ready for human review** (`lane_truth.py` `done: true`) binds **this HEAD**:

| Gate       | Green means                                                               |
| ---------- | ------------------------------------------------------------------------- |
| **L1**     | bundled fullstack audit ×2, real gates, `VERDICT: SHIP`                   |
| **L3**     | Codex **and** Cursor Claude `VERDICT: APPROVE` (no VERDICT is unfinished) |
| **6a**     | live in-browser QA — every planned case clicked                           |
| **6b**     | smoke green + player in the PR body                                       |
| **E2E**    | e2e check `success` on this SHA                                           |
| **Checks** | CI on this SHA is green or evidenced infra                                |

"L1 spawned", "Codex CR, fixer running", or a subagent saying Ship is **not** ready.

### Parent owns the finish

The parent chat owns the issue until `done: true`. A subagent that
stops, 401s, boot-loops, or hallucinates a greener gate is a **blocked
step**, not a stop for the operator.

When that happens the parent:

1. `lane_truth.py` + `claim_lint.py` (exit 1 ⇒ discard the claim)
2. Open the artifact on **this HEAD** or treat the gate as unset
3. Diagnose the actual blocker
4. Resume or spawn the next concrete step — do not ask "should I continue?"
5. Never paste agent A's story into agent B

`unstick_subagents.py` + `halt_lint.py` detect quiet / boot-stuck /
"brief the user" mid-lane. A Cursor job-finished notice is **not** the
scheduler — `advance_lane.py --strict` is. Unread `/tmp/l1-*` / `/tmp/l3-*`
reports ⇒ open, `--ingest`, record or fix, spawn the next gate in the
same turn. `lane_truth.py --pretty` is read-only; only `--record` writes
`truth.json`. One sticky ticket runs Path 0→6; leftovers get
ingest/unstick only until `done: true`. N pasted links are still N lanes.
Path 7 is chat-draft only for teammates.

## Stage detection

Pick the earliest unfinished path. SuperDev + a GitHub link is a **finish this
object** order — from its current stage to its **end**. **N links in one
prompt = N parallel lanes** — one worktree per object, at the same time.
Do not pick the first and queue the rest. The end is **ready for human
review**: L1, L3 Codex **and** Cursor Claude, 6a, green 6b, E2E, and
checks on **this HEAD** in `lane_truth.py`. Not "code exists", "PR opened",
"L1 spawned", or a subagent saying done. Every open own PR is in that tab.
Leftover `next` is the job. If a run dies mid-lane, the parent unsticks it.
Do not ask "what should I do?" Do not stop at a status essay.

```bash
python3 ~/.cursor/skills/superdev/scripts/resolve_gh_intention.py --pretty "<url-or-number>"
```

Adopt returned `stage`, `goal`, `completion_means`. Continue until that list is
done. `hard_stop` is **only** teammate-owned (someone else assigned ⇒ chat
draft). Unassigned ≠ teammate-owned: SuperDev+link authorizes assign-to-self
and the ship lane (Path 5 → L1 → L3 → open PR → 6a → green 6b). Never skip
ahead (untestable AC blocks code). Never stop mid-lane.

When a diff exists, classify prove intensity **before** L1 / QA / smoke:

```bash
python3 ~/.cursor/skills/superdev/scripts/prove_intensity.py --base origin/main --pretty
```

Declare `prove_intensity` + `review_depth` + reasons. Title words ("quick
fix") are ignored. When torn the script returns **full**. Cuts: `references/prove-intensity.md`.

**Open the PR — do not ask twice** on an owned **product** ship lane after the
ladder is green. Merge / close / force-push / teammate writes still need an
explicit ask. Pause words (`hold`, `don't push`) override.

**This repo lands on `main`.** SuperDev skill changes: commit on `main` and
`git push origin main`. Do not open a PR unless asked. Standing: if the
operator's installed skill has changed significantly from this `main` (new
hard rules, scripts, or lifecycle behavior), push without a second ask. Port
to this repo's layout — do not dump machine-specific paths. Pause overrides.

## Path 5.5 — local audit gate (most PRs)

L1 is **integral** (`references/fullstack-audit.md`). Also load `skills.audit`
when `operator.yaml` sets a team leaf.

1. Run the audit on the branch/PR diff. Emit merged P0/P1 in chat.
2. Fix every P0/P1 in the same session. No QA / smoke / push / reply while findings remain.
3. Re-run after fixes (×2+ total, unless intensity is **lite**). Verdict **Ship**.
   Every fix gets a **sibling sweep**. Prefer two consecutive Ship on the **same SHA**.
4. Then L2 + L3 (L3 **skip** on lite — say it out loud). Only after the
   intensity-scaled ladder: commit / push / PR-create / 6a / 6b / STAMP.
5. Docs-only: `prove_intensity.py` already returns lite + skip L1. Say the skip.

GitHub bots **confirm** after local audit is green; they are not the discovery loop.

### Local review ladder — complete before any PR exists

| Rung   | Pass                                                            | Owner                    |
| ------ | --------------------------------------------------------------- | ------------------------ |
| **L1** | audit ×2+ Ship (lite: one pass / skip docs)                     | bundled + `skills.audit` |
| **L2** | review lenses for every lane the diff touches + coverage assert | `references/coverage.md` |
| **L3** | Codex CLI + Cursor Claude Task both `APPROVE` (lite: **skip**)  | scripts                  |

**L3 Claude is Cursor Task `claude-opus-5-thinking-high`.** `local-bot-review.sh`
writes the same CI prompt; the parent spawns that Task and requires a
`VERDICT:` line. This chat acting as Claude is not L3. `--claude-engine cli`
(`claude -p`) is leftover — do not ask for terminal `/login`. Codex still
needs `npx @openai/codex login` if that CLI is logged out.

**Review depth** comes from `prove_intensity.py`. Never D1 on a **full** trigger
(auth, money, migrations, two-party, shared lib). Aria-only copy may be D1.

| Depth  | When                                                                         | Runs                                  |
| ------ | ---------------------------------------------------------------------------- | ------------------------------------- |
| **D1** | lite: ≤3 files, aria/CSS/docs only, no full trigger                          | Lens 0–1                              |
| **D2** | standard                                                                     | Lens 0–8 + routed families            |
| **D3** | full trigger (auth · money · tx · migrations · shared lib · two-party · >20) | Full + security-bar + sibling re-pass |

## Path 0 boot

Always: `emit_context_pack.py --write` + `route_model.py`. T1+: work history,
contradictions, resources, `lane_truth.py`, `unstick_subagents.py` — **warn**
on HIGH/MEDIUM before acting. Intention loop: TAG → REPLAY → MATCH → ADAPT
→ DELIVER → STAMP → **RECONCILE**. ADAPT is unconditional. After a push,
chat tags lose to the commit + files + PR body; gaps are a `miss`.

## Lifecycle paths

Detail in `references/lifecycle.md`. Required artifact unlocks the next stage.

| Path    | Use when                  | Required artifact                                            |
| ------- | ------------------------- | ------------------------------------------------------------ |
| **1**   | no ticket / "what next"   | 2 issue URLs + why (`gh issue list --assignee $login`)       |
| **2**   | create/sharpen an issue   | House issue body (Scope/Problem/AC/Non-goals/Risks/Unknowns) |
| **3**   | AC unclear, product edges | Grill persisted as 2PRD + verdict                            |
| **4**   | unknowns block code       | Unknowns register cleared by evidence                        |
| **5**   | ready to code             | Battle Rhythm · ponytail · 1 ticket · 3-failure              |
| **5.5** | any diff/branch/PR        | intensity-scaled L1 **Ship**                                 |
| **6a**  | user-visible own PR       | live QA — every planned case clicked; never **Not covered**  |
| **6b**  | after 6a, no open P0/P1   | subtitled smoke + player + table (scaled by intensity)       |
| **7**   | review requested          | P0/P1-only **chat draft**; never write teammate GitHub       |

**Path 6 completeness.** Not done if DIRTY, L1/L3 unfinished, leftover QA
cases, a **red** smoke, or (when smoke is required) no inline player /
prose-only Visual before-after. Forgetting 6b after a green ladder is a
miss. Attaching SuperDev is enough — do not wait to be tagged
`/tv-fullstack` or a QA skill.

**GitHub voice.** P0/P1 + `file:line`. No review-round essays. No GitHub comment
while work remains. Teammate objects chat-draft only.

## Non-negotiable rules

- **Never write anyone else's assigned PR** (or issues not assigned to
  `github.login`). Tickets = GitHub issues (`ticket_source`).
- **AuthZ** is server-side. UI hide ≠ authZ.
- **Ponytail always on for writes.** Name the rung before the first edit.
  `/ponytail off` is illegal on Path 5. Never `ultra` on auth / money /
  migrations / copy. Never cut F1–F10 or a **full/standard** L1–L3 to look
  lean. Lite (script-declared only) may skip L3.
- **Gates are objective** — run them. 3-failure then human. Audit ceiling 5.
- **Secrets:** amend out of history, gitignore, rotate, say so in PR.
- **Browser:** Cursor Browser MCP only (`cursor-ide-browser`) for smoke /
  visual checks. Preflight `browser_mcp_preflight.py`. Never an external browser.
- **AI runtime:** a tool schema is not authorization — re-authorize every tool
  argument server-side (F10).
- **Never tag reviewers** unless the operator names them this turn.
- **Merge / close** still need an explicit ask.
- **Never invoke bug-net / autopilot / unattended Coder workers.** Do not
  route, resume, or steal from them.
- **Agent claims are not facts.** After every subagent return, `lane_truth.py`
  then `claim_lint.py --ticket N --text-file <summary>`. Exit 1 ⇒ do not
  `--record`. Resume with FACTS + the spawn contract — never the agent's
  story (`references/agent-truth.md`). `--record` is parent-only, after the
  parent saw the artifact on this HEAD.

## Pre-push scans (every diff)

1. **Sibling sweep (F3)** — every guard/filter/constant you changed: count
   siblings/consumers/product lines in the PR body.
2. **Vacuous-test probe (F4)** — inputs that make the pre-fix code wrong.
3. **Transaction shape (F2)** — no awaited external HTTP inside a row-locking tx.
4. **Copy truth + density (F6)** — success copy true in every mode; deletion
   test for filler.
5. **Over-engineering (F11)** — ponytail-review delete-list.

Plus the quick line scan in `references/review-bar.md`.

## Definition of Done

1. Decomposed sanely.
2. Intensity-scaled L1 · L2 · L3 (lite skips L3) on the shipping head.
3. Lint 0 / format:check on affected projects.
4. Tests green; mutation-aware (F4).
5. Schema + migrations committed when entities change.
6. Owned ship lane ⇒ PR opened without a second ask.
7. PR mergeable (`MERGEABLE`).
8. User-visible ⇒ 6a live QA then intensity-scaled 6b smoke + Visual table.
9. House PR mechanics; bots triaged after local audit.
10. STAMP + RECONCILE: `record_intention.py` then `reconcile_push_intention.py`
    (`--write-learn`). Exit 1 ⇒ not done.

## Hard rules (absolute)

- Sticky: one `/superdev` binds the **entire** Agent conversation until exit words.
  Auto-switch is session-sticky too. First turn: `--fresh-chat`. Exit: `--auto-switch clear`.
- Local review ladder is HARD: no push / PR-create until L1–L3 pass on that head.
- SuperDev owns review depth. Do not ask.
- Audit/bot forever-loop ban: stop after two consecutive Ship on the same SHA,
  or identical actionable-findings hash, or 5 rounds.
- GitHub write split: ship-lane authorizes commit/push/open own PR. Merge, close,
  reviewer tags, teammate writes need an explicit ask.
- `"Just do X"` narrows this turn; it does not close an in-flight ship lane.
- Learn first, act second. Live state in `state/` only. Never copy another
  operator's `state/`.

## Answer style

Lead with `SuperDev session: active`, then **auto-switch: on|off** ·
**apply: stay|spawn** · **did** · **phase** · **skill_surface** ·
**paths_to_run** · **tier/model** · **ponytail**. On a write
turn, add **rung N**.
PR in play ⇒ name L1/L2/L3 + `prove_intensity` + `review_depth` before GitHub writes. Path 7 drafts:
no process theater — P0/P1 + `file:line` only.
