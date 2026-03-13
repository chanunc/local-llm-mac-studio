# Plan: Implement Per-Model Hot Cache in oMLX

## Objective
Enable per-model `hot_cache_max_size` configuration in oMLX by dynamically patching the server code. We will create a robust, reusable Python script in this repository that can re-apply the patch whenever oMLX is updated via Homebrew.

## Technical Approach

We will create a script `scripts/patch_omlx_cache.py` that modifies two files in the active `oMLX` Homebrew installation:

1. **`omlx/model_settings.py`**: Inject `hot_cache_max_size: Optional[str] = Field(default=None)` into the `ModelSettings` class to ensure the JSON parser accepts it.
2. **`omlx/engine_pool.py`**: Inject a hook right before engine creation in `_load_engine`.

The hook will:
- Read `hot_cache_max_size` from the model's settings.
- If found, update `self._scheduler_config.hot_cache_max_size`.
- If not found, fallback to the global `settings.json` value.

### Reusability (Future-Proofing)
The script will use regex and string replacement to locate the injection points dynamically, rather than hardcoding line numbers. It will also check if the hook is already present to prevent double-patching.

## Implementation Steps

1. Create `scripts/patch_omlx_cache.py` locally in this repository.
2. Add instructions to `docs/server/omlx-maintenance.md` on how to run this script after a `brew upgrade omlx`.
3. Present changes for user review.