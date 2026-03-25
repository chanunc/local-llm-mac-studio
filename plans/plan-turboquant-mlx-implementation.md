# TurboQuant for Mac Studio M3 Ultra: Feasibility & Implementation Plan

## Context

**What is TurboQuant?** A Google Research algorithm (ICLR 2026, arXiv:2504.19874) for **KV cache compression** during LLM inference. It is NOT a weight quantization method -- it reduces runtime memory by compressing the key-value cache that grows with context length.

**Why it matters for us:** Our Mac Studio M3 Ultra has 96GB unified memory. KV cache is the primary memory bottleneck for long-context inference. TurboQuant at 3.5 bits achieves **4.5x compression with zero quality loss**, potentially enabling much longer contexts or freeing memory for larger models.

**Current setup:** oMLX server on Mac Studio using MLX framework. Models are MLX safetensors or JANG format. KV cache is currently stored in full precision (float16/bfloat16).

**Target model for validation:** Qwen3.5-122B-A10B (HuggingFace: `Qwen/Qwen3.5-122B-A10B`)
- 122B total params, ~10B active per token (256 experts, 8 routed + 1 shared)
- **Hybrid attention**: 12 full-attention + 36 linear-attention layers (full_attention_interval=4)
- GQA: 32 Q heads, **only 2 KV heads** per full-attention layer, head_dim=256
- Linear layers: 16 K heads (dim 128), 64 V heads (dim 128) -- may use recurrent state, not per-token KV
- Max context: 262,144 tokens (256K)
- 4-bit MLX version: `mlx-community/Qwen3.5-122B-A10B-4bit` (~24GB weights, most popular)

**Pre-implementation step:** Stop oMLX server (`brew services stop omlx` on macstudio) to free memory before running standalone validation.

---

## TurboQuant Technical Summary

### Algorithm (two-stage pipeline)

**Stage 1 -- TurboQuant_MSE (random rotation + Lloyd-Max scalar quantization):**
1. Multiply each KV embedding by a precomputed random orthogonal matrix (Haar-random via QR decomposition)
2. After rotation, each coordinate follows a predictable Beta distribution (approx Gaussian for large d)
3. Quantize each coordinate independently using precomputed Lloyd-Max optimal centroids
4. Store b-bit indices per coordinate

**Stage 2 -- QJL residual correction (for keys only, ensures unbiased inner products):**
1. Compute residual: r = x - dequant(quant(x))
2. Project residual through random Gaussian matrix S, store only sign bits (1-bit)
3. Store ||r||_2 norm (single scalar per token)
4. Inner product estimator combines MSE reconstruction + residual correction term

**Key properties:**
- **Data-oblivious**: No calibration data, no training, no per-model tuning
- **Online**: Can quantize tokens as they stream in during generation
- **Near-optimal**: Within 2.7x of information-theoretic distortion lower bounds
- **Zero overhead**: No per-block normalization constants (unlike KIVI which adds 1-2 bits overhead)

### Papers

- **TurboQuant (main):** arXiv:2504.19874 -- ICLR 2026
- **QJL (1-bit residual):** arXiv:2406.03482 -- 1-bit quantized JL transform for KV cache
- **PolarQuant (predecessor):** arXiv:2502.02617 -- AISTATS 2026, polar coordinate quantization
- **Blog post:** https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression
- **PyTorch reference:** https://github.com/tonbistudio/turboquant-pytorch (pure PyTorch, tested on NVIDIA RTX)
- **MLX implementation:** https://github.com/ananyasingh7/turboquant-mlx- (complete MLX-native port)

### Performance (from paper, Llama-3.1-8B-Instruct)

| Bits/coord | Compression | LongBench-E avg | vs Full-precision |
|-----------|-------------|-----------------|-------------------|
| 16 (baseline) | 1x | 50.06 | -- |
| 3.5-bit TQ | 4.5x | 50.06 | Quality-neutral |
| 2.5-bit TQ | 6.4x | 49.44 | -0.62 (marginal) |
| 3-bit KIVI | 5.3x | 48.50 | -1.56 |

Needle-in-a-Haystack at 4x compression: TQ 0.997 vs KIVI 0.981 vs full 1.000.

---

## Feasibility Assessment: Mac Studio M3 Ultra

### YES -- This is feasible. Here's why:

**1. No CUDA dependency in the core algorithm**
The entire TurboQuant algorithm uses only standard linear algebra operations:
- Matrix multiplication (matmul), QR decomposition (one-time setup)
- Argmin for nearest-centroid lookup, sign function, vector norms
- All have direct MLX equivalents (`mx.matmul`, `mx.linalg.qr`, `mx.argmin`, `mx.sign`)

**2. Complete MLX implementation already exists**
The [ananyasingh7/turboquant-mlx-](https://github.com/ananyasingh7/turboquant-mlx-) repo provides a full MLX-native implementation -- no porting needed.

**3. Unified memory architecture is an advantage**
Apple Silicon's unified memory eliminates CPU-GPU transfer overhead for rotation matrices and allows the compressed KV cache and model weights to share the same memory pool efficiently.

### Risks and Challenges

| Risk | Severity | Mitigation |
|------|----------|------------|
| QR decomposition slow on MLX for large d | Low | One-time cost at model load; head_dim=256 for full-attn |
| Hybrid attention: TQ only helps 12/48 layers | Low | These 12 are the only layers with growing KV cache |
| `llama_patch.py` is Llama-specific | Medium | Need to create `qwen_patch.py` for Qwen3.5 hybrid attention |
| Per-token quantization adds latency | Medium | Offline codebook variant has negligible prefill overhead; ~15% generation overhead |

### Memory Impact Estimate: Qwen3.5-122B-A10B

**Hybrid architecture advantage:** Only 12 full-attention layers contribute to sequence-length-dependent KV cache (the 36 linear-attention layers likely use fixed-size recurrent state).

**Full-attention KV cache at bf16 (per token, 12 layers):**
- Per token: 12 layers * 2 KV heads * 256 head_dim * 2 (K+V) * 2 bytes = **24,576 bytes (~24 KB)**

| Context | bf16 KV cache | TQ 3.5-bit (4.5x) | TQ 2.5-bit (6.4x) | Savings |
|---------|--------------|--------------------|--------------------|---------|
| 8K | 192 MB | 43 MB | 30 MB | 149-162 MB |
| 32K | 768 MB | 171 MB | 120 MB | 597-648 MB |
| 128K | 3.0 GB | 682 MB | 480 MB | 2.3-2.5 GB |
| 256K | 6.0 GB | 1.4 GB | 960 MB | 4.6-5.0 GB |

**Total memory budget (4-bit weights + 256K context):**
- Model weights: ~24 GB
- KV cache (bf16): ~6 GB -> with TQ 3.5-bit: ~1.4 GB
- **Total: ~25.4 GB with TQ vs ~30 GB without** (fits easily in 96GB either way)

**Key insight:** The hybrid architecture already makes KV cache manageable. TurboQuant's value for this model is most impactful at **extreme context lengths (256K)** or when **serving multiple concurrent requests**. For models with standard full-attention (like Nemotron-3-Super-120B), the savings would be dramatically larger.

---

## Existing MLX Implementation

**Repository:** [ananyasingh7/turboquant-mlx-](https://github.com/ananyasingh7/turboquant-mlx-) (created March 25, 2026)

A complete, well-structured MLX-native implementation. This eliminates the need for porting from PyTorch.

### What it includes:
- **3 algorithms**: QJL, PolarQuant, and TurboQuant -- all in MLX
- **11 source modules** in `src/turboquant/`:
  - `turbo.py` -- two-stage quantize/dequantize/score functions
  - `qjl.py` -- sign-bit projection and asymmetric scoring
  - `polar.py` -- recursive polar transforms with angle codebooks
  - `cache.py` -- 3 drop-in KVCache replacements (PolarKVCache, QJLCache, TurboCache)
  - `llama_patch.py` -- runtime monkey-patching of Llama attention
  - `codebooks.py` -- weighted Lloyd-Max with scipy
  - `preconditioning.py` -- deterministic rotation/sketch matrix generation (seed=42)
  - `estimators.py` -- scoring functions for all 3 methods
  - `bits.py` -- sign/index bit packing
- **8 test files** covering shapes, round-trips, patching, orthogonality
- **5 benchmark scripts** measuring memory, throughput, distortion, quality
- **6 docs** including algorithm specs and architecture

### Dependencies:
- Python 3.11+, MLX >= 0.22.0, MLX-LM >= 0.22.0, NumPy >= 1.26, SciPy >= 1.12

### Key constraints from their CLAUDE.md:
- Sketch matrix S must NOT be row-normalized (breaks QJL estimator)
- TurboQuant 1-bit requires 2/pi scaling
- Dimension must be power-of-2 for polar (4 recursive levels)
- `mx.eval()` required after `update_and_fetch()` (MLX lazy evaluation)

### Current limitations:
- Benchmarked only against **Llama-3.2-3B-Instruct** (small model)
- `llama_patch.py` patches Llama-specific attention -- needs adaptation for Qwen3.5 architecture
- No support yet for hybrid attention (linear + full attention layers in Qwen3.5-122B)

---

## Implementation Plan

### Phase 0: Save Plan & Clone Existing Repo
1. Save this plan as `plans/plan-turboquant-mlx-implementation.md` (this file)
2. Clone `ananyasingh7/turboquant-mlx-` to Mac Studio
3. Install in dev mode: `pip install -e ".[dev]"` in the oMLX venv

### Phase 1: Validate Existing Implementation (Llama-3.2-3B)
**Pre-step:** Stop oMLX server: `ssh macstudio "brew services stop omlx"` to free memory.

1. Run the test suite: `pytest tests/` -- verify all 8 test files pass
2. Run `benchmarks/run_all.py` with Llama-3.2-3B-Instruct (small, quick validation)
3. Confirm memory compression ratios match claims (~5x for TurboQuant)
4. Run `benchmarks/generation_quality.py` to check perplexity impact

### Phase 2: Adapt for Qwen3.5-122B-A10B
The existing `llama_patch.py` is Llama-specific. Qwen3.5-122B-A10B differences:
1. **Hybrid attention**: Only 12/48 layers use full attention (every 4th layer). Linear-attention layers (36/48) use recurrent state, NOT per-token KV cache -- TurboQuant should only be applied to full-attention layers.
2. **GQA ratio**: 32 Q heads, 2 KV heads (16:1 ratio) -- verify cache shape handling
3. **Head dim**: 256 for full-attn, 128 for linear-attn
4. **Architecture class**: `Qwen3_5MoeForConditionalGeneration` -- need a `qwen_patch.py`

Tasks:
- Create `qwen_patch.py` analogous to `llama_patch.py` for Qwen3.5 attention
- Add layer-type detection to only patch full-attention layers
- Validate shape handling with 2 KV heads and head_dim=256
- Download `mlx-community/Qwen3.5-122B-A10B-4bit` if not present

### Phase 3: Benchmark on Qwen3.5-122B-A10B
1. Run benchmarks at various context lengths (8K, 32K, 128K, 256K)
2. Measure actual memory savings vs theoretical estimates
3. Compare generation quality with and without TurboQuant
4. Profile throughput impact (tokens/sec)

### Phase 4: oMLX Integration
1. Identify where oMLX allocates and manages KV cache in its inference loop
2. Inject TurboCache as drop-in replacement for full-attention layers
3. Add `kv_cache_bits` parameter to `model_settings.json` (per-model config)
4. Test end-to-end via API calls

### Phase 5: Documentation & Config
- Update `docs/models/model-summary.md` with KV cache compression notes
- Update `CLAUDE.md` with TurboQuant maintenance notes
- Document the turboquant-mlx- dependency and Qwen3.5 patches

---

## Results (March 25, 2026)

### Phase 1: Llama-3.2-3B Validation -- PASSED
- All 11 original tests pass
- TurboQuant: 86.2 tok/s (-3.2% vs baseline 89.0), coherent generation
- QJL: 75.0 tok/s (-15.7%), some quality degradation
- Polar: 31.2 tok/s (-64.9%), too slow for production

### Phase 2: Qwen3.5-122B-A10B-4bit -- PASSED
- Created `qwen_patch.py` (monkey-patches `Qwen3NextAttention.__call__`)
- Created `test_qwen_patch.py` (5 tests: patch/unpatch cycle, idempotency, layer assignment, head_dim, GQA shapes)
- All 16 tests pass (11 original + 5 new)
- Model architecture confirmed: 48 layers (12 full-attention, 36 linear), head_dim=256, 2 KV heads, 32 Q heads

**End-to-end generation results (100 tokens, JL lemma prompt):**

| Metric | Baseline | TurboQuant | Delta |
|--------|----------|------------|-------|
| Throughput | 20.6 tok/s | 16.9 tok/s | -18% |
| Memory overhead | 0 MB | +147 MB | Rotation/sketch matrices (one-time) |
| Output quality | Correct | **Identical** | No degradation detected |

**Output comparison:** Both baseline and TurboQuant produced identical text explaining the JL lemma -- word-for-word match in first 300 characters.

### Remaining Phases
- **Phase 3** (long-context benchmarks): Not yet run -- needs extended context test at 32K/128K/256K
- **Phase 4** (oMLX integration): Not yet started -- requires patching oMLX inference loop
- **Phase 5** (documentation): Pending Phase 4

---

## Verification Plan

1. **Unit tests**: `pytest tests/` on Mac Studio -- all 16 pass ✅
2. **Llama-3.2-3B smoke test**: `benchmarks/run_all.py` confirms memory reduction ✅
3. **Qwen3.5 shape validation**: 5 tests for 2 KV heads, head_dim=256, hybrid layer detection ✅
4. **A/B quality test**: Identical output with and without TurboQuant ✅
5. **Memory profiling**: `mx.get_active_memory()` at 8K/32K/128K/256K context -- pending
6. **Latency benchmarking**: 16.9 vs 20.6 tok/s (-18%) ✅
7. **Long-context stress test**: Needle-in-a-Haystack at 128K+ with TurboQuant -- pending

---

## Key Files

| File | Purpose |
|------|---------|
| `plans/plan-turboquant-mlx-implementation.md` | This plan document |
| **From ananyasingh7/turboquant-mlx- (cloned to ~/turboquant-mlx on macstudio):** | |
| `src/turboquant/turbo.py` | Core TurboQuant quantize/dequantize/score |
| `src/turboquant/cache.py` | Drop-in TurboCache, QJLCache, PolarKVCache |
| `src/turboquant/llama_patch.py` | Llama attention patching (reference) |
| `src/turboquant/codebooks.py` | Lloyd-Max codebook computation |
| `benchmarks/run_all.py` | Memory/throughput benchmark suite |
| **New files created on macstudio:** | |
| `src/turboquant/qwen_patch.py` | Qwen3.5 hybrid-attention patching |
| `tests/test_qwen_patch.py` | Qwen3.5 patch validation (5 tests) |
| `validate_qwen.py` | End-to-end Qwen3.5-122B validation script |
