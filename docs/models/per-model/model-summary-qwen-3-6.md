# Model Summary: Qwen3.6 Family

Alibaba's Qwen3.6 generation, all sharing the **hybrid Gated DeltaNet + full Gated Attention** stack (linear-attention recurrence interleaved with classic attention) plus a 27-layer ViT vision tower. The same architecture appears at three model sizes (27 B dense, 35 B/3 B-active MoE) and across multiple quants (uniform 4 / 6 / 8-bit MLX, JANG 4M mixed-precision, JANGTQ CRACK variants — see [`uncen-model/`](../uncen-model/) for the JANGTQ CRACK entries) plus one LoRA-merged variant tuned on Rust diffs.

## Index

- [Qwen3.6-35B-A3B (6-bit)](#qwen36-35b-a3b-6-bit) — Hybrid Gated DeltaNet + MoE + vision · 3 B active · 262 K native (1 M YaRN)
- [Qwen3.6-35B-A3B (4-bit)](#qwen36-35b-a3b-4-bit) — Same hybrid arch · 4-bit MLX (~22 GB) · dflash-mlx target paired with `z-lab/Qwen3.6-35B-A3B-DFlash`
- [Qwen3.6-27B JANG 4M (Dense + VL)](#qwen36-27b-jang-4m-dense--vl) — Dense 27 B · ViT · 17.5 GB · JANG 4/8-bit · vllm-mlx text-only
- [Qwen3.6-27B (6-bit Standard MLX)](#qwen36-27b-6-bit-standard-mlx) — Same dense 27 B + ViT · 22 GB · uniform 6-bit · llmster recommended
- [Qwen3.6-35B Rust LoRA (jedisct1, 8-bit)](#qwen36-35b-rust-lora-jedisct1-8-bit) — 35 B/3 B MoE · uniform 8-bit MLX · LoRA merged on 356 K Rust commits

---

## Qwen3.6-35B-A3B (6-bit)

New Qwen 3.6 release. Same 35B/3B MoE size class as `Qwen3.5-35B-A3B-JANG_4K`, but a different architecture: hybrid Gated DeltaNet (linear attention) interleaved with full Gated Attention layers, a built-in vision encoder, and native Multi-Token Prediction for speculative decoding. Thinking mode is the default.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) |
| MLX 6-bit | [mlx-community/Qwen3.6-35B-A3B-6bit](https://huggingface.co/mlx-community/Qwen3.6-35B-A3B-6bit) |
| Format | MLX safetensors (multimodal / `mlx_vlm` handler) |
| Vendor | Alibaba Qwen; MLX conversion by mlx-community |
| Parameters | 35B total, ~3B active (MoE, 256 experts, 8 routed + 1 shared) |
| Density | Sparse hybrid: 10× [3× (Gated DeltaNet → MoE) + 1× (Gated Attention → MoE)] = 40 layers |
| Quantization | 6-bit uniform MLX |
| Specialties | Vision-language (image + video), thinking mode by default, MTP speculative decoding, agentic coding, tool use |
| On-disk size | ~27 GB |
| Context Size | 262K native; extensible to ~1M with YaRN |
| License | Apache-2.0 |
| Key Features | Hybrid linear + full attention (long-context efficiency), native VL encoder, MTP |

**mlx-openai-server model ID:** `mlx-community/Qwen3.6-35B-A3B-6bit`

**Server config:** `model_type: multimodal`, `tool_call_parser: qwen3_vl`, `reasoning_parser: qwen3_vl`, `context_length: 131072` (conservative; raise toward 262K after stability checks).

**Requirements:**
- `mlx_lm >= 0.31.1` and `mlx_vlm >= 0.4.1` (confirmed working on Mac Studio pilot)
- Validated through-API on `mlx-openai-server` v1.7.1 single-handler mode on 2026-04-18: text + vision smoke tests pass; full benchmark in [model-benchmark-api-server.md](../benchmarks/model-benchmark-api-server.md#qwen36-35b-a3b-6-bit) shows 52.5 tok/s @ 512 → 35.6 tok/s @ 128K
- Reference YAML: [mlx-openai-server-qwen36-35b.yaml](../../servers/mlx-openai-server/mlx-openai-server-qwen36-35b.yaml)

**Caveats:**
- Default chat template emits `<think>` unconditionally; `chat_template_kwargs.enable_thinking=false` has no effect through `mlx-openai-server` 1.7.1 — same hookup gap as Gemma 4 ([#279](https://github.com/cubist38/mlx-openai-server/issues/279), fixed on `main`, awaiting 1.7.2)
- `oMLX` is **not recommended** for Qwen3.6 today: open issues [#812](https://github.com/jundot/omlx/issues/812) (tool calling silently stops), [#819](https://github.com/jundot/omlx/issues/819) (lmstudio 6bit fails to load), [#827](https://github.com/jundot/omlx/issues/827) (DFlash load failure), [#841](https://github.com/jundot/omlx/issues/841) (>127K silent crash)
- `waybarrios/vllm-mlx` post-PR [#278](https://github.com/waybarrios/vllm-mlx/pull/278) is the only Apple-Silicon server that exposes MTP/speculative decoding through OpenAI API for Qwen3.6 today, but inherits the upstream `mlx-lm` hybrid-attention cache bug ([#1162](https://github.com/ml-explore/mlx-lm/issues/1162)) — not deployed here yet
- MTP speculative decoding through `mlx-openai-server` remains unwired ([#177](https://github.com/cubist38/mlx-openai-server/issues/177), [#204](https://github.com/cubist38/mlx-openai-server/issues/204))
- Streaming `reasoning_content` / `content` split **does work cleanly** with the `qwen3_vl` parser on `mlx-openai-server` 1.7.1 — the Gemma-4-only streaming-leak bug ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) does not affect Qwen3.6

---

## Qwen3.6-35B-A3B (4-bit)

Same hybrid Gated DeltaNet + MoE architecture as the 6-bit variant above, quantized to 4-bit MLX (~22 GB on disk). Used as the **target model for the `dflash-mlx` speculative-decoding sidecar** paired with `z-lab/Qwen3.6-35B-A3B-DFlash` (0.5B BF16 drafter, ~1 GB). Not currently routed through any other server in this stack.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) |
| MLX 4-bit | [mlx-community/Qwen3.6-35B-A3B-4bit](https://huggingface.co/mlx-community/Qwen3.6-35B-A3B-4bit) |
| DFlash drafter | [z-lab/Qwen3.6-35B-A3B-DFlash](https://huggingface.co/z-lab/Qwen3.6-35B-A3B-DFlash) (0.5B BF16) |
| Format | MLX safetensors (multimodal `Qwen3_5MoeForConditionalGeneration` wrapper, weights nested under `language_model.*`) |
| Vendor | Alibaba Qwen; MLX conversion by mlx-community; drafter by z-lab |
| Parameters | 35B total, ~3B active (MoE, 256 experts, 8 routed + 1 shared); drafter adds 0.5B |
| Density | Sparse hybrid (same as 6-bit variant): 48 Gated DeltaNet + 16 Gated Attention layers |
| Quantization | 4-bit affine MLX, group_size=64, with selective 8-bit on `mlp.gate` / `shared_expert_gate` |
| Specialties | Speculative-decoding target on `dflash-mlx`; vision-language; thinking by default |
| On-disk size | ~22 GB target + ~1 GB drafter (vs ~27 GB at 6-bit) |
| Context Size | 262K native (matches 6-bit variant); benchmarked here at 32K |
| License | Apache-2.0 (target); MIT (drafter) |
| Key Features | DFlash drafter accepts ~87 % of drafted tokens on this target → sustained 74-89 tok/s decode through `dflash-serve` |

**dflash-mlx server config:**

```bash
~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512
```

`--draft-model` is required — the built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family pairs.

**Performance** (Mac Studio M3 Ultra, dflash-mlx 0.1.4.1 + post-patch mlx-lm 0.31.3, `temperature=0.0`, `block_tokens=16`):

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512  | **89.5** | 1,366 | 0.39 |
| 4K   | 88.4 | **1,812** | 2.27 |
| 8K   | 87.0 | 1,524 | 5.40 |
| 32K  | 74.1 | 837 | 39.2 |

Tool-call latency: 5/5 single-call scenarios, 1.68-6.08 s. Multi-turn 3-turn loop: 5.9 s total. Agent-bench browse: 27.59 s wall median (13% faster than llmster on the smaller dense Qwen3.6-27B-6bit). Agent-bench search: 54.78 s wall median (2.1× slower — 3-turn loop with growing context favors prefill, where llmster's closed runtime wins).

Raw bench JSONs: [`docs/models/benchmarks/qwen36-35b-a3b-4bit/`](../benchmarks/qwen36-35b-a3b-4bit/).

**Caveats:**
- Requires three local patches against upstream packages — see [`docs/servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md#installation).
- PyPI 0.1.0 has no tool-calling — install dflash-mlx from `git+https://github.com/bstnxbt/dflash-mlx.git` (which currently resolves to 0.1.4.1).
- Decode-bound win only; prefill-bound long-context multi-turn workloads lose to llmster.
- **DFlash 1.33× speedup does not replicate on M3 Ultra.** Upstream's number is from M5 Max. Standalone `dflash-benchmark` runs on this hardware show DFlash regressing vs baseline at 1k-4k horizons (best-case 0.78×, worst-case 0.62×) and reaching parity at 8k only via essay-text repetition collapse. `--quantize-draft` recovers a marginal 1.05× at 8k. See [`model-benchmark-standalone.md` § DFlash](../benchmarks/model-benchmark-standalone.md#dflash-speculative-decoding--qwen36-35b-a3b-4bit--dflash-drafter).

---

## Qwen3.6-27B JANG 4M (Dense + VL)

Dense 27.3B-parameter sibling of `Qwen3.6-35B-A3B`. Same Qwen3.6 hybrid attention stack — 48 Gated DeltaNet (linear-attention) layers + 16 full-attention layers — and the same 27-layer ViT vision tower, but no MoE: every parameter is active per token. Quantised with JANG mixed 4-bit/8-bit affine (4-bit FFN + linear-attention + ViT, 8-bit full-attention + embedding + lm_head, 4.45 bits/param average) for 17.5 GB on disk. Deployed on this Mac Studio on 2026-04-23.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) |
| Quant | [JANGQ-AI/Qwen3.6-27B-JANG_4M](https://huggingface.co/JANGQ-AI/Qwen3.6-27B-JANG_4M) |
| Format | JANG v2 mmap safetensors (11 shards) — loads in 2.8 s |
| Vendor | Alibaba Qwen base; JANGQ-AI mixed-precision quant |
| Parameters | 27.3 B (dense) |
| Density | Dense — no MoE; every param active per token |
| Quantization | JANG_4M: 4-bit FFN/linear-attn/ViT + 8-bit full-attn/embed/lm_head; ~4.45 bits/param avg |
| Specialties | Vision-language (image + video via ViT), thinking mode optional, hybrid Gated DeltaNet long-context, `qwen3_5` arch |
| On-disk size | ~17.5 GB |
| Context Size | 262K native; ~1M with YaRN |
| License | Apache-2.0 (base) |
| Key Features | Highest dense quality in the 27 GB class with VL + hybrid linear attention |

**vllm-mlx model ID:** `JANGQ-AI/Qwen3.6-27B-JANG_4M` (served from `~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M`)

**Server config (vllm-mlx):** `~/run_vllm_jang.py serve <path> --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` — same flags as the Qwen3.5-35B-A3B-JANG_4K setup. Loaded as `MLLM=False` (text-only — vllm-mlx does not expose the vision tower for this model).

**Performance** (vllm-mlx, [`benchmarks/model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md#qwen36-27b-jang-4m-dense--vl)):
- Gen: 36.5 tok/s @ 512 → 34.6 @ 8K → 27.0 @ 64K
- Prefill: ~310-345 tok/s across 512-32K, falling to 274 @ 64K
- TTFT: 1.7 s @ 512, 23.8 s @ 8K, 240 s @ 64K
- ~30-40 % slower gen and ~5× slower prefill than `Qwen3.6-35B-A3B-6bit` on `mlx-openai-server` (the MoE 3B-active sibling) — the dense-vs-MoE tradeoff is exactly as expected at full context

**Tool calling** ([`benchmarks/model-benchmark-agent-tool-call.md`](../benchmarks/model-benchmark-agent-tool-call.md#results-jangq-aiqwen36-27b-jang_4m)):
- API-level: 5/5 single-call pass, 3-turn agentic loop completes in 14.84 s (read → write → summary)
- Streaming `tool_calls` deltas verified via direct curl
- OpenCode end-to-end (2026-04-24): browse 114.25 s median, search 163.59 s median (medians across 3 measured runs each; p5-p95 89-251 s browse, 162-266 s search). ~2.7× slower than Qwen3.5-35B-A3B JANG 4K on the same scenarios — the expected dense-vs-sparse gap at OpenCode's ~10k-token system prompt

**Caveats:**
- **Vision input is not exposed via vllm-mlx** (`MLLM=False` at load). To exercise the ViT, deploy on `vmlx` (MLX Studio bundled Python — HF card recommendation) or `mlx-openai-server` with the `multimodal` handler. Neither has been validated for this specific model yet.
- **`usage.prompt_tokens=0`** for both streaming and non-streaming responses on vllm-mlx 0.2.6 — the JANG-loaded `qwen3_5` model does not propagate prompt-token count into the OpenAI usage block. Bench output computes prefill via the model's own tokenizer instead. Same shape as the Qwen3.5-122B JANG 2S note in `benchmarks/model-benchmark-api-server.md`.
- **Verbose reasoning preamble** — even on simple prompts the model emits ~80-200 tokens of `<think>`-equivalent reasoning into `reasoning_content` before the tool call. Consider `enable_thinking=false` via `chat_template_kwargs` if you need the lowest possible per-turn latency (not validated through vllm-mlx).
- **Client-config sync** — because vllm-mlx is single-model, local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` must default to whichever model is live on port 8000. Pointing at `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` while the server serves 27B returns HTTP 404 from the chat-completion endpoint. Keep those local configs aligned with `configs/clients/vllm-mlx/`.

---

## Qwen3.6-27B (6-bit Standard MLX)

Same dense 27.3B-parameter Qwen3.6 base as the JANG 4M variant — 48 Gated DeltaNet (linear-attention) layers + 16 full-attention layers + 27-layer ViT vision tower — but **uniform 6-bit MLX quantization** (22 GB on disk, no JANG mixed-precision). Standard `mlx-community/*` safetensors that loads on every server in this stack without architecture patches. Benchmarked head-to-head against vllm-mlx + JANG 4M on 2026-04-30 to compare server overhead.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) |
| Quant | [mlx-community/Qwen3.6-27B-6bit](https://huggingface.co/mlx-community/Qwen3.6-27B-6bit) |
| Format | MLX safetensors (5 shards, ~22 GB) — standard `qwen3_5` arch |
| Vendor | Alibaba Qwen base; mlx-community uniform 6-bit conversion |
| Parameters | 27.3 B (dense) |
| Density | Dense — every param active per token |
| Quantization | Uniform 6-bit MLX (group size 64) |
| Specialties | Vision-language (image + video via ViT), thinking mode optional, hybrid Gated DeltaNet long-context |
| On-disk size | ~22 GB |
| Context Size | 262K native; ~1M with YaRN |
| License | Apache-2.0 (base) |
| Key Features | Drop-in MLX safetensors — no JANG fork or wrapper required |

**Recommended server: llmster (LM Studio headless).** Tool calling and reasoning parsing are built into LM Studio's MLX runtime — no parser flags needed. Matches the JANG 4M variant's tool-call correctness (5/5 API-level pass) and is **3-5× faster end-to-end on the OpenCode agent loop**:

| Metric | vllm-mlx (this model, no JANG) | llmster (this model) | Δ |
|:-------|:------------------------------:|:--------------------:|:----:|
| OpenCode browse (wall) | 97.93 s | **31.96 s** | **3.1× faster** |
| OpenCode search (wall) | 127.28 s | **25.71 s** | **4.9× faster** |
| TTFT @ 32K | ~104 s (vllm-mlx + JANG 4M ref) | **0.70 s** | ~150× faster prefill |
| Prefill @ 32K | ~314 tok/s (JANG 4M ref) | **47,143 tok/s** | ~150× faster |
| Gen @ 512 | 36.5 tok/s (JANG 4M ref) | 29.9 tok/s | -18 % |
| 5-tool API harness pass rate | 5/5 | 5/5 | tied |

llmster's MLX runtime ships an aggressive prefill kernel that flattens TTFT across context lengths (0.49 s @ 512 → 0.70 s @ 32K). For agent workloads where the 10K-token system prompt + tool catalog is mostly prefill cost, this win compensates ~10× over the slightly slower decode path.

**llmster model ID:** `qwen3.6-27b` (LM Studio strips the org prefix and lowercases at load — verify with `/v1/models`)

**llmster setup:**
```bash
ssh macstudio "/opt/homebrew/bin/brew install --cask lm-studio"            # one-time install
ssh macstudio "open -a 'LM Studio' && sleep 8 && osascript -e 'quit app \"LM Studio\"'"  # bootstrap lms CLI
ssh macstudio "~/.lmstudio/bin/lms get https://huggingface.co/mlx-community/Qwen3.6-27B-6bit -y"
ssh macstudio "~/.lmstudio/bin/lms load qwen3.6-27b --gpu max --context-length 65536 -y"
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"     # port 1234, NOT 8000
```

**vllm-mlx server config** (also works, no patches needed): `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` — same flags as the JANG 4M variant, but launched via the standard `~/vllm-mlx-env/bin/vllm-mlx serve` (no `run_vllm_jang.py` wrapper required for the 6-bit standard MLX file).

**Performance** (llmster, [`benchmarks/model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md#qwen36-27b-6-bit-standard-mlx-on-llmster-vs-vllm-mlx)):
- Gen: 29.9 tok/s @ 512 → 28.8 @ 8K → 26.3 @ 32K
- Prefill: 1,086 tok/s @ 512 → 8,031 @ 4K → 15,321 @ 8K → **47,143 @ 32K**
- TTFT: 0.49 s @ 512, 0.51 s @ 4K, 0.54 s @ 8K, 0.70 s @ 32K — effectively flat
- Model load: ~5 s (warm), ~16 s (cold first launch after `lms get`)

**Quality vs JANG 4M:** External reference (LLM infrastructure research memo): 6-bit uniform retains ~1 ppt more quality than 4.45-bit JANG mixed on standard benchmarks while adding ~3.5 GB disk and ~10-20 % decode latency. Pick this variant when (a) running on llmster for the prefill win, or (b) avoiding the JANG fork overlay maintenance burden on vllm-mlx.

**Caveats:**
- **Vision input not exposed via vllm-mlx** (`MLLM=False` at load) — same constraint as the JANG 4M sibling. llmster also serves text-only by default; vision via this model has not been validated through `mlx-vlm` here yet.
- **llmster duplicates HF cache** — `lms get` re-downloads the 22 GB into `~/.lmstudio/models/mlx-community/Qwen3.6-27B-6bit/` even when present in `~/.cache/huggingface/hub/`. Plan ~22 GB extra disk.
- **Default `lms` context is 4096** — agent prompts (10K+ system prompt) need `--context-length 65536` (or larger) at `lms load` time. Memory is allocated up-front.
- **Default bind is 127.0.0.1** — `lms server start` won't accept LAN connections without `--bind 0.0.0.0`.
- **First-time install needs one GUI launch** to bootstrap `~/.lmstudio/bin/lms` after the cask install. Headless-only macOS hosts need a screen-share session for that single step.
- **Closed-source MLX runtime** — llmster's prefill kernel implementation is not auditable. If a future LM Studio update changes runtime behavior, results may shift.

**See also:** [`docs/servers/llmster/summary.md`](../../servers/llmster/summary.md) for the full LM Studio headless server runbook · [`docs/models/benchmarks/model-benchmark-agent-tool-call.md` § Server comparison](../benchmarks/model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30) for the raw bench data.

---

## Qwen3.6-35B Rust LoRA (jedisct1, 8-bit)

Qwen3.6-35B-A3B base with a rank-8 LoRA (alpha 16) trained on **356 K Rust commits / 634 K samples** for diff generation, then merged into uniform 8-bit MLX weights. `Qwen3_5MoeForConditionalGeneration` arch — 256 experts, 8 active per token, 40 layers (3 linear / 1 full attention pattern, Mamba-like SSM hybrid). Vision tokens defined in tokenizer but text-only here. Standard MLX safetensors — **no JANG wrapper, no patches** required. Currently the **best wall-time on agent browse** in this stack (close behind Qwen3.5-35B-A3B JANG 4K).

| Spec | Value |
|:-----|:------|
| Base Model | [Brooooooklyn/Qwen3.6-35B-A3B-UD-Q8_K_XL-mlx](https://huggingface.co/Brooooooklyn/Qwen3.6-35B-A3B-UD-Q8_K_XL-mlx) |
| Quant | [jedisct1/Qwen3.6-35B-rust.mlx](https://huggingface.co/jedisct1/Qwen3.6-35B-rust.mlx) |
| Format | MLX safetensors (uniform 8-bit, group_size=64) |
| Architecture | `Qwen3_5MoeForConditionalGeneration` (`qwen3_5_moe`) — 40 layers, hybrid (3 linear + 1 full attn) |
| Parameters | 35 B total, 3 B active per token (256 experts, 8 routed) |
| Specialties | Agentic coding (Rust-tuned diffs), tool calling, fast browse/search loops |
| Tokens/sec | ~83 tok/s gen @ 256 ctx, ~80 tok/s @ 8K (bench: [`benchmarks/qwen36-35b-rust/api-typical.json`](../benchmarks/qwen36-35b-rust/api-typical.json)) |
| TTFT | 0.31 s @ 256, 1.00 s @ 2K, 3.70 s @ 8K |
| On-disk size | ~35 GB |
| Context Size | 262,144 native (262K) |
| License | Apache-2.0 (base) |

**vllm-mlx model ID:** `jedisct1/Qwen3.6-35B-rust.mlx` (served from `~/.omlx/models/jedisct1--Qwen3.6-35B-rust.mlx`)

**Server config (vllm-mlx):** standard CLI with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` (same parser flags as the non-LoRA Qwen3.6 variants — the LoRA-merged weights still emit the Qwen3-coder XML tool-call format).

**Tool calling** ([`benchmarks/model-benchmark-agent-tool-call.md`](../benchmarks/model-benchmark-agent-tool-call.md#results-jedisct1qwen36-35b-rustmlx)):
- API-level: 4/5 single-call pass · single-tool 1.42-1.80 s 🥈 · 3-turn agentic loop 6.99 s
- OpenCode end-to-end (2026-04-30): browse 13.94 s 🥈 · search 26.31 s 🥈 — second-fastest in the stack on both scenarios
- ⚠ One agentic-reasoning prompt (`Find the largest file in /tmp`) hits the 1024-token cap because the model emits long Gemini-style chain-of-thought as `content` (no `<think>` wrapper, so the `qwen3` reasoning parser doesn't strip it). Other scenarios pass cleanly.

**Caveats:**
- Reasoning emitted as `content` (not `<think>`) — not extracted by `--reasoning-parser qwen3`. If you need a clean reasoning/content split, prefer Qwen3.5-35B-A3B JANG 4K which uses proper `<think>` tags.
- Rust-domain LoRA: not measured to degrade general performance, but explicitly tuned for code-diff workloads.
- Vision encoder defined in tokenizer but vllm-mlx loads as text-only (`MLLM=False`).

---

## See also

- Catalog stub: [`docs/models/model-summary.md` § Qwen3.6 Family](../model-summary.md#qwen36-family-hybrid-gated-deltanet--vision)
- JANGTQ-CRACK Qwen3.6 variants (research only, private submodule): [`docs/models/uncen-model/`](../uncen-model/)
- Sibling per-model: [`model-summary-ling.md`](model-summary-ling.md) (production primary) · [`model-summary-mimo-v2.5.md`](model-summary-mimo-v2.5.md)
