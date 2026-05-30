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
| [`lm-studio/`](lm-studio/) | `lm-studio` (LM Studio headless) | `granite-4.1-30b-q8` (IBM Granite 4.1 30B Q8_0, dense, Apache 2.0) | Full client template set (OpenCode, OpenClaw, Claude Code via OpenAI-compat, Pi, qwen-code). Roster also includes Gemma 4 31B-it 6-bit MLX, TrevorJS Gemma 4 26B A4B uncensored, DavidAU Heretic family, prithivMLmods/HauhauCS Aggressive variants, Huihui abliterated, Qwen3.6-27B 6-bit. For HauhauCS abliterated GGUFs use the uncen-model submodule's lm-studio templates. |
| [`dflash-mlx/`](dflash-mlx/) | `dflash-mlx` (DFlash speculative decoding) | `mlx-community/Qwen3.6-35B-A3B-4bit` + DFlash drafter | Provisional sidecar on port 8098. **OpenCode template only.** Requires three local patches. |
| [`mlx-openai-server/`](mlx-openai-server/) | `mlx-openai-server` | YAML-driven multi-model | Stable compatible-superset templates; check `/v1/models` for live roster. |
| [`omlx/`](omlx/) | `oMLX` | Multi-model roster | All four client configs maintained in lockstep — see Sync Policy. |
| [`vmlx/`](vmlx/) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Standard-fine-tune JANGTQ path via MLX Studio bundled Python. For dealignai JANGTQ-CRACK variants use the uncen-model submodule's vmlx templates. |
| [`llama-cpp-turboquant/`](llama-cpp-turboquant/) | `llama-cpp-turboquant` (TurboQuant / RotorQuant sidecar) | `qwen3.6-35b-a3b-turboquant-turbo3` (Qwen3.6-35B-A3B Q6_K + turbo3 V on TheTom fork) | Sidecar on port 8099. **OpenCode template only.** Two forks installed: `TheTom/llama-cpp-turboquant` (turbo2/3/4) + `johndpope/llama-cpp-turboquant` (iso3/4 + planar3/4 + turbo2/3/4). |
| [`llama-cpp-mtp/`](llama-cpp-mtp/) | `llama-cpp-mtp` (Qwen3.6 MTP self-drafting speculative decoding sidecar) | `qwen3.6-27b-mtp-ud-q6kxl` (`unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL`, dense 27 B + MTP heads, Unsloth Dynamic 2.0 6-bit) | Sidecar on port 8100. **OpenCode template only.** Built from [`am17an/llama.cpp@mtp-clean`](https://github.com/am17an/llama.cpp/tree/mtp-clean) (PR #22673); only path for Qwen3.6 MTP on Apple Silicon today. |
| [`vmlx-swift-lm/`](vmlx-swift-lm/) | `vmlx-swift-lm` (Osaurus MLX-Swift engine) | `zaya1-8b-jangtq4` (Zyphra ZAYA1-8B JANGTQ4 — top-1 CCA + MoE, 8.4B / 760M-active, Apache 2.0) | Provisional sidecar on port 1337. **OpenCode template only.** Only Mac Studio runtime that natively supports the ZAYA CCA cache contract. Engine: [osaurus-ai/vmlx-swift-lm](https://github.com/osaurus-ai/vmlx-swift-lm); app: `brew install --cask osaurus`. |
| [`mlx-lm/`](mlx-lm/) | `mlx-lm` (mlx_lm.server sidecar) | `chindamt-4b` (`iapp/ChindaMT-4B` — Qwen3.5-4B Thai↔English MT, MLX 4-bit, hybrid SSM/attention) | Sidecar on port 8080. **OpenCode template only.** Requires manual MLX conversion (tied-embedding strip + `mlx_lm.convert`); started with `--chat-template-args '{"enable_thinking":false}'`. |
| [`ds4/`](ds4/) | `ds4` (DwarfStar 4 native engine) | `deepseek-v4-flash` (`antirez/deepseek-v4-gguf` IQ2XXS-imatrix — DeepSeek-V4-Flash 284B/13B-active `deepseek4` MoE, 81 GB GGUF) | Sidecar on port 8101. **OpenCode template only.** Only Apple-Silicon path for `deepseek4` ([`antirez/ds4`](https://github.com/antirez/ds4), pure C+Metal, native DSML↔OpenAI tool calling). |
| [`litert-lm/`](litert-lm/) | `litert-lm` (Google LiteRT-LM edge runtime) | `gemma4-e4b` (`litert-community/gemma-4-E4B-it-litert-lm` — Gemma 4 E4B ~4B effective, 3.66 GB `.litertlm`) | Sidecar on port 9379. **OpenCode template only.** Alpha OpenAI serve mode. CPU/XNNPACK only (GPU broken on Apple Silicon). No `tools` param, no structured tool_calls. |
| [`sglang/`](sglang/) | `sglang` (SGLang MLX sidecar) | `openbmb/MiniCPM5-1B` (HF checkpoint, MiniCPM5 parser path) | Sidecar on port 30000. **OpenCode template only.** Provisional SGLang source install with `SGLANG_USE_MLX=1`; MiniCPM5 needs `--tool-call-parser minicpm5` and No Think mode for the local tool harness. |

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
