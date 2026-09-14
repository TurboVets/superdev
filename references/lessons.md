# Lessons ledger

Staging area for operational lessons (rubric LE-1). Each entry is the rule first,
the archaeology second, ≤6 lines. When a lesson hardens, promote it into
`SKILL.md` **replacing prose, not adding**.

Do not import another operator's personal ledger.

### Auto-switch never flipped the picker and never spawned

`auto-switch: on` was printed every turn while the parent kept doing the work.
T0 was `inherit`, so simple Qs stayed on Grok High Fast. T0/T1 now spawn
Composer unless the parent is already Composer. T2 Grok / T3 GPT / T4 Claude
(Fable + Opus). Banner shows `apply` + `did`. `--parent-model` on every boot.

### This repo lands on main — no PR unless asked

Skill changes: commit on `main` and `git push origin main`. A PR for a
SuperDev-repo change is unnecessary unless the operator asks for one.
Standing: if the installed skill has changed significantly from this `main`
(new hard rules, scripts, or lifecycle), push without asking. Port to this
layout. Pause words still override.

### SuperDev + a link ships that object; unassigned is not a hard_stop

Tagging SuperDev with an issue/PR URL means take it from its current stage
to Path 6. `hard_stop` is only teammate-owned (someone else assigned).
Unassigned is a ship lane — assign + complete. Never "explain fit."

### Never stop mid-lane — four artifacts or it is not finished

Owned ship end is **all four green**: L1 `/tv-fullstack` ×2, L3 local
Codex **and** Claude APPROVE, 6a in-browser QA, **green** 6b smoke +
player. Stopping after Path 5 ("ladder owed — say the word") is a miss.
Resume the earliest unfinished artifact. Merge still needs an ask.

### Do not wire a 1Password MCP until the token is already in Cursor

BugTrace was evaluated, wired as optional Path 5 K2, then ripped out — vault
unlock blocked connect. `precedent_lookup` stays the only K2 recon.

### Chat tags lose to the push

After every push / PR-create, `reconcile_push_intention.py`. If 6a/6b/skill
files the operator asked for are missing from the artifact, that is a `miss`
— do not wait for them to notice. `--source push` tags the shipped text.

### Prove intensity from the diff, not the title

`prove_intensity.py` is the gate. Aria-label / CSS / docs = **lite** (no L3,
no both-sides QA). A one-file guard, disconnect, share, or migration = **full**.
Attaching SuperDev runs L1 + 6a; do not wait for a fullstack or QA skill tag.
