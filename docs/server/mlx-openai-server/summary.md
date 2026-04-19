# mlx-openai-server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Gemma 4 26B-A4B (single-model)](#gemma-4-26b-a4b-single-model)
- [Qwen3.5 27B 4-bit](#qwen35-27b-4-bit)
- [Compact Hermes 4.3 36B](#compact-hermes-43-36b)
- [Quick Test](#quick-test)
- [API Endpoints](#api-endpoints)
- [JANG Model Support](#jang-model-support)
- [Known Issues](#known-issues)

---

## Overview

[mlx-openai-server](https://github.com/cubist38/mlx-openai-server) is a FastAPI/Uvicorn server providing an OpenAI-compatible API for MLX models on Apple Silicon. It features trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, and process-isolated multi-model deployment.

| Property | Value |
|----------|-------|
| Version | 1.7.1 |
| Repository | [cubist38/mlx-openai-server](https://github.com/cubist38/mlx-openai-server) |
| Python | 3.11+ (requires Homebrew Python 3.12 on Mac Studio) |
| Framework | MLX + mlx-lm 0.31.x + Uvicorn/FastAPI |
| API formats | OpenAI-compatible `/v1/chat/completions`, `/v1/responses` |
| Model types | Text (lm), multimodal (vlm), image generation (Flux), embeddings, whisper |
| Model formats | MLX safetensors, JANG (via monkey-patch) |
| Install location | `~/mlx-openai-server-env/` on Mac Studio |

---

## 🏗️ Architecture

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
- **Reasoning parsers**: Built-in parsers for Qwen3.5, Qwen3, Hermes, Kimi K2, Gemma 4, and others. Emits `reasoning_content` in streaming chunks for think tokens.

---

## ⚙️ Installation

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

## 🚀 Usage

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
- Qwen3.5 27B 4-bit as a `multimodal` Qwen3.5-VL-style entry with `qwen3_vl`
- Qwen3-Coder-30B-A3B-Instruct with `qwen3_coder`
- Hermes 4 70B with `hermes`
- Hermes 4.3 36B as a Seed-OSS chat-only entry with a custom template
- Qwen3.5-VL 122B as a medium-confidence multimodal entry

Excluded there:
- Nemotron family, which this repo still routes to `vllm-mlx`
- Mistral Small 4 JANG, which is not currently supportable on this `mlx-openai-server` stack

### Gemma 4 26B-A4B (single-model)

Validated on 2026-04-17:
- Model: `mlx-community/gemma-4-26b-a4b-it-4bit`
- Launch shape: `model_type: multimodal`, `tool_call_parser: gemma4`, `reasoning_parser: gemma4`
- Reference file: [mlx-openai-server-gemma4.yaml](mlx-openai-server-gemma4.yaml)

```bash
~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-gemma4.yaml --no-log-file
```

Observed behavior on Mac Studio M3 Ultra (96 GB):
- Loads in ~5s via `mlx_vlm` multimodal handler (15 GB on disk, ~16 GB RSS at idle)
- `/v1/models` returns single entry `mlx-community/gemma-4-26b-a4b-it-4bit`
- Tool calling verified: `finish_reason: tool_calls`, structured `tool_calls[]` with JSON args
- Non-streaming: `reasoning_content` (thinking) cleanly separated from `content` (answer)
- Streaming: reasoning parser partially broken in 1.7.1 ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) — thinking tokens may appear in `content`; fixed on `main`
- `enable_thinking: false` has no effect in 1.7.1 ([#279](https://github.com/cubist38/mlx-openai-server/issues/279)) — fixed on `main`
- 256K context configured; sliding-window architecture keeps prefill fast at mid-range contexts

Generation benchmarks (3 runs, temperature 0.0, 150 max tokens, includes reasoning tokens):

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | 62.5 | 1,710 | 0.30 |
| 4K | 54.6 | 3,117 | 1.32 |
| 8K | 60.6 | 3,154 | 2.60 |
| 32K | 50.6 | 2,892 | 11.34 |
| 64K | 42.0 | 2,542 | 25.78 |
| 128K | 27.1 | 1,995 | 65.70 |

### Qwen3.6-35B-A3B 6-bit

Validated on 2026-04-18:
- Model: `mlx-community/Qwen3.6-35B-A3B-6bit` (~27 GB on disk at `~/.omlx/models/mlx-community/Qwen3.6-35B-A3B-6bit`)
- Launch shape: `model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`, `context_length: 131072`, `enable_auto_tool_choice: true`
- Reference file: [mlx-openai-server-qwen36-35b.yaml](mlx-openai-server-qwen36-35b.yaml)

```bash
ssh macstudio "nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-qwen36-35b.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &"
```

Observed behavior on Mac Studio M3 Ultra (96 GB):
- Loads in ~8s via `mlx_vlm` multimodal handler (~30 GB peak RSS at idle)
- `/v1/models` returns single entry `mlx-community/Qwen3.6-35B-A3B-6bit`
- Non-streaming: `reasoning_content` (always-on `<think>`) cleanly separated from `content` (final answer)
- Streaming: `reasoning_content` and `content` arrive in separate SSE deltas — **the Gemma-4 streaming-leak bug ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) does not surface with the `qwen3_vl` parser here**
- Vision through API verified: `image_url` content blocks (data URL with base64 PNG) work end-to-end; a 64×64 solid-red PNG was correctly identified as "Red". `https://`-hosted images are also accepted but currently fetched through the server, so client-reachable URLs are required
- 131K context configured (conservative; Qwen3.6 native is 262K extensible to ~1M with YaRN). Long-context generation stays usable: 35.6 tok/s at 128K vs 52.5 tok/s at 512
- Server overhead at 512 ≈ 4% vs standalone (52.5 vs 54.7 tok/s), within the JANG-class band already seen on this server
- `enable_thinking=false` has no effect (same hookup gap as Gemma 4 [#279](https://github.com/cubist38/mlx-openai-server/issues/279)); thinking cannot currently be suppressed via API
- MTP/multi-token-prediction speculative decoding is not exposed — `mlx-openai-server` issues [#177](https://github.com/cubist38/mlx-openai-server/issues/177) and [#204](https://github.com/cubist38/mlx-openai-server/issues/204) remain open. Use `waybarrios/vllm-mlx` post-PR [#278](https://github.com/waybarrios/vllm-mlx/pull/278) if MTP-through-API is required
- `oMLX` rejected for Qwen3.6 today: open issues [#812](https://github.com/jundot/omlx/issues/812) (tool calling stops), [#819](https://github.com/jundot/omlx/issues/819) (lmstudio 6bit fails to load), [#827](https://github.com/jundot/omlx/issues/827) (DFlash load fail), [#841](https://github.com/jundot/omlx/issues/841) (>127K silent crash)

Through-server benchmarks (3 runs, temperature 0.0, 150 max tokens, includes reasoning tokens):

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | 52.5 | 1,401 | 0.34 |
| 4K | 53.0 | 2,237 | 1.64 |
| 8K | 51.3 | 2,197 | 3.32 |
| 32K | 46.3 | 1,798 | 16.22 |
| 64K | 40.3 | 1,408 | 41.40 |
| 128K | 35.6 | 927 | 125.73 |

Full results and methodology: [model-benchmark-api-server.md](../../models/model-benchmark-api-server.md). Raw JSON: [qwen36-35b-server-benchmark.json](qwen36-35b-server-benchmark.json).

### Qwen3.5 27B 4-bit

Validated on 2026-03-30:
- Model: `mlx-community/Qwen3.5-27B-4bit`
- Launch shape: `model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`
- Reference file:
  - [mlx-openai-server-qwen35-27b.yaml](/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/server/mlx-openai-server/mlx-openai-server-qwen35-27b.yaml)

Observed behavior on Mac Studio M3 Ultra:
- The repo name does not include `VL`, but the upstream MLX conversion is a multimodal Qwen3.5 build and must be served as `model_type: multimodal`
- Loads cleanly on `mlx-openai-server` and answers text-only chat requests
- `qwen3_vl` parsing separates thinking into `message.reasoning_content` while leaving the final answer in `message.content`
- Short text probes validated clean startup, `GET /v1/models`, and successful `/v1/chat/completions` responses on port `8000`

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

### Qwen3.5-VL CRACK Single-Model YAML

Validated on 2026-03-30:
- Model: `dealignai/Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK`
- Reference file:
  - [mlx-openai-server-crack-vl.yaml](/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/server/mlx-openai-server/mlx-openai-server-crack-vl.yaml)

Observed behavior on Mac Studio M3 Ultra:
- Loads cleanly as `model_type: multimodal` on `mlx-openai-server`
- Basic text-only chat responded in roughly 3 seconds during validation
- The model is currently a better live fit on this stack than compact Hermes 4.3
- Text-only chat can still surface visible `<think>` output, so clients may need parser handling or response trimming if they expect plain final answers

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

## 💬 Quick Test

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen3.5-27B-4bit",
    "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
    "max_tokens": 128
  }' | python3 -m json.tool
```

Current live roster on the Mac Studio:
- `mlx-community/Qwen3.6-35B-A3B-6bit` (Qwen3.6-only mode, switched 2026-04-18)

---

## 🔌 API Endpoints

| Endpoint | Model Types | Purpose |
|----------|------------|---------|
| `/v1/chat/completions` | lm, multimodal | Chat completions (streaming + non-streaming) |
| `/v1/responses` | lm, multimodal | OpenAI Responses API |
| `/v1/images/generations` | image-generation | Image creation (Flux) |
| `/v1/images/edits` | image-edit | Image modification |
| `/v1/embeddings` | embeddings | Text vectors |
| `/v1/audio/transcriptions` | whisper | Speech-to-text |
| `GET /v1/models` | all | List available models |

**No Anthropic-format API support.** Clients must use OpenAI-compatible mode. Claude Code requires `claude-code-router` for Anthropic-to-OpenAI translation.

---

## 🧠 JANG Model Support

Not supported natively. Requires a `.pth`-based patch in the venv that intercepts `mlx_lm.load()` at Python startup — works in `multiprocessing.spawn` subprocesses and survives pip upgrades. Supports simultaneous JANG + non-JANG multi-model deployment. See [JANG Patch](jang-patch.md) for installation, multi-model config, and details.

---

## ⚠️ Known Issues

1. **64K context performance drop**: 15% overhead vs standalone at 64K context, compared to vllm-mlx's 3%. The overhead likely comes from the inference worker queue and reasoning parser processing.
2. **No Anthropic-format API**: Clients expecting Anthropic-format requests (Claude Code) need a translation layer like `claude-code-router`.
3. **Single-request concurrency**: The InferenceWorker processes one request at a time. Multiple simultaneous clients will queue.
4. **JANG not native**: Requires `.pth`-based patch in the venv (`jang_patch.pth` + `jang_mlx_patch.py`). Survives pip upgrades but must be reinstalled if the venv is recreated.
5. **Streaming format**: Uses `reasoning_content` field for think tokens instead of `content`. Benchmark scripts and clients expecting `content` or `reasoning` fields will miss these tokens.
6. **Separate venv**: Cannot share the vllm-mlx or oMLX venvs due to dependency conflicts.
7. **Tool call arguments as string**: OpenAI API clients (OpenClaw, etc.) send `tool_call.arguments` as a JSON string, but Qwen3.5's chat template expects a dict — causes `"Can only get item pairs from a mapping"` error. Fixed by `scripts/patch_mlx_openai_tool_args.py` (see [Maintenance](maintenance.md#tool-call-arguments-patch)). Must re-apply after upgrades.
8. **Nemotron family incompatible**: No chat template fallback, no reasoning/tool parsers for Nemotron. Use vllm-mlx instead. See [Nemotron Server Compatibility](../../models/model-summary.md#nemotron-server-compatibility) for details.
9. **Mistral Small 4 is not currently supported here**: Upstream `mlx-lm` does not yet ship native `mistral4` support, and this repo no longer carries a local patch path. Use `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`, or `vLLM` for Mistral's official self-deployment path.
10. **Gemma 4 streaming reasoning leak (1.7.1):** Bug [#280](https://github.com/cubist38/mlx-openai-server/issues/280) — reasoning parser not applied in the streaming path; thinking tokens bleed into `content` chunks. Non-streaming is clean. Fix is on `main`; awaiting 1.7.2 release.
11. **Gemma 4 `enable_thinking` ignored (1.7.1):** Bug [#279](https://github.com/cubist38/mlx-openai-server/issues/279) — `chat_template_kwargs.enable_thinking=false` has no effect. Cannot suppress thinking via API in 1.7.1. Fixed on `main`.
12. **Seed-OSS models need extra wiring**: Compact Hermes 4.3 36B is based on `seed_oss`, not the older Hermes tokenizer family. On this `mlx-openai-server` build it needs an explicit Seed-OSS chat template and currently has no validated tool parser path.
13. **Qwen 3.5/3.6 empty `<think>` cache miss (template bug, applies engine-wide):** Shipped Jinja templates emit `<think>\n\n</think>\n\n` for every prior assistant turn even when `reasoning_content` is empty, drifting the prompt prefix and breaking KV-cache reuse — worst after tool use ([r/LocalLLaMA 1sg076h](https://www.reddit.com/r/LocalLLaMA/comments/1sg076h/)). Patched on Mac Studio 2026-04-19 by adding `and reasoning_content` to the `loop.index0 > ns.last_query_index` guard in 6 model templates. See [maintenance.md#qwen-empty-think-template-patch](maintenance.md#qwen-empty-think-template-patch). **Must be re-applied on any model re-download.**
14. **`chat_template_kwargs` must be nested, not top-level:** The server only reads `request.chat_template_kwargs.<key>`. Sending `preserve_thinking: true` at the request root is silently dropped (same plumbing class as #11). Clients must send `{"chat_template_kwargs": {"preserve_thinking": true, "enable_thinking": true}}`. Verified at `app/handler/mlx_lm.py:1010-1012` → `app/models/mlx_lm.py:136-142` (main and v1.7.1 identical).

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-qwen36-35b.yaml` | Qwen3.6-only single-model config (current live) |
| `~/mlx-openai-server-gemma4.yaml` | Gemma-4-only single-model config |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model config (Qwen3-Coder-Next + Qwen3.6-35B) |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |

Full file list including JANG patch files: [JANG Patch](jang-patch.md#files-on-mac-studio)
