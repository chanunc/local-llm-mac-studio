# Client Configs

**Last updated: 2026-03-25**

Client config files for connecting to the Mac Studio M3 Ultra. Organized by server type. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` with the real IP.

## Server Roles

| Server | Port | Role | Model | API Key |
|--------|------|------|-------|---------|
| **vllm-mlx** | 8000 | **Primary** — fastest inference, single model | Qwen3-Coder-Next 6-bit | Not needed |
| **oMLX** | 8000 | **Multi-model** — SSD cache, hot-swap, admin dashboard | 9 models (see below) | Required |

Only one server runs at a time on port 8000. vllm-mlx is the default for daily coding; switch to oMLX when you need model variety or the admin dashboard.

## Config Files

### `vllm-mlx/` — Primary Server (Single Model)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Model:** `mlx-community/Qwen3-Coder-Next-6bit` — 60GB dense, 131K context, 51-69 tok/s generation.

### `omlx/` — Multi-Model Server (SSD Cache)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Models:** Qwen3-Coder-Next, Qwen3.5-122B, Qwen3.5-27B Opus Distilled, OmniCoder-9B, Nemotron Nano/Super/Cascade, JANG variants. Requires API key (`<YOUR_API_KEY>`).

## Switching Servers

```bash
# Switch to oMLX (multi-model)
ssh macstudio "pkill -f vllm-mlx; sleep 2; /opt/homebrew/bin/brew services start omlx"

# Switch to vllm-mlx (primary, fastest)
ssh macstudio "/opt/homebrew/bin/brew services stop omlx; sleep 2"
ssh macstudio "nohup ~/vllm-mlx-env/bin/vllm-mlx serve \
  ~/.omlx/models/mlx-community--Qwen3-Coder-Next-6bit \
  --served-model-name mlx-community/Qwen3-Coder-Next-6bit \
  --port 8000 --host 0.0.0.0 > /tmp/vllm-mlx.log 2>&1 &"
```
