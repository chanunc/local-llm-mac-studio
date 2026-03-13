# Mac Studio M3 Ultra — Local LLM Server for Claude Code

## Index
- [Architecture](#architecture)
- [What Was Done](#what-was-done)
  - [Phase 1: SSH Setup](#phase-1-ssh-setup)
  - [Phase 2: Mac Studio Base Setup](#phase-2-mac-studio-base-setup)
  - [Phase 3: macOS Performance Tuning](#phase-3-macos-performance-tuning)
  - [Phase 4: Model Download](#phase-4-model-download)
  - [Phase 5: Server Setup](#phase-5-server-setup)
  - [Phase 6: Persistent Services (launchd)](#phase-6-persistent-services-launchd)
  - [Phase 7: Claude Code Configuration](#phase-7-claude-code-configuration)
- [Key Discovery: LiteLLM Does NOT Translate](#key-discovery-litellm-does-not-translate)
- [Files Modified](#files-modified)
- [Testing](#testing)
  - [Layer 1: mlx-lm server (OpenAI format, port 8080)](#layer-1-mlx-lm-server-openai-format-port-8080)
  - [Layer 2: claude-code-router (Anthropic format, port 3456)](#layer-2-claude-code-router-anthropic-format-port-3456)
  - [Layer 3: Claude Code end-to-end](#layer-3-claude-code-end-to-end)
  - [Connectivity & health checks](#connectivity--health-checks)
- [Usage](#usage)
- [Changing the LLM Model](#changing-the-llm-model)
  - [Step 1: Download the new model](#step-1-download-the-new-model)
  - [Step 2: Update mlx-lm server plist](#step-2-update-mlx-lm-server-plist)
  - [Step 3: Update router config](#step-3-update-router-config)
  - [Step 4: Restart both services](#step-4-restart-both-services)
  - [Step 5: Verify](#step-5-verify)
  - [Model sizing guide for 96GB Mac Studio](#model-sizing-guide-for-96gb-mac-studio)
  - [Finding models](#finding-models)
- [Maintenance](#maintenance)
  - [Restart services](#restart-services)
  - [Check health](#check-health)
  - [Check logs](#check-logs)
  - [Upgrade all tools](#upgrade-all-tools)

## Architecture

```
MacBook (this machine)                    Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Claude Code         │                   │ mlx-lm server (port 8080)       │
│   claude-local      │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   ANTHROPIC_BASE_URL│                   │   OpenAI API format             │
│   = :3456           │                   │                                 │
│                     │                   │ claude-code-router (port 3456)  │
│                     │                   │   Anthropic API → OpenAI API    │
└─────────────────────┘                   └──────────────────────────────────┘
```

## What Was Done

### Phase 1: SSH Setup

```bash
# On MacBook
ssh-keygen -t ed25519
ssh-copy-id <YOUR_USERNAME>@<MAC_STUDIO_IP>

# Add to ~/.ssh/config
cat >> ~/.ssh/config << 'EOF'
Host macstudio
    HostName <MAC_STUDIO_IP>
    User <YOUR_USERNAME>
    IdentityFile ~/.ssh/id_ed25519
EOF
```

### Phase 2: Mac Studio Base Setup

```bash
# On Mac Studio — install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install mlx-lm and claude-code-router via Homebrew
brew install mlx-lm claude-code-router

# Create logs dir
mkdir -p ~/llm-server/logs
```

### Phase 3: macOS Performance Tuning

```bash
# On Mac Studio — reserve ~90GB of 96GB for GPU
sudo sysctl iogpu.wired_limit_mb=92160
echo 'iogpu.wired_limit_mb=92160' | sudo tee /etc/sysctl.conf

# Disable Spotlight indexing
sudo mdutil -a -i off

# Disable system sleep (keeps SSH and LLM server always reachable)
# Display still turns off after 10 min to save energy
sudo pmset -a sleep 0 disksleep 0 displaysleep 10
```

### Phase 4: Model Download

```bash
# On Mac Studio
mlx_lm.manage --scan mlx-community/Qwen3-Coder-Next-4bit
```

- `Qwen3-Coder-Next-4bit` (~42GB, 4-bit quantized)
- MoE architecture (only 3B params active per pass) — 4-bit quality loss is modest
- Leaves ~50GB headroom for KV cache + OS

### Phase 5: Server Setup

**mlx-lm server (port 8080):**
- Installed via Homebrew (`brew install mlx-lm`)
- Serves OpenAI-compatible `/v1/chat/completions` API
- Supports native function/tool calling
- Loads model into Apple Silicon unified memory
- Tuned for max context: `--prompt-cache-size 2` (2 concurrent KV caches), `--prompt-cache-bytes 17179869184` (16GB cap, ~170K tokens per cache), `--max-tokens 8192`

**claude-code-router (port 3456):**
- Installed via Homebrew (`brew install claude-code-router`)
- Receives Anthropic `/v1/messages` requests from Claude Code
- Translates to OpenAI `/v1/chat/completions` format and routes to mlx-lm
- Built-in `enhancetool` transformer handles tool_use blocks (no manual patching needed)

Create router config:
```bash
mkdir -p ~/.claude-code-router
cat > ~/.claude-code-router/config.json << 'EOF'
{
  "APIKEY": "not-needed",
  "HOST": "0.0.0.0",
  "LOG": true,
  "API_TIMEOUT_MS": 600000,
  "Providers": [
    {
      "name": "mlx-local",
      "api_base_url": "http://localhost:8080/v1/chat/completions",
      "api_key": "not-needed",
      "models": ["mlx-community/Qwen3-Coder-Next-4bit"],
      "transformer": {
        "use": ["enhancetool"]
      }
    }
  ],
  "Router": {
    "default": "mlx-local,mlx-community/Qwen3-Coder-Next-4bit"
  }
}
EOF
```

### Phase 6: Persistent Services (launchd)

**mlx-lm server plist** (`~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>Label</key>
    <string>com.<YOUR_USERNAME>.mlx-lm-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/mlx_lm.server</string>
        <string>--model</string>
        <string>mlx-community/Qwen3-Coder-Next-4bit</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8080</string>
        <string>--prompt-cache-size</string>
        <string>2</string>
        <string>--prompt-cache-bytes</string>
        <string>17179869184</string>
        <string>--max-tokens</string>
        <string>8192</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/Users/<YOUR_USERNAME>/llm-server/logs/mlx-lm-server.err</string>
    <key>StandardOutPath</key>
    <string>/Users/<YOUR_USERNAME>/llm-server/logs/mlx-lm-server.log</string>
    <key>WorkingDirectory</key>
    <string>/Users/<YOUR_USERNAME>/llm-server</string>
</dict>
</plist>
```

**claude-code-router plist** (`~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.<YOUR_USERNAME>.litellm-proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/ccr</string>
        <string>start</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/<YOUR_USERNAME>/llm-server</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/<YOUR_USERNAME>/llm-server/logs/claude-code-proxy.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/<YOUR_USERNAME>/llm-server/logs/claude-code-proxy.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
```

Load both services:
```bash
launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist
# Wait for "Starting httpd" in logs before loading proxy
tail -f ~/llm-server/logs/mlx-lm-server.err
launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist
```

**Health-check cron** (auto-restarts mlx-lm if unresponsive):
```bash
# Add to crontab on Mac Studio
crontab -e
# Add this line:
*/5 * * * * /Users/<YOUR_USERNAME>/llm-server/healthcheck.sh
```

### Phase 7: Claude Code Configuration

On MacBook, create `~/.claude/macstudio-settings.json`:
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://<MAC_STUDIO_IP>:3456",
    "ANTHROPIC_AUTH_TOKEN": "not-needed"
  }
}
```

Add alias to `~/.zshrc`:
```bash
alias claude-local="claude --settings ~/.claude/macstudio-settings.json"
```

## Key Discovery: LiteLLM Does NOT Translate

The original plan used LiteLLM proxy for Anthropic→OpenAI translation. **This does not work.** LiteLLM's `/v1/messages` endpoint is a **pass-through** — it sends Anthropic-format requests directly to the backend without translation. The initial fix used `claude-code-proxy` (fuergaosi233) with a manual patch. This was later replaced by `claude-code-router` (musistudio), which handles tool_use natively via its `enhancetool` transformer — no patching needed.

## Files Modified

| Machine | File | Purpose |
|---------|------|---------|
| MacBook | `~/.ssh/id_ed25519` | SSH key |
| MacBook | `~/.ssh/config` | SSH alias `macstudio` |
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code local model config |
| MacBook | `~/.zshrc` | `claude-local` alias |
| Mac Studio | `~/llm-server/` | Server dir (logs, healthcheck) |
| Mac Studio | `~/.claude-code-router/config.json` | Router config (providers, routing) |
| Mac Studio | `~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist` | mlx-lm service |
| Mac Studio | `~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist` | Router service |
| Mac Studio | `/etc/sysctl.conf` | GPU memory tuning |

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

### Layer 2: claude-code-router (Anthropic format, port 3456)

Test basic message (Anthropic API format):
```bash
curl http://<MAC_STUDIO_IP>:3456/v1/messages \
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
curl http://<MAC_STUDIO_IP>:3456/v1/messages \
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
If tool calls appear as text instead of `tool_use` blocks, check the `enhancetool` transformer is configured in `~/.claude-code-router/config.json`.

Test with system prompt:
```bash
curl http://<MAC_STUDIO_IP>:3456/v1/messages \
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
curl -s http://<MAC_STUDIO_IP>:3456/v1/messages \
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

# Download (replace with your model name)
mlx_lm.manage --scan mlx-community/YOUR-NEW-MODEL
```

### Step 2: Update mlx-lm server plist
Edit the model name in the launchd plist:
```bash
# On Mac Studio, edit ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist
# Change the <string> after --model to the new model name
nano ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist
```
Change:
```xml
<string>mlx-community/Qwen3-Coder-Next-4bit</string>
```
To:
```xml
<string>mlx-community/YOUR-NEW-MODEL</string>
```

### Step 3: Update router config
Edit the model name in `~/.claude-code-router/config.json`:
```bash
# On Mac Studio — update the model in both "models" array and "Router.default"
nano ~/.claude-code-router/config.json
```

### Step 4: Restart both services
```bash
# On Mac Studio
launchctl unload ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist
launchctl unload ~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist
sleep 5
launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist
# Wait for model to load into GPU memory (check logs)
tail -f ~/llm-server/logs/mlx-lm-server.err
# Once "Uvicorn running" appears, start the proxy
launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist
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
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.mlx-lm-server.plist"
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist && launchctl load ~/Library/LaunchAgents/com.<YOUR_USERNAME>.litellm-proxy.plist"
```

### Check health
```bash
# mlx-lm server
curl http://<MAC_STUDIO_IP>:8080/v1/models

# Proxy (Anthropic format)
curl http://<MAC_STUDIO_IP>:3456/v1/messages \
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
### Upgrade all tools
```bash
# MacBook — CLI tools (Homebrew)
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent

# Mac Studio — server + router (Homebrew)
ssh macstudio "/opt/homebrew/bin/brew upgrade mlx-lm claude-code-router"
```

# Then restart both services (see above)

# Linux (narutaki) — OpenClaw
ssh narutaki "openclaw update"
```
