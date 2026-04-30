# vllm-mlx JANG Model Support Patch

Step-by-step guide to run JANG-quantized models on [vllm-mlx](https://github.com/vllm-project/vllm-mlx) (v0.2.6).

## Index
- [Background](#background)
- [How It Works](#how-it-works)
- [The Wrapper Script](#the-wrapper-script)
- [Running the Server](#running-the-server)
- [Verification](#verification)
- [Limitations](#limitations)

---

## 🔎 Background

vllm-mlx uses `mlx_lm.load()` internally (via `vllm_mlx.utils.tokenizer.load_model_with_fallback()`). Like mlx-lm.server, it cannot load JANG models natively because `mlx_lm.load()` fails on JANG's custom weight shapes.

The same monkey-patch approach works: intercept `mlx_lm.load()` before vllm-mlx starts, detect JANG paths, and delegate to `jang_tools.load_jang_model()`.

**Prerequisites:**
- vllm-mlx installed in a Python 3.10+ venv (system Python 3.9 is too old)
- `jang_tools` installed in the same venv
- JANG model downloaded to `~/.omlx/models/`

---

## 🧠 How It Works

1. A wrapper script imports `mlx_lm` and replaces `mlx_lm.load` with a patched version
2. The patched function checks if the model path contains a JANG config file
3. If JANG, calls `jang_tools.load_jang_model()`; otherwise falls through to original
4. The wrapper then invokes `vllm_mlx.cli.main()` which starts the Uvicorn server

---

## 🧩 The Wrapper Script

Create `/Users/chanunc/run_vllm_jang.py` on the Mac Studio:

```python
"""Launch vllm-mlx with JANG model support via monkey-patch."""
import sys
import os
import logging

# Support VLLM_MLX_LOG_LEVEL env var (default: INFO)
log_level = os.environ.get("VLLM_MLX_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger("jang_patch")

# Monkey-patch mlx_lm.load to detect and load JANG models
import mlx_lm
_orig_load = mlx_lm.load

def patched_load(path_or_hf_repo, tokenizer_config=None, **kwargs):
    from pathlib import Path
    from jang_tools.loader import is_jang_model, load_jang_model

    model_path = Path(path_or_hf_repo)
    if not model_path.is_dir():
        omlx_path = Path.home() / ".omlx" / "models" / path_or_hf_repo.replace("/", "--")
        if omlx_path.is_dir():
            model_path = omlx_path

    if model_path.is_dir() and is_jang_model(str(model_path)):
        logger.info(f"JANG model detected: {model_path}")
        model, tokenizer = load_jang_model(str(model_path))
        logger.info(f"JANG model loaded: {type(model).__name__}")
        return model, tokenizer

    return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)

mlx_lm.load = patched_load

logger.info("JANG monkey-patch applied to mlx_lm.load")

# Now run vllm-mlx CLI
from vllm_mlx.cli import main
sys.exit(main())
```

### Step-by-Step Setup

#### 1. Create the vllm-mlx venv (one-time)

vllm-mlx requires Python 3.10+. Use Homebrew Python 3.12:

```bash
/opt/homebrew/bin/python3.12 -m venv ~/vllm-mlx-env
~/vllm-mlx-env/bin/pip install --upgrade pip
~/vllm-mlx-env/bin/pip install 'git+https://github.com/waybarrios/vllm-mlx.git'
```

#### 2. Install jang_tools in the venv

```bash
~/vllm-mlx-env/bin/pip install 'jang[mlx]>=0.1.0'
```

#### 3. Fix the missing return bug (v0.2.6)

vllm-mlx v0.2.6 has a bug where `load_model_with_fallback()` does not return the model after a successful `mlx_lm.load()` call. Patch it:

```bash
/opt/homebrew/bin/python3.12 -c "
path = '/Users/chanunc/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/utils/tokenizer.py'
with open(path) as f:
    content = f.read()

old = '        model, tokenizer = load(model_name, tokenizer_config=tokenizer_config)\n    except ValueError as e:'
new = '        model, tokenizer = load(model_name, tokenizer_config=tokenizer_config)\n        return model, tokenizer\n    except ValueError as e:'

content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print('Patched successfully')
"
```

Verify the patch:
```bash
grep -A1 'model, tokenizer = load(model_name' ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/utils/tokenizer.py
```

Expected output:
```
        model, tokenizer = load(model_name, tokenizer_config=tokenizer_config)
        return model, tokenizer
```

#### 4. Stop oMLX (frees port 8000)

```bash
/opt/homebrew/bin/brew services stop omlx
```

#### 5. Copy the wrapper script

```bash
scp run_vllm_jang.py macstudio:~/run_vllm_jang.py
```

---

## 🚀 Running the Server

### Foreground (for testing)

```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0
```

### Background (for benchmarking)

```bash
nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 > /tmp/vllm_jang.log 2>&1 &
```

### Debug logging

vllm-mlx has no `--log-level` flag. Apply `scripts/patches/patch_vllm_mlx_log_level.py` once (see [maintenance guide](maintenance.md#7-debug-logging)), then `VLLM_MLX_LOG_LEVEL` works with any launch method including the JANG wrapper:

```bash
VLLM_MLX_LOG_LEVEL=DEBUG ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0
```

The wrapper calls `logging.basicConfig()` before importing vllm-mlx, so in JANG scenarios the wrapper's level always takes precedence — the patch is a no-op and doesn't interfere.

Expected startup log:
```
INFO:jang_patch:JANG monkey-patch applied to mlx_lm.load
INFO:jang_patch:JANG model detected: /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K
INFO:jang_tools.loader:JANG v2 detected — loading via mmap (instant)
INFO:jang_tools.loader:  Loading 4 safetensors shards via mmap
INFO:jang_tools.loader:JANG v2 loaded in 0.9s: Qwen3.5-35B-A3B (4.0-bit avg)
INFO:jang_patch:JANG model loaded: Model
INFO:vllm_mlx.models.llm:Model loaded successfully: ...
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 🧪 Verification

### Check model list
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool
```

### Test inference
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 20
  }'
```

### Test Anthropic API format (native)
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "/Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K",
    "max_tokens": 20,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### Stop the server

```bash
pkill -f run_vllm_jang
```

### Restore oMLX

```bash
/opt/homebrew/bin/brew services start omlx
```

---

## ⚠️ Limitations

- **Single model only:** `vllm-mlx serve` loads one model at startup.
- **Separate venv required:** Cannot share the oMLX Homebrew venv (Python 3.11 vs 3.12, different mlx-lm versions).
- **Model name is the full path:** The API model ID is the local filesystem path.
- **v0.2.6 return bug:** Must patch `vllm_mlx/utils/tokenizer.py` after install (see step 3 above). Future versions may fix this.
- **No admin dashboard:** No web UI for model management.
- **Not a persistent service:** Must be started manually via CLI commands above.

---

## 📊 Benchmark Results

See [model-benchmark-api-server.md](../../models/model-benchmark-api-server.md) for full comparison. Summary at 32K context:

| Server | Gen t/s | vs oMLX |
|--------|---------|---------|
| vllm-mlx + JANG | 83.8 | **+40%** |
| mlx-lm.server + JANG | 77.6 | +30% |
| oMLX + JANG | 59.9 | baseline |
