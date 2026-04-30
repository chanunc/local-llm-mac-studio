# Qwen Code Setup: MacBook / WSL / Linux → Mac Studio LLM Server

[Qwen Code](https://github.com/QwenLM/qwen-code) is an open-source terminal AI agent by the Qwen team, tuned for Qwen models. It speaks OpenAI-compatible protocols natively, so it connects **directly** to any of the Mac Studio servers on port 8000 with a pointer in `~/.qwen/settings.json` — no proxy needed.

This guide defaults to **Qwen3.5-35B-A3B JANG 4K**, the model currently loaded on the Mac Studio (`~/mlx-openai-server-multimodel.yaml`).

## Index
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Per-server templates](#per-server-templates)
  - [Environment variables](#environment-variables)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Changing the Model](#changing-the-model)

## 🏗️ Architecture

```
MacBook / Linux / WSL                     Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Qwen Code           │                   │ mlx-openai-server (port 8000)   │
│   OpenAI-compatible │───── LAN ────────>│   Qwen3.5-35B-A3B JANG 4K       │
│   direct connection │                   │   /v1/chat/completions          │
└─────────────────────┘                   └──────────────────────────────────┘
```

Same wire protocol as OpenCode. Qwen Code works against all four servers in this repo (vllm-mlx, mlx-openai-server, oMLX, vmlx) — pick the one currently running and its matching template under `configs/clients/<server>/qwen-code-settings.json`.

## ⚙️ Installation

```bash
# macOS / Linux (npm)
npm install -g @qwen-code/qwen-code@latest

# or the bundled installer
bash -c "$(curl -fsSL https://qwen-code-assets.oss-cn-hangzhou.aliyuncs.com/installation/install-qwen.sh)"
```

Verify: `qwen --version`

## 🧩 Configuration

Qwen Code reads user-level settings from `~/.qwen/settings.json`. The repo ships a ready-to-copy template per server:

```bash
mkdir -p ~/.qwen

# mlx-openai-server (JANG 4K currently loaded)
cp configs/clients/mlx-openai-server/qwen-code-settings.json ~/.qwen/settings.json

# or for the other servers
cp configs/clients/vllm-mlx/qwen-code-settings.json    ~/.qwen/settings.json
cp configs/clients/omlx/qwen-code-settings.json        ~/.qwen/settings.json
```

Then replace the `<MAC_STUDIO_IP>` placeholder with the Mac Studio's LAN IP (or Tailscale address) and, for oMLX, replace `<YOUR_API_KEY>` with the real oMLX API key — or export it as `MACSTUDIO_API_KEY` in your shell (env wins over `settings.json`).

Minimal shape the templates follow:

```json
{
  "modelProviders": {
    "openai": [
      {
        "id": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K",
        "name": "Qwen3.5-35B-A3B JANG 4-bit (Mac Studio)",
        "baseUrl": "http://<MAC_STUDIO_IP>:8000/v1",
        "envKey": "MACSTUDIO_API_KEY"
      }
    ]
  },
  "env": { "MACSTUDIO_API_KEY": "not-needed" },
  "security": { "auth": { "selectedType": "openai" } },
  "model": { "name": "JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K" }
}
```

### Per-server templates

| Template | Server | Default model | Auth |
|:---------|:-------|:--------------|:-----|
| `configs/clients/mlx-openai-server/qwen-code-settings.json` | mlx-openai-server | `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` | none (`not-needed`) |
| `configs/clients/vllm-mlx/qwen-code-settings.json` | vllm-mlx | `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` | none (`not-needed`) |
| `configs/clients/omlx/qwen-code-settings.json` | oMLX | `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` | `<YOUR_API_KEY>` |

### Environment variables

Qwen Code resolves API keys from the env var named in `envKey`. Exported shell vars override `settings.json → env`:

```bash
export MACSTUDIO_API_KEY='not-needed'   # mlx-openai-server / vllm-mlx
export MACSTUDIO_API_KEY='<YOUR_API_KEY>'   # oMLX
```

## 🧪 Testing

1. **Connectivity** — confirm the target server is up:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool
   # oMLX only:
   curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
     -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool
   ```

2. **Interactive** — launch the TUI and send a prompt:
   ```bash
   qwen
   ```

3. **One-shot**:
   ```bash
   qwen -p "Write a Python hello world"
   ```

4. **Tool use** — create a test file, then ask Qwen Code to read it.

## ⚠️ Troubleshooting

- **`invalid auth type`** — `security.auth.selectedType` must be `"openai"` for OpenAI-compatible endpoints.
- **`model not found`** — the `id` field in `modelProviders.openai[].id` must match an entry in `GET /v1/models`. For vllm-mlx the model name comes from `--served-model-name`; for mlx-openai-server / oMLX it's the HF-style ID in the YAML / model settings.
- **Connection refused** — confirm the server is running (`tail -f /tmp/mlx-openai-server.log` on the Mac Studio) and that only one server holds port 8000 (see README "Start a Server").
- **401 on oMLX** — the API key must be set via `envKey` / `MACSTUDIO_API_KEY`; the `apiKey` field in opencode-style configs does not apply here.
- **Long generations time out** — Qwen Code inherits standard HTTP timeouts from `fetch`. If you need longer, either reduce the prompt or switch to a thinner server (mlx-openai-server / vllm-mlx) where throughput is higher.

## 🔁 Changing the Model

1. Load the target model on the Mac Studio server (see the matching `docs/servers/<server>/summary.md`).
2. Update `~/.qwen/settings.json`:
   - Add or edit an entry in `modelProviders.openai[]` with the new `id`.
   - Point `model.name` at that `id`.
3. Restart the Qwen Code session.

Qwen Code does not need restart to see a changed `baseUrl`, but the `model.name` is read at session start.
