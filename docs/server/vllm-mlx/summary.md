# vllm-mlx Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Quick Test](#quick-test)
- [API Endpoints](#api-endpoints)
- [JANG Model Support](#jang-model-support)
- [Tool Calling & Reasoning (Qwen3.5)](#-tool-calling--reasoning-qwen35)
- [Known Issues](#known-issues)

---

## Overview

[vllm-mlx](https://github.com/vllm-project/vllm-mlx) is a vLLM port for Apple Silicon, providing GPU-accelerated inference with native OpenAI-compatible and Anthropic-format APIs. It is the **fastest server tested** for single-request throughput on the Mac Studio M3 Ultra, achieving only 3-4% overhead vs raw standalone `mlx_lm.generate()`.

| Property | Value |
|----------|-------|
| Version | 0.2.6 |
| Repository | [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx) |
| Python | 3.10+ (requires Homebrew Python 3.12 on Mac Studio) |
| Framework | MLX + Uvicorn/FastAPI |
| API formats | OpenAI-compatible `/v1/chat/completions`, Anthropic-format `/v1/messages` (native) |
| Model formats | MLX safetensors, JANG (via monkey-patch) |
| Install location | `~/vllm-mlx-env/` on Mac Studio |

---

## 🏗️ Architecture

```
Client (MacBook / Linux / WSL)          Mac Studio M3 Ultra
┌──────────────────────┐                ┌──────────────────────────────┐
│ Claude Code          │                │ vllm-mlx (port 8000)        │
│ OpenCode / Pi        │─── LAN ───────>│   Uvicorn + FastAPI          │
│                      │                │   mlx_lm model backend       │
│                      │                │   Native OpenAI-compatible + Anthropic-format APIs │
└──────────────────────┘                └──────────────────────────────┘
```

vllm-mlx wraps `mlx_lm` model loading and `stream_generate()` with an async Uvicorn/FastAPI server. It supports:
- Continuous batching (with `--continuous-batching` flag)
- Prompt caching
- Speculative prefill
- Tool calling (with `--enable-auto-tool-choice`)
- Reasoning extraction (with `--reasoning-parser`)
- MCP server integration
- Embeddings API
- Audio transcription/speech

---

## ⚙️ Installation

### Create dedicated venv

vllm-mlx requires Python 3.10+. Mac Studio's system Python is 3.9.6, so use Homebrew Python:

```bash
/opt/homebrew/bin/python3.12 -m venv ~/vllm-mlx-env
~/vllm-mlx-env/bin/pip install --upgrade pip
~/vllm-mlx-env/bin/pip install 'git+https://github.com/waybarrios/vllm-mlx.git'
```

### Fix missing return bug (v0.2.6)

vllm-mlx v0.2.6 has a bug where `load_model_with_fallback()` in `vllm_mlx/utils/tokenizer.py` does not return the model tuple after a successful `mlx_lm.load()`. See [jang-patch.md](jang-patch.md#3-fix-the-missing-return-bug-v026) for the one-line fix.

### Install JANG support (optional)

```bash
~/vllm-mlx-env/bin/pip install 'jang[mlx]>=0.1.0'
```

See [jang-patch.md](jang-patch.md) for the full JANG wrapper setup.

---

## 🚀 Usage

### Start server (standard MLX model)

```bash
~/vllm-mlx-env/bin/vllm-mlx serve \
  mlx-community/Qwen3.5-35B-A3B-4bit \
  --port 8000 --host 0.0.0.0
```

### Start server (JANG model)

```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0
```

### CLI chat

```bash
~/vllm-mlx-env/bin/vllm-mlx-chat mlx-community/Qwen3.5-35B-A3B-4bit
```

### CLI benchmark

```bash
~/vllm-mlx-env/bin/vllm-mlx-bench mlx-community/Qwen3.5-35B-A3B-4bit
```

### Debug logging

vllm-mlx has no `--log-level` flag. Apply the patch once (see [maintenance guide](maintenance.md#7-debug-logging)), then use `VLLM_MLX_LOG_LEVEL` with any launch method:

```bash
VLLM_MLX_LOG_LEVEL=DEBUG ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S \
  --served-model-name JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S \
  --port 8000 --host 0.0.0.0
```

### Stop server

```bash
pkill -f vllm-mlx
# or
pkill -f run_vllm_jang
```

---

## 💬 Quick Test

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S",
    "messages": [{"role": "user", "content": "Say hello in one sentence"}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

---

## 🔌 API Endpoints

| Endpoint | Format | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | OpenAI | Chat completions (streaming + non-streaming) |
| `/v1/completions` | OpenAI | Text completions |
| `/v1/messages` | Anthropic | Anthropic Messages API (native) |
| `/v1/messages/count_tokens` | Anthropic | Token counting |
| `/v1/models` | OpenAI | List loaded models |
| `/v1/embeddings` | OpenAI | Text embeddings |
| `/v1/audio/transcriptions` | OpenAI | Audio transcription |
| `/v1/audio/speech` | OpenAI | Text-to-speech |
| `/v1/mcp/tools` | Custom | MCP tool listing |
| `/v1/mcp/execute` | Custom | MCP tool execution |
| `/v1/status` | Custom | Server status |
| `/v1/cache/stats` | Custom | Cache statistics |
| `/health` | Custom | Health check |

---

## 🧠 JANG Model Support

Not supported natively. Requires a monkey-patch wrapper script. See [jang-patch.md](jang-patch.md) for step-by-step instructions.

---

## 🔧 Tool Calling & Reasoning (Qwen3.5)

Qwen3.5 models (all sizes) use a **non-standard XML tool-call format** (`<function=name><parameter=key>value</parameter></function>`) instead of JSON. This requires specific parser flags:

```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --served-model-name JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3
```

| Flag | Required for | What happens without it |
|------|-------------|------------------------|
| `--enable-auto-tool-choice` | Any tool use | Server ignores `tools[]` in requests |
| `--tool-call-parser qwen3_coder` | Qwen3.5 tool calls | Raw `<tool_call>` XML leaks into `content` as plain text |
| `--reasoning-parser qwen3` | Qwen3 thinking models | `<think>…</think>` dumps into `content` instead of `reasoning` field |

**Parser mapping:** `qwen3_coder` is aliased to the `HermesToolParser` which handles the Nemotron XML format (`<function=name><parameter=key>value</parameter></function>`). Do **not** use `--tool-call-parser qwen` — that parser expects JSON inside `<tool_call>` tags, which Qwen3.5 does not emit.

**Known issue — stale `.pyc` cache:** After patching or upgrading `server.py`, delete compiled bytecode or the old code runs:
```bash
find ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/__pycache__/ -name 'server*.pyc' -delete
```

**Community references:**
- [HuggingFace Qwen3.5-35B-A3B discussions #4](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/discussions/4) — 21 template bugs documented
- [vLLM PR #35347](https://github.com/vllm-project/vllm/pull/35347) — dedicated `Qwen35CoderToolParser`
- [Ollama #14493](https://github.com/ollama/ollama/issues/14493) — Qwen3.5 tool calling "completely non-functional" with wrong parser
- [mlx-lm #1061](https://github.com/ml-explore/mlx-lm/issues/1061) — MLX quantizations show progressive tool-call degradation

---

## ⚠️ Known Issues

1. **v0.2.6 return bug:** `load_model_with_fallback()` missing return statement. Must patch after install.
2. **Single model per instance:** Only one model loaded at a time. No hot-swapping.
3. **No persistent service:** Must be started manually (see [Usage](#usage) for start/stop commands).
4. **Separate venv from oMLX:** Cannot share the oMLX Homebrew Python environment (version conflict).
5. **JANG not native:** Requires monkey-patch wrapper for JANG models.
6. **Model ID is full path:** When using local model paths, the API model ID is the filesystem path.
7. **Qwen3.5 tool calls need `qwen3_coder` parser:** See [Tool Calling & Reasoning](#-tool-calling--reasoning-qwen35) above.

## 🧩 Nemotron Support

vllm-mlx is the **only local server** with full Nemotron support — built-in chat template fallback, `nemotron` tool parser, and `think` reasoning parser. mlx-openai-server and oMLX cannot serve Nemotron models correctly. See [Nemotron Server Compatibility](../../models/model-summary.md#nemotron-server-compatibility) for details.
