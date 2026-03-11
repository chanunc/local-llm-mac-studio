# OpenClaw Setup: Linux Machine → Mac Studio LLM Server

OpenClaw on the Linux machine connects **directly** to the mlx-lm server's OpenAI-compatible endpoint — no proxy needed.

## Architecture

```
Linux (narutaki@<LINUX_CLIENT_IP>)          Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────────┐              ┌──────────────────────────────────┐
│ OpenClaw                │              │ mlx-lm server (port 8080)       │
│   openai-completions    │──── LAN ────>│   Qwen3-Coder-Next-4bit         │
│   direct connection     │              │   /v1/chat/completions          │
└─────────────────────────┘              └──────────────────────────────────┘
```

## Prerequisites

- SSH access from MacBook: `ssh narutaki` (config in `~/.ssh/config`)
- Mac Studio mlx-lm server running on port 8080

## SSH Config (MacBook)

Entry in `~/.ssh/config`:

```
Host narutaki
    HostName <LINUX_CLIENT_IP>
    User narutaki
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

SSH key was copied with `ssh-copy-id` (or manual `authorized_keys` setup).

## OpenClaw Configuration

Config file: `~/.openclaw/openclaw.json` on the Linux machine.

The Mac Studio provider config is available at `configs/openclaw-macstudio-provider.json` in this repo. It was added to the existing `models.providers` section (merged alongside DeepSeek and Kimi providers):

```json
{
  "macstudio": {
    "baseUrl": "http://<MAC_STUDIO_IP>:8080/v1",
    "apiKey": "not-needed",
    "api": "openai-completions",
    "models": [
      {
        "id": "mlx-community/Qwen3-Coder-Next-4bit",
        "name": "Qwen3 Coder (Mac Studio)",
        "reasoning": false,
        "input": ["text"],
        "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
        "contextWindow": 170000,
        "maxTokens": 8192
      }
    ]
  }
}
```

Key decisions:
- `api: "openai-completions"` — mlx-lm uses Chat Completions format
- `baseUrl` includes `/v1` since mlx-lm expects it
- Cost is all zeros (local model, no API charges)
- Model alias: `qwen3-local` (use `/model qwen3-local` in OpenClaw)
- Added as first fallback in `agents.defaults.model.fallbacks`

## Testing

1. **Connectivity from Linux**:
   ```bash
   ssh narutaki "curl -s http://<MAC_STUDIO_IP>:8080/v1/models"
   ```

2. **Switch to Mac Studio model in OpenClaw**:
   Use `/model qwen3-local` or `/model macstudio/mlx-community/Qwen3-Coder-Next-4bit`

3. **Test a simple prompt** to verify end-to-end flow.

## Troubleshooting

### Can't connect to Mac Studio from Linux

- Verify the server is running: `curl http://<MAC_STUDIO_IP>:8080/v1/models`
- Check if mlx-lm is up: `ssh macstudio "launchctl list | grep mlx"`
- Restart mlx-lm:
  ```bash
  ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
  ```

### API format issues

If `openai-completions` doesn't work, try changing to `openai-responses` in the config. mlx-lm may or may not support the newer Responses API format.

### Tool calling quality

Qwen3-Coder-Next-4bit may not handle OpenClaw's tool format perfectly. This is a known limitation of smaller quantized models.

## Comparison with Other Setups

| | Claude Code (MacBook) | OpenCode (MacBook) | OpenClaw (Linux) |
|---|---|---|---|
| API format | Anthropic (needs proxy) | OpenAI (direct) | OpenAI (direct) |
| Proxy needed | Yes (claude-code-router) | No | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` | `~/.openclaw/openclaw.json` |
| Machine | MacBook | MacBook | Linux (<LINUX_CLIENT_IP>) |
