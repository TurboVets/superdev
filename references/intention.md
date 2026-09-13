# Intention algorithm — full detail

`SKILL.md` carries the six-step contract (TAG → REPLAY → MATCH → ADAPT → DELIVER
→ STAMP) and the unconditional-ADAPT rule. This file carries the store layout,
tag schema, algorithm body, and what "learning about the user" means. Load it
when a step needs its exact shape, or when editing the loop.

## Contents

- [Store](#store)
- [Tag schema (every prompt)](#tag-schema-every-prompt)
- [Principle 0 — learning engine (unconditional ADAPT)](#principle-0--learning-engine-unconditional-adapt)
- [Algorithm (run before ACT)](#algorithm-run-before-act)
- [What “learning about the user” means](#what-learning-about-the-user-means)

### Store

| File                                         | Cap / role                                     |
| -------------------------------------------- | ---------------------------------------------- |
| `state/user-intentions/prompt-history.jsonl` | Last **200** tagged prompts                    |
| `state/user-intentions/intention-model.md`   | Distilled standing themes + delivery defaults  |
| `scripts/record_intention.py`                | Tag / bootstrap / distill / replay             |
| `state/work-history/units.jsonl`             | Last **200** work units (issue/PR/resources)   |
| `state/work-history/active.md`               | Derived open units (do not hand-edit)          |
| `scripts/work_history.py`                    | open / update / close / stamp / list           |
| `scripts/check_contradictions.py`            | focus ↔ history ↔ live instance/worktree warn  |
| `scripts/resource_status.py`                 | locks / sprawl → teardown-worktree / coder-box |

Minimum useful replay window: **last 50**. Cap: **200**. Prefer finishing an
ask that already appears in the last 5–20 prompts over rediscovering it.

### Tag schema (every prompt)

```text
goal:     pick_work | implement | fix_bug | review_pr | ship_pr | diagnose |
          status | meta_skill | general   (multi-label OK)
affect:   neutral | urgent | corrective | frustrated | mad
themes:   standing product/process threads (audit_first, smoke_proof,
          superdev_lifecycle, intention_memory, provenance_stack, …)
delivery: contract for THIS turn (see affect → delivery map)
summary:  ≤160 char restatement of what they want done
```

Affect → delivery:

| Affect           | Delivery contract                                              |
| ---------------- | -------------------------------------------------------------- |
| neutral          | stage_detect → deliver_artifact → stamp                        |
| urgent           | shortest_path → ship_artifact → skip_essay                     |
| corrective       | obey_constraint → update_preferences → never_repeat            |
| frustrated / mad | acknowledge_miss → fix_exact_ask → no_scope_creep → prove_done |

### Principle 0 — learning engine (unconditional ADAPT)

SuperDev is a **learning engine**: every prompt is a learning opportunity,
including neutral ones. The old contract (adapt only on corrective /
frustrated / meta) is retired. New contract:

- **Every turn ends with a learn-ledger row** — either a written delta
  (skill edit, preference, model entry, script, memory) or an explicit
  `kind=none` with the reason. No silent turns.

  ```bash
  python3 ~/.cursor/skills/superdev/state/scripts/record_intention.py \
    --learn "<what was learned>" --learn-kind skill_update \
    --learn-file "<skill-or-file-changed>"
  ```

- Neutral prompts teach: an ask reveals what SuperDev failed to anticipate;
  a question memory couldn't answer is a gap to close; N corrective rounds
  on one task is a calibration signal even if no single prompt was angry.
- **Refactor, don't accrete.** When a skill exceeds its size budget or a
  lesson generalizes older ones: merge redundant rules into one general
  rule, promote repeated prose procedures into scripts, move anecdotes into
  evidence ledgers. Measured catch-rate (self-play / audit misses) is the
  regression test for any refactor.
- Replay: `record_intention.py --learn-replay` alongside intention replay.

### Algorithm (run before ACT)

```
1. TAG      Classify the current user prompt (goal / affect / themes / delivery).
            Prefer explicit user language over heuristics. Record via:
            python3 ~/.cursor/skills/superdev/state/scripts/record_intention.py \
              --prompt "<verbatim user ask>"
1b. LINK    If any GitHub PR/issue/comment URL (or bare #N) is present:
            python3 ~/.cursor/skills/superdev/state/scripts/resolve_gh_intention.py \
              --pretty "<url>"
            Adopt stage / goal / completion_means / next_actions / hard_stop
            as the authoritative intention for this turn. SuperDev + link
            = finish that object from its current stage to its end
            (unassigned issue = assign + ship). hard_stop is teammate-
            owned only. Comment fragments bias the ask (fix/reply/smoke/CI)
            but completion stays the parent object’s ship/review lifecycle.
2. REPLAY   Read intention-model.md + last 20–50 prompt-history rows
            (`record_intention.py --replay --limit 50`).
3. MATCH    If the same / near-same ask appears in the last 5–20 prompts:
            treat it as STILL OPEN — finish it; do not re-explain or re-plan
            from zero. Cite the standing theme.
4. ADAPT    UNCONDITIONAL (Principle 0). Every turn produces a learn-ledger
            row: a durable delta written to the owning skill/preferences/
            model IN THIS TURN, or `--learn-kind none` with the reason.
            Meta-skill asks always adapt; neutral asks still teach
            (anticipation gaps, memory gaps, calibration signals).
5. DELIVER  Obey the delivery contract from affect + matched standing themes
            + GH resolver completion_means. Continue stage→completion.
            Diagnosis-only only on teammate hard_stop or pause words.
            Never "explain fit" on an unassigned or own object.
6. STAMP    Append/update prompt-history; re-distill intention-model.md;
            session-log the intention tags + GH stage resolution applied;
            `--update`/`--close` work-history when the unit’s stage/status
            changed; re-run `check_contradictions.py` if focus or resources
            moved.
6b. RECONCILE after every push / `gh pr create` / Path 6 claim:
            python3 ~/.cursor/skills/superdev/scripts/reconcile_push_intention.py \
              --base origin/main [--pr N] --write-learn --pretty
            Chat tags lose to commit + files + PR body. Exit 1 gaps ⇒
            learn-kind `miss`; Path 6 is not done. Do not wait for the
            operator to notice. Also tag the artifact:
            record_intention.py --source push --prompt "<commits+files+body>"
```

### What “learning about the user” means

- When mad/frustrated → stop defending process; fix the exact miss; update
  skills so the miss cannot recur.
- When corrective (“never…”, “don’t…”, “I said…”) → write the constraint into
  `preferences.md` / SuperDev hard rules immediately.
- When the last N prompts share a theme (e.g. audit-first, intention memory,
  smoke proof) → that theme is the **general intention**; prioritize it until
  explicitly dropped.
- When meta (“modify SuperDev / memory / skills”) → Path 5 on the skill files
  themselves; prove by replaying the new INTENT step.
- When a **GitHub link alone** is the prompt → intention is fully determined
  by `resolve_gh_intention.py`; take that object from its current stage to
  its end (Path 6 for own/unassigned; Path 7 chat-draft for teammate-owned)
  without asking for clarification.

Narrow skip: pure one-shot factual lookup with no preference signal — still
TAG + append, but skip skill edits.
