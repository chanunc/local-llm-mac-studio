# 🧠 Local LLM Agent Network

Run large language models locally on a **Mac Studio M3 Ultra (96GB)** and connect coding agents over LAN.

```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (96GB)
  Claude Code                            vllm-mlx (primary) :8000
  OpenCode                               or oMLX (multi-model) :8000
  OpenClaw                               OpenAI + Anthropic API
  Pi
```

## ⚡ Quick Start

### 🚀 Start a Server

```bash
# vllm-mlx (fastest, single model)
nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S \
  --served-model-name JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S \
  --port 8000 --host 0.0.0.0 > /tmp/vllm-mlx.log 2>&1 &

# mlx-openai-server (multi-model, low overhead)
# stop other servers first: pkill -f vllm-mlx; /opt/homebrew/bin/brew services stop omlx; sleep 2
JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &

# oMLX (9 models, hot-swap)
# stop other servers first: pkill -f mlx-openai-server; pkill -f vllm-mlx; sleep 2
/opt/homebrew/bin/brew services start omlx
```

### 🩺 Health Check

```bash
# No auth (vllm-mlx / mlx-openai-server)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool

# With auth (oMLX)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool

# Admin dashboard (oMLX only)
open http://<MAC_STUDIO_IP>:8000/admin
```

### 💬 Quick Test

Same command works across all servers — swap in the model name from `/v1/models`. Add `-H "Authorization: Bearer <YOUR_API_KEY>"` for oMLX only.

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<MODEL_NAME>",
    "messages": [{"role": "user", "content": "Say hello in one sentence"}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

---

## 🖥️ Servers

| Server | Speed | Models | API | Best For |
|:-------|:-----:|:------:|:----|:---------|
| **[vllm-mlx](docs/server/vllm-mlx/summary.md)** | ⚡ Fastest | Single | OpenAI + Anthropic | Daily use — lowest overhead on Apple Silicon |
| **[mlx-openai-server](docs/server/mlx-openai-server/summary.md)** | 🟢 Fast | Multi (YAML) | OpenAI | Prompt caching, speculative decoding |
| **[mlx-lm](docs/server/mlx-lm/summary.md)** | 🟡 Good | Single | OpenAI | Lightweight dev/testing |
| **[oMLX](docs/server/omlx/summary.md)** | 🔴 Slower | 9 hot-swap | OpenAI + Anthropic | Model variety with SSD caching |

All servers support [JANG](https://jangq.ai/) mixed-precision models via patches:
[vllm-mlx](docs/server/vllm-mlx/jang-patch.md) ·
[oMLX](docs/server/omlx/jang-fork.md) ·
[mlx-openai-server](docs/server/mlx-openai-server/jang-patch.md) ·
[mlx-lm](docs/server/mlx-lm/jang-patch.md)

Server maintenance: [vllm-mlx](docs/server/vllm-mlx/maintenance.md) · [oMLX](docs/server/omlx/maintenance.md) · [mlx-openai-server](docs/server/mlx-openai-server/maintenance.md)

---

## 🤖 Models

All models fit in **96GB unified memory**.

| Model | Type | Size&#124;GB | Context | Best For |
|:--------------------------------------|:------------|----------:|--------:|:---------|
| [Qwen3.5-122B-A10B JANG 2S](docs/models/model-summary.md#qwen35-122b-a10b-jang-2s) | MoE 122B/10B | 35 | 200K+ | Compact 122B, instant load |
| [Qwen3-Coder-Next 6-bit](docs/models/model-summary.md#qwen3-coder-next-6-bit) | Dense 80B | 60 | 170K | Coding specialist |
| [Qwen3.5-122B-A10B 4-bit](docs/models/model-summary.md#qwen35-122b-a10b-4-bit) | MoE 122B/10B | 65 | 128K | Full-precision alternative |
| [Qwen3.5-27B Opus Distilled](docs/models/model-summary.md#qwen35-27b-claude-opus-distilled-qx64-hi) | Dense 27B | 19 | 128K | Reasoning / chain-of-thought |
| [OmniCoder-9B 8-bit](docs/models/model-summary.md#omnicoder-9b-8-bit) | Dense 9B | 9.5 | 262K | Lightweight coding agent |
| [Qwen3.5-35B-A3B JANG 4K](docs/models/model-summary.md#qwen35-35b-a3b-jang-4-bit-mixed-precision) | MoE 35B/3B | 19 | 262K | Fast small MoE |
| [Nemotron 3 Super 120B](docs/models/model-summary.md#nemotron-3-super-120b-a12b-45-bit) | MoE 120B/12B | 66.5 | 200K | Mamba-2 hybrid |
| [Nemotron 3 Nano 30B](docs/models/model-summary.md#nemotron-3-nano-30b-a3b-8-bit) | MoE 32B/3B | 34 | 262K | NVIDIA MoE |
| [Nemotron Cascade 2 30B](docs/models/model-summary.md#nemotron-cascade-2-30b-a3b-nvfp4) | Hybrid 30B/3B | 17 | 262K | Mamba-2 + MoE |

Full specs and per-model details: [Model Summary](docs/models/model-summary.md)

**Quantization key**: *JANG* = adaptive mixed-precision ([jangq.ai](https://jangq.ai)), *MoE* = Mixture of Experts (total/active params), *nvfp4* = NVIDIA 4-bit float.

---

## 📊 Benchmarks

### Generation Speed (tokens/sec)

**Qwen3-Coder-Next 6-bit** (dense 60GB):

| Server | 512 | 8K | 32K | 64K |
|:-------|:---:|:--:|:---:|:---:|
| vllm-mlx | **68.8** 🥇 | **63.8** 🥇 | **56.4** 🥇 | **51.7** 🥇 |
| mlx-lm | 68.4 🥈 | 62.7 🥈 | 54.0 🥈 | 47.7 🥈 |
| oMLX | 66.5 | 56.9 | 40.4 | 34.8 |

**Qwen3.5-35B-A3B JANG** (MoE, primary architecture):

| Server | 32K | 64K |
|:-------|:---:|:---:|
| vllm-mlx | **83.8** 🥇 | **71.6** 🥇 |
| mlx-openai-server | 81.3 🥈 | 62.8 |
| mlx-lm | 77.6 | 65.1 🥈 |
| oMLX | 59.9 | 49.0 |

Full results: [Standalone](docs/models/model-benchmark-standalone.md) · [API Server](docs/models/model-benchmark-api-server.md) · [TurboQuant KV Cache](docs/models/model-benchmark-turboquant-jang.md)

---

## 🛠️ Coding Agents

| Agent | Description | Setup |
|:------|:------------|:------|
| **Claude Code** | Anthropic's official CLI | [Guide](docs/clients/new-client-machine-setup.md) |
| **OpenCode** | Autonomous coding agent | [Guide](docs/clients/opencode-setup.md) |
| **OpenClaw** | Multi-agent framework | [Guide](docs/clients/openclaw-setup.md) |
| **Pi** | Coding assistant | [Guide](docs/clients/pi-setup.md) |

---

## ⚠️ Known Limitations

See [oMLX Maintenance](docs/server/omlx/maintenance.md) for detailed troubleshooting. Key issues:

- **oMLX**: No GGUF support, JANG+Nemotron-H broken (matmul mismatch), starlette 1.0 dashboard bug ([#361](https://github.com/jundot/omlx/issues/361))
- **Nemotron family**: Requires vllm-mlx — chat template not packaged in MLX weights ([details](docs/models/model-summary.md#server-compatibility))
- **Qwen3.5-122B + OpenClaw**: HTTP 500 with large system prompts ([#42](https://github.com/jundot/omlx/issues/42))
