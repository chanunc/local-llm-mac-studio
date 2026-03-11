# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Configuration and documentation for running a local LLM server on a Mac Studio M3 Ultra (96GB) and connecting multiple machines and coding agents via LAN.

## Architecture

- **Mac Studio** (`<MAC_STUDIO_IP>`, SSH alias `macstudio`): runs mlx-lm server (port 8080) and claude-code-proxy (port 4000)
- **MacBook** (this machine): runs Claude Code, OpenCode, and Pi — connects via LAN
- **Linux** (`<LINUX_CLIENT_IP>`, SSH alias `narutaki`): runs OpenClaw — connects via LAN
- **Model**: `mlx-community/Qwen3-Coder-Next-4bit` (~42GB) served via MLX on Apple Silicon
- **Proxy**: `claude-code-proxy` (fuergaosi233) translates Anthropic API → OpenAI API format (needed only by Claude Code; other tools connect directly to mlx-lm)

## Docs

| File | Purpose |
|------|---------|
| `summary.md` | Full setup documentation, testing, and maintenance |
| `new-machine-setup.md` | Connect a new machine to the Mac Studio LLM |
| `opencode-setup.md` | OpenCode (MacBook) → Mac Studio |
| `openclaw-setup.md` | OpenClaw (Linux) → Mac Studio |
| `pi-setup.md` | Pi Coding Agent (MacBook) → Mac Studio |

## Key Files

| Location | File | Purpose |
|----------|------|---------|
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code env config for local model |
| MacBook | `~/.config/opencode/opencode.json` | OpenCode config |
| MacBook | `~/.pi/agent/models.json` | Pi Coding Agent config |
| MacBook | `~/.ssh/config` | SSH aliases (`macstudio`, `narutaki`) |
| Linux | `~/.openclaw/openclaw.json` | OpenClaw config with `macstudio` provider |
| Mac Studio | `~/llm-server/` | Server project dir (venv, .env, logs) |
| Mac Studio | `~/llm-server/.env` | Proxy config (BIG_MODEL, SMALL_MODEL, OPENAI_API_BASE) |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist` | mlx-lm launchd service |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist` | Proxy launchd service |

## Common Commands

```bash
# Use local LLM via Claude Code
claude-local

# SSH to machines
ssh macstudio
ssh narutaki

# Quick health check
curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool

# Restart services on Mac Studio
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist"

# Check logs
ssh macstudio "tail -20 ~/llm-server/logs/mlx-lm-server.err"
ssh macstudio "tail -20 ~/llm-server/logs/claude-code-proxy.err"

# Upgrade all tools
brew upgrade claude-code opencode pi-coding-agent
ssh macstudio "~/llm-server/venv/bin/pip install --upgrade claude-code-proxy mlx-lm"
ssh narutaki "openclaw update"
```

## Known Issues

- **SSH timeouts**: Fixed — was caused by macOS sleeping after 1 min idle. Fix applied: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10`. If SSH flakiness returns, verify with `ssh macstudio "pmset -g | grep sleep"`.
- **Proxy tool_use patch**: `server/fastapi.py` in site-packages has `is_claude_model = True` patch. This is lost on `pip install --upgrade claude-code-proxy` — reapply with:
  ```bash
  ssh macstudio "SITE=~/llm-server/venv/lib/python3.12/site-packages/server && sed -i '' 's/is_claude_model = clean_model.startswith(\"claude-\")/is_claude_model = True/' \$SITE/fastapi.py"
  ```
- **Model changes**: See "Changing the LLM Model" section in `summary.md` for step-by-step instructions.
