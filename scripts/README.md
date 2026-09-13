# SuperDev scripts

| Script | Role |
| ------ | ---- |
| `route_model.py` | **Decides** skill_surface + paths_to_run + model; learns from `--record --loops` |
| `browser_mcp_preflight.py` | Disk/live Cursor Browser MCP gap check |
| `local-bot-review.sh` | Local Claude + Codex bot replicas before push |
| `battle_rhythm.py` | Path 5 gates: kickoff / recon / harness / setup-green / 3-failure / deviate / smoke-script / pattern archive / promote |
| `prove_intensity.py` | **Decides** lite / standard / full from the diff (never the title). `--pretty` / `--self-check` |
| `reconcile_push_intention.py` | After push: asked vs commit/files/PR body. Exit 1 gaps ⇒ Path 6 not done. `--write-learn` |

Related: `scripts/rate_skills.py` (promote/tighten/demote) + `references/skill-routing.md`.

```bash
# Decide
python3 route_model.py --prompt "..." --path 5.5 --goal ship_pr --pretty
# Learn (after phase)
python3 route_model.py --record --model gpt-5.6-sol-medium --phase 5.5 --loops 2 --outcome ship
# Rankings
python3 route_model.py --leaderboard
```

Related memory scripts: `emit_context_pack.py`, `record_intention.py`,
`compact_session_log.py`.

