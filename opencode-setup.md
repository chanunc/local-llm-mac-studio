# OpenCode Setup: MacBook → Mac Studio LLM Server

OpenCode connects **directly** to the mlx-lm server's OpenAI-compatible endpoint — no proxy needed.

## Architecture

```
MacBook                                   Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ OpenCode            │                   │ mlx-lm server (port 8080)       │
│   openai-compatible │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   direct connection │                   │   /v1/chat/completions          │
└─────────────────────┘                   └──────────────────────────────────┘
```

## Installation

```bash
brew install opencode
```

Verify: `opencode --version`

## Configuration

Copy config from this repo, or create manually:

```bash
mkdir -p ~/.config/opencode
cp configs/opencode.json ~/.config/opencode/opencode.json
```

Global config at `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "macstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://<MAC_STUDIO_IP>:8080/v1",
        "apiKey": "not-needed",
        "timeout": 600000
      },
      "models": {
        "mlx-community/Qwen3-Coder-Next-4bit": {
          "name": "Qwen3 Coder (Mac Studio)",
          "limit": {
            "context": 16000,
            "output": 4096
          }
        }
      }
    }
  },
  "model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit",
  "small_model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit"
}
```

### Shell Alias

Add to `~/.zshrc`:

```bash
alias oc='opencode'
```

## Testing

1. **Connectivity check**:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool
   ```

2. **Launch interactive TUI**:
   ```bash
   opencode
   ```
   Send "Hello" and verify you get a response.

3. **One-shot test**:
   ```bash
   opencode -p "Write a Python hello world"
   ```

4. **Tool use test**: Create a test file, then ask OpenCode to read it.

## Troubleshooting

### Can't connect to Mac Studio

- Verify the server is running: `curl http://<MAC_STUDIO_IP>:8080/v1/models`
- Check if mlx-lm is up: `ssh macstudio "launchctl list | grep mlx"`
- Restart mlx-lm:
  ```bash
  ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
  ```

### Slow or hanging responses

- The 600000ms (10 min) timeout in config should handle long generations
- Check Mac Studio memory pressure: `ssh macstudio "memory_pressure"`
- Reduce `context` limit in config if model runs out of memory

### Context limit errors

- Qwen3-Coder-Next-4bit supports up to 32K context but large contexts use more memory
- Client context is set to 16K by default (conservative for stability)
- Increase `limit.context` in config up to 32000 if you need more but monitor memory

### Server reliability

mlx-lm is installed via Homebrew on the Mac Studio (`brew install mlx-lm`). Server settings balance context size and memory safety:
- `--prompt-cache-size 2` — max 2 concurrent KV caches
- `--prompt-cache-bytes 17179869184` — max 16GB KV cache per slot (~170K tokens)
- `--max-tokens 8192` — default output cap per request

A health-check cron runs every 5 minutes on the Mac Studio (`~/llm-server/healthcheck.sh`).
It auto-restarts the server if it becomes unresponsive. Logs: `~/llm-server/logs/healthcheck.log`

Upgrade with: `ssh macstudio "/opt/homebrew/bin/brew upgrade mlx-lm"`

## Changing the Model

1. Load the new model on Mac Studio (see `summary.md` "Changing the LLM Model")
2. Update `opencode.json`:
   - Change model ID in `models` key and in `model`/`small_model` fields
   - Adjust `context` and `output` limits for the new model
3. Restart OpenCode

## Comparison with Claude Code Setup

| | Claude Code | OpenCode |
|---|---|---|
| API format | Anthropic (needs proxy) | OpenAI (direct) |
| Proxy needed | Yes (claude-code-proxy) | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` |
| Launch command | `claude-local` | `opencode` / `oc` |
