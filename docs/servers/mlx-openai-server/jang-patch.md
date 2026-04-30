# mlx-openai-server JANG Model Support Patch

Step-by-step guide to run JANG-quantized models on [mlx-openai-server](https://github.com/cubist38/mlx-openai-server) (v1.7.0), including simultaneous JANG + non-JANG multi-model deployment.

## Index
- [Background](#background)
- [How It Works](#how-it-works)
- [Installing the Patch](#installing-the-patch)
- [Running the Server](#running-the-server)
- [Multi-Model Configuration](#multi-model-configuration)
- [Verification](#verification)
- [Upgrade Safety](#upgrade-safety)
- [Limitations](#limitations)
- [Benchmark Results](#benchmark-results)

---

## 🔎 Background

mlx-openai-server uses `mlx_lm.load()` to load models, which only supports standard MLX safetensors and nvfp4. JANG models use a custom weight format (adaptive mixed-precision) that requires `jang_tools.load_jang_model()`. Both loaders return the **identical model class** (`mlx_lm.models.qwen3_5_moe.Model`) — the difference is only in weight loading.

Unlike the other servers, mlx-openai-server's multi-model mode spawns each model in a **separate subprocess** (`multiprocessing.spawn`). Standard monkey-patches applied in the parent process don't propagate to spawned children. This requires a `.pth`-based patch instead of a wrapper script.

**Why `.pth`?** Python executes `.pth` files at interpreter startup — including in spawned subprocesses. This means every model subprocess gets the patch automatically.

**Prerequisites:**
- mlx-openai-server installed in `~/mlx-openai-server-env/` (Python 3.12)
- `jang_tools` installed: `~/mlx-openai-server-env/bin/pip install jang`
- JANG model downloaded to `~/.omlx/models/`

---

## 🧠 How It Works

Two files in `~/mlx-openai-server-env/lib/python3.12/site-packages/`:

| File | Purpose |
|------|---------|
| `jang_patch.pth` | One-liner (`import jang_mlx_patch`) — triggers the patch module at Python startup |
| `jang_mlx_patch.py` | Patches `mlx_lm.utils.load` and `mlx_lm.load` to detect JANG models and delegate to `jang_tools.load_jang_model()` |

**Activation:** Set `JANG_PATCH_ENABLED=1` environment variable. Without it, the patch is dormant and mlx_lm behaves normally.

**Patch logic:**
1. Checks if the model path contains a JANG model (via `jang_tools.loader.is_jang_model()`)
2. If JANG: loads via `jang_tools.load_jang_model()`, returns standard `mlx_lm.models.qwen3_5_moe.Model`
3. If not JANG: falls through to original `mlx_lm.utils.load()` (standard MLX, nvfp4, etc.)

Both JANG and non-JANG models can run simultaneously in multi-model mode — each subprocess gets the patch independently.

---

## ⚙️ Installing the Patch

```bash
SITE=~/mlx-openai-server-env/lib/python3.12/site-packages

# 1. Create .pth trigger
echo 'import jang_mlx_patch' > $SITE/jang_patch.pth

# 2. Create patch module
cat > $SITE/jang_mlx_patch.py << 'PYEOF'
"""JANG model support patch for mlx_lm. Activated by JANG_PATCH_ENABLED=1."""
import os

if os.environ.get("JANG_PATCH_ENABLED") == "1":
    try:
        import mlx_lm.utils
        import mlx_lm

        _orig_load = mlx_lm.utils.load

        def _jang_patched_load(path_or_hf_repo, tokenizer_config=None, **kwargs):
            from pathlib import Path
            try:
                from jang_tools.loader import is_jang_model, load_jang_model
            except ImportError:
                return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)

            model_path = Path(path_or_hf_repo)
            if not model_path.is_dir():
                omlx_path = Path.home() / ".omlx" / "models" / path_or_hf_repo.replace("/", "--")
                if omlx_path.is_dir():
                    model_path = omlx_path

            if model_path.is_dir() and is_jang_model(str(model_path)):
                model, tokenizer = load_jang_model(str(model_path))
                if kwargs.get("return_config"):
                    return model, tokenizer, {}
                return model, tokenizer

            return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)

        mlx_lm.utils.load = _jang_patched_load
        mlx_lm.load = _jang_patched_load

    except ImportError:
        pass
PYEOF

# 3. Verify
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

---

## 🚀 Running the Server

**Important:** Any command that loads a JANG model must be prefixed with `JANG_PATCH_ENABLED=1`. Without it, the `.pth` patch is dormant and JANG models will fail with a shape mismatch error.

### Single JANG model

```bash
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --model-path ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --served-model-name JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --reasoning-parser qwen3_5 \
  --no-log-file
```

### Background (production)

```bash
JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml \
  --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &
```

### Stop

```bash
pkill -f mlx-openai-server
```

---

## 🧩 Multi-Model Configuration

JANG and non-JANG models can run simultaneously via YAML config. Each model runs in a process-isolated subprocess, and the `.pth` patch activates independently in each.

### YAML config (`~/mlx-openai-server-multimodel.yaml`)

```yaml
server:
  host: 0.0.0.0
  port: 8000
models:
  - model_path: /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K
    model_type: lm
    served_model_name: JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K
    reasoning_parser: qwen3_5
    context_length: 262144
  - model_path: /Users/chanunc/.omlx/models/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
    model_type: lm
    served_model_name: mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
    reasoning_parser: qwen3
    context_length: 262144
```

### Adding models

Key fields from `ModelEntryConfig`:

| Field | Default | Purpose |
|-------|---------|---------|
| `model_path` | (required) | Local path or HuggingFace repo |
| `model_type` | `lm` | `lm`, `multimodal`, `image-generation`, `image-edit`, `embeddings`, `whisper` |
| `served_model_name` | same as `model_path` | Model ID in API responses |
| `on_demand` | `false` | Load only when first requested |
| `on_demand_idle_timeout` | `60` | Seconds before unloading idle on-demand model |
| `reasoning_parser` | none | `qwen3_5`, `qwen3`, `hermes`, `kimi_k2`, etc. |
| `context_length` | model default | Override max context |

---

## 🧪 Verification

### Check model list
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool
```

### Test JANG model inference
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 20
  }'
```

### Test non-JANG model
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 20
  }'
```

### Verify patch is active
```bash
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

---

## 🔁 Upgrade Safety

The `.pth` file and patch module are **not touched by `pip install --upgrade mlx-lm`** or `pip install --upgrade mlx-openai-server`** — pip only overwrites files from its own packages. No re-patching needed after upgrades.

```bash
~/mlx-openai-server-env/bin/pip install --upgrade mlx-openai-server

# Verify JANG patch still works (should print True)
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

Only reinstall the patch if the venv itself is deleted and recreated.

The legacy wrapper script (`~/run_mlx_openai_jang.py`) is still available for single-model mode but is not needed for multi-model deployments.

---

## ⚠️ Limitations

- **Not native:** Requires `.pth`-based patch in the venv. Must be reinstalled if the venv is recreated.
- **No Anthropic-format API:** Only serves the OpenAI-compatible `/v1/chat/completions` API. Needs a proxy for Claude Code.
- **Single-request concurrency:** The InferenceWorker processes one request at a time. Multiple simultaneous clients will queue.
- **64K context performance drop:** 15% overhead vs standalone at 64K context, compared to vllm-mlx's 3%.
- **Streaming format:** Uses `reasoning_content` field for think tokens. Clients expecting `content` or `reasoning` fields will miss these tokens.
- **Separate venv:** Cannot share the vllm-mlx or oMLX venvs due to dependency conflicts.

---

## 📊 Benchmark Results

See [model-benchmark-api-server.md](../../models/benchmarks/model-benchmark-api-server.md) for full comparison. Summary at 32K context (Qwen3.5-35B-A3B JANG 4K):

| Server | Gen t/s | vs oMLX |
|--------|---------|---------|
| vllm-mlx + JANG | **83.8** | **+40%** |
| mlx-openai-server + JANG | 81.3 | +28% |
| mlx-lm.server + JANG | 77.6 | +30% |
| oMLX + JANG | 59.9 | baseline |

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-env/.../jang_patch.pth` | Triggers JANG patch at Python startup |
| `~/mlx-openai-server-env/.../jang_mlx_patch.py` | JANG detection and loading logic |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config (JANG + Qwen coder 30B 4-bit) |
| `~/run_mlx_openai_jang.py` | Legacy single-model JANG wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
