# Model Summary: Qwen3.5 Family

Alibaba's Qwen3.5 generation as catalogued in this stack. Six variants spanning dense 27 B distilled-reasoning, the flagship 122 B/10 B-active multimodal MoE, JANG-quantised compact-122 B, the 35 B/3 B-active MoE in JANG mixed-precision form, the 35 B/3 B-active AgentWorld language world model GGUF, and a 9 B dense GGUF marketed "uncensored" that benchmarks as aligned (negative result).

## Index

- [Qwen3.5-27B Claude Opus Distilled (qx64-hi)](#qwen35-27b-claude-opus-distilled-qx64-hi) — Reasoning / chain-of-thought
- [Qwen3.5-122B-A10B (4-bit)](#qwen35-122b-a10b-4-bit) — Agentic reasoning
- [Qwen3.5-122B-A10B JANG 2S](#qwen35-122b-a10b-jang-2s) — Compact 122 B · 46% smaller than MLX 4-bit
- [Qwen3.5-35B-A3B JANG 4-bit (Mixed Precision)](#qwen35-35b-a3b-jang-4-bit-mixed-precision) — JANG adaptive quantization · 48% smaller than MLX 8-bit
- [Qwen-AgentWorld-35B-A3B UD-Q6_K](#qwen-agentworld-35b-a3b-ud-q6_k) — Language world model / environment simulator, llama.cpp GGUF
- [Qwythos-9B Claude-Mythos-5-1M Q8_0](#qwythos-9b-claude-mythos-5-1m-q8_0) — ⚠ marketed uncensored, behaves aligned (negative result)

---

## 🤖 Qwen3.5-27B Claude Opus Distilled (qx64-hi)

Dense 27B fine-tuned with Claude Opus 4.6 reasoning chains. Excels at structured chain-of-thought reasoning and extended autonomous coding sessions (9+ min uninterrupted).

| Spec | Value |
|:-----|:------|
| Base Model | [Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled](https://huggingface.co/Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled) |
| MLX qx64-hi | [nightmedia/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx](https://huggingface.co/nightmedia/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx) |
| Vendor | Jackrong (distillation); nightmedia (hybrid MLX quantization) |
| Parameters | 27B total, 27B active |
| Density | Dense (all params per token) |
| Specialties | Chain-of-thought reasoning (`<think>` tags), autonomous coding agent |
| Tokens/sec | ~29-35 tok/s on Apple Silicon (qx64-hi); peak memory 26.6GB |
| Context Size | 262,144 tokens native (256K) |
| Cache | KV cache on 16/64 layers only; 48 DeltaNet layers use fixed-size recurrent state (~4x context capacity) |
| Key Benchmarks | ARC 0.434, BoolQ 0.850, WinoGrande 0.721, Perplexity 4.149 |

**Caveats:**
- Dense model — every token activates all 27B params, too slow for OpenClaw (dense + agent thinking overhead)
- Preview/research quality
- Hallucination risk on real-world facts

---

## 🤖 Qwen3.5-122B-A10B (4-bit)

122B multimodal vision-language MoE with 10B active params. Supports 262K native context (1M+ with YaRN). Strong across reasoning, coding, and vision tasks.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.5-122B-A10B](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) |
| MLX 4-bit | [mlx-community/Qwen3.5-122B-A10B-4bit](https://huggingface.co/mlx-community/Qwen3.5-122B-A10B-4bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 122B total, 10B active (256 experts, 8 routed + 1 shared) |
| Density | Sparse MoE |
| Specialties | Multimodal (text+image+video), agentic reasoning, 201 languages |
| Tokens/sec | TBD on M3 Ultra; 4-bit model is ~69.6GB on disk |
| Context Size | 262,144 tokens native (256K); extensible to 1,010,000 tokens via YaRN |
| Cache | Full VLM KV cache; YaRN scaling to 1M+ tokens |
| Key Benchmarks | MMLU-Pro 86.7, GPQA Diamond 86.6, SWE-Bench 72.0 |

**Caveats:**
- HTTP 500 errors with OpenClaw large system prompts ([oMLX #42](https://github.com/jundot/omlx/issues/42))
- MXFP8 quantization not confirmed in oMLX

---

## 🤖 Qwen3.5-122B-A10B JANG 2S

JANG 2-bit quantization of the 122B MoE model. Uses aggressive mixed-precision: 6-bit for critical parameters, 4-bit for important parameters, 2-bit for 98% of expert MLP layers. **46% smaller** than MLX 4-bit (35 GB vs 65 GB) with only 6% MMLU drop, freeing ~30 GB extra for KV cache and dramatically extending context.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.5-122B-A10B](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) |
| JANG 2S | [JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S](https://huggingface.co/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S) |
| Vendor | Alibaba Qwen; JANG quantization by JANGQ-AI |
| Parameters | 122B total, ~10B active (256 experts, 8 routed) |
| Density | Sparse MoE + GatedDeltaNet SSM |
| Bits per weight | 2.x avg (attention 6-bit, important 4-bit, experts 2-bit) |
| Specialties | Agentic reasoning at compact size, thinking mode |
| Tokens/sec | ~54 tok/s |
| On-disk size | ~35 GB |
| Context Size | 200K+ (with 95 GB memory limit, ~60 GB available for KV cache) |
| Cache | Native KV cache on attention layers |
| Key Benchmarks | MMLU 79% (vs 85% MLX 4-bit, vs 56.5% MLX native 2-bit) |

**Caveats:**
- 6% MMLU drop vs MLX 4-bit — acceptable trade-off for 46% size reduction
- Requires JANG fork overlay (AlexTzk PR #364) on oMLX
- VLM capable per base model but vision support in oMLX is unverified

---

## 🤖 Qwen3.5-35B-A3B JANG 4-bit (Mixed Precision)

> **Removed from disk 2026-05-05** — deleted from `~/.omlx/models/` during the post-Granite storage cleanup. Re-download from `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` if needed.

First JANG-format model on the oMLX server. Uses adaptive mixed-precision quantization (JANG_4K profile): attention layers at 8-bit for coherence, MoE expert layers at 4-bit for compression. Same base architecture as the MLX 8-bit variant but **48% smaller** (19GB vs 37GB) with sub-second model loading via zero-copy mmap.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) |
| JANG 4-bit | [JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K](https://huggingface.co/JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K) |
| Format | JANG v2 mixed-precision (requires oMLX JANG fork) |
| Vendor | Alibaba Qwen; JANG quantization by JANGQ-AI |
| Parameters | 35B total, ~3B active (MoE) |
| Density | Sparse MoE |
| Quantization | JANG_4K: 4-bit average, attention at 8-bit, experts at 4-bit |
| Specialties | Same as MLX 8-bit variant; much smaller footprint |
| Model Load | **0.8 seconds** (zero-copy mmap) vs 15-30s for standard MLX |
| On-disk size | ~19 GB (vs ~37 GB for MLX 8-bit) |
| Context Size | 262K (262,144 tokens — full context fits easily at 19GB model weight) |
| Hot Cache | 24GB (global default; total ~43GB at full context, well within 96GB) |
| Key Benchmarks | Same base model as MLX 8-bit; JANG_4K retains attention coherence |

**oMLX model ID:** `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`

**Requirements:**
- oMLX with AlexTzk fork overlay ([PR #364](https://github.com/jundot/omlx/pull/364))
- `jang[mlx]>=0.1.0` pip package installed in oMLX venv

**Caveats:**
- JANG format is not supported by upstream oMLX — requires the fork overlay
- JANG ecosystem is early stage; no community validation of quality claims
- Future `brew upgrade omlx` will overwrite the fork — must re-apply after upgrades
- Detected as VLM model type (`qwen3_5_moe`) in oMLX discovery

---

## 🤖 Qwen-AgentWorld-35B-A3B UD-Q6_K

Qwen-AgentWorld is a Qwen3.5 MoE language world model: it is trained to simulate agent environments and feedback across MCP, Search, Terminal, SWE, Android, Web, OS, and related tool-use tasks. Treat it as an agent-environment / world-model experiment, not a normal assistant fine-tune.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen-AgentWorld-35B-A3B](https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B) |
| GGUF | [unsloth/Qwen-AgentWorld-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF) |
| File | `Qwen-AgentWorld-35B-A3B-UD-Q6_K.gguf` |
| Vendor | Alibaba Qwen team; GGUF quantization by Unsloth |
| Parameters | 34.7B total, ~3B active (256 experts, 8 routed) |
| Density | Sparse MoE (`qwen35moe`) |
| Quantization | Unsloth Dynamic 6-bit GGUF (`UD-Q6_K`), 27.3 GiB |
| Context Size | 262,144 train context; benchmarked at `-c 131072` |
| Server | `llama-cpp-mainline` on port 8100, plain GGUF path, no MTP/speculative flags |
| Tool-call | API smoke **4/5** at 1024-token cap; multi-turn loop **6.22 s** |
| Agent loop | OpenCode browse **22.52 s** / search **39.47 s** median |
| Throughput | 81.5 tok/s @ 512, 60.6 tok/s @ 65K, 49.4 tok/s @ 120K nominal |

**Launch shape:**

```bash
ssh macstudio 'GGUF="$HOME/.cache/huggingface/hub/models--unsloth--Qwen-AgentWorld-35B-A3B-GGUF/snapshots/3a305abf5cfd119ee999dfe929c433746edd8d63/Qwen-AgentWorld-35B-A3B-UD-Q6_K.gguf"; \
  nohup "$HOME/llama-cpp-mainline/build/bin/llama-server" \
    -m "$GGUF" -ngl 99 -fa on -np 1 -c 131072 \
    --host 0.0.0.0 --port 8100 \
    --alias qwen-agentworld-35b-a3b-ud-q6k \
    --jinja --reasoning on > /tmp/qwen-agentworld-llama-cpp.log 2>&1 &'
```

**Caveats:**
- The upstream config advertises `mtp_num_hidden_layers=1`, but the clean GGUF has no MTP / next-n tensors or GGUF MTP metadata. Run it without `--spec-type draft-mtp`.
- The API smoke miss is the `Find the largest file in /tmp` scenario hitting the harness's 1024-token cap (`finish_reason=length`) before a tool call. The read/write multi-turn loop completes cleanly.
- OpenCode search worked but often chose local `bash` fetches instead of only `webfetch`; count this as tool-capable but not a drop-in replacement for the fastest assistant-tuned Qwen/Gemma agent models.
- The perf sweep used llama.cpp prompt cache warmups; 512-120K prefill tok/s values are cache-warm and should not be read as cold-prefill throughput.
- Text-only run. No `mmproj` was loaded.

Raw logs: [`../benchmarks/logs/qwen-agentworld-35b-a3b-ud-q6k/`](../benchmarks/logs/qwen-agentworld-35b-a3b-ud-q6k/).

---

## 🤖 Qwythos-9B Claude-Mythos-5-1M Q8_0

Dense 9 B Qwen3.5 + vision GGUF from empero-ai, marketed as "uncensored" (cybersecurity / red-teaming / pharmacology framing). **Benchmarks as effectively aligned** — a documented negative result, not a usable uncensored model. Full deploy + perf + refusal writeup: [`docs/models/uncen-model/qwythos-9b-mythos5-benchmark.md`](../uncen-model/qwythos-9b-mythos5-benchmark.md).

| Spec | Value |
|:-----|:------|
| HuggingFace | [empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF) |
| Architecture | `qwen35` dense 9 B + vision (`mmproj` available, skipped for benchmarks) |
| Quantization | Q8_0 GGUF (8.87 GiB on disk / resident) |
| Server | lm-studio (GGUF); no parser flags (LM Studio handles Qwen3 chat-template + `<think>`) |
| Throughput | 64.7 tok/s @ 512, 52.3 @ 65K; prefill ~123K tok/s @ 65K |
| Tool-call | API smoke **5/5**, multi-turn 3/3; OpenCode browse 9.38 s / search 18.27 s (webfetch fired) |
| Refusal (mlabonne 10/520) | **1/10 complied (9/10 refused), ~0/10 useful** — lowest of any lm-studio entry |
| Context | 131072 loaded (1M native via YaRN) |
| License | Apache 2.0 |

**Caveats:**
- **Not actually uncensored** — refuses or pivots to "ethical/educational" framings on 9/10 harm prompts; do not deploy for uncensored work.
- **Vendor identity-injection** — asserts "I'm Qwythos, an AI created by Empero AI" in ~9/10 replies; overrides system-prompt persona.
- Tooling itself is fine — the alignment is the only disqualifier.

---

## See also

- Catalog stub: [`docs/models/model-summary.md` § Qwen3.5 Family](../model-summary.md#qwen35-family-moe--dense-distilled--jang)
- Sibling per-model files: [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md) · [`model-summary-qwen-3-coder.md`](model-summary-qwen-3-coder.md)
