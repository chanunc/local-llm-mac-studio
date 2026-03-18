# Model Summary

Detailed specs, benchmarks, and caveats for each model served by the oMLX server on Mac Studio M3 Ultra (96GB). For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Adding a Model to oMLX](#adding-a-model-to-omlx)
- [Qwen3-Coder-Next (6-bit / 8-bit)](#qwen3-coder-next-6-bit--8-bit) — Daily driver (coding)
- [Qwen3.5-27B Claude Opus Distilled (qx64-hi)](#qwen35-27b-claude-opus-distilled-qx64-hi) — Reasoning / chain-of-thought
- [Qwen3.5-122B-A10B (4-bit)](#qwen35-122b-a10b-4-bit) — Agentic reasoning
- [OmniCoder-9B (8-bit)](#omnicoder-9b-8-bit) — Coding agent (agentic trajectories)
- [Qwen3.5-35B-A3B (8-bit)](#qwen35-35b-a3b-8-bit) — SWE agent
- [Qwen3.5-35B-A3B Holodeck (qx86-hi)](#qwen35-35b-a3b-holodeck-qx86-hi--hybrid-variant) — Hybrid precision MoE
- [Nemotron 3 Nano 30B-A3B (8-bit)](#nemotron-3-nano-30b-a3b-8-bit) — NVIDIA MoE · efficient inference
- [Huihui Qwen3.5-35B-A3B Abliterated (8-bit)](#huihui-qwen35-35b-a3b-abliterated-8-bit) — Uncensored / abliterated (converted from BF16)

---

## Adding a Model to oMLX

### Step 1: Find a model

Browse MLX-format models on HuggingFace. oMLX only supports MLX safetensors — not GGUF. Good sources:
- [`mlx-community`](https://huggingface.co/mlx-community) — official MLX conversions
- [`nightmedia`](https://huggingface.co/nightmedia) — hybrid-precision MLX quantizations (qx64-hi, qx86-hi)

Look for repos where the files end in `.safetensors` and include a `config.json`.

### Step 2: Download the model

**Option A — Admin panel (easiest):**
1. Open `http://<MAC_STUDIO_IP>:8000/admin`
2. Go to the **HuggingFace** tab
3. Search for the model ID (e.g., `mlx-community/Qwen3.5-35B-A3B-8bit`)
4. Click **Download** — oMLX streams it directly into `~/.omlx/models/`

**Option B — CLI on Mac Studio:**
```bash
ssh macstudio
pip install huggingface-hub   # if not already installed
huggingface-cli download mlx-community/Qwen3.5-35B-A3B-8bit \
  --local-dir ~/.omlx/models/mlx-community/Qwen3.5-35B-A3B-8bit
```

oMLX expects the two-level org/repo directory structure: `~/.omlx/models/<org>/<repo>/`.

**Option C — Symlink an existing download:**
```bash
ssh macstudio
ln -s /path/to/existing/model ~/.omlx/models/mlx-community/my-model
```

Models are auto-discovered on the next API request — **no restart needed**.

### Step 3: Configure per-model settings (optional)

To set context size, hot cache, or TTL per model, edit `~/.omlx/model_settings.json` on Mac Studio:

```json
{
  "mlx-community/Qwen3.5-35B-A3B-8bit": {
    "context_size": 32768,
    "hot_cache_max_size": "8GB",
    "ttl": 3600
  }
}
```

Common settings:
| Key | Description | Example |
|:----|:------------|:--------|
| `context_size` | Max context tokens (reduce if OOM) | `32768` |
| `hot_cache_max_size` | RAM hot cache for KV blocks | `"8GB"` |
| `ttl` | Seconds before idle model is evicted | `3600` |

Restart oMLX after editing model_settings.json:
```bash
ssh macstudio "brew services restart omlx"
```

### Step 4: Update client configs

After adding a model, update all client configs to make it available. See the **Editing Workflow** section in [CLAUDE.md](../../CLAUDE.md) for the full checklist.

### Step 5: Verify

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool
```

The new model ID should appear in the list.

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
| Context Size | 262,144 tokens native (256K); reduce to 32K if server fails to start |
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
| Context Size | 262,144 tokens native (256K) |
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
| Context Size | 262,144 tokens native (256K); extensible to 1,010,000 tokens via YaRN |
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
| Context Size | 262,144 tokens native (256K); extensible to 1M+ via YaRN |
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
| Context Size | 262,144 tokens native (256K); extensible to 1,010,000 tokens via YaRN |
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
| Context Size | 262,144 tokens native (256K); extensible to 1,010,000 tokens via YaRN |
| Cache | Same as standard variant |
| Key Benchmarks | Same base model as standard 8-bit |

**Caveats:**
- ~2GB larger than standard 8-bit variant
- Vision/multimodal concurrency limited

---

## Nemotron 3 Nano 30B-A3B (8-bit)

NVIDIA's 32B sparse MoE with only 3B active params, quantized to 8-bit MLX. Trained on Nemotron-CC datasets with strong multilingual coverage across 6 languages.

| Spec | Value |
|:-----|:------|
| Base Model | [nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) |
| MLX 8-bit | [mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit](https://huggingface.co/mlx-community/NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit) |
| Vendor | NVIDIA; MLX by mlx-community |
| Parameters | 32B total, 3B active (MoE) |
| Density | Sparse MoE |
| Specialties | Text generation, multilingual (6 languages), efficient inference |
| Tokens/sec | TBD on M3 Ultra; ~33.6GB on disk |
| Context Size | 256K default; up to 1M tokens (requires VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 in vLLM) |
| Cache | Standard KV cache |
| Key Benchmarks | TBD |

**Caveats:**
- oMLX serves this model without the `mlx-community/` prefix — use ID `NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit` in client configs
- Invalid JSON config warning on HuggingFace model card (cosmetic, does not affect inference)

---

## Huihui Qwen3.5-35B-A3B Abliterated (8-bit)

Higher-quality 8-bit conversion of the Huihui abliterated variant, self-converted from BF16 source using `mlx_lm.convert` on Mac Studio M3 Ultra. Same MoE architecture as the standard 35B-A3B with ~3B active parameters per token. This variant trades ~15 GB extra disk vs the 4-bit AITRADER build for improved weight precision.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) |
| Abliterated source | [huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated](https://huggingface.co/huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated) |
| MLX 8-bit | Self-converted — `~/.omlx/models/huihui-ai/Huihui-Qwen3.5-35B-A3B-abliterated-8bit-mlx` |
| Conversion tool | `mlx_lm.convert --q-bits 8 --q-group-size 64` |
| Vendor | Alibaba Qwen; abliteration by huihui-ai; MLX conversion local |
| Parameters | 35B total, ~3B active (MoE) |
| Density | Sparse MoE |
| Specialties | Uncensored responses, all tasks the base model handles, higher precision than 4-bit |
| Tokens/sec | TBD on M3 Ultra; expected similar to mlx-community 8-bit (~80 tok/s) |
| On-disk size | ~35 GB (8-bit MLX) |
| Context Size | 262K (262,144 tokens — native model limit) |

**oMLX model ID:** `Huihui-Qwen3.5-35B-A3B-abliterated-8bit-mlx`

**Caveats:**
- oMLX strips the `huihui-ai/` org prefix — use ID `Huihui-Qwen3.5-35B-A3B-abliterated-8bit-mlx` in client configs (same behavior as 4-bit AITRADER variant)

**Conversion notes:**
- BF16 source (~70 GB download) converted with oMLX stopped to maximize free RAM (~90–92 GB available, ~80 GB peak needed)
- Used `mlx_lm.convert` v0.31.1 with transformers 5.3.0
- See [model-conversion-gguf-mlx.md](model-conversion-gguf-mlx.md) for broader conversion context

**Caveats:**
- Context set to 262K (native model limit) — 8-bit MoE model uses ~35 GB + KV cache only on ~16/64 layers, so 262K is feasible on 96 GB
- VLM capable per base model card but vision support in oMLX is unverified
