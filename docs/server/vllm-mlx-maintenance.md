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

## 6. Persistent Service Setup

To run vllm-mlx as a persistent launchd service (auto-start on boot):

Create `~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist` on Mac Studio:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.chanunc.vllm-mlx</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/chanunc/vllm-mlx-env/bin/python</string>
        <string>/Users/chanunc/run_vllm_jang.py</string>
        <string>serve</string>
        <string>/Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K</string>
        <string>--port</string>
        <string>8000</string>
        <string>--host</string>
        <string>0.0.0.0</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/chanunc/llm-server/logs/vllm-mlx.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/chanunc/llm-server/logs/vllm-mlx.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

**Note:** `RunAtLoad` and `KeepAlive` are set to `false` to avoid conflict with oMLX (which is the default production server). Start manually when needed:

```bash
# Start vllm-mlx (stop oMLX first)
ssh macstudio "/opt/homebrew/bin/brew services stop omlx"
ssh macstudio "launchctl load ~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist"

# Stop vllm-mlx and restore oMLX
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist"
ssh macstudio "/opt/homebrew/bin/brew services start omlx"
```

---

## 7. Debug Logging

### Server logs

```bash
# Live logs (foreground mode)
ssh macstudio "tail -f /tmp/vllm_jang.log"

# Or if using launchd
ssh macstudio "tail -f ~/llm-server/logs/vllm-mlx.err"
```

### Verbose startup

Add `--log-level debug` to the serve command:
```bash
ssh macstudio "~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  /Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 --log-level debug"
```

### Cache statistics

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/cache/stats | python3 -m json.tool
```

### Server status

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/status | python3 -m json.tool
```
