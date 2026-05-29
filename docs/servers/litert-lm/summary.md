# litert-lm Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Starting the server](#starting-the-server)
- [Health check](#health-check)
- [Tool-call benchmarks](#tool-call-benchmarks)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`litert-lm` is Google's production-ready, open-source edge inference framework ([github.com/google-ai-edge/LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)). It bundles models in `.litertlm` format with XNNPACK CPU acceleration. The CLI includes an alpha OpenAI-compatible HTTP server (`litert-lm serve --api openai`).

**Status: provisional sidecar — deployed 2026-05-28.** Evaluation only. The OpenAI serve mode is alpha: no `tools` parameter, no GET /v1/models, per-character SSE chunks, max ~3K context.

Bound to port **9379** (default), OpenAI API only. Coexists with all other servers on their dedicated ports.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌─────────────────────────────────────────────┐
│ Claude Code    │            │ litert-lm serve (port 9379, sidecar)        │
│ OpenCode       │─── LAN ───>│   ~/.litert-lm/models/gemma4-e4b/           │
│                │            │   model: Gemma 4 E4B (~4B effective, 3.66GB)│
│                │            │   backend: CPU / XNNPACK                    │
│                │            │   OpenAI API only (alpha)                   │
│                │            │   --api openai --host 0.0.0.0               │
└────────────────┘            └─────────────────────────────────────────────┘
```

## Installation

```bash
# Install uv if not present
brew install uv

# Install litert-lm CLI
uv tool install litert-lm

# Install Python API in the benchmark runner environment for native tool-call benchmarks
pip install litert-lm-api

# Add to PATH
export PATH="$HOME/.local/bin:$PATH"

# Import a model from HuggingFace
litert-lm import --from-huggingface-repo litert-community/gemma-4-E4B-it-litert-lm \
  gemma-4-E4B-it.litertlm gemma4-e4b

# Verify
litert-lm list
```

## Starting the server

```bash
ssh macstudio "export PATH=\"/Users/chanunc/.local/bin:\$PATH\" && \
  nohup litert-lm serve --api openai --host 0.0.0.0 --port 9379 --verbose \
  > /tmp/litert-lm.log 2>&1 &"
```

Stop:
```bash
ssh macstudio "pkill -f 'litert-lm serve'"
```

## Health check

No GET /v1/models — use a POST chat completion probe:

```bash
curl -s http://<MAC_STUDIO_IP>:9379/v1/chat/completions -X POST \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4-e4b","messages":[{"role":"user","content":"ping"}],"max_tokens":4,"temperature":0.0}'
```

## Tool-call benchmarks

Run both harness modes when evaluating LiteRT-LM:

```bash
# OpenAI HTTP shim: preserves compatibility with normal server benchmarks.
python3 scripts/bench/bench_api_tool_call.py \
  --mode openai-http \
  --base-url http://<MAC_STUDIO_IP>:9379/v1 \
  --model gemma4-e4b \
  --output docs/models/benchmarks/logs/gemma4-e4b-litert-lm/api-tool-test.json

# Native LiteRT-LM Python API: exercises the documented LiteRT-LM tool loop.
python3 scripts/bench/bench_api_tool_call.py \
  --mode litert-native \
  --native-model-path ~/.litert-lm/models/gemma4-e4b/model.litertlm \
  --native-backend cpu \
  --model gemma4-e4b \
  --output docs/models/benchmarks/logs/gemma4-e4b-litert-lm/native-tool-test.json
```

Native mode uses sandboxed Python tool functions and records actual function invocations. It does not produce OpenAI `finish_reason=tool_calls`, because LiteRT-LM's native API executes the tool loop internally and returns the final model response.

Native benchmark result on Mac Studio (2026-05-28): **5/5 single-call scenarios**, with 7.83 s file-read, 8.23 s command, 10.68 s search+read, 11.71 s list+read+write, and 22.01 s agentic-reasoning. The native config loop completed in 11.03 s with `read_file` + `write_file`. Raw log: [`../../models/benchmarks/logs/gemma4-e4b-litert-lm/native-tool-test.json`](../../models/benchmarks/logs/gemma4-e4b-litert-lm/native-tool-test.json).

## Performance (Mac Studio M3 Ultra 96 GB)

From `litert-lm benchmark` (official CLI):

| Metric | Value |
|:--|:--|
| Prefill | 71.5 tok/s |
| Decode | 13.85 tok/s |
| Init (cold) | 24.2 s |
| TTFT (512 tok) | 7.2 s |
| Backend | CPU / XNNPACK |
| Model size | 3.66 GB |
| Max context | ~3072 tokens (crashes at 4096) |

## Known limitations

- **GPU backend produces garbage** on Apple Silicon. The `gpu` backend (`gpu_artisan`) is designed for mobile GPUs / Google hardware, not Metal. Always use `cpu`.
- **No OpenAI HTTP `tools` support in serve mode.** The OpenAI handler drops `tools` and `tool_choice` from requests and never returns structured `tool_calls`. Native LiteRT-LM CLI/Python tool calling is separate and should be tested with `bench_api_tool_call.py --mode litert-native`.
- **No GET /v1/models.** Server only accepts POST.
- **Per-character SSE chunks.** Each streamed chunk contains a single character, not a token. Inflates chunk count relative to actual token count.
- **No `usage` in responses.** `prompt_tokens` and `completion_tokens` always absent.
- **Context limit ~3K.** Server crashes with `litert_lm_conversation_send_message failed` at 4096 input tokens.
- **Cold start ~24s.** Engine initializes on first request (XNNPACK delegate compilation).
- **Single concurrent request.** BaseHTTPServer — no batching, no concurrency.
- **XNNPACK cache warning.** Harmless: `in-memory cache is not enabled for this build`. Does not affect correctness.

## See also

- [LiteRT-LM GitHub](https://github.com/google-ai-edge/LiteRT-LM)
- [litert-community/gemma-4-E4B-it-litert-lm](https://huggingface.co/litert-community/gemma-4-E4B-it-litert-lm) — model card
- [`docs/models/per-model/model-summary-gemma.md`](../../models/per-model/model-summary-gemma.md) — Gemma family docs
