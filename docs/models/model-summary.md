# Model Summary

Detailed specs, benchmarks, and caveats for the main model set used across the Mac Studio servers. For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Adding a Model to oMLX](#adding-a-model-to-omlx)
- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — Vision + reasoning + tool use · 15 GB · 256K
- [Qwen3-Coder Family (MLX 6-bit + 4-bit)](#qwen3-coder-family-mlx-6-bit--4-bit) — 2 variants: Coder-Next 6-bit (daily driver), Coder-30B-A3B 4-bit. Detail at [`per-model/model-summary-qwen-3-coder.md`](per-model/model-summary-qwen-3-coder.md)
- [Qwen3.5 Family (MoE + dense distilled + JANG)](#qwen35-family-moe--dense-distilled--jang) — 4 variants: 27B Opus Distilled, 122B-A10B 4-bit, 122B-A10B JANG 2S, 35B-A3B JANG 4K. Detail at [`per-model/model-summary-qwen-3-5.md`](per-model/model-summary-qwen-3-5.md)
- [OmniCoder-9B (8-bit)](#omnicoder-9b-8-bit) — Coding agent (agentic trajectories)
- [Nemotron Family (vllm-mlx only)](#nemotron-family-vllm-mlx-only) — 3 variants + server compatibility note: Nano 30B, Super 120B, Cascade-2 30B. Detail at [`per-model/model-summary-nemotron.md`](per-model/model-summary-nemotron.md)
- [Mistral Small 4 119B-A6B JANG 2L](#mistral-small-4-119b-a6b-jang-2l) — 119B MoE · 6B active · 30 GB · 82 tok/s · vision
- [Qwen3.6 Family (Hybrid Gated DeltaNet + Vision)](#qwen36-family-hybrid-gated-deltanet--vision) — 5 variants: 35B-A3B 6-bit / 4-bit, 27B JANG 4M, 27B 6-bit, 35B Rust LoRA. Full per-variant detail at [`per-model/model-summary-qwen-3-6.md`](per-model/model-summary-qwen-3-6.md)
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

## Qwen3-Coder Family (MLX 6-bit + 4-bit)

Two Qwen3-Coder variants used here. Per-variant detail (specs, server config, caveats) lives in the dedicated per-model file: **[`per-model/model-summary-qwen-3-coder.md`](per-model/model-summary-qwen-3-coder.md)**.

| Variant | Type | Size | Quant | Best For | Detail |
|:--------|:-----|----:|:------|:---------|:-------|
| Qwen3-Coder-Next 6-bit | Sparse MoE 80B/3B | 60 GB | Uniform 6-bit MLX | Daily coding driver | [link](per-model/model-summary-qwen-3-coder.md#qwen3-coder-next-6-bit) |
| Qwen3-Coder-30B-A3B Instruct 4-bit | Sparse MoE 30.5B/3.3B | 17.2 GB | Uniform 4-bit MLX | Compact coding option | [link](per-model/model-summary-qwen-3-coder.md#qwen3-coder-30b-a3b-instruct-4-bit) |

---

## Qwen3.5 Family (MoE + dense distilled + JANG)

Four Qwen3.5 variants catalogued here. Per-variant detail (specs, server config, caveats, JANG fork notes) lives in the dedicated per-model file: **[`per-model/model-summary-qwen-3-5.md`](per-model/model-summary-qwen-3-5.md)**.

| Variant | Type | Size | Quant | Best For | Detail |
|:--------|:-----|----:|:------|:---------|:-------|
| Qwen3.5-27B Claude Opus Distilled (qx64-hi) | Dense 27B | 19 GB | Hybrid qx64-hi MLX | Reasoning / chain-of-thought | [link](per-model/model-summary-qwen-3-5.md#qwen35-27b-claude-opus-distilled-qx64-hi) |
| Qwen3.5-122B-A10B 4-bit | MoE 122B/10B + VL | 65 GB | Uniform 4-bit MLX | Agentic reasoning, multimodal | [link](per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-4-bit) |
| Qwen3.5-122B-A10B JANG 2S | MoE 122B/10B + SSM | 35 GB | JANG mixed 2-bit avg | Compact 122B (200K+ context) | [link](per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-jang-2s) |
| Qwen3.5-35B-A3B JANG 4K | MoE 35B/3B | 19 GB | JANG mixed 4-bit avg | Fast small MoE on oMLX (JANG fork) | [link](per-model/model-summary-qwen-3-5.md#qwen35-35b-a3b-jang-4-bit-mixed-precision) |

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

## Nemotron Family (vllm-mlx only)

Three Nemotron variants plus the cross-cutting server-compatibility note. Per-variant detail and the **vllm-mlx-only** explainer (chat template not packaged in MLX weights) live in the dedicated per-model file: **[`per-model/model-summary-nemotron.md`](per-model/model-summary-nemotron.md)**.

| Variant | Type | Size | Quant | Best For | Detail |
|:--------|:-----|----:|:------|:---------|:-------|
| Nemotron 3 Nano 30B-A3B 8-bit | MoE 32B/3B | 33.6 GB | 8-bit MLX | NVIDIA MoE · multilingual | [link](per-model/model-summary-nemotron.md#nemotron-3-nano-30b-a3b-8-bit) |
| Nemotron 3 Super 120B-A12B 4.5-bit | Mamba-2 + MoE 120B/12B | 66.5 GB | 4.5-bit MLX | Large-scale reasoning | [link](per-model/model-summary-nemotron.md#nemotron-3-super-120b-a12b-45-bit) |
| Nemotron Cascade 2 30B-A3B nvfp4 | Mamba-2 + MoE 30B/3B | 17 GB | nvfp4 MLX | Triple-hybrid efficiency | [link](per-model/model-summary-nemotron.md#nemotron-cascade-2-30b-a3b-nvfp4) |

**vllm-mlx is the only correctly-functioning host** — `mlx-openai-server` and `oMLX` lack the chat-template fallback and Nemotron-specific parsers. Full reasoning, server matrix, and recommended launch command in [`per-model/model-summary-nemotron.md` § Nemotron Server Compatibility](per-model/model-summary-nemotron.md#nemotron-server-compatibility).

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

## Qwen3.6 Family (Hybrid Gated DeltaNet + Vision)

Five Qwen3.6 variants currently catalogued in this stack — all sharing the **hybrid Gated DeltaNet (linear-attention) + full Gated Attention** architecture plus a 27-layer ViT vision tower. Per-variant deployment details, server configs, benchmarks, and caveats live in the dedicated per-model file: **[`per-model/model-summary-qwen-3-6.md`](per-model/model-summary-qwen-3-6.md)**.

| Variant | Type | Size | Quant | Primary server here | Detail |
|:--------|:-----|----:|:------|:--------------------|:-------|
| Qwen3.6-35B-A3B 6-bit | MoE 35B/3B + VL | 27 GB | Uniform 6-bit MLX | mlx-openai-server | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-6-bit) |
| Qwen3.6-35B-A3B 4-bit | MoE 35B/3B + VL | 22 GB target + 1 GB drafter | 4-bit MLX + DFlash drafter | dflash-mlx (provisional) | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-4-bit) |
| Qwen3.6-27B JANG 4M | Dense 27B + VL | 17.5 GB | JANG mixed 4/8-bit | vllm-mlx (text-only) | [link](per-model/model-summary-qwen-3-6.md#qwen36-27b-jang-4m-dense--vl) |
| Qwen3.6-27B 6-bit standard MLX | Dense 27B + VL | 22 GB | Uniform 6-bit MLX | llmster | [link](per-model/model-summary-qwen-3-6.md#qwen36-27b-6-bit-standard-mlx) |
| Qwen3.6-35B Rust LoRA (jedisct1) | MoE 35B/3B (LoRA-merged) | 35 GB | Uniform 8-bit MLX | vllm-mlx | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-rust-lora-jedisct1-8-bit) |

The JANGTQ-CRACK Qwen3.6 variants (`dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` and `JANGTQ2-CRACK`) live in the private uncen-model submodule — see [`uncen-model/`](uncen-model/) and the JANGTQ deployment notes further down.

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
| Tokens/sec | 64.5 @ 512 → 64.4 @ 8K → 57.3 @ 64K (vllm-mlx, [bench](benchmarks/model-benchmark-api-server.md#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid)) |
| On-disk size | ~80 GB |
| Context Size | 131,072 native; **64K practical ceiling on M3 Ultra** — 128K OOMs |
| Reasoning | None — does not emit `<think>` blocks |
| Vision | No — text-only |
| License | MIT (base) |

**vllm-mlx model ID:** `mlx-community/Ling-2.6-flash-mlx-6bit`

**Server config (vllm-mlx):** `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits Hermes-format `<tool_call>{json}</tool_call>` blocks — `qwen3_coder` won't parse these). No `--reasoning-parser`.

**Requires three local patches** before the model will load:
1. Vendor `mlx_lm/models/bailing_hybrid.py` from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227)
2. [`scripts/patches/patch_mlx_lm_threadlocal_stream.py`](../../scripts/patches/patch_mlx_lm_threadlocal_stream.py) — per-thread lazy `generation_stream` accessor
3. [`scripts/patches/patch_vllm_mlx_inline_gen.py`](../../scripts/patches/patch_vllm_mlx_inline_gen.py) — replace `await asyncio.to_thread(...)` with inline sync calls in `vllm_mlx/engine/simple.py`

mlx-openai-server is **incompatible** — its inference-worker thread design is more deeply thread-coupled than vllm-mlx and patch #3 doesn't apply directly.

**Tool calling** ([`benchmarks/model-benchmark-agent-tool-call.md`](benchmarks/model-benchmark-agent-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit)):
- API-level: 5/5 single-call pass · 3-turn agentic loop **4.74 s** 🏆 (fastest in this stack)
- OpenCode end-to-end (2026-04-30): browse 25.75 s · search 29.64 s — third-fastest, behind only the two A3B-sparse Qwen3.6 variants

**See also:** [`docs/models/per-model/model-summary-ling.md`](per-model/model-summary-ling.md) for the full deployment guide (vendoring PR #1227, patch scripts, sampling config, RAM/VRAM profile).

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

**See also:** [`docs/models/per-model/model-summary-mimo-v2.5.md`](per-model/model-summary-mimo-v2.5.md) for the TL;DR (Findings / Limitations / Blocker), full three-config benchmark comparison, and deployment instructions.

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

**Reference YAML:** [mlx-openai-server-gemma4.yaml](../servers/mlx-openai-server/mlx-openai-server-gemma4.yaml)

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
