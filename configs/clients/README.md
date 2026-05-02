# Client Config Templates

Per-server config templates for the four CLI clients we run against the Mac Studio. Drop them into the matching client's config directory after substituting `<MAC_STUDIO_IP>` and `<YOUR_API_KEY>`.

## Two folders, by model type

This folder (`configs/clients/`) holds the **censored / standard / instruction-tuned** roster for each server — Qwen3.6 base/MLX/JANG/JANGTQ standard fine-tunes, Gemma, Ling, Qwen3-Coder, OmniCoder, Osaurus JANGTQ4, etc.

The **uncensored** roster (HauhauCS abliterations, dealignai CRACK variants, NousResearch Hermes, Dolphin, magnum, Huihui abliterated, etc.) lives in the sibling submodule at [`docs/models/uncen-model/client-configs/`](../../docs/models/uncen-model/client-configs/). Pick the folder that matches the model class you want to run; templates have the same per-server shape so you can swap freely.

## Layout (censored roster)

One subdirectory per server. The contents mirror each other so you can swap servers by swapping which subdirectory you copy from.

| Subdir | Server | Default model | Notes |
|:--|:--|:--|:--|
| [`vllm-mlx/`](vllm-mlx/) | `vllm-mlx` | `mlx-community/Ling-2.6-flash-mlx-6bit` | Single-model server. OpenAI + Anthropic. Currently stopped — restart to use. |
| [`llmster/`](llmster/) | `llmster` (LM Studio headless) | `gemma-4-31b-it-mlx` (Gemma 4 31B-it 6-bit MLX, dense) | OpenCode template only. Gemma is the dense agent-loop speed leader on llmster (browse 5.11 s, search 6.37 s); also lists `qwen3.6-27b` 6-bit. For HauhauCS abliterated GGUFs use the uncen-model submodule's llmster templates. |
| [`dflash-mlx/`](dflash-mlx/) | `dflash-mlx` (DFlash speculative decoding) | `mlx-community/Qwen3.6-35B-A3B-4bit` + DFlash drafter | Provisional sidecar on port 8098. **OpenCode template only.** Requires three local patches. |
| [`mlx-openai-server/`](mlx-openai-server/) | `mlx-openai-server` | YAML-driven multi-model | Stable compatible-superset templates; check `/v1/models` for live roster. |
| [`omlx/`](omlx/) | `oMLX` | Multi-model roster | All four client configs maintained in lockstep — see Sync Policy. |
| [`vmlx/`](vmlx/) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Standard-fine-tune JANGTQ path via MLX Studio bundled Python. For dealignai JANGTQ-CRACK variants use the uncen-model submodule's vmlx templates. |

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

Adding or removing a model — or switching the production primary — touches multiple files. Follow the per-event checklists in [`CLAUDE.md` § Sync Policy](../../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) before committing. **Censored-vs-uncensored discipline:** keep the rosters separated by folder. A new censored fine-tune lands here; a new abliteration / CRACK / Hermes-style variant lands in `docs/models/uncen-model/client-configs/`.
