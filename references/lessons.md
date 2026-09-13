# Lessons ledger

Staging area for operational lessons (rubric LE-1). Each entry is the rule first,
the archaeology second, ≤6 lines. When a lesson hardens, promote it into
`SKILL.md` **replacing prose, not adding**.

Do not import another operator's personal ledger.

### Chat tags lose to the push

After every push / PR-create, `reconcile_push_intention.py`. If 6a/6b/skill
files the operator asked for are missing from the artifact, that is a `miss`
— do not wait for them to notice. `--source push` tags the shipped text.

### Prove intensity from the diff, not the title

`prove_intensity.py` is the gate. Aria-label / CSS / docs = **lite** (no L3,
no both-sides QA). A one-file guard, disconnect, share, or migration = **full**.
Attaching SuperDev runs L1 + 6a; do not wait for a fullstack or QA skill tag.
