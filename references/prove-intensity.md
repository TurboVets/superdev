# Prove intensity — thorough vs quick

SuperDev decides this from the **diff**, never from the PR title, never by
asking. A ticket titled "quick fix" that touches a guard is **full**.

```bash
python3 ~/.cursor/skills/superdev/scripts/prove_intensity.py --base origin/main --pretty
```

Declare the line it prints (`prove_intensity` · `review_depth` · reasons) at
stage detection. When torn, the script returns **full**.

| Intensity    | What the diff looks like                                        | Ladder                                                                                                                      |
| ------------ | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **lite**     | ≤3 runtime files, docs/CSS/aria-label only, **no** full trigger | L1 one pass (skip if docs) · L2 D1 · **L3 skip** · QA the changed control · smoke skip if aria/docs, else one clip · no e2e |
| **standard** | Default. Logic change, no full trigger                          | L1 ×2 Ship · L2 D2 · L3 · QA every claimed surface · one smoke, hold the result · e2e if labeled                            |
| **full**     | Any trigger below, or >20 runtime files                         | L1 ×2 + stability · L2 D3 · L3 · QA **both sides** · smoke both sides, hold the result · e2e if user-visible                |

## Full triggers (any one ⇒ cannot lowball)

authZ / guards · money · migrations / `.sql` · GraphQL schema · shared libs
(`libs/auth|shared|ui|tds|client|cases|…`) · two-party (share, disconnect,
POA, invite, transfer, revoke) · new route · PII redaction · AI runtime ·
`FOR UPDATE` / advisory locks.

A one-file `*.guard.ts` is **full**. A one-file `[aria-label]` is **lite**.

## Do not

- Trust "nit" / "quick" / "chore" in the title.
- Run a two-party QA + dual smoke + local bots on an aria-label.
- Skip both-sides QA on disconnect / share / org-switch because "it's a small diff."
- Invent a fourth intensity. Three is the set.
