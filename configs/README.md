# Client Configs

**Last updated: 2026-04-30**

Client config files for connecting to the Mac Studio M3 Ultra. Templates now live under `configs/client/`, organized by server type. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` with the real IP.

## 🖥️ Server Roles

| Server | Port | Role | Model(s) | API Key |
|--------|------|------|----------|---------|
| **vllm-mlx** | 8000 | **Primary** -- fastest inference, single model | Ling-2.6-flash mlx-6bit (~80GB, current production) | Not needed |
| **mlx-openai-server** | 8000 | **OpenAI server** -- process isolation, prompt cache, speculative decoding | Superset config (see below) | Not needed |
| **oMLX** | 8000 | **Multi-model** -- SSD cache, hot-swap, admin dashboard | 9 models (see below) | Required (`<YOUR_API_KEY>`) |
| **vmlx** | 8000 | **JANGTQ** -- only route for TurboQuant-weight (JANGTQ) CRACK models; runs out of MLX Studio bundled Python | MiniMax-M2.7-JANGTQ-CRACK (~57GB) | Not needed |
| **llmster** | **1234** | **LM Studio headless** -- standard MLX/GGUF only; closed-source runtime; **3-5× faster agent loops** than vllm-mlx for non-JANG models | Qwen3.6-27B-6bit (~22GB) | Not needed |

Only one server can occupy port 8000 at a time (vllm-mlx, mlx-openai-server, oMLX, vmlx). **llmster runs on a separate port (1234)** so it can technically run alongside one of the others, but in practice memory pressure on a 96 GB M3 Ultra means stopping the port-8000 server before loading a model into llmster. vllm-mlx + Ling is the production default; switch to mlx-openai-server for multi-model with low overhead, oMLX when you need the full 9-model roster + admin dashboard, vmlx when you need an uncensored JANGTQ model (the loader + Metal kernels ship only inside the MLX Studio DMG's bundled Python — see [`docs/models/model-summary.md`](../docs/models/model-summary.md#unblocking-path--corrected--deployed-2026-04-20)), or llmster when you need the fastest possible agent loop on a standard MLX model.

### Why vllm-mlx is Primary

Benchmarked on Qwen3-Coder-Next 6-bit (dense 60GB model):

| Context | vllm-mlx | oMLX | vllm-mlx advantage |
|---------|----------|------|--------------------|
| 512 | 68.8 t/s | 66.5 t/s | +3% |
| 8K | 63.8 t/s | 56.9 t/s | +12% |
| 32K | 56.4 t/s | 40.4 t/s | **+40%** |
| 64K | 51.7 t/s | 34.8 t/s | **+49%** |

The speed gap widens significantly at longer contexts -- exactly where coding agents operate.

## 🧩 Config Files

### `client/vllm-mlx/` -- Primary Server (Single Model)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Model:** `mlx-community/Ling-2.6-flash-mlx-6bit` -- [bailing_hybrid](../docs/models/model-summary-ling.md) MoE, 6-bit MLX uniform, ~80GB on disk, 64K practical context (128K OOMs), 104B total / 7.4B active. Launched via standard `~/vllm-mlx-env/bin/vllm-mlx serve` (no JANG wrapper) with `--enable-auto-tool-choice --tool-call-parser hermes`. Requires three local patches (PR #1227 vendor + threadlocal-stream + inline-gen) — see [`model-summary-ling.md`](../docs/models/model-summary-ling.md) for the full deploy recipe. Older primaries: `JANGQ-AI/Qwen3.6-27B-JANG_4M` (dense+VL fallback, 17.5GB) and `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S` (122B/10B MoE, 35GB) — both still available via `run_vllm_jang.py` wrapper.

### `client/mlx-openai-server/` -- Multi-Model Server (Process Isolation)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code (OpenAI mode) |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Superset model list for clients:**

| Model | Quant | Size | Context | Best For |
|-------|-------|------|---------|----------|
| Qwen3-Coder-Next | 6-bit | ~60GB | 170K | Daily driver (coding) |
| Qwen3-Coder-30B-A3B Instruct | 4-bit | ~16GB | 262K | Compact coding model |
| Qwen3.5-27B Opus Distilled | qx64-hi | ~19GB | 128K | Reasoning |
| Qwen3.5-122B-A10B | 4-bit | ~65GB | 128K | Agentic reasoning |
| Qwen3.5-122B-A10B JANG 2S | [JANG](https://jangq.ai/) 2-bit | ~35GB | 200K | Compact 122B |
| OmniCoder-9B | 8-bit | ~9.5GB | 262K | Coding agent |
| Qwen3.5-35B-A3B JANG 4K | [JANG](https://jangq.ai/) 4-bit | ~19GB | 262K | Mixed-precision MoE |
| Qwen3.6-35B-A3B | 6-bit | ~27GB | 262K (1M YaRN) | Hybrid MoE + vision, thinking |

No API key needed. OpenAI-compatible API only (no Anthropic-format API). Claude Code requires OpenAI-compatible provider mode. Features: trie-based prompt caching, Qwen3.5 reasoning parser, speculative decoding support.

These `mlx-openai-server` client configs intentionally list a stable superset of commonly used **compatible** model IDs so the files do not need updating every time the live YAML changes. The actual server may expose only a subset at any given time; check `/v1/models` to see what is currently loaded.

Excluded from this superset:
- Nemotron family — currently incompatible on `mlx-openai-server`
- Mistral Small 4 — currently unsupported on `mlx-openai-server`

### `client/omlx/` -- Multi-Model Server (SSD Cache)

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

### `client/vmlx/` -- JANGTQ Server (Uncensored CRACK)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Model:** `dealignai/MiniMax-M2.7-JANGTQ-CRACK` -- MiniMax-M2.7 MoE (230B total / ~10B active / 256 experts), JANGTQ quant (2-bit TurboQuant codebook + 8-bit attention/embeddings, Hadamard rotation, Metal-fused dequant+matmul), CRACK-abliterated for uncensored use. ~57 GB on disk. Educational / experimental -- see [`docs/models/uncen-model/minimax-m27-crack-benchmark.md`](../docs/models/uncen-model/minimax-m27-crack-benchmark.md) for the deploy + perf report.

Speaks OpenAI + Anthropic + Ollama API on port 8000. No API key required. Runs out of the MLX Studio DMG's bundled Python (`/Applications/vMLX.app/Contents/Resources/bundled-python/python/`) because the TurboQuant loader (`jang_tools.load_jangtq`) and Metal kernels (`turboquant/{tq_kernel,hadamard_kernel,gather_tq_kernel,fused_gate_up_kernel}`) are not distributed via the public pypi `jang` or `vmlx` wheels ([`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5) tracks this).

**Not compatible with**: `--smelt` or `--flash-moe` flags ([`vmlx#81`](https://github.com/jjang-ai/vmlx/issues/81) -- both raise `ValueError` on `weight_format=mxtq`). Use the bundled `python3 -m vmlx_engine.cli serve` invocation only; the bundled `bin/vmlx` shebang points at the maintainer's build tree.

### `client/llmster/` -- LM Studio Headless (Standard MLX, Port 1234)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Model:** `qwen3.6-27b` (LM Studio mangles `mlx-community/Qwen3.6-27B-6bit` → lowercases + strips org prefix at load time — verify with `/v1/models`). Standard MLX 6-bit safetensors, ~22 GB on disk under `~/.lmstudio/models/`. **Currently OpenCode-only** — Claude Code, OpenClaw, Pi, qwen-code config files have not been added because llmster's role is provisional (3-5× faster agent loops than vllm-mlx on non-JANG models, but closed-source runtime and no JANG/JANGTQ/`bailing_hybrid` support).

Speaks **OpenAI-compatible** API on port **1234** (NOT 8000). No API key required. Default `lms server start` binds to `127.0.0.1`; LAN clients require `--bind 0.0.0.0`. Tool calling and `<think>` reasoning parsing are built into the MLX runtime — no parser flags needed. Full server runbook: [`docs/server/llmster/summary.md`](../docs/server/llmster/summary.md).

## 🔀 Switching Servers

```bash
# Switch to mlx-openai-server (multi-model, low overhead)
pkill -f vllm-mlx; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2
nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml \
  --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &

# Switch to oMLX (multi-model, 9 models)
pkill -f mlx-openai-server; pkill -f vllm-mlx; pkill -f vmlx_engine; sleep 2
/opt/homebrew/bin/brew services start omlx

# Switch to vllm-mlx (current production primary: Ling-2.6-flash mlx-6bit)
pkill -f mlx-openai-server; pkill -f vmlx_engine; pkill -f lm-studio; /opt/homebrew/bin/brew services stop omlx; sleep 2
nohup ~/vllm-mlx-env/bin/vllm-mlx serve \
  ~/.cache/huggingface/hub/models--mlx-community--Ling-2.6-flash-mlx-6bit/snapshots/df79bba4bc9d3ea919afd7e017d8d262b0bbc995 \
  --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > /tmp/vllm-mlx.log 2>&1 &

# Switch to vmlx (JANGTQ CRACK — bundled-Python headless)
pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 > /tmp/vmlx.log 2>&1 &

# Switch to llmster (LM Studio headless, port 1234 — separate from port 8000)
# First-time setup: brew install --cask lm-studio + one GUI launch to bootstrap ~/.lmstudio/bin/lms
pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2
~/.lmstudio/bin/lms load qwen3.6-27b --gpu max --context-length 65536 -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors
```
