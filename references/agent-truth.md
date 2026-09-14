# Agent truth — facts over prose

SuperDev owns completion. Subagents execute a `NEXT`. They do not declare done.

## Sources (only these)

| Fact                            | Source                                                         |
| ------------------------------- | -------------------------------------------------------------- |
| HEAD, dirty, ahead, last commit | `git` in the ticket worktree                                   |
| PR, mergeable, player in body   | `gh pr list` — close/fix/resolves `#N` or branch contains N    |
| L1 / L3 / 6a / 6b               | `<lane.dir>/truth.json` SHA fields, recorded by the **parent** |
| E2E                             | `gh` check-runs on the PR SHA — name contains `e2e`, `success` |
| Quiet / boot-stuck              | transcript mtime + last `current_step`                         |

A completion summary, a stamp chip, a dashboard line, or another agent's
story is a **claim**. If CLAIM ≠ FACT, the claim is discarded.

## After every subagent return

```bash
S=~/.cursor/skills/superdev
python3 $S/scripts/lane_truth.py --pretty
python3 $S/scripts/lane_truth.py --facts-block --ticket <N>
```

The tab is **every open own PR** (`github.login` on `default_repo`), plus
lane issues with no PR. `done: true` means ready for human review
(L1+L3+6a+6b+E2E on HEAD). Do not merge unless asked. Leftover `next` is
work — finish it.

1. If `done: true` — that PR is ready. Leave it.
2. If `next` is set — resume/spawn with the FACTS block. Never paste the
   agent's story back in.
3. `--record` only after the parent saw the artifact on **this HEAD**
   (audit files, both L3 verdicts, 6a cases clicked, player URL in the PR).
   An agent saying "L1 Ship" is not a record.

## Prompt contract

Every resume/spawn starts with FACTS + NEXT. If the agent contradicts FACTS,
interrupt and send FACTS again.

Quiet >5 min or stuck on SuperDev boot → `unstick_subagents.py` (it refuses
`done` unless `lane_truth` binds all five to HEAD).
