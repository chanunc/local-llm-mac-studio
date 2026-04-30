# Model Summary: Qwen3.5 Family

Alibaba's Qwen3.5 generation as catalogued in this stack. Four variants spanning dense 27 B distilled-reasoning, the flagship 122 B/10 B-active multimodal MoE, JANG-quantised compact-122 B, and the 35 B/3 B-active MoE in JANG mixed-precision form.

## Index

- [Qwen3.5-27B Claude Opus Distilled (qx64-hi)](#qwen35-27b-claude-opus-distilled-qx64-hi) — Reasoning / chain-of-thought
- [Qwen3.5-122B-A10B (4-bit)](#qwen35-122b-a10b-4-bit) — Agentic reasoning
- [Qwen3.5-122B-A10B JANG 2S](#qwen35-122b-a10b-jang-2s) — Compact 122 B · 46% smaller than MLX 4-bit
- [Qwen3.5-35B-A3B JANG 4-bit (Mixed Precision)](#qwen35-35b-a3b-jang-4-bit-mixed-precision) — JANG adaptive quantization · 48% smaller than MLX 8-bit

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

## See also

- Catalog stub: [`docs/models/model-summary.md` § Qwen3.5 Family](../model-summary.md#qwen35-family-moe--dense-distilled--jang)
- Sibling per-model files: [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md) · [`model-summary-qwen-3-coder.md`](model-summary-qwen-3-coder.md)
