# vllm-mlx Maintenance & Troubleshooting

## Index
- [1. Upgrading vllm-mlx](#1-upgrading-vllm-mlx)
- [2. Re-applying Patches After Upgrade](#2-re-applying-patches-after-upgrade)
- [3. Port Conflicts with oMLX](#3-port-conflicts-with-omlx)
- [4. Model Loading Failures](#4-model-loading-failures)
- [5. Memory Management](#5-memory-management)
- [6. Persistent Service Setup](#6-persistent-service-setup)
- [7. Debug Logging](#7-debug-logging)

---

## 1. Upgrading vllm-mlx

```bash
ssh macstudio "~/vllm-mlx-env/bin/pip install --upgrade 'git+https://github.com/waybarrios/vllm-mlx.git'"
```

After upgrading, re-apply the return bug patch (see section 2) unless the upstream fix has been merged.

Check installed version:
```bash
ssh macstudio "~/vllm-mlx-env/bin/pip show vllm-mlx | grep Version"
```

---

## 2. Re-applying Patches After Upgrade

### Return bug patch (v0.2.6)

After every `pip install --upgrade`, check if the bug persists:

```bash
ssh macstudio "grep -A2 'model, tokenizer = load(model_name, tokenizer_config' ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/utils/tokenizer.py"
```

If you see `except ValueError` immediately after the load line (no `return` statement), apply the fix:

```bash
ssh macstudio "/opt/homebrew/bin/python3.12 -c \"
path = '/Users/chanunc/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/utils/tokenizer.py'
with open(path) as f:
    content = f.read()
old = '        model, tokenizer = load(model_name, tokenizer_config=tokenizer_config)\n    except ValueError as e:'
new = '        model, tokenizer = load(model_name, tokenizer_config=tokenizer_config)\n        return model, tokenizer\n    except ValueError as e:'
if 'return model, tokenizer' not in content.split('load(model_name')[1].split('except')[0]:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('Patched')
else:
    print('Already patched or fixed upstream')
\""
```

### JANG support

The JANG monkey-patch (`~/run_vllm_jang.py`) is external to the package, so it survives upgrades. No re-application needed.

---

## 3. Port Conflicts with oMLX

vllm-mlx and oMLX both default to port 8000. Only one can run at a time.

**Before starting vllm-mlx:**
```bash
ssh macstudio "/opt/homebrew/bin/brew services stop omlx"
```

**Before restoring oMLX:**
```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f run_vllm_jang; sleep 2"
ssh macstudio "/opt/homebrew/bin/brew services start omlx"
```

**Check what's on port 8000:**
```bash
ssh macstudio "lsof -i :8000 | head -5"
```

---

## 4. Model Loading Failures

### "cannot unpack non-iterable NoneType object"

This is the return bug in `load_model_with_fallback()`. See section 2.

### "No module named 'jang_tools'"

Install jang in the vllm-mlx venv:
```bash
ssh macstudio "~/vllm-mlx-env/bin/pip install 'jang[mlx]>=0.1.0'"
```

### "Package requires a different Python: 3.9.6 not in '>=3.10'"

You're using system Python instead of Homebrew Python. The venv must be created with Python 3.10+:
```bash
ssh macstudio "rm -rf ~/vllm-mlx-env"
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/vllm-mlx-env"
# Then reinstall...
```

### JANG model: "Expected shape ... but received shape ..."

You're loading a JANG model without the monkey-patch. Use `~/run_vllm_jang.py` instead of `vllm-mlx serve` directly.

---

## 5. Memory Management

vllm-mlx loads the full model into Apple Silicon unified memory. Monitor usage:

```bash
# Current memory pressure
ssh macstudio "memory_pressure | head -5"

# Metal GPU memory usage
ssh macstudio "~/vllm-mlx-env/bin/python -c 'import mlx.core as mx; print(f\"{mx.metal.get_active_memory()/1e9:.1f} GB active\")'"
```

**Important:** Always stop vllm-mlx before starting oMLX (or vice versa) to avoid OOM from both servers loading models simultaneously.

---

## 6. Service Management

vllm-mlx runs as a launchd service with a convenience script (`~/bin/vllm-service`) that handles oMLX port conflicts automatically.

**Components:**
- **Plist:** `~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist` (launchd service definition)
- **Script:** `~/bin/vllm-service` (start/stop/restart/status/log)
- **Wrapper:** `~/run_vllm_jang.py` (JANG monkey-patch + vllm-mlx CLI)
- **Log:** `/opt/homebrew/var/log/vllm-mlx.log`

**Source files in repo:** `configs/vllm-mlx.plist`, `scripts/vllm-mlx-service.sh`

### Quick Reference

```bash
# Switch from oMLX to vllm-mlx (stops oMLX, starts vllm-mlx)
ssh macstudio "~/bin/vllm-service start"

# Switch back to oMLX (stops vllm-mlx, starts oMLX)
ssh macstudio "~/bin/vllm-service stop"

# Restart vllm-mlx (no oMLX swap)
ssh macstudio "~/bin/vllm-service restart"

# Check status and health
ssh macstudio "~/bin/vllm-service status"

# Tail logs
ssh macstudio "~/bin/vllm-service log"
```

### How It Works

- **`start`** checks if oMLX is running on port 8000 and stops it first, then loads the vllm-mlx launchd plist. The service has `KeepAlive: true` so launchd auto-restarts it on crash.
- **`stop`** unloads the plist and automatically restarts oMLX (the production default).
- **`RunAtLoad: false`** — vllm-mlx does NOT start on boot. oMLX is the default production server and owns port 8000 at boot time. Start vllm-mlx explicitly when needed.
- **`status`** shows PID, port owner, and runs a `/v1/models` health check.

### Re-deploying After Changes

If you modify the plist or service script in the repo:
```bash
# Update plist
scp configs/vllm-mlx.plist macstudio:~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist

# Update service script
scp scripts/vllm-mlx-service.sh macstudio:~/bin/vllm-service
ssh macstudio "chmod +x ~/bin/vllm-service"

# If vllm-mlx is running, restart to pick up plist changes
ssh macstudio "~/bin/vllm-service restart"
```

### Changing the Model

Edit the plist to change the model path:
```bash
ssh macstudio "sed -i '' 's|JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K|NEW-MODEL-DIR|' ~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist"
ssh macstudio "~/bin/vllm-service restart"
```

Or for standard (non-JANG) models, edit `ProgramArguments` in the plist to use `~/vllm-mlx-env/bin/vllm-mlx` directly instead of the JANG wrapper.

---

## 7. Debug Logging

### Server logs

```bash
# Live logs (via service script)
ssh macstudio "~/bin/vllm-service log"

# Or directly
ssh macstudio "tail -f /opt/homebrew/var/log/vllm-mlx.log"
```

### Verbose startup

Edit the plist to add `--log-level` `debug` to ProgramArguments, then restart:
```bash
ssh macstudio "~/bin/vllm-service restart"
```

### Cache statistics

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/cache/stats | python3 -m json.tool
```

### Server status

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/status | python3 -m json.tool
```
