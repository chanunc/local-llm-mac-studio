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

**Server:** mlx-openai-server v1.7.1 (`model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`, `context_length: 131072`). Reference YAML: [mlx-openai-server-qwen36-35b.yaml](../server/mlx-openai-server/mlx-openai-server-qwen36-35b.yaml). Raw JSON: [qwen36-35b-server-benchmark.json](../server/mlx-openai-server/qwen36-35b-server-benchmark.json).

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

## Qwen3.5-122B-A10B JANG 2S @ 128K

Model: `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S` (122B MoE, ~10B active, JANG 2S ≈2.1-bit average)  
Tested on **Mac Studio M3 Ultra (96 GB)** — April 18, 2026.

**Method:** Streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs at ctx=131,072. Same filler-text generator as the Qwen3.6 / Gemma 4 rows above.

**Server:** vllm-mlx v0.2.6 launched via `~/run_vllm_jang.py serve` wrapper (the JANG monkey-patch path). Single-model. Reference: `CLAUDE.md` "Common Commands" section. Raw JSON: [qwen35-122b-jang2s-128k-benchmark.json](../server/vllm-mlx/qwen35-122b-jang2s-128k-benchmark.json).

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

**Server:** vllm-mlx v0.2.6 launched directly via `~/vllm-mlx-env/bin/vllm-mlx serve` (no JANG wrapper). Single-model. Mode: `Simple (maximum throughput)`. Raw JSON: [qwen3-coder-next-6bit-128k-benchmark.json](../server/vllm-mlx/qwen3-coder-next-6bit-128k-benchmark.json).

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
