# Benchmark: Google TurboQuant KV Cache Compression

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25, 2026.

> **What TurboQuant + JANG are, MLX implementation landscape, full-attention quality bug, flovflo comparison:** [`../techniques/model-quantization-turboquant.md`](../techniques/model-quantization-turboquant.md) and [`../techniques/model-quantization-jang.md`](../techniques/model-quantization-jang.md). This file is benchmark numbers only.

Implementation tested: **Prince Canuma's mlx-vlm PR [#858](https://github.com/Blaizzy/mlx-vlm/pull/858)** (3,077 lines, 9+ custom Metal kernels). Qwen3.5 hybrid models — `Qwen3NextAttention.__call__` monkey-patched to route decode through `TurboQuantKVCache.decode_attention()` and prefill through standard `scaled_dot_product_attention` with dequantized KV states.

---

## 🤖 Results: Qwen3.5-122B-A10B-4bit

Model: `mlx-community/Qwen3.5-122B-A10B-4bit` (~24 GB weights, 48 layers: 12 full-attention + 36 linear-attention).

TurboQuant only applies to the 12 full-attention layers (the 36 linear-attention layers use fixed-size recurrent state, not per-token KV cache).

| Context | Method | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|--------|------------|---------|-----------|---------|
| 512 | baseline | **577.0** 🏆 | **60.0** 🏆 | 165.9 🥈 | 69.75 |
| 512 | turbo 3.5-bit | 362.6 🥈 | 37.3 🥈 | **156.9** 🏆 | 69.75 |
| 8K | baseline | **775.0** 🏆 | **56.6** 🏆 | 327.9 🥈 | 72.31 |
| 8K | turbo 3.5-bit | 706.5 🥈 | 28.5 🥈 | **195.2** 🏆 | 72.31 |
| 32K | baseline | **643.9** 🏆 | **49.8** 🏆 | 849.9 🥈 | 75.82 |
| 32K | turbo 3.5-bit | 581.7 🥈 | 16.5 🥈 | **328.8** 🏆 | 75.82 |
| 64K | baseline | **502.8** 🏆 | **42.1** 🏆 | 1545.9 🥈 | 80.73 |
| 64K | turbo 3.5-bit | 438.6 🥈 | 10.0 🥈 | **505.6** 🏆 | 80.73 |

**KV cache compression ratio:** 2.6x at 32K, 3.1x at 64K (memory delta comparison).

---

## 🤖 Results: Qwen3.5-35B-A3B-4bit

Model: `mlx-community/Qwen3.5-35B-A3B-4bit` (~18.6 GB weights, 40 layers: 10 full-attention + 30 linear-attention).

| Context | Method | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|--------|------------|---------|-----------|---------|
| 512 | baseline | **1770.1** 🏆 | **109.7** 🏆 | 77.4 🥈 | 20.20 |
| 512 | turbo 3.5-bit | 829.1 🥈 | 56.8 🥈 | **69.9** 🏆 | 20.20 |
| 8K | baseline | **2311.6** 🏆 | **103.0** 🏆 | 212.4 🥈 | 21.83 |
| 8K | turbo 3.5-bit | 1890.1 🥈 | 42.8 🥈 | **101.8** 🏆 | 21.83 |
| 32K | baseline | **1858.8** 🏆 | **90.3** 🏆 | 647.4 🥈 | 23.73 |
| 32K | turbo 3.5-bit | 1532.0 🥈 | 24.4 🥈 | **213.1** 🏆 | 23.73 |
| 64K | baseline | **1429.6** 🏆 | **76.3** 🏆 | 1227.4 🥈 | 26.43 |
| 64K | turbo 3.5-bit | 1161.2 🥈 | 15.2 🥈 | **360.7** 🏆 | 26.43 |

**KV cache compression ratio:** 3.0x at 32K, 3.4x at 64K.

---

## 🤖 Results: Qwen3.5-35B-A3B JANG 4K

Model: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` (~17.5 GB weights, adaptive mixed-precision). Tests whether TurboQuant's KV cache compression stacks with JANG weight quantisation. JANG details: [`../techniques/model-quantization-jang.md`](../techniques/model-quantization-jang.md).

| Context | Method | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|--------|------------|---------|-----------|---------|
| 512 | baseline | **1688.5** 🏆 | **103.6** 🏆 | 77.4 🥈 | 19.15 |
| 512 | turbo 3.5-bit | 692.8 🥈 | 54.2 🥈 | **69.9** 🏆 | 19.15 |
| 8K | baseline | **2456.8** 🏆 | **98.0** 🏆 | 212.4 🥈 | 20.72 |
| 8K | turbo 3.5-bit | 1959.4 🥈 | 41.3 🥈 | **101.8** 🏆 | 20.72 |
| 32K | baseline | **1952.6** 🏆 | **86.5** 🏆 | 647.4 🥈 | 22.62 |
| 32K | turbo 3.5-bit | 1594.8 🥈 | 23.9 🥈 | **213.1** 🏆 | 22.62 |
| 64K | baseline | **1485.6** 🏆 | **73.9** 🏆 | 1227.4 🥈 | 25.33 |
| 64K | turbo 3.5-bit | 1197.6 🥈 | 15.0 🥈 | **360.7** 🏆 | 25.33 |

**KV cache compression ratio:** 3.0x at 32K, 3.4x at 64K.

---

## 🔍 Summary

| Model | 32K Gen (baseline) | 32K Gen (turbo) | Penalty | KV Compression |
|-------|-------------------|----------------|---------|----------------|
| 122B-4bit | 49.8 t/s | 16.5 t/s | **-67%** 🏆 | 2.6x |
| 35B-4bit | **90.3 t/s** 🏆 | **24.4 t/s** 🏆 | -73% | **3.0x** 🏆 |
| 35B-[JANG](https://jangq.ai/) | 86.5 t/s 🥈 | 23.9 t/s 🥈 | -72% 🥈 | **3.0x** 🏆 |

### Why the Large Speed Penalty + When TurboQuant Helps + PR #858 Quality Bug + flovflo Comparison

All four discussions live in [`../techniques/model-quantization-turboquant.md`](../techniques/model-quantization-turboquant.md). Headline takeaway for these results: per-token quantize/dequantize without fused Metal kernels dominates; JANG vs standard-4bit weights show identical KV-side penalty; the kikoncuo full-attention quality bug does not affect Qwen3.5's hybrid architecture (which only quantises ~25% of layers).

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/turboquant-pcr/turboquant.py` | Prince Canuma's TurboQuant (from PR #858) |
| `~/turboquant-pcr/benchmark_pcr.py` | 122B benchmark script |
| `~/turboquant-pcr/benchmark_35b.py` | 35B-4bit benchmark script |
| `~/turboquant-pcr/benchmark_jang35b.py` | 35B-JANG benchmark script |
| `~/turboquant-pcr/results/benchmark_*.json` | Raw JSON results |
