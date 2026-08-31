# SuperDev

Cursor Agent skill that runs an **issue-to-ship lifecycle** with a local review
ladder **before** any PR exists. Generalized flow. Per-operator identity lives
in `operator.yaml` — not in the skill.

This is the shareable extraction of the SuperDev operator used on TurboVets
platform work. It does **not** include anyone's personal memory, mail, or
product-law files.

## What you get

| Quality | What it actually does |
| ------- | --------------------- |
| **Sticky session** | One `/superdev` binds the rest of the Agent chat until `exit SuperDev`. |
| **Token-economy boot** | Path 0 emits a small context pack and picks a model tier (T0–T4). It does not re-read the whole skill every turn. |
| **GitHub link = intention** | A pasted PR/issue/comment URL is enough. SuperDev resolves stage + completion means and continues. |
| **Never skip / never stop early** | Untestable AC blocks code. A 5.5 audit is not a status report — it continues through prove + PR. |
| **L1 → L2 → L3 ladder** | Local audit ×2 Ship → human-lane coverage → local bot replicas. No push / PR-create until that head is green. |
| **Ponytail (least code)** | Name the ladder rung before the first product-code write. `/ponytail off` is illegal on Path 5. |
| **Owned vs teammate** | Own ship lane: commit / push / open PR. Teammate PRs: chat-draft P0/P1 only. Never write someone else's GitHub. |
| **Intention memory** | Tags every prompt; adapts delivery. Personal `state/` — do not copy another operator's. |
| **Work-history + contradictions** | Tracks issue/PR/worktree units; warns before acting against stale focus. |
| **House review bar** | Sibling sweep, vacuous-test probe, tx shape, copy truth+density, over-engineering (F1–F11). |
| **Security bar** | S-1…S-11 on auth / URL / upload / HTML / PII diffs. |
| **Path 6 completeness** | Mergeable PR, subtitled smoke + inline player when user-visible, Visual before-after table. |

### The flow (same for every operator)

```
0 boot  →  1 pick  →  2 issue  →  3 grill  →  4 unknowns
                 ↘  5 build  →  5.5 local audit ladder  →  6 prove / PR  →  7 review
```

A GitHub URL jumps to the matching stage. Merge still needs an explicit ask.

## Install

```bash
git clone <this-repo-url> ~/src/superdev
cd ~/src/superdev
./install.sh
```

`install.sh` copies the skill to `~/.cursor/skills/superdev`, writes
`operator.yaml` from the example if missing, pre-fills `github.login` from
`gh api user`, and installs the sticky Cursor rule
`~/.cursor/rules/superdev-sticky.mdc`.

Then edit `~/.cursor/skills/superdev/operator.yaml`:

```yaml
github:
  login: "your-gh-login"          # required
  default_repo: "org/repo"        # required for bare issue/PR numbers
workspace:
  path: "/absolute/path/to/repo"
skills:
  audit: "tv-fullstack"           # your team's fullstack audit skill, or empty
  frontend: "tv-frontend"
  backend: "tv-backend"
  smoke: "tv-smoke-test"
```

In a **new** Agent chat, attach the `superdev` skill or type `/superdev`.

**Do not copy `state/` from another person.** Intentions and work-history are
personal. Empty state is correct on first run.

## What the colleague must configure

### Required

| Tool | Why | How |
| ---- | --- | --- |
| [GitHub CLI](https://cli.github.com/) `gh` | Resolve PRs/issues, open own PRs, list assigned tickets | `gh auth login` then `gh api user --jq .login` |
| `operator.yaml` `github.login` + `default_repo` | SuperDev will not guess identity | `./install.sh` + edit the file |
| Cursor Agent | This is a Cursor skill, not a Claude plugin | Clone + `./install.sh` |

### Recommended MCP (Cursor → Settings → MCP)

| MCP | SuperDev uses it for | If missing |
| --- | -------------------- | ---------- |
| **Cursor Browser** (`cursor-ide-browser`) | Path 6 smoke, visual proof, session capture | SuperDev **stops** before smoke and asks you to enable Browser Tab. Status must read **Connected to Browser Tab**. |
| Team audit skill (in-repo) | Path 5.5 L1 | Set `skills.audit` or SuperDev says the skip out loud on docs-only diffs |

### Optional MCP

| MCP | When to turn on | SuperDev rule |
| --- | --------------- | ------------- |
| Fathom (`user-fathom`) | Path 1 transcripts the operator names | Skip if unset. Never `list_meetings` as a default hunt. |
| Slack (`plugin-slack-slack`) | Read-only product rulings | **Never post.** Draft outreach in chat for the operator to send. |
| Nx (`user-nrwl.angular-console-extension-nx-mcp`) | Monorepo graph / generators | Optional. `nx` CLI still works without it. |
| Figma | Only when a figma.com URL is pasted | Off otherwise. |
| Atlassian / Jira | Off | Tickets are GitHub issues. Do not enable unless you change `ticket_source`. |

### Optional CLIs (L3 local bots)

`scripts/local-bot-review.sh` replicates in-repo `@codex` / `@claude` review
workflows against `base...HEAD`. Needs:

- `npx @openai/codex login`
- `claude` → `/login`
- The **target repo** to have the same auto-review prompt stack (or L3 is a skip
  you say out loud)

### Ponytail

Least-code bar is bundled (`references/ponytail.md`). Intensity is `full` unless
you set `ponytail.intensity` in `operator.yaml`. Never `ultra` on auth, money,
migrations, or user-facing copy.

## Layout

```
SKILL.md                 # flow + hard rules (<500 lines)
BOOT.md                  # Path 0 token-saver
operator.example.yaml    # copy → operator.yaml
install.sh
rules/superdev-sticky.mdc
scripts/                 # boot, routing, GH resolve, coverage, bots
references/              # lifecycle, review-bar, security-bar, ponytail, …
state/                   # created locally; gitignored
```

## Common extractions (what to reuse as-is)

These are the portable parts. Keep them. Plug team skills around them.

1. **Paths 0–7** — stage table + required artifact (`references/lifecycle.md`)
2. **Link resolver** — `resolve_gh_intention.py`
3. **L1–L3 ladder** — audit ×2, coverage, local bots
4. **Ponytail** — write-time least-code + L2 delete-list
5. **F1–F11 review bar** + **S-1…S-11 security bar**
6. **`route_model.py`** — tier + `--record --loops` learning
7. **Intention + work-history** — personal `state/`, same scripts
8. **Sticky rule** — conversation-scoped, not auto-start
9. **GitHub write split** — own PR vs teammate vs merge-needs-ask

Team-specific (do **not** ship in this repo; point `operator.yaml` at them):

- Product law / grill scales
- Full-stack audit skill name
- Smoke + asset-upload skills
- In-repo bot prompt stacks

## Invoke

```
/superdev
/superdev https://github.com/org/repo/pull/123
```

Exit: `exit SuperDev` / `drop SuperDev` / `normal agent` / `without SuperDev`.

## What SuperDev will not do

- Write a teammate's PR or an issue not assigned to `github.login`
- Request reviewers or `@mention` unless you name them this turn
- Merge / close without an explicit ask
- Post to Slack
- Start on a fresh chat that never invoked it
- Import another operator's `state/`
