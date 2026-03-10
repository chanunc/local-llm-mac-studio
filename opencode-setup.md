# OpenCode Setup: MacBook → Mac Studio LLM Server

OpenCode connects **directly** to the mlx-lm server's OpenAI-compatible endpoint — no proxy needed.

## Architecture

```
MacBook                                   Mac Studio M3 Ultra (192.168.1.181)
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

Global config at `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "macstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://192.168.1.181:8080/v1",
        "apiKey": "not-needed",
        "timeout": 600000
      },
      "models": {
        "mlx-community/Qwen3-Coder-Next-4bit": {
          "name": "Qwen3 Coder (Mac Studio)",
          "limit": {
            "context": 32000,
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
   curl -s http://192.168.1.181:8080/v1/models | python3 -m json.tool
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

- Verify the server is running: `curl http://192.168.1.181:8080/v1/models`
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
- Reduce `limit.context` in config if you hit OOM errors

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
