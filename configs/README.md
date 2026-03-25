# Client Configs

**Last updated: 2026-03-25**

Client config files for connecting to the Mac Studio M3 Ultra. Organized by server type. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` with the real IP.

## Server Roles

| Server | Port | Role | Model(s) | API Key |
|--------|------|------|----------|---------|
| **vllm-mlx** | 8000 | **Primary** -- fastest inference, single model | Qwen3-Coder-Next 6-bit (~60GB) | Not needed |
| **oMLX** | 8000 | **Multi-model** -- SSD cache, hot-swap, admin dashboard | 9 models (see below) | Required (`<YOUR_API_KEY>`) |

Only one server runs at a time on port 8000. vllm-mlx is the default for daily coding; switch to oMLX when you need model variety or the admin dashboard.

### Why vllm-mlx is Primary

Benchmarked on Qwen3-Coder-Next 6-bit (dense 60GB model):

| Context | vllm-mlx | oMLX | vllm-mlx advantage |
|---------|----------|------|--------------------|
| 512 | 68.8 t/s | 66.5 t/s | +3% |
| 8K | 63.8 t/s | 56.9 t/s | +12% |
| 32K | 56.4 t/s | 40.4 t/s | **+40%** |
| 64K | 51.7 t/s | 34.8 t/s | **+49%** |

The speed gap widens significantly at longer contexts -- exactly where coding agents operate.

## Config Files

### `vllm-mlx/` -- Primary Server (Single Model)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Model:** `mlx-community/Qwen3-Coder-Next-6bit` -- 60GB dense, 131K context, 51-69 tok/s generation. Uses `--served-model-name` so clients see the clean HuggingFace-style model ID.

### `omlx/` -- Multi-Model Server (SSD Cache)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**9 models available:**

| Model | Quant | Size | Context | Best For |
|-------|-------|------|---------|----------|
| Qwen3-Coder-Next | 6-bit | ~60GB | 131K | Daily driver (coding) |
| Qwen3.5-27B Opus Distilled | qx64-hi | ~19GB | 128K | Reasoning |
| Qwen3.5-122B-A10B | 4-bit | ~65GB | 128K | Agentic reasoning |
| Qwen3.5-122B-A10B JANG 2S | [JANG](https://jangq.ai/) 2-bit | ~35GB | 200K+ | Compact 122B |
| OmniCoder-9B | 8-bit | ~9.5GB | 262K | Coding agent |
| Nemotron 3 Nano 30B-A3B | 8-bit | ~34GB | 262K | NVIDIA MoE |
| Nemotron 3 Super 120B-A12B | 4.5-bit | ~66.5GB | 200K | Large MoE |
| Nemotron Cascade 2 30B-A3B | nvfp4 | ~17GB | 32K | Mamba-2 hybrid |
| Qwen3.5-35B-A3B JANG 4K | [JANG](https://jangq.ai/) 4-bit | ~19GB | 262K | Mixed-precision MoE |

Requires API key (`<YOUR_API_KEY>`). oMLX uses SSD-backed KV cache and supports hot-swapping between models via the admin dashboard at `http://<MAC_STUDIO_IP>:8000/admin`.

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
