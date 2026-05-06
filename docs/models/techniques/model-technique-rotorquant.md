# RotorQuant — KV-Cache Compression via Block-Diagonal Rotation

## What it is

**RotorQuant** is a runtime KV-cache compression scheme published by [`scrya-com`](https://github.com/scrya-com/rotorquant) as a Clifford-rotor reimagining of the original [TurboQuant](https://arxiv.org/abs/2504.19874) (Google, ICLR 2026). It replaces TurboQuant's dense `d × d` random orthogonal rotation matrix with lightweight Clifford rotors from `Cl(3,0)`, achieving:

- **5.3× faster prefill** vs TurboQuant (per author benchmarks)
- **28% faster decode** vs TurboQuant
- **44× fewer parameters** for the rotation step
- **99.0% attention cosine similarity** (vs TurboQuant's 99.5%) — quality essentially preserved
- **5× KV compression** at 3-bit (`iso3` mode)

The compression is **applied at runtime** to the K and V tensors of the KV cache. It is **weight-format-agnostic** — any quantisation of the model weights (GGUF, MLX, AWQ) can be combined with RotorQuant on the cache. The trade-off is decode-side compute: the inverse rotation + dequant has to run on every attention step, which is cheap with optimised kernels and expensive without.

The `rotorquant` package umbrellas three related variants:

| Variant | Algorithm | Bit-depths | Server support |
|:--|:--|:--|:--|
| **TurboQuant** (`turbo2/3/4`) | Dense orthogonal rotation + Lloyd-Max | 2 / 3 / 4-bit | llama-cpp-turboquant fork (Metal); `arozanov/turboquant-mlx` (MLX, fused Metal kernels); `helgklaizar/turboquant-mlx` (MLX, no fused kernels); upstream llama.cpp **no**; upstream mlx-lm **no** |
| **PlanarQuant** (`planar3/4`) | Givens 2-D rotation + Lloyd-Max | 3 / 4-bit | llama-cpp-turboquant fork (Metal) only |
| **RotorQuant / IsoQuant** (`iso3/4`) | Clifford-rotor / quaternion 4-D rotation + Lloyd-Max | 3 / 4-bit | **llama-cpp-turboquant fork only** — no MLX, no upstream llama.cpp, no vLLM |

## Server compatibility on this stack

| Server | RotorQuant (`iso3/4`) | TurboQuant (`turbo2/3/4`) | PlanarQuant (`planar3/4`) | Notes |
|:--|:--:|:--:|:--:|:--|
| **llama-cpp-turboquant** (port 8099) | ✅ | ✅ | ✅ | Built from [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant) `feature/planarquant-kv-cache`. The only server in this stack that exposes RotorQuant. See [`docs/servers/llama-cpp-turboquant/summary.md`](../../servers/llama-cpp-turboquant/summary.md). |
| `vllm-mlx` | ❌ | ❌ | ❌ | Open feature request: [`vllm#38291`](https://github.com/vllm-project/vllm/issues/38291) |
| `mlx-openai-server` | ❌ | partial⁺ | ❌ | mlx-lm has no built-in TurboQuant cache. Third-party `arozanov/turboquant-mlx` adds it via monkey-patch — not yet integrated here. |
| `mlx_lm.server` | ❌ | partial⁺ | ❌ | Same as mlx-openai-server (shared backend). |
| `vmlx` | ❌ | ❌ | ❌ | vmlx requires `weight_format=mxtq` (JANGTQ Metal kernels), an unrelated weight-quant scheme that internally borrows the "TurboQuant" name. |
| `lm-studio` (LM Studio MLX engine) | ❌ | ❌ | ❌ | Per the `rotorquant` model card: not supported. Use `q8_0` fallback. |
| `dflash-mlx` | ❌ | ❌ | ❌ | Hard-coded Qwen3.6-DFlash drafter pair; no KV-cache hook. |
| `oMLX` | ❌ | ❌ | ❌ | No upstream support. |
| Ollama | ❌ | ❌ | ❌ | Use `OLLAMA_KV_CACHE_TYPE=q8_0` fallback. |
| `transformers` (PyTorch + MPS) | ✅ | ✅ | ✅ | Reference path — `from rotorquant import IsoQuantCache; cache = IsoQuantCache(bits=4); model.generate(..., past_key_values=cache)`. Requires the bf16 base model (~70 GB). Not currently served on this stack — would need a brand-new FastAPI wrapper. |

⁺ The MLX TurboQuant ports (`arozanov/turboquant-mlx`, `helgklaizar/turboquant-mlx`, `rachittshah/mlx-turboquant`, `yzamari/mlx-turboquant`) target only the dense-rotation variant from the original paper. The newer Clifford-rotor RotorQuant has **zero MLX implementations as of 2026-05-06** — the only Apple Silicon path is via the llama.cpp fork.

## How servers integrate it (operational summary)

### `llama-cpp-turboquant` (only path on this stack)

```bash
~/llama-cpp-turboquant/build/bin/llama-server \
  -m <model.gguf> \
  --cache-type-k iso3 --cache-type-v iso3 \
  -ngl 99 -fa on \
  --host 0.0.0.0 --port 8099 -c 65536 --jinja
```

The `--cache-type-{k,v}` flags accept `f32 / f16 / bf16 / q8_0 / q4_0 / q4_1 / iq4_nl / q5_0 / q5_1 / turbo2 / turbo3 / turbo4 / planar3 / iso3 / planar4 / iso4`. Pick `iso3` for RotorQuant 3-bit (the model card's primary recommendation).

Operational details: [`docs/servers/llama-cpp-turboquant/summary.md`](../../servers/llama-cpp-turboquant/summary.md).

## Local empirical findings (2026-05-06, M3 Ultra 96 GB)

Benchmarked on `unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` + `iso3` K + `iso3` V via the `johndpope/llama-cpp-turboquant` fork.

| Aspect | Observation |
|:--|:--|
| Decode tok/s @ 512 | **46.3** (vs Gemma 4 31B-it-MLX-6bit baseline 20.4 — **2.27× faster**) |
| Decode tok/s @ 8 K | 23.2 (still ahead of Gemma 4 baseline 14.7 @ 65 K) |
| Multi-turn smoke loop | **8.48 s** (vs Gemma 4 20.73 s — **2.4× faster**) |
| Cold prefill @ 8 K | ~145 tok/s (slow — iso3 K compression has heavy compute on prefill) |
| Cold prefill @ 32 K | **>600 s (timeout)** — the iso3 K dequant kernel does not yet scale at long fresh prompts |
| Warm TTFT (cache hit) | **0.05–0.11 s** at 512 / 4 K / 8 K |
| KV memory @ 65 K | K (iso3) 640 MiB + V (iso3) 125 MiB = **765 MiB** (vs ~6 GiB for f16 — ~8× compression) |
| Tool calling | ✅ Qwen3.6 native `<tool_call>` XML parsed by llama-server (5/5 single-call) |
| Reasoning channel | ✅ `<think>` blocks land in `reasoning_content`, separate from `content` |

**Workload fit:** great for **agent / multi-turn loops where the prompt prefix is static and re-cached** (warm prefill is ~0.1 s). Poor for **single-shot long fresh prompts** above 16 K (cold prefill kernel slow).

**Headline claim cross-check:** the model card's "5.3× prefill" advantage is realised *vs TurboQuant* (the older variant), not vs `f16`. Against `f16` baseline, iso3 prefill is *slower*; the win is in memory + decode, not prefill.

## When to use it

- **Use** if you need to run Qwen3.6-class models with **very long contexts on tight memory** and are dominated by **agent / multi-turn workloads** (warm prompt cache).
- **Don't use** for single-shot long fresh prompts (RAG over a 50 K freshly-pasted document) — the cold prefill cost dominates.
- **Don't use** if you need MLX (no port exists yet) or if your client speaks only Anthropic API (llama-server is OpenAI-only).

## Known issues

- **`-fa` flag arg shape** — the build under test errors on bare `-fa`. Must use `-fa on` (or `off` / `auto`).
- **Cold prefill super-linear in context length** — needs upstream optimisation; not a blocker for agent workloads but rules out long-document RAG. **Speedup paths under investigation:** see "Faster paths" section below.
- **Asymmetric K/V kernels missing on johndpope's fork.** Tried `--cache-type-k q8_0 --cache-type-v iso3` to keep K prefill fast — failed with `Function kernel_flash_attn_ext_vec_kq8_0_viso3_dk256_dv256 was not found in the library`. Asymmetric K/V is documented on [TheTom's `feature/turboquant-kv-cache` fork](https://github.com/TheTom/llama-cpp-turboquant) (`q8_0-K + turbo3-V`), not johndpope's `feature/planarquant-kv-cache`.
- **Speculative decoding incompatible** — log line: `speculative decoding not supported by this context`. The fork's iso3 cache implementation does not yet support partial-sequence removal, which `common_speculative_is_compat` requires.
- **No PyPI / Homebrew distribution.** Track upstream via `git pull` + rebuild after llama.cpp lands new features.

## Faster paths (community alternatives, not yet validated locally)

Researching the LM Studio bug-tracker issue [`lmstudio-ai/lmstudio-bug-tracker#1719`](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1719) and the canonical llama.cpp discussion [`ggml-org/llama.cpp#20969`](https://github.com/ggml-org/llama.cpp/discussions/20969) surfaces three concrete options that may eliminate the cold-prefill bottleneck. None are wired into this stack today; each is a follow-up experiment.

### Option A — Switch to TheTom's fork on `feature/turboquant-kv-cache` (most likely fix)

[`TheTom/llama-cpp-turboquant`](https://github.com/TheTom/llama-cpp-turboquant) on branch `feature/turboquant-kv-cache` has **graph-side WHT (Walsh-Hadamard Transform) rotation already integrated** — [reported](https://github.com/TheTom/turboquant_plus) to bring TurboQuant prefill to **q8_0 parity (2747 vs 2694 tok/s on M5 Max @ 32 K)**, against `iso3`'s ~145 tok/s on this stack. Trade-off: this branch supports `turbo2/3/4` only, **not `iso3`** (Clifford-rotor). PolarQuant (TurboQuant) and Clifford-rotor (RotorQuant) both achieve ~99% attention cosine similarity vs `f16` per the original [TurboQuant paper](https://arxiv.org/abs/2504.19874) and [scrya-com's RotorQuant figures](https://github.com/scrya-com/rotorquant) — so dropping iso3 for turbo3 is essentially a wash on quality and a strict win on prefill speed. Build instructions same as this runbook, change the `git checkout` branch.

### Option B — Asymmetric `q8_0`-K + `turbo3`-V on TheTom's fork

TheTom's fork explicitly supports asymmetric K/V flags (`--cache-type-k q8_0 --cache-type-v turbo3`) for low-bit weight models. Keeps K cache at fast `q8_0` (eliminating the cold-prefill bottleneck) and only compresses V at 3-bit (still ~half the KV memory savings of full iso3 / turbo3). Tried on johndpope's fork → kernel missing (see Known Issues). Tied to Option A — if you switch forks, you also unlock Option B.

### Option C — `mlx-optiq` PyPI package (drop-in `mlx_lm.server` replacement, MLX-native)

[`pip install mlx-optiq`](https://pypi.org/project/mlx-optiq/) — MLX-native KV-cache compression that monkey-patches `mlx_lm.server.stream_generate` and `maybe_quantize_kv_cache` for per-layer mixed-precision (4 / 8-bit). Drop-in replacement: launch via `optiq serve` instead of `mlx_lm.server`. Reported **+31% decode at 64 K context vs fp16 KV** on Qwen3.5-9B / M3 Max; **+32% prefill / +26% decode** headline. Production-ready for Qwen3.5 (full family) and Qwen3.6-27B as of v0.0.10. **Qwen3.6-35B-A3B not yet listed** in the supported set — would need to test if it loads. Gemma-4 KV is upstream-blocked. If this path works for Qwen3.6-35B-A3B, it removes the GGUF dependency entirely and serves the same MLX 6-bit weights already on disk.

### Other paths surveyed

- [`flovflo/turboquant-mlx-qwen35-kv`](https://huggingface.co/flovflo/turboquant-mlx-qwen35-kv) — standalone CLI bench, Qwen3.5-only.
- [`atomicmilkshake/llama-cpp-turboquant`](https://github.com/atomicmilkshake/llama-cpp-turboquant) — adds TriAttention KV-cache pruning. **CUDA-only**, no Apple Silicon support for the custom features.
- [oMLX TurboQuant toggle (rumour)](https://medium.com/@michael.hannecke/turboquant-on-apple-macos-five-integration-paths-for-local-kv-cache-compression-42e83959d414) — the Medium article claims oMLX has an admin-UI toggle, but the [oMLX README](https://github.com/jundot/omlx) confirms only "block-based KV cache management inspired by vLLM" (paged attention, prefix sharing, hot/cold tiering). **No TurboQuant toggle** as of 2026-05-06. Article is misleading.

### Recommended next experiment

Re-build on **TheTom's `feature/turboquant-kv-cache`** with `--cache-type-k q8_0 --cache-type-v turbo3` for the asymmetric K/V variant. If cold prefill at 32 K drops below 30 s and OpenCode search drops below Gemma 4's 35.55 s baseline, this becomes a real production candidate.

## See also

- Server runbook: [`docs/servers/llama-cpp-turboquant/summary.md`](../../servers/llama-cpp-turboquant/summary.md)
- Upstream fork: [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant)
- Reference Python implementation: [`scrya-com/rotorquant`](https://github.com/scrya-com/rotorquant)
- Original TurboQuant paper: [arXiv 2504.19874](https://arxiv.org/abs/2504.19874) (ICLR 2026)
- vLLM feature request: [`vllm#38291`](https://github.com/vllm-project/vllm/issues/38291)
- TurboQuant on MLX (separate, no RotorQuant): [`arozanov/turboquant-mlx`](https://github.com/arozanov/turboquant-mlx), [`helgklaizar/turboquant-mlx`](https://github.com/helgklaizar/turboquant-mlx)
- Bench data: [`docs/models/benchmarks/qwen36-35b-a3b-rotorquant-iso3/`](../benchmarks/qwen36-35b-a3b-rotorquant-iso3/)
