# mlx-openai-server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [JANG Model Support](#jang-model-support)
- [Performance](#performance)
- [Comparison with vllm-mlx](#comparison-with-vllm-mlx)
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

```bash
nohup ~/mlx-openai-server-env/bin/python ~/run_mlx_openai_jang.py launch \
  --model-path ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --served-model-name JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --reasoning-parser qwen3_5 \
  --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &
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
# ~/mlx-openai-server-config.yaml
server:
  host: 0.0.0.0
  port: 8000
models:
  - model_path: mlx-community/Qwen3.5-35B-A3B-4bit
    model_type: lm
    served_model_name: qwen3.5-35b
  - model_path: mlx-community/Qwen3-0.6B-4bit
    model_type: lm
    served_model_name: qwen3-0.6b
    on_demand: true
    idle_timeout: 60
```

```bash
~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-config.yaml
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

Not supported natively. Requires a monkey-patch wrapper script (`~/run_mlx_openai_jang.py`) that:

1. Patches `mlx_lm.utils.load` before any server imports
2. Patches the already-imported `load` reference in `app.models.mlx_lm`
3. Detects JANG model paths via `jang_tools.loader.is_jang_model()`
4. Delegates to `jang_tools.load_jang_model()` which returns the standard `mlx_lm.models.qwen3_5_moe.Model` class

The wrapper is at `~/run_mlx_openai_jang.py` on the Mac Studio. Unlike vllm-mlx (which only needs `mlx_lm.load` patched), mlx-openai-server uses `from mlx_lm.utils import load` directly, so both `mlx_lm.utils.load` and the module-level `load` reference must be patched.

---

## Performance

Tested on Mac Studio M3 Ultra with Qwen3.5-35B-A3B JANG 4K. Full results in [model-benchmark-api-server.md](../models/model-benchmark-api-server.md).

### Generation Speed (tok/s)

| Context | mlx-openai-server | vllm-mlx | mlx-lm.server | oMLX | Standalone |
|---------|-------------------|---------|---------------|------|-----------|
| 512 | 99.4 | **100.5** | 96.3 | -- | 103.6 |
| 8K | 93.9 | **95.5** | 90.7 | -- | 98.0 |
| 32K | 81.3 | **83.6** | 77.6 | 59.9 | 86.5 |
| 64K | 62.8 | **71.6** | 65.1 | 49.0 | 73.9 |

### Server Overhead vs Standalone

| Context | mlx-openai-server | vllm-mlx | mlx-lm.server | oMLX |
|---------|-------------------|---------|---------------|------|
| 512 | -4% | -3% | -7% | -- |
| 8K | -4% | -2% | -7% | -- |
| 32K | -6% | -3% | -10% | -31% |
| 64K | **-15%** | -3% | -12% | -34% |

### Time to First Token (seconds)

| Context | mlx-openai-server | vllm-mlx | mlx-lm.server |
|---------|-------------------|---------|---------------|
| 512 | **0.44** | 0.56 | 0.62 |
| 8K | 3.11 | **3.10** | 3.17 |
| 32K | 15.17 | **15.15** | 15.33 |
| 64K | 39.47 | **39.30** | 39.55 |

---

## Comparison with vllm-mlx

| Feature | mlx-openai-server v1.7 | vllm-mlx v0.2.6 |
|---------|------------------------|------------------|
| **Generation speed** | 4-15% overhead (worse at 64K) | **3-4% overhead (consistent)** |
| **TTFT** | Slightly faster at 512 | Slightly faster at 8K+ |
| **Prompt caching** | **Trie-based LRU, byte limits, Qwen3.5-specific** | Basic KV cache reuse |
| **Speculative decoding** | **Built-in (`--draft-model-path`)** | Not documented |
| **Reasoning parser** | **Native Qwen3.5 think-tag parser** | Generic |
| **Multi-model** | **Native YAML config, on-demand loading** | Single model only |
| **Continuous batching** | No (single-request queue) | **Yes** |
| **Anthropic API** | No (OpenAI only) | **Native `/v1/messages`** |
| **Multimodal** | **Vision, image gen, whisper** | Vision, audio |

**Bottom line:** vllm-mlx is faster for raw single-stream throughput. mlx-openai-server has richer features (speculative decoding, prompt cache, multi-model) that could help in interactive multi-turn workflows, but at a generation speed cost — especially at long contexts.

---

## Known Issues

1. **64K context performance drop**: 15% overhead vs standalone at 64K context, compared to vllm-mlx's 3%. The overhead likely comes from the inference worker queue and reasoning parser processing.
2. **No Anthropic API**: Clients expecting Anthropic format (Claude Code) need a translation layer like `claude-code-router`.
3. **Single-request concurrency**: The InferenceWorker processes one request at a time. Multiple simultaneous clients will queue.
4. **JANG not native**: Requires monkey-patch wrapper with two-level patching (module + import reference).
5. **Streaming format**: Uses `reasoning_content` field for think tokens instead of `content`. Benchmark scripts and clients expecting `content` or `reasoning` fields will miss these tokens.
6. **Separate venv**: Cannot share the vllm-mlx or oMLX venvs due to dependency conflicts.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/run_mlx_openai_jang.py` | JANG monkey-patch wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
