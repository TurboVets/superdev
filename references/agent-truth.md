# Agent truth — facts over prose

**SuperDev's job:** one GitHub issue, start → ready for human review
(`done: true` = L1 + L3 Codex **and** Claude + 6a + green 6b + E2E on
**this HEAD**). A fluent summary is not that. Zero hallucination is a
_system_ property (HALO 2026; Anthropic: ground truth from the
environment at each step). The model will invent. The harness must refuse.

**Parent owns the finish.** A subagent that stops, 401s, boot-loops, or
claims a greener gate is unfinished work. The parent runs
`lane_truth.py` + `claim_lint.py`, opens the artifact on this HEAD (or
treats the gate as unset), diagnoses the blocker, and resumes or spawns.
Do not ask the operator. Do not paste agent A's story into agent B.

## Layers (what the world does → what we run)

| Layer                     | Borrowed from                | SuperDev                                                                                                                                           |
| ------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Retrieve before speak  | RAG / cite-or-drop           | `git` / `gh` / `lane_truth.py` before any HEAD / L1 / L3 / 6a / 6b / e2e sentence                                                                  |
| 2. Constrained state      | OpenAI RunState              | FACTS block is the only legal state string. Agents do not own `truth.json`                                                                         |
| 3. Deterministic verifier | HALO layer 3 (non-LLM check) | `turn_gate.py` (claim_lint + halt_lint + receipt). Cursor `stop` / `subagentStop` hooks resume if the receipt is stale. LLM-as-judge is not enough |
| 4. Evidence tracing       | cite-or-drop / SourceCheckup | A verdict names a file path + SHA. A topical cite is not support                                                                                   |
| 5. Abstain                | faithfulness judges          | No tool output ⇒ write `UNVERIFIED`, never a SHA or "Ship"                                                                                         |
| 6. Inter-agent isolation  | multi-agent failure surveys  | Never paste agent A's story into agent B. FACTS only                                                                                               |

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
python3 $S/scripts/advance_lane.py --strict
python3 $S/scripts/turn_gate.py --ticket <N> --text-file <draft>
```

`turn_gate` exit 1 ⇒ do not send the reply, do not `--record`. Cursor stop
hooks auto-submit a resume if the receipt is missing or stale.
`advance_lane.py --strict` exit 1 ⇒ unread L1/L3 files; open, `--ingest`,
then record. A `>>> claude` line with no `VERDICT:` is an abrupt stop.
Reads of `lane_truth.py` do not write. Only `--record` / `--ingest --apply`.

The tab is **every open own PR** (`github.login` on `default_repo`), plus
lane issues with no PR. `done: true` means ready for human review
(L1+L3 Codex **and** Claude+6a+green 6b+E2E on HEAD). "L1 spawned" /
"fixer running" is not that. Do not merge unless asked. Leftover `next`
is work — the parent finishes it.

1. If `done: true` — that PR is ready. Leave it.
2. If `next` is set — resume/spawn with the FACTS block. Never paste the
   agent's story back in. A quiet or halted agent is a parent unstick,
   not a status essay.
3. `--record` only after the parent saw the artifact on **this HEAD**.
   An agent saying "L1 Ship" is not a record.

## Spawn contract (paste at the top of every Task prompt)

```
FACTS (from lane_truth.py --facts-block) bind this ticket. Do not contradict them.
You may not state HEAD, L1, L3, 6a, 6b, e2e, mergeable, or done unless you just
ran git/gh/lane_truth and quote that output. No tool output ⇒ UNVERIFIED.
You may not run lane_truth.py --record. You may not cite a verdict file you
did not open. Do not invent a SHA or a tool result. Do not claim a greener
next than FACTS. If you did not click it, it is not 6a. If the player URL is
not in the PR body on this HEAD, 6b is unset.
```

Quiet >5 min or stuck on SuperDev boot → `unstick_subagents.py` (refuses
`done` unless `lane_truth` binds all five to HEAD).
