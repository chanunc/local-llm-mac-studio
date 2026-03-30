# mlx-openai-server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Compact Hermes 4.3 36B](#compact-hermes-43-36b)
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
  - model_path: /Users/chanunc/.omlx/models/mlx-community/Qwen3-Coder-Next-6bit
    model_type: lm
    served_model_name: mlx-community/Qwen3-Coder-Next-6bit
    enable_auto_tool_choice: true
    tool_call_parser: qwen3_coder
    reasoning_parser: qwen3_next
    context_length: 170000
```

```bash
~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file
```

Repo-managed reference config for the models currently supportable on this Mac Studio:
- [macstudio-supported-models.yaml](/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/server/mlx-openai-server/macstudio-supported-models.yaml)

Included there:
- Qwen3.5 JANG 122B / 35B with `qwen3_coder` + `qwen3_5`
- Qwen3-Coder-30B-A3B-Instruct with `qwen3_coder`
- Hermes 4 70B with `hermes`
- Hermes 4.3 36B as a Seed-OSS chat-only entry with a custom template
- Qwen3.5-VL 122B as a medium-confidence multimodal entry

Excluded there:
- Nemotron family, which this repo still routes to `vllm-mlx`
- Mistral Small 4 JANG, which is not currently supportable on this `mlx-openai-server` stack

### Compact Hermes 4.3 36B

Validated on 2026-03-30:
- Model: `alexcovo/Hermes-4.3-36B-mlx-4Bit` (community MLX conversion of `NousResearch/Hermes-4.3-36B`)
- Launch shape: `--trust-remote-code` plus the official Seed-OSS chat template
- Reference files:
  - [mlx-openai-server-hermes43-36b.yaml](/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/server/mlx-openai-server/mlx-openai-server-hermes43-36b.yaml)
  - [seed-oss-36b-chat-template.jinja](/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/server/mlx-openai-server/seed-oss-36b-chat-template.jinja)

Observed behavior on Mac Studio M3 Ultra:
- Loads and serves short chat completions successfully on `mlx-openai-server`
- Short prompts responded in roughly 3 to 6 seconds during validation
- The current `mlx-openai-server` build does not expose a `seed_oss` tool parser, so treat this model as chat-only on this server
- Responses can continue past the first useful answer unless clients keep `max_tokens` conservative or trim at the first `<|eot_id|>`

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
    "model": "mlx-community/Qwen3-Coder-Next-6bit",
    "messages": [{"role": "user", "content": "Say hello in one sentence"}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

Current live roster on the Mac Studio:
- `mlx-community/Qwen3-Coder-Next-6bit`

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
8. **Nemotron family incompatible**: No chat template fallback, no reasoning/tool parsers for Nemotron. Use vllm-mlx instead. See [Nemotron Server Compatibility](../../models/model-summary.md#nemotron-server-compatibility) for details.
9. **Mistral Small 4 is not currently supported here**: Upstream `mlx-lm` does not yet ship native `mistral4` support, and this repo no longer carries a local patch path. Use `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`, or `vLLM` for Mistral's official self-deployment path.
10. **Seed-OSS models need extra wiring**: Compact Hermes 4.3 36B is based on `seed_oss`, not the older Hermes tokenizer family. On this `mlx-openai-server` build it needs an explicit Seed-OSS chat template and currently has no validated tool parser path.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |

Full file list including JANG patch files: [JANG Patch](jang-patch.md#files-on-mac-studio)
