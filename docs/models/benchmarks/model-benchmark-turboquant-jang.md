# Benchmark: Google TurboQuant KV Cache Compression

Tested on **Mac Studio M3 Ultra (96 GB)** — March 25, 2026.

## 🔎 What is TurboQuant?

Google Research's KV cache compression algorithm (ICLR 2026, [arXiv:2504.19874](https://arxiv.org/abs/2504.19874)). Compresses the key-value cache at runtime to reduce memory usage during long-context inference. It is NOT weight quantization -- it compresses the activations stored per token during generation.

**Two-stage pipeline:**
1. **PolarQuant MSE** -- Random orthogonal rotation + Lloyd-Max scalar quantization (precomputed codebooks, no calibration)
2. **QJL residual** -- 1-bit sign correction via Johnson-Lindenstrauss projection (keys only)

**Key properties:** Data-oblivious (no training), online (quantize as tokens stream in), near-optimal (within 2.7x of information-theoretic bounds).

## ⚙️ Implementation Tested

**Prince Canuma's mlx-vlm PR [#858](https://github.com/Blaizzy/mlx-vlm/pull/858)** -- extracted as standalone `turboquant.py` (3,077 lines). Self-contained module with 9+ custom Metal GPU kernels. Compresses both keys and values (unlike [ananyasingh7/turboquant-mlx-](https://github.com/ananyasingh7/turboquant-mlx-) which only compresses keys).

Prince Canuma's [X post](https://x.com/Prince_Canuma) demonstrated 4.9x KV cache compression on Qwen3.5-35B with zero quality loss.

We monkey-patched `Qwen3NextAttention.__call__` to route decode steps through `TurboQuantKVCache.decode_attention()` and prefill through standard `scaled_dot_product_attention` with dequantized KV states.

**References:**
- [TurboQuant paper](https://arxiv.org/abs/2504.19874) -- Google Research, ICLR 2026
- [Google blog post](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression)
- [Prince Canuma's PR #858](https://github.com/Blaizzy/mlx-vlm/pull/858) -- MLX implementation with Metal kernels
- [ananyasingh7/turboquant-mlx-](https://github.com/ananyasingh7/turboquant-mlx-) -- Alternative MLX port (keys-only, no Metal kernels)
- [flovflo/turboquant-mlx-qwen35-kv](https://huggingface.co/flovflo/turboquant-mlx-qwen35-kv) -- Standalone prototype using MLX built-ins (no custom kernels, no PolarQuant/QJL)

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

Model: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` (~17.5 GB weights, adaptive mixed-precision).

### What is JANG?

[JANG](https://jangq.ai/) is an adaptive mixed-precision quantization format by [JANGQ-AI](https://github.com/jjang-ai/jangq). Unlike uniform quantization (e.g., all weights at 4-bit), JANG assigns different bit widths per layer based on sensitivity analysis: attention layers get 6-8 bit precision while MoE expert layers get 2-4 bit. This achieves 48% smaller model size than standard MLX 8-bit with minimal quality loss.

**Key properties:**
- **Instant mmap load** -- memory-mapped weight files load in <1 second (vs 5-15s for standard MLX safetensors)
- **Same inference path** -- once loaded via `jang_tools.load_jang_model()`, the model runs through standard `mlx_lm` generation with no runtime overhead
- **Requires integration** -- oMLX needs the [AlexTzk fork overlay](../../servers/omlx/jang-fork.md) (PR #364); mlx-lm and vllm-mlx use a [monkey-patch wrapper](../../servers/vllm-mlx/jang-patch.md)

This benchmark tests whether TurboQuant's KV cache compression stacks with JANG weight quantization.

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

### Why the Large Speed Penalty?

1. **Per-token overhead:** TurboQuant runs quantize + dequantize on every generated token. Without fused Metal kernels for the full attention path, this adds significant latency per decode step.
2. **Intermediate buffers:** Rotation matrix multiplication, residual computation, and sign packing create large temporary allocations that compete with KV cache for memory bandwidth.
3. **Architecture mismatch:** Qwen3.5's hybrid design (only 25% of layers use full-attention) already keeps KV cache small. TurboQuant's value is greatest for pure full-attention models with many KV heads.
4. **Quantization format independent:** JANG and standard 4-bit show identical TurboQuant penalties, confirming the bottleneck is in KV cache operations, not weight access.

### When TurboQuant Would Help

- Hybrid-attention models where only a fraction of layers use full-attention KV cache (current sweet spot)
- Pure full-attention models once the per-layer rotation fix lands (see [PR #858 discussion](#pr-858-status--community-findings))
- Concurrent request serving where KV cache pressure is the memory bottleneck
- When fused Metal kernels for quantized attention eliminate intermediate buffer overhead
- Models where KV cache dominates total memory (not the case for Qwen3.5's 2-head hybrid design)

---

## 🧠 PR #858 Status & Community Findings

As of March 27, 2026, [PR #858](https://github.com/Blaizzy/mlx-vlm/pull/858) is still **open** with no new commits since March 25 (the day of our benchmark). Prince Canuma noted in the PR that "this implementation is far from optimal" and he's still working on matching the paper's claimed 8x speedup.

### Full-Attention Model Quality Bug

[kikoncuo](https://github.com/Blaizzy/mlx-vlm/pull/858#issuecomment-4133882463) ran perplexity and passkey-retrieval evaluations and discovered a critical quality issue:

| Model | Architecture | Layers Quantized | PPL (baseline) | PPL (TurboQuant 4-bit) | Passkey Retrieval |
|-------|-------------|-----------------|----------------|------------------------|-------------------|
| Qwen2.5-3B | Full attention (36 layers) | 36/36 (100%) | 11.74 | **243.71** | 0% (was 100%) |
| Qwen3.5-4B | Hybrid (8 attn + 24 SSM) | 8/36 (22%) | 12.03 | **12.14** (+0.10) | 100% |

**Root cause:** The same rotation matrix is shared across all layers, causing quantization errors to accumulate linearly (e1 + e2 + ... + e36 = 36e). With independent rotations per layer, errors would partially cancel (√36·e).

### Layer-Selective Quantization Fix

kikoncuo found that skipping the first and last layers dramatically recovers quality:

| Strategy | Layers Quantized | PPL | Delta vs Baseline |
|----------|-----------------|-----|-------------------|
| FP16 baseline | 0/36 | 12.23 | — |
| **Odd + skip first/last 2** | **16/36 (44%)** | **12.74** | **+0.50** |
| Odd layers only | 18/36 (50%) | 12.78 | +0.55 |
| Skip first/last 2 | 32/36 (89%) | 13.16 | +0.93 |
| All layers | 36/36 (100%) | 255.22 | +242.99 |

**Prince Canuma confirmed** he has a fix in a separate branch with per-layer independent rotations, but hasn't merged it yet. The fix will also slightly improve hybrid model quality (though Qwen3.5 already shows near-zero degradation).

### Implications for Our Benchmark

Our benchmarks used Qwen3.5 (hybrid architecture, 25% full-attention layers), which falls into the "safe" category. The per-layer rotation bug would only affect us if we benchmarked pure full-attention models like Llama, Mistral, or Qwen2.5. When the fix lands, it should be safe to apply TurboQuant to all model architectures.

---

## 🧩 Alternative Implementation: flovflo/turboquant-mlx-qwen35-kv

[flovflo/turboquant-mlx-qwen35-kv](https://huggingface.co/flovflo/turboquant-mlx-qwen35-kv) is a standalone TurboQuant-inspired implementation released March 25, 2026. It takes a fundamentally different approach from PR #858.

### Key Differences from PR #858

| Aspect | flovflo (standalone) | PR #858 (our implementation) |
|--------|---------------------|------------------------------|
| **Metal kernels** | **None** — pure MLX built-ins | **9+ custom Metal GPU kernels** |
| **Quantizer** | MLX built-in affine (`mx.quantize`) | **PolarQuant MSE** (rotation-aware, Lloyd-Max optimal) |
| **Rotation** | Random sign-flip + permutation | **Randomized orthogonal** (proper decorrelation) |
| **Residual correction** | Coordinate sampling (4 random coords, sign×RMS) | **QJL** (Johnson-Lindenstrauss, 1-bit signs) |
| **Value compression** | Optional MLX affine | **Full TurboQuant pipeline** |
| **Sign storage** | bf16 ±1.0 (2 bytes each) | Packed bits via Metal kernels |
| **Code size** | ~400 lines Python | 3,077 lines + Metal shaders |
| **Prefill/decode** | Same path, cache converted post-prefill | Separate optimized paths |

### What flovflo Does Well

- **Clean pip-installable package** with Typer CLI (`tqkv` command)
- **Chunked prefill** with post-prefill cache conversion (avoids quantizing during prefill)
- **Configurable group size** (auto-selects largest power-of-2 dividing head_dim)
- **`from_kvcache()` converter** — cleanly converts standard KVCache to TurboQuant after prefill

### What flovflo Is Missing

1. **No PolarQuant** — uses MLX's generic affine quantizer instead of MSE-optimal rotation-aware codebooks
2. **No real QJL** — picks 4 random coordinates and stores sign×RMS, not a proper Johnson-Lindenstrauss random projection (extremely low expressiveness)
3. **No custom kernels** — all ops through `mx.quantize`/`mx.quantized_matmul` built-ins, adding Python-level per-token overhead
4. **Weaker rotation** — sign-flip + permutation doesn't decorrelate dimensions as effectively as Walsh-Hadamard or structured orthogonal transforms
5. **Sign bits not packed** — packing module exists but is unused in the main path

### Verdict

flovflo is a **lightweight TurboQuant-inspired prototype** useful as a reference for the integration pattern (cache subclass, attention dispatch, post-prefill conversion) but is **not a faithful implementation** of the paper's algorithms. PR #858 is significantly more complete with proper PolarQuant, QJL, and fused Metal kernels.

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/turboquant-pcr/turboquant.py` | Prince Canuma's TurboQuant (from PR #858) |
| `~/turboquant-pcr/benchmark_pcr.py` | 122B benchmark script |
| `~/turboquant-pcr/benchmark_35b.py` | 35B-4bit benchmark script |
| `~/turboquant-pcr/benchmark_jang35b.py` | 35B-JANG benchmark script |
| `~/turboquant-pcr/results/benchmark_*.json` | Raw JSON results |
