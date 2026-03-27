# Mac Studio M3 Ultra — Local LLM Server for Claude Code

## Index
- [Architecture](#architecture)
- [What Was Done](#what-was-done)
  - [Phase 1: SSH Setup](#phase-1-ssh-setup)
  - [Phase 2: Mac Studio Base Setup](#phase-2-mac-studio-base-setup)
  - [Phase 3: macOS Performance Tuning](#phase-3-macos-performance-tuning)
  - [Phase 4: Model Download](#phase-4-model-download)
  - [Phase 5: Server Setup](#phase-5-server-setup)
  - [Phase 6: Persistent Service](#phase-6-persistent-service)
  - [Phase 7: Claude Code Configuration](#phase-7-claude-code-configuration)
- [Key Discovery: LiteLLM Does NOT Translate](#key-discovery-litellm-does-not-translate)
- [Files Modified](#files-modified)
- [Quick Test](#quick-test)
- [Testing](#testing)
  - [Layer 1: oMLX server — OpenAI format (port 8000)](#layer-1-omlx-server--openai-format-port-8000)
  - [Layer 2: oMLX server — Anthropic format (port 8000)](#layer-2-omlx-server--anthropic-format-port-8000)
  - [Layer 3: Claude Code end-to-end](#layer-3-claude-code-end-to-end)
  - [Connectivity & health checks](#connectivity--health-checks)
- [Usage](#usage)
- [Changing the LLM Model](#changing-the-llm-model)
  - [Step 1: Load the new model](#step-1-load-the-new-model)
  - [Step 2: Restart oMLX (if needed)](#step-2-restart-omlx-if-needed)
  - [Step 3: Verify](#step-3-verify)
  - [Stopping or Cancelling Model Downloads](#stopping-or-cancelling-model-downloads)
  - [Model sizing guide for 96GB Mac Studio](#model-sizing-guide-for-96gb-mac-studio)
  - [Finding models](#finding-models)
- [Maintenance](#maintenance)
  - [Restart service](#restart-service)
  - [Check health](#check-health)
  - [Check logs](#check-logs)
  - [Check service status and version](#check-service-status-and-version)
  - [Admin panel](#admin-panel)
  - [Upgrade all tools](#upgrade-all-tools)

## Architecture

```
MacBook (this machine)                    Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Claude Code         │                   │ oMLX server (port 8000)         │
│   claude-local      │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   ANTHROPIC_BASE_URL│                   │   OpenAI + Anthropic API native │
│   = :8000           │                   │                                 │
│ OpenCode, Pi        │───── LAN ────────>│                                 │
│   (direct to 8000)  │                   │                                 │
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

# Install oMLX via Homebrew
brew tap jundot/omlx https://github.com/jundot/omlx
brew install omlx
```

**Requirements:** macOS 15.0+ (Sequoia), Apple Silicon, Python 3.10+

oMLX stores its configuration and data in `~/.omlx/` (logs, models, cache) — no manual directory setup needed.

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

Models are auto-discovered from `~/.omlx/models/` subdirectories (two-level org structure supported, e.g., `mlx-community/Qwen3-Coder-Next-4bit/`).

**Easiest method:** Admin panel at `http://<MAC_STUDIO_IP>:8000/admin` has built-in HuggingFace search and one-click download.

**Manual method:** Place or symlink a model directory into `~/.omlx/models/`. The model appears automatically on the next request — no restart needed.

Current model: `mlx-community/Qwen3-Coder-Next-4bit`
- ~42GB, 4-bit quantized
- MoE architecture (only 3B params active per pass) — 4-bit quality loss is modest
- Leaves ~50GB headroom for KV cache + OS

### Phase 5: Server Setup

**oMLX server (port 8000):**
- Installed via Homebrew (`brew install omlx`)
- Natively serves both OpenAI `/v1/chat/completions` and Anthropic `/v1/messages` API formats
- Supports native function/tool calling
- Loads model into Apple Silicon unified memory
- Single service replaces the old mlx-lm + claude-code-router two-service setup
- Supports LRU model eviction, model pinning, per-model TTL, and model aliases — configurable via admin panel or `~/.omlx/settings.json`

**API Key Authentication:**
oMLX requires an API key for access. You can configure this in two ways:
1. **Via `settings.json`:**
   Edit `~/.omlx/settings.json` and set your desired key:
   ```json
   "auth": {
     "api_key": "<YOUR_API_KEY>"
   }
   ```
2. **Via Admin Panel (First Launch):**
   When you first navigate to `http://<MAC_STUDIO_IP>:8000/admin`, you will be prompted to create an admin password and generate an API key. Save this key, as you will need it for all client connections.

**SSD cache (optional):** `--paged-ssd-cache-dir ~/.omlx/cache` enables tiered KV cache (hot RAM + cold SSD). Context persists across requests and server restarts. Useful for long-context workloads.

**RAM Caching (Hot Cache):** For high-performance tiered caching, allocate a portion of the Mac Studio's RAM to serve as a "hot" buffer for the SSD cache. This keeps the most frequently used KV blocks in memory, significantly reducing disk I/O.
- Configure in `~/.omlx/settings.json`:
  - `cache.hot_cache_max_size`: e.g., `"40GB"` or `"60GB"` (default is `"0"`)
- Example for a 96GB/128GB machine:
  ```json
  "cache": {
    "enabled": true,
    "hot_cache_max_size": "40GB"
  }
  ```
- Restart service after changing: `ssh macstudio "brew services restart omlx"`

Start for testing:
```bash
omlx serve --host 0.0.0.0 --port 8000 --api-key <YOUR_API_KEY>
```

### Phase 6: Persistent Service

Set up oMLX as a persistent service via Homebrew:
```bash
brew services start omlx
```

`brew services start omlx` auto-restarts on crash (via `KeepAlive` in the launchd plist). No custom healthcheck cron is needed.

### Phase 7: Claude Code Configuration

On MacBook, create `~/.claude/macstudio-settings.json`:
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://<MAC_STUDIO_IP>:8000",
    "ANTHROPIC_AUTH_TOKEN": "<YOUR_API_KEY>",
    "ANTHROPIC_MODEL": "mlx-community/Qwen3-Coder-Next-4bit"
  }
}
```

Add alias to `~/.zshrc`:
```bash
alias claude-local="claude --settings ~/.claude/macstudio-settings.json"
```

**Context scaling:** oMLX can scale reported token counts so Claude Code's auto-compact triggers correctly for smaller-context models. Configure in `~/.omlx/settings.json` on the Mac Studio:
- `claude_code.context_scaling_enabled`: `true`/`false`
- `claude_code.target_context_size`: integer (default `170000`)

## Key Discovery: LiteLLM Does NOT Translate

The original plan used LiteLLM proxy for Anthropic→OpenAI translation. **This does not work.** LiteLLM's `/v1/messages` endpoint is a **pass-through** — it sends Anthropic-format requests directly to the backend without translation. The initial fix used `claude-code-proxy` (fuergaosi233) with a manual patch. This was later replaced by `claude-code-router` (musistudio), which handles tool_use natively via its `enhancetool` transformer — no patching needed. The final migration to oMLX eliminated the need for any proxy entirely, as oMLX natively speaks both API formats.

## Files Modified

| Machine | File | Purpose |
|---------|------|---------|
| MacBook | `~/.ssh/id_ed25519` | SSH key |
| MacBook | `~/.ssh/config` | SSH alias `macstudio` |
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code local model config |
| MacBook | `~/.zshrc` | `claude-local` alias |
| Mac Studio | `~/.omlx/` | oMLX config, models, logs, and cache |
| Mac Studio | `/etc/sysctl.conf` | GPU memory tuning |

## Quick Test

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "messages": [{"role": "user", "content": "Say hello in one sentence"}],
    "max_tokens": 50
  }' | python3 -m json.tool
```

---

## Testing

### Layer 1: oMLX server — OpenAI format (port 8000)

Test basic chat completion:
```bash
curl http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "messages": [{"role": "user", "content": "Write a Python hello world"}],
    "max_tokens": 200
  }'
```

Test native function/tool calling:
```bash
curl http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
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
curl http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>"
```

### Layer 2: oMLX server — Anthropic format (port 8000)

Test basic message (Anthropic API format):
```bash
curl http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "max_tokens": 200,
    "messages": [{"role": "user", "content": "Write a Python hello world"}]
  }'
```
Expected: Anthropic-format response with `"type": "message"`, `"content": [{"type": "text", ...}]`.

Test tool use (critical for Claude Code):
```bash
curl http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
    "max_tokens": 1024,
    "tools": [{"name": "get_weather", "description": "Get weather for a location", "input_schema": {"type": "object", "properties": {"location": {"type": "string"}}, "required": ["location"]}}],
    "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}]
  }'
```
Expected: `"content": [{"type": "tool_use", "id": "...", "name": "get_weather", "input": {"location": "Tokyo"}}]` and `"stop_reason": "tool_use"`.

Test with system prompt:
```bash
curl http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "mlx-community/Qwen3-Coder-Next-4bit",
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
echo OK

# Is oMLX running? (OpenAI format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool

# Is oMLX running? (Anthropic format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"mlx-community/Qwen3-Coder-Next-4bit","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool

# Memory pressure on Mac Studio
memory_pressure | head -20
```

## Usage

```bash
# Open a new terminal, then:
claude-local

# Or one-off:
claude-local -p "Write a Python function that reverses a string"
```

## Changing the LLM Model

To swap `Qwen3-Coder-Next-4bit` for a different model:

### Step 1: Load the new model

Three methods:
1. **Admin panel HuggingFace downloader:** Open `http://<MAC_STUDIO_IP>:8000/admin`, search for the model, and download with one click.
2. **Manual placement:** Download or symlink the model directory into `~/.omlx/models/` on the Mac Studio.
3. Models are auto-discovered on the next request — no restart required if using the admin panel or manual placement.

### Step 2: Restart oMLX (if needed)

A restart is usually not needed for new models (they are auto-discovered). If switching the default model or changing server config:
```bash
brew services restart omlx
```

### Step 3: Verify
Run the Layer 1 and Layer 2 tests above to confirm the new model works.

### Stopping or Cancelling Model Downloads

If a download is taking too long or you've accidentally queued too many versions (e.g., multiple GGUF quantizations):

1.  **Admin Panel (Recommended):**
    - Open `http://<MAC_STUDIO_IP>:8000/admin`.
    - Go to the **Downloads** or **HuggingFace** tab.
    - Click **Cancel** on the active task. oMLX will handle the cleanup of partial files.

2.  **API Command (Advanced):**
    - Find the `task_id` in the `server.log` (e.g., `6f4def05-...`).
    - Run the following command from any machine on the LAN:
    ```bash
    curl -X POST http://<MAC_STUDIO_IP>:8000/admin/api/hf/cancel/<task_id> \
      -H "x-api-key: <YOUR_API_KEY>"
    ```

3.  **Service Restart (Nuclear Option):**
    - Restarting the service will immediately kill all background download threads.
    ```bash
    brew services restart omlx
    ```
    - **Note:** After a restart, you may need to manually delete any `.incomplete` or `.lock` files in `~/.omlx/models/` or its `.cache` subdirectories to free up space.

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

For advanced troubleshooting, discovery fixes, and "hard restart" commands, see: **[maintenance.md](maintenance.md)**

### Restart service
```bash
brew services restart omlx
```

### Check health
```bash
# oMLX server (OpenAI format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>"

# oMLX server (Anthropic format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"mlx-community/Qwen3-Coder-Next-4bit","max_tokens":50,"messages":[{"role":"user","content":"Hi"}]}'

# Memory pressure
memory_pressure | head -20
```

### Check logs
```bash
tail -20 /opt/homebrew/var/log/omlx.log   # brew service log
tail -20 ~/.omlx/logs/server.log           # application log
```

### Check service status and version
```bash
brew services info omlx  # service status
brew info omlx           # check version
```

### Admin panel

`http://<MAC_STUDIO_IP>:8000/admin` — real-time monitoring, model management, built-in chat, benchmarking, HuggingFace downloader, per-model settings.
### Upgrade all tools
```bash
# MacBook — CLI tools (Homebrew)
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent

# Mac Studio — oMLX server (Homebrew)
/opt/homebrew/bin/brew upgrade omlx
```

# Then restart: brew services restart omlx

# Linux (narutaki) — OpenClaw
ssh narutaki "openclaw update"
```
