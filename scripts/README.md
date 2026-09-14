# SuperDev scripts

| Script | Role |
| ------ | ---- |
| `route_model.py` | **Decides** skill_surface + paths_to_run + model; `--auto-switch` session spawn; learns from `--record --loops` |
| `browser_mcp_preflight.py` | Disk/live Cursor Browser MCP gap check |
| `local-bot-review.sh` | Codex CLI + Cursor Claude Task replicas before push |
| `battle_rhythm.py` | Path 5 gates: kickoff / recon / harness / setup-green / 3-failure / deviate / smoke-script / pattern archive / promote |
| `prove_intensity.py` | **Decides** lite / standard / full from the diff (never the title). `--pretty` / `--self-check` |
| `reconcile_push_intention.py` | After push: asked vs commit/files/PR body. Exit 1 gaps ⇒ Path 6 not done. `--write-learn` |
| `lane_truth.py` | SHA-bound L1/L3/6a/6b/E2E for every open own PR. `--facts-block` / `--record` (parent only) |
| `claim_lint.py` | Fail if prose claims a greener L1/L3/6a/6b/done than `lane_truth`. Run on every subagent return |
| `unstick_subagents.py` | Parent-owned finish: quiet / boot-stuck / claimed-done while `next` exists → resume or spawn |
| `halt_lint.py` | Fail if a reply or bot log is a mid-lane halt. Job-finished notice is resume |
| `gh_comment_lint.py` | ≤1200 chars / ≤10 lines before any GitHub comment. `--exempt evidence\|question` |
| `cleanup_smoke_repos.py` | Dry-run / `--apply` delete of stale `tv-smoke-*` staging repos |

Related: `scripts/rate_skills.py` (promote/tighten/demote) + `references/skill-routing.md`.

```bash
# Decide (first SuperDev turn of a chat)
python3 route_model.py --fresh-chat --prompt "..." --path 5.5 --goal ship_pr --pretty \
  --parent-model cursor-grok-4.6-high-fast
# Session switch
python3 route_model.py --auto-switch off
python3 route_model.py --auto-switch status
# Learn (after phase)
python3 route_model.py --record --model gpt-5.6-sol-medium --phase 5.5 --loops 2 --outcome ship
# Rankings
python3 route_model.py --leaderboard
python3 route_model.py --self-check
```

Related memory scripts: `emit_context_pack.py`, `record_intention.py`,
`compact_session_log.py`.

