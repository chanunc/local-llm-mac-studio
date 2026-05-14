# LM Studio MLX prefill-speed technique

**What it is.** A pair of low-level tuning choices in LM Studio's bundled `mlx-lm` build that together explain why [`lm-studio`](summary.md) can run **3–5× faster end-to-end** than `vllm-mlx` and the upstream `mlx_lm.server` on identical MLX safetensors / GGUF weights for agent-style workloads. Despite the closed-distribution Electron packaging and the `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0` binary filename, neither lever is a proprietary kernel — both are documented in public LM Studio patches and bug reports, and both can be applied to stock `mlx-lm` directly.

This file is the canonical reference for *what the technique is*. The lm-studio runbook ([`docs/servers/lm-studio/summary.md`](summary.md)) cross-links here for the explanation; the production-state pointer in [`docs/current.md`](../../current.md) credits this technique when lm-studio is the live primary.

## The "closed-source" framing is overstated

The wrapper is open source. [`lmstudio-ai/mlx-engine`](https://github.com/lmstudio-ai/mlx-engine) is MIT-licensed and is what LM Studio 0.3.4+ ships pre-bundled. Per its own README it is "primarily a wrapper" built on `mlx-lm`, `mlx-vlm`, and `Outlines` — integration code, not a novel runtime. The `mlx-llm-mac-arm64-apple-metal-advsimd` filename is the build-target string (Apple Silicon, Metal GPU, ARM Advanced SIMD instructions); there is no special instruction-set magic in the name.

What is genuinely closed:

- The Electron app shell, model loader UX, and chat-template auto-detection logic.
- The bundled CPython tarball (`cpython3.11-mac-arm64@10`) and the on-disk layout under `~/.lmstudio/extensions/backends/`.
- The exact pinned versions of `mlx-lm` / `mlx-vlm` / `Outlines` shipped per release — `lms` does not surface a `pip freeze`.

What is **not** closed: the inference-path optimisation recipe, which is the actual source of the prefill lift.

## The two levers

Both are reproducible against stock `mlx-lm` from PyPI / homebrew. They stack: the mechanism is the same on both sides — fewer GPU dispatches, fewer drain/restart cycles per chunk.

| Lever | Stock `mlx-lm` | LM Studio | Public evidence |
|:--|:--|:--|:--|
| `PROMPT_PROCESSING_CHUNK_SIZE` / `prefill_step_size` | 512 | 4096–8192 | [`thornad/lmstudio-mlx-patch`](https://github.com/thornad/lmstudio-mlx-patch): patching 512 → 4096 yields 65 → 129 tok/s (**2.0×**). [`lmstudio-js#507`](https://github.com/lmstudio-ai/lmstudio-js/issues/507): 512 → 8192 yields 1.22× @ 5K, **1.56× @ 18K** on M1 Pro / 30B. Plateau at 8192; 16384 regresses (memory-alloc / launch limits). |
| Per-chunk `mx.eval()` + `mx.clear_cache()` sync barriers | called every chunk | JIT-compiled, batched into one dispatch | [`Blaizzy/mlx-vlm#945`](https://github.com/Blaizzy/mlx-vlm/issues/945): per-chunk eval/clear stalls the GPU pipeline; cost scales with chunk count, not compute. vMLX / LM Studio compile the entire prefill into one kernel when it fits in memory. Quoted: ~10K prefill in **14 s on vMLX vs significantly longer on stock mlx-vlm** on the same M3 Ultra. |

### Lever 1 — chunk size

Historic `mlx-lm` (the era of the public patches below) defaulted `PROMPT_PROCESSING_CHUNK_SIZE` (in `mlx_engine/cache_wrapper.py`) and `prefill_step_size` (in `mlx_lm/generate.py`) to **512**. Each chunk is one GPU dispatch. For a 10K system prompt + tool catalog (typical OpenCode / Claude Code first turn), that was 20 dispatches just for prefill, and dispatch overhead dominated real compute on Apple Silicon.

The public patches measured against this 512 baseline. LM Studio bumps to **4096–8192**: going 512 → 4096 cuts dispatch count 8× and halves prefill wall-time on the `thornad` patch's test (65 → 129 tok/s). Going 512 → 8192 yields the [#507](https://github.com/lmstudio-ai/lmstudio-js/issues/507) M1 Pro numbers: 1.22× @ 5K, **1.56× @ 18K**. The plateau is real — 16384 regresses, attributed in #507 to "memory allocation overhead or GPU kernel launch limits in MLX".

> **Current `mlx-lm`-default note (verified 2026-05-06):** the `mlx_lm.server` shipped in the homebrew `mlx-lm` 0.31.3 formula now defaults to `--prefill-step-size 2048`, **not 512** — the upstream knob has already been moved partway up. The remaining gap to LM Studio is the 2048 → 8192 step, which on our hardware OOMs (see [Local measurement on Mac Studio](#local-measurement-on-mac-studio-m3-ultra-96-gb-2026-05-06)). The 2× / 1.56× public numbers above measure the **historical** lift, not the lift available against today's stock `mlx-lm`.

### Lever 2 — eval / clear_cache barrier elimination

Per [`Blaizzy/mlx-vlm#945`](https://github.com/Blaizzy/mlx-vlm/issues/945), the upstream `mlx_vlm.server` calls `mx.eval()` and `mx.clear_cache()` after every chunk during prompt processing. Each is an explicit GPU sync — the pipeline stalls, drains, the cache is cleared, and the next chunk starts cold. Cost scales with **chunk count**, not compute, so the penalty compounds at long context.

vMLX (and by extension LM Studio's `mlx-engine`) JIT-compile and batch the entire prefill pass into a single GPU dispatch when it fits in memory. The 32K / 512 = 64 sync points become 0. This is why our local `Qwen3.6-27B-6bit` 32K prefill is 47,143 tok/s on lm-studio vs 314 tok/s on vllm-mlx + JANG 4M for the equivalent dense run — a 150× ratio that the chunk-size lever alone cannot explain.

### Why they stack the way they do

- Lever 1 lowers the **per-prefill-token** dispatch overhead by enlarging the work per dispatch.
- Lever 2 removes the **per-dispatch barrier** entirely.

Multiplied at long context, Lever 1 alone is 2× and Lever 2 alone is ~10–50× depending on chunk count, so the combined lift hits the documented 100× regime.

## Server compatibility

Mac Studio M3 Ultra, 96 GB unified memory.

| Server | Lever 1 (chunk size) | Lever 2 (no per-chunk barriers) | Effective prefill |
|:--|:--|:--|:--|
| `lm-studio` (LM Studio bundled `mlx-engine`) | ✅ 4096–8192 | ✅ batched | **47K tok/s @ 32K** |
| `mlx_lm.server` (homebrew Cellar `mlx-lm` 0.31.3) | ✅ 2048 default, `--prefill-step-size` flag exposed (8192 OOMs locally) | ✅ no per-chunk eval | strong — 9,965 tok/s @ 4K, **63,306 tok/s @ 32K** on Gemma 4 31B-it 6-bit, beats lm-studio on prefill across the board on the same weights |
| `mlx-openai-server` | ❌ 512 default | ✅ trie-based prompt caching adjacent | mid-tier; the prefix-cache reuse partially hides the dispatch cost on warm turns |
| `vllm-mlx` (when serving non-`bailing_hybrid`) | ❌ 512 default | ❌ JANG path adds extra eval points | worst — 314 tok/s @ 32K on JANG 4M |
| `mlx_vlm.server` (PR #1115 spec-decode path) | ❌ 512 default | ❌ per-chunk eval/clear_cache (issue #945) | worst on long-reasoning prompts; observed 0-chunk hangs at 360 s in [Gemma 4 31B-it bf16 + MTP drafter](../../models/per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment) |
| `vmlx` (MLX Studio bundled `vmlx_engine`) | ✅ JIT-compiled prefill | ✅ batched | competitive with lm-studio on JANGTQ models |

## What does not contribute

A few things often credited to LM Studio's speed are *not* the source of this lift, in case future investigations chase the wrong target:

- **Apple Advanced SIMD instructions.** The `advsimd` token in the runtime filename is the build target (ARMv8 Advanced SIMD baseline), not a special path. The actual decode kernels are Metal GPU kernels from `mlx-lm`, identical to what stock `mlx-lm` ships.
- **Closed CUDA/Metal kernels.** None known. The `mlx-engine` repo lists only public dependencies.
- **Prompt caching / prefix caching.** LM Studio's [unified-MLX-engine post](https://lmstudio.ai/blog/unified-mlx-engine) reports ~25× faster follow-up TTFT, but that is **prompt-cache reuse on turn 2+** and is orthogonal to the prefill-step-size lever above. vMLX, `vllm-mlx`, and `mlx-openai-server` all support prefix caching too — it is not specific to LM Studio.
- **Quantisation tricks.** lm-studio runs the same MLX safetensors / GGUF files as everyone else, byte-for-byte.

## LM Studio acknowledges the chunk-size knob

[`lmstudio-js#506`](https://github.com/lmstudio-ai/lmstudio-js/issues/506) is titled *"MLX Prompt Processing Slow, 3–4× less than raw python mlx"* — the LM Studio team's own bug-tracker shows historical cases where the Electron path was slower than raw `mlx-lm`. The current lead is the result of accumulated tuning of the same knobs, not a fundamentally different inference architecture. The PyPI default has not been bumped because larger chunk sizes need more peak memory, and `mlx-lm` ships safe defaults for low-RAM laptops.

## Local measurement on Mac Studio M3 Ultra (96 GB), 2026-05-06

We tested whether the chunk-size lever transfers cleanly to our production `mlx_lm.server` (Cellar 0.31.3, Gemma 4 31B-it MLX 6-bit). Two findings invalidate the naive "patch it higher" actionable:

**1. Upstream `mlx_lm.server` default is already 2048, not 512.** The public patch references (`thornad/lmstudio-mlx-patch`, `lmstudio-js#507`) target an older `mlx-lm` default of 512. The current release exposes `--prefill-step-size` as a CLI flag with default **2048**, so there is no need to monkey-patch `generate.py` on a current install — the lever is already partly applied without configuration.

**2. Raising to 8192 OOMs on long context.** Restarting the server with `--prefill-step-size 8192` crashes during a 65K-context request:

```
libc++abi: terminating due to uncaught exception of type std::runtime_error:
[METAL] Command buffer execution failed: Insufficient Memory
(00000008:kIOGPUCommandBufferCallbackErrorOutOfMemory)
```

This happens roughly 60% through prefill on a 65K prompt — the 8192-token activation chunk plus the growing KV cache plus the 6-bit weights exceed the Metal command-buffer ceiling on 96 GB unified memory. Mirrors the public observation in [`lmstudio-js#507`](https://github.com/lmstudio-ai/lmstudio-js/issues/507) that 16384 regresses; on M3 Ultra + Gemma 4 31B 6-bit the cliff is at 8192 for full-window contexts.

**3. We are already past the prefill bottleneck.** Baseline at default 2048 (raw JSON: [`docs/models/benchmarks/logs/gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json`](../../models/benchmarks/gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json)) on Gemma 4 31B-it 6-bit beats lm-studio on prefill across the board on the same weights:

| Context | `mlx_lm.server` @ 2048 (default) | lm-studio | Ratio |
|:--|--:|--:|--:|
| 512 | 1,337 tok/s | 1,232 | 1.09× |
| 4K | 9,965 | 6,028 | 1.65× |
| 8K | 19,331 | 11,584 | 1.67× |
| 32K | 63,306 | 36,297 | 1.74× |

The remaining 5.11 s vs 12.33 s OpenCode browse gap to lm-studio on identical weights is **not prefill-bound** — it's thinking-mode-on output bloat (3–4× more output tokens per turn under `mlx_lm.server`'s default chat template) plus a small decode-rate gap (20.4 vs 21.8 tok/s). Patching `prefill_step_size` higher cannot close that gap.

**Conclusion for our lab.** No `scripts/patches/` entry is added. Production stays on the default `--prefill-step-size 2048`. If a future benchmark drives a model with a smaller activation footprint (e.g., a 13B–20B class model where 8192 fits), revisit the flag at that point — but for Gemma 4 31B 6-bit it OOMs.

## Known limitations of the technique

- **Memory-bound at long context.** Chunk size 8192 needs more peak memory during prefill than 512 — fine on the M3 Ultra's 96 GB, can OOM on 16–32 GB MacBooks.
- **Not always a win on short prompts.** On <2K prefill, dispatch overhead is amortised in either configuration; the win is small. Same for short outputs where decode dominates.
- **Not portable to non-MLX backends.** The chunk-size lever is specific to `mlx-lm`'s prefill loop. `llama.cpp` has its own prefill chunking knob (`--ubatch-size`) tuned independently; the issue and patch above do not transfer.
- **Plateaus / regresses past 8192.** [#507](https://github.com/lmstudio-ai/lmstudio-js/issues/507) documents 16384 as worse than 8192, attributed to memory-allocation overhead or MLX kernel-launch limits.

## Source-code references

- [`lmstudio-ai/mlx-engine`](https://github.com/lmstudio-ai/mlx-engine) — the MIT-licensed wrapper (`cache_wrapper.py` carries the chunk-size constant)
- [`thornad/lmstudio-mlx-patch`](https://github.com/thornad/lmstudio-mlx-patch) — minimal patch + 2× benchmark
- [`lmstudio-js#507`](https://github.com/lmstudio-ai/lmstudio-js/issues/507) — chunk-size 8192 proposal with M1 Pro numbers
- [`lmstudio-js#506`](https://github.com/lmstudio-ai/lmstudio-js/issues/506) — historical regression vs raw `mlx-lm`
- [`Blaizzy/mlx-vlm#945`](https://github.com/Blaizzy/mlx-vlm/issues/945) — per-chunk `mx.eval()` + `mx.clear_cache()` barrier bug, vMLX comparison
- [LM Studio unified MLX engine blog](https://lmstudio.ai/blog/unified-mlx-engine) — official commentary on follow-up TTFT (prompt-cache lift, separate from prefill-step-size)

## Cross-references

- [`docs/servers/lm-studio/summary.md`](summary.md) — server runbook; the [Performance](summary.md#performance-mac-studio-m3-ultra-96-gb) table is the local benchmark this technique explains.
- [`docs/models/per-model/model-summary-gemma.md`](../../models/per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) — Gemma 4 31B-it 6-bit on lm-studio (5.11 s browse / 6.37 s search) vs the same weights on `mlx_lm.server` (12.33 s / 35.55 s) is a clean side-by-side of this technique's impact, modulo thinking-mode default.
- [`docs/models/benchmarks/model-benchmark-api-server.md`](../../models/benchmarks/model-benchmark-api-server.md) — raw cross-server prefill numbers that motivated this writeup.
- [`docs/current.md`](../../current.md) — production-state pointer.
