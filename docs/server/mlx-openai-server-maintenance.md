# mlx-openai-server Maintenance

## JANG Model Support

Not supported natively. JANG models require a `.pth`-based patch installed in the venv that intercepts `mlx_lm.load()` at Python startup.

### Why a patch is needed

mlx-openai-server's multi-model mode spawns each model in a separate subprocess (`multiprocessing.spawn`). Standard monkey-patches applied in the parent process don't propagate to spawned children. The `.pth` approach solves this because Python executes `.pth` files at interpreter startup — including in spawned subprocesses.

### How it works

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

### Upgrade safety

The `.pth` file and patch module are **not touched by `pip install --upgrade mlx-lm`** or `pip install --upgrade mlx-openai-server` — pip only overwrites files from its own packages. No re-patching needed after upgrades.

The legacy wrapper script (`~/run_mlx_openai_jang.py`) is still available for single-model mode but is not needed for multi-model deployments.

### Installing the patch

If the venv is recreated, reinstall the patch:

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

## Multi-Model Configuration

YAML config at `~/mlx-openai-server-multimodel.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8000
models:
  - model_path: /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K
    model_type: lm
    served_model_name: JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K
    reasoning_parser: qwen3_5
  - model_path: /Users/chanunc/.omlx/models/RepublicOfKorokke--Nemotron-Cascade-2-30B-A3B-mlx-nvfp4
    model_type: lm
    served_model_name: RepublicOfKorokke/Nemotron-Cascade-2-30B-A3B-mlx-nvfp4
    on_demand: true
    on_demand_idle_timeout: 120
```

Start with:

```bash
JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml \
  --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &
```

### Adding models

Add entries to the YAML config. Key fields from `ModelEntryConfig`:

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

## Upgrading

```bash
~/mlx-openai-server-env/bin/pip install --upgrade mlx-openai-server

# Verify JANG patch still works (should print True)
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

The `.pth` patch survives upgrades. Only reinstall if the venv itself is deleted and recreated.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-env/.../jang_patch.pth` | Triggers JANG patch at Python startup |
| `~/mlx-openai-server-env/.../jang_mlx_patch.py` | JANG detection and loading logic |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config (JANG + nvfp4) |
| `~/run_mlx_openai_jang.py` | Legacy single-model JANG wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
