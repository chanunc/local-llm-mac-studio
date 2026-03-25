# vllm-mlx Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [JANG Model Support](#jang-model-support)
- [Performance](#performance)
- [Known Issues](#known-issues)

---

## Overview

[vllm-mlx](https://github.com/vllm-project/vllm-mlx) is a vLLM port for Apple Silicon, providing GPU-accelerated inference with an OpenAI + Anthropic compatible API. It is the **fastest server tested** for single-request throughput on Mac Studio M3 Ultra, achieving only 3-4% overhead vs raw standalone `mlx_lm.generate()`.

| Property | Value |
|----------|-------|
| Version | 0.2.6 |
| Repository | [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx) |
| Python | 3.10+ (requires Homebrew Python 3.12 on Mac Studio) |
| Framework | MLX + Uvicorn/FastAPI |
| API formats | OpenAI `/v1/chat/completions`, Anthropic `/v1/messages` (native) |
| Model formats | MLX safetensors, JANG (via monkey-patch) |
| Install location | `~/vllm-mlx-env/` on Mac Studio |

---

## Architecture

```
Client (MacBook / Linux / WSL)          Mac Studio M3 Ultra
┌──────────────────────┐                ┌──────────────────────────────┐
│ Claude Code          │                │ vllm-mlx (port 8000)        │
│ OpenCode / Pi        │─── LAN ───────>│   Uvicorn + FastAPI          │
│                      │                │   mlx_lm model backend       │
│                      │                │   OpenAI + Anthropic native  │
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

## Installation

### Create dedicated venv

vllm-mlx requires Python 3.10+. Mac Studio's system Python is 3.9.6, so use Homebrew Python:

```bash
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/vllm-mlx-env"
ssh macstudio "~/vllm-mlx-env/bin/pip install --upgrade pip"
ssh macstudio "~/vllm-mlx-env/bin/pip install 'git+https://github.com/waybarrios/vllm-mlx.git'"
```

### Fix missing return bug (v0.2.6)

vllm-mlx v0.2.6 has a bug where `load_model_with_fallback()` in `vllm_mlx/utils/tokenizer.py` does not return the model tuple after a successful `mlx_lm.load()`. See [vllm-mlx-jang-patch.md](vllm-mlx-jang-patch.md#3-fix-the-missing-return-bug-v026) for the one-line fix.

### Install JANG support (optional)

```bash
ssh macstudio "~/vllm-mlx-env/bin/pip install 'jang[mlx]>=0.1.0'"
```

See [vllm-mlx-jang-patch.md](vllm-mlx-jang-patch.md) for the full JANG wrapper setup.

---

## Usage

### Start server (standard MLX model)

```bash
ssh macstudio "~/vllm-mlx-env/bin/vllm-mlx serve \
  mlx-community/Qwen3.5-35B-A3B-4bit \
  --port 8000 --host 0.0.0.0"
```

### Start server (JANG model)

```bash
ssh macstudio "~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0"
```

### CLI chat

```bash
ssh macstudio "~/vllm-mlx-env/bin/vllm-mlx-chat mlx-community/Qwen3.5-35B-A3B-4bit"
```

### CLI benchmark

```bash
ssh macstudio "~/vllm-mlx-env/bin/vllm-mlx-bench mlx-community/Qwen3.5-35B-A3B-4bit"
```

### Stop server

```bash
ssh macstudio "pkill -f vllm-mlx"
# or
ssh macstudio "pkill -f run_vllm_jang"
```

---

## API Endpoints

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

## JANG Model Support

Not supported natively. Requires a monkey-patch wrapper script. See [vllm-mlx-jang-patch.md](vllm-mlx-jang-patch.md) for step-by-step instructions.

---

## Performance

Tested on Mac Studio M3 Ultra with Qwen3.5-35B-A3B. Full results in [model-benchmark-api-server.md](../models/model-benchmark-api-server.md).

### Generation Speed (tok/s)

| Context | vllm-mlx (4bit) | vllm-mlx (JANG) | oMLX (JANG) | Standalone |
|---------|-----------------|-----------------|-------------|-----------|
| 512 | 106.4 | 100.7 | -- | 109.7 |
| 8K | 100.1 | 95.6 | -- | 103.0 |
| 32K | 86.5 | 83.8 | 59.9 | 90.3 |
| 64K | 74.3 | 71.4 | 49.0 | 76.3 |

### Server Overhead vs Standalone

| Context | vllm-mlx overhead | oMLX overhead |
|---------|------------------|---------------|
| 32K | -4% | -34% |
| 64K | -3% | -36% |

---

## Known Issues

1. **v0.2.6 return bug:** `load_model_with_fallback()` missing return statement. Must patch after install.
2. **Single model per instance:** Only one model loaded at a time. No hot-swapping.
3. **No persistent service:** Must be started manually. Create a launchd plist for auto-start.
4. **Separate venv from oMLX:** Cannot share the oMLX Homebrew Python environment (version conflict).
5. **JANG not native:** Requires monkey-patch wrapper for JANG models.
6. **Model ID is full path:** When using local model paths, the API model ID is the filesystem path.
