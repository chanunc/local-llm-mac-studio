# Plan: Implement Per-Model Hot Cache in oMLX

## Objective
Enable per-model `hot_cache_max_size` configuration in oMLX by dynamically patching the server code. We will create a robust, reusable Python script in this repository that can re-apply the patch whenever oMLX is updated via Homebrew.

## Technical Approach

We will create a script `scripts/patches/patch_omlx_cache.py` that modifies two files in the active `oMLX` Homebrew installation:

1. **`omlx/model_settings.py`**: Inject `hot_cache_max_size: Optional[str] = Field(default=None)` into the `ModelSettings` class to ensure the JSON parser accepts it.
2. **`omlx/engine_pool.py`**: Inject a hook right before engine creation in `_load_engine`.

The hook will:
- Read `hot_cache_max_size` from the model's settings.
- If found, update `self._scheduler_config.hot_cache_max_size`.
- If not found, fallback to the global `settings.json` value.

### Reusability (Future-Proofing)
The script will use regex and string replacement to locate the injection points dynamically, rather than hardcoding line numbers. It will also check if the hook is already present to prevent double-patching.

## Usage Instructions

After running the `scripts/patches/patch_omlx_cache.py` script on the Mac Studio and restarting the service, you can simply add `"hot_cache_max_size": "10GB"` to any model entry in the admin panel or `model_settings.json`.

### Example `model_settings.json`:
```json
{
  "version": 1,
  "models": {
    "mlx-community--Qwen3-Coder-Next-8bit": {
      "model_alias": "mlx-community/Qwen3-Coder-Next-8bit",
      "hot_cache_max_size": "10GB"
    },
    "mlx-community--Qwen3-Coder-Next-6bit": {
      "model_alias": "mlx-community/Qwen3-Coder-Next-6bit",
      "hot_cache_max_size": "40GB"
    }
  }
}
```

## Implementation Steps
1. Create `scripts/patches/patch_omlx_cache.py` locally in this repository (Completed).
2. Run the script on Mac Studio: `python3 scripts/patches/patch_omlx_cache.py`.
3. Restart oMLX: `brew services restart omlx`.
4. Add instructions to `docs/servers/omlx/maintenance.md` on how to run this script after a `brew upgrade omlx`.
5. Present changes for user review.