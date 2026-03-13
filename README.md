# 🧠 Local LLM Agent Network

High-performance local AI infrastructure powered by a **Mac Studio M3 Ultra (96GB)**. This repository provides setup guides to run massive LLMs locally and connect multiple coding agents over LAN.

## 🚀 Server Options
- **Primary: [oMLX](https://github.com/jundot/omlx)** ([Setup Guide](docs/server/omlx-summary.md)) — Optimized server with native OpenAI/Anthropic API support.
- **Alternative: [mlx-lm](https://github.com/ml-explore/mlx-examples/tree/main/llms/mlx_lm)** ([Setup Guide](docs/server/mlxlm-summary.md)) — Native MLX implementation with custom routing.

## 🤖 Models & Benchmarks
Performance and context limits optimized for **96GB Unified Memory**.

| Model | Quant | Size | Context (96GB) | **Hot Cache (RAM)** | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Qwen3-Coder-Next** | 6-bit | ~60GB | 128K - 170K | **30GB** | **Daily Driver** (Coding) |
| **Qwen3-Coder-Next** | 8-bit | ~79GB | 16K - 32K | **8GB** | Maximum precision |
| **Qwen3.5-27B Claude Opus Distilled** | qx64-hi (6-bit) | ~19GB | 128K | **20GB** | Reasoning / Chain-of-thought |
| **Qwen3.5-122B-A10B** | 4-bit | ~65GB | 64K - 128K | **25GB** | Agentic reasoning |

*Quant notes: **6-bit** = best quality/size balance for daily use. **8-bit** ≈ full precision, limited context. **qx64-hi** = hybrid 6-bit with higher-precision attention layers, smaller footprint than standard 6-bit.*
*Hot Cache requires the [per-model patch](plans/plan-hot-cache-max-size-per-model.md) to be applied.*

## 🛠️ Tools & Agents
- **Claude Code**: Anthropic's official CLI ([Setup](docs/clients/new-client-machine-setup.md))
- **OpenCode**: Autonomous coding agent ([Setup](docs/clients/opencode-setup.md))
- **OpenClaw**: Multi-agent framework ([Setup](docs/clients/openclaw-setup.md))
- **Pi**: Coding assistant ([Setup](docs/clients/pi-setup.md))

## 📡 Connectivity
- **Health Check**: `curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"`
- **Admin Panel**: `http://<MAC_STUDIO_IP>:8000/admin`

---
*For advanced troubleshooting and discovery fixes, see the [Maintenance Guide](docs/server/omlx-maintenance.md).*
