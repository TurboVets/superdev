# SuperDev BOOT (token-saver)

**Sticky session:** if this chat already invoked `/superdev`, keep running
SuperDev on every turn — do not wait for re-tag. Reply with
`SuperDev session: active`. Exit only on explicit user exit words.

**SuperDev decides** boot vs full_skill vs full_paths — see `scripts/route_model.py`.

```bash
S=~/.cursor/skills/superdev
python3 $S/scripts/emit_context_pack.py --write
python3 $S/scripts/route_model.py --prompt "<ask>" --path "<stage>" --goal "<goals>" --pretty
python3 $S/scripts/work_history.py --active
python3 $S/scripts/check_contradictions.py
python3 $S/scripts/resource_status.py
```

Light → obey `boot` / `full_skill`. Heavy → obey `paths_to_run` only.
`SKILL.md` is instructions only; detail is one level deep in `references/`.

- `lifecycle.md` — exact steps of the path you are in
- `routing.md` — tier tables
- `skill-routing.md` — which leaf skill to load (`operator.yaml` `skills.*`)
- `intention.md` — TAG → STAMP
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
