# oMLX JANG Fork Overlay

How JANG and nvfp4 model support was added to the oMLX server via [AlexTzk/omlx](https://github.com/AlexTzk/omlx) fork (PR [#364](https://github.com/jundot/omlx/pull/364)).

## Index
- [Background](#background)
- [What the Fork Adds](#what-the-fork-adds)
- [Installation](#installation)
- [Supported Formats](#supported-formats)
- [Current JANG & nvfp4 Models](#current-jang--nvfp4-models)
- [Known Limitations](#known-limitations)
- [Maintenance After Upgrades](#maintenance-after-upgrades)
- [Rollback](#rollback)

---

## 🔎 Background

oMLX v0.2.20 (Homebrew) only loads standard MLX safetensors. To serve JANG-quantized models (adaptive mixed-precision) and nvfp4 models, we pip-install AlexTzk's fork over the Homebrew package. The fork adds a `JANGLoader` engine (+1,130 lines) that handles JANG's custom weight format, and the existing MLX engine handles nvfp4 natively.

**Architecture after fork overlay:**
```
/opt/homebrew/Cellar/omlx/0.2.20/libexec/lib/python3.11/site-packages/
├── omlx/           ← AlexTzk fork (pip-installed over Homebrew)
├── omlx.bak/       ← Original Homebrew package (backup)
├── jang/            ← jang-2.2.0 (pip dependency)
└── starlette/       ← Pinned to 0.46.2 (dashboard fix)
```

## 🧠 What the Fork Adds

- **`omlx/engine/jang.py`** — 675-line `JANGLoader` that reads JANG v2 format (zero-copy mmap, custom Metal kernels)
- **JANG model discovery** — Models with JANG metadata detected as `engine: jang` in server logs
- **Standard MLX engine** — Unchanged; continues to serve MLX safetensors including nvfp4 quantizations

## ⚙️ Installation

These steps install the fork into the existing Homebrew oMLX venv. Run from your client machine (MacBook).

### 1. Stop oMLX
```bash
/opt/homebrew/bin/brew services stop jundot/omlx/omlx
```

### 2. Back up original package
```bash
SITE=/opt/homebrew/opt/omlx/libexec/lib/python3.11/site-packages && mv $SITE/omlx $SITE/omlx.bak
```

### 3. Install JANG dependency
```bash
/opt/homebrew/opt/omlx/libexec/bin/pip install 'jang[mlx]>=0.1.0'
```

### 4. Install fork (no-deps to preserve existing packages)
```bash
/opt/homebrew/opt/omlx/libexec/bin/pip install --no-deps --target=/opt/homebrew/opt/omlx/libexec/lib/python3.11/site-packages git+https://github.com/AlexTzk/omlx.git@main
```

### 5. Re-apply hot cache patch
The fork overwrites `engine_pool.py` and `model_settings.py`, so the per-model hot cache patch must be reapplied:
```bash
python3 /tmp/patch_omlx_cache.py
```

### 6. Fix starlette dashboard bug
oMLX v0.2.20 pulls starlette 1.0.0 which breaks the admin dashboard ([#361](https://github.com/jundot/omlx/issues/361)):
```bash
/opt/homebrew/opt/omlx/libexec/bin/pip install "starlette==0.46.2" --ignore-installed
```

### 7. Start oMLX
```bash
/opt/homebrew/bin/brew services start jundot/omlx/omlx
```

### 8. Verify
```bash
# Check all models discovered
curl -s http://localhost:8000/v1/models -H 'Authorization: Bearer <YOUR_API_KEY>' | python3 -c 'import sys,json; [print(m["id"]) for m in json.load(sys.stdin)["data"]]'

# Check JANG models detected
grep -i jang ~/.omlx/logs/server.log | tail -5

# Test inference on a JANG model
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"model": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K", "messages": [{"role": "user", "content": "Hello"}], "max_tokens": 10}'
```

---

## 🧩 Supported Formats

After the fork overlay, oMLX serves three model formats:

| Format | Engine | Example | Notes |
|:-------|:-------|:--------|:------|
| **MLX safetensors** | MLX (built-in) | `mlx-community/Qwen3-Coder-Next-6bit` | Standard quantizations (4/6/8-bit) |
| **MLX nvfp4/mxfp4** | MLX (built-in) | `RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4` | NVIDIA FP4 and MX FP4 quantizations |
| **JANG** | JANGLoader (fork) | `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` | Adaptive mixed-precision via [jangq.ai](https://jangq.ai) |

**Not supported:** GGUF, MXFP8 (unconfirmed).

---

## 🤖 Current JANG & nvfp4 Models

| Model | Format | Size | Context | Status |
|:-------|:-------|:-----|:--------|:-------|
| [Qwen3.5-35B-A3B JANG 4K](https://huggingface.co/JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K) | JANG 4-bit | 19 GB | 262K | Active |
| [Nemotron Cascade 2 30B-A3B nvfp4](https://huggingface.co/RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4) | nvfp4 | 17 GB | 32K | Active |
| [Qwen3.5-122B-A10B JANG 2S](https://huggingface.co/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S) | JANG 2-bit | 35 GB | 200K+ | Downloaded, not activated |

---

## ⚠️ Known Limitations

- **JANG + Nemotron-H architecture**: JANG-quantized models using the Nemotron-H architecture (Mamba-2 + latent MoE gate) fail with `[matmul] shape mismatch` at the expert router gate. This is a bug in PR #364's weight mapping for latent MoE projections. Affects: `JANGQ-AI/Nemotron-Cascade-2-30B-A3B-JANG_4M`, `JANGQ-AI/Nemotron-3-Super-120B-A12B-JANG_4M`. **Workaround:** Use MLX nvfp4/mxfp4 quantizations instead for Nemotron models.
- **Non-Nemotron JANG models work fine**: Qwen3.5-35B-A3B, Qwen3.5-122B-A10B, and other non-Nemotron architectures load and run correctly via JANG.
- **Unreviewed code**: The fork has not been merged upstream. JANG loader code is unreviewed by oMLX maintainers.
- **Breaks Homebrew upgrade path**: `brew upgrade omlx` will overwrite the fork — must re-apply after every upgrade (see below).

---

## 🛠️ Maintenance After Upgrades

After `brew upgrade omlx`, the fork is overwritten. Re-apply the full stack:

```bash
# 1. Stop service
/opt/homebrew/bin/brew services stop jundot/omlx/omlx

# 2. Move new omlx package aside
SITE=/opt/homebrew/opt/omlx/libexec/lib/python3.11/site-packages && mv $SITE/omlx $SITE/omlx.bak

# 3. Install JANG dependency + fork
/opt/homebrew/opt/omlx/libexec/bin/pip install 'jang[mlx]>=0.1.0'
/opt/homebrew/opt/omlx/libexec/bin/pip install --no-deps --target=$SITE git+https://github.com/AlexTzk/omlx.git@main

# 4. Re-apply hot cache patch
python3 /tmp/patch_omlx_cache.py

# 5. Fix starlette dashboard bug
/opt/homebrew/opt/omlx/libexec/bin/pip install "starlette==0.46.2" --ignore-installed

# 6. Restart
/opt/homebrew/bin/brew services start jundot/omlx/omlx
```

---

## 🔁 Rollback

To revert to stock Homebrew oMLX (removes JANG support):

```bash
# 1. Stop service
/opt/homebrew/bin/brew services stop jundot/omlx/omlx

# 2. Reinstall clean oMLX from Homebrew
/opt/homebrew/bin/brew reinstall omlx

# 3. Re-apply non-fork patches
/opt/homebrew/opt/omlx/libexec/bin/pip install "starlette==0.46.2" --ignore-installed
python3 /tmp/patch_omlx_cache.py

# 4. Restart
/opt/homebrew/bin/brew services start jundot/omlx/omlx
```

JANG and nvfp4 models will no longer load after rollback. Standard MLX safetensors models are unaffected.
