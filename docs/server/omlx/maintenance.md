# oMLX Server Maintenance & Troubleshooting

This guide covers advanced maintenance tasks and troubleshooting for the oMLX server on the Mac Studio.

## Index
- [1. Model Discovery Issues](#1-model-discovery-issues)
  - [Method A: Verify Directory Naming](#method-a-verify-directory-naming)
  - [Method B: The "Hard Restart" (Process Persistence)](#method-b-the-hard-restart-process-persistence)
  - [Method C: Clear Discovery Cache](#method-c-clear-discovery-cache)
- [2. Managing Model Aliases](#2-managing-model-aliases)
- [3. Monitoring Downloads](#3-monitoring-downloads)
- [4. Port Conflicts](#4-port-conflicts)

## 1. Model Discovery Issues

If you add a new model to `~/.omlx/models/` but it does not appear in the dashboard or API:

### Method A: Verify Directory Naming
oMLX is most reliable when directories follow the Hugging Face `--` convention or a clean alias.
- **Recommended naming:** `org--model-name-quantization` (e.g., `mlx-community--Qwen3-Coder-Next-6bit`)
- **Avoid:** Special characters or spaces.

### Method B: The "Hard Restart" (Process Persistence)
Sometimes `brew services restart omlx` fails to kill the existing Python process, causing it to "zombie" on port 8000 and serve old metadata from memory.

**Run this command to force a clean reload:**
```bash
# Hard kill all oMLX processes and restart the service
pkill -9 -f omlx && sleep 2 && brew services restart omlx
```

### Method C: Clear Discovery Cache
If the server is stuck on an old list of models, clear the internal metadata cache:
```bash
rm -rf ~/.omlx/cache/* && brew services restart omlx
```

## 2. Managing Model Aliases

To make model IDs look cleaner in your tools (e.g., changing `mlx-community--Qwen3-Coder-Next-6bit` to `mlx-community/Qwen3-Coder-Next-6bit`), edit `~/.omlx/model_settings.json`:

```json
{
  "version": 1,
  "models": {
    "mlx-community--Qwen3-Coder-Next-6bit": {
      "model_alias": "mlx-community/Qwen3-Coder-Next-6bit"
    }
  }
}
```
*Note: Always perform a **Hard Restart** (Method B) after editing this file.*

## 3. Monitoring Downloads

Since background downloads via the API can be opaque, use these commands to monitor progress:

**Check Log Files:**
```bash
# Check the last few lines of active download logs
tail -n 5 ~/download_6bit.log
tail -n 5 ~/download_8bit.log
```

**Check Disk Usage:**
```bash
# Monitor the Hugging Face cache size
du -sh ~/.cache/huggingface/hub/models--mlx-community--Qwen*
```

## 4. Port Conflicts

If the server fails to start, check if another process is holding port 8000:
```bash
lsof -i :8000
```
If you see a process, use `kill -9 <PID>` to free the port.

## 5. JANG Fork Overlay Management

oMLX currently runs with the [AlexTzk/omlx fork](https://github.com/AlexTzk/omlx) (PR #364) pip-installed over the Homebrew v0.2.20 base to add JANG model support.

**After `brew upgrade omlx`**, re-apply the full stack:
```bash
# 1. Stop service
/opt/homebrew/bin/brew services stop jundot/omlx/omlx

# 2. Move old omlx package aside
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

**Known JANG limitations:**
- Nemotron-H architecture fails (matmul shape mismatch at latent MoE gate)
- Qwen3.5 MoE models work correctly
- JANG models are detected with `engine: jang` in discovery logs

## 6. Starlette Dashboard Fix

oMLX v0.2.20 pulls starlette 1.0.0 which breaks the admin dashboard ([#361](https://github.com/jundot/omlx/issues/361)):
```
GET /admin/dashboard → 500 (unhandled): unhashable type: 'dict'
```

Fix:
```bash
/opt/homebrew/opt/omlx/libexec/bin/pip install "starlette==0.46.2" --ignore-installed
/opt/homebrew/bin/brew services restart jundot/omlx/omlx
```

## 7. Debug Logging

To trace incoming requests and model responses:
```bash
# Enable debug logging
python3 -c "
import json
with open('/Users/chanunc/.omlx/settings.json') as f:
    cfg = json.load(f)
cfg['server']['log_level'] = 'debug'
with open('/Users/chanunc/.omlx/settings.json', 'w') as f:
    json.dump(cfg, f, indent=4)
"
/opt/homebrew/bin/brew services restart jundot/omlx/omlx

# Watch live
tail -f ~/.omlx/logs/server.log

# Revert to info when done
python3 -c "
import json
with open('/Users/chanunc/.omlx/settings.json') as f:
    cfg = json.load(f)
cfg['server']['log_level'] = 'info'
with open('/Users/chanunc/.omlx/settings.json', 'w') as f:
    json.dump(cfg, f, indent=4)
"
/opt/homebrew/bin/brew services restart jundot/omlx/omlx
```
