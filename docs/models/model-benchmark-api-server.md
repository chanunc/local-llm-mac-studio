# Benchmark: API Server Inference

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25-27, 2026.

## Method

Streaming `/v1/chat/completions` requests via Python `urllib`, parsing SSE `data:` chunks to measure per-token timing. Each test generates 50 tokens at temperature 0.0 across context lengths 512, 8K, 32K, 64K.

**Servers tested:**
- **oMLX** v0.2.20 (Homebrew + AlexTzk JANG fork) -- production server with scheduler, paged KV cache, model hot-swapping
- **mlx-lm.server** v0.31.2 (built-in to mlx-lm) -- thin `ThreadingHTTPServer` wrapper around `stream_generate()`
- **vllm-mlx** v0.2.6 (pip from [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx)) -- vLLM port for Apple Silicon with Uvicorn/FastAPI
- **mlx-openai-server** v1.7.0 (pip from [cubist38/mlx-openai-server](https://github.com/cubist38/mlx-openai-server)) -- FastAPI/Uvicorn server with trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, process isolation for multi-model

JANG model support was added to mlx-lm.server, vllm-mlx, and mlx-openai-server via a ~15-line monkey-patch that intercepts `mlx_lm.load()` / `mlx_lm.utils.load()`, detects JANG model paths (via `jang_tools.loader.is_jang_model()`), and delegates to `jang_tools.load_jang_model()`. All loaders return the identical `mlx_lm.models.qwen3_5_moe.Model` class, so no further changes are needed.

---

## Qwen3.5-35B-A3B-4bit (Standard MLX Quantization)

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

## Qwen3.5-35B-A3B JANG 4K

Model: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`

### Generation Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|-----------|---------|-------------------|---------------|------|
| 512 | **103.6** 🏆 | 100.7 🥈 | 99.4 | 96.3 | -- |
| 8K | **98.0** 🏆 | 95.6 🥈 | 93.9 | 90.7 | -- |
| 16K | -- | -- | -- | -- | 67.8 |
| 32K | **86.5** 🏆 | 83.8 🥈 | 81.3 | 77.6 | 59.9 |
| 64K | **73.9** 🏆 | 71.6 🥈 | 62.8 | 65.1 | 49.0 |
| 128K | -- | -- | -- | -- | 33.8 |

### Prefill Speed (tok/s)

| Context | Standalone | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|-----------|---------|-------------------|---------------|------|
| 512 | **1688.5** 🏆 | 831.0 | 1164.0 🥈 | 824.1 | -- |
| 8K | 2456.8 | **2643.9** 🏆 | 2632.0 🥈 | 2582.2 | -- |
| 16K | -- | -- | -- | -- | 378.5 |
| 32K | 1952.6 | **2164.7** 🏆 | 2160.0 🥈 | 2137.5 | 366.8 |
| 64K | 1485.6 | **1668.4** 🏆 | 1660.0 🥈 | 1657.1 | 341.5 |
| 128K | -- | -- | -- | -- | 295.4 |

### Time to First Token (seconds)

| Context | vllm-mlx | mlx-openai-server | mlx-lm.server | oMLX |
|---------|---------|-------------------|---------------|------|
| 512 | 0.56 🥈 | **0.44** 🏆 | 0.62 | -- |
| 8K | **3.10** 🏆 | 3.11 🥈 | 3.17 | -- |
| 32K | **15.15** 🏆 | 15.17 🥈 | 15.33 | -- |
| 64K | **39.30** 🏆 | 39.47 🥈 | 39.55 | -- |

oMLX results from [omlx.ai leaderboard](https://omlx.ai) (submitted March 24, 2026).

---

## Server Overhead Comparison

Percentage slower than raw standalone at each context length:

### Generation Speed Overhead

| Context | vllm-mlx (4bit) | mlx-lm (4bit) | oMLX (4bit) | vllm-mlx (JANG) | mlx-openai (JANG) | mlx-lm (JANG) | oMLX (JANG) |
|---------|----------------|---------------|-------------|-----------------|-------------------|---------------|-------------|
| 512 | **-3%** 🏆 | -8% 🥈 | -- | **-2%** 🏆 | -4% 🥈 | -7% | -- |
| 8K | **-3%** 🏆 | -8% 🥈 | -- | **-2%** 🏆 | -4% 🥈 | -7% | -- |
| 32K | **-4%** 🏆 | -11% 🥈 | -34% | **-3%** 🏆 | -6% 🥈 | -10% | -31% |
| 64K | **-3%** 🏆 | -13% 🥈 | -36% | **-3%** 🏆 | -12% 🥈 | -15% | -34% |

### Prefill Speed Overhead

| Context | vllm-mlx | mlx-lm.server | oMLX |
|---------|---------|---------------|------|
| 32K | **+11%** 🏆 | +10% 🥈 | -80% |
| 64K | **+13%** 🏆 | +12% 🥈 | -- |

Note: vllm-mlx and mlx-lm.server show *higher* prefill than standalone at longer contexts due to measurement differences (TTFT includes HTTP overhead but server may chunk prefill differently).

---

## Key Findings

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

## vllm-mlx Bug Fix

vllm-mlx v0.2.6 has a bug in `vllm_mlx/utils/tokenizer.py`: the `load_model_with_fallback()` function is missing `return model, tokenizer` after a successful `mlx_lm.load()` call, causing the function to return `None`. Patched locally by adding the missing return statement.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `/tmp/benchmark_server.py` | API benchmark client (SSE streaming, original) |
| `/tmp/benchmark_server2.py` | API benchmark client (SSE streaming, +reasoning_content support) |
| `/tmp/run_mlx_server_jang.py` | mlx-lm.server JANG wrapper |
| `/tmp/run_vllm_jang.py` | vllm-mlx JANG wrapper |
| `~/run_mlx_openai_jang.py` | mlx-openai-server JANG wrapper |
| `~/turboquant-pcr/results/server_*.json` | Raw JSON results |
| `~/vllm-mlx-env/` | vllm-mlx Python 3.12 venv |
| `~/mlx-openai-server-env/` | mlx-openai-server Python 3.12 venv |
