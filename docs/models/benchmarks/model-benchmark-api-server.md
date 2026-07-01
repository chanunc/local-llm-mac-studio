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
Tested on **Mac Studio M3 Ultra (96 GB)** — original May 1, 2026 (vMLX 1.3.65); refreshed May 5, 2026 under vMLX 1.5.20 + `--continuous-batching`.

Raw JSON: [`qwen36-35b-a3b-jangtq4-osaurus/api-server-vmlx.json`](qwen36-35b-a3b-jangtq4-osaurus/api-server-vmlx.json) — current file reflects the 2026-05-05 refresh; prior 2026-05-01 numbers preserved in git history.

### Generation Speed (tok/s)

| Context | vMLX 1.5.20 (2026-05-05) | vMLX 1.3.65 (2026-05-01) |
|:--|--:|--:|
| 512 | 65.7 | 64.9 |
| 4K | 64.0 | 64.8 |
| 8K | 61.1 | 64.0 |
| 32K | **37.4** | 58.8 |
| 64K | **18.4** | 52.6 |

### Prefill Speed (tok/s)

| Context | vMLX 1.5.20 (2026-05-05) | vMLX 1.3.65 (2026-05-01) |
|:--|--:|--:|
| 512 | **919** | 359.7 |
| 4K | **990** | 365.1 |
| 8K | **956** | 362.0 |
| 32K | **877** | 346.3 |
| 64K | **758** | 325.7 |

### Time to First Token

| Context | vMLX 1.5.20 | vMLX 1.3.65 |
|:--|--:|--:|
| 512 | **0.58 s** | 1.49 s |
| 4K | **4.16 s** | 11.29 s |
| 8K | **8.59 s** | 22.70 s |
| 32K | **37.36 s** | 94.71 s |
| 64K | **86.52 s** | 201.32 s |

Notes:
- vMLX 1.5.20 (with `--continuous-batching` mandatory — see [`docs/servers/vmlx/maintenance.md`](../servers/vmlx/maintenance.md)) **ships ~2.5× faster prefill** at every context length, cutting TTFT by 57-63 %. Net win for prefill-bound agent loops.
- **Long-context decode regression:** gen falls 36 % @ 32K and 65 % @ 64K versus the prior runtime. Tasks generating >2K output tokens at >16K input feel noticeably slower (see the OpenCode search result in [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md)).
- Startup logs (both runtimes) confirm native JANGTQ VLM fast path: `load_jangtq_vlm`, 120 TurboQuant modules replaced, no fallback warning.
- Agent-loop latency in 1.3.65 was dominated by prefill (OpenCode sends ~11K tokens on first turn, growing to ~42K). With 1.5.20's prefill speedup, agent loops are now decode-bound at long context.

---

---

## Gemma 4 26B-A4B-it (4-bit)

Model: `mlx-community/gemma-4-26b-a4b-it-4bit`  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 17, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens count both `reasoning_content` (thinking) and `content` (answer) phases — Gemma 4 always thinks before answering. 512 warm values shown (run 1 was a cold-start: 59.4 tok/s gen / 28 tok/s prefill / 18.7s TTFT).

**Servers:** (1) mlx-openai-server v1.7.1 (mlx-lm 0.31.2, mlx-vlm 0.4.4), 2026-04-17; raw JSON: [api-server-mlx-openai-server.json](gemma-4-26b-a4b-it-4bit/api-server-mlx-openai-server.json) (if present). vllm-mlx has a known reasoning parser bug ([#38855](https://github.com/vllm-project/vllm/issues/38855)) and oMLX lacks the `gemma4` parser. (2) lm-studio v0.4.12 (MLX runtime, no parser flags), 2026-05-08; raw JSON: [api-server-llmster.json](gemma-4-26b-a4b-it-4bit/api-server-llmster.json).

### Generation Speed (tok/s)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 62.5              | **114.0** 🏆 |
| 4K      | 54.6              | **106.4** 🏆 |
| 8K      | 60.6              | **98.8** 🏆 |
| 32K     | 50.6              | **76.7** 🏆 |
| 64K     | 42.0              | — |
| 128K    | 27.1              | — |

### Prefill Speed (tok/s)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 1,710             | **3,040** 🏆 |
| 4K      | 3,117             | **18,780** 🏆 |
| 8K      | 3,154             | **34,830** 🏆 |
| 32K     | 2,892             | **99,580** 🏆 |
| 64K     | 2,542             | — |
| 128K    | 1,995             | — |

### Time to First Token (seconds)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 0.30              | **0.18** 🏆 |
| 4K      | 1.32              | **0.22** 🏆 |
| 8K      | 2.60              | **0.24** 🏆 |
| 32K     | 11.34             | **0.33** 🏆 |
| 64K     | 25.78             | — |
| 128K    | 65.70             | — |

**Notes:**
- Gen speed is stable across runs (±0.1 tok/s at 32K–128K) — minimal variance due to MoE routing determinism at temperature 0.0
- 8K slightly faster than 4K in generation on mlx-openai-server — likely GPU utilization sweet spot for this sliding-window MoE
- 128K TTFT (65.7s) on mlx-openai-server is dominated by prefill time; generation itself is 27.1 tok/s once started

**lm-studio comparison observations (2026-05-08):**
- **lm-studio decode is 1.5–1.9× faster** than mlx-openai-server at every shared context (114 vs 62.5 tok/s @ 512; 76.7 vs 50.6 tok/s @ 32 K). Same MLX safetensors, same hardware — gap is the LM Studio MLX runtime's per-token decoder. Same magnitude as the Qwen3.6-35B-A3B-6bit gap on this server pair ([§Qwen3.6-35B-A3B (6-bit)](#qwen36-35b-a3b-6-bit)).
- **Prefill scaling is dramatic:** 6× faster at 4 K, 11× faster at 8 K, **34× faster at 32 K** (99,580 vs 2,892 tok/s). The lm-studio prefill kernel pattern observed for Qwen3.6 also applies to Gemma 4.
- **Unlike Qwen3.6, OpenCode end-to-end is *faster* on this MLX path than on the GGUF Q8_0 sibling** — search 3.23 s vs 7.20 s on the Q8_0 GGUF (2.2× faster). Format-vs-runtime conclusion does not generalise across families. See [`model-benchmark-tool-call.md` § Results: mlx-community/gemma-4-26b-a4b-it-4bit on lm-studio](model-benchmark-tool-call.md#results-mlx-communitygemma-4-26b-a4b-it-4bit-on-lm-studio).

---

## Qwen3.6-35B-A3B (6-bit)

Model: `mlx-community/Qwen3.6-35B-A3B-6bit`  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 18, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens count both `reasoning_content` (thinking) and `content` (answer) phases — Qwen3.6 always thinks before answering. Warm values shown (run 1 to run 3 differ only in TTFT for ctx=512: 0.58s cold vs 0.34s warm; gen tok/s identical to ±0.3 across all runs).

**Servers:** (1) mlx-openai-server v1.7.1 — `model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`, `context_length: 131072`; reference YAML: [mlx-openai-server-qwen36-35b.yaml](../../servers/mlx-openai-server/mlx-openai-server-qwen36-35b.yaml); raw JSON: [api-server-mlx-openai-server.json](qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json) (2026-04-18). (2) lm-studio v0.4.12 — LM Studio MLX runtime, no parser flags, loaded with `lms load 'mlx-community/qwen3.6-35b-a3b' --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-mlx-6bit -y`; raw JSON: [api-server-llmster.json](qwen36-35b-a3b-6bit/api-server-llmster.json) (2026-05-08, 50 max-tokens cap, 1 warmup + 2 measured).

> Why not other servers: `oMLX` has multiple open Qwen3.6 issues ([#812](https://github.com/jundot/omlx/issues/812), [#819](https://github.com/jundot/omlx/issues/819), [#827](https://github.com/jundot/omlx/issues/827), [#841](https://github.com/jundot/omlx/issues/841)); `vllm-mlx` post-PR [#278](https://github.com/waybarrios/vllm-mlx/pull/278) is the only alternative that exposes MTP through API but inherits the upstream `mlx-lm` hybrid-cache bug ([#1162](https://github.com/ml-explore/mlx-lm/issues/1162)).

### Generation Speed (tok/s)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 52.5              | **89.7** 🏆 |
| 4K      | 53.0              | **87.7** 🏆 |
| 8K      | 51.3              | **86.0** 🏆 |
| 32K     | 46.3              | **76.1** 🏆 |
| 64K     | 40.3              | — |
| 128K    | 35.6              | — |

### Prefill Speed (tok/s)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 1,401             | 2,610     |
| 4K      | 2,237             | **18,820** 🏆 |
| 8K      | 2,197             | **34,800** 🏆 |
| 32K     | 1,798             | **96,860** 🏆 |
| 64K     | 1,408             | — |
| 128K    | 927               | — |

### Time to First Token (seconds)

| Context | mlx-openai-server | lm-studio |
|:--------|:-----------------:|:---------:|
| 512     | 0.34              | **0.21** 🏆 |
| 4K      | 1.64              | **0.22** 🏆 |
| 8K      | 3.32              | **0.24** 🏆 |
| 32K     | 16.22             | **0.34** 🏆 |
| 64K     | 41.40             | — |
| 128K    | 125.73            | — |

(lm-studio rows missing 64K/128K because the server was loaded with `--context-length 65536` and the probe at 65536 itself returns HTTP 400 — re-probe with `--context-length 131072` if you need the long-tail; the 32 K row is already 53 × faster TTFT than mlx-openai-server, so the prefill kernel scaling is well-established below 64 K.)

**Notes:**
- Server overhead at 512 ≈ 4% gen vs the standalone clean reading of 54.7 tok/s (`model-benchmark-standalone.md:101`); within the 4-15% band already seen for Qwen3.5-JANG on this server
- Streaming reasoning split is **clean** for Qwen3.6 with the `qwen3_vl` parser — `reasoning_content` and `content` arrive in separate SSE deltas. The Gemma 4 streaming-leak bug ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) does not surface here
- Prompt-token counts reported by the server are slightly under the requested context (e.g. ctx=131072 → prompt_tokens=116,518) because the seed-string filler tokenises shorter than 1 char-per-quarter-token in spots — the reported tok/s is computed against the actual `prompt_tokens` from `usage`
- Vision through API verified: `image_url` content blocks (data:image/png;base64) accepted; 64×64 solid-red PNG correctly identified as "Red"
- Hybrid Gated DeltaNet pays off at long context: 128K gen at 35.6 tok/s is **31% faster** than Gemma 4's 27.1 tok/s at the same context, despite Qwen3.6 activating ~3B params vs Gemma 4's ~4B
- `enable_thinking=false` not testable here — same parser-hookup gap as Gemma 4 ([#279](https://github.com/cubist38/mlx-openai-server/issues/279)); `<think>` is always emitted (counted in gen tokens above)

**lm-studio comparison observations (2026-05-08):**
- **lm-studio decode is 1.6–1.9× faster than mlx-openai-server** at every shared context (89.7 vs 52.5 tok/s @ 512; 76.1 vs 46.3 tok/s @ 32 K). Same MLX safetensors, same hardware — the gap is the LM Studio MLX runtime's per-token decoder.
- **Prefill scaling is dramatic.** lm-studio's prefill kernel runs ~14× faster at 4 K (18.8 K vs 2.2 K tok/s) and **54× faster at 32 K** (96.9 K vs 1.8 K tok/s), matching the 47 K tok/s @ 32 K behaviour observed for `mlx-community/Qwen3.6-27B-6bit` ([§Qwen3.6-27B 6-bit on lm-studio vs vllm-mlx](#qwen36-27b-6-bit-standard-mlx-on-lm-studio-vs-vllm-mlx)). The pattern generalises across the Qwen3.6 family on this server.
- **Despite the throughput win, OpenCode end-to-end is 3× slower than the GGUF Q6_K sibling on the same lm-studio runtime** — see [`model-benchmark-tool-call.md` § Results: mlx-community/Qwen3.6-35B-A3B-6bit on lm-studio](model-benchmark-tool-call.md#results-mlx-communityqwen36-35b-a3b-6bit-on-lm-studio) for the per-turn breakdown. Format-driven gap that the throughput probe doesn't surface.

---

## Qwen3.6-35B-A3B MLX via Ollama

Model: `qwen3.6:35b-mlx`  
Tested on **Mac Studio M3 Ultra (96 GB)** — May 30, 2026.

**Method:** Streaming `/v1/chat/completions`, 50 max tokens, temperature 0.0, 2 measured runs per context. Raw JSON: [`logs/qwen36-35b-mlx-ollama/api-server-ollama.json`](logs/qwen36-35b-mlx-ollama/api-server-ollama.json).

**Server:** Homebrew Ollama 0.24.0 with `mlx-c`, launched with `OLLAMA_HOST=0.0.0.0:11434 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`.

### Generation Speed (tok/s)

| Context | Ollama MLX |
|:--|--:|
| 512 | 101.9 |
| 4K | 96.0 |
| 8K | 97.7 |
| 32K | 83.9 |
| 65K | 72.5 |

### Prefill Speed (tok/s)

| Context | Ollama MLX |
|:--|--:|
| 512 | 9,322 |
| 4K | 62,210 |
| 8K | 120,686 |
| 32K | 330,170 |
| 65K | 498,380 |

### Time to First Token (seconds)

| Context | Ollama MLX |
|:--|--:|
| 512 | 0.057 |
| 4K | 0.066 |
| 8K | 0.069 |
| 32K | 0.099 |
| 65K | 0.132 |

**Notes:**
- Ollama's MLX path has extremely low TTFT in this short-output throughput harness. The OpenCode agent loop still measures real multi-turn latency: browse 9.75 s and search 18.4 s with `webfetch`.
- Tool calling passes the local API smoke 5/5; see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md#opencode-end-to-end-opencode-run---format-json-real-agent-loop) and the [`ollama` runbook](../../servers/ollama/summary.md).

---

## Gemma 4 26B-A4B via Ollama

Model: `gemma4:26b`
Tested on **Mac Studio M3 Ultra (96 GB)** — May 31, 2026.

**Method:** Streaming `/v1/chat/completions`, 50 max tokens, temperature 0.0, 2 measured runs per context. Raw JSON: [`logs/gemma4-26b-ollama/api-server-ollama.json`](logs/gemma4-26b-ollama/api-server-ollama.json).

**Server:** Homebrew Ollama 0.24.0 with `mlx-c`, launched with `OLLAMA_HOST=0.0.0.0:11434 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`.

### Generation Speed (tok/s)

| Context | Ollama MLX |
|:--|--:|
| 512 | 77.9 |
| 4K | 70.0 |
| 8K | 68.7 |
| 32K | 49.4 |
| 65K | 36.5 |

### Prefill Speed (tok/s)

| Context | Ollama MLX |
|:--|--:|
| 512 | 3,074.6 |
| 4K | 21,208.4 |
| 8K | 39,302.3 |
| 32K | 99,565.2 |
| 65K | 132,056.5 |

### Time to First Token (seconds)

| Context | Ollama MLX |
|:--|--:|
| 512 | 0.176 |
| 4K | 0.195 |
| 8K | 0.209 |
| 32K | 0.33 |
| 65K | 0.496 |

**Notes:**
- The OpenCode agent loop still measures real multi-turn latency: browse 16.7 s and search 26.37 s with `webfetch`.
- Tool calling passes the local API smoke 5/5; see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md#opencode-end-to-end-opencode-run---format-json-real-agent-loop) and the [`ollama` runbook](../../servers/ollama/summary.md).

---

## Gemma4-12B Agentic v2 Q8_0 + TurboQuant turbo3 on llama-cpp-turboquant

Model: `yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF` (`gemma4-v2-Q8_0.gguf`, 12.67 GB)
Server: `llama-cpp-turboquant` :8099, TheTom fork `69d8e4b`, `--cache-type-k turbo3 --cache-type-v turbo3`, `-c 262144`, `--jinja --reasoning on`
Tested on **Mac Studio M3 Ultra (96 GB)** — June 24, 2026.

**Method:** Streaming `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Raw JSON: [`logs/gemma4-12b-agentic-v2-q8-turbo3-256k/api-server.json`](logs/gemma4-12b-agentic-v2-q8-turbo3-256k/api-server.json).

### Generation Speed (tok/s)

| Context | Decode tok/s |
|:--|--:|
| 512 | 29.7 |
| 4K | 28.6 |
| 8K | 27.7 |
| 32K | 24.7 |
| 65K | 21.7 |
| 131K | 17.2 |

### Prefill Speed (tok/s)

| Context | Prefill tok/s |
|:--|--:|
| 512 | 2,582 |
| 4K | 25,817 |
| 8K | 48,159 |
| 32K | 150,826 |
| 65K | 231,778 |
| 131K | 313,613 |

### Time to First Token

| Context | TTFT |
|:--|--:|
| 512 | 0.210 s |
| 4K | 0.160 s |
| 8K | 0.171 s |
| 32K | 0.217 s |
| 65K | 0.283 s |
| 131K | 0.418 s |

### Context fit

Launch logs confirmed the server allocated `n_ctx = 262144`. With `turbo3` KV, the 256K KV footprint was small for this architecture: non-SWA cache `800 MiB` plus SWA cache `93.75 MiB`; Q8 weights mapped at ~12.07 GiB on Metal plus ~1.02 GiB CPU mapped.

The standard benchmark's nominal `262144` prompt was rejected because chat-template overhead made the request `262176` tokens, exceeding the exact slot. A separate near-ceiling probe with `260024` prompt tokens completed without truncation and generated 8 tokens. Server-side timing: `1,177.6 s` prompt eval for the uncached 128,940-token extension (~109.5 tok/s) plus `12.8 tok/s` decode. Raw probe: [`logs/gemma4-12b-agentic-v2-q8-turbo3-256k/max-context-probe.json`](logs/gemma4-12b-agentic-v2-q8-turbo3-256k/max-context-probe.json).

**Takeaway:** Q8_0 fits the full 256K context on the 96 GB Mac Studio, but uncached near-ceiling prompts are impractically slow under this TheTom build because prompt-cache checkpointing dominates. Agent workloads at normal prompt sizes are governed by model behavior, not memory; see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md#results-yuxinlu1gemma4-12b-agentic-v2-q8_0--turboquant-turbo3).

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
- Tool calling and `<think>` reasoning both work via this server config — see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md#results-jangq-aiqwen36-27b-jang_4m) for API-level + agentic-loop results
- Vision input is NOT exposed: vllm-mlx loads the model as `MLLM=False` (text-only). For VL inference, deploy on `vmlx` (MLX Studio bundled Python) or `mlx-openai-server` with the `multimodal` handler — neither has been validated for this specific model

---

## Qwen3.6-27B 6-bit (Standard MLX, on lm-studio vs vllm-mlx)

Model: `mlx-community/Qwen3.6-27B-6bit` (same dense 27.3B Qwen3.6 hybrid + ViT base as JANG 4M, but uniform 6-bit MLX quantization at 22 GB on disk — no JANG mixed-precision)
Tested on **Mac Studio M3 Ultra (96 GB)** — April 30, 2026.

**Why this matters:** This is the only model in the repo that runs on both vllm-mlx and lm-studio (LM Studio headless `lms server`) without architecture patches — standard MLX safetensors. It's the cleanest server-overhead comparison available.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 cold + 2 warm runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-lm-studio.json](qwen36-27b-6bit/api-server-lm-studio.json).

**Server:** lm-studio v0.4.12 (Homebrew cask `lm-studio`), MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`, `lms server start --bind 0.0.0.0`. Model loaded via `lms load qwen3.6-27b --gpu max --context-length 65536`. Served identifier: `qwen3.6-27b` (LM Studio strips the org prefix and lowercases it).

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **29.9** |
| 4K | 29.3 |
| 8K | 28.8 |
| 32K | 26.3 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 1,086 |
| 4K | 8,031 |
| 8K | 15,321 |
| 32K | **47,143** |

### Time to First Token (seconds)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **0.49** |
| 4K | 0.51 |
| 8K | 0.54 |
| 32K | 0.70 |

**Notes:**
- **Headline finding: TTFT is essentially flat from 512 → 32K (0.49 → 0.70 s)**. lm-studio's MLX runtime appears to use a much more aggressive prefill kernel than vllm-mlx — prefill speed scales linearly into the tens-of-thousands of tok/s range (47K tok/s at 32K context). Compare to `Qwen3.6-27B JANG 4M` on vllm-mlx where 32K TTFT is **104.45 s** at 314 tok/s prefill.
- **Generation speed is ~10–20 % slower than vllm-mlx + JANG 4M** at equal contexts (e.g. 512: 29.9 vs 36.5 tok/s; 32K: 26.3 vs 30.9 tok/s). Expected: 6-bit uniform > 4.45-bit mixed on memory bandwidth. The big win is prefill, not decode.
- 64K not tested on lm-studio — context-length limit was set to 65,536 at load time but the bench's 64K filler probe pushed past the model's hard ceiling (resolved: ran 4 contexts instead of 5).
- vllm-mlx baseline for this exact model file (`mlx-community/Qwen3.6-27B-6bit`) was never run for the api-server benchmark — only agent-bench. Direct vs JANG-variant comparison is the closest available.
- Tool calling works out of the box on lm-studio's MLX runtime — see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md#results-mlx-communityqwen36-27b-6bit-on-lm-studio) for the agent-loop comparison (lm-studio is **3–5× faster than vllm-mlx end-to-end** on the same model file).

---

## Gemma 4 31B-it (6-bit, dense, on lm-studio)

Model: `lmstudio-community/gemma-4-31B-it-MLX-6bit` (Google Gemma 4 dense **31B** instruction-tuned, 6-bit MLX, no MoE, no vision — 29 GB on disk, 31.32 GB total weights as reported by `lms get`)
Tested on **Mac Studio M3 Ultra (96 GB)** — May 1, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 3 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-lm-studio.json](gemma-4-31b-it-6bit/api-server-lm-studio.json).

**Server:** lm-studio, MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`, `lms server start --bind 0.0.0.0 --cors`. Model loaded via `lms load gemma-4-31b-it-mlx --gpu max --context-length 65536` (the served identifier from `/v1/models` is `gemma-4-31b-it-mlx` — note LM Studio retains the `-mlx` suffix from the `-MLX-` segment of the HF id, unlike Qwen3.6 where it strips `-6bit`).

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **21.8** |
| 4K | 21.5 |
| 8K | 21.1 |
| 32K | 18.3 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 1,232 |
| 4K | 6,028 |
| 8K | 11,584 |
| 32K | **36,297** |

### Time to First Token (seconds)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **0.44** |
| 4K | 0.68 |
| 8K | 0.71 |
| 32K | 0.90 |

**Notes:**
- **Decode tax for the larger dense model:** Gemma 4 31B-it (dense) is ~30–40 % slower in decode than Qwen3.6-27B-6bit on the same lm-studio (21.8 vs 29.9 tok/s @ 512; 18.3 vs 26.3 tok/s @ 32K). Expected — 31B dense vs 27B dense at the same 6-bit quant pays a roughly proportional bandwidth tax.
- **Prefill is also lower** at 32K (36K vs 47K tok/s) — same reason, more parameters to stream through the prefill kernel per token.
- **TTFT stays sub-1 s through 32K** — the headline lm-studio property holds.
- **`lms get` failed twice** on this model (timed out at 88 % with hung "Finalizing download…" state, only shards 4–6 of 6 on disk). Working path: kill the hung process, finish the download with `huggingface_hub.snapshot_download`, then `lms ls` recognises it. Detail in [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) "Loader gotcha" callout.
- **First load ignored `--context-length`** — model came up at 4K context despite the explicit flag, hit `HTTP 400: tokens exceed context length` on the 4K bench. Re-`lms unload` + re-`lms load --context-length 65536` correctly seats 64K.

---

## Gemma 4 31B-it (6-bit, dense, on mlx-lm server)

Model: `lmstudio-community/gemma-4-31B-it-MLX-6bit` — same weights as the lm-studio run above.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 6, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context (512, 4K, 8K, 32K, 65K). Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-mlx-lm.json](gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json).

**Server:** `mlx_lm.server` (mlx-lm 0.31.3 from the Cellar libexec binary at `/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server`), started via `/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit --host 0.0.0.0 --port 8000 --max-tokens 8192`. Model served by full filesystem path (not a short HF ID). **Thinking mode ON** — mlx-lm enables Gemma 4 thinking by default. Initial bench used `/opt/homebrew/bin/mlx_lm.server` which silently linked to a python3.11 mlx_lm install lacking Gemma 4 — discovered 2026-05-06 during the bf16+MTP experiment cleanup; the Cellar libexec is the canonical entry point.

### Generation Speed (tok/s)

| Context | mlx-lm server | lm-studio (2026-05-01, for ref) |
|:--------|:-------------:|:-----------------------------:|
| 512 | **20.5** | 21.8 |
| 4K | **20.2** | 21.5 |
| 8K | **19.8** | 21.1 |
| 32K | **17.2** | 18.3 |
| 65K | **14.7** | — (not tested) |

### Prefill Speed (tok/s)

| Context | mlx-lm server | lm-studio (for ref) |
|:--------|:-------------:|:-----------------:|
| 512 | 1,337 | 1,232 |
| 4K | **9,965** | 6,028 |
| 8K | **19,331** | 11,584 |
| 32K | **63,306** | 36,297 |
| 65K | **101,361** | — |

### Time to First Token (seconds)

| Context | mlx-lm server | lm-studio (for ref) |
|:--------|:-------------:|:-----------------:|
| 512 | **0.41** | 0.44 |
| 4K | **0.41** | 0.68 |
| 8K | **0.43** | 0.71 |
| 32K | **0.52** | 0.90 |
| 65K | **0.65** | — |

**Notes:**
- **Gen speed nearly identical to lm-studio** — within 6% across all contexts. The model load path (mlx-lm direct vs. LM Studio MLX runtime) has negligible impact on decode speed.
- **Prefill is dramatically faster on mlx-lm** — 2.5× at 4K (9,965 vs 6,028 tok/s) and 1.7× at 32K (63,306 vs 36,297 tok/s). LM Studio's MLX runtime appears to use a less-optimized prefill kernel. At 65K context, prefill reaches 101K tok/s — the model can ingest long contexts very quickly.
- **TTFT stays sub-0.65 s through 65K** — TTFT is only weakly dependent on context length since prefill is so fast. A 65K-token prompt adds only 0.24 s to TTFT vs 512 tokens.
- **Thinking mode ON:** the model generates thinking context on some prompts (affecting per-turn agent latency), but these throughput numbers measure a simple 50-token completion and thus reflect pure decode bandwidth.

---

## Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm, 2026-05-06 failed experiment)

Model: `mlx-community/gemma-4-31B-it-bf16` (~58 GB) target paired with `mlx-community/gemma-4-31B-it-assistant-bf16` MTP drafter (839 MB). The first end-to-end attempt at Google's [MTP speculative-decoding](https://ai.google.dev/gemma/docs/mtp/mtp) drafter on this stack. The drafter ran cleanly (3.07–4.29 tokens accepted per verification round) but the deployment is **incompatible with streaming agent clients** (opencode hits 300 s timeouts on every run; full failure analysis lives in [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment)).
Tested on **Mac Studio M3 Ultra (96 GB)** — May 6, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context (512, 4K, 8K, 16K). 32K+ OOMs (Metal ~118 GB attempted vs 62 GB cap). Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-mlx-vlm.json`](gemma-4-31b-bf16-mtp/api-server-mlx-vlm.json).

**Server:** `python -m mlx_vlm.server` (mlx-vlm 0.5.0 from main; PyPI 0.4.4 lacks `mlx_vlm.speculative`). Launched with `--draft-model mlx-community/gemma-4-31B-it-assistant-bf16 --draft-kind mtp --draft-block-size 6 --max-tokens 8192`.

### Generation Speed (tok/s)

| Context | bf16 + MTP (mlx-vlm) | 6-bit (mlx-lm, ref) |
|:--------|:--------------------:|:-------------------:|
| 512 | **17.0** | 20.5 |
| 4K | **13.8** | 20.2 |
| 8K | **12.3** | 19.8 |
| 16K | **10.7** | (not benched) |
| 32K | OOM | 17.2 |

### Prefill Speed (tok/s)

| Context | bf16 + MTP (mlx-vlm) | 6-bit (mlx-lm, ref) |
|:--------|:--------------------:|:-------------------:|
| 512 | 180 | 1,337 |
| 4K | 228 | 9,965 |
| 8K | 200 | 19,331 |
| 16K | 122 | (not benched) |

### Time to First Token (seconds)

| Context | bf16 + MTP (mlx-vlm) | 6-bit (mlx-lm, ref) |
|:--------|:--------------------:|:-------------------:|
| 512 | 3.02 | **0.41** |
| 4K | 18.14 | **0.41** |
| 8K | 41.04 | **0.43** |
| 16K | 134.4 | (not benched) |

**Notes:**
- **The drafter matches upstream's own B=1 numbers.** Server logs (`[MTP] batch=1 ... accept=3.07–4.29 rounds=...`) and 12.3 tok/s @ 8K align with the maintainer's reference in [PR #1115](https://github.com/Blaizzy/mlx-vlm/pull/1115): "B=1: 11.7 tok/s, 4.64 acc/round, ≈6.2× over baseline". My install includes #1112 (drafter), #1115 (server dispatch), #1117 (batching follow-up). The drafter is operating at upstream-expected efficiency.
- **B=1 decode being 17 % slower than 6-bit is *expected*.** Upstream documents "MTP works best for B>1"; bf16 weights' bandwidth tax outpaces the speculative speedup at single-request decode. PR #1117's `MLX_VLM_SPEC_BATCH_WAIT_MS` env var (unset in this run) is the upstream-recommended bridge for any concurrent agent workload.
- **TTFT regression** *is* a real distinct issue: 7–95× slower than 6-bit (3.02 s vs 0.41 s @ 512; 41 s vs 0.43 s @ 8K) because `mlx_vlm.server` doesn't expose a prompt cache the way `mlx_lm.server` does.
- **32K and beyond OOM** — drafter-tree allocations push the speculative path past the 62 GB max Metal buffer cap. 16K is the safe ceiling.
- **Streaming SSE flushes for trivial prompts but hangs for long-reasoning prompts.** Confirmed via direct curl probes: `"Reply ok"` produces 35 chunks in 2.69 s with `finish_reason: stop`; `"Browse www.example.com"` produces zero chunks in 360 s. Reproducible. `chat_template.jinja` verified byte-identical to 6-bit's working template — issue [#941](https://github.com/Blaizzy/mlx-vlm/issues/941) ruled out. Likely an upstream bug in mlx-vlm's speculative streaming flush path; worth filing against [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm).
- **Even when streaming works, the agent loop fails.** Server logs show 8192 reasoning tokens per opencode turn at 12.3 tok/s ≈ 666 s — 2× opencode's 300 s wall. `MLX_VLM_SPEC_BATCH_WAIT_MS=10` (PR #1117) doesn't help; it coalesces concurrent requests into batches, but agent loops are sequential.
- **Reverted to 6-bit on mlx-lm** the same session. mlx-vlm-from-main install (`~/mlx-vlm-env/`) and bf16 weights kept on disk for any future upstream-fix re-test.

---

## prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K (GGUF, on lm-studio)

Model: `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` (`Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf`) — prithivMLmods abliteration, mradermacher quantization. 28.51 GB on disk, 26.56 GiB resident at 65536 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 2, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-lm-studio.json](qwen36-35b-a3b-prithiv-aggressive/api-server-lm-studio.json).

**Server:** lm-studio v0.4.12, GGUF runtime (not MLX — note this is `.Q6_K.gguf`, not a safetensors MLX repo). Loaded with `lms load qwen3.6-35b-a3b-uncensored-aggressive --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k -y`. Parser flags not required — LM Studio handles Qwen3 chat-template tool-calls and `<think>` natively for this model.

**Deployment gotcha:** LM Studio memory guardrail (`modelLoadingGuardrails.mode: "high"`) counts only ~24 GB free pages, ignoring ~62 GB inactive/reclaimable — blocks load with "insufficient system resources." Workaround: temporarily set `mode` to `"off"` via `~/.lmstudio/settings.json`, load, restore to `"high"`. See [`qwen36-35b-a3b-prithiv-aggressive-benchmark.md`](../../uncen-model/qwen36-35b-a3b-prithiv-aggressive-benchmark.md) for the full recipe.

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **83.6** |
| 4K | 80.8 |
| 8K | 79.0 |
| 32K | 70.6 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 5,350 |
| 4K | 35,118 |
| 8K | 56,616 |
| 32K | **113,519** |

### Time to First Token (seconds)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **0.10** |
| 4K | 0.12 |
| 8K | 0.15 |
| 32K | 0.29 |

**Notes:**
- **TTFT is flat and sub-300 ms through 32K** — same headline lm-studio GGUF property seen on the 27B-6bit and HauhauCS variants. At 32K the TTFT is 0.29s vs 0.70s on the 27B-6bit run.
- **Generation is ~2.3–2.8× faster than Qwen3.6-27B-6bit** on the same lm-studio (83.6 vs 29.9 tok/s @ 512; 70.6 vs 26.3 tok/s @ 32K). The MoE 3B-active GGUF wins decisively over dense 27B on bandwidth-bound decode.
- **Prefill scales unusually fast:** 5K → 35K → 57K → 114K tok/s across 512 → 32K context. Compare to lm-studio 27B-6bit (MLX): 1K → 8K → 15K → 47K tok/s at the same contexts. The GGUF prefill kernel in LM Studio's GGUF runtime benefits from MoE sparsity more aggressively than the MLX uniform-quant kernel.
- **65K probe not run** — model loaded at exactly `--context-length 65536`; the bench's 65K filler probe fills the context exactly, leaving no headroom for `max_tokens=50`. Would require reloading at 70K context to probe accurately.
- **GGUF vs MLX runtime distinction:** unlike the MLX-safetensors models in the rest of this doc, this model runs through LM Studio's GGUF engine. Prefill rates are not directly comparable to the MLX-based servers — the LM Studio GGUF engine uses its own quantization-kernel path.

---

## Qwythos-9B Claude-Mythos-5-1M Q8_0 (GGUF, on lm-studio)

Model: `empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF` (`Qwythos-9B-Claude-Mythos-5-1M-Q8_0.gguf`) — Qwen3.5-9B dense + vision, empero-ai "uncensored" branding (**not borne out — 1/10 mlabonne, see [writeup](../../uncen-model/qwythos-9b-mythos5-benchmark.md)**). 8.87 GB on disk, 8.87 GiB resident at 131072 context. Smallest model in the stack.
Tested on **Mac Studio M3 Ultra (96 GB)** — June 22, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [api-server-llmster.json](qwythos-9b-mythos5/api-server-llmster.json).

**Server:** lm-studio, GGUF runtime. Loaded with `lms load qwythos-9b-claude-mythos-5-1m --gpu max --context-length 131072 --identifier qwythos-9b-mythos5-q8 -y`. No parser flags required — LM Studio handles the Qwen3 chat-template tool-calls and `<think>` natively. 8.87 GiB sits well below the LM Studio guardrail threshold, so no guardrail dance needed.

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **64.7** |
| 4K | 64.0 |
| 8K | 63.1 |
| 32K | 57.6 |
| 65K | 52.3 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 4,795 |
| 4K | 28,192 |
| 8K | 48,222 |
| 32K | 102,993 |
| 65K | **122,873** |

### Time to First Token (seconds)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **0.13** |
| 4K | 0.15 |
| 8K | 0.17 |
| 32K | 0.32 |
| 65K | 0.53 |

**Notes:**
- **Decode is slower than the larger Qwen3.6-35B-A3B MoE GGUFs** (64.7 vs 83.6 tok/s @ 512 for prithivMLmods) despite being a far smaller model — Qwythos is dense 9 B (full 9 B activated per decode step) vs the MoE's 3 B-active. Bandwidth-bound decode favours the sparse-MoE even at much larger total weights.
- **Prefill and TTFT track the usual lm-studio GGUF profile** — sub-200 ms TTFT through 8K, ~123K tok/s prefill @ 65K.
- **Loaded at full 131072 context**, so the 65K filler probe has headroom (unlike the prithivMLmods/HauhauCS sections capped at 65536).

---

## DavidAU Qwen3.6-40B Heretic Q6_K IMatrix (GGUF, on lm-studio)

Model: `DavidAU/Qwen3.6-40B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking-NEO-CODE-Di-IMatrix-MAX-GGUF` (`Qwen3.6-40B-Deck-Opus-NEO-CODE-HERE-2T-OT-Q6_K.gguf`) — DavidAU Heretic recipe (full abliteration + Deckard/PDK), IMatrix-weighted Q6_K. 30.17 GiB on disk, ~30 GiB resident at 131072 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 3, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-lm-studio.json`](qwen36-40b-davidau-heretic/api-server-lm-studio.json).

**Server:** lm-studio, GGUF runtime. Loaded with `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier 'qwen36-40b-davidau-heretic-q6k' -y`. No parser flags required — LM Studio handles Qwen3 chat-template tool-calls and `<think>` natively.

**Deployment gotcha:** LM Studio memory guardrail (`modelLoadingGuardrails.mode: "high"`) counts only ~24 GB free pages, ignoring 60+ GB inactive/reclaimable — consistently blocks dense 40B + 131K load. Must temporarily set `mode` to `"off"`, load, then restore to `"high"`. See [`docs/servers/lm-studio/summary.md`](../../servers/lm-studio/summary.md) for the full toggle recipe.

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **9.7** |
| 4K | 9.6 |
| 8K | 9.5 |
| 32K | 8.8 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 678 |
| 4K | 5,210 |
| 8K | 10,098 |
| 32K | 32,444 |

### Time to First Token (seconds)

| Context | lm-studio |
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

## Gemma 4 31B-it Q4_K_M + external MTP assistant (mainline llama.cpp, 2026-06-09)

Model: `unsloth/gemma-4-31B-it-GGUF` (`gemma-4-31B-it-Q4_K_M.gguf`, 17.0 GiB) + `MTP/gemma-4-31B-it-MTP-Q8_0.gguf` (491 MiB `gemma4_assistant` external drafter). Dense 31B, Q4_K_M target with external Q8_0 MTP assistant.
Tested on **Mac Studio M3 Ultra (96 GB)** — June 9, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 3 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSONs: [`gemma4-31b-mtp-llama-cpp/api-server-baseline.json`](gemma4-31b-mtp-llama-cpp/api-server-baseline.json) (no MTP), [`gemma4-31b-mtp-llama-cpp/api-server-mtp-n1.json`](gemma4-31b-mtp-llama-cpp/api-server-mtp-n1.json) (winning depth).

**Server:** `llama-cpp-mainline` port 8100, built from `ggml-org/llama.cpp` commit `961e9a3` (contains PR [#23398](https://github.com/ggml-org/llama.cpp/pull/23398) Gemma 4 MTP support and post-merge KV fix [#24277](https://github.com/ggml-org/llama.cpp/pull/24277)). Flags: `-ngl 99 -fa on -np 1 -c 65536 --jinja --reasoning on`. MTP runs add `-md <draft.gguf> --spec-type draft-mtp --spec-draft-n-max <N>`.

### Generation Speed (tok/s)

| Context | Baseline (no MTP) · TTFT · prefill | MTP `n=1` (winner) · TTFT · prefill | Δ decode | MTP `n=2` | MTP `n=4` |
|:--------|:-----------------------------------:|:------------------------------------:|:--------:|:---------:|:---------:|
| 512 (543 in) | 29.89 · 0.29 s · 1,868 K | **33.51** · 0.31 s · 1,753 K | **+12 %** | 31.85 | 23.76 |
| 4K (4128 in) | 28.61 · 0.16 s · 25,724 K | **32.07** · 0.18 s · 22,931 K | **+12 %** | 28.81 | 20.24 |
| 8K (8223 in) | 27.84 · 0.17 s · 48,514 K | **32.02** · 0.19 s · 43,051 K | **+15 %** | 28.98 | 21.11 |
| 32K (32799 in) | 23.75 · 0.23 s · 145,860 K | **25.44** · 0.26 s · 127,970 K | **+7 %** | 23.39 | 17.27 |

**Direct completion probe on `n=1`** (`"In one short sentence, what is MLX?"`): `draft_n=41`, `draft_n_accepted=38` (**92.7 % acceptance** on that request). Full benchmark comparison: [`gemma4-31b-mtp-llama-cpp/comparison.md`](gemma4-31b-mtp-llama-cpp/comparison.md).

### Notes

- **Measured optimum on M3 Ultra: `--spec-draft-n-max 1`.** Deeper drafts (`n=2`, `n=4`) regress below baseline — the Q8_0 drafter's logits diverge enough from the Q4_K_M target that extra candidate tokens are rejected more often than accepted. The PR author's reported optimum was `n=4` on DGX Spark hardware; quantization and backend move the optimum substantially.
- **Gain narrows at 32K (+7 %).** Dense KV bandwidth cost grows with context and the per-token drafter overhead becomes relatively more expensive as decode slows. Still a net positive at all tested contexts.
- **TTFT adds ~20 ms vs baseline** at every context (drafter load on first token). Negligible for generation workloads.
- **Candidate binary not adopted as default.** Post-upgrade Qwen3.6-27B-MTP browse regressed from 28.38 s to 56–60 s (OpenCode first-turn context expanded from 118 to ~8.9 K tokens). Decode microbench improved (+4–7 %) and tool smoke stayed 5/5, but the agent-loop regression makes the upgraded binary unsafe as a drop-in replacement. Source tree stays at `961e9a3`; default executable reverted to `510b5c2`.

---

## DavidAU Gemma 4 31B Heretic Q6_k (GGUF, on lm-studio)

Model: `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` (`gemma-4-31B-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Q6_k.gguf`) — Thinking variant, DavidAU HERETIC + Mystery Fine Tune on Gemma 4 31B dense base. 25.20 GB on disk, 23.47 GiB resident at 131072 context.
Tested on **Mac Studio M3 Ultra (96 GB)** — May 3, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 warmup + 2 measured runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-lm-studio.json`](gemma4-31b-davidau-heretic/api-server-lm-studio.json).

**Server:** lm-studio, GGUF runtime. Loaded with `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier 'gemma4-31b-davidau-heretic-q6k' -y`. No parser flags required — LM Studio handles Gemma 4 tool-calls natively.

### Generation Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | **24.2** |
| 4K | 23.0 |
| 8K | 23.2 |
| 32K | 20.9 |
| 64K | 21.0 |

### Prefill Speed (tok/s)

| Context | lm-studio |
|:--------|:-------:|
| 512 | 1,132 |
| 4K | 12,658 |
| 8K | 20,175 |
| 32K | 54,332 |
| 64K | 53,531 |

### Time to First Token (seconds)

| Context | lm-studio |
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

## 🤖 IBM Granite 4.1 30B Q8_0 (Dense, GGUF) on lm-studio

Model: `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF`

Tested on **Mac Studio M3 Ultra (96 GB)** — 2026-05-05.

**Server:** lm-studio / LM Studio headless on port 1234. Raw JSON: [`granite-4.1-30b-q8/api-server-lm-studio.json`](granite-4.1-30b-q8/api-server-lm-studio.json).

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
- Comparable to Gemma 4 31B-it on lm-studio (18–22 tok/s).

---

## 🤖 DeepSeek-V4-Flash (284B/13B-active `deepseek4` MoE, IQ2XXS-imatrix) on ds4

Model: `deepseek-v4-flash` from `antirez/deepseek-v4-gguf` `IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix` (284 B total / 13 B active, 256-expert MoE, 2-bit routed experts + Q8 attn/shared/out, 81 GB GGUF, MIT).

Tested on **Mac Studio M3 Ultra (96 GB)** — 2026-05-18.

**Server:** `ds4` ("DwarfStar 4", [`antirez/ds4`](https://github.com/antirez/ds4)) — standalone native C + Metal engine, sidecar port 8101, `--ctx 65536` + disk-KV offload. Only Apple-Silicon path for `deepseek4` (unmerged upstream `llama.cpp`; vLLM/SGLang CUDA-only). Raw JSON: [`deepseek-v4-flash/api-server-ds4.json`](deepseek-v4-flash/api-server-ds4.json).

### Generation Speed (tok/s)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **34.6** | 4,512 | 0.12 |
| 4K | 26.9 | 737 | 5.58 |
| 8K | 26.6 | 513 | 16.0 |
| 32K | 25.4 | 4,851 warm / 864 cold | 6.8 warm / 37.9 cold |

**Notes:**
- 284 B total but only **13 B active/token** → flat ~25–35 tok/s decode, far above what a 284 B dense model would manage at 2-bit on Apple Silicon. The MoE sparsity path is what makes this model locally usable.
- **Cold long-context prefill is the bottleneck** (~500–860 tok/s @ 8–32 K) — the Hybrid Compressed-Sparse + Heavily-Compressed Attention does heavy compute on first prefill. `ds4`'s SHA1-keyed **disk KV cache** turns a 37.9 s cold 32 K prefill into a **6.8 s warm** one (5.5×); this is the explicit design intent ("the KV cache is a first-class disk citizen").
- 81 GB weights + 1.3 GB ctx buffers @ 65 K fit a 96 GB-class machine with disk-KV offload; `q4-imatrix` (153 GB) and batiai Q3–Q8 (135–302 GB) do not.

---

## 128K Cross-Model Summary

All models benchmarked at the 128K-context bucket (closest standard size to the 100K-class workload):

| Model | Quant | Server | Gen tok/s | Prefill tok/s | TTFT (s) | Date |
|---|---|---:|---:|---:|---:|---|
| **Qwen3-Coder-Next 6-bit** (Dense 80B + Gated DeltaNet) | 6-bit MLX | vllm-mlx | **44.2** 🥇 | **736** 🥇 | **158.4** 🥇 | 2026-04-18 |
| **Qwen-AgentWorld-35B-A3B** (MoE 35B/3B world model) | GGUF UD-Q6_K | llama-cpp-mainline | 49.4‡ | 632,798‡ | 0.19‡ | 2026-07-01 |
| **Qwen3.6-35B-A3B** (Hybrid MoE 35B/3B + VL) | 6-bit MLX | mlx-openai-server | 35.6 🥈 | 927* | 125.7 🥈 | 2026-04-18 |
| **Qwen3.5-122B-A10B JANG 2S** (MoE 122B/10B) | JANG ~2.1-bit | vllm-mlx (JANG wrapper) | 34.5 | 405† | 323.9 | 2026-04-18 |
| **Qwen3.5-35B-A3B JANG 4K** (MoE 35B/3B) | JANG ~4-bit | oMLX | 33.8 | 295.4 | — | 2026-03-24 (omlx.ai) |
| **Gemma 4 26B-A4B** (MoE 26B/4B + VL) | 4-bit MLX | mlx-openai-server | 27.1 | 1,995 | 65.7 | 2026-04-17 |
| **Qwen3.6-27B Fable-5 LoRA** (Dense 27B + runtime LoRA, ChatML v4) | GGUF Q6_K + LoRA | llama-cpp-mainline | 13.0 | 292,299 | 0.45 | 2026-06-28 |

\* Qwen3.6 prefill at 128K is the lowest of the 35B-class models because the hybrid stack's full-attention layers become memory-bound past 64K  
† Qwen3.5-122B JANG 2S prefill normalised against requested 131,072; against the actual ~116,516-token filler the rate is ~360 tok/s
‡ AgentWorld row is a nominal 120K probe, not the exact 128K bucket. The server prompt cache was warm from the preceding 512-65K sweep, so TTFT/prefill are cache-warm and not comparable to cold-prefill MLX rows.

**Takeaways:**
- For a 100K+-class workload where you need to push generation throughput on a normal assistant/coding model, **Qwen3-Coder-Next 6-bit on vllm-mlx remains the clean comparable winner** — 44.2 tok/s gen at the exact 128K bucket. AgentWorld's 49.4 tok/s at 120K is faster in this cache-warm llama.cpp probe, but it is a language world model rather than an assistant-tuned coder/chat model.
- **Qwen3.6-35B-A3B** is the pick when you also need vision or always-on thinking; the gen-speed cost is ~20% vs Coder-Next, the TTFT is actually lower (125.7 vs 158.4 s) thanks to the hybrid Gated DeltaNet at 35B activation
- **Qwen3.5-122B JANG 2S** delivers competitive 34.5 tok/s gen at 122B parameters by activating only ~10B per token, but the JANG dequantization cost makes prefill at 128K very slow (5+ min TTFT) — choose this only when you need 122B's reasoning quality at long context and can wait for prefill

---

## 🤖 Qwen-AgentWorld-35B-A3B UD-Q6_K on llama.cpp

Model: `unsloth/Qwen-AgentWorld-35B-A3B-GGUF` (`Qwen-AgentWorld-35B-A3B-UD-Q6_K.gguf`, snapshot `3a305abf5cfd119ee999dfe929c433746edd8d63`). Server: `llama-cpp-mainline` on port 8100, launched with `-ngl 99`, `-fa on`, `--jinja`, `--reasoning on`, and `-c 131072`. No MTP/speculative flags: the clean GGUF does not carry MTP tensors/metadata even though the upstream HF config has `mtp_num_hidden_layers=1`.

**Streaming SSE results** (bench_api_server.py, 2 runs median for 512-65K; 120K is a single probe):

| Context | TTFT (s) | Gen (tok/s) | Prefill (tok/s) |
|:--|:--:|:--:|:--:|
| 512 | 0.034 | 81.49 | 15,903 |
| 4K | 0.038 | 80.26 | 108,118 |
| 8K | 0.041 | 77.71 | 200,124 |
| 32K | 0.066 | 69.34 | 494,449 |
| 65K | 0.110 | 60.62 | 594,526 |
| 120K nominal | 0.190 | 49.42 | 632,798 |

The server prompt cache was enabled and warm after the earlier contexts, so the reported prefill/TTFT values are cache-warm. Treat decode as the useful throughput signal; cold prefill still needs a separate restarted-server measurement if it becomes a decision point.

Raw logs: [`logs/qwen-agentworld-35b-a3b-ud-q6k/api-server-llama-cpp-mainline.json`](logs/qwen-agentworld-35b-a3b-ud-q6k/api-server-llama-cpp-mainline.json), [`logs/qwen-agentworld-35b-a3b-ud-q6k/api-server-llama-cpp-mainline-120k-probe.json`](logs/qwen-agentworld-35b-a3b-ud-q6k/api-server-llama-cpp-mainline-120k-probe.json)

---

## 🤖 Qwen3.6-27B Fable-5 LoRA Q6_K on llama.cpp

Model: `hotdogs/qwen3.6-27b-fable5-lora` **ChatML v4** GGUF LoRA (`qwen36-fable5-lora-ChatML(v2+ORPO+ChatML).gguf`) over `unsloth/Qwen3.6-27B-GGUF` `Qwen3.6-27B-Q6_K.gguf`.
Server: `llama-cpp-mainline` on port 8100, launched with `--lora`, `-ngl 99`, `-fa on`, `--jinja`, `--reasoning on`, and `-c 262144` to probe the upper window. Throughput is identical to the prior v1 adapter (same base + same 76 MB LoRA size).

**Streaming SSE results** (bench_api_server.py, 2 runs median; 256K is a single cold run):

| Context | TTFT (s) | Gen (tok/s) | Prefill (tok/s) |
|:--|:--:|:--:|:--:|
| 512 | 0.16 | 21.9 | 3,355 |
| 4K | 0.17 | 21.6 | 25,074 |
| 8K | 0.17 | 21.3 | 48,400 |
| 32K | 0.21 | 19.6 | 157,298 |
| 65K | 0.28 | 17.2 | 231,976 |
| 131K | 0.45 | 13.0 | 292,299 |
| 256K (fully cold) | 1,950 | 8.1 | ~131 |

The 512–131K TTFT/prefill figures are cache-warm (warmup run primes the KV cache; measured-run prefill reuses it, hence the implausibly high "prefill tok/s"). The **256K row is a single fully-cold run** on a freshly restarted server (empty prompt cache, no co-resident models): a 256,025-token prompt prefilled in ~1,950 s (≈131 tok/s genuine cold prefill) then decoded 50 tokens at 8.1 tok/s. This is the first completed near-260K measurement — the 2026-06-22 attempt timed out at 600 s (cancelled at ~200K tokens). An earlier 2026-06-28 probe showed a faster ~1,245 s only because it followed the 512–131K curve and reused the shared `Hello world.` filler prefix via context checkpoints (prefilling just 131K→256K); ~1,950 s is the true fully-cold cost. A nominal 262,144-token prompt is still rejected with HTTP 400 once chat-template overhead is added. The server used about 50 GB RSS. Use 131K as the practical interactive ceiling — a ~30-minute cold prefill is not usable in an agent loop.

Raw logs: [`logs/qwen36-27b-fable5-lora-q6k-131k/`](logs/qwen36-27b-fable5-lora-q6k-131k/)

---

## 🤖 Gemma 4 E4B (~4B, LiteRT-LM) on litert-lm

Model: `litert-community/gemma-4-E4B-it-litert-lm` (3.66 GB `.litertlm`)
Server: `litert-lm serve --api openai` v0.12.0, port 9379, CPU/XNNPACK backend

**Official `litert-lm benchmark` results:**

| Metric | Value |
|:--|:--|
| Prefill | 71.5 tok/s |
| Decode | 13.85 tok/s |
| TTFT (512 input) | 7.2 s |
| Init (cold) | 24.2 s |
| Max context | ~3072 (crashes at 4096) |

**Streaming SSE results** (bench_api_server.py, 2 runs median):

| Context | TTFT (s) | Gen (tok/s)* | Notes |
|:--|:--|:--|:--|
| 512 | 5.0 | 24.4* | Warm (engine already initialized) |
| 2048 | 10.6 | 25.1* | |
| 4096 | — | — | Server crash: `litert_lm_conversation_send_message failed` |

\* SSE gen_tps inflated — server emits per-character chunks, not per-token. True decode from official benchmark: **13.85 tok/s**.

**Notes:** No `usage` stats returned (prompt_tokens/completion_tokens always 0). GPU backend (`gpu_artisan`) produces `<pad>` garbage on Apple Silicon — CPU only. Smallest model in lab (~4B effective). Tool calling not tested via this benchmark (separate API tool-call harness returned 0/5 — handler limitation, not model).

Raw log: [`logs/gemma4-e4b-litert-lm/api-server.json`](logs/gemma4-e4b-litert-lm/api-server.json)

---

## 🤖 LiquidAI LFM2.5-8B-A1B Q8_0 (`lfm2moe` MoE 8.3B/1.5B-active) on llama.cpp

Model: `LiquidAI/LFM2.5-8B-A1B-GGUF` Q8_0 (9.01 GB), chat-template patched for the LFM2 pythonic tool parser
Server: `llama-cpp-mainline` `--jinja` `:8100` (plain, no MTP), `-c 65536`, `-fa on`

**Streaming SSE results** (bench_api_server.py, 2 runs median):

| Context | TTFT (s) | Gen (tok/s) | Prefill (tok/s) |
|:--|:--|:--|:--|
| 512 | 0.03 | **190.6** | 20 K |
| 4 096 | 0.03 | 188.5 | 148 K |
| 8 192 | 0.03 | 185.2 | 277 K |
| 32 768 | 0.04 | 169.9 | 827 K |

Very fast for a 9 GB-footprint model — the ~1.5 B active path holds decode near 170–190 tok/s and TTFT at 30–40 ms across context. lm-studio runtime is comparable for generation (197–209 tok/s ≤4 K, 166–188 @ 8–32 K), but **only llama.cpp can parse the model's pythonic tool calls** — see the [tool-call benchmark](model-benchmark-tool-call.md) and [per-model doc](../per-model/model-summary-lfm2.md). 65 536-context probe overflows the window (prompt + 50 gen tokens exceed `-c 65536`), so 32 768 is the largest measured.

Raw log: [`lfm2.5-8b-a1b-q8/`](lfm2.5-8b-a1b-q8/) (also `api-server-llmster.json` for the lm-studio generation run).

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
