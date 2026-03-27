# mlx-lm.server JANG Model Support Patch

Step-by-step guide to run JANG-quantized models on Apple's built-in `mlx-lm.server` (v0.31.2).

## Index
- [Background](#background)
- [How It Works](#how-it-works)
- [The Wrapper Script](#the-wrapper-script)
- [Running the Server](#running-the-server)
- [Verification](#verification)
- [Limitations](#limitations)

---

## Background

`mlx-lm.server` uses `mlx_lm.load()` to load models, which only supports standard MLX safetensors. JANG models use a custom weight format (adaptive mixed-precision) that requires `jang_tools.load_jang_model()` to load. However, both loaders return the **identical model class** (`mlx_lm.models.qwen3_5_moe.Model`) -- the difference is only in weight loading.

This means we can monkey-patch `mlx_lm.load()` to detect JANG model paths and delegate to the JANG loader, with zero changes to the server code.

**Prerequisites:**
- `mlx-lm` installed (comes with oMLX Homebrew venv)
- `jang_tools` installed: `/opt/homebrew/opt/omlx/libexec/bin/pip install 'jang[mlx]>=0.1.0'`
- JANG model downloaded to `~/.omlx/models/` (e.g., `JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K`)

---

## How It Works

1. A wrapper script imports `mlx_lm` and replaces `mlx_lm.load` with a patched version
2. The patched function checks if the model path contains a JANG config file (via `jang_tools.loader.is_jang_model()`)
3. If JANG is detected, it calls `jang_tools.load_jang_model()` instead of the original `mlx_lm.load()`
4. If not JANG, it falls through to the original `mlx_lm.load()` unchanged
5. The wrapper then starts the normal mlx-lm server via `mlx_lm.server.main()`

---

## The Wrapper Script

Create `/Users/chanunc/run_mlx_server_jang.py` on the Mac Studio:

```python
"""Launch mlx-lm.server with JANG model support via monkey-patch."""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jang_patch")

# Monkey-patch mlx_lm.load to detect and load JANG models
import mlx_lm
_orig_load = mlx_lm.load

def patched_load(path_or_hf_repo, tokenizer_config=None, **kwargs):
    from pathlib import Path
    from jang_tools.loader import is_jang_model, load_jang_model

    # Resolve path: could be HF repo name or local path
    model_path = Path(path_or_hf_repo)
    if not model_path.is_dir():
        # Check oMLX models directory with -- convention
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
# Also patch in mlx_lm.utils since server.py imports load from there
import mlx_lm.utils
mlx_lm.utils.load = patched_load

logger.info("JANG monkey-patch applied to mlx_lm.load")

# Now run the server
from mlx_lm.server import main
sys.exit(main())
```

### Step-by-Step Setup

#### 1. Stop oMLX (frees port 8000 and GPU memory)

```bash
/opt/homebrew/bin/brew services stop omlx
```

#### 2. Copy the wrapper script

```bash
scp run_mlx_server_jang.py macstudio:~/run_mlx_server_jang.py
```

Or create it directly:
```bash
cat > ~/run_mlx_server_jang.py << 'PYEOF'
# paste the script above
PYEOF
```

#### 3. Verify jang_tools is installed

```bash
/opt/homebrew/opt/omlx/libexec/bin/python -c 'from jang_tools.loader import is_jang_model; print("OK")'
```

If not installed:
```bash
/opt/homebrew/opt/omlx/libexec/bin/pip install 'jang[mlx]>=0.1.0'
```

---

## Running the Server

### Foreground (for testing)

```bash
/opt/homebrew/opt/omlx/libexec/bin/python ~/run_mlx_server_jang.py \
  --model /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0
```

### Background (for benchmarking)

```bash
nohup /opt/homebrew/opt/omlx/libexec/bin/python ~/run_mlx_server_jang.py \
  --model /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 > /tmp/mlx_jang.log 2>&1 &
```

### With tuning options

```bash
/opt/homebrew/opt/omlx/libexec/bin/python ~/run_mlx_server_jang.py \
  --model /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --prompt-cache-size 2 \
  --prompt-cache-bytes 17179869184
```

Expected startup log:
```
INFO:jang_patch:JANG monkey-patch applied to mlx_lm.load
INFO:jang_patch:JANG model detected: /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K
INFO:jang_tools.loader:JANG v2 detected — loading via mmap (instant)
INFO:jang_tools.loader:  Loading 4 safetensors shards via mmap
INFO:jang_tools.loader:JANG v2 loaded in 2.9s: Qwen3.5-35B-A3B (4.0-bit avg)
INFO:jang_patch:JANG model loaded: Model
INFO:root:Starting httpd at 0.0.0.0 on port 8000...
```

---

## Verification

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

### Stop the server

```bash
pkill -f run_mlx_server_jang
```

### Restore oMLX

```bash
/opt/homebrew/bin/brew services start omlx
```

---

## Limitations

- **Single model only:** mlx-lm.server loads one model at startup. No hot-swapping.
- **No admin dashboard:** Unlike oMLX, there is no web UI.
- **Model name is the full path:** The API model ID is the local filesystem path, not a clean HF-style name.
- **Not production-hardened:** mlx-lm.server warns it "is not recommended for production as it only implements basic security checks."
- **No Anthropic API format:** Only serves OpenAI `/v1/chat/completions`. Needs a proxy (e.g., claude-code-router) for Claude Code compatibility.
- **Reasoning field quirk:** Qwen3.5 models stream thinking tokens in the `delta.reasoning` field instead of `delta.content`. Some clients may not parse this correctly.

---

## Benchmark Results

See [model-benchmark-api-server.md](../models/model-benchmark-api-server.md) for full comparison. Summary at 32K context:

| Server | Gen t/s | vs oMLX |
|--------|---------|---------|
| mlx-lm.server + JANG | 77.6 | +30% |
| oMLX + JANG | 59.9 | baseline |
