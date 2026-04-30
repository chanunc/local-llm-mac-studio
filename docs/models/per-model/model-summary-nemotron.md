# Model Summary: Nemotron Family

NVIDIA's Nemotron 3 / Cascade-2 lineage as catalogued in this stack. Three variants (32 B/3 B-active Nano, 120 B/12 B-active Super, and 30 B/3 B-active Cascade-2 with Mamba-2 hybrid) plus the cross-cutting server-compatibility note that explains why **only `vllm-mlx`** correctly serves Nemotron models on Apple Silicon.

## Index

- [Nemotron 3 Nano 30B-A3B (8-bit)](#nemotron-3-nano-30b-a3b-8-bit) — NVIDIA MoE · efficient inference
- [Nemotron 3 Super 120B-A12B (4.5-bit)](#nemotron-3-super-120b-a12b-45-bit) — NVIDIA 120B MoE · Mamba-2 + Attention hybrid
- [Nemotron Cascade 2 30B-A3B (nvfp4)](#nemotron-cascade-2-30b-a3b-nvfp4) — Mamba-2 + MoE + Attention hybrid · 3B active
- [Nemotron Server Compatibility](#nemotron-server-compatibility) — vllm-mlx only; mlx-openai-server and oMLX broken

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

## See also

- Catalog stub: [`docs/models/model-summary.md` § Nemotron Family](../model-summary.md#nemotron-family-vllm-mlx-only)
- Sibling per-model files: [`model-summary-qwen-3-5.md`](model-summary-qwen-3-5.md) · [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md) · [`model-summary-qwen-3-coder.md`](model-summary-qwen-3-coder.md)
