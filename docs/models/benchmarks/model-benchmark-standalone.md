# Benchmark: Raw Python Standalone Inference

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25, 2026.

## 🧪 Method

Direct `mlx_lm.generate.stream_generate()` calls with no server overhead. This represents the theoretical maximum throughput for each model on this hardware. Models loaded via `mlx_lm.load()` (standard MLX) or `jang_tools.load_jang_model()` (JANG format).

Benchmark scripts use `time.perf_counter()` around prefill and per-token generation to measure throughput. Memory tracked via `mx.metal.get_peak_memory()`. Each run generates 50 tokens at temperature 0.0.

---

## 🤖 Qwen3.5-122B-A10B-4bit

Model: `mlx-community/Qwen3.5-122B-A10B-4bit`
- 122B total params, ~10B active per token (256 experts, 8 routed + 1 shared)
- Hybrid attention: 12 full-attention + 36 linear-attention layers
- GQA: 32 Q heads, 2 KV heads, head_dim 256
- Weight size: ~24 GB, loaded via `mlx_lm.load()`

| Context | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|------------|---------|-----------|---------|
| 512 | 577.0 | 60.0 | 165.9 | 69.75 |
| 8K | 775.0 | 56.6 | 327.9 | 72.31 |
| 32K | 643.9 | 49.8 | 849.9 | 75.82 |
| 64K | 502.8 | 42.1 | 1545.9 | 80.73 |

---

## 🤖 Qwen3.5-35B-A3B-4bit

Model: `mlx-community/Qwen3.5-35B-A3B-4bit`
- 35B total params, ~3B active per token (128 experts, 8 routed + 1 shared)
- Hybrid attention: 10 full-attention + 30 linear-attention layers
- GQA: 24 Q heads, 2 KV heads, head_dim 192
- Weight size: ~18.6 GB, loaded via `mlx_lm.load()`

| Context | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|------------|---------|-----------|---------|
| 512 | 1770.1 | 109.7 | 77.4 | 20.20 |
| 8K | 2311.6 | 103.0 | 212.4 | 21.83 |
| 32K | 1858.8 | 90.3 | 647.4 | 23.73 |
| 64K | 1429.6 | 76.3 | 1227.4 | 26.43 |

---

## 🤖 Qwen3.5-35B-A3B JANG 4K

Model: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`
- Same architecture as 35B-A3B above
- JANG adaptive mixed-precision quantization (4.0-bit average, 6-8 bit attention, 2-4 bit experts)
- Weight size: ~17.5 GB (6% smaller than standard 4-bit), loaded via `jang_tools.load_jang_model()`
- JANG v2 format loads in ~3 seconds via mmap (zero-copy)

| Context | Prefill t/s | Gen t/s | KV Mem MB | Peak GB |
|---------|------------|---------|-----------|---------|
| 512 | 1688.5 | 103.6 | 77.4 | 19.15 |
| 8K | 2456.8 | 98.0 | 212.4 | 20.72 |
| 32K | 1952.6 | 86.5 | 647.4 | 22.62 |
| 64K | 1485.6 | 73.9 | 1227.4 | 25.33 |

---

## ⚖️ Cross-Model Comparison

### Generation Speed (tok/s)

| Context | 122B-4bit | 35B-4bit | 35B-JANG |
|---------|----------|---------|---------|
| 512 | 60.0 | **109.7** 🏆 | 103.6 🥈 |
| 8K | 56.6 | **103.0** 🏆 | 98.0 🥈 |
| 32K | 49.8 | **90.3** 🏆 | 86.5 🥈 |
| 64K | 42.1 | **76.3** 🏆 | 73.9 🥈 |

### Prefill Speed (tok/s)

| Context | 122B-4bit | 35B-4bit | 35B-JANG |
|---------|----------|---------|---------|
| 512 | 577.0 | **1770.1** 🏆 | 1688.5 🥈 |
| 8K | 775.0 | 2311.6 🥈 | **2456.8** 🏆 |
| 32K | 643.9 | 1858.8 🥈 | **1952.6** 🏆 |
| 64K | 502.8 | 1429.6 🥈 | **1485.6** 🏆 |

### Observations

- **35B vs 122B:** 35B models are ~1.8x faster at generation (fewer active params per token: 3B vs 10B) and ~3x faster at prefill.
- **4-bit vs JANG:** Within 5% of each other across all metrics. JANG uses 6% less memory (17.5 vs 18.6 GB base) with no measurable speed penalty.
- **Context scaling:** Generation speed degrades ~30% from 512 to 64K tokens across all models, driven by growing KV cache memory bandwidth.
- **Prefill peaks at 8K:** All models show peak prefill throughput around 8K tokens, where Metal GPU utilization is optimal before memory bandwidth becomes the bottleneck.

---

## Qwen3.6-35B-A3B 6-bit vs Qwen3.5-35B-A3B JANG 4K

Tested on **Mac Studio M3 Ultra (96 GB)** — April 17, 2026.

**Qwen3.6-35B-A3B-6bit** — loaded via `mlx_vlm.load()` (multimodal handler). Text-only inference. Prefill measured via a 1-token generation call; gen t/s at 512 tokens is the clean reading — at longer contexts the second mlx_vlm.generate() call re-runs prefill, inflating the denominator, so those gen figures are not comparable to stream_generate measurements.

| Context | Prefill t/s | Gen t/s¹ | Peak GB |
|---------|------------|----------|---------|
| 512 | 1,029.6 | 54.7 | 29.90 |
| 8,192 | 2,220.9 | — ² | 31.59 |
| 32,768 | 1,765.5 | — ² | 33.75 |
| ~40,001 | 1,654.3 | — ² | 34.33 |

¹ Only the 512-token gen figure is methodologically clean (prefill cost negligible).
² VLM double-prefill artefact; actual generation speed ≈ 55 t/s across contexts based on 512 measurement.

Note: 64K context was not reached — filler exhausted at ~40K tokens on this run.

---

**Qwen3.5-35B-A3B JANG 4K** — loaded via `jang_tools.load_for_inference()`, generated via `mlx_lm.stream_generate()`. Clean prefill/gen split at first-token boundary.

| Context | Prefill t/s | Gen t/s | Peak GB |
|---------|------------|---------|---------|
| 512 | 1,051.1 | 105.8 | 19.20 |
| 8,192 | 2,348.5 | 99.4 | 20.88 |
| 32,768 | 1,857.8 | 85.6 | 22.95 |
| 65,536 | 1,395.7 | 73.9 | 25.83 |

---

**Head-to-head summary (35B/3B MoE class):**

| | Qwen3.6 6-bit | JANG 4K | Winner |
|--|--|--|--|
| Gen speed (clean 512) | ~55 t/s | 105.8 t/s | JANG 4K ~2× faster |
| Prefill @ 512 | 1,029.6 t/s | 1,051.1 t/s | Tie |
| Prefill @ 8K | 2,220.9 t/s | 2,348.5 t/s | Tie (both linear attention) |
| RAM @ rest | 29.9 GB | 19.2 GB | JANG 4K 36% smaller |
| Vision / video | ✅ | ❌ | Qwen3.6 only |
| Thinking mode | ✅ default | ✗ | Qwen3.6 only |
| MTP (speculative) | ✅ built-in | ❌ | Qwen3.6 only |

Conclusion: JANG 4K is ~2× faster for generation and uses ~36% less RAM. Qwen3.6 trades that for vision input, native thinking, and a newer hybrid architecture. Use Qwen3.6 when vision or reasoning is needed; use JANG 4K for maximum coding throughput.

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/turboquant-pcr/benchmark_pcr.py` | 122B standalone benchmark |
| `~/turboquant-pcr/benchmark_35b.py` | 35B-4bit standalone benchmark |
| `~/turboquant-pcr/benchmark_jang35b.py` | 35B-JANG standalone benchmark |
| `~/turboquant-pcr/results/benchmark_*.json` | Raw JSON results |
| `/tmp/benchmark_qwen36.py` | Qwen3.6 VLM benchmark (mlx_vlm) |
| `/tmp/benchmark_jang.py` | JANG 4K benchmark (jang_tools + mlx_lm 0.31.1) |
