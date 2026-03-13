# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Index
- [Project](#project)
- [Architecture](#architecture)
- [Docs](#docs)
- [Config Files](#config-files-configs)
- [Key Files](#key-files)
- [Common Commands](#common-commands)
- [Known Issues](#known-issues)

## Project

Configuration and documentation for running a local LLM server on a Mac Studio M3 Ultra (96GB) and connecting multiple machines and coding agents via LAN. This is a docs-only repo — no code to build, lint, or test.

**Data flow**: All tools (Claude Code, OpenCode, Pi, OpenClaw) connect directly to oMLX (:8000), which natively serves both OpenAI and Anthropic API formats.

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
Linux (<LINUX_CLIENT_IP>)
┌─────────────────────┐
│ OpenClaw            │───── LAN ────────> (connects to 8000 directly)
└─────────────────────┘
WSL Linux (192.168.31.x via eth2)
┌─────────────────────┐
│ OpenCode            │───── LAN ────────> (connects to 8000 directly)
└─────────────────────┘
```

- **Mac Studio** (`<MAC_STUDIO_IP>`, SSH alias `macstudio`): runs oMLX server (port 8000) — serves both OpenAI and Anthropic API formats natively
- **MacBook** (this machine): runs Claude Code, OpenCode, and Pi — connects via LAN
- **Linux** (`<LINUX_CLIENT_IP>`, SSH alias `narutaki`): runs OpenClaw — connects via LAN
- **WSL Linux** (`192.168.31.x` via `eth2`): runs OpenCode — requires `ip route add` for LAN routing (see `docs/clients/opencode-setup.md`)
- **Model**: `mlx-community/Qwen3-Coder-Next-4bit` (~42GB) served via oMLX on Apple Silicon
- **Server**: oMLX natively speaks both OpenAI and Anthropic API formats — no proxy needed for any tool

## Docs

| File | Purpose |
|------|---------|
| `docs/server/omlx-summary.md` | Full setup documentation, testing, and maintenance (oMLX) |
| `docs/server/omlx-maintenance.md` | Advanced troubleshooting, discovery fixes, and hard restarts |
| `docs/server/mlxlm-summary.md` | Alternative: native mlx-lm + claude-code-router setup |
| `docs/clients/new-client-machine-setup.md` | Connect a new machine to the Mac Studio LLM |
| `docs/clients/opencode-setup.md` | OpenCode (MacBook / WSL) → Mac Studio |
| `docs/clients/openclaw-setup.md` | OpenClaw (Linux) → Mac Studio |
| `docs/clients/pi-setup.md` | Pi Coding Agent (MacBook) → Mac Studio |

## Config Files (`configs/`)

Ready-to-use config files for setting up new machines. Copy to the appropriate location.

| File | Copy to | Used by |
|------|---------|---------|
| `configs/claude-code-macstudio-settings.json` | `~/.claude/macstudio-settings.json` | Claude Code |
| `configs/opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `configs/pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `configs/openclaw-macstudio-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |
| `configs/claude-code-router.json.archived` | N/A | Archived: old router config |

## Key Files

| Location | File | Purpose |
|----------|------|---------|
| MacBook | `~/.claude/macstudio-settings.json` | Claude Code env config for local model |
| MacBook | `~/.config/opencode/opencode.json` | OpenCode config |
| MacBook | `~/.pi/agent/models.json` | Pi Coding Agent config |
| MacBook | `~/.ssh/config` | SSH aliases (`macstudio`, `narutaki`) |
| Linux | `~/.openclaw/openclaw.json` | OpenClaw config with `macstudio` provider |
| Mac Studio | `~/.omlx/` | oMLX config, models, logs, and cache |

## Common Commands

```bash
# Use local LLM via Claude Code
claude-local

# SSH to machines
ssh macstudio
ssh narutaki

# Quick health check (OpenAI format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool

# Health check (Anthropic format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" -H "x-api-key: <YOUR_API_KEY>" -H "anthropic-version: 2023-06-01" \
  -d '{"model":"mlx-community/Qwen3-Coder-Next-4bit","max_tokens":10,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool

# Memory pressure on Mac Studio
ssh macstudio "memory_pressure | head -20"

# Restart oMLX on Mac Studio
ssh macstudio "brew services restart omlx"

# Check logs
ssh macstudio "tail -20 /opt/homebrew/var/log/omlx.log"
ssh macstudio "tail -20 ~/.omlx/logs/server.log"

# Service status
ssh macstudio "brew services info omlx"

# Admin panel: http://<MAC_STUDIO_IP>:8000/admin

# Upgrade all tools
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent
ssh macstudio "/opt/homebrew/bin/brew upgrade omlx"
ssh narutaki "openclaw update"
```

## Known Issues

- **SSH timeouts**: Fixed — was caused by macOS sleeping after 1 min idle. Fix applied: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10`. If SSH flakiness returns, verify with `ssh macstudio "pmset -g | grep sleep"`.
- **Model changes**: See "Changing the LLM Model" section in `docs/server/omlx-summary.md` for step-by-step instructions.
