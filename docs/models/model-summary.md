# Model Summary

Detailed specs, benchmarks, and caveats for the main model set used across the Mac Studio servers. For the quick-reference table, see [README.md](../../README.md).

*Sources: HuggingFace model cards, dev.to, Medium, Reddit, community benchmarks.*

## Index
- [Adding a Model to oMLX](#adding-a-model-to-omlx)
- [IBM Granite 4.1 Family](#ibm-granite-41-family) — 1 variant: **30B Q8_0 GGUF (unsloth, Apache 2.0, 24.8 tok/s, browse 6.24 s — active lm-studio main 2026-05-05)**. Detail at [`per-model/model-summary-granite-4.1.md`](per-model/model-summary-granite-4.1.md)
- [Gemma 4 Family](#gemma-4-family) — 8 variants: 26B-A4B (4-bit, MoE multimodal), 31B-it (6-bit, dense text-only), 31B-it 6-bit + MTP drafter (mlx-vlm — **streaming bug fully fixed 2026-05-20 on main `45e6ece`** via PRs #1166/#1182/#1188; browse 91.47 s / search 189.85 s — still 5–7× behind mlx-lm 6-bit because prefill ~100× slower), DavidAU Heretic 31B Q6_k GGUF (uncensored, 7/10 mlabonne), TrevorJS Uncensored 26B-A4B Q8_0 GGUF (EGA abliteration, 8/10 mlabonne, 87.6 tok/s, browse 2.93 s 🥈, search 7.35 s 🥇), TrevorJS Uncensored 31B-it Q4_K_M GGUF (dense, abliteration, harness 7/10 / manual 10/10 mlabonne, browse 10.08 s), **Huihui Gemma 4 26B A4B Abliterated i1-Q6_K (huihui-ai abliteration + mradermacher imatrix, 9/10 mlabonne, browse 2.55 s 🥇 all-time leader — active lm-studio main 2026-05-15)**, and **Gemma 4 E4B (LiteRT-LM edge runtime, ~4B, 13.85 tok/s decode, CPU/XNNPACK, evaluation-only)**. Detail at [`per-model/model-summary-gemma.md`](per-model/model-summary-gemma.md)
- [Qwen3-Coder Family (MLX 6-bit + 4-bit)](#qwen3-coder-family-mlx-6-bit--4-bit) — 2 variants: Coder-Next 6-bit (daily driver), Coder-30B-A3B 4-bit. Detail at [`per-model/model-summary-qwen-3-coder.md`](per-model/model-summary-qwen-3-coder.md)
- [Qwen3.5 Family (MoE + dense distilled + JANG)](#qwen35-family-moe--dense-distilled--jang) — 5 variants: 27B Opus Distilled, 122B-A10B 4-bit, 122B-A10B JANG 2S, 35B-A3B JANG 4K, Qwythos-9B Q8_0 (⚠ marketed-uncensored, behaves aligned). Detail at [`per-model/model-summary-qwen-3-5.md`](per-model/model-summary-qwen-3-5.md)
- [OmniCoder-9B (8-bit)](#omnicoder-9b-8-bit) — Coding agent (agentic trajectories)
- [Nemotron Family (vllm-mlx only)](#nemotron-family-vllm-mlx-only) — 3 variants + server compatibility note: Nano 30B, Super 120B, Cascade-2 30B. Detail at [`per-model/model-summary-nemotron.md`](per-model/model-summary-nemotron.md)
- [Mistral Small 4 119B-A6B JANG 2L](#mistral-small-4-119b-a6b-jang-2l) — 119B MoE · 6B active · 30 GB · 82 tok/s · vision
- [Qwen3.6 Family (Hybrid Gated DeltaNet + Vision)](#qwen36-family-hybrid-gated-deltanet--vision) — 14 variants: 35B-A3B 6-bit / 4-bit / Ollama 35B MLX / Osaurus JANGTQ4 / DavidAU Heretic 40B Q6_K IMatrix GGUF (prior main), prithivMLmods 35B-A3B Aggressive Q6_K GGUF (prior main), HauhauCS Aggressive Q6_K_P (prior main), 27B JANG 4M, 27B 6-bit, HauhauCS Balanced Q8_K_P GGUF, **prithivMLmods Q3.6-27B GLM-5.1-DA Q4_K_M (prior lm-studio main, 2026-05-14 → 2026-05-15 — browse 11.62 s / search 19.47 s)**, 35B Rust LoRA, **Huihui Qwen3.6-35B-A3B Claude-4.7-Opus abliterated MTP Q6_K (first MoE+MTP in lab — browse 3.40 s / search 12.01 s, 10/10 mlabonne, 83% MTP acceptance, 94.4 tok/s on mainline llama.cpp, re-bench 2026-06-11)**, **llmfan46 Qwen3.6-27B uncensored Heretic v2 Native-MTP-Preserved Q6_K (first Heretic-abliterated + MTP — dense 27B, browse 38.99 s / search 40.42 s, 10/10 mlabonne, ~74% MTP acceptance, 24.6 tok/s, 2026-05-21)**. Full per-variant detail at [`per-model/model-summary-qwen-3-6.md`](per-model/model-summary-qwen-3-6.md)
- [Ling-2.6-flash mlx-6bit (bailing_hybrid)](#ling-26-flash-mlx-6bit-bailing_hybrid) — 104B/7.4B MoE · 6-bit MLX · MLA + linear-attention SSM · vllm-mlx + 3 patches
- [MiMo V2.5 4-bit, 130-expert pruned (jedisct1)](#mimo-v25-4-bit-130-expert-pruned-jedisct1) — 4-bit MLX · pruning calibration loss → not viable for agent workloads
- [ChindaMT-4B (Thai ↔ English Translation)](#chindamt-4b-thai--english-translation) — **active mlx-lm sidecar on port 8080**, 186 tok/s, 2.2 GB MLX 4-bit, Apache-2.0. Qwen3.5-4B base + hybrid SSM architecture; GGUF not viable.
- [Qwen3-ASR Family](#qwen3-asr-family) — 2 variants + forced aligner: **1.7B (active speech-to-text sidecar, MPS, 19.06× RTF on 15 s English clip)**, 0.6B, ForcedAligner-0.6B. Detail at [`per-model/model-summary-qwen3-asr.md`](per-model/model-summary-qwen3-asr.md)
- [Z-Image / Z-Anime Family (Image Generation)](#z-image--z-anime-family-image-generation) — 2 variants on disk: **Z-Anime Distill-4-step AIO BF16 (active, 17.75 s @ 1024² M3 Ultra MPS)**, Z-Anime Base AIO BF16 (best-quality reference, 235.16 s @ 28 steps). S3-DiT 6B, Apache-2.0, ComfyUI on port 8188 (web UI only). [bench](benchmarks/z-anime/wall-time-comfyui.md)
- [DeepSeek-V4-Flash (284B/13B-active MoE, ds4)](#deepseek-v4-flash-284b13b-active-moe-ds4) — 1 viable variant: **IQ2XXS-imatrix 81 GB GGUF on the `antirez/ds4` native Metal engine, port 8101 (only Apple-Silicon path for `deepseek4`; 5/5 smoke, browse 18.78 s / search 28.22 s)**. Detail at [`per-model/model-summary-deepseek-v4.md`](per-model/model-summary-deepseek-v4.md)
- [LFM2.5 Family (LiquidAI `lfm2moe` hybrid MoE)](#lfm25-family-liquidai-lfm2moe-hybrid-moe) — 1 variant: **LFM2.5-8B-A1B Q8_0 (8.3B/1.5B-active MoE, 190 tok/s, browse 11.1 s / search 19.72 s — `llama-cpp-mainline --jinja` only; lm-studio tool calls broken; canonical GGUF needs chat-template patch)**. Detail at [`per-model/model-summary-lfm2.md`](per-model/model-summary-lfm2.md)
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

Five Qwen3.5 variants catalogued here. Per-variant detail (specs, server config, caveats, JANG fork notes) lives in the dedicated per-model file: **[`per-model/model-summary-qwen-3-5.md`](per-model/model-summary-qwen-3-5.md)**.

| Variant | Type | Size | Quant | Best For | Detail |
|:--------|:-----|----:|:------|:---------|:-------|
| Qwen3.5-27B Claude Opus Distilled (qx64-hi) | Dense 27B | 19 GB | Hybrid qx64-hi MLX | Reasoning / chain-of-thought | [link](per-model/model-summary-qwen-3-5.md#qwen35-27b-claude-opus-distilled-qx64-hi) |
| Qwen3.5-122B-A10B 4-bit | MoE 122B/10B + VL | 65 GB | Uniform 4-bit MLX | Agentic reasoning, multimodal | [link](per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-4-bit) |
| Qwen3.5-122B-A10B JANG 2S | MoE 122B/10B + SSM | 35 GB | JANG mixed 2-bit avg | Compact 122B (200K+ context) | [link](per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-jang-2s) |
| Qwen3.5-35B-A3B JANG 4K | MoE 35B/3B | 19 GB | JANG mixed 4-bit avg | Fast small MoE on oMLX (JANG fork) | [link](per-model/model-summary-qwen-3-5.md#qwen35-35b-a3b-jang-4-bit-mixed-precision) |
| Qwythos-9B Claude-Mythos-5-1M Q8_0 ⚠ | Dense 9B + VL | 8.87 GiB | Q8_0 GGUF (lm-studio) | ⚠ marketed uncensored, behaves aligned (1/10 mlabonne) — negative result | [link](per-model/model-summary-qwen-3-5.md#qwythos-9b-claude-mythos-5-1m-q8_0) |

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

Fourteen Qwen3.6 variants currently catalogued in this stack — all sharing the **hybrid Gated DeltaNet (linear-attention) + full Gated Attention** architecture plus a 27-layer ViT vision tower. Per-variant deployment details, server configs, benchmarks, and caveats live in the dedicated per-model file: **[`per-model/model-summary-qwen-3-6.md`](per-model/model-summary-qwen-3-6.md)**.

| Variant | Type | Size | Quant | Primary server here | Detail |
|:--------|:-----|----:|:------|:--------------------|:-------|
| Qwen3.6-35B-A3B 6-bit | MoE 35B/3B + VL | 27 GB | Uniform 6-bit MLX | mlx-openai-server / lm-studio (MLX-vs-GGUF data point, 2026-05-08) | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-6-bit) |
| Qwen3.6-35B-A3B 4-bit | MoE 35B/3B + VL | 22 GB target + 1 GB drafter | 4-bit MLX + DFlash drafter | dflash-mlx (provisional) | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-4-bit) |
| Qwen3.6-35B-A3B MLX via Ollama | MoE 35B/3B | 21 GB | Ollama MLX (`qwen3.6:35b-mlx`) | ollama port 11434 | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-mlx-via-ollama) — 5/5 API smoke, 5.96 s API loop, OpenCode browse 9.75 s / search 18.4 s |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | MoE 35B/3B + VL | 19.7 GB | JANGTQ4 / `mxtq` | vmlx (stopped 2026-05-02 reference) | [link](per-model/model-summary-qwen-3-6.md#osaurus-qwen36-35b-a3b-jangtq4) |
| Qwen3.6-27B JANG 4M | Dense 27B + VL | 17.5 GB | JANG mixed 4/8-bit | vllm-mlx (text-only) | [link](per-model/model-summary-qwen-3-6.md#qwen36-27b-jang-4m-dense--vl) |
| Qwen3.6-27B 6-bit standard MLX | Dense 27B + VL | 22 GB | Uniform 6-bit MLX | lm-studio | [link](per-model/model-summary-qwen-3-6.md#qwen36-27b-6-bit-standard-mlx) |
| unsloth Qwen3.6-27B-MTP UD-Q6_K_XL | Dense 27B + MTP heads (vision broken under MTP) | 26 GB | GGUF Unsloth Dynamic 2.0 6-bit + MTP draft heads | **llama-cpp-mtp (prior main 2026-05-15, port 8100 — stopped same day; sidecar for MTP experiments)** — only Apple-Silicon MTP path today | [technique](techniques/model-technique-qwen-3-6-mtp.md) · [runbook](../servers/llama-cpp-mtp/summary.md) — 84–89 % MTP draft acceptance, decode 22.9 → 20.0 tok/s @ 414 → 29 128 input tokens, smoke 5/5 + multi 21.92 s, OpenCode browse 35.98 s / search 35.24 s |
| Jackrong Qwopus3.6-27B v2 MTP Q6_K | Dense 27B + MTP heads (vision broken under MTP) | 22.4 GB | GGUF Q6_K + MTP draft heads | llama-cpp-mainline port 8100 (sidecar for MTP experiments) — fastest dense-27B-MTP in agent loops | [per-model](per-model/model-summary-qwen-3-6.md#jackrong-qwopus36-27b-v2-mtp-q6k) — 25.7 → 20.1 tok/s decode @ 512 → 29K, smoke 5/5 + multi 21.02 s, OpenCode browse 16.96 s / search 27.62 s |
| HauhauCS Qwen3.6-27B Uncensored Balanced Q8_K_P | Dense 27B + VL | 32 GB | GGUF `Q8_K_P` | lm-studio (prior sidecar — superseded 2026-05-02) | [link](per-model/model-summary-qwen-3-6.md#hauhaucs-qwen36-27b-uncensored-balanced-q8_k_p) |
| prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M | Dense 27B + VL | 15.41 GB | GGUF `Q4_K_M` | lm-studio (prior main 2026-05-14 → 2026-05-15; **speed-first fallback** — faster on agent loops than the current MTP main) | [link](per-model/model-summary-qwen-3-6.md#prithivmlmods-q36-27b-glm-51-da-q4_k_m) |
| HauhauCS Qwen3.6-35B-A3B Uncensored Aggressive Q6_K_P | MoE 35B/3B + VL | 31 GB | GGUF `Q6_K_P` | lm-studio (prior main — superseded 2026-05-02 by prithivMLmods) | [link](per-model/model-summary-qwen-3-6.md#hauhaucs-qwen36-35b-a3b-uncensored-aggressive-q6_k_p) |
| prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K | MoE 35B/3B + VL | 28.51 GB | GGUF `Q6_K` | lm-studio (prior main — superseded 2026-05-03 by DavidAU 40B) | [link](per-model/model-summary-qwen-3-6.md#prithivmlmods-qwen36-35b-a3b-uncensored-aggressive-q6_k) |
| DavidAU Qwen3.6-40B Heretic Q6_K IMatrix | Dense 40B | 30.17 GiB | GGUF `Q6_K` IMatrix | lm-studio (prior main — superseded by lm-studio Gemma 4 26B-A4B Q8_0, then by TrevorJS Gemma 4 31B-it Q4_K_M 2026-05-10) | [link](per-model/model-summary-qwen-3-6.md#davidau-qwen36-40b-heretic-uncensored-thinking-q6_k-imatrix) |
| Qwen3.6-35B Rust LoRA (jedisct1) | MoE 35B/3B (LoRA-merged) | 35 GB | Uniform 8-bit MLX | vllm-mlx | [link](per-model/model-summary-qwen-3-6.md#qwen36-35b-rust-lora-jedisct1-8-bit) |

The JANGTQ-CRACK Qwen3.6 variants (`dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` and `JANGTQ2-CRACK`) live in the private uncen-model submodule — see [`uncen-model/`](uncen-model/) and the JANGTQ deployment notes further down.

---

## Ling-2.6-flash mlx-6bit (`bailing_hybrid`)

InclusionAI's `bailing_hybrid` MoE — **104 B total / 7.4 B active** — sparse-expert hybrid mixing 4 MLA layers (absorbed-form Multi-head Latent Attention) with 28 Lightning-style linear-attention recurrence layers. 256 routed experts (8/tok, group-limited top-8) + 1 shared, sigmoid `noaux_tc` routing. 6-bit MLX uniform quant, ~80 GB on disk. Text-only, no `<think>` reasoning emitted.

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

**Tool calling** ([`benchmarks/model-benchmark-tool-call.md`](benchmarks/model-benchmark-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit)):
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

## IBM Granite 4.1 Family

IBM Granite 4.1 30B Instruct — dense decoder-only model, Apache 2.0 license. One variant currently deployed: **Q8_0 GGUF** from Unsloth (28.57 GiB resident, 65K context, lm-studio). Loaded as the lm-studio main 2026-05-05; superseded by Gemma 4 26B-A4B Q8_0 and then by TrevorJS Gemma 4 31B-it Q4_K_M (current main, 2026-05-10) — kept as the Apache-2.0 fallback in `lms ls`. Full deployment recipe, smoke/perf/agent benchmarks, and caveats at **[`per-model/model-summary-granite-4.1.md`](per-model/model-summary-granite-4.1.md)**.

| Variant | Type | Size | Quant | Primary server here | Detail |
|:--------|:-----|----:|:------|:--------------------|:-------|
| Granite 4.1 30B Q8_0 (unsloth GGUF) | Dense 30B, no MoE | 29 GB | Q8_0 GGUF | lm-studio (Apache-2.0 fallback; prior main 2026-05-05) | [link](per-model/model-summary-granite-4.1.md) |

---

## ChindaMT-4B (Thai ↔ English Translation)

**`iapp/ChindaMT-4B`** — Thai-English machine translation fine-tune of Qwen3.5-4B by iApp Technology (Apache-2.0, gated HF repo). **Active sidecar on mlx-lm port 8080.** Deployed 2026-05-15.

| Field | Value |
|:--|:--|
| Base model | Qwen/Qwen3.5-4B |
| Architecture | `Qwen3_5ForConditionalGeneration` — hybrid: 24/32 layers are Mamba-style SSM (linear attention), 8/32 are full attention. Vision encoder present but not loaded. |
| Task | Thai ↔ English machine translation (NOT a general-purpose model) |
| Format on disk | MLX 4-bit quantized (2.2 GB) at `~/mlx-models/chindamt-4b-4bit/` |
| Context | 262,144 tokens max |
| License | Apache-2.0 |
| HF | [`iapp/ChindaMT-4B`](https://huggingface.co/iapp/ChindaMT-4B) (gated) |
| Server | `mlx-lm` 0.31.3 (Cellar libexec binary), port 8080, OpenAI API |
| Decode | **186 tok/s** @ 2.5 GB peak memory (M3 Ultra, 4-bit) |
| Prefill | 33 tok/s |
| Memory | 2.5 GB peak — coexists with any main model on the 96 GB M3 Ultra |

**Model ID:** `mlx_lm.server` uses the exact string passed to `--model` as the model ID — always send the full absolute path in API requests and client configs. Short aliases (e.g. `chindamt-4b`) trigger a HuggingFace 404 as the server tries to resolve them remotely.

**Chat template quirk:** The Qwen3.5 template defaults to thinking mode, placing output in `message.reasoning` instead of `message.content`. Disable it server-wide at launch with `--chat-template-args '{"enable_thinking":false}'` (preferred). Per-request fallback: include `"chat_template_kwargs": {"enable_thinking": false}` in the JSON body.

```bash
# curl (with per-request kwarg as fallback)
curl -s http://<MAC_STUDIO_IP>:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/Users/chanunc/mlx-models/chindamt-4b-4bit",
    "messages": [{"role": "user", "content": "Translate to English: สวัสดีครับ วันนี้อากาศดีมาก"}],
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": false}
  }' | python3 -m json.tool
# content: "Hello! The weather is very nice today."

# openai-cli (thinking disabled at server level — no extra flag needed)
# Pipe through jq -r to decode \uXXXX escapes — the Go CLI ASCII-encodes Thai by default.
OPENAI_API_KEY=not-needed \
OPENAI_BASE_URL=http://<MAC_STUDIO_IP>:8080/v1 \
openai chat:completions create \
  --model "/Users/chanunc/mlx-models/chindamt-4b-4bit" \
  --message '{"role": "user", "content": "Translate to English: สวัสดีครับ วันนี้อากาศดีมาก"}' \
  --max-tokens 200 | jq -r '.choices[0].message.content'
# Hello! The weather is very nice today.
```

**Conversion notes (for re-deploy):**
- No GGUF path: llama.cpp has no runtime support for SSM/linear-attention (turboquant converter handles the format but the runtime CPU-spins without output)
- MLX conversion requires stripping the tied `lm_head.weight` first — bug in mlx-lm 0.31.3's `qwen3_5` outer `sanitize()` method (`language_model.lm_head.weight` is not popped before passing to the inner sanitize). Fixed-HF source with weight stripped at `~/mlx-models/chindamt-4b-fixed-hf/` (8.5 GB, keep for re-convert)
- Rebuild: `mlx_lm.convert --hf-path ~/mlx-models/chindamt-4b-fixed-hf --mlx-path ~/mlx-models/chindamt-4b-4bit -q --q-bits 4`

Launch:

```bash
ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/mlx-models/chindamt-4b-4bit \
  --host 0.0.0.0 --port 8080 \
  --chat-template-args '{\"enable_thinking\":false}' \
  > /tmp/chindamt.log 2>&1 &"
```

Stop:

```bash
ssh macstudio "pkill -f 'mlx_lm.server.*chindamt'"
```

---

## Qwen3-ASR Family

Apache-2.0 speech-to-text family released **2026-01-30**. Two checkpoints + a forced aligner; **`Qwen/Qwen3-ASR-1.7B`** is the active variant on this lab. ASR is a separate axis from the chat/agent stack — runs out of `~/qwen-asr-env/` on the transformers + MPS path, no port-bound daemon. Full deployment + benchmark detail at **[`per-model/model-summary-qwen3-asr.md`](per-model/model-summary-qwen3-asr.md)**.

| Variant | Type | Disk (bf16) | Quant | Server here | Detail |
|:--|:--|:--|:--|:--|:--|
| **`Qwen/Qwen3-ASR-1.7B`** | Speech→text, 30 langs + 22 Chinese dialects | 4.7 GB | bf16 (no quant — see analysis) | `~/qwen-asr-env/` (transformers + MPS) | [link](per-model/model-summary-qwen3-asr.md) |
| `Qwen/Qwen3-ASR-0.6B` | Speech→text, throughput-leader | 1.2 GB | bf16 | not deployed | [link](per-model/model-summary-qwen3-asr.md#family-overview) |
| `Qwen/Qwen3-ForcedAligner-0.6B` | Word/char timestamp companion (≤ 5 min) | ~1.2 GB | bf16 | not deployed | [link](per-model/model-summary-qwen3-asr.md#family-overview) |

Performance on M3 Ultra MPS (1.7B, 15.05 s English clip, 3 warm passes): **avg 0.790 s wall, RTF 19.06×**, peak Python RSS 1.1 GB, model load 3.2 s warm / 42 s cold. ~13 % of Qwen's published H100 RTFx of 147.93 — but a 1-hour clip still transcribes in ~3 min. Streaming + `qwen-asr-serve` daemon are CUDA-only, so on Apple Silicon the interface is the in-process Python API (`Qwen3ASRModel.transcribe(audio=…)`) — see [`docs/servers/qwen-asr/summary.md`](../servers/qwen-asr/summary.md) for the runbook.

**Quantization decision: stay bf16.** The 1.7B model is only 4.7 GB and ASR is quality-sensitive (a wrong logit becomes a transcript word error that compounds into WER). Community 4-bit/8-bit uploads on HF have no published WER baselines.

---

## Z-Image / Z-Anime Family (Image Generation)

Apache-2.0 image-generation family. Tongyi-MAI **Z-Image** is Alibaba's S3-DiT (Single-Stream Diffusion Transformer, 6B params; [arXiv:2511.22699](https://arxiv.org/abs/2511.22699)) with a unified text + visual + image-VAE token stream. **`SeeSee21/Z-Anime`** is a full fine-tune (not a LoRA merge) for anime aesthetics; ships BF16 / FP8 safetensors, GGUF Q8_0 / Q4_K_S, diffusers folder, and AIO single-files (UNet + qwen_3_4b text encoder + ae VAE bundled).

Active deploy: ComfyUI 0.20.1 on port **8188**, web UI only — no OpenAI `/v1/images/generations` shim, no `configs/clients/comfyui/`. Two AIO BF16 variants on disk for the "fast iteration vs best quality" pair. Full runbook: [`docs/servers/comfyui/summary.md`](../servers/comfyui/summary.md).

| Variant | Type | Disk (BF16 AIO) | Steps · CFG | Wall time @ 1024² (MPS) | Use |
|:--|:--|:--|:--|--:|:--|
| **`SeeSee21/Z-Anime` Distill-4-step AIO BF16** | S3-DiT 6B, sampler-distilled | 19 GiB | 4 · 1.0 | **17.75 s** (σ 0.03 s) | Fast iteration / interactive |
| **`SeeSee21/Z-Anime` Base AIO BF16** | S3-DiT 6B, full sampler | 19 GiB | 28 · 4.0 | **235.16 s** (σ 0.08 s) | Best-quality reference |
| `Tongyi-MAI/Z-Image-Turbo` | Base architecture (not deployed here) | — | 4–8 · 1.0 | — | Reference architecture only |

Wall times measured 2026-05-08 on Mac Studio M3 Ultra, 1 warm-up + 3 timed runs each, sampler `euler` / scheduler `beta` / `ModelSamplingAuraFlow` shift 3.5. Per-step cost is **4.4 s/step at CFG 1.0** and **8.4 s/step at CFG 4.0** — the 1.91× ratio matches CFG > 1's doubled forward pass exactly. Raw JSON: [`benchmarks/z-anime/wall-time-comfyui.json`](benchmarks/z-anime/wall-time-comfyui.json). Full benchmark write-up: [`benchmarks/z-anime/wall-time-comfyui.md`](benchmarks/z-anime/wall-time-comfyui.md).

**Why ComfyUI over MLX or DrawThings:**
- ComfyUI 0.20.x has first-party Z-Image-Turbo support (Nov 2025), loads AIO files via `CheckpointLoaderSimple` + the Z-Image-specific `ModelSamplingAuraFlow` node — no custom-node patching required for the canonical workflow.
- [`uqer1244/MLX_z-image`](https://github.com/uqer1244/MLX_z-image) is a 4-bit MLX port of Tongyi's *base* Z-Image only — no Z-Anime weights have been MLX-ported yet. Native MLX would likely beat MPS by 2–3× on M3 Ultra but porting the SeeSee21 fine-tune is a separate research thread.
- DrawThings on Mac doesn't yet support Z-Image / S3-DiT or the qwen_3_4b text encoder — skip.
- Alternative ([`OrdinarySF/z-image-inference`](https://github.com/OrdinarySF/z-image-inference) — Gradio + FastAPI MPS) is kept in reserve if ComfyUI stalls; same MPS path, no advantage on M3 Ultra unless the user wants a server endpoint that ComfyUI doesn't expose.

**Quantization decision: stay BF16 AIO.** The model is only 6B; FP8 (10.51 GiB AIO) saves ~9 GiB at noticeable quality cost on a 96 GB box. GGUF Q8_0 (7.22 GiB) and Q4_K_S (4.51 GiB) variants ship in the repo but require the `ComfyUI-GGUF` custom-node pack (`UnetLoaderGGUF` + `CLIPLoaderGGUF`) which isn't installed — they're useful on 12–16 GB consumer boxes, not here.

**Doesn't compete with the chat servers for any port.** Port 8188 is collision-free against 8000 / 1234 / 8098 / 8099. ComfyUI can run alongside any port-8000 LLM with no orchestration changes.

---

## DeepSeek-V4-Flash (284B/13B-active MoE, ds4)

**`deepseek-ai/DeepSeek-V4-Flash`** (MIT, released 2026-04-24) — 284 B-total / 13 B-active 256-expert MoE, 1 M context, reasoning model (`non-think` / `think-high` / `think-max`). Novel `deepseek4` architecture (Hybrid Compressed-Sparse + Heavily-Compressed Attention, Manifold-Constrained Hyper-Connections) — **not in upstream `llama.cpp`**; vLLM/SGLang loaders are CUDA-only. Served via the [`antirez/ds4`](https://github.com/antirez/ds4) standalone native Metal engine on sidecar port 8101 — the only Apple-Silicon path. Full per-variant detail + quant/server landscape at [`per-model/model-summary-deepseek-v4.md`](per-model/model-summary-deepseek-v4.md).

| Field | Value |
|:--|:--|
| Base model | `deepseek-ai/DeepSeek-V4-Flash` |
| Architecture | `deepseek4` — 256-expert MoE, 13 B active/token, Hybrid Attention (CSA + HCA) + mHC |
| Quant | `antirez/deepseek-v4-gguf` IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-**imatrix** (2-bit routed experts, Q8 attn/shared/out) |
| Format on disk | 81 GB GGUF at `~/ds4/gguf/` (symlinked `~/ds4/ds4flash.gguf`) |
| Parameters / Density | 284 B total / 13 B active (256 experts) |
| Context | 65 536 launched (model max 1 M; Think Max needs ≥ 384 K) |
| License | MIT |
| Server | `ds4` (DwarfStar 4) native C+Metal engine, port 8101, OpenAI + Anthropic + Responses APIs |
| Decode | **34.6 tok/s @ 512**, ~25–27 tok/s @ 4–32 K |
| Prefill | 4,512 tok/s @ 512; 513–864 cold @ 8–32 K; 4,851 warm @ 32 K (disk KV) |
| Memory | 81 GB weights + 1.3 GB ctx buffers @ 65 K (fits 96 GB-class with disk-KV offload) |
| Smoke | ✅ 5/5 single-call · multi-turn 3 turns / 8.95 s |
| Agent (opencode) | browse 18.78 s · search 28.22 s median wall (2–3 turns, `webfetch`) |
| API model id | `deepseek-v4-flash` |

**Quant/engine lock-in:** `ds4` only loads `antirez/deepseek-v4-gguf` files. persadian IQ1_S-XL (61.5 GB, smallest) is CUDA-only via `arishma108/llama.cpp feat/v4-port-cuda` — no Metal. batiai Q3–Q8 (135–302 GB) need unmerged upstream `deepseek4` and exceed RAM. Only `q2-imatrix` fits a 96 GB-class machine.

Launch / stop:

```bash
ssh macstudio "cd ~/ds4 && nohup ./ds4-server --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt > /tmp/ds4-server.log 2>&1 &"
ssh macstudio "pkill -f 'ds4-server'"
```

Full runbook (build, download, tool-call internals, known limitations): [`docs/servers/ds4/summary.md`](../servers/ds4/summary.md).

---

## Gemma 4 Family

Six Google Gemma 4 variants currently catalogued in this stack — the **26B-A4B** mixture-of-experts multimodal release (vision + audio + video, 256K context), the dense **31B-it** instruction-tuned text-only release (64K context, thinking mode ON), the **DavidAU HERETIC 31B** uncensored fine-tune (Q6_k GGUF, lm-studio), the **TrevorJS EGA 26B-A4B** uncensored MoE (Q8_0 GGUF, browse leader 2.93 s 🥇), and the **TrevorJS abliterated 31B-it** uncensored dense (Q4_K_M GGUF, manual 10/10 compliance, current lm-studio main 2026-05-10). Per-variant deployment details, server configs, benchmarks, and caveats for the censored variants live in the dedicated per-model file: **[`per-model/model-summary-gemma.md`](per-model/model-summary-gemma.md)**. Uncensored benchmark data lives in the submodule: [`uncen-model/`](uncen-model/).

| Variant | Type | Size | Quant | Primary server here | Detail |
|:--------|:-----|----:|:------|:--------------------|:-------|
| Gemma 4 26B-A4B (4-bit) | MoE 26B/4B + vision + audio | 15 GB | 4-bit MLX (8-bit MoE proj layer 0) | mlx-openai-server / lm-studio (MLX-vs-GGUF data point, 2026-05-08) | [link](per-model/model-summary-gemma.md#gemma-4-26b-a4b-4-bit) |
| Gemma 4 31B-it (6-bit) | Dense 31B text-only | 29 GB | 6-bit MLX | mlx-lm server | [link](per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) |
| Gemma 4 31B-it 6-bit + MTP drafter (mlx-vlm) — *streaming bug fixed 2026-05-20 on main `45e6ece`; prefill still ~100× behind mlx-lm* | Dense 31B + MTP `gemma4_assistant` drafter | 24 GB + 839 MB | 6-bit MLX target + bf16 drafter | mlx-vlm main `45e6ece` (PRs #1166/#1182/#1188) | [link](per-model/model-summary-gemma.md#main-45e6ece-re-test-2026-05-20--streaming-bug-fully-fixed-but-prefill-still-57-behind-mlx-lm) |
| DavidAU Gemma 4 31B Heretic Q6_k | Dense 31B uncensored (HERETIC+MysteryFT), vision-capable, loaded text-only | 23.47 GiB | Q6_k GGUF | lm-studio | [bench](uncen-model/gemma4-31b-davidau-heretic-benchmark.md) |
| TrevorJS Gemma 4 26B-A4B Uncensored Q8_0 | MoE 26B/4B uncensored (EGA abliteration) | 25.02 GiB | Q8_0 GGUF | lm-studio | [bench](uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md) |
| **TrevorJS Gemma 4 31B-it Uncensored Q4_K_M** | Dense 31B uncensored (norm-preserving biprojected abliteration) | **17.40 GiB** | Q4_K_M GGUF | **lm-studio (current main 2026-05-10)** | [bench](uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md) |

---

## LFM2.5 Family (LiquidAI `lfm2moe` hybrid MoE)

LiquidAI's on-device hybrid MoE. The lab variant is **LFM2.5-8B-A1B Q8_0** — 8.3 B total / ~1.5 B active (`lfm2moe`, 32 × 959 M experts), reasoning-only, text-only, `lfm1.0` proprietary license. Fast for its footprint (**190 tok/s** decode, browse 11.1 s / search 19.72 s), but tool-calling support is runtime-dependent on this days-old architecture.

| Variant | Type | Size | Quant | Working server | Detail |
|:--|:--|--:|:--|:--|:--|
| LFM2.5-8B-A1B Q8_0 | MoE 8.3B/1.5B-active, text-only, reasoning-only | 9.01 GB | Q8_0 GGUF (template-patched) | `llama-cpp-mainline` `:8100` via `--jinja` | [link](per-model/model-summary-lfm2.md) |

**Headline gotcha:** the native tool format is Pythonic (`<|tool_call_start|>[func(arg="...")]<|tool_call_end|>`). **lm-studio cannot parse it** — it injects its own `[TOOL_REQUEST]` format, which the reasoning-only model buries in its `<think>` block → smoke 0/5 ([lmstudio-js #458](https://github.com/lmstudio-ai/lmstudio-js/issues/458)). **llama.cpp `--jinja` works (5/5)** but only after the GGUF chat-template carries the `{# List of tools: [ #}` marker that routes llama.cpp to the LFM2 pythonic parser — the canonical GGUF lacks it and returns HTTP 500 ([ggml-org/llama.cpp #20245](https://github.com/ggml-org/llama.cpp/issues/20245)); the community fix [`nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2`](https://huggingface.co/nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2) adds exactly that one line. Full deployment recipe (transplant the marker template into Q8_0), benchmarks, and the recurrent-`invalid`-tool-call caveat in [`per-model/model-summary-lfm2.md`](per-model/model-summary-lfm2.md).

---

## JANGTQ-CRACK Deployment History (Apr 2026)

Historical narrative of the JANGTQ TurboQuant deployment work that landed alongside the Gemma 4 26B verification — kept here for context on the loader-discovery path and the resulting CRACK variant rankings. Empirical refusal-rate benchmarks for the CRACK variants live in the private [`uncen-model/`](uncen-model/) submodule; this section captures only the deployment story.

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
