# SuperDev BOOT (token-saver)

**Sticky session:** if this chat already invoked `/superdev`, keep running
SuperDev on every turn — do not wait for re-tag. Reply with
`SuperDev session: active`. Exit only on explicit user exit words.
**SuperDev's job is one GitHub issue, start → ready for human review.**
The end is L1 fullstack ×2 + L3 Codex **and** Cursor Claude + 6a in-browser QA

- **green** 6b smoke + E2E. A subagent that stops, 401s, or hallucinates
  a gate is a blocked step — the **parent** diagnoses and continues. Do
  not ask to continue. "L1 spawned" is not ready. Unassigned is a ship
  lane. `hard_stop` is only teammate-owned.
  **This repo → `main`.** Commit and push `origin main`. No PR unless asked.
  Standing: if the installed skill has changed significantly from GitHub `main`,
  push without a second ask (hard rules / scripts / lifecycle — not a typo dump).

**SuperDev decides** boot vs full_skill vs full_paths — see `scripts/route_model.py`.

```bash
S=~/.cursor/skills/superdev
python3 $S/scripts/emit_context_pack.py --write
python3 $S/scripts/route_model.py --prompt "<ask>" --path "<stage>" --goal "<goals>" --pretty \
  --parent-model "<this chat's slug>"
# First SuperDev turn of this chat only: add --fresh-chat
# Chat words `auto-switch off|on` write session.json and stick. Exit: --auto-switch clear.
# apply: spawn ⇒ first tool is Task model=<slug>. apply: stay (t0/same_parent/off) ⇒ parent.
# Banner must show apply + did. The Cursor picker never moves.
python3 $S/scripts/work_history.py --active
python3 $S/scripts/check_contradictions.py
python3 $S/scripts/resource_status.py
# Lane in play: facts over agent prose (T1+)
python3 $S/scripts/lane_truth.py --pretty
python3 $S/scripts/unstick_subagents.py --pretty
# After a subagent return: claim_lint.py --ticket N --text-file <summary>
# Before ending a turn that got a job-finished notice: halt_lint.py
```

Light → obey `boot` / `full_skill`. Heavy → obey `paths_to_run` only.
`SKILL.md` is instructions only; detail is one level deep in `references/`.

- `lifecycle.md` — exact steps of the path you are in
- `routing.md` — tier tables
- `skill-routing.md` — which leaf skill to load (`operator.yaml` `skills.*`)
- `intention.md` — TAG → STAMP
- `agent-truth.md` — facts over subagent prose; leftover `next` is work; spawn contract + `claim_lint.py`
- `review-bar.md` / `security-bar.md` on Path 5.5 / 7
- `ponytail.md` on every Path 5 write (name the rung)
- `prove_intensity.py --pretty` when a diff exists — declare before L1/QA/smoke
- `fullstack-audit.md` + `live-qa.md` are integral (team leaves optional)

No push / PR-create until the **intensity-scaled** L1→L3 ladder is green.
L3 skips on **lite**. 6a live QA before 6b smoke. Never **Not covered**.
Never tag/request reviewers unless the operator names them this turn.
Record loops after each phase so routing learns.
Warn on HIGH/MEDIUM contradictions before ACT.
Path 1 ticket source is **GitHub issues** (`gh issue list --assignee $login`)
unless `operator.yaml` says otherwise. Never invent ticket IDs.
**Ponytail always-on for Path 5 writes.** Default `full`.
