# TurboQuant & JANGTQ — KV Cache Compression + TurboQuant-Weight Format

Two related-but-distinct things share the "TurboQuant" name in this repo:

1. **TurboQuant** (Google Research, ICLR 2026, [arXiv:2504.19874](https://arxiv.org/abs/2504.19874)) — a **KV cache compression** algorithm. Compresses key-value activations stored per token during generation. Not weight quantisation.
2. **JANGTQ** — JANGQ-AI's **weight format** that bakes TurboQuant-style codebooks into the saved weights and runs through custom Metal kernels at inference time. Loads via `jang_tools.load_jangtq()`. Currently bundled only in MLX Studio's DMG bundled Python ([`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5)).

These two layers can stack: a JANGTQ-weight model (e.g. `MiniMax-M2.7-JANGTQ-CRACK`) is independent of whether the runtime additionally compresses its KV cache.

## TurboQuant — the KV-cache algorithm

Two-stage online compression, applied per token as the cache fills:

1. **PolarQuant MSE** — random orthogonal rotation + Lloyd-Max scalar quantisation (precomputed codebooks, no calibration step).
2. **QJL residual** — 1-bit sign correction via Johnson-Lindenstrauss projection, applied to keys only.

**Properties:** data-oblivious (no training), online (quantize as tokens stream in), near-optimal (within 2.7× of information-theoretic bounds). Google's reported claim: 4.5× compression at 3.5-bit with zero quality loss on Llama-3.1-8B.

### MLX implementations

| Implementation | Metal kernels | Quantizer | Status |
|:--|:--|:--|:--|
| [Prince Canuma's PR #858](https://github.com/Blaizzy/mlx-vlm/pull/858) | **9+ custom kernels** (3,077 lines) | PolarQuant MSE + QJL | Open, not merged. Used in this repo's benchmark. |
| [`flovflo/turboquant-mlx-qwen35-kv`](https://huggingface.co/flovflo/turboquant-mlx-qwen35-kv) | None — pure MLX built-ins | MLX affine (`mx.quantize`) | Lightweight prototype. Missing real PolarQuant + QJL. |
| [`ananyasingh7/turboquant-mlx-`](https://github.com/ananyasingh7/turboquant-mlx-) | None | Keys-only | Reference port. |

PR #858 is the only faithful MLX implementation today.

### Local benchmark results (M3 Ultra, March 25 2026)

`mlx-community/Qwen3.5-35B-A3B-4bit` at 32K context:

| Method | Prefill tok/s | Gen tok/s | KV Mem MB |
|:--|--:|--:|--:|
| baseline | 1,858.8 | **90.3** | 647.4 |
| TurboQuant 3.5-bit | 1,532.0 | 24.4 (-73%) | 213.1 (**3.0×**) |

The same KV compression ratio (3.0× at 32K, 3.4× at 64K) holds whether the weights are MLX 4-bit or JANG 4K — confirming the bottleneck is in KV operations, not weight access. **Generation tok/s drops 67-73%** because PR #858's per-token quantize/dequantize lacks fused-attention Metal kernels and creates large intermediate buffers.

Full numbers across 122B / 35B-4bit / 35B-JANG: [`../benchmarks/model-benchmark-turboquant-jang.md`](../benchmarks/model-benchmark-turboquant-jang.md).

### Known bugs in PR #858

- **Full-attention model quality collapse.** [kikoncuo's analysis](https://github.com/Blaizzy/mlx-vlm/pull/858#issuecomment-4133882463) found Qwen2.5-3B perplexity exploding from 11.74 → 243.71 and passkey retrieval dropping from 100% → 0% when all 36 attention layers are quantised. Root cause: a single shared rotation matrix across layers causes errors to accumulate linearly (36e instead of √36·e). Skipping the first and last 2 layers recovers most of the quality (PPL 12.74 with 16/36 layers). Hybrid-attention models like Qwen3.5 (only ~25% full-attention layers) are unaffected — that is why the local benchmarks hold up.
- **Per-layer rotation fix unmerged.** Prince Canuma confirmed a separate branch with independent per-layer rotations exists but has not landed.

### When TurboQuant helps

- Hybrid-attention models where only a fraction of layers use full-attention KV (current sweet spot).
- Pure full-attention models *once the per-layer rotation fix lands*.
- Concurrent request serving where KV cache pressure is the memory bottleneck.
- Workloads where KV cache dominates total memory (not the case for Qwen3.5's hybrid design).

## JANGTQ — the weight format

JANGTQ is JANGQ-AI's weight format that uses TurboQuant-style codebooks for **weight quantisation** (distinct from the KV-cache algorithm above, despite the name overlap). Loaded via `jang_tools.load_jangtq()` and run through custom Metal kernels (`tq_kernel`, `hadamard_kernel`, `gather_tq_kernel`, `fused_gate_up_kernel`).

### Why vmlx is the only viable server

The public pypi `jang` package **does not ship `load_jangtq` or any of the turboquant Metal kernels** — see [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5). They are bundled exclusively inside the MLX Studio Electron DMG's relocatable Python (`panel/scripts/bundle-python.sh` per the vmlx 1.3.62 CHANGELOG). `vmlx` runs headlessly out of that bundled Python — no GUI session required despite the Electron packaging.

```
$BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
$BP/lib/python3.12/site-packages/jang_tools/load_jangtq.py        ← loader
$BP/lib/python3.12/site-packages/jang_tools/turboquant/*.py       ← Metal kernels
```

`vllm-mlx`, `mlx-openai-server`, `oMLX`, and `dflash-mlx` cannot load JANGTQ today. There is no pip-installable fallback. Install path is the DMG. Server runbook: [`../../servers/vmlx/summary.md`](../../servers/vmlx/summary.md).

### Verifying the fast path

After server startup, the log must contain:

```
JANGTQ v2 loaded in ~10s: <model-name> (0.0-bit avg, native TQ, no dequant)
Replaced <N> modules with TurboQuantLinear / TurboQuantSwitchLinear
```

**Absence of `JANGTQ fast path unavailable`** is the verification that matters — that warning means `vmlx_engine/utils/jang_loader.py` fell back to dequant-and-requant which produces gibberish output on the MiniMax family ([`vmlx#81`](https://github.com/jjang-ai/vmlx/issues/81)).

### Performance — `MiniMax-M2.7-JANGTQ-CRACK` on M3 Ultra

| Prompt tokens | Completion | Elapsed | tok/s (incl. prefill) |
|--:|--:|--:|--:|
| 52 | 523 | 12.0 s | **43.72** |
| 510 | 534 | 13.6 s | 39.42 |
| 2,138 | 308 | 17.2 s | 17.91 |
| 8,407 | 311 | 50.2 s | 6.20 |

At short context, meets the vmlx maintainer's 42 tok/s M3 Ultra baseline ([`vmlx#72`](https://github.com/jjang-ai/vmlx/issues/72)). Aggregate tok/s collapses at long context because the metric bundles prefill into elapsed time. Peak wired RAM during generation ≈ 66.6 GB / 96 GB.

Full deploy + perf detail: [`../uncen-model/minimax-m27-crack-benchmark.md`](../uncen-model/minimax-m27-crack-benchmark.md) (private submodule).

### MLLM tool-use bugs

vmlx 1.0.3 has **three MLLM-path defects** that affect every JANGTQ MLLM model (`is_mllm=True`): `tools[]` silently dropped before the chat template, `_apply_chat_template` ignores tools entirely, multi-turn tool replay crashes on Jinja. Fixed by [`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`](../../../scripts/patches/patch_vmlx_jangtq_mllm_tools.py). Idempotent. **Re-apply after every DMG upgrade.**

### Currently deployed JANGTQ models

| Model | Variant | On-disk | Status |
|:--|:--|--:|:--|
| [`dealignai/MiniMax-M2.7-JANGTQ-CRACK`](https://huggingface.co/dealignai/MiniMax-M2.7-JANGTQ-CRACK) | 230B / ~10B active MoE, 2-bit codebook + 8-bit attn/embed | ~57 GB | Active on vmlx |

Other JANGTQ-CRACK variants (Qwen3.6-VL, Qwen3.5-VL-122B) require the same patch and have the same bug surface.

## Known limitations (combined)

- **Single-vendor dependency for JANGTQ** — loader + Metal kernels live only in the DMG. New DMG install is the only supported path after reinstall. Upstream tracking: [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5).
- **`--smelt` and `--flash-moe` raise on `weight_format=mxtq`** ([`vmlx#81`](https://github.com/jjang-ai/vmlx/issues/81)) — do not pass either flag.
- **No vmlx Homebrew service entry** — launched via `nohup … &`, killed via `pkill -f vmlx_engine`.
- **PR #858 KV-cache TurboQuant is gen-tok/s-negative on Apple Silicon** today — the per-token quantize/dequantize cost outweighs the memory bandwidth savings for the tested models. Use only if KV cache memory is your binding constraint, not for raw throughput.

## See also

- [`../../servers/vmlx/summary.md`](../../servers/vmlx/summary.md) — vmlx server runbook (start/stop, logs, verification)
- [`../../servers/vmlx/maintenance.md`](../../servers/vmlx/maintenance.md) — DMG upgrade lifecycle, MLLM tool patch
- [`../benchmarks/model-benchmark-turboquant-jang.md`](../benchmarks/model-benchmark-turboquant-jang.md) — full PR #858 benchmark (122B / 35B / 35B-JANG)
- [`../uncen-model/minimax-m27-crack-benchmark.md`](../uncen-model/minimax-m27-crack-benchmark.md) — MiniMax-M2.7-JANGTQ-CRACK perf + RAM detail
- [`model-quantization-jang.md`](model-quantization-jang.md) — JANG (the per-layer mixed-precision weight format) — different layer of optimisation, can stack
- [`../../../plans/active/plan-turboquant-mlx-implementation.md`](../../../plans/active/plan-turboquant-mlx-implementation.md) — MLX implementation feasibility plan
- [TurboQuant paper](https://arxiv.org/abs/2504.19874) — Google Research, ICLR 2026
- [Google blog post](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression)
- [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5) — upstream tracking issue for missing pypi loaders
