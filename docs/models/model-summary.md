# Model Summary

Detailed specs, benchmarks, and caveats for each model served by the oMLX server on Mac Studio M3 Ultra (96GB). For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Qwen3-Coder-Next (6-bit / 8-bit)](#qwen3-coder-next-6-bit--8-bit) — Daily driver (coding)
- [Qwen3.5-27B Claude Opus Distilled (qx64-hi)](#qwen35-27b-claude-opus-distilled-qx64-hi) — Reasoning / chain-of-thought
- [Qwen3.5-122B-A10B (4-bit)](#qwen35-122b-a10b-4-bit) — Agentic reasoning
- [OmniCoder-9B (8-bit)](#omnicoder-9b-8-bit) — Coding agent (agentic trajectories)
- [Qwen3.5-35B-A3B (8-bit)](#qwen35-35b-a3b-8-bit) — SWE agent
- [Qwen3.5-35B-A3B Holodeck (qx86-hi)](#qwen35-35b-a3b-holodeck-qx86-hi--hybrid-variant) — Hybrid precision MoE

---

## Qwen3-Coder-Next (6-bit / 8-bit)

80B sparse MoE with only 3B active params. Optimized for coding agents and IDE integration. Performance comparable to Claude Sonnet 4.0 on SWE tasks. This is the **daily driver** model.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) |
| MLX 6-bit | [mlx-community/Qwen3-Coder-Next-6bit](https://huggingface.co/mlx-community/Qwen3-Coder-Next-6bit) |
| MLX 8-bit | [mlx-community/Qwen3-Coder-Next-8bit](https://huggingface.co/mlx-community/Qwen3-Coder-Next-8bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 80B total, 3B active (512 experts, 10 routed + 1 shared) |
| Density | Sparse MoE |
| Specialties | Code generation, agentic reasoning, tool use, long-horizon recovery |
| Tokens/sec | ~40-60 tok/s on M3 Ultra (6-bit); ~60 tok/s on M4 Pro (4-bit) |
| Cache | KV cache on 12/48 Gated Attention layers; supports q8/q4/FP8 cache quantization |
| Key Benchmarks | SWE-Bench Verified 42.8%, SWE-Bench Pro 44.3% |

**Caveats:**
- Non-thinking mode only (no `<think>` blocks)
- MLX KV cache issues during conversation branching
- 8-bit variant limited to 16K-32K context due to ~79GB memory footprint

---

## Qwen3.5-27B Claude Opus Distilled (qx64-hi)

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
| Cache | KV cache on 16/64 layers only; 48 DeltaNet layers use fixed-size recurrent state (~4x context capacity) |
| Key Benchmarks | ARC 0.434, BoolQ 0.850, WinoGrande 0.721, Perplexity 4.149 |

**Caveats:**
- Dense model — every token activates all 27B params, too slow for OpenClaw (dense + agent thinking overhead)
- Preview/research quality
- Hallucination risk on real-world facts

---

## Qwen3.5-122B-A10B (4-bit)

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
| Cache | Full VLM KV cache; YaRN scaling to 1M+ tokens |
| Key Benchmarks | MMLU-Pro 86.7, GPQA Diamond 86.6, SWE-Bench 72.0 |

**Caveats:**
- HTTP 500 errors with OpenClaw large system prompts ([oMLX #42](https://github.com/jundot/omlx/issues/42))
- MXFP8 quantization not confirmed in oMLX

---

## OmniCoder-9B (8-bit)

9B dense model fine-tuned on 425K+ curated agentic coding trajectories from Claude Opus 4.6, GPT-5.3/5.4, and Gemini 3.1 Pro. Expert at error recovery and targeted edit diffs.

| Spec | Value |
|:-----|:------|
| Base Model | [Tesslate/OmniCoder-9B](https://huggingface.co/Tesslate/OmniCoder-9B) |
| MLX 8-bit | [NexVeridian/OmniCoder-9B-8bit](https://huggingface.co/NexVeridian/OmniCoder-9B-8bit) |
| Vendor | Tesslate; MLX by NexVeridian |
| Parameters | 9B total, 9B active (base: Qwen3.5-9B) |
| Density | Dense |
| Specialties | Agentic coding, error recovery, LSP diagnostics, read-before-write patterns |
| Tokens/sec | ~3,076 tok/s prompt eval; generation TBD on M3 Ultra |
| Cache | Standard KV cache; YaRN scaling to 1M+ |
| Key Benchmarks | GPQA Diamond 83.8% (pass@1), AIME 2025 90% (pass@5) |

**Caveats:**
- Non-English performance not extensively evaluated
- Best with temperature 0.6 general / 0.2-0.4 agentic

---

## Qwen3.5-35B-A3B (8-bit)

35B MoE with only 3B active params — frontier-class reasoning at efficient compute. 69.2% SWE-bench Verified.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) |
| MLX 8-bit | [mlx-community/Qwen3.5-35B-A3B-8bit](https://huggingface.co/mlx-community/Qwen3.5-35B-A3B-8bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 35B total, 3B active (256 experts, 8 routed + 1 shared) |
| Density | Sparse MoE |
| Specialties | SWE agent tasks, efficient high-throughput inference, thinking mode |
| Tokens/sec | ~80.6 tok/s on M3 Ultra (8-bit, 39.3GB memory) |
| Cache | Native KV cache; q4 weight + KV cache quantization available |
| Key Benchmarks | SWE-bench 69.2% |

**Caveats:**
- Vision/multimodal concurrency limited
- KV cache reuse disabled in llama.cpp (not an issue for oMLX/MLX)

---

## Qwen3.5-35B-A3B Holodeck (qx86-hi) — Hybrid Variant

Hybrid-precision variant of Qwen3.5-35B-A3B with higher-quality attention layers (qx86-hi quantization). Same MoE architecture (3B active) but better quality in critical layers at +2GB cost.

| Spec | Value |
|:-----|:------|
| MLX qx86-hi | [nightmedia/Qwen3.5-35B-A3B-Holodeck-qx86-hi-mlx](https://huggingface.co/nightmedia/Qwen3.5-35B-A3B-Holodeck-qx86-hi-mlx) |
| Vendor | nightmedia (hybrid MLX quantization) |
| Parameters | 35B total, 3B active (same architecture as standard 8-bit) |
| Density | Sparse MoE |
| Specialties | Same as standard variant with improved attention precision |
| Tokens/sec | Similar to 8-bit; ~37GB memory (vs ~35GB standard) |
| Cache | Same as standard variant |
| Key Benchmarks | Same base model as standard 8-bit |

**Caveats:**
- ~2GB larger than standard 8-bit variant
- Vision/multimodal concurrency limited
