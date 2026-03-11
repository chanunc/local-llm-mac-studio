# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Configuration and documentation for running a local LLM server on a Mac Studio M3 Ultra (96GB) and connecting multiple machines and coding agents via LAN. This is a docs-only repo — no code to build, lint, or test.

**Data flow**: Claude Code → claude-code-router (:3456, Anthropic format) → mlx-lm (:8080, OpenAI format). Other tools (OpenCode, Pi, OpenClaw) connect directly to mlx-lm on :8080.

## Architecture

```
MacBook (this machine)                    Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Claude Code         │                   │ mlx-lm server (port 8080)       │
│   claude-local      │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   ANTHROPIC_BASE_URL│                   │   OpenAI API format             │
│   = :3456           │                   │                                 │
│ OpenCode, Pi        │───── LAN ────────>│ claude-code-router (port 3456)  │
│   (direct to 8080)  │                   │   Anthropic API → OpenAI API    │
└─────────────────────┘                   └──────────────────────────────────┘
Linux (<LINUX_CLIENT_IP>)
┌─────────────────────┐
│ OpenClaw            │───── LAN ────────> (connects to 8080 directly)
└─────────────────────┘
```

- **Mac Studio** (`<MAC_STUDIO_IP>`, SSH alias `macstudio`): runs mlx-lm server (port 8080) and claude-code-router (port 3456)
- **MacBook** (this machine): runs Claude Code, OpenCode, and Pi — connects via LAN
- **Linux** (`<LINUX_CLIENT_IP>`, SSH alias `narutaki`): runs OpenClaw — connects via LAN
- **Model**: `mlx-community/Qwen3-Coder-Next-4bit` (~42GB) served via MLX on Apple Silicon
- **Proxy**: `claude-code-router` (musistudio) translates Anthropic API → OpenAI API format (needed only by Claude Code; other tools connect directly to mlx-lm)

## Docs

| File | Purpose |
|------|---------|
| `summary.md` | Full setup documentation, testing, and maintenance |
| `new-client-machine-setup.md` | Connect a new machine to the Mac Studio LLM |
| `opencode-setup.md` | OpenCode (MacBook) → Mac Studio |
| `openclaw-setup.md` | OpenClaw (Linux) → Mac Studio |
| `pi-setup.md` | Pi Coding Agent (MacBook) → Mac Studio |

## Config Files (`configs/`)

Ready-to-use config files for setting up new machines. Copy to the appropriate location.

| File | Copy to | Used by |
|------|---------|---------|
| `configs/claude-code-macstudio-settings.json` | `~/.claude/macstudio-settings.json` | Claude Code |
| `configs/opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `configs/pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `configs/openclaw-macstudio-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |
| `configs/claude-code-router.json` | `~/.claude-code-router/config.json` | Mac Studio server |

## Key Files

| Location | File | Purpose |
|----------|------|---------|
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code env config for local model |
| MacBook | `~/.config/opencode/opencode.json` | OpenCode config |
| MacBook | `~/.pi/agent/models.json` | Pi Coding Agent config |
| MacBook | `~/.ssh/config` | SSH aliases (`macstudio`, `narutaki`) |
| Linux | `~/.openclaw/openclaw.json` | OpenClaw config with `macstudio` provider |
| Mac Studio | `~/llm-server/` | Server dir (logs, healthcheck) |
| Mac Studio | `~/.claude-code-router/config.json` | Router config (providers, routing) |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist` | mlx-lm launchd service |
| Mac Studio | `~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist` | Router launchd service |

## Common Commands

```bash
# Use local LLM via Claude Code
claude-local

# SSH to machines
ssh macstudio
ssh narutaki

# Quick health check (mlx-lm)
curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool

# Health check (router — Anthropic format)
curl -s http://<MAC_STUDIO_IP>:3456/v1/messages \
  -H "Content-Type: application/json" -H "x-api-key: not-needed" -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool

# Memory pressure on Mac Studio
ssh macstudio "memory_pressure | head -20"

# Restart services on Mac Studio
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist"

# Check logs
ssh macstudio "tail -20 ~/llm-server/logs/mlx-lm-server.err"
ssh macstudio "tail -20 ~/llm-server/logs/claude-code-proxy.err"

# Upgrade all tools
brew upgrade claude-code opencode pi-coding-agent
ssh macstudio "/opt/homebrew/bin/brew upgrade mlx-lm claude-code-router"
ssh narutaki "openclaw update"
```

## Known Issues

- **SSH timeouts**: Fixed — was caused by macOS sleeping after 1 min idle. Fix applied: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10`. If SSH flakiness returns, verify with `ssh macstudio "pmset -g | grep sleep"`.
- **Model changes**: See "Changing the LLM Model" section in `summary.md` for step-by-step instructions.
