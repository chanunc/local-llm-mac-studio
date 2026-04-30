# vllm-mlx Maintenance & Troubleshooting

## Index
- [1. Upgrading vllm-mlx](#1-upgrading-vllm-mlx)
- [2. Re-applying Patches After Upgrade](#2-re-applying-patches-after-upgrade)
- [3. Port Conflicts with oMLX](#3-port-conflicts-with-omlx)
- [4. Model Loading Failures](#4-model-loading-failures)
- [5. Memory Management](#5-memory-management)
- [6. KV Cache & Context Configuration](#6-kv-cache--context-configuration)
- [7. Debug Logging](#7-debug-logging)
- [8. Qwen3.5 Tool Calling & Reasoning Parsers](#8-qwen35-tool-calling--reasoning-parsers)

---

## 🔁 1. Upgrading vllm-mlx

```bash
~/vllm-mlx-env/bin/pip install --upgrade 'git+https://github.com/waybarrios/vllm-mlx.git'
```

After upgrading, re-apply the return bug patch (see section 2) unless the upstream fix has been merged.

Check installed version:
```bash
~/vllm-mlx-env/bin/pip show vllm-mlx | grep Version
```

---

## 🩹 2. Re-applying Patches After Upgrade

### Return bug patch (v0.2.6)

After every `pip install --upgrade`, check if the bug persists:

```bash
grep -A2 'model, tokenizer = load(model_name, tokenizer_config' \
  ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/utils/tokenizer.py
```

If you see `except ValueError` immediately after the load line (no `return` statement), apply the fix:

```bash
/opt/homebrew/bin/python3.12 -c "
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
"
```

### JANG support

The JANG monkey-patch (`~/run_vllm_jang.py`) is external to the package, so it survives upgrades. No re-application needed.

---

## 🔌 3. Port Conflicts with oMLX

vllm-mlx and oMLX both default to port 8000. Only one can run at a time.

**Before starting vllm-mlx:**
```bash
/opt/homebrew/bin/brew services stop omlx
```

**Before restoring oMLX:**
```bash
pkill -f vllm-mlx; pkill -f run_vllm_jang; sleep 2
/opt/homebrew/bin/brew services start omlx
```

**Check what's on port 8000:**
```bash
lsof -i :8000 | head -5
```

---

## ⚠️ 4. Model Loading Failures

### "cannot unpack non-iterable NoneType object"

This is the return bug in `load_model_with_fallback()`. See section 2.

### "No module named 'jang_tools'"

Install jang in the vllm-mlx venv:
```bash
~/vllm-mlx-env/bin/pip install 'jang[mlx]>=0.1.0'
```

### "Package requires a different Python: 3.9.6 not in '>=3.10'"

You're using system Python instead of Homebrew Python. The venv must be created with Python 3.10+:
```bash
rm -rf ~/vllm-mlx-env
/opt/homebrew/bin/python3.12 -m venv ~/vllm-mlx-env
# Then reinstall...
```

### JANG model: "Expected shape ... but received shape ..."

You're loading a JANG model without the monkey-patch. Use `~/run_vllm_jang.py` instead of `vllm-mlx serve` directly.

---

## 🧠 5. Memory Management

vllm-mlx loads the full model into Apple Silicon unified memory. Monitor usage:

```bash
# Current memory pressure
memory_pressure | head -5

# Metal GPU memory usage
~/vllm-mlx-env/bin/python -c 'import mlx.core as mx; print(f"{mx.metal.get_active_memory()/1e9:.1f} GB active")'
```

**Important:** Always stop vllm-mlx before starting oMLX (or vice versa) to avoid OOM from both servers loading models simultaneously.

---

## 🧩 6. KV Cache & Context Configuration

vllm-mlx manages context length through its KV cache system. By default it auto-detects available RAM and allocates ~20% for cache.

### Cache memory options

| Option | Default | Purpose |
|--------|---------|---------|
| `--cache-memory-mb N` | auto (~20% RAM) | Hard limit on cache memory in MB |
| `--cache-memory-percent 0.20` | 20% of available RAM | Fraction of available RAM for cache |
| `--no-memory-aware-cache` | off | Disable auto memory detection, use legacy entry-count cache |

Example — allocate 40% of available RAM to cache (more context capacity):
```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S \
  --served-model-name JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S \
  --cache-memory-percent 0.40 \
  --port 8000 --host 0.0.0.0
```

### KV cache quantization

Quantize the KV cache at runtime to reduce memory per token, allowing longer contexts at the cost of minor quality loss:

| Option | Default | Purpose |
|--------|---------|---------|
| `--kv-cache-quantization` | off | Enable KV cache quantization |
| `--kv-cache-quantization-bits {4,8}` | 8 | Bit width (4 or 8) |
| `--kv-cache-quantization-group-size N` | 64 | Group size for quantization |
| `--kv-cache-min-quantize-tokens N` | 256 | Min tokens before quantization kicks in |

Example — 8-bit KV cache quantization:
```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S \
  --served-model-name JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S \
  --kv-cache-quantization --kv-cache-quantization-bits 8 \
  --port 8000 --host 0.0.0.0
```

### Paged KV cache (experimental)

| Option | Default | Purpose |
|--------|---------|---------|
| `--use-paged-cache` | off | Enable paged KV cache for memory efficiency |
| `--paged-cache-block-size N` | 64 | Tokens per cache block |
| `--max-cache-blocks N` | 1000 | Maximum number of cache blocks |

### Prefix caching

| Option | Default | Purpose |
|--------|---------|---------|
| `--enable-prefix-cache` | on | Cache repeated prompt prefixes |
| `--disable-prefix-cache` | — | Disable prefix caching |
| `--prefix-cache-size N` | 100 | Max entries in prefix cache (legacy mode) |

### Other generation options

| Option | Default | Purpose |
|--------|---------|---------|
| `--max-tokens N` | 32768 | Default max tokens for generation |
| `--prefill-step-size N` | 2048 | Chunk size for prompt prefill (larger = more memory, faster prefill) |
| `--chunked-prefill-tokens N` | 0 (disabled) | Max prefill tokens per scheduler step |

### Estimating context capacity

For JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S (~35GB weights) on 96GB Mac Studio:

```
Total RAM:           96 GB
Model weights:      ~35 GB
System/overhead:    ~10 GB
Available for KV:   ~51 GB

Default (20%):      ~10 GB cache → ~100K-150K context
At 40%:             ~20 GB cache → ~200K+ context
```

Check actual cache allocation at runtime:
```bash
curl -s http://localhost:8000/v1/cache/stats | python3 -m json.tool
```

---

## 🪵 7. Debug Logging

### Server logs

```bash
# Live log stream
tail -f /tmp/vllm-mlx.log

# Last 50 lines
tail -50 /tmp/vllm-mlx.log
```

### Enable DEBUG level

vllm-mlx has no `--log-level` flag. Apply the patch once to make `VLLM_MLX_LOG_LEVEL` work natively with any launch method:

```bash
~/vllm-mlx-env/bin/python scripts/patches/patch_vllm_mlx_log_level.py
```

Re-run after every `pip install --upgrade vllm-mlx` (upgrades overwrite `server.py`). Idempotent — safe to re-run at any time.

Then use the env var with any server start command:

```bash
VLLM_MLX_LOG_LEVEL=DEBUG ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S \
  --served-model-name JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S \
  --port 8000 --host 0.0.0.0
```

**Note:** The JANG wrapper (`run_vllm_jang.py`) already supports `VLLM_MLX_LOG_LEVEL` independently — it calls `logging.basicConfig()` before importing vllm-mlx so the patch is a no-op in JANG scenarios. The patch closes the gap for direct `vllm-mlx serve` (standard MLX models).

### Health checks

```bash
# List loaded models
curl -s http://localhost:8000/v1/models | python3 -m json.tool

# Cache statistics
curl -s http://localhost:8000/v1/cache/stats | python3 -m json.tool

# Server status
curl -s http://localhost:8000/v1/status | python3 -m json.tool

# Quick inference test
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'
```

### Process checks

```bash
# Is vllm-mlx running?
pgrep -f run_vllm_jang && echo "running" || echo "not running"

# What's on port 8000?
lsof -i :8000 -sTCP:LISTEN | head -3

# Memory usage
memory_pressure | head -5
```

---

## 🔧 8. Qwen3.5 Tool Calling & Reasoning Parsers

### Problem

All Qwen3.5 models (9B, 27B, 35B-A3B, 122B-A10B, 397B) emit tool calls in a **non-standard XML format**:

```xml
<tool_call>
<function=webfetch>
<parameter=url>
https://example.com
</parameter>
</function>
</tool_call>
```

Without the correct parser flags, this XML leaks into the `content` field as plain text. Clients like OpenCode render it as the model "hallucinating" tool names instead of actually calling tools.

### Fix

Add three flags when starting vllm-mlx with any Qwen3.5 model:

```bash
~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K \
  --served-model-name JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3
```

### Parser details

| Flag value | Registered as | Actual parser class | Format handled |
|-----------|--------------|---------------------|---------------|
| `qwen3_coder` | `HermesToolParser` | Nemotron XML: `<function=name><parameter=key>value</parameter></function>` | Qwen3.5 tool calls |
| `qwen` | `QwenToolParser` | JSON inside `<tool_call>` tags | Qwen3 (NOT Qwen3.5) |
| `qwen3` (reasoning) | `Qwen3ReasoningParser` | `<think>…</think>` extraction | All Qwen3/3.5 thinking models |

**Critical:** `--tool-call-parser qwen` does NOT work for Qwen3.5. The `qwen` parser expects `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` (JSON), but Qwen3.5 emits XML. Use `qwen3_coder`.

### Verification

Non-streaming test (tool calls should appear in `tool_calls` field, not in `content`):

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K",
    "messages": [{"role": "user", "content": "Browse example.com"}],
    "tools": [{"type": "function", "function": {"name": "webfetch", "description": "Fetch a web page", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}],
    "stream": false
  }' | python3 -m json.tool
```

Expected: `"tool_calls": [{"function": {"name": "webfetch", ...}}]` and `"finish_reason": "tool_calls"`.

### Stale `.pyc` cache

After upgrading or patching `server.py`, Python may still run the old compiled bytecode. Always clear after changes:

```bash
find ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/__pycache__/ -name 'server*.pyc' -delete
```
