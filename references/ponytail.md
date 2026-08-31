# Ponytail — SuperDev least-code bar

Adopted 2026-08-21 from [ponytail](http://ponytail.dev)
([DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail)).
Cursor slash skills live at `~/.cursor/skills/ponytail*/SKILL.md`
(`/ponytail`, `/ponytail-review`, `/ponytail-audit`, `/ponytail-debt`,
`/ponytail-gain`, `/ponytail-help`). SuperDev still owns intensity, the
write-time ladder, and the delete-list review.

**ALWAYS ON for SuperDev product-code writes** (operator, 2026-08-21). Not a
default you can skip. Write without naming the rung = miss (same weight as
skipping L1). Intensity is **full** unless the operator sets `lite` or `ultra` this
session. Persist in `~/.config/ponytail/config.json` or `PONYTAIL_DEFAULT_MODE`.
`/ponytail off` / "stop ponytail" / "normal mode" do **not** apply to SuperDev
Path 5 or any runtime-code ApplyPatch/Write. House F1–F10 still never get cut.

## When it runs

| Path         | What SuperDev does                                                                         |
| ------------ | ------------------------------------------------------------------------------------------ |
| **5 K2/K3**  | Climb the ladder **after** reading the flow, **before** writing. Say the rung in one line. |
| **5.5 / L2** | Run **ponytail-review** on the working tree diff. Record axis `over-engineering`.          |
| **7**        | Same delete-list, chat-draft only on teammate PRs. Never a GitHub essay.                   |

Does **not** YAGNI SuperDev process: L1–L3, smoke, coverage, Path 6 completeness,
grill, or house PR body.

## The ladder (stop at the first rung that holds)

1. **Need to exist?** Speculative = skip, say so in one line. (YAGNI)
2. **Already here?** Reuse. On this repo `@turbovets/shared/utils` and the
   existing helper/pattern win — do not re-inline `uniq` / `sleep` / `cloneDeep`.
3. **Stdlib?** Use it.
4. **Native platform?** `<input type="date">`, CSS, DB constraint, Angular/Nest
   primitive already in the stack.
5. **Already-installed dep?** Use it. Do not add a package for a few lines.
6. **One line?** One line.
7. **Only then:** the minimum that works.

Read fully, then be lazy. Two rungs work → take the higher one. Bug fix = one
root-cause guard (this **is** F3 sibling sweep), not a patch on the ticket path.

## Intensity

| Level     | SuperDev behavior                                                                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **lite**  | Build the ask. Name the lazier alternative in one line. User picks.                                                                                                                 |
| **full**  | Ladder enforced. Shortest working diff. **Always-on default.**                                                                                                                      |
| **ultra** | YAGNI extremist. Ship the one-liner and challenge the rest of the ask. **Forbidden** on auth, money, migrations, user-facing copy, shared-lib authZ (same surfaces that forbid D1). |
| **off**   | **Illegal on SuperDev writes.** Ignore it. Stay at `full`. House F1–F10 still run.                                                                                                  |

## House overrides (never simplify away)

Vanilla ponytail carves out validation, data-loss handling, security, a11y.
SuperDev adds:

- **F1–F10** (`review-bar.md`) — AuthZ, tx shape, sibling sweep, vacuous tests,
  contracts, copy truth, migrations, provenance, ship mechanics, AI runtime.
- **F4 tests** beat ponytail's "one assert / no fixtures." Mutation-aware
  positive+negative twins stay. A trivial one-liner still needs no new test.
- **L1–L3 ladder, smoke, coverage** — process, not product code.
- **Shared-lib / multi-PL** — product-line neutrality stays; do not delete a
  shared gate to shrink a vets-only ticket.

Mark a real corner-cut with a `ponytail:` comment: ceiling + upgrade path.

## Ponytail-review (L2 axis `over-engineering`)

Over-engineering only. Correctness / security / perf stay on F1–F10. One line
per finding. Does not apply the cuts — lists them; SuperDev applies P0/P1 cuts
in the same session.

Format: `file:L12-38: tag: what to cut. What replaces it.`

| Tag       | Means                                                                     |
| --------- | ------------------------------------------------------------------------- |
| `delete:` | Dead code, unused flexibility, speculative feature. Replacement: nothing. |
| `stdlib:` | Hand-rolled thing the language/runtime ships. Name the function.          |
| `native:` | Dep or code doing what the platform already does. Name the feature.       |
| `yagni:`  | Abstraction with one impl, config nobody sets, layer with one caller.     |
| `shrink:` | Same logic, fewer lines. Show the shorter form.                           |

End with `net: -N lines possible.` Nothing to cut → `Lean already. Ship.`

Never flag for deletion: one mutation-aware test, a sibling-sweep guard,
an AuthZ check, a `SET LOCAL lock_timeout`, or a trust-boundary validator.

## Commands SuperDev honors in chat

| Command                                     | Effect                                                               |
| ------------------------------------------- | -------------------------------------------------------------------- |
| `/ponytail` / `/ponytail lite\|full\|ultra` | Report or set intensity. `off` is a no-op on SuperDev writes.        |
| `/ponytail-review`                          | Delete-list on the current diff (this file).                         |
| `/ponytail-audit`                           | Same hunt, whole touched packages — not a repo-wide rewrite.         |
| `/ponytail-debt`                            | Collect `ponytail:` comments in the working tree into a chat ledger. |
| `/ponytail-help`                            | Point here.                                                          |

Do not copy ponytail into `platform/.cursor/rules/` (team-wide). The Cursor
adapter lives at `~/.cursor/rules/ponytail.mdc` (user-scope).
