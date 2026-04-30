# Plan: Connect iTermAI to oMLX Server

## Context

iTermAI is iTerm2's built-in AI plugin. It uses **OpenAI Chat Completions format** (`/v1/chat/completions`) and supports custom local endpoints. oMLX already serves this format natively — no proxy, no server changes, no model renaming needed. This is a client-side configuration only.

---

## Key Finding

iTermAI config lives entirely in iTerm2 Settings → AI tab. Just point it at oMLX's OpenAI endpoint with the correct model ID.

---

## Setup Steps

### Step 1: Open iTerm2 AI Settings

`iTerm2 menu → Settings (⌘,) → AI tab`

Enable "Configure AI Model Manually" if shown.

### Step 2: Fill in the fields

| Field | Value |
|-------|-------|
| **URL** | `http://<MAC_STUDIO_IP>:8000/v1/chat/completions` |
| **API Key** | `test-key-123` (any non-empty string — oMLX ignores the value) |
| **Model** | See model ID list below |

### Step 3: Recommended model IDs

Use the model ID **exactly as served by oMLX** (org prefix may be stripped by oMLX):

| Model ID | Notes |
|----------|-------|
| `mlx-community/Qwen3.5-35B-A3B-8bit` | Recommended — 69.2% SWE-bench, fast MoE |
| `NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit` | Fast, efficient |
| `Huihui-Qwen3.5-35B-A3B-abliterated-8bit-mlx` | Uncensored variant |

> Confirm exact IDs at any time:
> ```bash
> curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
>   -H "Authorization: Bearer test-key-123" | python3 -m json.tool | grep '"id"'
> ```

### Step 4: Test in iTerm2

Open AI chat (Cmd+Y or AI menu) and send a test prompt. A coherent response confirms the connection is working.

---

## Verification

```bash
# Test the exact endpoint iTermAI calls
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Authorization: Bearer test-key-123" \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen3.5-35B-A3B-8bit","max_tokens":20,"messages":[{"role":"user","content":"Hi"}]}'
```

Expected: JSON response with a non-empty `content` field in `choices[0].message`.
