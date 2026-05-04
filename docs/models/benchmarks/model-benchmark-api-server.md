# Benchmark: API Server Inference

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25-27, 2026 (Qwen3.5 models) · April 17, 2026 (Gemma 4).

## 🧪 Method

Streaming `/v1/chat/completions` requests via Python `urllib`, parsing SSE `data:` chunks to measure per-token timing. Each test generates 50 tokens at temperature 0.0 across context lengths 512, 8K, 32K, 64K.

**Servers tested:**
- **oMLX** v0.2.20 (Homebrew + AlexTzk JANG fork) -- production server with scheduler, paged KV cache, model hot-swapping
- **mlx-lm.server** v0.31.2 (built-in to mlx-lm) -- thin `ThreadingHTTPServer` wrapper around `stream_generate()`
- **vllm-mlx** v0.2.6 (pip from [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx)) -- vLLM port for Apple Silicon with Uvicorn/FastAPI
- **mlx-openai-server** v1.7.0 (pip from [cubist38/mlx-openai-server](https://github.com/cubist38/mlx-openai-server)) -- FastAPI/Uvicorn server with trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, process isolation for multi-model

JANG model support was added to mlx-lm.server, vllm-mlx, and mlx-openai-server via a ~15-line monkey-patch that intercepts `mlx_lm.load()` / `mlx_lm.utils.load()`, detects JANG model paths (via `jang_tools.loader.is_jang_model()`), and delegates to `jang_tools.load_jang_model()`. All loaders return the identical `mlx_lm.models.qwen3_5_moe.Model` class, so no further changes are needed.

**Unsupported architectures (deployed via patches):** `mlx-community/Ling-2.6-flash-mlx-6bit` uses `bailing_hybrid`, not yet in mlx-lm 0.31.3. Deployed by side-loading `mlx_lm/models/bailing_hybrid.py` from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227) plus two server-side workarounds for thread-bound Metal-kernel state — see [Ling-2.6-flash](#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid) section below.

---

## 🤖 Qwen3.5-35B-A3B-4bit (Standard MLX Quantization)

Model: `mlx-community/Qwen3.5-35B-A3B-4bit`

### Generation Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-lm.server | oMLX |
|---------|-----------|---------|---------------|------|
| 512 | **109.7** 🏆 | 106.4 🥈 | 100.9 | -- |
| 8K | **103.0** 🏆 | 100.1 🥈 | 94.8 | -- |
| 32K | **90.3** 🏆 | 86.5 🥈 | 80.1 | 59.9 |
| 64K | **76.3** 🏆 | 74.3 🥈 | 66.4 | 49.0 |

### Prefill Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-lm.server | oMLX |
|---------|-----------|---------|---------------|------|
| 512 | **1770.1** 🏆 | 692.8 | 776.4 🥈 | -- |
| 8K | 2311.6 | **2489.7** 🏆 | 2432.7 🥈 | -- |
| 32K | 1858.8 | **2060.0** 🏆 | 2034.2 🥈 | 366.8 |
| 64K | 1429.6 | **1609.1** 🏆 | 1592.8 🥈 | -- |

### Time to First Token (seconds)

| Context | vllm-mlx | mlx-lm.server | oMLX |
|---------|---------|---------------|------|
| 512 | 0.74 🥈 | **0.66** 🏆 | -- |
| 8K | **3.29** 🏆 | 3.37 🥈 | -- |
| 32K | **15.91** 🏆 | 16.11 🥈 | -- |
| 64K | **40.73** 🏆 | 41.14 🥈 | -- |

---

## 🤖 Qwen3.5-35B-A3B JANG 4K

Model: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`

### Generation Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|-----------|---------|-------------------|---------------|------|
| 512 | **103.6** 🏆 | 100.7 🥈 | 99.4 | 96.3 | 80.8 |
| 8K | **98.0** 🏆 | 95.6 🥈 | 93.9 | 90.7 | 76.2 |
| 16K | -- | -- | -- | -- | 67.8 |
| 32K | **86.5** 🏆 | 83.8 🥈 | 81.3 | 77.6 | 59.9 |
| 64K | **73.9** 🏆 | 71.6 🥈 | 62.8 | 65.1 | 49.0 |
| 128K | -- | -- | -- | -- | 33.8 |

### Prefill Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|-----------|---------|-------------------|---------------|------|
| 512 | **1688.5** 🏆 | 831.0 | 1164.0 🥈 | 824.1 | 310.3 |
| 8K | 2456.8 | **2643.9** 🏆 | 2632.0 🥈 | 2582.2 | 430.7 |
| 16K | -- | -- | -- | -- | 378.5 |
| 32K | 1952.6 | **2164.7** 🏆 | 2160.0 🥈 | 2137.5 | 366.8 |
| 64K | 1485.6 | **1668.4** 🏆 | 1660.0 🥈 | 1657.1 | 341.5 |
| 128K | -- | -- | -- | -- | 295.4 |

### Time to First Token (seconds)

| Context | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|---------|-------------------|---------------|------|
| 512 | 0.56 🥈 | **0.44** 🏆 | 0.62 | 1.65 |
| 8K | **3.10** 🏆 | 3.11 🥈 | 3.17 | 19.02 |
| 32K | **15.15** 🏆 | 15.17 🥈 | 15.33 | 62.76 |
| 64K | **39.30** 🏆 | 39.47 🥈 | 39.55 | 89.48 |

oMLX 16K/128K and 4-bit results from [omlx.ai leaderboard](https://omlx.ai) (March 24, 2026). JANG 512/8K and TTFT from local benchmarks (March 27, 2026).

---

## ⚖️ Server Overhead Comparison

Percentage slower than raw standalone at each context length:

### Generation Speed Overhead

| Context | vllm-mlx (4bit) | mlx-lm (4bit) | oMLX (4bit) | vllm-mlx (JANG) | mlx-openai (JANG) | mlx-lm (JANG) | oMLX (JANG) |
|---------|----------------|---------------|-------------|-----------------|-------------------|---------------|-------------|
| 512 | **-3%** 🏆 | -8% 🥈 | -- | **-2%** 🏆 | -4% 🥈 | -7% | -22% |
| 8K | **-3%** 🏆 | -8% 🥈 | -- | **-2%** 🏆 | -4% 🥈 | -7% | -22% |
| 32K | **-4%** 🏆 | -11% 🥈 | -34% | **-3%** 🏆 | -6% 🥈 | -10% | -31% |
| 64K | **-3%** 🏆 | -13% 🥈 | -36% | **-3%** 🏆 | -12% 🥈 | -15% | -34% |

### Prefill Speed Overhead

| Context | vllm-mlx | mlx-lm.server | oMLX |
|---------|---------|---------------|------|
| 32K | **+11%** 🏆 | +10% 🥈 | -80% |
| 64K | **+13%** 🏆 | +12% 🥈 | -- |

Note: vllm-mlx and mlx-lm.server show *higher* prefill than standalone at longer contexts due to measurement differences (TTFT includes HTTP overhead but server may chunk prefill differently).

---

## 🔍 Key Findings

### 1. vllm-mlx is the fastest server

Only 3-4% slower than raw standalone across all context lengths. At 32K with JANG: 83.8 t/s vs 86.5 standalone.

### 2. mlx-openai-server is close but drops at 64K

4-6% overhead at short-to-medium contexts, competitive with vllm-mlx. However, at 64K context it drops to 62.8 t/s (-15% vs standalone), worse than both vllm-mlx (71.6 t/s, -3%) and mlx-lm.server (65.1 t/s, -12%). The overhead likely comes from its inference worker queue and reasoning parser processing. TTFT is slightly faster than vllm-mlx at 512 tokens (0.44s vs 0.56s). Its trie-based prompt caching, speculative decoding, and Qwen3.5 reasoning parser are advantages for interactive use that don't show in single-request benchmarks.

### 3. mlx-lm.server is a close third

7-13% overhead, increasing with context length. Simpler architecture (no async, no batching) but still much faster than oMLX.

### 4. oMLX has 30-36% generation overhead

At 32K: 59.9 t/s vs 86.5 standalone (-31%). The overhead comes from:
- Paged KV cache management and scheduler loop
- Token streaming and stop condition checking
- Prefill chunking (explains the 80% prefill overhead: 366.8 vs 1952.6 t/s)

### 5. JANG performs identically to standard 4-bit

Within 2-5% across all servers and context lengths. JANG's adaptive mixed-precision does not add measurable inference overhead once the model is loaded.

### 6. JANG monkey-patch works on all servers

A ~15-line wrapper script intercepts `mlx_lm.load()` / `mlx_lm.utils.load()` and delegates JANG paths to `jang_tools.load_jang_model()`. No server code modifications needed. All servers loaded JANG models in <3 seconds via mmap.

---

## Osaurus Qwen3.6-35B-A3B JANGTQ4 on vmlx

Model: `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4`  
Server: `vmlx` (MLX Studio bundled Python), main port 8000  
Tested on **Mac Studio M3 Ultra (96 GB)** — May 1, 2026.

Raw JSON: [`qwen36-35b-a3b-jangtq4-osaurus/api-server-vmlx.json`](qwen36-35b-a3b-jangtq4-osaurus/api-server-vmlx.json)

### Generation Speed (tok/s)

| Context | vmlx |
|:--|--:|
| 512 | 64.9 |
| 4K | 64.8 |
| 8K | 64.0 |
| 32K | 58.8 |
| 64K | 52.6 |

### Prefill Speed (tok/s)

| Context | vmlx |
|:--|--:|
| 512 | 359.7 |
| 4K | 365.1 |
| 8K | 362.0 |
| 32K | 346.3 |
| 64K | 325.7 |

### Time to First Token

| Context | TTFT |
|:--|--:|
| 512 | 1.49 s |
| 4K | 11.29 s |
| 8K | 22.70 s |
| 32K | 94.71 s |
| 64K | 201.32 s |

Notes:
- Startup logs confirmed native JANGTQ VLM fast path: `load_jangtq_vlm`, 120 TurboQuant modules replaced, and no fallback warning.
- Decode is stable around 64 tok/s through 8K and 52.6 tok/s at 64K.
- Agent-loop latency is dominated by prefill: OpenCode sends ~11K tokens on first turn and grows to ~42K tokens for the Hacker News scenario.

---

---

## Gemma 4 26B-A4B-it (4-bit)

Model: `mlx-community/gemma-4-26b-a4b-it-4bit`  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 17, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens count both `reasoning_content` (thinking) and `content` (answer) phases — Gemma 4 always thinks before answering. 512 warm values shown (run 1 was a cold-start: 59.4 tok/s gen / 28 tok/s prefill / 18.7s TTFT).

**Server:** mlx-openai-server v1.7.1 (mlx-lm 0.31.2, mlx-vlm 0.4.4) — only server tested; vllm-mlx has a known reasoning parser bug ([#38855](https://github.com/vllm-project/vllm/issues/38855)) and oMLX lacks the `gemma4` parser.

### Generation Speed (tok/s)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | **62.5** |
| 4K | 54.6 |
| 8K | **60.6** |
| 32K | 50.6 |
| 64K | 42.0 |
| 128K | 27.1 |

### Prefill Speed (tok/s)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | 1,710 |
| 4K | 3,117 |
| 8K | **3,154** |
| 32K | 2,892 |
| 64K | 2,542 |
| 128K | 1,995 |

### Time to First Token (seconds)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | 0.30 |
| 4K | 1.32 |
| 8K | 2.60 |
| 32K | 11.34 |
| 64K | 25.78 |
| 128K | 65.70 |

**Notes:**
- Gen speed is stable across runs (±0.1 tok/s at 32K–128K) — minimal variance due to MoE routing determinism at temperature 0.0
- 8K slightly faster than 4K in generation — likely GPU utilization sweet spot for this sliding-window MoE
- 128K TTFT (65.7s) is dominated by prefill time; generation itself is 27.1 tok/s once started

---

## Qwen3.6-35B-A3B (6-bit)

Model: `mlx-community/Qwen3.6-35B-A3B-6bit`  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 18, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens count both `reasoning_content` (thinking) and `content` (answer) phases — Qwen3.6 always thinks before answering. Warm values shown (run 1 to run 3 differ only in TTFT for ctx=512: 0.58s cold vs 0.34s warm; gen tok/s identical to ±0.3 across all runs).

**Server:** mlx-openai-server v1.7.1 (`model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`, `context_length: 131072`). Reference YAML: [mlx-openai-server-qwen36-35b.yaml](../../servers/mlx-openai-server/mlx-openai-server-qwen36-35b.yaml). Raw JSON: [api-server-mlx-openai-server.json](qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json).

> Why mlx-openai-server only: `oMLX` has multiple open Qwen3.6 issues ([#812](https://github.com/jundot/omlx/issues/812), [#819](https://github.com/jundot/omlx/issues/819), [#827](https://github.com/jundot/omlx/issues/827), [#841](https://github.com/jundot/omlx/issues/841)); `vllm-mlx` post-PR [#278](https://github.com/waybarrios/vllm-mlx/pull/278) is the only alternative that exposes MTP through API but inherits the upstream `mlx-lm` hybrid-cache bug ([#1162](https://github.com/ml-explore/mlx-lm/issues/1162)). Not run here.

### Generation Speed (tok/s)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | **52.5** |
| 4K | **53.0** |
| 8K | 51.3 |
| 32K | 46.3 |
| 64K | 40.3 |
| 128K | 35.6 |

### Prefill Speed (tok/s)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | 1,401 |
| 4K | **2,237** |
| 8K | 2,197 |
| 32K | 1,798 |
| 64K | 1,408 |
| 128K | 927 |

### Time to First Token (seconds)

| Context | mlx-openai-server |
|:--------|:-----------------:|
| 512 | 0.34 |
| 4K | 1.64 |
| 8K | 3.32 |
| 32K | 16.22 |
| 64K | 41.40 |
| 128K | 125.73 |

**Notes:**
- Server overhead at 512 ≈ 4% gen vs the standalone clean reading of 54.7 tok/s (`model-benchmark-standalone.md:101`); within the 4-15% band already seen for Qwen3.5-JANG on this server
- Streaming reasoning split is **clean** for Qwen3.6 with the `qwen3_vl` parser — `reasoning_content` and `content` arrive in separate SSE deltas. The Gemma 4 streaming-leak bug ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) does not surface here
- Prompt-token counts reported by the server are slightly under the requested context (e.g. ctx=131072 → prompt_tokens=116,518) because the seed-string filler tokenises shorter than 1 char-per-quarter-token in spots — the reported tok/s is computed against the actual `prompt_tokens` from `usage`
- Vision through API verified: `image_url` content blocks (data:image/png;base64) accepted; 64×64 solid-red PNG correctly identified as "Red"
- Hybrid Gated DeltaNet pays off at long context: 128K gen at 35.6 tok/s is **31% faster** than Gemma 4's 27.1 tok/s at the same context, despite Qwen3.6 activating ~3B params vs Gemma 4's ~4B
- `enable_thinking=false` not testable here — same parser-hookup gap as Gemma 4 ([#279](https://github.com/cubist38/mlx-openai-server/issues/279)); `<think>` is always emitted (counted in gen tokens above)

---

## Qwen3.6-35B-A3B (4-bit) on dflash-mlx

Model: `mlx-community/Qwen3.6-35B-A3B-4bit` paired with `z-lab/Qwen3.6-35B-A3B-DFlash` drafter (DFlash speculative decoding via block-diffusion).
Tested on **Mac Studio M3 Ultra (96 GB)** — April 30, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs each. Note the lower max_tokens cap vs the 6-bit row above (50 vs 150) — these are decode-throughput numbers; for full benchmark detail see [agent-bench-dflash-mlx.json](qwen36-35b-a3b-4bit/agent-bench-dflash-mlx.json).

**Server:** dflash-mlx 0.1.4.1 (`pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'` + 3 local patches — see [`docs/servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md)). Wraps `mlx_lm.server`. `--draft-model` required for Qwen3.6 (built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family). Raw JSON: [api-server-dflash-mlx.json](qwen36-35b-a3b-4bit/api-server-dflash-mlx.json).

### Generation Speed (tok/s)

| Context | dflash-mlx | mlx-openai-server (6-bit) |
|:--------|:----------:|:--------------------------:|
| 512 | **89.5** | 52.5 |
| 4K | 88.4 | 53.0 |
| 8K | 87.0 | 51.3 |
| 32K | 74.1 | 46.3 |

### Prefill Speed (tok/s)

| Context | dflash-mlx | mlx-openai-server (6-bit) |
|:--------|:----------:|:--------------------------:|
| 512 | 1,366 | 1,401 |
| 4K | **1,812** | 2,237 |
| 8K | 1,524 | 2,197 |
| 32K | 837 | 1,798 |

### Time to First Token (seconds)

| Context | dflash-mlx | mlx-openai-server (6-bit) |
|:--------|:----------:|:--------------------------:|
| 512 | 0.39 | 0.34 |
| 4K | 2.27 | 1.64 |
| 8K | 5.40 | 3.32 |
| 32K | 39.2 | 16.22 |

**Notes:**
- DFlash drafter accepts ~87% of drafted tokens on Qwen3.6-35B-A3B → effective decode is **1.7× faster** than the 6-bit autoregressive baseline at 512 ctx and **1.6× faster** at 32K. The win is decode-bound; prefill is comparable or slower (4-bit gets a small kernel benefit at 4K but the 32K prefill is 2.1× slower than 6-bit on mlx-openai-server, likely due to draft-model prefill overlap).
- TTFT scales worse with context than mlx-openai-server because dflash-mlx pays both target-prefill and draft-prefill costs. At 32K the TTFT is 2.4× higher.
- Bench script: [`bench_api_server.py`](../../../scripts/bench/bench_api_server.py) — note: requires the `delta.reasoning` recognition fix landed 2026-04-30 (mlx-lm naming differs from `delta.reasoning_content` used by other servers).
- Streaming reasoning leaves through `delta.reasoning` (not `reasoning_content`) — informational; `bench_api_server.py` already handles both.

---

## Qwen3.5-4B + DFlash drafter — bstnxbt vs Aryagm (cross-fork comparison, 2026-04-30)

Same target (`Qwen/Qwen3.5-4B`) and drafter (`z-lab/Qwen3.5-4B-DFlash`) on both DFlash-MLX forks, benched against `bench_api_server.py` (50 max tokens, temperature 0.0, 1 warmup + 2 measured per context). Production (Ling on `vllm-mlx :8000`) was left running throughout — the 4B target+drafter occupies <10 GB unified memory.

**Aryagm fork** (`https://github.com/Aryagm/dflash-mlx`) — `dflash-mlx-openai-server`, custom HTTPServer, `tools[]` silently dropped (verified — `prompt_tokens=24` regardless of catalog). Adapter system limited to `qwen3` and `qwen3_5` model_types; **rejects `qwen3_5_moe`** (Qwen3.6-35B-A3B-4bit fails with `NotImplementedError: Unsupported MLX DFlash target model_type='qwen3_5_moe'`). Default verify mode `stream`, no `--temp` / `--top-p`. Raw JSON: [`api-server-aryagm.json`](qwen35-4b-dflash/api-server-aryagm.json).

**bstnxbt fork** (`https://github.com/bstnxbt/dflash-mlx`) 0.1.4.1 — `dflash-serve`, wraps `mlx_lm.server`. Full `tools[]` / `temp` / `top_p` / sampling controls. Requires three local patches against upstream packages (see [`docs/servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md)). Raw JSON: [`api-server-bstnxbt.json`](qwen35-4b-dflash/api-server-bstnxbt.json).

### Generation Speed (tok/s)

| Context | Aryagm | bstnxbt | bstnxbt advantage |
|:--------|:------:|:-------:|:------:|
| 512 | 34.7 | **67.0** | **1.93×** |
| 4K | 36.1 | **66.4** | **1.84×** |
| 8K | 24.3 | **65.5** | **2.69×** |
| 32K | 10.8 | **59.0** | **5.5×** |

### Prefill Speed (tok/s)

| Context | Aryagm | bstnxbt |
|:--------|:------:|:-------:|
| 512 | **1,553** | 1,277 |
| 4K | **1,740** | 1,664 |
| 8K | **1,631** | 1,462 |
| 32K | **1,154** | 790 |

### Time to First Token (seconds)

| Context | Aryagm | bstnxbt |
|:--------|:------:|:-------:|
| 512 | **0.35** | 0.42 |
| 4K | **2.37** | 2.48 |
| 8K | **5.04** | 5.62 |
| 32K | **28.4** | 41.5 |

**Findings:**
- **bstnxbt sustains 1.8-5.5× faster decode** at every context length on the same target+drafter pair. Most dramatic at 32K (5.5×) where the drafter's speculative budget compounds.
- **Aryagm has slightly faster prefill** (1,154 vs 790 tok/s @ 32K) and faster TTFT (28.4 vs 41.5 s @ 32K). Trade-off: Aryagm hits first token sooner but generates much slower thereafter.
- The two CLIs expose different speculation knobs (Aryagm's `--max-speculative-tokens` / `--verify-mode` vs bstnxbt's `--block-tokens`). Defaults were used in both runs — the gap may narrow with tuning, but the Aryagm decode-rate fall-off across context is the dominant signal.
- **Tool-calling capability splits decisively:** Aryagm 0.1.x drops `tools[]` entirely; bstnxbt 0.1.4.1 with `mlx_lm.server` wrap exposes full OpenAI tool surface. For agent workloads only bstnxbt is currently viable.
- **Model-type coverage:** Aryagm only supports `qwen3` and `qwen3_5` adapters → rejects `qwen3_5_moe` (Qwen3.6-35B-A3B-4bit). bstnxbt accepts any model `mlx_lm.utils.load` can load.

For the **production-relevant Qwen3.6-35B-A3B-4bit + DFlash** pair, only bstnxbt has been benched — see [Qwen3.6-35B-A3B (4-bit) on dflash-mlx](#qwen36-35b-a3b-4-bit-on-dflash-mlx) above.

---

## Qwen3.5-122B-A10B JANG 2S @ 128K

Model: `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S` (122B MoE, ~10B active, JANG 2S ≈2.1-bit average)  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 18, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs at ctx=131,072. Same filler-text generator as the Qwen3.6 / Gemma 4 rows above.

**Server:** vllm-mlx v0.2.6 launched via `~/run_vllm_jang.py serve` wrapper (the JANG monkey-patch path). Single-model. Reference: `CLAUDE.md` "Common Commands" section. Raw JSON: [api-server-vllm-mlx-128k.json](qwen35-122b-jang2s/api-server-vllm-mlx-128k.json).

| Run | TTFT (s) | Prefill (tok/s) | Gen (tok/s) | Tokens generated |
|----:|---------:|----------------:|------------:|-----------------:|
| 1 | 324.17 | 404 | 34.42 | 150 |
| 2 | 323.85 | 405 | 34.60 | 150 |
| 3 | 323.83 | 405 | 34.45 | 150 |
| **median** | **323.85** | **405** | **34.45** | 150 |

**Notes:**
- vllm-mlx-via-JANG-wrapper does **not** populate `usage.prompt_tokens` in streaming chunks (always `0`), so the prefill rate is computed against the requested `ctx_len=131,072`. The same filler text tokenises to **116,516** tokens on the native Qwen3-Coder-Next path below — so the apples-to-apples prefill is closer to **360 tok/s** if normalised to the actual prompt count
- Mode is `Simple (maximum throughput)` per server log — no paged cache, no prefix cache, no kv-cache quantization. These could be enabled to trade quality vs throughput
- JANG's 2.1-bit average weight format adds a per-token dequantization cost in prefill; this is the dominant reason the 122B JANG prefill at 128K (405 t/s) is slower than the dense 80B Coder-Next at 128K (736 t/s) on the same vllm-mlx
- 34.4 tok/s gen is competitive with Qwen3.6 (35.6) at the same context, and beats Gemma 4 (27.1)
- mlx-openai-server was not tested for this model at 128K — its JANG path uses the same `.pth` patch but the server's prefill-batching profile on a 122B model would be its own benchmark

---

## Qwen3-Coder-Next 6-bit @ 128K

Model: `mlx-community/Qwen3-Coder-Next-6bit` (dense 80B, hybrid Gated DeltaNet — 12 of 48 layers carry KV cache)  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 18, 2026.

**Method:** Same streaming SSE methodology as above. 3 runs at ctx=131,072, max_tokens=150, temperature 0.0.

**Server:** vllm-mlx v0.2.6 launched directly via `~/vllm-mlx-env/bin/vllm-mlx serve` (no JANG wrapper). Single-model. Mode: `Simple (maximum throughput)`. Raw JSON: [api-server-vllm-mlx-128k.json](qwen3-coder-next-6bit/api-server-vllm-mlx-128k.json).

| Run | TTFT (s) | Prefill (tok/s) | Gen (tok/s) | prompt_tokens | gen tokens |
|----:|---------:|----------------:|------------:|--------------:|-----------:|
| 1 | 159.26 | 732 | 44.21 | 116,516 | 146 |
| 2 | 158.43 | 736 | 44.02 | 116,516 | 146 |
| 3 | 158.40 | 736 | 44.21 | 116,516 | 146 |
| **median** | **158.43** | **736** | **44.21** | 116,516 | 146 |

**Notes:**
- Run-to-run variance is essentially zero (TTFT ±0.4s, gen ±0.1 tok/s) — the cold/warm distinction does not matter at this prefill cost
- vllm-mlx native (non-JANG) path **does** populate `usage.prompt_tokens` in streaming chunks; numbers above use that as the prefill denominator
- Generation speed at 128K (44.2 tok/s) is the **highest of any model benchmarked at 128K** in this repo — beats Qwen3.6 (35.6), Qwen3.5-122B JANG 2S (34.5), Gemma 4 (27.1)
- Prefill at 128K (736 t/s) is also the fastest at this context
- 60 GB weights + ~6 GB hybrid KV cache @ 128K fits comfortably in 96 GB unified memory
- Qwen3-Coder-Next has no thinking mode by default — gen tokens are pure `content`, not `reasoning_content`

---

## Qwen3.6-27B JANG 4M (Dense + VL)

Model: `JANGQ-AI/Qwen3.6-27B-JANG_4M` (dense 27.3B, Qwen3.6 hybrid 48 Gated DeltaNet + 16 full-attention, ViT vision encoder, JANG mixed 4/8-bit ≈4.45 bits/param, 17.5 GB on disk)
Tested on **Mac Studio M3 Ultra (96 GB)** — April 23, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 cold + 2 warm runs per context. Filler-token padding via `Hello world. ` repetition. Vision tower not exercised (vllm-mlx loads as `MLLM=False`). Raw JSON: [api-server-vllm-mlx.json](qwen36-27b-jang4m/api-server-vllm-mlx.json). Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py).

**Server:** vllm-mlx v0.2.6 via `~/run_vllm_jang.py` wrapper with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`. JANG load: 2.8s mmap (instant). `mlx-lm` 0.31.1, `jang-tools` 2.2.0.

### Generation Speed (tok/s)

| Context | vllm-mlx (JANG wrapper) |
|:--------|:-----------------------:|
| 512 | **36.5** |
| 4K | 35.8 |
| 8K | 34.6 |
| 32K | 30.9 |
| 64K | 27.0 |

### Prefill Speed (tok/s)

| Context | vllm-mlx (JANG wrapper) |
|:--------|:-----------------------:|
| 512 | 311 |
| 4K | **347** |
| 8K | 345 |
| 32K | 314 |
| 64K | 274 |

### Time to First Token (seconds)

| Context | vllm-mlx (JANG wrapper) |
|:--------|:-----------------------:|
| 512 | 1.72 |
| 4K | 11.89 |
| 8K | 23.82 |
| 32K | 104.45 |
| 64K | 239.58 |

**Notes:**
- vllm-mlx + this model returns `usage.prompt_tokens=0` for both streaming and non-streaming responses; prefill rates above are computed against the actual chat-templated token counts measured locally with the model's own tokenizer (536 / 4,121 / 8,216 / 32,792 / 65,561 tokens for the 5 contexts respectively). The `notes` field in the raw JSON records this.
- 128K not tested — extrapolating from the 32K → 64K curve (TTFT 2.3× per context doubling), 128K TTFT would land around ~9-10 minutes per request, outside a useful interactive band for a dense 27B
- Compared to `Qwen3.6-35B-A3B (6-bit)` on `mlx-openai-server` at the same contexts: dense 27B is **~30-40% slower at gen** (27.0 vs 40.3 tok/s @ 64K) and **~5× slower at prefill** (274 vs 1,408 tok/s @ 64K). The MoE 3B-active sibling wins decisively for through-server throughput; the dense 27B's value is on quality (full 27B params per token) and the JANG mixed-precision compression
- Tool calling and `<think>` reasoning both work via this server config — see [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-jangq-aiqwen36-27b-jang_4m) for API-level + agentic-loop results
- Vision input is NOT exposed: vllm-mlx loads the model as `MLLM=False` (text-only). For VL inference, deploy on `vmlx` (MLX Studio bundled Python) or `mlx-openai-server` with the `multimodal` handler — neither has been validated for this specific model

---

## Qwen3.6-27B 6-bit (Standard MLX, on llmster vs vllm-mlx)

Model: `mlx-community/Qwen3.6-27B-6bit` (same dense 27.3B Qwen3.6 hybrid + ViT base as JANG 4M, but uniform 6-bit MLX quantization at 22 GB on disk — no JANG mixed-precision)
Tested on **Mac Studio M3 Ultra (96 GB)** — April 30, 2026.

**Why this matters:** This is the only model in the repo that runs on both vllm-mlx and llmster (LM Studio headless `lms server`) without architecture patches — standard MLX safetensors. It's the cleanest server-overhead comparison available.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 cold + 2 warm runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-llmster.json](qwen36-27b-6bit/api-server-llmster.json).

**Server:** llmster v0.4.12 (Homebrew cask `lm-studio`), MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`, `lms server start --bind 0.0.0.0`. Model loaded via `lms load qwen3.6-27b --gpu max --context-length 65536`. Served identifier: `qwen3.6-27b` (LM Studio strips the org prefix and lowercases it).

### Generation Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | **29.9** |
| 4K | 29.3 |
| 8K | 28.8 |
| 32K | 26.3 |

### Prefill Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | 1,086 |
| 4K | 8,031 |
| 8K | 15,321 |
| 32K | **47,143** |

### Time to First Token (seconds)

| Context | llmster |
|:--------|:-------:|
| 512 | **0.49** |
| 4K | 0.51 |
| 8K | 0.54 |
| 32K | 0.70 |

**Notes:**
- **Headline finding: TTFT is essentially flat from 512 → 32K (0.49 → 0.70 s)**. llmster's MLX runtime appears to use a much more aggressive prefill kernel than vllm-mlx — prefill speed scales linearly into the tens-of-thousands of tok/s range (47K tok/s at 32K context). Compare to `Qwen3.6-27B JANG 4M` on vllm-mlx where 32K TTFT is **104.45 s** at 314 tok/s prefill.
- **Generation speed is ~10–20 % slower than vllm-mlx + JANG 4M** at equal contexts (e.g. 512: 29.9 vs 36.5 tok/s; 32K: 26.3 vs 30.9 tok/s). Expected: 6-bit uniform > 4.45-bit mixed on memory bandwidth. The big win is prefill, not decode.
- 64K not tested on llmster — context-length limit was set to 65,536 at load time but the bench's 64K filler probe pushed past the model's hard ceiling (resolved: ran 4 contexts instead of 5).
- vllm-mlx baseline for this exact model file (`mlx-community/Qwen3.6-27B-6bit`) was never run for the api-server benchmark — only agent-bench. Direct vs JANG-variant comparison is the closest available.
- Tool calling works out of the box on llmster's MLX runtime — see [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-mlx-communityqwen36-27b-6bit-on-llmster) for the agent-loop comparison (llmster is **3–5× faster than vllm-mlx end-to-end** on the same model file).

---

## Gemma 4 31B-it (6-bit, dense, on llmster)

Model: `lmstudio-community/gemma-4-31B-it-MLX-6bit` (Google Gemma 4 dense **31B** instruction-tuned, 6-bit MLX, no MoE, no vision — 29 GB on disk, 31.32 GB total weights as reported by `lms get`)
Tested on **Mac Studio M3 Ultra (96 GB)** — May 1, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 3 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-llmster.json](gemma-4-31b-it-6bit/api-server-llmster.json).

**Server:** llmster, MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`, `lms server start --bind 0.0.0.0 --cors`. Model loaded via `lms load gemma-4-31b-it-mlx --gpu max --context-length 65536` (the served identifier from `/v1/models` is `gemma-4-31b-it-mlx` — note LM Studio retains the `-mlx` suffix from the `-MLX-` segment of the HF id, unlike Qwen3.6 where it strips `-6bit`).

### Generation Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | **21.8** |
| 4K | 21.5 |
| 8K | 21.1 |
| 32K | 18.3 |

### Prefill Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | 1,232 |
| 4K | 6,028 |
| 8K | 11,584 |
| 32K | **36,297** |

### Time to First Token (seconds)

| Context | llmster |
|:--------|:-------:|
| 512 | **0.44** |
| 4K | 0.68 |
| 8K | 0.71 |
| 32K | 0.90 |

**Notes:**
- **Decode tax for the larger dense model:** Gemma 4 31B-it (dense) is ~30–40 % slower in decode than Qwen3.6-27B-6bit on the same llmster (21.8 vs 29.9 tok/s @ 512; 18.3 vs 26.3 tok/s @ 32K). Expected — 31B dense vs 27B dense at the same 6-bit quant pays a roughly proportional bandwidth tax.
- **Prefill is also lower** at 32K (36K vs 47K tok/s) — same reason, more parameters to stream through the prefill kernel per token.
- **TTFT stays sub-1 s through 32K** — the headline llmster property holds.
- **`lms get` failed twice** on this model (timed out at 88 % with hung "Finalizing download…" state, only shards 4–6 of 6 on disk). Working path: kill the hung process, finish the download with `huggingface_hub.snapshot_download`, then `lms ls` recognises it. Detail in [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) "Loader gotcha" callout.
- **First load ignored `--context-length`** — model came up at 4K context despite the explicit flag, hit `HTTP 400: tokens exceed context length` on the 4K bench. Re-`lms unload` + re-`lms load --context-length 65536` correctly seats 64K.

---

## prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K (GGUF, on llmster)

Model: `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` (`Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf`) — prithivMLmods abliteration, mradermacher quantization. 28.51 GB on disk, 26.56 GiB resident at 65536 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 2, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-llmster.json](qwen36-35b-a3b-prithiv-aggressive/api-server-llmster.json).

**Server:** llmster v0.4.12, GGUF runtime (not MLX — note this is `.Q6_K.gguf`, not a safetensors MLX repo). Loaded with `lms load qwen3.6-35b-a3b-uncensored-aggressive --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k -y`. Parser flags not required — LM Studio handles Qwen3 chat-template tool-calls and `<think>` natively for this model.

**Deployment gotcha:** LM Studio memory guardrail (`modelLoadingGuardrails.mode: "high"`) counts only ~24 GB free pages, ignoring ~62 GB inactive/reclaimable — blocks load with "insufficient system resources." Workaround: temporarily set `mode` to `"off"` via `~/.lmstudio/settings.json`, load, restore to `"high"`. See [`qwen36-35b-a3b-prithiv-aggressive-benchmark.md`](../../uncen-model/qwen36-35b-a3b-prithiv-aggressive-benchmark.md) for the full recipe.

### Generation Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | **83.6** |
| 4K | 80.8 |
| 8K | 79.0 |
| 32K | 70.6 |

### Prefill Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | 5,350 |
| 4K | 35,118 |
| 8K | 56,616 |
| 32K | **113,519** |

### Time to First Token (seconds)

| Context | llmster |
|:--------|:-------:|
| 512 | **0.10** |
| 4K | 0.12 |
| 8K | 0.15 |
| 32K | 0.29 |

**Notes:**
- **TTFT is flat and sub-300 ms through 32K** — same headline llmster GGUF property seen on the 27B-6bit and HauhauCS variants. At 32K the TTFT is 0.29s vs 0.70s on the 27B-6bit run.
- **Generation is ~2.3–2.8× faster than Qwen3.6-27B-6bit** on the same llmster (83.6 vs 29.9 tok/s @ 512; 70.6 vs 26.3 tok/s @ 32K). The MoE 3B-active GGUF wins decisively over dense 27B on bandwidth-bound decode.
- **Prefill scales unusually fast:** 5K → 35K → 57K → 114K tok/s across 512 → 32K context. Compare to llmster 27B-6bit (MLX): 1K → 8K → 15K → 47K tok/s at the same contexts. The GGUF prefill kernel in LM Studio's GGUF runtime benefits from MoE sparsity more aggressively than the MLX uniform-quant kernel.
- **65K probe not run** — model loaded at exactly `--context-length 65536`; the bench's 65K filler probe fills the context exactly, leaving no headroom for `max_tokens=50`. Would require reloading at 70K context to probe accurately.
- **GGUF vs MLX runtime distinction:** unlike the MLX-safetensors models in the rest of this doc, this model runs through LM Studio's GGUF engine. Prefill rates are not directly comparable to the MLX-based servers — the LM Studio GGUF engine uses its own quantization-kernel path.

---

## DavidAU Qwen3.6-40B Heretic Q6_K IMatrix (GGUF, on llmster)

Model: `DavidAU/Qwen3.6-40B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking-NEO-CODE-Di-IMatrix-MAX-GGUF` (`Qwen3.6-40B-Deck-Opus-NEO-CODE-HERE-2T-OT-Q6_K.gguf`) — DavidAU Heretic recipe (full abliteration + Deckard/PDK), IMatrix-weighted Q6_K. 30.17 GiB on disk, ~30 GiB resident at 131072 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 3, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-llmster.json`](qwen36-40b-davidau-heretic/api-server-llmster.json).

**Server:** llmster, GGUF runtime. Loaded with `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier 'qwen36-40b-davidau-heretic-q6k' -y`. No parser flags required — LM Studio handles Qwen3 chat-template tool-calls and `<think>` natively.

**Deployment gotcha:** LM Studio memory guardrail (`modelLoadingGuardrails.mode: "high"`) counts only ~24 GB free pages, ignoring 60+ GB inactive/reclaimable — consistently blocks dense 40B + 131K load. Must temporarily set `mode` to `"off"`, load, then restore to `"high"`. See [`docs/current.md`](../../current.md) for the full toggle recipe.

### Generation Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | **9.7** |
| 4K | 9.6 |
| 8K | 9.5 |
| 32K | 8.8 |

### Prefill Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | 678 |
| 4K | 5,210 |
| 8K | 10,098 |
| 32K | 32,444 |

### Time to First Token (seconds)

| Context | llmster |
|:--------|:-------:|
| 512 | 0.79 |
| 4K | 0.80 |
| 8K | 0.82 |
| 32K | 1.01 |

**Notes:**
- **Dense 40B penalty:** gen speed is 8.8–9.7 tok/s — all 40B params active per decode step (no MoE sparsity). Compare to prithivMLmods MoE-35B/3B-active (83.6–70.6 tok/s) or HauhauCS (~90–72 tok/s). Dense 40B is ~9× slower on decode.
- **Prefill also significantly slower:** 678–32K tok/s at 512–32K context, vs prithivMLmods 5,350–113,519 tok/s. The GGUF kernel loses the MoE sparsity advantage on prefill too.
- **TTFT flat but slower:** 0.79–1.01 s through 32K (vs sub-300ms for MoE siblings). Still sub-1 s through 8K.
- **65K probe not run** — bench script probes at 65K only when `--context-length ≥ 65536`; model was loaded at exactly 131072, but the 65K probe would require 65K fill tokens which conflicts with bench warmup logic at that size. 32K is the largest clean probe.
- **GGUF vs MLX runtime:** same runtime distinction as prithivMLmods — numbers not directly comparable to MLX-based servers.

---

## DavidAU Gemma 4 31B Heretic Q6_k (GGUF, on llmster)

Model: `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` (`gemma-4-31B-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Q6_k.gguf`) — Thinking variant, DavidAU HERETIC + Mystery Fine Tune on Gemma 4 31B dense base. 25.20 GB on disk, 23.47 GiB resident at 131072 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 3, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-llmster.json`](gemma4-31b-davidau-heretic/api-server-llmster.json).

**Server:** llmster, GGUF runtime. Loaded with `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier 'gemma4-31b-davidau-heretic-q6k' -y`. No parser flags required — LM Studio handles Gemma 4 tool-calls natively.

### Generation Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | **24.2** |
| 4K | 23.0 |
| 8K | 23.2 |
| 32K | 20.9 |
| 64K | 21.0 |

### Prefill Speed (tok/s)

| Context | llmster |
|:--------|:-------:|
| 512 | 1,132 |
| 4K | 12,658 |
| 8K | 20,175 |
| 32K | 54,332 |
| 64K | 53,531 |

### Time to First Token (seconds)

| Context | llmster |
|:--------|:-------:|
| 512 | 0.48 |
| 4K | 0.33 |
| 8K | 0.41 |
| 32K | 0.60 |
| 64K | 1.22 |

**Notes:**
- **Prefill superlinear scaling:** 1,132 tok/s @ 512 → 54,332 tok/s @ 32K — a 48× improvement for 64× more context. Flash attention parallelism peaks at mid-to-long contexts on M3 Ultra.
- **Gen speed stable:** 20.9–24.2 tok/s across contexts — significantly faster than DavidAU 40B (8.8–9.7 tok/s) and ~10% faster than the standard Gemma 4 31B-it MLX 6-bit (21.8–18.3 tok/s). GGUF Q6_k on llama.cpp backend outpaces MLX safetensors on short contexts.
- **Thinking overhead:** The 50-token bench measures raw decode speed. In practice, the Thinking variant spends its token budget on `<|channel>thought` content at the same speed — agent turns effectively run at ~4–5 tok/s for visible output.
- **GGUF vs MLX runtime:** numbers not directly comparable to MLX-based servers.

---

## Ling-2.6-flash mlx-6bit (104B/7B-active, bailing_hybrid)

Model: `mlx-community/Ling-2.6-flash-mlx-6bit` (`BailingMoeV2_5ForCausalLM`, `model_type=bailing_hybrid`) — 256 experts, 8 active per token, 32 layers (mixed MLA + Lightning-style linear-attention recurrence, MLA on 4/15/23/31), `max_position_embeddings=131,072`, sigmoid noaux_tc MoE with group-limited top-8. 6-bit MLX uniform quant (~80 GB on disk). No vision, no `<think>` reasoning emitted.
Tested on **Mac Studio M3 Ultra (96 GB)** — April 29, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 cold + 2 warm runs per context. Filler-token padding via `Hello world. ` repetition. Raw JSON: [api-server-vllm-mlx.json](ling-2.6-flash-6bit/api-server-vllm-mlx.json). Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py).

**Server:** vllm-mlx v0.2.6 native CLI (no JANG wrapper) with `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits `<tool_call>{json}</tool_call>` Hermes-format calls — vllm-mlx has no `qwen3` tool-call parser; `qwen3_coder` expects XML body, not JSON). mlx-lm 0.31.3 with three local patches needed to get this model running:

1. **`mlx_lm/models/bailing_hybrid.py`** — vendored from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227) (ivanfioravanti). Without it: `ValueError: Model type bailing_hybrid not supported`.
2. **[`scripts/patches/patch_mlx_lm_threadlocal_stream.py`](../../../scripts/patches/patch_mlx_lm_threadlocal_stream.py)** — converts `mlx_lm.generate.generation_stream` from a module-level thread-local stream into a per-thread lazy accessor. Stock mlx-lm creates the stream at import time on the main thread; vllm-mlx (and mlx-openai-server) run inference in worker threads where that stream object is unreachable.
3. **[`scripts/patches/patch_vllm_mlx_inline_gen.py`](../../../scripts/patches/patch_vllm_mlx_inline_gen.py)** — replaces every `await asyncio.to_thread(...)` in `vllm_mlx/engine/simple.py` with a direct synchronous call. Fundamental MLX limitation: custom `mx.fast.metal_kernel` objects (used by `bailing_hybrid` for the linear-attention recurrence and the GLA SSM kernel) are bound to the thread that built them. Trying to invoke them from a different thread raises `RuntimeError: There is no Stream(gpu, 0) in current thread` even after patch #2. Running generation inline on the asyncio event loop avoids the cross-thread invocation entirely. Generation now blocks the loop, which is fine for single-stream inference servers.

mlx-openai-server tripped the same threading bug (`There is no Stream(gpu, 1) in current thread` at `mx.eval([c.state for c in model_cache])` in its prompt-cache prefill); patch #2 alone is not enough there because the mlx-openai-server inference-worker design is more deeply thread-coupled than vllm-mlx and patch #3 doesn't apply directly. vllm-mlx is the only viable host for this model today.

### Generation Speed (tok/s)

| Context | vllm-mlx |
|:--------|:--------:|
| 512 | **64.5** |
| 4K | 64.5 |
| 8K | 64.4 |
| 32K | 61.5 |
| 64K | 57.3 |
| 128K | ⛔ OOM |

### Prefill Speed (tok/s)

| Context | vllm-mlx (against actual chat-templated tokens) |
|:--------|:-----------------------------------------------:|
| 512 | ~750 |
| 4K | ~1,090 |
| 8K | ~1,120 |
| 32K | ~1,060 |
| 64K | ~890 |

Prompt-token counts reported by the server are 0 (vllm-mlx field-fill bug, same as JANG_4M); rates above use locally-tokenised prompt sizes (~535 / 4,100 / 8,200 / 32,800 / 65,500 tokens for the five contexts).

### Time to First Token (seconds)

| Context | vllm-mlx |
|:--------|:--------:|
| 512 | 0.70 |
| 4K | 3.77 |
| 8K | 7.34 |
| 32K | 30.92 |
| 64K | 73.53 |
| 128K | ⛔ OOM mid-prefill |

**Notes:**
- **128K OOMs** — the `bailing_hybrid` cache layout (KVCache for the 4 MLA layers + ArraysCache(size=1) for the 28 linear-attention layers) plus 80 GB of weights lands above the 96 GB unified-memory ceiling on M3 Ultra at 128K. Server crashes with `[METAL] Command buffer execution failed: Insufficient Memory`. Useful interactive ceiling on this hardware sits around 64K
- Generation throughput stays **flat (~64 tok/s)** from 512 → 8K and only slips to 57 tok/s at 64K — much less context-sensitivity than the dense 27B models. The recurrent linear-attention path doesn't grow KV state with context (single-step recurrence) so memory bandwidth pressure scales mainly with the 4 MLA layers
- Compared to `Qwen3.6-35B-A3B (6-bit)` on `mlx-openai-server` at 64K: Ling is **~42% faster** in generation (57.3 vs 40.3 tok/s) but slower in prefill at the same context, because the MLA absorbed-form is more compute-heavy per token than Qwen3.6's sliding-window MoE at this hardware. The architectural win shows at long context — Ling holds 64 tok/s gen at 32K where Qwen3.6 has dropped to 46.3
- Vision is N/A — `bailing_hybrid` is text-only

---

## 🤖 IBM Granite 4.1 30B Q8_0 (Dense, GGUF) on llmster

Model: `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF`

Tested on **Mac Studio M3 Ultra (96 GB)** — 2026-05-05.

**Server:** llmster / LM Studio headless on port 1234. Raw JSON: [`granite-4.1-30b-q8/api-server-llmster.json`](granite-4.1-30b-q8/api-server-llmster.json).

### Generation Speed (tok/s)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **24.8** | 2,520 | 0.22 |
| 4K | **26.0** | 17,890 | 0.23 |
| 8K | 23.6 | 34,200 | 0.24 |
| 32K | 18.7 | 92,600 | 0.36 |

**65K context:** HTTP 400 (sliding window boundary). Real queries < 32K work fine.

**Notes:**
- Dense 30B: all parameters active every token → 24–26 tok/s gen is expected for this class. Prefill scales well (2.5K → 92K tok/s from 512 → 32K) due to well-behaved dense attention.
- 3–3.5× slower than TrevorJS Gemma 4 26B A4B MoE (87.6 tok/s) due to MoE sparsity advantage.
- Comparable to Gemma 4 31B-it on llmster (18–22 tok/s).

---

## 128K Cross-Model Summary

All models benchmarked at the 128K-context bucket (closest standard size to the 100K-class workload):

| Model | Quant | Server | Gen tok/s | Prefill tok/s | TTFT (s) | Date |
|---|---|---:|---:|---:|---:|---|
| **Qwen3-Coder-Next 6-bit** (Dense 80B + Gated DeltaNet) | 6-bit MLX | vllm-mlx | **44.2** 🥇 | **736** 🥇 | **158.4** 🥇 | 2026-04-18 |
| **Qwen3.6-35B-A3B** (Hybrid MoE 35B/3B + VL) | 6-bit MLX | mlx-openai-server | 35.6 🥈 | 927* | 125.7 🥈 | 2026-04-18 |
| **Qwen3.5-122B-A10B JANG 2S** (MoE 122B/10B) | JANG ~2.1-bit | vllm-mlx (JANG wrapper) | 34.5 | 405† | 323.9 | 2026-04-18 |
| **Qwen3.5-35B-A3B JANG 4K** (MoE 35B/3B) | JANG ~4-bit | oMLX | 33.8 | 295.4 | — | 2026-03-24 (omlx.ai) |
| **Gemma 4 26B-A4B** (MoE 26B/4B + VL) | 4-bit MLX | mlx-openai-server | 27.1 | 1,995 | 65.7 | 2026-04-17 |

\* Qwen3.6 prefill at 128K is the lowest of the 35B-class models because the hybrid stack's full-attention layers become memory-bound past 64K  
† Qwen3.5-122B JANG 2S prefill normalised against requested 131,072; against the actual ~116,516-token filler the rate is ~360 tok/s

**Takeaways:**
- For a 100K+-class workload where you need to push generation throughput, **Qwen3-Coder-Next 6-bit on vllm-mlx wins** — 44.2 tok/s gen and 158s TTFT, both best in class. Trade-off: no vision, no thinking
- **Qwen3.6-35B-A3B** is the pick when you also need vision or always-on thinking; the gen-speed cost is ~20% vs Coder-Next, the TTFT is actually lower (125.7 vs 158.4 s) thanks to the hybrid Gated DeltaNet at 35B activation
- **Qwen3.5-122B JANG 2S** delivers competitive 34.5 tok/s gen at 122B parameters by activating only ~10B per token, but the JANG dequantization cost makes prefill at 128K very slow (5+ min TTFT) — choose this only when you need 122B's reasoning quality at long context and can wait for prefill

---

## 🩹 vllm-mlx Bug Fix

vllm-mlx v0.2.6 has a bug in `vllm_mlx/utils/tokenizer.py`: the `load_model_with_fallback()` function is missing `return model, tokenizer` after a successful `mlx_lm.load()` call, causing the function to return `None`. Patched locally by adding the missing return statement.

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `/tmp/benchmark_server.py` | API benchmark client (SSE streaming, original) |
| `/tmp/benchmark_server2.py` | API benchmark client (SSE streaming, +reasoning_content support) |
| `/tmp/benchmark_server3.py` | API benchmark client (SSE streaming, +API key auth) |
| `/tmp/run_mlx_server_jang.py` | mlx-lm.server JANG wrapper |
| `/tmp/run_vllm_jang.py` | vllm-mlx JANG wrapper |
| `~/run_mlx_openai_jang.py` | mlx-openai-server JANG wrapper |
| `~/turboquant-pcr/results/server_*.json` | Raw JSON results |
| `~/vllm-mlx-env/` | vllm-mlx Python 3.12 venv |
| `~/mlx-openai-server-env/` | mlx-openai-server Python 3.12 venv |
