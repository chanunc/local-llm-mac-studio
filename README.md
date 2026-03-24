# 🧠 Local LLM Agent Network

High-performance local AI infrastructure powered by a **Mac Studio M3 Ultra (96GB)**. This repository provides setup guides to run massive LLMs locally and connect multiple coding agents over LAN.

## Index
- [Server Options](#-server-options)
  - [oMLX](docs/server/omlx-summary.md) · [JANG Fork](docs/server/omlx-jang-fork.md) · [Maintenance](docs/server/omlx-maintenance.md) · [mlx-lm](docs/server/mlxlm-summary.md)
- [Models & Benchmarks](#-models--benchmarks)
  - [Qwen3-Coder-Next 6-bit](docs/models/model-summary.md#qwen3-coder-next-6-bit) · [Qwen3.5-27B Opus Distilled](docs/models/model-summary.md#qwen35-27b-claude-opus-distilled-qx64-hi) · [Qwen3.5-122B 4-bit](docs/models/model-summary.md#qwen35-122b-a10b-4-bit) · [Qwen3.5-122B JANG 2S](docs/models/model-summary.md#qwen35-122b-a10b-jang-2s) · [OmniCoder-9B](docs/models/model-summary.md#omnicoder-9b-8-bit) · [Nemotron 3 Nano](docs/models/model-summary.md#nemotron-3-nano-30b-a3b-8-bit) · [Nemotron 3 Super 120B](docs/models/model-summary.md#nemotron-3-super-120b-a12b-45-bit) · [Nemotron Cascade 2 30B](docs/models/model-summary.md#nemotron-cascade-2-30b-a3b-nvfp4) · [Qwen3.5-35B JANG 4-bit](docs/models/model-summary.md#qwen35-35b-a3b-jang-4-bit-mixed-precision)
- [Tools & Agents](#-tools--agents)
  - [Claude Code](docs/clients/new-client-machine-setup.md) · [OpenCode](docs/clients/opencode-setup.md) · [OpenClaw](docs/clients/openclaw-setup.md) · [Pi](docs/clients/pi-setup.md)
- [Connectivity](#-connectivity)
- [oMLX Limitations](#-omlx-limitations)

## 🚀 Server Options
- **Primary: [oMLX](https://github.com/jundot/omlx)** ([Setup Guide](docs/server/omlx-summary.md) · [JANG Fork](docs/server/omlx-jang-fork.md) · [Maintenance](docs/server/omlx-maintenance.md)) — Optimized server with native OpenAI/Anthropic API support. JANG and nvfp4 format support via [AlexTzk fork overlay](docs/server/omlx-jang-fork.md).
- **Alternative: [mlx-lm](https://github.com/ml-explore/mlx-examples/tree/main/llms/mlx_lm)** ([Setup Guide](docs/server/mlxlm-summary.md)) — Native MLX implementation with custom routing.

## 🤖 Models & Benchmarks
Performance and context limits optimized for **96GB Unified Memory**.

| Model | Quant | Size | Context (96GB) | **Hot Cache (RAM)** | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [**Qwen3-Coder-Next**](https://huggingface.co/mlx-community/Qwen3-Coder-Next-6bit) | 6-bit | ~60GB | 128K - 170K | **20GB** | **Daily Driver** (Coding) |
| [**Qwen3.5-27B Claude Opus Distilled**](https://huggingface.co/nightmedia/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx) | qx64-hi (6-bit) | ~19GB | 128K | **20GB** | Reasoning / Chain-of-thought |
| [**Qwen3.5-122B-A10B**](https://huggingface.co/mlx-community/Qwen3.5-122B-A10B-4bit) | 4-bit | ~65GB | 64K - 128K | **20GB** | Agentic reasoning |
| [**Qwen3.5-122B-A10B JANG**](https://huggingface.co/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S) | JANG 2-bit | ~35GB | 200K+ | **12GB** | Compact 122B · 46% smaller than MLX 4-bit · instant mmap load |
| [**OmniCoder-9B**](https://huggingface.co/NexVeridian/OmniCoder-9B-8bit) | 8-bit | ~9.5GB | 262K | **8GB** | Coding Agent — trained on 425K+ curated agentic coding trajectories |
| [**Nemotron 3 Nano 30B-A3B**](https://huggingface.co/mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit) | 8-bit | ~34GB | 262K | **20GB** | NVIDIA MoE · 32B total, 3B active |
| [**Nemotron 3 Super 120B-A12B**](https://huggingface.co/inferencerlabs/NVIDIA-Nemotron-3-Super-120B-A12B-MLX-4.5bit) | 4.5-bit | ~66.5GB | 200K | **12GB** | 120B MoE (12B active) · Mamba-2 + Attention hybrid |
| [**Nemotron Cascade 2 30B-A3B**](https://huggingface.co/RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4) | nvfp4 | ~17GB | 32K | **12GB** | Mamba-2 + MoE + Attention hybrid · 30B total, 3B active · 55 tok/s |
| [**Qwen3.5-35B-A3B JANG**](https://huggingface.co/JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K) | JANG 4-bit | ~19GB | 262K | **24GB** | JANG mixed-precision · 48% smaller than MLX 8-bit · 0.8s load |

*Quant notes: **6-bit** = best quality/size balance for daily use. **8-bit** ≈ full precision, limited context. **qx64-hi** = hybrid 6-bit with higher-precision attention layers, smaller footprint than standard 6-bit. **JANG** = adaptive mixed-precision (attention 6-8 bit, experts 2-4 bit) via [jangq.ai](https://jangq.ai), requires fork overlay.*
*Hot Cache requires the [per-model patch](plans/plan-hot-cache-max-size-per-model.md) to be applied.*

## 🛠️ Tools & Agents
- **Claude Code**: Anthropic's official CLI ([Setup](docs/clients/new-client-machine-setup.md))
- **OpenCode**: Autonomous coding agent ([Setup](docs/clients/opencode-setup.md))
- **OpenClaw**: Multi-agent framework ([Setup](docs/clients/openclaw-setup.md))
- **Pi**: Coding assistant ([Setup](docs/clients/pi-setup.md))

## 📡 Connectivity
- **Health Check**: `curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"`
- **Admin Panel**: `http://<MAC_STUDIO_IP>:8000/admin`

## ⚠️ oMLX Limitations

Known compatibility gaps with oMLX as of v0.2.20 (+ AlexTzk JANG fork):

- **GGUF format**: oMLX only serves MLX safetensors and JANG models. GGUF models (e.g. from `llama.cpp`) are not supported — use `llama-server` or LM Studio for those.
- **JANG + Nemotron-H**: JANG-quantized Nemotron-H models fail with matmul shape mismatch at the latent MoE gate — bug in PR #364's weight mapping. Non-Nemotron JANG models (Qwen3.5, etc.) work fine.
- **MXFP8 quantization**: Models quantized with the `mxfp8` format are not confirmed to load. Use standard `4-bit`, `6-bit`, `8-bit` MLX or JANG quantizations instead.
- **Starlette dashboard bug**: oMLX v0.2.20 pulls starlette 1.0.0 which breaks the admin dashboard with "unhashable type: dict" error. Fix: `pip install "starlette==0.46.2"` in the oMLX venv ([#361](https://github.com/jundot/omlx/issues/361)).
- **Qwen3.5-27B Claude Opus Distilled + OpenClaw**: Dense 27B model — every token requires all 27B parameters, too slow for OpenClaw.
- **Qwen3.5-122B + OpenClaw**: Known HTTP 500 errors with large system prompts. Tracked in [oMLX #42](https://github.com/jundot/omlx/issues/42).

---
*For advanced troubleshooting and discovery fixes, see the [Maintenance Guide](docs/server/omlx-maintenance.md).*
