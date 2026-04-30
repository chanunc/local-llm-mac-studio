# Model Summary

Detailed specs, benchmarks, and caveats for the main model set used across the Mac Studio servers. For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Adding a Model to oMLX](#adding-a-model-to-omlx)
- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — Vision + reasoning + tool use · 15 GB · 256K
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
- [Qwen3.6-27B JANG 4M (Dense + VL)](#qwen36-27b-jang-4m-dense--vl) — Dense 27B Qwen3.6 hybrid · ViT · 17.5 GB · JANG 4/8-bit · vllm-mlx text-only
- [Qwen3.6-27B (6-bit Standard MLX)](#qwen36-27b-6-bit-standard-mlx) — Same dense 27B Qwen3.6 + ViT · 22 GB · uniform 6-bit · llmster recommended (3-5× faster agent loop than vllm-mlx)
- [Qwen3.6-35B Rust LoRA (jedisct1, 8-bit)](#qwen36-35b-rust-lora-jedisct1-8-bit) — 35B/3B MoE · uniform 8-bit MLX · LoRA merged on 356K Rust commits · best wall-time on agent loops
- [Ling-2.6-flash mlx-6bit (bailing_hybrid)](#ling-26-flash-mlx-6bit-bailing_hybrid) — 104B/7.4B MoE · 6-bit MLX · MLA + linear-attention SSM · vllm-mlx + 3 patches
- [MiMo V2.5 4-bit, 130-expert pruned (jedisct1)](#mimo-v25-4-bit-130-expert-pruned-jedisct1) — 4-bit MLX · pruning calibration loss → not viable for agent workloads
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
- Validated through-API on `mlx-openai-server` v1.7.1 single-handler mode on 2026-04-18: text + vision smoke tests pass; full benchmark in [model-benchmark-api-server.md](model-benchmark-api-server.md#qwen36-35b-a3b-6-bit) shows 52.5 tok/s @ 512 → 35.6 tok/s @ 128K
- Reference YAML: [mlx-openai-server-qwen36-35b.yaml](../server/mlx-openai-server/mlx-openai-server-qwen36-35b.yaml)

**Caveats:**
- Default chat template emits `<think>` unconditionally; `chat_template_kwargs.enable_thinking=false` has no effect through `mlx-openai-server` 1.7.1 — same hookup gap as Gemma 4 ([#279](https://github.com/cubist38/mlx-openai-server/issues/279), fixed on `main`, awaiting 1.7.2)
- `oMLX` is **not recommended** for Qwen3.6 today: open issues [#812](https://github.com/jundot/omlx/issues/812) (tool calling silently stops), [#819](https://github.com/jundot/omlx/issues/819) (lmstudio 6bit fails to load), [#827](https://github.com/jundot/omlx/issues/827) (DFlash load failure), [#841](https://github.com/jundot/omlx/issues/841) (>127K silent crash)
- `waybarrios/vllm-mlx` post-PR [#278](https://github.com/waybarrios/vllm-mlx/pull/278) is the only Apple-Silicon server that exposes MTP/speculative decoding through OpenAI API for Qwen3.6 today, but inherits the upstream `mlx-lm` hybrid-attention cache bug ([#1162](https://github.com/ml-explore/mlx-lm/issues/1162)) — not deployed here yet
- MTP speculative decoding through `mlx-openai-server` remains unwired ([#177](https://github.com/cubist38/mlx-openai-server/issues/177), [#204](https://github.com/cubist38/mlx-openai-server/issues/204))
- Streaming `reasoning_content` / `content` split **does work cleanly** with the `qwen3_vl` parser on `mlx-openai-server` 1.7.1 — the Gemma-4-only streaming-leak bug ([#280](https://github.com/cubist38/mlx-openai-server/issues/280)) does not affect Qwen3.6

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

**Performance** (vllm-mlx, [`model-benchmark-api-server.md`](model-benchmark-api-server.md#qwen36-27b-jang-4m-dense--vl)):
- Gen: 36.5 tok/s @ 512 → 34.6 @ 8K → 27.0 @ 64K
- Prefill: ~310-345 tok/s across 512-32K, falling to 274 @ 64K
- TTFT: 1.7 s @ 512, 23.8 s @ 8K, 240 s @ 64K
- ~30-40 % slower gen and ~5× slower prefill than `Qwen3.6-35B-A3B-6bit` on `mlx-openai-server` (the MoE 3B-active sibling) — the dense-vs-MoE tradeoff is exactly as expected at full context

**Tool calling** ([`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-jangq-aiqwen36-27b-jang_4m)):
- API-level: 5/5 single-call pass, 3-turn agentic loop completes in 14.84 s (read → write → summary)
- Streaming `tool_calls` deltas verified via direct curl
- OpenCode end-to-end (2026-04-24): browse 114.25 s median, search 163.59 s median (medians across 3 measured runs each; p5-p95 89-251 s browse, 162-266 s search). ~2.7× slower than Qwen3.5-35B-A3B JANG 4K on the same scenarios — the expected dense-vs-sparse gap at OpenCode's ~10k-token system prompt

**Caveats:**
- **Vision input is not exposed via vllm-mlx** (`MLLM=False` at load). To exercise the ViT, deploy on `vmlx` (MLX Studio bundled Python — HF card recommendation) or `mlx-openai-server` with the `multimodal` handler. Neither has been validated for this specific model yet.
- **`usage.prompt_tokens=0`** for both streaming and non-streaming responses on vllm-mlx 0.2.6 — the JANG-loaded `qwen3_5` model does not propagate prompt-token count into the OpenAI usage block. Bench output computes prefill via the model's own tokenizer instead. Same shape as the Qwen3.5-122B JANG 2S note in `model-benchmark-api-server.md`.
- **Verbose reasoning preamble** — even on simple prompts the model emits ~80-200 tokens of `<think>`-equivalent reasoning into `reasoning_content` before the tool call. Consider `enable_thinking=false` via `chat_template_kwargs` if you need the lowest possible per-turn latency (not validated through vllm-mlx).
- **Client-config sync** — because vllm-mlx is single-model, local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` must default to whichever model is live on port 8000. Pointing at `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` while the server serves 27B returns HTTP 404 from the chat-completion endpoint. Keep those local configs aligned with `configs/client/vllm-mlx/`.

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

**Performance** (llmster, [`model-benchmark-api-server.md`](model-benchmark-api-server.md#qwen36-27b-6-bit-standard-mlx-on-llmster-vs-vllm-mlx)):
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

**See also:** [`docs/server/llmster/summary.md`](../server/llmster/summary.md) for the full LM Studio headless server runbook · [`docs/models/model-benchmark-agent-tool-call.md` § Server comparison](model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30) for the raw bench data.

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
| Tokens/sec | ~83 tok/s gen @ 256 ctx, ~80 tok/s @ 8K (bench: [`benchmarks/qwen36-35b-rust/api-typical.json`](benchmarks/qwen36-35b-rust/api-typical.json)) |
| TTFT | 0.31 s @ 256, 1.00 s @ 2K, 3.70 s @ 8K |
| On-disk size | ~35 GB |
| Context Size | 262,144 native (262K) |
| License | Apache-2.0 (base) |

**vllm-mlx model ID:** `jedisct1/Qwen3.6-35B-rust.mlx` (served from `~/.omlx/models/jedisct1--Qwen3.6-35B-rust.mlx`)

**Server config (vllm-mlx):** standard CLI with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` (same parser flags as the non-LoRA Qwen3.6 variants — the LoRA-merged weights still emit the Qwen3-coder XML tool-call format).

**Tool calling** ([`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-jedisct1qwen36-35b-rustmlx)):
- API-level: 4/5 single-call pass · single-tool 1.42-1.80 s 🥈 · 3-turn agentic loop 6.99 s
- OpenCode end-to-end (2026-04-30): browse 13.94 s 🥈 · search 26.31 s 🥈 — second-fastest in the stack on both scenarios
- ⚠ One agentic-reasoning prompt (`Find the largest file in /tmp`) hits the 1024-token cap because the model emits long Gemini-style chain-of-thought as `content` (no `<think>` wrapper, so the `qwen3` reasoning parser doesn't strip it). Other scenarios pass cleanly.

**Caveats:**
- Reasoning emitted as `content` (not `<think>`) — not extracted by `--reasoning-parser qwen3`. If you need a clean reasoning/content split, prefer Qwen3.5-35B-A3B JANG 4K which uses proper `<think>` tags.
- Rust-domain LoRA: not measured to degrade general performance, but explicitly tuned for code-diff workloads.
- Vision encoder defined in tokenizer but vllm-mlx loads as text-only (`MLLM=False`).

---

## Ling-2.6-flash mlx-6bit (`bailing_hybrid`)

InclusionAI's `bailing_hybrid` MoE — **104 B total / 7.4 B active** — sparse-expert hybrid mixing 4 MLA layers (absorbed-form Multi-head Latent Attention) with 28 Lightning-style linear-attention recurrence layers. 256 routed experts (8/tok, group-limited top-8) + 1 shared, sigmoid `noaux_tc` routing. 6-bit MLX uniform quant, ~80 GB on disk. Text-only, no `<think>` reasoning emitted. Currently **production primary on this Mac Studio**.

| Spec | Value |
|:-----|:------|
| Base Model | [inclusionAI/Ling-2.6-flash](https://huggingface.co/inclusionAI/Ling-2.6-flash) |
| Quant | [mlx-community/Ling-2.6-flash-mlx-6bit](https://huggingface.co/mlx-community/Ling-2.6-flash-mlx-6bit) |
| Format | MLX safetensors (uniform 6-bit, group_size=64) |
| Architecture | `BailingMoeV2_5ForCausalLM` (`bailing_hybrid`) — 32 layers (4 MLA + 28 linear-attn) |
| Parameters | 104 B total, 7.4 B active per token (256 routed + 1 shared) |
| Tokens/sec | 64.5 @ 512 → 64.4 @ 8K → 57.3 @ 64K (vllm-mlx, [bench](model-benchmark-api-server.md#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid)) |
| On-disk size | ~80 GB |
| Context Size | 131,072 native; **64K practical ceiling on M3 Ultra** — 128K OOMs |
| Reasoning | None — does not emit `<think>` blocks |
| Vision | No — text-only |
| License | MIT (base) |

**vllm-mlx model ID:** `mlx-community/Ling-2.6-flash-mlx-6bit`

**Server config (vllm-mlx):** `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits Hermes-format `<tool_call>{json}</tool_call>` blocks — `qwen3_coder` won't parse these). No `--reasoning-parser`.

**Requires three local patches** before the model will load:
1. Vendor `mlx_lm/models/bailing_hybrid.py` from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227)
2. [`scripts/patch_mlx_lm_threadlocal_stream.py`](../../scripts/patch_mlx_lm_threadlocal_stream.py) — per-thread lazy `generation_stream` accessor
3. [`scripts/patch_vllm_mlx_inline_gen.py`](../../scripts/patch_vllm_mlx_inline_gen.py) — replace `await asyncio.to_thread(...)` with inline sync calls in `vllm_mlx/engine/simple.py`

mlx-openai-server is **incompatible** — its inference-worker thread design is more deeply thread-coupled than vllm-mlx and patch #3 doesn't apply directly.

**Tool calling** ([`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit)):
- API-level: 5/5 single-call pass · 3-turn agentic loop **4.74 s** 🏆 (fastest in this stack)
- OpenCode end-to-end (2026-04-30): browse 25.75 s · search 29.64 s — third-fastest, behind only the two A3B-sparse Qwen3.6 variants

**See also:** [`docs/models/model-summary-ling.md`](model-summary-ling.md) for the full deployment guide (vendoring PR #1227, patch scripts, sampling config, RAM/VRAM profile).

---

## MiMo V2.5 4-bit, 130-expert pruned (jedisct1)

Xiaomi's `MiMoV2ForCausalLM` (`mimo_v2`), pruned by `jedisct1` to keep only the first 130 experts per layer plus a quantized output head. ~80 GB on disk, 4-bit MLX uniform quant. Multimodal chat template (text + vision + audio pads) but text-only output via vllm-mlx. Default thinking ON. Deployed and benchmarked 2026-04-30 — **not viable as an agent backbone** (failure investigation documented separately).

| Spec | Value |
|:-----|:------|
| HuggingFace | [jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead](https://huggingface.co/jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead) |
| Base | [XiaomiMiMo/MiMo-V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5) |
| Architecture | `MiMoV2ForCausalLM` (`mimo_v2`) |
| Quant | 4-bit uniform MLX (`group_size=64`) |
| Pruning | First 130 experts kept per layer (config `expert_keep_indices`) |
| On-disk size | ~80 GB |
| Tool-call format | Hermes-style `<tool_call><function=name><parameter=k>v</parameter></function></tool_call>` |
| Reasoning | `<think>…</think>` blocks |
| Multimodality | Vision + audio + video pads in chat template; vllm-mlx loads text-only |

**Status: NOT in production.** Three configurations tested (baseline thinking-on, Fix #1 thinking-off, Fix #2 + Hermes parser) — all produce **near-zero pass rates (0-1 of 3 runs per scenario)** on OpenCode end-to-end. Failure signature: `output_tokens=8192` with no tool call emitted. Single-tool API harness *does* pass cleanly, so the issue is OpenCode's 10-tool catalog + system prompt overwhelming this pruned variant.

**Root cause:** Heavy expert pruning to 130/layer degrades simultaneous instruction-following and structured output under long system prompts. Architectural — not a parser or prompt issue. Production reverted to Ling-2.6-flash.

**Requires PR [ml-explore/mlx-lm#1219](https://github.com/ml-explore/mlx-lm/pull/1219) vendored** (`mimo_v2.py`, 556 lines) — `mimo_v2` arch is not in mlx-lm 0.31.3.

**Caveats:**
- **Not viable as an agent backbone** in this stack — disabling thinking and switching to Hermes parser do not reliably fix tool-calling. Pass rates remain near 0/3 with non-deterministic recovery.
- **Retry only with a less-aggressive pruning variant** (e.g. `first200experts`) when one becomes available.

**See also:** [`docs/models/model-summary-mimo-v2.5.md`](model-summary-mimo-v2.5.md) for the TL;DR (Findings / Limitations / Blocker), full three-config benchmark comparison, and deployment instructions.

---

## Gemma 4 26B-A4B (4-bit)

Google's first mixture-of-experts Gemma. The 26B-A4B activates only ~4B parameters per token (128 experts, top-4 routing) giving MoE-class throughput while supporting 256K context, native vision+video+audio multimodal input, and built-in thinking mode. Verified on Mac Studio M3 Ultra (96 GB) on April 17, 2026.

| Spec | Value |
|:-----|:------|
| Base Model | [google/gemma-4-26b-a4b-it](https://huggingface.co/google/gemma-4-26b-a4b-it) |
| MLX 4-bit | [mlx-community/gemma-4-26b-a4b-it-4bit](https://huggingface.co/mlx-community/gemma-4-26b-a4b-it-4bit) |
| Format | MLX safetensors (multimodal / `mlx_vlm` handler) |
| Vendor | Google DeepMind; MLX conversion by mlx-community |
| Architecture | `Gemma4ForConditionalGeneration` — MoE text + vision encoder + audio encoder |
| Parameters | 26B total, ~4B active (128 experts, top-4 routing) |
| Quantization | 4-bit (group size 64), with 8-bit on MoE gate/up/down projectors of layer 0 |
| Specialties | Thinking mode (chain-of-thought), image + video + audio input, tool calling, 256K context |
| On-disk size | ~15 GB |
| Context Size | 262,144 tokens (256K); sliding window 1024 on intermediate layers |
| License | Gemma Terms of Use |
| Requirements | `mlx-openai-server >= 1.7.1`, `mlx-lm >= 0.31.2`, `mlx-vlm >= 0.4.4` |

**mlx-openai-server model ID:** `mlx-community/gemma-4-26b-a4b-it-4bit`

**Server config:** `model_type: multimodal`, `tool_call_parser: gemma4`, `reasoning_parser: gemma4`, `context_length: 262144`

**Reference YAML:** [mlx-openai-server-gemma4.yaml](../server/mlx-openai-server/mlx-openai-server-gemma4.yaml)

### Benchmarks (mlx-openai-server 1.7.1, M3 Ultra 96 GB, Apr 17 2026)

Method: streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens include both `reasoning_content` (thinking) and `content` (answer) phases.

> **512 note:** run 1 was a cold-start (59.4 tok/s gen, 28 tok/s prefill, 18.7s TTFT). Table shows warm values (runs 2–3).

#### Generation Speed (tok/s)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **62.5** | 1,710 | 0.30 |
| 4K | 54.6 | 3,117 | 1.32 |
| 8K | 60.6 | 3,154 | 2.60 |
| 32K | 50.6 | 2,892 | 11.34 |
| 64K | 42.0 | 2,542 | 25.78 |
| 128K | 27.1 | 1,995 | 65.70 |

Prefill peaks at 8K (~3,154 tok/s) — typical for sliding-window models where GPU utilisation is highest in the mid-range. Generation speed drops gradually with context due to sliding window KV growth.

### Caveats

- **Thinking always on (streaming):** Bug [#280](https://github.com/cubist38/mlx-openai-server/issues/280) — reasoning parser not applied mid-stream in 1.7.1. Fixed on `main` but not yet released. Non-streaming requests separate `content` / `reasoning_content` correctly (verified).
- **`chat_template_kwargs` ignored:** Bug [#279](https://github.com/cubist38/mlx-openai-server/issues/279) — `enable_thinking: false` has no effect in 1.7.1. Fixed on `main`. Thinking cannot currently be suppressed via API.
- **vllm-mlx:** Not tested. Bug [#38855](https://github.com/vllm-project/vllm/issues/38855) means reasoning parser strips `<|channel>` markers — not recommended until vllm-mlx picks up the vLLM main fix.
- **oMLX:** Not tested. The 4-bit MLX port includes `chat_template.jinja` so the tokenizer issue seen with 8-bit variants does not apply here; however, Gemma 4 parsers are not registered in oMLX's parser map.

### Variant attempted but blocked: `JANGQ-AI/Qwen3.6-35B-A3B-JANGTQ4`

A TurboQuant-weight (`.tq_packed` + `.tq_norms`) quant of the same base model (~20 GB on disk). Loader requires the private `jang_tools.load_jangtq` / `load_jangtq_vlm` modules bundled with `vmlx[jang]==1.3.61`'s fast path. Neither module is in the PyPI `jang==2.3.2` package nor in the public `jjang-ai/jangq` GitHub repo (verified with a fresh clone). vmlx's own dequant-and-requant fallback is commented as producing gibberish on this family, which we reproduced: weights load at correct shapes (~19.5 GB peak), but generation collapses into repeating loops (`"Paris capital Paris capital..."` on a `"The capital of France is"` prompt). Conclusion: not runnable on M3 Ultra with public tooling until upstream publishes the TQ loaders. Parked; model removed from disk.

#### Unblocking path — corrected & deployed (2026-04-20)

The 2026-04-20 deploy pass revealed the original unblock claim ("pip install `vmlx>=1.3.49`") was **incorrect**. Deeper inspection of `~/vmlx-env/` (already at `vmlx==1.3.61` from the Apr-17 attempt) showed zero results for `find ~/vmlx-env -name 'load_jangtq*'`, `tq_kernel`, `hadamard_kernel`, `gather_tq_kernel`, or `fused_gate_up_kernel`. `gh search code 'def load_jangtq_model' --owner jjang-ai` returns zero hits — **the loader is not committed to any public jjang-ai repo**. The pypi `jang==2.3.2` and `vmlx` wheels both lack it.

**Where the loader actually ships**: inside the MLX Studio Electron DMG's bundled relocatable Python, built by `panel/scripts/bundle-python.sh` (referenced in the `vmlx` CHANGELOG 1.3.62 entry "Bundled Python Distribution"). Installing `/Applications/vMLX.app` from `https://github.com/jjang-ai/mlxstudio/releases/download/v1.3.65/vMLX-1.3.65-arm64.dmg` lays down `/Applications/vMLX.app/Contents/Resources/bundled-python/python/` containing `lib/python3.12/site-packages/jang_tools/` with `load_jangtq.py`, `load_jangtq_vlm.py`, and `turboquant/{tq_kernel,hadamard_kernel,gather_tq_kernel,fused_gate_up_kernel}.py`. That bundled Python has `vmlx_engine 1.0.3` + `jang_tools 2.4.1` and can be invoked headlessly — **no GUI session required**, despite the Electron wrapper. The shipped `bin/vmlx` shebang points at the maintainer's build path, so use `python3 -m vmlx_engine.cli serve …` directly (the CHANGELOG itself notes "Bundled spawn uses `python3 -m vmlx_engine.cli serve` (avoids shebang issues)").

- **Upstream `jjang-ai/jangq#5`** (filed 2026-04-19 by `mshicom`) is the authoritative open record of the PyPI block — loader stubs on `jang-spec-plan5-bundle-python-validation` are incomplete.
- **Incompatible flags** still hold: per [vmlx#81](https://github.com/jjang-ai/vmlx/issues/81), JANGTQ models must use the native fast path only — `--smelt` and `--flash-moe` will raise `ValueError` on `weight_format=mxtq`.

**Deployment outcome (2026-04-20)**: `dealignai/MiniMax-M2.7-JANGTQ-CRACK` (~57 GB weights) is now deployable on the Mac Studio M3 Ultra via the bundled-Python headless path. Server startup log confirms the fast path (`JANGTQ v2 loaded in 10.1s: MiniMax-M2.7 (0.0-bit avg, native TQ, no dequant)` + `Replaced 186 modules` with `TurboQuantLinear`), and short-context decode measures **43.72 tok/s at ~52 prompt tokens / 39.42 tok/s at ~510 prompt tokens**, in line with the 42 tok/s baseline from the vmlx maintainer's M3 Ultra verification. Peak wired-memory under generation ≈ 66.6 GB (well within 96 GB). Empirical CRACK refusal-rate benchmarks live in the private `docs/models/uncen-model` submodule per project convention for uncen-family detail. See CLAUDE.md for the MLX Studio / bundled-Python server-switch snippet alongside `vllm-mlx` / `mlx-openai-server` / `oMLX`. Single-vendor dependency risk remains — until `jjang-ai/jangq#5` lands the loader in the public `jang-tools` package, re-applying the DMG install is the only supported path after a reinstall.

**Second JANGTQ variant deployed (2026-04-20)**: `dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK` (11.6 GB weights, 12 shards, vision-language) loads via the same bundled-Python fast path in **1.4 s** and sustains **~66 tok/s decode** at 700 completion tokens — decisively faster than MiniMax-M2.7 thanks to ~3 B active params per token. Quality is impaired, however: with default `enable_thinking=true` the model early-exits with 1–2 tokens on 6/10 mlabonne harmful_behaviors prompts (empty-`<think>` interaction with the CRACK abliteration); with `chat_template_kwargs.enable_thinking=false` the 2-bit routed-expert quant produces degenerate, inverted, or garbled output on half the prompts — 8/10 keyword-match but only **4/10 useful compliance**. Not a replacement for MiniMax-M2.7 on compliance-critical work, but a viable vmlx install smoke-test and low-RAM fallback. Empirical detail in the `docs/models/uncen-model` submodule: `qwen36-35b-jangtq2-crack-benchmark.md`.

**Third JANGTQ variant deployed (2026-04-20) — new efficiency-frontier winner**: `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` (**19.7 GB** weights, 19 shards, vision-language) loads via the same bundled-Python fast path in **1.7 s** and sustains **~64 tok/s decode** at 700 completion tokens — effectively identical throughput to the 2-bit sibling, confirming that 8-bit attention/shared-expert weights dominate per-token compute rather than routed-expert bitwidth. Quality is the inverse of JANGTQ2: with default `enable_thinking=true` the model produces full 300-token coherent responses on **10/10** mlabonne harmful_behaviors prompts (temp=1.0, avg latency **4.66 s** — the fastest in the uncen-model set). Verified with a 1500-token tutorial generation: fully-formed structured output with materials list, step-by-step instructions, and safety warnings, `finish_reason=length`. This **ties MiniMax-M2.7-JANGTQ-CRACK on useful compliance at 1/3 the weights (19.7 GB vs 57 GB)** and establishes the new recommended default for uncensored content on this hardware. Thinking-template interaction reverses vs JANGTQ2: thinking-OFF *destabilises* this variant (3 prompts early-exit). The extra 2 bits on routed experts preserves enough expert capacity for CRACK abliteration to produce substantive rather than degenerate output. Empirical detail: `docs/models/uncen-model/qwen36-35b-jangtq4-crack-benchmark.md`.
