# Multiverse Computing HyperNova 60B (CompactifAI)

CompactifAI-compressed derivative of **`openai/gpt-oss-120b`** published by **Multiverse Computing** ([org](https://huggingface.co/MultiverseComputingCAI), [2602 launch press](https://multiversecomputing.com/resources/multiverse-computing-opens-full-access-to-hypernova-60b-2602-on-hugging-face), [CompactifAI page](https://multiversecomputing.com/compactifai), [CompactifAI paper arXiv:2401.14109](https://arxiv.org/html/2401.14109v2)). **60 B total / 4.8 B active**, gpt-oss MoE architecture with `num_local_experts` reduced from 128 to 80 via Matrix Product Operator (MPO) decomposition, weights repacked into native MXFP4 (BF16 attn/router + U8-packed MXFP4 experts). Apache-2.0. Two checkpoints exist on HuggingFace: **2602** (initial release, 2026-02-24) and **2605** (refresh, "sharper at coding").

This is a **candidate experiment** for the lab — not yet deployed, not yet benchmarked here. The compression-technique slot it would occupy (quantum-inspired tensor-network compression) is currently empty in [`docs/models/techniques/`](../techniques/).

## Overview

- [Architecture](#architecture) — what changed vs upstream gpt-oss-120b (only `num_local_experts: 80`)
- [CompactifAI — how the compression works](#compactifai--how-the-compression-works) — MPO/SVD bond-dimension truncation, why it does not need a custom runtime
- [Performance claims and what they actually mean](#performance-claims-and-what-they-actually-mean) — the Multiverse benchmark table, "sharper at coding" caveat
- [Tool-calling — harmony-format inheritance](#tool-calling--harmony-format-inheritance) — same parser story as gpt-oss-120b, with the documented gotchas
- [Runtime path on Mac Studio — conversion is mandatory](#runtime-path-on-mac-studio--conversion-is-mandatory) — why transformers+MPS OOMs; MLX vs GGUF tradeoff
- [Server-fit matrix on this stack](#server-fit-matrix-on-this-stack) — which runtimes can host the converted weights
- [Quantization candidates](#quantization-candidates) — MLX MXFP4-Q4 / MXFP4-Q8 / GGUF MXFP4 (none uploaded yet for HyperNova)
- [Recommended path — convert to MLX, host on vmlx-swift-lm or oMLX](#recommended-path--convert-to-mlx-host-on-vmlx-swift-lm-or-omlx)
- [Verification recipe — three layers](#verification-recipe--three-layers) — agent loop first, then LiveCodeBench, then AIDER
- [Open questions](#open-questions)
- [See also](#see-also)

## Architecture

From the [HuggingFace config.json](https://huggingface.co/MultiverseComputingCAI/Hypernova-60B-2605/raw/main/config.json):

- **`architectures: ["GptOssForCausalLM"]`**, **`model_type: "gpt_oss"`** — stock transformers gpt-oss class
- **32 decoder layers**, alternating `sliding_attention` / `full_attention`
- Hidden size **2880**, **64 query heads / 8 KV heads**, head dim 64
- **`num_local_experts: 80`** (vs **128** in upstream `openai/gpt-oss-120b`) — the only structural change CompactifAI makes
- **`num_experts_per_tok: 4`** (top-4 routing)
- Context length **131,072** via YaRN (`factor: 32.0`, `original_max_position_embeddings: 4096`)
- `rope_theta: 150000`, `sliding_window: 128`, `swiglu_limit: 7.0`
- **`quantization_config.quant_method: "mxfp4"`** with `modules_to_not_convert` covering `self_attn`, `mlp.router`, `embed_tokens`, `lm_head` — exactly the upstream gpt-oss MXFP4 layout
- Vocab **201,088**, harmony BOS/EOS/PAD ids (`199998`/`200002`/`199999`)
- **No `auto_map`**, no `modeling_*.py` files in the repo → no custom runtime code required; transformers' built-in `GptOssForCausalLM` loads it

On-disk shape: 7 safetensors shards totalling **~32 GB** (4.82 + 4.97 × 5 + 4.46 GB). Tensor dtypes `BF16` (kept BF16 modules) + `U8` (MXFP4 packed MoE experts, 2 nibbles per byte). Versus upstream gpt-oss-120b at ~65 GB → ~50 % size reduction, all from the 128→80 expert count drop.

The 4.8 B "active parameters" figure follows from top-4-of-80 routing across MoE layers; in upstream gpt-oss-120b the same routing across 128 experts gives ~5.1 B active, so CompactifAI also marginally reduces active params.

## CompactifAI — how the compression works

CompactifAI ([Multiverse Computing](https://multiversecomputing.com/compactifai), [arXiv:2401.14109v2](https://arxiv.org/html/2401.14109v2)) decomposes self-attention and MLP weight matrices via Matrix Product Operators (MPOs):

1. Take a weight matrix `W ∈ R^{m × n}` from a Linear layer.
2. Run sequential SVDs along reshaped tensor legs, retaining only the top χ singular values at each cut (χ = "bond dimension").
3. Store the truncated MPO factor tensors — total parameter count drops as a function of χ.
4. **Critically: re-multiply the factors back into a dense `W'` of the same `(m, n)` shape before publishing.** The compressed model on HuggingFace is a *lower-rank approximation* of the original, not a model that runs MPOs at inference time.

Evidence the factors are pre-merged in HyperNova-60B-2605:

- No `modeling_*.py` files in the HF repo
- No `auto_map` in `config.json`
- Tensor layout is standard `GptOssForCausalLM` (verified by config.json `architectures` + `model_type`)
- `mlx-community/gpt-oss-120b-MXFP4-Q4` conversion precedent shows `mlx_lm.convert` succeeds on the gpt-oss architecture without custom code

**Consequence for the lab:** CompactifAI's runtime story is a non-issue. The compressed model loads like any other gpt-oss derivative — the win is on disk (and in dequant memory, and in tok/s on bandwidth-bound MoE), not in a new inference kernel. This is structurally different from JANG / JANGTQ / RotorQuant / DFlash / Markovian RSA, which require runtime support.

Compression budget per CompactifAI's own claims: up to 93 % memory reduction at 2-3 % accuracy drop. HyperNova at 32/65 GB is a ~50 % reduction, well within the comfortable regime.

## Performance claims and what they actually mean

Multiverse publishes a benchmark table on the [Hypernova-60B-2605 model card](https://huggingface.co/MultiverseComputingCAI/Hypernova-60B-2605):

| Benchmark | gpt-oss-120b | HyperNova 2602 | **HyperNova 2605** |
|:--|--:|--:|--:|
| LiveCodeBench | 62.75 | 51.53 | **68.68** |
| AIDER | 43.60 | 26.20 | **34.20** |
| IFBench | 67.01 | 59.40 | **66.57** |
| SciCode | 41.52 | 33.53 | **36.00** |
| Terminal Bench | 24.24 | 12.12 | **15.91** |

Reading:

- **"Sharper at coding" = sharper than 2602, not sharper than gpt-oss-120b.** 2605 beats 2602 across every row, but vs the uncompressed parent it only wins on LiveCodeBench (68.68 vs 62.75) and loses everywhere else.
- The LiveCodeBench result is the most striking — a 50 %-compressed model out-performing its parent on a contamination-controlled coding eval — and therefore the most worth scrutinising. Plausible explanations: 2605 added coding-focused SFT/RL on top of the compression; eval was run at a different reasoning level; LCB version drift between Multiverse's run and the upstream gpt-oss-120b figure.
- **AIDER -9 pts vs parent** is the cautionary signal: a multi-file editing benchmark closer to real coding-agent workloads, where CompactifAI compression cost capability.
- **Terminal Bench drop from 24.24 → 15.91** suggests agent-style tool-use under shell environments degrades more than single-shot coding.

External baselines for cross-checking: [vals.ai LiveCodeBench](https://www.vals.ai/benchmarks/lcb), [LiveCodeBench leaderboard](https://livecodebench.github.io/leaderboard.html), [BigCodeBench leaderboard](https://bigcode-bench.github.io/) — all host independent gpt-oss-120b runs.

The model card does **not** publish HumanEval, MBPP, BigCodeBench, SWE-bench, EvalPlus, MMLU, or GPQA numbers for either checkpoint, which makes cross-family comparisons against the rest of the lab roster (Granite 4.1, Gemma 4, Qwen3.6, Ling) indirect.

## Tool-calling — harmony-format inheritance

The model card states verbatim:

> "use the same [harmony response format] as gpt-oss-120b where applicable; behavior may differ otherwise"
> "Tool-calling behavior follows OpenAI-style schemas; compatibility refers to format and structure — exact parity with the base or other models is not guaranteed"

Implication: HyperNova inherits the full gpt-oss harmony-parser ecosystem, including its known friction points:

- **Harmony is non-standard.** OpenAI shipped a [standalone `harmony` Python library](https://huggingface.co/blog/faster-transformers) because the format doesn't cleanly map to existing Jinja chat templates. Most runtimes implement their own approximate parser; drift bugs are common.
- **llama.cpp** had a tool-call crash on gpt-oss with `--jinja --reasoning-format none` until patched ([discussion #15341](https://github.com/ggml-org/llama.cpp/discussions/15341)). Working now, but each version bump risks regression.
- **LM Studio** wrote a third independent harmony parser with documented phase-isolation bugs (reasoning/tool phases not decoupled in some prompt shapes).
- **vLLM** had a dedicated tool-calls bug ([vllm#22337](https://github.com/vllm-project/vllm/issues/22337)).
- **Failure mode**: when the parser misfires, the model emits literal harmony tokens (`<|start|>assistant<|channel|>commentary…`) into the assistant message — same class of failure flagged in [`feedback project_jangtq4_search_hang_layer.md`](../../../.. /memory/project_jangtq4_search_hang_layer.md) for Qwen3 XML. Run an API-level harness first to isolate parser vs model.

**Stack-specific prediction:**

- On **lm-studio** — likely flaky out of the gate; LM Studio's harmony parser is the bug-prone third implementation.
- On **vmlx-swift-lm / Osaurus** — gpt-oss is **not listed** in the documented native family handlers in [`docs/servers/vmlx-swift-lm/summary.md`](../../servers/vmlx-swift-lm/summary.md) (Gemma 4, Mistral Small 4, Qwen 3.5 / 3.6, DeepSeek-V4, NemotronH, Hunyuan v3, MiniMax M2.7, ZAYA). Verify before deploying — may need a parser flag, may need engine work.
- On **mlx-openai-server** — no harmony parser shipped; would render raw harmony tokens.

## Runtime path on Mac Studio — conversion is mandatory

**No-conversion (transformers + MPS) does not fit.** MXFP4 dequantisation on Apple Silicon falls through to `Mxfp4Config(dequantize=True)` (Triton MXFP4 kernels are CUDA-only, sm75+, per [transformers PR #39940](https://github.com/huggingface/transformers/pull/39940)). 4-bit MXFP4 → BF16 is a 4× expansion: ~30 GB MoE × 4 + ~4 GB attn + ~2 GB KV ≈ **126 GB**, vs 96 GB unified memory. OOM at load. HuggingFace discussions [#21](https://huggingface.co/openai/gpt-oss-20b/discussions/21) / [#61](https://huggingface.co/openai/gpt-oss-20b/discussions/61) confirm the failure pattern on M-series.

Conversion paths that work:

| Format | Tool | Size | Native runtime | Status |
|:--|:--|--:|:--|:--|
| **MLX** | `mlx_lm convert --hf-path … --q-bits 4` (`mlx_lm ≥ 0.27.0` per `mlx-community/gpt-oss-120b-MXFP4-Q4` precedent) | ~32–35 GB | vmlx-swift-lm, mlx-openai-server, oMLX | Untested for HyperNova; precedent strong |
| **GGUF** | `convert_hf_to_gguf.py` from llama.cpp main | ~32 GB MXFP4 native | lm-studio, llama.cpp, llama-cpp-turboquant | Untested for HyperNova; `bartowski`/`ggml-org` gpt-oss-120b GGUFs prove the path |

No `mlx-community` or `bartowski` or `unsloth` upload of HyperNova-60B exists as of 2026-05-14 — a self-conversion would be the first community upload.

## Server-fit matrix on this stack

| Server | Status | What it would need |
|:--|:--|:--|
| **`vmlx-swift-lm` (Osaurus, port 1337)** | candidate | MLX bundle in `~/.osaurus/models/MultiverseComputingCAI/Hypernova-60B-2605/`. gpt-oss handler is **not listed** among the documented native families ([runbook](../../servers/vmlx-swift-lm/summary.md)) — verify support or fall back to oMLX. Same `OSU_MODELS_DIR` override required. |
| **`oMLX` (port 8000)** | candidate | MLX bundle in `~/.omlx/models/MultiverseComputingCAI/Hypernova-60B-2605/`. Cleanest path — oMLX handles arbitrary MLX safetensors + JANG without per-family code. Update `~/.omlx/model_settings.json` for context size. |
| **`mlx-openai-server` (port 8000)** | candidate | Add to `~/mlx-openai-server-multimodel.yaml`. No harmony parser shipped → tool-calls will surface raw harmony tokens. |
| **`vllm-mlx` (port 8000)** | candidate | Loads stock gpt-oss directly if vllm-mlx ≥ recent version. Tool-call flags: parser depends on vllm-mlx release; check [vllm#22337](https://github.com/vllm-project/vllm/issues/22337) status. |
| **`lm-studio` (port 1234)** | candidate | GGUF in `~/.lmstudio/models/`. LM Studio's harmony parser is bug-prone — likely first place tool-calling regresses. |
| **`llama-cpp-turboquant` (port 8099)** | candidate | GGUF via either fork's `llama-server`. No advantage over lm-studio for this model (turbo3/iso3 quants don't apply to MXFP4 MoE). |
| **`vmlx` (bundled-Python, port 8000)** | not useful | JANGTQ-specific; HyperNova has no JANGTQ release. |
| **`dflash-mlx` (port 8098)** | not useful | No gpt-oss drafter exists; DFlash needs a paired draft model. |

## Quantization candidates

None exist as community uploads today. If self-converting:

| Quant | Producer | Size estimate | Notes |
|:--|:--|--:|:--|
| **MLX MXFP4-Q4** | self via `mlx_lm convert --q-bits 4` | ~32 GB | Closest to native; preserves the on-disk MXFP4 layout. Precedent: `mlx-community/gpt-oss-120b-MXFP4-Q4`. |
| **MLX MXFP4-Q8** | self via `mlx_lm convert --q-bits 8` | ~55 GB | Higher quality, fits in 96 GB only without other servers running. Precedent: `mlx-community/gpt-oss-120b-MXFP4-Q8`. |
| **MLX 4-bit (no MXFP4 preserve)** | self via `mlx_lm convert --q-bits 4 --quantize-method gguf` | ~32 GB | Loses MXFP4's documented FFN-quality property. Avoid for HyperNova. |
| **GGUF MXFP4 native** | self via `convert_hf_to_gguf.py --outtype auto` | ~32 GB | Required if hosting on lm-studio. Don't requantize FFN beyond MXFP4 — per [llama.cpp #15095](https://github.com/ggml-org/llama.cpp/discussions/15095), gpt-oss FFNs degrade under any non-MXFP4 quant. |
| **GGUF Q5_K_M / Q8_0 attn+embed** | self via `llama-quantize` second-pass | ~30 GB | Only quantises attention + embeddings further; MoE FFN stays MXFP4. Marginal disk win, marginal quality risk. |

Start with **MLX MXFP4-Q4** for the first deployment — matches the upstream `mlx-community/gpt-oss-120b-MXFP4-Q4` recipe, preserves MXFP4 quality guarantees, leaves room for other servers on the machine.

## Recommended path — convert to MLX, host on vmlx-swift-lm or oMLX

**Rationale:**

1. **MLX over GGUF**: MXFP4 on Apple Silicon performs better through MLX's group-quant path than through llama.cpp's MXFP4 implementation (latter is general-purpose, former leverages Metal kernels tuned for grouped 4-bit). Most of the lab's high-tok/s results (Qwen3.6-Coder, Granite 4.1 on lm-studio is the exception) come from MLX-native runtimes.
2. **vmlx-swift-lm first, oMLX fallback**: Osaurus has the best tok/s on the M3 Ultra for MoE models (per ZAYA1, Ling), but gpt-oss isn't in the documented native family list — risk of unsupported architecture. oMLX accepts any MLX safetensors with `model_type: gpt_oss` via the standard transformers-to-mlx loader and is the safer first deployment.
3. **lm-studio third**: If MLX paths both fail or tool-calling collapses, GGUF on lm-studio is the well-supported fallback (Granite 4.1 30B precedent for similar memory footprint).

**Why not lm-studio first**: LM Studio's harmony parser is the documented bug-prone third implementation, and HyperNova's harmony reliance is its largest tool-calling risk surface.

## Verification recipe — three layers

The Multiverse benchmark claims are vendor-attested only. Three layers of verification, lightest first — stop at the first failure since downstream layers depend on the upstream working.

### Layer 1 — Lab agent loop (decisive for daily use)

```bash
# Standing rule: Event-4 pre-benchmark hygiene before any deploy.
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep || echo 'clean'"

# 1. Convert to MLX MXFP4-Q4 on Mac Studio (uses local ~/.cache/huggingface).
ssh macstudio "hf download MultiverseComputingCAI/Hypernova-60B-2605 \
  --local-dir ~/.cache/huggingface/hub/models--MultiverseComputingCAI--Hypernova-60B-2605/snapshots/main"
ssh macstudio "~/mlx-openai-server-env/bin/python -m mlx_lm convert \
  --hf-path ~/.cache/huggingface/hub/models--MultiverseComputingCAI--Hypernova-60B-2605/snapshots/main \
  --mlx-path ~/.omlx/models/MultiverseComputingCAI/Hypernova-60B-2605-MXFP4-Q4 \
  --q-bits 4"

# 2. Start oMLX as the first host (lower risk than vmlx-swift-lm for unsupported family).
ssh macstudio "/opt/homebrew/bin/brew services start omlx"

# 3. Smoke + harmony-leak check (run via API-level harness BEFORE OpenCode).
curl -s -X POST http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"MultiverseComputingCAI/Hypernova-60B-2605-MXFP4-Q4",
       "messages":[{"role":"user","content":"List two files in /etc"}],
       "tools":[{"type":"function","function":{"name":"list_dir","description":"List directory",
                 "parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],
       "max_tokens":256}' | python3 -m json.tool
# Check: tool_calls populated cleanly, NOT raw <|channel|>commentary tokens in content.

# 4. Agent loop bench (the workload that matters for this lab).
python scripts/bench/bench_agent_tool_call.py \
  --server omlx --model MultiverseComputingCAI/Hypernova-60B-2605-MXFP4-Q4 \
  --scenario browse,search --runs 1 --warmup 0 \
  --output docs/models/benchmarks/logs/hypernova-60b-2605/agent-bench-omlx.json
```

**Pass criteria**: browse latency ≤ 15 s, search ≤ 30 s, no harmony-token leakage, tool-call success on multi-turn. Compare against Granite 4.1 30B Q8 (browse 6.24 s, [`docs/models/benchmarks/logs/granite-4.1-30b-q8/`](../benchmarks/granite-4.1-30b-q8/)) and TrevorJS Gemma 4 31B-it (browse 10.08 s).

**Stop here if it fails.** No point validating coding capability on a model that can't drive the tool harness.

### Layer 2 — Reproduce LiveCodeBench (the surprising claim)

```bash
# Public LCB harness; not Multiverse's wrapper.
pip install livecodebench  # or git clone github.com/LiveCodeBench/LiveCodeBench
livecodebench --model openai/MultiverseComputingCAI/Hypernova-60B-2605-MXFP4-Q4 \
  --openai-api-base http://<MAC_STUDIO_IP>:8000/v1 \
  --release_version release_v6 --scenario codegeneration \
  --num_samples 1 --temperature 0.2
```

**Pass criterion**: within ±3 pts of the claimed 68.68 (so 65.7–71.7). If it lands ~55, the published number is reasoning-level-tuned or eval-version-shifted — document and move on. LCB v6 is contamination-controlled; do not use pre-v6.

### Layer 3 — Reproduce AIDER regression vs parent (the cautionary signal)

```bash
git clone https://github.com/Aider-AI/aider && cd aider/benchmark
./benchmark.py --model openai/MultiverseComputingCAI/Hypernova-60B-2605-MXFP4-Q4 \
  --openai-api-base http://<MAC_STUDIO_IP>:8000/v1 --num-tests 20
# Baseline: same run against bartowski/openai_gpt-oss-120b-GGUF on lm-studio.
```

**Pass criterion**: 9 ± 3 pts below gpt-oss-120b's AIDER baseline. Wider gap = CompactifAI cost real agentic-coding capability and the lab should not promote HyperNova to a main.

## Open questions

- **gpt-oss in vmlx-swift-lm**: native family handler status not documented in the runbook. Determine by deploying — if Osaurus refuses to load, fall back to oMLX without further investigation.
- **Harmony parser on oMLX**: oMLX is generic, not family-aware. Whether tool-calls render as OpenAI `tool_calls` JSON or as raw harmony tokens in `content` is unverified. If raw tokens leak, the model is fine and the parser is wrong — workaround would be a client-side harmony→OpenAI shim, not a re-conversion.
- **2602 vs 2605 choice**: 2605 dominates 2602 on every published benchmark — go directly to 2605. Only keep 2602 around if a regression in 2605 surfaces during verification.
- **Quality vs Granite 4.1 / Gemma 4**: no shared benchmark exists between HyperNova's published table and the lab's existing roster docs. Layer 1's agent harness is the first apples-to-apples comparison.
- **Active-param parity claim**: 4.8 B active is close to Qwen3.6-35B-A3B's 3 B and Ling-2.6-flash's 7.4 B — direct head-to-head on the same agent harness clarifies whether CompactifAI's accuracy claim survives outside its own benchmark suite.
- **Markovian-equivalent inference-time scheme**: HyperNova has no published test-time-compute boost analogous to ZAYA1's Markovian RSA. Vendor numbers are single-pass. No harness changes needed.

## See also

- [MultiverseComputingCAI/Hypernova-60B-2605 (model card)](https://huggingface.co/MultiverseComputingCAI/Hypernova-60B-2605)
- [MultiverseComputingCAI/Hypernova-60B-2602 (prior checkpoint)](https://huggingface.co/MultiverseComputingCAI/Hypernova-60B-2602)
- [MultiverseComputingCAI org](https://huggingface.co/MultiverseComputingCAI)
- [CompactifAI paper — arXiv:2401.14109v2](https://arxiv.org/html/2401.14109v2)
- [CompactifAI product page](https://multiversecomputing.com/compactifai)
- [HyperNova 60B 2602 launch press](https://multiversecomputing.com/resources/multiverse-computing-opens-full-access-to-hypernova-60b-2602-on-hugging-face)
- [HyperNova 60B 2602 paper (Multiverse)](https://multiversecomputing.com/papers/hypernova-60b-2602-same-intelligence-half-the-size-improved-tool-calling-capability)
- [openai/gpt-oss-120b (parent)](https://huggingface.co/openai/gpt-oss-120b)
- [mlx-community/gpt-oss-120b-MXFP4-Q4 (MLX conversion precedent)](https://huggingface.co/mlx-community/gpt-oss-120b-MXFP4-Q4)
- [mlx-community/gpt-oss-120b-MXFP4-Q8 (MLX conversion precedent, higher quality)](https://huggingface.co/mlx-community/gpt-oss-120b-MXFP4-Q8)
- [bartowski/openai_gpt-oss-120b-GGUF (GGUF baseline for AIDER comparison)](https://huggingface.co/bartowski/openai_gpt-oss-120b-GGUF)
- [llama.cpp discussion #15095 — gpt-oss + MXFP4](https://github.com/ggml-org/llama.cpp/discussions/15095)
- [llama.cpp discussion #15396 — running gpt-oss with llama.cpp](https://github.com/ggml-org/llama.cpp/discussions/15396)
- [llama.cpp discussion #15341 — gpt-oss tool-call/grammar bug](https://github.com/ggml-org/llama.cpp/discussions/15341)
- [vllm#22337 — gpt-oss-120b tool-calls bug](https://github.com/vllm-project/vllm/issues/22337)
- [transformers MXFP4 docs](https://huggingface.co/docs/transformers/quantization/mxfp4)
- [transformers PR #39940 — MXFP4 on older hardware (CUDA only)](https://github.com/huggingface/transformers/pull/39940)
- [LiveCodeBench leaderboard](https://livecodebench.github.io/leaderboard.html) · [vals.ai LCB](https://www.vals.ai/benchmarks/lcb) · [BigCodeBench leaderboard](https://bigcode-bench.github.io/)
- [Aider benchmark harness](https://github.com/Aider-AI/aider/tree/main/benchmark)
