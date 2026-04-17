# Model Summary

Detailed specs, benchmarks, and caveats for the main model set used across the Mac Studio servers. For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Adding a Model to oMLX](#adding-a-model-to-omlx)
- [Qwen3-Coder-Next (6-bit)](#qwen3-coder-next-6-bit) — Daily driver (coding)
- [Qwen3-Coder-30B-A3B Instruct (4-bit)](#qwen3-coder-30b-a3b-instruct-4-bit) — Compact coding model
- [Qwen3.5-27B Claude Opus Distilled (qx64-hi)](#qwen35-27b-claude-opus-distilled-qx64-hi) — Reasoning / chain-of-thought
- [Qwen3.5-122B-A10B (4-bit)](#qwen35-122b-a10b-4-bit) — Agentic reasoning
- [Qwen3.5-122B-A10B JANG 2S](#qwen35-122b-a10b-jang-2s) — Compact 122B · 46% smaller than MLX 4-bit
- [OmniCoder-9B (8-bit)](#omnicoder-9b-8-bit) — Coding agent (agentic trajectories)
- [Nemotron 3 Nano 30B-A3B (8-bit)](#nemotron-3-nano-30b-a3b-8-bit) — NVIDIA MoE · efficient inference
- [Nemotron 3 Super 120B-A12B (4.5-bit)](#nemotron-3-super-120b-a12b-45-bit) — NVIDIA 120B MoE · Mamba-2 + Attention hybrid
- [Nemotron Cascade 2 30B-A3B (nvfp4)](#nemotron-cascade-2-30b-a3b-nvfp4) — Mamba-2 + MoE + Attention hybrid · 3B active
- [Nemotron Server Compatibility](#nemotron-server-compatibility) — vllm-mlx only; mlx-openai-server and oMLX broken
- [Mistral Small 4 119B-A6B JANG 2L](#mistral-small-4-119b-a6b-jang-2l) — 119B MoE · 6B active · 30 GB · 82 tok/s · vision
- [Qwen3.5-35B-A3B JANG 4-bit (Mixed Precision)](#qwen35-35b-a3b-jang-4-bit-mixed-precision) — JANG adaptive quantization · 48% smaller than MLX 8-bit
- [Qwen3.6-35B-A3B (6-bit)](#qwen36-35b-a3b-6-bit) — Hybrid Gated DeltaNet + MoE + vision encoder · 3B active · 262K native (1M YaRN)
- [Uncensored Models Guide](uncen-model/uncen-model-guide.md) — research, benchmarks, recommendations (private submodule)

---

## ➕ Adding a Model to oMLX

### Step 1: Find a model

Browse MLX-format models on HuggingFace. oMLX supports MLX safetensors and JANG format (with fork) — not GGUF. Good sources:
- [`mlx-community`](https://huggingface.co/mlx-community) — official MLX conversions
- [`nightmedia`](https://huggingface.co/nightmedia) — hybrid-precision MLX quantizations (qx64-hi, qx86-hi)
- [`JANGQ-AI`](https://huggingface.co/JANGQ-AI) — JANG adaptive mixed-precision quantizations (requires fork overlay)
- [`inferencerlabs`](https://huggingface.co/inferencerlabs) — MLX quantizations for large models (Nemotron-H, etc.)

Look for repos where the files end in `.safetensors` and include a `config.json`.

### Step 2: Download the model

**Option A — Admin panel (easiest):**
1. Open `http://<MAC_STUDIO_IP>:8000/admin`
2. Go to the **HuggingFace** tab
3. Search for the model ID (e.g., `mlx-community/Qwen3.5-35B-A3B-8bit`)
4. Click **Download** — oMLX streams it directly into `~/.omlx/models/`

**Option B — CLI on Mac Studio:**
```bash
pip install huggingface-hub   # if not already installed
huggingface-cli download mlx-community/Qwen3.5-35B-A3B-8bit \
  --local-dir ~/.omlx/models/mlx-community/Qwen3.5-35B-A3B-8bit
```

oMLX expects the two-level org/repo directory structure: `~/.omlx/models/<org>/<repo>/`.

**Option C — Symlink an existing download:**
```bash
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
brew services restart omlx
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

## 🤖 Qwen3-Coder-Next (6-bit)

80B sparse MoE with only 3B active params. Optimized for coding agents and IDE integration. Performance comparable to Claude Sonnet 4.0 on SWE tasks. This is the **daily driver** model. The 6-bit quantization provides the best quality/size balance with 128-170K context on 96GB.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) |
| MLX 6-bit | [mlx-community/Qwen3-Coder-Next-6bit](https://huggingface.co/mlx-community/Qwen3-Coder-Next-6bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 80B total, 3B active (512 experts, 10 routed + 1 shared) |
| Density | Sparse MoE |
| Specialties | Code generation, agentic reasoning, tool use, long-horizon recovery |
| Tokens/sec | ~40-60 tok/s on M3 Ultra (6-bit) |
| Context Size | 128K - 170K on 96GB (262K native limit) |
| On-disk size | ~60 GB |
| Cache | KV cache on 12/48 Gated Attention layers; supports q8/q4/FP8 cache quantization |
| Key Benchmarks | SWE-Bench Verified 42.8%, SWE-Bench Pro 44.3% |

**Caveats:**
- Non-thinking mode only (no `<think>` blocks)
- MLX KV cache issues during conversation branching

---

## 🤖 Qwen3-Coder-30B-A3B Instruct (4-bit)

Smaller Qwen coder MoE tuned for agentic coding and tool use. This is a compact coding option for local MLX servers when you want something smaller than Qwen3-Coder-Next.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) |
| MLX 4-bit | [mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 30.5B total, 3.3B active |
| Density | Sparse MoE |
| Architecture | `qwen3_moe` |
| Specialties | Agentic coding, browser use, function calling |
| Context Size | 262,144 tokens native (256K) |
| On-disk size | 17.2 GB |
| Current server use | Not in the default live server roster |
| Key Notes | Non-thinking mode only; does not emit `<think></think>` blocks |

**Caveats:**
- Compact coding tradeoff, not a drop-in quality replacement for Qwen3-Coder-Next 80B
- Long contexts still need memory discipline in practice when paired with another loaded model

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

## 🤖 OmniCoder-9B (8-bit)

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

## 🤖 Nemotron 3 Nano 30B-A3B (8-bit)

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
- See [Nemotron Server Compatibility](#nemotron-server-compatibility) for server limitations

---

## 🤖 Nemotron 3 Super 120B-A12B (4.5-bit)

NVIDIA's 120B sparse MoE with 12B active params, using a hybrid Mamba-2 SSM + Attention architecture. Only ~55 of 88 layers use KV cache (attention layers); Mamba layers use fixed-size recurrent state, making context very memory-efficient.

| Spec | Value |
|:-----|:------|
| Base Model | [nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16) |
| MLX 4.5-bit | [inferencerlabs/NVIDIA-Nemotron-3-Super-120B-A12B-MLX-4.5bit](https://huggingface.co/inferencerlabs/NVIDIA-Nemotron-3-Super-120B-A12B-MLX-4.5bit) |
| Vendor | NVIDIA; MLX quantization by inferencerlabs |
| Parameters | 120B total, 12B active (512 routed experts, 22 active + 1 shared) |
| Architecture | Hybrid Mamba-2 SSM + Transformer Attention (88 layers: ~33 Mamba + ~55 Attention) |
| Density | Sparse MoE |
| Specialties | Large-scale reasoning, broad knowledge, multilingual |
| Tokens/sec | ~49.6 tok/s (tested on M3 Ultra 512GB); ~50 tok/s expected on 96GB |
| On-disk size | ~66.5 GB |
| Context Size | 262K native; configured to 200K (memory-safe with 12GB hot cache) |
| Hot Cache | **12GB** (per-model override; gives ~228K max context) |
| Key Benchmarks | 91.65% token accuracy, 1.336 perplexity (inferencerlabs coding test) |

**oMLX model ID:** `inferencerlabs/NVIDIA-Nemotron-3-Super-120B-A12B-MLX-4.5bit`

**Caveats:**
- Requires oMLX v0.2.20+ (Nemotron-H support via mlx-lm PR #992)
- At 66.5GB, leaves only ~29GB for OS + KV cache on 96GB; process enforcer at 88GB
- 9-bit variant (127GB) does NOT fit in 96GB — only the 4.5-bit is viable
- KV cache only on attention layers (~55 of 88); Mamba layers use fixed state = ~55 KB/token
- See [Nemotron Server Compatibility](#nemotron-server-compatibility) for server limitations

---

## 🤖 Nemotron Cascade 2 30B-A3B (nvfp4)

NVIDIA's second-generation Cascade model with a triple-hybrid architecture: Mamba-2 SSM + Mixture of Experts + Dense Attention. 30B total parameters with only 3B active per token. The nvfp4 (NVIDIA FP4, group size 16) quantization keeps the model at just 17GB with minimal quality loss.

| Spec | Value |
|:-----|:------|
| Base Model | [NVIDIA/Nemotron-Cascade-2-30B-A3B](https://huggingface.co/nvidia/Nemotron-Cascade-2-30B-A3B) |
| MLX nvfp4 | [RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4](https://huggingface.co/RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4) |
| Vendor | NVIDIA; MLX nvfp4 by RepublicOfKorokke |
| Parameters | 30B total, 3B active (128 experts, top-6 routed) |
| Density | Sparse MoE + Mamba-2 SSM hybrid |
| Architecture | 52 layers (46 Mamba-2 + MoE, 6 dense attention) |
| Specialties | Efficient hybrid inference, reasoning mode |
| Tokens/sec | ~55 tok/s generation, ~154 tok/s prefill |
| On-disk size | ~17 GB |
| Context Size | 262K |
| Cache | KV cache only on 6 attention layers (~0.2 GB at 32K) |
| Key Benchmarks | MMLU 93.0% (reasoning), 69.0% (no-think) |

**Caveats:**
- nvfp4 is a less common MLX quantization format — confirmed working on oMLX v0.2.20 + fork
- JANG-quantized variants of this model do NOT work (matmul shape mismatch at MoE gate — use nvfp4/mxfp4 MLX instead)
- See [Nemotron Server Compatibility](#nemotron-server-compatibility) for server limitations

---

## 🔌 Nemotron Server Compatibility

All Nemotron models (Nano, Super, Cascade 2) share the same server compatibility constraints due to NVIDIA's tokenizer implementation.

### Nemotron vs Qwen 3.5: Why the Difference?

Nemotron and Qwen 3.5 use the **same ChatML format** (`<|im_start|>`/`<|im_end|>`) and the **same tool-call XML** (`<tool_call><function=name><parameter=...>`). The incompatibility isn't about model capabilities — it's a **packaging problem**.

| | Qwen 3.5 | Nemotron |
|---|---|---|
| Chat template in `tokenizer_config.json` | Full Jinja2 template (~200 lines) | Empty string |
| Template location | Standard HuggingFace convention | Embedded in tokenizer Python code |
| Primary target runtime | HuggingFace ecosystem (any server) | vLLM (CUDA) with built-in handling |
| Any mlx-lm server works? | Yes | No — needs fallback logic |
| Tool format | Qwen3-style XML | Same Qwen3-style XML |

NVIDIA's primary target is **vLLM on CUDA GPUs**, which handles Nemotron templates internally. They didn't ship the template in `tokenizer_config.json` where the broader HuggingFace ecosystem (including mlx-lm, mlx-openai-server, oMLX) expects it. The architectural differences (Mamba-2 SSM hybrid, sparse attention) are irrelevant to this issue — it's purely about how the chat template is distributed.

**If someone contributed the Nemotron chat template as a fallback** to mlx-openai-server or oMLX (like vllm-mlx did), those servers would work with Nemotron too.

### Architecture Comparison

| | Qwen 3.5 (122B/35B) | Nemotron Cascade 2 | Nemotron Super 120B |
|---|---|---|---|
| Type | Transformer MoE + GatedDeltaNet | Mamba-2 + MoE + Attention | Mamba-2 + MoE + Attention |
| KV cache layers | All layers | 6 of 52 | ~55 of 88 |
| SSM layers | GatedDeltaNet (fixed state) | 46 Mamba-2 layers | ~33 Mamba-2 layers |
| Tool format | Qwen3-style XML | Qwen3-style XML | Qwen3-style XML |
| Reasoning | `<think>` tags | `<think>` tags | `<think>` tags |

### Server Compatibility

Servers that rely on `tokenizer_config.json` for the chat template cannot format messages correctly — prompts lack `<|im_start|>`/`<|im_end|>` wrapping, degrading even basic chat.

Nemotron also requires specialized parsers:
- **Reasoning:** `think` parser for `<think>` tag extraction
- **Tool calling:** `nemotron` parser for tool-call detection and structured output

| Server | Chat Template | Tool Parser | Reasoning Parser | Status |
|--------|--------------|-------------|-----------------|--------|
| **vllm-mlx** | Built-in `NEMOTRON_CHAT_TEMPLATE` fallback, auto-detected by model name | `nemotron` tool parser | `think_parser` (generic `<think>` tags) | **Works** |
| **mlx-openai-server** | No fallback — empty template used as-is | None | None | **Broken** — echoes raw tool XML |
| **oMLX** | No fallback — relies on `tokenizer.apply_chat_template()` | None | None | **Broken** — malformed prompts |

**Recommendation:** Serve Nemotron models exclusively via **vllm-mlx** with:
```bash
~/vllm-mlx-env/bin/vllm-mlx serve <model-path> \
  --reasoning-parser think \
  --enable-auto-tool-choice --tool-call-parser nemotron \
  --port 8000 --host 0.0.0.0
```

On mlx-openai-server and oMLX, Nemotron models may work for simple direct chat (without tools), but responses will be degraded due to missing ChatML formatting. Tool-using clients (OpenClaw, Pi) will see the model echo raw XML tags instead of answering.

---

## 🤖 Mistral Small 4 119B-A6B JANG 2L

Mistral's 119B sparse MoE with 6B active params and Pixtral vision encoder. JANG_2L quantization compresses to just 30 GB — 52% smaller than MLX Community 4-bit (63 GB) — while achieving 94% MMLU and **5x faster prefill** (216 vs 43 tok/s). Uses MLA (Multi-Head Latent Attention) and 128 routed MoE experts with top-4 routing.

| Spec | Value |
|:-----|:------|
| Base Model | [MistralAI/Mistral-Small-4-119B-2603](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) |
| JANG 2L | [JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L](https://huggingface.co/JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L) |
| Vendor | Mistral AI; JANG quantization by JANGQ-AI |
| Parameters | 119B total, 6B active (128 experts, top-4 routed + shared) |
| Density | Sparse MoE |
| Architecture | 36 MoE layers, MLA attention (kv_lora_rank=256, q_lora_rank=1024) |
| Vision | Pixtral encoder, 1540px max image resolution |
| Quantization | JANG_2L: 2.14-bit avg — attention 8-bit, shared experts 6-bit, routed experts 2-bit, router 16-bit |
| Tokens/sec | **82 tok/s** gen, **216 tok/s** prefill (M3 Ultra) |
| On-disk size | ~30 GB |
| Peak RAM | 40 GB |
| Context Size | Not specified (base model supports 128K) |
| Reasoning | `[THINK]`/`[/THINK]` tags via `reasoning_effort: "high"` |
| Key Benchmarks | MMLU 94% (200Q, reasoning mode), 5 subjects at 100% |

**JANG variant comparison:**

| Variant | Bits | Size | RAM | Gen tok/s | Prefill tok/s | Fits on |
|---------|------|------|-----|-----------|---------------|---------|
| **JANG_2L** | 2.14 | 30 GB | 40 GB | 82 | 216 | 48 GB+ |
| JANG_4M | 4.08 | 57 GB | 68 GB | 80 | 202 | 96 GB+ |
| JANG_6M | 6.04 | 84 GB | 95 GB | 74 | 160 | 128 GB+ |
| MLX Community 4-bit | 4.0 | 63 GB | 68 GB | 84 | 43 | 96 GB+ |

**Server compatibility:**

| Server | Status | Notes |
|--------|--------|-------|
| vllm-mlx | **Broken** | Current local MLX stack still lacks native `mistral4` MLA support |
| mlx-openai-server | **Broken** | Same upstream `mlx-lm` limitation; no repo-managed local patch is maintained |
| oMLX | **Broken** | Same upstream `mlx-lm` limitation |

**Root cause:** Mistral Small 4 uses `mistral4` text architecture with **MLA (Multi-Head Latent Attention)** — `kv_lora_rank=256`, `q_lora_rank=1024`. Upstream `mlx-lm` only has `mistral3.py`, which implements standard GQA, not MLA. Current MLX servers here therefore load the weights but do not support correct inference for this model family.

Chat template is in `tokenizer_config.json` (5,919 chars) with full tool support using Mistral native format (`[INST]`, `[TOOL_CALLS]`, `[ARGS]`). No Nemotron-style template issues — the blocker is purely the missing MLA architecture implementation in mlx-lm.

**Caveats:**
- **Current MLX servers in this repo are not usable for Mistral Small 4** until upstream `mlx-lm` adds native `mistral4` support with MLA attention
- Must use `temperature=1.0` — greedy decoding (temp=0) causes infinite thinking loops
- Recommended sampling: `top_p=0.95`, `top_k=40`
- JANG is the only working quantization for this model — MLX uniform 2/3/4-bit all produce ~25% MMLU (broken)
- Reasoning uses `[THINK]`/`[/THINK]` (Mistral format), not `<think>`/`</think>` (Qwen format)
- MMLU benchmark used reasoning mode enabled — single-pass without reasoning would score lower
- **Official full-feature deployment guidance points to `vLLM`**, not MLX. See Mistral's [self-deployment docs](https://docs.mistral.ai/deployment/self-deployment) and the base model card's `vLLM` section: [mistralai/Mistral-Small-4-119B-2603](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603)
- **For Apple Silicon local use, the practical community path is `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`**, not MLX. See [LM Studio community GGUF](https://huggingface.co/lmstudio-community/Mistral-Small-4-119B-2603-GGUF), [Unsloth GGUF](https://huggingface.co/unsloth/Mistral-Small-4-119B-2603-GGUF), and [AaryanK GGUF notes](https://huggingface.co/AaryanK/Mistral-Small-4-119B-2603-GGUF)
- **For this 96 GB Mac Studio, `Q4_K_M` is the realistic GGUF starting point** (~72 GB on disk from the LM Studio build); larger `Q6_K` / `Q8_0` builds are likely too tight or too large for comfortable local use

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
- Verified on `mlx-openai-server` v1.7.0 in multi-handler mode alongside `Qwen3-Coder-Next-6bit`

**Caveats:**
- Default chat template emits `<think>` unconditionally; `chat_template_kwargs.enable_thinking=false` did not suppress it in pilot testing — needs follow-up on parser / template wiring
- Compatibility on `oMLX` and `vllm-mlx` not yet verified (hybrid Gated DeltaNet is new; upstream support may lag)
- MTP speculative decoding benefits require server-side support — not yet wired in `mlx-openai-server`
