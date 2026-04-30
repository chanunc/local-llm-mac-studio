# Model Conversion Guide: HuggingFace BF16 → MLX

How to convert a HuggingFace model to MLX safetensors format for use with oMLX on Mac Studio (M3 Ultra, 96GB).

---

## ✨ The Short Answer

**Don't convert — download instead.** Thousands of models are already converted on HuggingFace. Self-conversion is last resort for models with no pre-built MLX version.

**GGUF → MLX direct conversion does not work.** `mlx_lm.convert` does not accept GGUF files. The only working path is HuggingFace BF16 safetensors → MLX. See [Why GGUF → MLX Direct Fails](#why-gguf--mlx-direct-fails) for details.

---

## 🌳 Conversion Decision Tree

```
Need a model in oMLX?
│
├─ Search mlx-community first
│   https://huggingface.co/mlx-community
│   → Thousands of official MLX conversions
│
├─ Search nightmedia
│   https://huggingface.co/nightmedia
│   → Hybrid-precision variants (qx64-hi, qx86-hi) — better quality/size
│
├─ Search AITRADER
│   https://huggingface.co/AITRADER
│   → Abliterated/uncensored MLX variants
│
└─ No pre-built MLX exists?
    → Self-convert from HuggingFace BF16 source
       See: Step-by-Step Conversion below
```

**Rule of thumb for this setup:** If the model has a HuggingFace BF16 source and fits the RAM budget (≤35B dense, ≤70B MoE), you can convert it. For larger models, prefer pre-built.

---

## 🔎 Finding Pre-Converted Models

| Org | Specialty | URL |
|-----|-----------|-----|
| `mlx-community` | Official MLX conversions (4/6/8-bit affine) | https://huggingface.co/mlx-community |
| `nightmedia` | Hybrid-precision (`qx64-hi`, `qx86-hi`) — higher quality in attention layers | https://huggingface.co/nightmedia |
| `AITRADER` | Abliterated/uncensored 4-bit MLX | https://huggingface.co/AITRADER |
| `bartowski` | GGUF (not MLX — skip for oMLX) | — |

**Search tip:** On HuggingFace, search `<model-name> mlx` and filter by the org. Look for repos where files end in `.safetensors` and include a `config.json`.

---

## 🧩 mlx_lm.convert: Complete Reference

### Input Formats

| Input | Supported | Notes |
|-------|-----------|-------|
| HuggingFace safetensors (BF16/FP16) | ✅ Yes | Local directory or HF model ID |
| HuggingFace PyTorch `.bin` | ✅ Yes | Local directory |
| HuggingFace model ID (auto-download) | ✅ Yes | Downloads on first run |
| GGUF | ❌ No | Not supported — see Why GGUF → MLX Direct Fails |
| `.npz` numpy | ❌ No | Wrong format |

### Installation & Version Requirements

```bash
# Install mlx-lm on Mac Studio
/opt/homebrew/bin/pip3.11 install mlx-lm

# Upgrade (recommended before converting)
/opt/homebrew/bin/pip3.11 install --upgrade mlx-lm transformers
```

**Version requirements for Qwen3.5 models:**
- `mlx-lm ≥ 0.25.2`
- `transformers ≥ 4.52.4`

### Flag Reference

| Flag | Purpose | Default |
|------|---------|---------|
| `--hf-path` / `--model` | Source: local path or HF model ID | required |
| `--mlx-path` | Output directory | `mlx_model` |
| `-q` / `--quantize` | Enable quantization | off (BF16 output) |
| `--q-bits` | Bits per weight: 4, 6, 8 | 4 |
| `--q-group-size` | Weights sharing a scale factor | 64 |
| `--q-mode` | Quantization mode: `affine`, `mxfp4`, `mxfp8`, `nvfp4` | `affine` |
| `--quant-predicate` | Mixed-bit recipe: `mixed_2_6`, `mixed_3_4`, `mixed_3_6`, `mixed_4_6` | off |
| `--dtype` | Non-quantized dtype: `float16`, `bfloat16`, `float32` | `bfloat16` |
| `--upload-repo` | Push output to HF Hub after conversion | off |
| `-d` / `--dequantize` | Reverse: decompress quantized → BF16 | off |
| `--trust-remote-code` | Allow custom tokenizer code | off |

### Quantization Strategy Guide

**Standard quantization (affine mode — use for oMLX):**

| Bits | Size/param | Quality | When to use |
|------|-----------|---------|-------------|
| 4-bit | ~0.5 bytes | Good — slight perplexity increase | Default choice; fits most models in 96GB |
| 6-bit | ~0.75 bytes | Better — community sweet spot | Use when you have 25-30% more RAM headroom |
| 8-bit | ~1.0 bytes | Near-lossless | Max quality; large models may stress 96GB |

**Mixed-bit recipes (affine only):**

`--quant-predicate mixed_4_6` applies 6-bit to quality-critical layers (`v_proj`, `down_proj`, `lm_head` in early/late layers) and 4-bit to the rest. Better quality than pure 4-bit with modest size increase (~10%). Use when you'd choose 6-bit but want smaller output.

**Floating-point modes (hardware-dependent):**

| Mode | Group size | Notes |
|------|-----------|-------|
| `mxfp4` | 32 | Microscaling FP4 — **not reliably supported in oMLX** |
| `mxfp8` | 32 | Microscaling FP8 — **not confirmed in oMLX** |
| `nvfp4` | 32 | Preserves router gates at 8-bit — recommended for MoE models when supported |

**Recommendation for this setup:** Use `affine` mode (default). `mxfp8` is not confirmed in oMLX.

### Memory Requirements

Conversion loads the full BF16 source into memory plus the output. Rule: need ~2× the BF16 source size in RAM.

| Model type | BF16 source | RAM needed | Output (4-bit) | Fits on M3 Ultra (96GB)? |
|-----------|------------|-----------|----------------|--------------------------|
| 7B dense | ~14 GB | ~28 GB | ~4 GB | ✅ Yes |
| 27B dense | ~54 GB | ~70 GB | ~16 GB | ✅ Yes |
| 30B MoE (3B active) | ~64 GB | ~70 GB | ~18 GB | ✅ Yes (close — close all apps) |
| 35B MoE (3B active) | ~70 GB | ~80 GB | ~20 GB | ✅ Yes (close all apps) |
| 70B dense | ~140 GB | ~140 GB | ~35 GB | ❌ No — exceeds 96GB |
| 70B MoE | ~80 GB | ~90 GB | ~40 GB | ⚠️ Borderline — depends on active params |

**Before starting conversion:** Close all browser tabs and heavy apps on Mac Studio. Unified memory is shared.

### MoE-Specific Notes

- `mlx_lm.convert` handles Qwen MoE (3.5-35B-A3B, 122B-A10B) correctly from HF source
- MoE BF16 footprint is smaller than the total parameter count suggests (only router + expert weights matter)
- `--q-mode nvfp4` preserves router gate precision — recommended for MoE when `nvfp4` is supported
- Standard 4-bit or 6-bit affine works fine in practice for MoE inference

---

## ⚙️ Step-by-Step: Convert from HuggingFace BF16

This example converts `huihui-ai/Qwen3.5-35B-A3B-abliterated` to 4-bit MLX. Adapt the model IDs and paths for other models.

### Step 1: Check disk space

```bash
df -h ~
```

**Need:** BF16 source size + output size + 10 GB headroom. For a 35B MoE: ~90 GB free minimum.

### Step 2: Install/upgrade mlx-lm

```bash
/opt/homebrew/bin/pip3.11 install --upgrade mlx-lm transformers
```

### Step 3: Download HF BF16 source

Find the original HuggingFace model the GGUF was derived from. For the abliterated variant:

```bash
/opt/homebrew/bin/hf download \
  huihui-ai/Qwen3.5-35B-A3B-abliterated \
  --local-dir ~/tmp/source-hf
```

**What's happening:** Downloads the full BF16 PyTorch/safetensors source weights (~70 GB). This is the original weights before any quantization.

### Step 4: Convert HF BF16 → MLX

**4-bit (default — smaller, fast):**
```bash
/opt/homebrew/bin/mlx_lm.convert \
  --hf-path ~/tmp/source-hf \
  --mlx-path ~/.omlx/models/huihui-ai/Qwen3.5-35B-A3B-abliterated-4bit-mlx \
  --quantize \
  --q-bits 4 \
  --q-group-size 64
```

**6-bit (better quality — community sweet spot):**
```bash
/opt/homebrew/bin/mlx_lm.convert \
  --hf-path ~/tmp/source-hf \
  --mlx-path ~/.omlx/models/huihui-ai/Qwen3.5-35B-A3B-abliterated-6bit-mlx \
  --quantize \
  --q-bits 6 \
  --q-group-size 64
```

**4-bit with mixed-bit quality boost:**
```bash
/opt/homebrew/bin/mlx_lm.convert \
  --hf-path ~/tmp/source-hf \
  --mlx-path ~/.omlx/models/huihui-ai/Qwen3.5-35B-A3B-abliterated-mixed46-mlx \
  --quantize \
  --q-bits 4 \
  --quant-predicate mixed_4_6
```

**What's happening:**
1. Loads BF16 weights into memory
2. Applies quantization (groups of 64 weights share a scale factor)
3. Writes MLX safetensors shards + `model.safetensors.index.json`
4. Copies tokenizer + config files

**Expected output structure:**
```
~/.omlx/models/huihui-ai/Qwen3.5-35B-A3B-abliterated-4bit-mlx/
├── config.json
├── tokenizer.json
├── tokenizer_config.json
├── model.safetensors.index.json
├── model-00001-of-0000X.safetensors
└── ...
```

**Output sizes:** ~20 GB (4-bit), ~28 GB (6-bit). Conversion time: ~20–40 min on M3 Ultra.

### Step 5: Register in oMLX model_settings.json

Edit `~/.omlx/model_settings.json` and add inside the `"models"` object:

```json
"huihui-ai--Qwen3.5-35B-A3B-abliterated-4bit-mlx": {
  "force_sampling": false,
  "model_alias": "huihui-ai/Qwen3.5-35B-A3B-abliterated-4bit-mlx",
  "is_pinned": false,
  "is_default": false
}
```

**What's happening:** oMLX maps `model_alias` (the `org/repo` path relative to `~/.omlx/models/`) to API request model IDs. The JSON key uses `--` as the directory separator.

### Step 6: Restart oMLX

```bash
/opt/homebrew/bin/brew services restart omlx
```

### Step 7: Verify

```bash
# Model should appear in list
curl -s http://localhost:8000/v1/models \
  -H 'Authorization: Bearer test-key-123' | python3 -m json.tool | grep id

# Quick inference test
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Authorization: Bearer test-key-123' \
  -H 'Content-Type: application/json' \
  -d '{"model":"huihui-ai/Qwen3.5-35B-A3B-abliterated-4bit-mlx","max_tokens":30,"messages":[{"role":"user","content":"Hi"}]}'
```

### Step 8: Clean up BF16 source

```bash
rm -rf ~/tmp/source-hf
```

This frees ~70 GB. Do this after confirming inference works.

### Step 9: Update client configs and docs

After confirming the model works, update all client configs per the **Editing Workflow** in [CLAUDE.md](../../../CLAUDE.md):
- `configs/client/omlx/opencode.json`
- `configs/client/omlx/pi-models.json`
- `configs/client/omlx/openclaw-provider.json`
- `README.md` — Models & Benchmarks table
- `docs/models/model-summary.md` — add model spec entry

---

## ⚠️ Why GGUF → MLX Direct Fails

### mlx_lm.convert doesn't accept GGUF

`mlx_lm.convert` expects a directory with `config.json` + `.safetensors` or `.bin` weight files. GGUF is a single-file container format from llama.cpp — there is no GGUF input path in `mlx_lm.convert`. Passing a GGUF file or directory will error out.

### gguf2mlx failure analysis

`gguf2mlx` (github.com/barrontang/gguf2mlx) was tested on `Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive-Q8_0.gguf` (34 GB) and failed:

1. **What it needs:** `llama-cpp-python` to extract tensors from the GGUF
2. **What happened:** `llama-cpp-python` failed to load the 34 GB MoE GGUF file
3. **Fallback:** The tool created a fake 221-tensor placeholder structure (~1.7 GB instead of 34 GB)
4. **Format issue:** Output was `.npz` (numpy archive), not `.safetensors` — not loadable by oMLX

There is no reliable GGUF → MLX path. The correct approach is always: find the HF BF16 source, then run `mlx_lm.convert`.

---

## 🛠️ Troubleshooting

| Issue | Likely cause | Fix |
|-------|-------------|-----|
| OOM during conversion | BF16 source + weights in memory | Close all apps; ensure 2× BF16 source size available |
| OOM on inference (8-bit is large) | ~35 GB in memory | Add `"context_size": 16384` to model entry in `model_settings.json` |
| Model doesn't appear in API | `model_settings.json` not reloaded | Restart oMLX: `brew services restart omlx` |
| `config.json` errors / tokenizer mismatch | Conversion skipped tokenizer files | Copy tokenizer files from original HF repo |
| GPU timeout during conversion (70B+) | Dense model too large for unified memory | Use pre-built MLX from mlx-community instead |
| `mlx_lm.convert` fails on Qwen3.5 | Outdated mlx-lm or transformers | Upgrade: `pip3.11 install --upgrade mlx-lm transformers` (need ≥0.25.2 / ≥4.52.4) |
| Conversion output is `.npz` not `.safetensors` | Wrong tool (gguf2mlx fallback) | Use `mlx_lm.convert` from HF BF16 source |
