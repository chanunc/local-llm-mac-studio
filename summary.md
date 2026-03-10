# Mac Studio M3 Ultra — Local LLM Server for Claude Code

## Architecture

```
MacBook (this machine)                    Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Claude Code         │                   │ mlx-lm server (port 8080)       │
│   claude-local      │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   ANTHROPIC_BASE_URL│                   │   OpenAI API format             │
│   = :4000           │                   │                                 │
│                     │                   │ claude-code-proxy (port 4000)   │
│                     │                   │   Anthropic API → OpenAI API    │
└─────────────────────┘                   └──────────────────────────────────┘
```

## What Was Done

### Phase 1: SSH Setup
- Generated ED25519 SSH key (`~/.ssh/id_ed25519`)
- Copied public key to Mac Studio via `ssh-copy-id`
- Created `~/.ssh/config` with alias `macstudio` for `<MAC_STUDIO_IP>`

### Phase 2: Mac Studio Base Setup
- Installed Python 3.12 via Homebrew
- Created venv at `~/llm-server/venv`
- Installed `mlx-lm` (MLX-based LLM inference) and `claude-code-proxy` (Anthropic↔OpenAI translator)

### Phase 3: macOS Performance Tuning
- Maximized GPU wired memory: `iogpu.wired_limit_mb=92160` (~90GB of 96GB)
- Persisted in `/etc/sysctl.conf`
- Disabled Spotlight indexing: `sudo mdutil -a -i off`
- Disabled system sleep (keeps SSH and LLM server always reachable):
  ```bash
  sudo pmset -a sleep 0 disksleep 0 displaysleep 10
  ```
  Display still turns off after 10 min to save energy.

### Phase 4: Model Download
- Downloaded `mlx-community/Qwen3-Coder-Next-4bit` (~42GB, 4-bit quantized)
- MoE architecture (only 3B params active per pass) — 4-bit quality loss is modest
- Leaves ~50GB headroom for KV cache + OS

### Phase 5: Server Setup

**mlx-lm server (port 8080):**
- Serves OpenAI-compatible `/v1/chat/completions` API
- Supports native function/tool calling
- Loads model into Apple Silicon unified memory
- Hardened with: `--prompt-cache-size 4` (max 4 KV caches), `--prompt-cache-bytes 4294967296` (4GB cap), `--max-tokens 4096`
- Health-check cron (`~/llm-server/healthcheck.sh`) runs every 5 min, auto-restarts if unresponsive

**claude-code-proxy (port 4000):**
- Receives Anthropic `/v1/messages` requests from Claude Code
- Translates to OpenAI `/v1/chat/completions` format via `litellm.completion()`
- Translates responses back to Anthropic format (including tool_use blocks)
- **Patched** `is_claude_model = True` to ensure proper `tool_use` content blocks for all models

### Phase 6: Persistent Services (launchd)
- `~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist` — mlx-lm on port 8080
- `~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist` — claude-code-proxy on port 4000
- Both with `RunAtLoad: true`, `KeepAlive: true`, logs to `~/llm-server/logs/`

### Phase 7: Claude Code Configuration
- Created `~/.claude/macstudio-settings.json` with `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN`
- Added `claude-local` alias to `~/.zshrc`

## Key Discovery: LiteLLM Does NOT Translate

The original plan used LiteLLM proxy for Anthropic→OpenAI translation. **This does not work.** LiteLLM's `/v1/messages` endpoint is a **pass-through** — it sends Anthropic-format requests directly to the backend without translation. The fix was switching to `claude-code-proxy` (fuergaosi233), which uses `litellm.completion()` internally to do actual format translation.

## Files Modified

| Machine | File | Purpose |
|---------|------|---------|
| MacBook | `~/.ssh/id_ed25519` | SSH key |
| MacBook | `~/.ssh/config` | SSH alias `macstudio` |
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code local model config |
| MacBook | `~/.zshrc` | `claude-local` alias |
| Mac Studio | `~/llm-server/` | Project directory |
| Mac Studio | `~/llm-server/.env` | Proxy env config |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist` | mlx-lm service |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist` | Proxy service |
| Mac Studio | `/etc/sysctl.conf` | GPU memory tuning |
| Mac Studio | `server/fastapi.py` (site-packages) | Patched tool_use handling |

## Testing

### Layer 1: mlx-lm server (OpenAI format, port 8080)

Test basic chat completion directly against the model:
```bash
curl http://<MAC_STUDIO_IP>:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "messages": [{"role": "user", "content": "Write a Python hello world"}],
    "max_tokens": 200
  }'
```

Test native function/tool calling:
```bash
curl http://<MAC_STUDIO_IP>:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
    "tools": [{"type": "function", "function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}}],
    "max_tokens": 500
  }'
```
Expected: response with `"tool_calls"` array and `"finish_reason": "tool_calls"`.

List available models:
```bash
curl http://<MAC_STUDIO_IP>:8080/v1/models
```

### Layer 2: claude-code-proxy (Anthropic format, port 4000)

Test basic message (Anthropic API format):
```bash
curl http://<MAC_STUDIO_IP>:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 200,
    "messages": [{"role": "user", "content": "Write a Python hello world"}]
  }'
```
Expected: Anthropic-format response with `"type": "message"`, `"content": [{"type": "text", ...}]`.

Test tool use translation (critical for Claude Code):
```bash
curl http://<MAC_STUDIO_IP>:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1024,
    "tools": [{"name": "get_weather", "description": "Get weather for a location", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}],
    "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}]
  }'
```
Expected: `"content": [{"type": "tool_use", "id": "...", "name": "get_weather", "input": {"location": "Tokyo"}}]` and `"stop_reason": "tool_use"`.
If tool calls appear as text instead of `tool_use` blocks, the `is_claude_model` patch needs to be reapplied.

Test with system prompt:
```bash
curl http://<MAC_STUDIO_IP>:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 200,
    "system": "You are a helpful coding assistant. Always respond with code examples.",
    "messages": [{"role": "user", "content": "How do I read a file in Python?"}]
  }'
```

### Layer 3: Claude Code end-to-end

Basic prompt test:
```bash
claude-local -p "Write a Python function that reverses a string"
```

Tool use test (file reading — tests Read tool):
```bash
echo "Hello from test file" > /tmp/test-local-llm.txt
claude-local -p "Read the file /tmp/test-local-llm.txt and tell me what it says"
```

Interactive session:
```bash
claude-local
```

### Connectivity & health checks
```bash
# Is Mac Studio reachable?
ping -c 2 <MAC_STUDIO_IP>

# Is SSH working?
ssh macstudio "echo OK"

# Is mlx-lm running?
curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool

# Is proxy running?
curl -s http://<MAC_STUDIO_IP>:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool

# Memory pressure on Mac Studio
ssh macstudio "memory_pressure | head -20"
```

## Usage

```bash
# Open a new terminal, then:
claude-local

# Or one-off:
claude-local -p "Write a Python function that reverses a string"
```

## Changing the LLM Model

To swap `Qwen3-Coder-Next-4bit` for a different model (e.g., upgrading to 8-bit or a different model entirely):

### Step 1: Download the new model
```bash
ssh macstudio
cd ~/llm-server && source venv/bin/activate

# Download (replace with your model name)
python -c "from mlx_lm import load; load('mlx-community/YOUR-NEW-MODEL')"
```

### Step 2: Update mlx-lm server plist
Edit the model name in the launchd plist:
```bash
# On Mac Studio, edit ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist
# Change the <string> after --model to the new model name
nano ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist
```
Change:
```xml
<string>mlx-community/Qwen3-Coder-Next-4bit</string>
```
To:
```xml
<string>mlx-community/YOUR-NEW-MODEL</string>
```

### Step 3: Update proxy config
Edit the model names in `.env` and the launchd plist:
```bash
# On Mac Studio
# Update .env
cat > ~/llm-server/.env << 'EOF'
PREFERRED_PROVIDER=openai
OPENAI_API_KEY=not-needed
OPENAI_API_BASE=http://localhost:8080/v1
BIG_MODEL=mlx-community/YOUR-NEW-MODEL
SMALL_MODEL=mlx-community/YOUR-NEW-MODEL
EOF

# Update launchd plist env vars (BIG_MODEL and SMALL_MODEL)
nano ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist
```

### Step 4: Restart both services
```bash
# On Mac Studio
launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist
launchctl unload ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist
sleep 5
launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist
# Wait for model to load into GPU memory (check logs)
tail -f ~/llm-server/logs/mlx-lm-server.err
# Once "Uvicorn running" appears, start the proxy
launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist
```

### Step 5: Verify
Run the Layer 1 and Layer 2 tests above to confirm the new model works.

### Model sizing guide for 96GB Mac Studio
| Quantization | Approx Size | Headroom for KV cache | Recommendation |
|---|---|---|---|
| 4-bit | ~40-45GB | ~50GB | Safe, good for large context |
| 8-bit | ~80-85GB | ~10GB | Tight, may OOM on long contexts |
| 16-bit/FP16 | ~160GB+ | N/A | Will not fit |

### Finding models
Browse MLX-optimized models at: `https://huggingface.co/mlx-community`
Filter by size to find models that fit your memory budget.

## Maintenance

### Restart services
```bash
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist"
```

### Check health
```bash
# mlx-lm server
curl http://<MAC_STUDIO_IP>:8080/v1/models

# Proxy (Anthropic format)
curl http://<MAC_STUDIO_IP>:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":50,"messages":[{"role":"user","content":"Hi"}]}'

# Memory pressure
ssh macstudio "memory_pressure | head -20"
```

### Check logs
```bash
ssh macstudio "tail -20 ~/llm-server/logs/mlx-lm-server.err"
ssh macstudio "tail -20 ~/llm-server/logs/claude-code-proxy.err"
```

### After upgrading claude-code-proxy
Re-apply the tool_use patch:
```bash
ssh macstudio "SITE=~/llm-server/venv/lib/python3.12/site-packages/server && sed -i '' 's/is_claude_model = clean_model.startswith(\"claude-\")/is_claude_model = True/' \$SITE/fastapi.py"
```
