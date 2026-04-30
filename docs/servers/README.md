# Server Docs

Operational runbooks for inference servers on the Mac Studio. Use [`docs/current.md`](../current.md) first to see what is live now, then open the matching runbook below.

| Server | Runbook | Role |
|:--|:--|:--|
| `vllm-mlx` | [`vllm-mlx/summary.md`](vllm-mlx/summary.md) | Production primary, single-model, OpenAI + Anthropic APIs |
| `llmster` | [`llmster/summary.md`](llmster/summary.md) | Fast standard MLX/GGUF sidecar on port 1234 |
| `mlx-openai-server` | [`mlx-openai-server/summary.md`](mlx-openai-server/summary.md) | OpenAI-only multi-model YAML server |
| `oMLX` | [`omlx/summary.md`](omlx/summary.md) | Homebrew-managed multi-model server with dashboard |
| `vmlx` | [`vmlx/summary.md`](vmlx/summary.md) | JANGTQ / TurboQuant path via MLX Studio bundled Python |
| `mlx-lm` | [`mlx-lm/summary.md`](mlx-lm/summary.md) | Lightweight single-model development server |

## Maintenance And Patches

| Topic | Doc |
|:--|:--|
| vllm-mlx maintenance | [`vllm-mlx/maintenance.md`](vllm-mlx/maintenance.md) |
| vllm-mlx JANG wrapper | [`vllm-mlx/jang-patch.md`](vllm-mlx/jang-patch.md) |
| mlx-openai-server maintenance | [`mlx-openai-server/maintenance.md`](mlx-openai-server/maintenance.md) |
| mlx-openai-server JANG patch | [`mlx-openai-server/jang-patch.md`](mlx-openai-server/jang-patch.md) |
| oMLX maintenance | [`omlx/maintenance.md`](omlx/maintenance.md) |
| oMLX JANG fork | [`omlx/jang-fork.md`](omlx/jang-fork.md) |
| vmlx maintenance | [`vmlx/maintenance.md`](vmlx/maintenance.md) |
| mlx-lm JANG patch | [`mlx-lm/jang-patch.md`](mlx-lm/jang-patch.md) |

Patch scripts live under [`../../scripts/patches/`](../../scripts/patches/). Re-run them after upstream package upgrades when the relevant runbook says so.
