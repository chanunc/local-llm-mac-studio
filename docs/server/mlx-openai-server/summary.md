# mlx-openai-server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Quick Test](#quick-test)
- [API Endpoints](#api-endpoints)
- [JANG Model Support](#jang-model-support)
- [Known Issues](#known-issues)

---

## Overview

[mlx-openai-server](https://github.com/cubist38/mlx-openai-server) is a FastAPI/Uvicorn server providing OpenAI-compatible endpoints for MLX models on Apple Silicon. It features trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, and process-isolated multi-model deployment.

| Property | Value |
|----------|-------|
| Version | 1.7.0 |
| Repository | [cubist38/mlx-openai-server](https://github.com/cubist38/mlx-openai-server) |
| Python | 3.11+ (requires Homebrew Python 3.12 on Mac Studio) |
| Framework | MLX + mlx-lm 0.31.x + Uvicorn/FastAPI |
| API formats | OpenAI `/v1/chat/completions`, `/v1/responses` |
| Model types | Text (lm), multimodal (vlm), image generation (Flux), embeddings, whisper |
| Model formats | MLX safetensors, JANG (via monkey-patch) |
| Install location | `~/mlx-openai-server-env/` on Mac Studio |

---

## Architecture

```
Client (MacBook / Linux / WSL)          Mac Studio M3 Ultra
┌──────────────────────┐                ┌──────────────────────────────────┐
│ Claude Code          │                │ mlx-openai-server (port 8000)   │
│ OpenCode / Pi        │─── LAN ───────>│   Uvicorn + FastAPI              │
│                      │                │   InferenceWorker (queue-based)  │
│                      │                │   Trie prompt cache              │
│                      │                │   OpenAI API only                │
└──────────────────────┘                └──────────────────────────────────┘
```

**Key architectural features:**
- **InferenceWorker**: Single daemon thread processes requests sequentially from a queue (configurable size, default 100). Async handlers submit work via `submit()` / `submit_stream()`.
- **Trie-based prompt cache**: Stores token sequences in a trie for exact matches, shorter prefixes, and longer cached sequences. LRU eviction with optional byte limits. Qwen3.5-specific non-trimmable cache optimization.
- **Process isolation (multi-model)**: Each model runs in a dedicated subprocess using `multiprocessing.spawn` to prevent Metal/GPU semaphore leaks.
- **Speculative decoding**: Uses a small draft model to generate candidate tokens verified by the main model.
- **Reasoning parsers**: Built-in parsers for Qwen3.5, Qwen3, Hermes, Kimi K2, and others. Emits `reasoning_content` in streaming chunks for think tokens.

---

## Installation

### Create dedicated venv

```bash
/opt/homebrew/bin/python3.12 -m venv ~/mlx-openai-server-env
~/mlx-openai-server-env/bin/pip install --upgrade pip
~/mlx-openai-server-env/bin/pip install mlx-openai-server
```

### Install JANG support

```bash
~/mlx-openai-server-env/bin/pip install jang
```

The JANG wrapper script (`~/run_mlx_openai_jang.py`) monkey-patches `mlx_lm.utils.load` before the server imports it. See [JANG Model Support](#jang-model-support) for details.

---

## Usage

### Start server (standard MLX model)

```bash
~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --model-path mlx-community/Qwen3.5-35B-A3B-4bit \
  --served-model-name mlx-community/Qwen3.5-35B-A3B-4bit \
  --port 8000 --host 0.0.0.0
```

### Start server (JANG model)

**Important:** Any command that loads a JANG model must be prefixed with `JANG_PATCH_ENABLED=1`. Without it, the `.pth` patch is dormant and JANG models will fail with a shape mismatch error. See [Maintenance](maintenance.md) for patch details.

```bash
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --model-path ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --served-model-name JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --reasoning-parser qwen3_5 \
  --no-log-file
```

### Start with speculative decoding

```bash
~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --model-path mlx-community/Qwen3.5-35B-A3B-4bit \
  --draft-model-path mlx-community/Qwen3-0.6B-4bit \
  --num-draft-tokens 3 \
  --port 8000 --host 0.0.0.0
```

### Start with YAML config (multi-model)

```yaml
# ~/mlx-openai-server-multimodel.yaml
server:
  host: 0.0.0.0
  port: 8000
models:
  - model_path: /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K
    model_type: lm
    served_model_name: JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K
    reasoning_parser: qwen3_5
    context_length: 262144
  - model_path: /Users/chanunc/.omlx/models/RepublicOfKorokke--Nemotron-Cascade-2-30B-A3B-mlx-nvfp4
    model_type: lm
    served_model_name: RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4
    context_length: 262144
    on_demand: true
    on_demand_idle_timeout: 120
```

```bash
# JANG_PATCH_ENABLED=1 required if any model in the config is JANG format
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml
```

### Key CLI flags

| Flag | Purpose |
|------|---------|
| `--prompt-cache-size N` | Max prompt KV cache entries (default 10, 0 to disable) |
| `--max-bytes N` | Max total bytes for prompt caches before eviction |
| `--reasoning-parser qwen3_5` | Enable Qwen3.5 think-tag parsing |
| `--enable-auto-tool-choice` | Enable automatic tool calling |
| `--context-length N` | Override model's default context length |
| `--no-log-file` | Console-only logging |
| `--log-level DEBUG` | Verbose logging |

### Stop server

```bash
pkill -f mlx-openai-server
# or for JANG wrapper
pkill -f run_mlx_openai_jang
```

### View logs

```bash
tail -20 /tmp/mlx-openai-server.log
```

---

## Quick Test

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K",
    "messages": [{"role": "user", "content": "Say hello in one sentence"}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

---

## API Endpoints

| Endpoint | Model Types | Purpose |
|----------|------------|---------|
| `/v1/chat/completions` | lm, multimodal | Chat completions (streaming + non-streaming) |
| `/v1/responses` | lm, multimodal | OpenAI Responses API |
| `/v1/images/generations` | image-generation | Image creation (Flux) |
| `/v1/images/edits` | image-edit | Image modification |
| `/v1/embeddings` | embeddings | Text vectors |
| `/v1/audio/transcriptions` | whisper | Speech-to-text |
| `GET /v1/models` | all | List available models |

**No Anthropic API support.** Clients must use OpenAI-compatible mode. Claude Code requires `claude-code-router` for Anthropic-to-OpenAI translation.

---

## JANG Model Support

Not supported natively. Requires a `.pth`-based patch in the venv that intercepts `mlx_lm.load()` at Python startup — works in `multiprocessing.spawn` subprocesses and survives pip upgrades. Supports simultaneous JANG + non-JANG multi-model deployment. See [JANG Patch](jang-patch.md) for installation, multi-model config, and details.

---

## Known Issues

1. **64K context performance drop**: 15% overhead vs standalone at 64K context, compared to vllm-mlx's 3%. The overhead likely comes from the inference worker queue and reasoning parser processing.
2. **No Anthropic API**: Clients expecting Anthropic format (Claude Code) need a translation layer like `claude-code-router`.
3. **Single-request concurrency**: The InferenceWorker processes one request at a time. Multiple simultaneous clients will queue.
4. **JANG not native**: Requires `.pth`-based patch in the venv (`jang_patch.pth` + `jang_mlx_patch.py`). Survives pip upgrades but must be reinstalled if the venv is recreated.
5. **Streaming format**: Uses `reasoning_content` field for think tokens instead of `content`. Benchmark scripts and clients expecting `content` or `reasoning` fields will miss these tokens.
6. **Separate venv**: Cannot share the vllm-mlx or oMLX venvs due to dependency conflicts.
7. **Tool call arguments as string**: OpenAI API clients (OpenClaw, etc.) send `tool_call.arguments` as a JSON string, but Qwen3.5's chat template expects a dict — causes `"Can only get item pairs from a mapping"` error. Fixed by `scripts/patch_mlx_openai_tool_args.py` (see [Maintenance](maintenance.md#tool-call-arguments-patch)). Must re-apply after upgrades.
8. **Nemotron family incompatible**: All Nemotron models (Cascade 2, Nano, Super, etc.) store their ChatML chat template in tokenizer Python code — not in `tokenizer_config.json` (which is empty). mlx-lm can't invoke this code path, so messages lack proper `<|im_start|>`/`<|im_end|>` wrapping, degrading even basic chat. mlx-openai-server also lacks the `nemotron_v3` reasoning parser and `qwen3_coder` tool-call parser that vLLM provides, so tool use (OpenClaw) and think-tag streaming are broken — the model echoes raw tool XML (`<parameter=path>...`) instead of answering. Nemotron models require vLLM with `--reasoning-parser nemotron_v3 --tool-call-parser qwen3_coder`.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |

Full file list including JANG patch files: [JANG Patch](jang-patch.md#files-on-mac-studio)
