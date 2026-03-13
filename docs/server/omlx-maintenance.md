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
ssh macstudio "pkill -9 -f omlx && sleep 2 && brew services restart omlx"
```

### Method C: Clear Discovery Cache
If the server is stuck on an old list of models, clear the internal metadata cache:
```bash
ssh macstudio "rm -rf ~/.omlx/cache/* && brew services restart omlx"
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
ssh macstudio "tail -n 5 ~/download_6bit.log"
ssh macstudio "tail -n 5 ~/download_8bit.log"
```

**Check Disk Usage:**
```bash
# Monitor the Hugging Face cache size
ssh macstudio "du -sh ~/.cache/huggingface/hub/models--mlx-community--Qwen*"
```

## 4. Port Conflicts

If the server fails to start, check if another process is holding port 8000:
```bash
ssh macstudio "lsof -i :8000"
```
If you see a process, use `kill -9 <PID>` to free the port.
