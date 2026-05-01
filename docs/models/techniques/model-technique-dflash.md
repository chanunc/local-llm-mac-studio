# DFlash — Block-Diffusion Speculative Decoding

Last updated: 2026-05-01.

DFlash is a **speculative-decoding** technique published as [arXiv:2602.06036](https://arxiv.org/abs/2602.06036). A small **drafter** model (block-diffusion architecture, conditioned on the target's hidden states) proposes blocks of tokens; the **target** verifies them in parallel in a single forward pass and accepts the longest matching prefix. The published value proposition is **higher decode tok/s without changing target output quality**, conditional on high *draft acceptance* (typically >85%).

DFlash is orthogonal to weight quantisation (the target can be 4-bit / 6-bit MLX while the drafter is bf16) and orthogonal to KV-cache compression. It is a *generation-time technique*, not a model format.

## How it stacks in this repo

| Layer | What it is | Where it lives |
|:--|:--|:--|
| **Server** | `dflash-mlx` (port 8098) — wraps `mlx_lm.server`, runs the verify loop | [`../../servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md) |
| **Target** | Standard MLX safetensors (e.g. `mlx-community/Qwen3.6-35B-A3B-4bit`) | HF cache |
| **Drafter** | Block-diffusion drafter from `z-lab/*` (e.g. `z-lab/Qwen3.6-35B-A3B-DFlash`) | HF cache |
| **Patches** | Three local patches against `dflash-mlx 0.1.4.1` + `mlx-lm 0.31.3` | [`../../../scripts/patches/`](../../../scripts/patches/) |

## Cross-fork landscape (2026-04-30)

Two MLX implementations exist. Numbers from `Qwen/Qwen3.5-4B` + `z-lab/Qwen3.5-4B-DFlash`:

| Fork | Decode tok/s vs other fork | `tools[]` array | `qwen3_5_moe` adapter | Status |
|:--|:--|:--|:--|:--|
| [`bstnxbt/dflash-mlx`](https://github.com/bstnxbt/dflash-mlx) | **Baseline** (1.8–5.5× faster than Aryagm) | Supported | Supported | Used in this repo |
| [`Aryagm/dflash-mlx`](https://github.com/Aryagm/dflash-mlx) | 1.8–5.5× slower | Silently dropped | Missing — rejects Qwen3.6-35B-A3B-4bit | Not used |

Cross-fork raw data: [`../benchmarks/model-benchmark-api-server.md` § bstnxbt vs Aryagm](../benchmarks/model-benchmark-api-server.md#qwen35-4b--dflash-drafter--bstnxbt-vs-aryagm-cross-fork-comparison-2026-04-30).

The `DRAFT_REGISTRY` in `bstnxbt/dflash-mlx 0.1.4.1` only auto-resolves Qwen3.5 family pairs. Qwen3.6 targets must pass `--draft-model` explicitly. There is **no `Qwen3.6-27B-DFlash` drafter** in any fork — Qwen3.6-35B-A3B is the only Qwen3.6 target with a working drafter pair today.

## M3 Ultra regression — investigation

This section summarizes external research on why `dflash-mlx` regresses on the Mac Studio M3 Ultra despite upstream M5 Max speedup claims. It complements the raw local data in [`../benchmarks/model-benchmark-standalone.md`](../benchmarks/model-benchmark-standalone.md#dflash-speculative-decoding--qwen36-35b-a3b-4bit--dflash-drafter).

### Local finding

Local standalone `dflash-benchmark` runs on Mac Studio M3 Ultra + `mlx` 0.31.2 show DFlash underperforming plain `mlx_lm.stream_generate()` on `mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash`.

| Output horizon | Baseline | DFlash | Speedup | Acceptance |
|---:|---:|---:|---:|---:|
| 1024 | 104.29 tok/s | 81.23 tok/s | 0.78x | 70.80% |
| 2048 | 103.54 tok/s | 74.23 tok/s | 0.72x | 68.51% |
| 4096 | 102.73 tok/s | 63.89 tok/s | 0.62x | 64.72% |
| 8192 | 100.99 tok/s | 98.46 tok/s | 0.98x | 77.43% |
| 8192 + `--quantize-draft` | 101.41 tok/s | 106.83 tok/s | 1.05x | 78.67% |

The 8192-token default run appears partly inflated by late text repetition: final-cycle acceptance rises sharply after the prose output collapses into a repetitive tail. That makes the 8k result less representative of normal generation.

### Phase 1 repro result

The upstream-style benchmark does reproduce a strong DFlash win on the same M3 Ultra hardware when the prompt is switched from open-ended essay prose to the upstream math/reasoning task.

| Prompt | Prompt tokens | Baseline | DFlash | Speedup | Acceptance |
|---|---:|---:|---:|---:|---:|
| Upstream math/reasoning | 102 | 100.49 tok/s | 161.64 tok/s | 1.61x | 86.66% |
| Structured JSON | 66 | 101.97 tok/s | 149.27 tok/s | 1.46x | 84.55% |
| Local prose essay | 34 | 100.61 tok/s | 98.88 tok/s | 0.98x | 77.43% |

This materially changes the diagnosis:

- The M3 Ultra is not categorically incapable of benefiting from DFlash.
- The largest driver looks like prompt distribution and resulting acceptance ratio.
- The win is not limited to one hand-picked prompt: structured constrained output also clears the speedup threshold.
- The local regression is real, but it is workload-specific rather than a universal hardware/backend failure.

Raw JSONs: [`standalone-dflash-upstream-prompt-m3ultra.json`](../benchmarks/qwen36-35b-a3b-4bit/standalone-dflash-upstream-prompt-m3ultra.json), [`standalone-dflash-sweep-structured-json.json`](../benchmarks/qwen36-35b-a3b-4bit/standalone-dflash-sweep-structured-json.json)

### External evidence

Search coverage included GitHub, Reddit, DEV/community write-ups, Hugging Face model cards, vLLM/speculators documentation, and NVIDIA forum posts. I did not find an indexed X.com post with concrete DFlash regression debugging data; the useful evidence came from the sources below.

#### Upstream `bstnxbt/dflash-mlx`

Upstream reports strong M5 Max results for the exact Qwen3.6 35B 4-bit pair:

- `Qwen3.6-35B-A3B-4bit`, 8192 tokens: `133.20 -> 177.45 tok/s`, `1.33x`, `87.01%` acceptance.
- Methodology: Apple M5 Max, 64 GB, MLX 0.31.1, stock `mlx_lm.stream_generate()` baseline, three repeats, 60s cooldown, math/reasoning prompt.
- README notes that gains rely on numerical coherence, tape-replay rollback, long-context verify kernels, and high acceptance.

Source: https://github.com/bstnxbt/dflash-mlx

#### Reddit LocalLLaMA launch thread

The author and commenters call out two points that match the local regression:

- On Apple unified memory, quantized targets can already be fast enough that the bf16 draft becomes the bottleneck.
- DFlash was built around Qwen3.5/Qwen3.6 hybrid architectures, but actual speedup varies by target size, quantization, prompt, and hardware.

Source: https://www.reddit.com/r/LocalLLaMA/comments/1skesyq/dflash_speculative_decoding_on_apple_silicon_41x/

#### Sabesh Apple Silicon parameter sweep

A 300-run MLX DFlash sweep found that DFlash can regress when the target/draft pair or prompt class does not fit speculative decoding assumptions.

Key findings:

- Target/draft model variants must match closely; quantization mismatch can lower acceptance enough to make DFlash slower than baseline.
- Deterministic tasks such as code, structured lists, and constrained answers perform better.
- Open-ended or random prompts can fall below `1.0x` speedup because draft-token acceptance drops.
- Block size is workload dependent; 16 was best in that Qwen3.5-4B sweep, but larger values dropped sharply.

Source: https://www.sabesh.space/musings/research/speculative-decoding-in-mlx-using-dflash

#### z-lab issue #60: thinking-mode acceptance collapse

An Apple Silicon user reported Qwen3.5-35B-A3B DFlash moving from `1.30x` speedup with thinking enabled to `0.26-0.36x` with thinking disabled. The issue suggests the drafter was trained on one output distribution and rejects heavily when the chat template changes the distribution.

This matters for tool-calling and structured-output workloads because those often disable thinking.

Source: https://github.com/z-lab/dflash/issues/60

#### z-lab issue #66: long-context decode degradation

Another upstream issue reports decode speed degrading significantly as prompt length grows. This reinforces that long-context DFlash behavior is not solved uniformly across backends.

Source: https://github.com/z-lab/dflash/issues/66

#### Qwen3.6 DFlash GGUF model card

The Qwen3.6 27B DFlash GGUF card documents Qwen3.6-specific fragility:

- Qwen3.6 drafter has sliding-window attention layers.
- Quantizing the drafter too aggressively can collapse acceptance.
- Thinking-mode template behavior can materially change throughput.

Although this is GGUF/CUDA-oriented and for 27B, the architectural warning is relevant to Qwen3.6 DFlash generally.

Source: https://huggingface.co/spiritbuun/Qwen3.6-27B-DFlash-GGUF

#### DEV / vLLM speculators docs

The DEV write-up is mostly architectural, but it states the key operational caveat: DFlash still depends on high target/draft acceptance, and reported gains are author-run, backend-specific, and not yet a field-wide verdict. The vLLM speculators docs describe DFlash as block-parallel drafting conditioned on target hidden states and note that not all hardware configurations have been validated.

Sources:

- https://dev.to/simon_paxton/speculative-decodings-ceiling-just-moved-with-dflash-5764
- https://docs.vllm.ai/projects/speculators/en/latest/user_guide/algorithms/dflash/

### Most likely causes for this repo

| Hypothesis | Likelihood | Reason |
|:--|:--|:--|
| Prompt mismatch | Very high | Same M3 Ultra host swings from `0.98x` on prose to `1.61x` on math and `1.46x` on constrained JSON. |
| Acceptance too low | Very high | Local prose sits at 64-79% acceptance; the winning prompt families are at 84.55-86.66%. |
| M3 Ultra vs M5 Max behavior | Medium | Hardware still matters, but the M3 Ultra can reproduce a meaningful win when acceptance is high. |
| Quantized target / bf16 draft bottleneck | High | Apple unified-memory reports say quantized targets can make the draft path the bottleneck. |
| Chat-template or thinking-mode mismatch | Medium | Needs local sweep; upstream reports show this can be catastrophic. |
| MLX version difference | Medium | Upstream used MLX 0.31.1; local runs used 0.31.2. Worth isolating in a throwaway venv. |
| Model/draft ID mismatch | Low-medium | The pair is documented as supported, but exact tokenizer/template/version should still be verified. |
| Thermal throttling | Low | Three local repeats with 60s cooldown had tight spread. |

### Proposed fix path

The fix is not one patch until the cause is isolated. Use the active plan [`plan-dflash-regression-investigation.md`](../../../plans/active/plan-dflash-regression-investigation.md):

1. Re-run the upstream benchmark exactly on M3 Ultra.
2. Sweep prompt classes: math, code, structured output, agent/tool style, prose, random/creative.
3. Sweep chat-template and thinking-mode settings.
4. Sweep runtime variables: MLX version, latest `dflash-mlx`, `--quantize-draft`, and verify-linear kernel toggles.
5. Validate any winning profile through `dflash-serve`.
6. If still regressed, file upstream with raw JSONs and acceptance-per-cycle evidence.

### Current recommendation

Keep `dflash-mlx` as a workload-gated sidecar rather than a general default. It is now justified for deterministic reasoning-heavy and constrained structured-output tasks that keep acceptance near the mid-to-high 80% range, but it should stay off for open-ended prose and other low-agreement distributions until the broader prompt sweep is complete. For normal agent loops, `llmster` remains the better practical choice; for Ling production, stay on `vllm-mlx`.

## See also

- [`../../servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md) — server runbook (start/stop, logs, port, patches)
- [`../benchmarks/model-benchmark-standalone.md`](../benchmarks/model-benchmark-standalone.md#dflash-speculative-decoding--qwen36-35b-a3b-4bit--dflash-drafter) — raw standalone DFlash benchmarks
- [`../benchmarks/model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md) — cross-fork bstnxbt vs Aryagm comparison
- [`../../../plans/active/plan-dflash-regression-investigation.md`](../../../plans/active/plan-dflash-regression-investigation.md) — active investigation plan
