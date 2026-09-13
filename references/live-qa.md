# Path 6a — live QA (unrecorded click-through)

Integral SuperDev prove rung. Not smoke (`tv-smoke-test`) and not L1 audit.
Load a team `skills.qa` leaf when set; this file is the contract SuperDev
always runs.

**Clearance = every planned case clicked in this pass.** A leftover list is
not a pass. Never post **Not covered**. A blocker (row never selected, action
that should fail but succeeds) is a finding, not a skip.

## Intensity (from `prove_intensity.py`)

| Intensity    | Click                                                                 |
| ------------ | --------------------------------------------------------------------- |
| **lite**     | The one changed control. No both-sides. Skip if docs-only.            |
| **standard** | Every claimed button / dialog / toast / reload. Leftover = unfinished |
| **full**     | Standard **plus both parties** (agent and client / org A and org B)   |

## Ask vs owned ship lane

- **Owned Path 6:** SuperDev already owns the one local instance — move it,
  do not re-ask to start. Still ask **hosted vs local** unless this message
  already said. **Never wipe volumes** unless the operator said yes.
- **Otherwise:** ask before start / restart / checkout / wipe. Decline ⇒ stop.

Local URL is the team's app origin (never a raw `localhost` SSR port if the
app rejects it). Hosted: only the origin they named.

## Plan

`gh pr view <n> --json title,body,files` → list the claimed surfaces. That
list is the plan. Drive like a user: click, type, submit, navigate. A
screenshot is not a test. After a write, stay on the page **and** hard-reload.

Severity: **P0** data loss / auth leak / blocked action succeeds · **P1**
primary action broken / promised UI missing · **P2** flash / lying label.

Do not film (6b) while a P0/P1 from this pass is open.

## Stack notes (owned local)

Do not start a second instance. Probe before restarting. Unlock the browser
when finished.
