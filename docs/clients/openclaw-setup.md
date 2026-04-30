# OpenClaw Setup: Linux Machine → Mac Studio LLM Server

OpenClaw on the Linux machine connects **directly** to the oMLX server's OpenAI-compatible API endpoint.

## Index
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [SSH Config (MacBook)](#ssh-config-macbook)
- [OpenClaw Configuration](#openclaw-configuration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
  - [Can't connect to Mac Studio from Linux](#cant-connect-to-mac-studio-from-linux)
  - [API format issues](#api-format-issues)
  - [Tool calling quality](#tool-calling-quality)
- [Comparison with Other Setups](#comparison-with-other-setups)

## 🏗️ Architecture

```
Linux (narutaki@<LINUX_CLIENT_IP>)          Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────────┐              ┌──────────────────────────────────┐
│ OpenClaw                │              │ oMLX server (port 8000)         │
│   openai-completions    │──── LAN ────>│   Qwen3-Coder-Next-4bit         │
│   direct connection     │              │   /v1/chat/completions          │
└─────────────────────────┘              └──────────────────────────────────┘
```

## ✅ Prerequisites

- SSH access from MacBook: `ssh narutaki` (config in `~/.ssh/config`)
- Mac Studio oMLX server running on port 8000

## 🔑 SSH Config (MacBook)

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

## 🧩 OpenClaw Configuration

Config file: `~/.openclaw/openclaw.json` on the Linux machine.

The Mac Studio provider config is available at `configs/clients/omlx/openclaw-provider.json` in this repo. It was added to the existing `models.providers` section (merged alongside DeepSeek and Kimi providers):

```json
{
  "macstudio": {
    "baseUrl": "http://<MAC_STUDIO_IP>:8000/v1",
    "apiKey": "<YOUR_API_KEY>",
    "api": "openai-completions",
    "models": [
      {
        "id": "mlx-community/Qwen3-Coder-Next-4bit",
        "name": "Qwen3 Coder 4-bit (Fast)",
        "reasoning": false,
        "input": ["text"],
        "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
        "contextWindow": 170000,
        "maxTokens": 8192
      },
      {
        "id": "mlx-community/Qwen3-Coder-Next-6bit",
        "name": "Qwen3 Coder 6-bit (Balanced)",
        "reasoning": false,
        "input": ["text"],
        "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
        "contextWindow": 170000,
        "maxTokens": 8192
      },
      {
        "id": "mlx-community/Qwen3-Coder-Next-8bit",
        "name": "Qwen3 Coder 8-bit (Precision)",
        "reasoning": false,
        "input": ["text"],
        "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
        "contextWindow": 32000,
        "maxTokens": 8192
      },
      {
        "id": "mlx-community/Qwen3.5-122B-A10B-4bit",
        "name": "Qwen 3.5 122B (Agentic)",
        "reasoning": true,
        "input": ["text"],
        "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
        "contextWindow": 128000,
        "maxTokens": 8192
      }
    ]
  }
}
```

Key decisions:
- `api: "openai-completions"` — oMLX uses Chat Completions format
- `baseUrl` includes `/v1` since oMLX expects it
- Cost is all zeros (local model, no API charges)
- Model alias: `qwen3-local` (use `/model qwen3-local` in OpenClaw)
- Added as first fallback in `agents.defaults.model.fallbacks`

## 🧪 Testing

1. **Connectivity from Linux**:
   ```bash
   ssh narutaki "curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H 'Authorization: Bearer <YOUR_API_KEY>'"
   ```

2. **Switch to Mac Studio models in OpenClaw**:
   Use the `/model` command to choose your preferred quantization:
   - `/model qwen3-4bit`
   - `/model qwen3-6bit`
   - `/model qwen3-8bit`
   - `/model qwen3.5-122b`
   
   *(Note: Ensure these aliases are configured in your OpenClaw model settings).*

3. **Test a simple prompt** to verify end-to-end flow.

## ⚠️ Troubleshooting

Additional client-specific notes:
- [OpenClaw Known Issues](openclaw-known-issues.md)

### Can't connect to Mac Studio from Linux

- Verify the server is running: `curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"`
- Restart oMLX:
  ```bash
  brew services restart omlx
  ```

You can also check model status via the oMLX admin panel at `http://<MAC_STUDIO_IP>:8000/admin`.

### API format issues

If `openai-completions` doesn't work, try changing to `openai-responses` in the config. oMLX may or may not support the newer Responses API format.

### Tool calling quality

Qwen3-Coder-Next-4bit may not handle OpenClaw's tool format perfectly. This is a known limitation of smaller quantized models.

## 🔍 Comparison with Other Setups

| | Claude Code (MacBook) | OpenCode (MacBook) | OpenClaw (Linux) |
|---|---|---|---|
| API format | Anthropic (native) | OpenAI (native) | OpenAI (native) |
| Proxy needed | No | No | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` | `~/.openclaw/openclaw.json` |
| Machine | MacBook | MacBook | Linux (<LINUX_CLIENT_IP>) |
