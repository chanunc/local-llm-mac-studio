# Server Docs

Operational runbooks for inference servers on the Mac Studio. Run [`scripts/chk_llm_macstu.py`](../../scripts/chk_llm_macstu.py) to probe what is live now, then open the matching runbook below.

| Server | Runbook | Role |
|:--|:--|:--|
| `vllm-mlx` | [`vllm-mlx/summary.md`](vllm-mlx/summary.md) | Production primary, single-model, OpenAI + Anthropic APIs |
| `lm-studio` | [`lm-studio/summary.md`](lm-studio/summary.md) | Fast standard MLX/GGUF sidecar on port 1234 |
| `dflash-mlx` | [`dflash-mlx/summary.md`](dflash-mlx/summary.md) | Provisional DFlash speculative-decoding sidecar on port 8098 |
| `mlx-openai-server` | [`mlx-openai-server/summary.md`](mlx-openai-server/summary.md) | OpenAI-only multi-model YAML server |
| `oMLX` | [`omlx/summary.md`](omlx/summary.md) | Homebrew-managed multi-model server with dashboard |
| `vmlx` | [`vmlx/summary.md`](vmlx/summary.md) | JANGTQ / TurboQuant path via MLX Studio bundled Python |
| `ollama` | [`ollama/summary.md`](ollama/summary.md) | Ollama Apple-Silicon MLX sidecar on port 11434 |
| `vmlx-swift-lm` | [`vmlx-swift-lm/summary.md`](vmlx-swift-lm/summary.md) | MLX-Swift engine via Osaurus on port 1337 — only path for ZAYA1 / Hy3 / MiniMax-M2.7 |
| `mlx-lm` | [`mlx-lm/summary.md`](mlx-lm/summary.md) | Lightweight single-model development server |
| `llama-cpp-turboquant` | [`llama-cpp-turboquant/summary.md`](llama-cpp-turboquant/summary.md) | Provisional RotorQuant / TurboQuant / PlanarQuant KV-cache sidecar on port 8099 |
| `llama-cpp-mtp` | [`llama-cpp-mtp/summary.md`](llama-cpp-mtp/summary.md) | Provisional MTP (Qwen3.6 self-drafting speculative decoding) sidecar on port 8100 |
| `qwen-asr` | [`qwen-asr/summary.md`](qwen-asr/summary.md) | Speech-to-text sidecar (Qwen3-ASR, transformers + MPS, no port-bound daemon) |
| `comfyui` | [`comfyui/summary.md`](comfyui/summary.md) | Image-generation sidecar on port 8188 (ComfyUI + Z-Anime, MPS, web UI only — no OpenAI shim) |
| `ds4` | [`ds4/summary.md`](ds4/summary.md) | DwarfStar 4 native engine on port 8101 — only Apple-Silicon path for DeepSeek-V4-Flash (`deepseek4` arch, DSML tool calling) |
| `litert-lm` | [`litert-lm/summary.md`](litert-lm/summary.md) | Provisional Google LiteRT-LM edge runtime on port 9379 — Gemma 4 E4B, CPU/XNNPACK, alpha OpenAI serve (no tool calling) |
| `sglang` | [`sglang/summary.md`](sglang/summary.md) | Provisional SGLang MLX sidecar on port 30000 — MiniCPM5 `minicpm5` parser path |

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
