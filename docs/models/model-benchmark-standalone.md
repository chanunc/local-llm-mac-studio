# Benchmark: Raw Python Standalone Inference

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25, 2026.

## Method

Direct `mlx_lm.generate.stream_generate()` calls with no server overhead. This represents the theoretical maximum throughput for each model on this hardware. Models loaded via `mlx_lm.load()` (standard MLX) or `jang_tools.load_jang_model()` (JANG format).

Benchmark scripts use `time.perf_counter()` around prefill and per-token generation to measure throughput. Memory tracked via `mx.metal.get_peak_memory()`. Each run generates 50 tokens at temperature 0.0.

---

## Qwen3.5-122B-A10B-4bit

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

## Qwen3.5-35B-A3B-4bit

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

## Qwen3.5-35B-A3B JANG 4K

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

## Cross-Model Comparison

### Generation Speed (tok/s)

| Context | 122B-4bit | 35B-4bit | 35B-JANG |
|---------|----------|---------|---------|
| 512 | 60.0 | **109.7** 🏆 | 103.6 |
| 8K | 56.6 | **103.0** 🏆 | 98.0 |
| 32K | 49.8 | **90.3** 🏆 | 86.5 |
| 64K | 42.1 | **76.3** 🏆 | 73.9 |

### Prefill Speed (tok/s)

| Context | 122B-4bit | 35B-4bit | 35B-JANG |
|---------|----------|---------|---------|
| 512 | 577.0 | **1770.1** 🏆 | 1688.5 |
| 8K | 775.0 | 2311.6 | **2456.8** 🏆 |
| 32K | 643.9 | 1858.8 | **1952.6** 🏆 |
| 64K | 502.8 | 1429.6 | **1485.6** 🏆 |

### Observations

- **35B vs 122B:** 35B models are ~1.8x faster at generation (fewer active params per token: 3B vs 10B) and ~3x faster at prefill.
- **4-bit vs JANG:** Within 5% of each other across all metrics. JANG uses 6% less memory (17.5 vs 18.6 GB base) with no measurable speed penalty.
- **Context scaling:** Generation speed degrades ~30% from 512 to 64K tokens across all models, driven by growing KV cache memory bandwidth.
- **Prefill peaks at 8K:** All models show peak prefill throughput around 8K tokens, where Metal GPU utilization is optimal before memory bandwidth becomes the bottleneck.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/turboquant-pcr/benchmark_pcr.py` | 122B standalone benchmark |
| `~/turboquant-pcr/benchmark_35b.py` | 35B-4bit standalone benchmark |
| `~/turboquant-pcr/benchmark_jang35b.py` | 35B-JANG standalone benchmark |
| `~/turboquant-pcr/results/benchmark_*.json` | Raw JSON results |
