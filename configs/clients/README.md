# Client Config Templates

Per-server config templates for the four CLI clients we run against the Mac Studio. Drop them into the matching client's config directory after substituting `<MAC_STUDIO_IP>` and `<YOUR_API_KEY>`.

## Layout

One subdirectory per server. The contents mirror each other so you can swap servers by swapping which subdirectory you copy from.

| Subdir | Server | Default model | Notes |
|:--|:--|:--|:--|
| [`vllm-mlx/`](vllm-mlx/) | `vllm-mlx` | `mlx-community/Ling-2.6-flash-mlx-6bit` | Production primary. Single model. OpenAI + Anthropic. |
| [`llmster/`](llmster/) | `llmster` (LM Studio headless) | `qwen3.6-27b` | Provisional sidecar on port 1234. **OpenCode template only.** |
| [`dflash-mlx/`](dflash-mlx/) | `dflash-mlx` (DFlash speculative decoding) | `mlx-community/Qwen3.6-35B-A3B-4bit` + DFlash drafter | Provisional sidecar on port 8098. **OpenCode template only.** Requires three local patches. |
| [`mlx-openai-server/`](mlx-openai-server/) | `mlx-openai-server` | YAML-driven multi-model | Stable compatible-superset templates; check `/v1/models` for live roster. |
| [`omlx/`](omlx/) | `oMLX` | Multi-model roster | All four client configs maintained in lockstep — see Sync Policy. |
| [`vmlx/`](vmlx/) | `vmlx` | `dealignai/MiniMax-M2.7-JANGTQ-CRACK` | JANGTQ CRACK path via MLX Studio bundled Python. |

## Files per server

For each fully-supported server, all four exist:

| File | Client |
|:--|:--|
| `opencode.json` | OpenCode |
| `claude-code-settings.json` | Claude Code |
| `pi-models.json` | Pi |
| `openclaw-provider.json` | OpenClaw |
| `qwen-code-settings.json` | Qwen Code |

## Switching servers

Use [`../../scripts/switch_opencode_config.py`](../../scripts/switch_opencode_config.py) to swap OpenCode between templates locally. For other clients, copy the matching file from the server subdir into the client's standard config path (see [`docs/clients/`](../../docs/clients/)).

## Sync Policy

Adding or removing a model — or switching the production primary — touches multiple files. Follow the per-event checklists in [`CLAUDE.md` § Sync Policy](../../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) before committing.
