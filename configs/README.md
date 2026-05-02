# Client Configs

**Last updated: 2026-05-02 (llmster prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K deploy-and-benchmark — new active main)**

Client config files for connecting to the Mac Studio M3 Ultra. Templates live under [`configs/clients/`](clients/), organized by server type — see [`clients/README.md`](clients/README.md) for the per-server layout. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` with the real IP.

**Censored vs uncensored:** templates in this folder pin **censored / standard / instruction-tuned** models per server (Ling, Gemma, Osaurus JANGTQ4, Qwen3-Coder, etc.). The matching **uncensored** roster (HauhauCS abliterations, dealignai CRACK variants, NousResearch Hermes, Dolphin, magnum, Huihui, etc.) lives in [`docs/models/uncen-model/client-configs/`](../docs/models/uncen-model/client-configs/). Pick the folder that matches the model class you want to talk to. The **live Mac Studio state** is independent of which template you use — see [`../docs/current.md`](../docs/current.md) for what's actually running right now.

## 🖥️ Server Roles

| Server | Port | Role | Model(s) | API Key |
|--------|------|------|----------|---------|
| **vllm-mlx** | 8000 | Previous primary / fallback -- fastest inference, single model; currently stopped | Ling-2.6-flash mlx-6bit (~80GB) | Not needed |
| **mlx-openai-server** | 8000 | **OpenAI server** -- process isolation, prompt cache, speculative decoding; currently stopped | Superset config (see below) | Not needed |
| **oMLX** | 8000 | **Multi-model** -- SSD cache, hot-swap, admin dashboard; currently stopped | 9 models (see below) | Required (`<YOUR_API_KEY>`) |
| **vmlx** | 8000 | JANGTQ -- only route for TurboQuant-weight (JANGTQ) models; runs out of MLX Studio bundled Python; **currently stopped** (was last main 2026-05-01 with Osaurus JANGTQ4) | OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 (~19.7GB) | Not needed |
| **llmster** | **1234** | **Current main (2026-05-02)** / **LM Studio headless** -- standard MLX/GGUF only; closed-source runtime; **3-5× faster agent loops** than vllm-mlx on the prior 27B-6bit precedent | prithivMLmods Qwen3.6-35B-A3B Uncensored Aggressive Q6_K (26.56 GiB) | Not needed |
| **dflash-mlx** | **8098** | **DFlash speculative decoding** -- target+drafter pair, wraps mlx_lm.server in 0.1.4.1+, requires 3 local patches; sustains 74-89 tok/s decode at 86.7% draft acceptance; **currently stopped** | Qwen3.6-35B-A3B-4bit + DFlash drafter (~23GB) | Not needed |

Only one server can occupy port 8000 at a time (vllm-mlx, mlx-openai-server, oMLX, vmlx). **llmster runs on a separate port (1234)** so it can technically run alongside one of the others, but the experimentation-lab framing in [`CLAUDE.md`](../CLAUDE.md#project) means we usually run only one model at a time. Current main is **llmster + prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K** (deployed 2026-05-02 after Event-4 hygiene); restart the HauhauCS Aggressive Q6_K_P or vmlx + Osaurus JANGTQ4 from [`docs/current.md`](../docs/current.md) when you need the comparison slots again.

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

**Model:** `mlx-community/Ling-2.6-flash-mlx-6bit` -- [bailing_hybrid](../docs/models/per-model/model-summary-ling.md) MoE, 6-bit MLX uniform, ~80GB on disk, 64K practical context (128K OOMs), 104B total / 7.4B active. Launched via standard `~/vllm-mlx-env/bin/vllm-mlx serve` (no JANG wrapper) with `--enable-auto-tool-choice --tool-call-parser hermes`. Requires three local patches (PR #1227 vendor + threadlocal-stream + inline-gen) — see [`model-summary-ling.md`](../docs/models/per-model/model-summary-ling.md) for the full deploy recipe. Older primaries: `JANGQ-AI/Qwen3.6-27B-JANG_4M` (dense+VL fallback, 17.5GB) and `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S` (122B/10B MoE, 35GB) — both still available via `run_vllm_jang.py` wrapper.

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

### `client/vmlx/` -- JANGTQ Server (Censored Standard Fine-Tune)

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-settings.json` | `~/.claude/settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |

**Templates pin the censored Osaurus JANGTQ4 fine-tune.** Default: `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` -- Qwen3.6 MoE+VL (35B total / ~3B active), JANGTQ4 / `mxtq`, ~19.7 GB on disk. API tool harness passes 5/5; OpenCode median is 72.75 s browse and 135.06 s search. Raw results: [`docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/`](../docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/). vmlx was stopped 2026-05-02 per Event-4 hygiene before deploying prithivMLmods Aggressive Q6_K on llmster; restart command in [`docs/current.md`](../docs/current.md).

For uncensored vmlx JANGTQ-CRACK variants (`dealignai/MiniMax-M2.7-JANGTQ-CRACK`, `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK`, `dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK`) use the matching templates under [`docs/models/uncen-model/client-configs/vmlx/`](../docs/models/uncen-model/client-configs/vmlx/).

Speaks OpenAI + Anthropic + Ollama API on port 8000. No API key required. Runs out of the MLX Studio DMG's bundled Python (`/Applications/vMLX.app/Contents/Resources/bundled-python/python/`) because the TurboQuant loader (`jang_tools.load_jangtq`) and Metal kernels (`turboquant/{tq_kernel,hadamard_kernel,gather_tq_kernel,fused_gate_up_kernel}`) are not distributed via the public pypi `jang` or `vmlx` wheels ([`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5) tracks this).

**Not compatible with**: `--smelt` or `--flash-moe` flags ([`vmlx#81`](https://github.com/jjang-ai/vmlx/issues/81) -- both raise `ValueError` on `weight_format=mxtq`). Use the bundled `python3 -m vmlx_engine.cli serve` invocation only; the bundled `bin/vmlx` shebang points at the maintainer's build tree.

### `client/llmster/` -- LM Studio Headless (Standard MLX, Port 1234)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Templates pin censored / standard MLX models on llmster.** Default is `gemma-4-31b-it-mlx` (Gemma 4 31B-it 6-bit) — the dense agent-loop speed leader on llmster (browse 5.11 s, search 6.37 s). Also lists `qwen3.6-27b` (Qwen3.6-27B 6-bit MLX). **Currently OpenCode-only** — Claude Code, OpenClaw, Pi, qwen-code config files have not been added because llmster's role is provisional (3-5× faster agent loops than vllm-mlx on non-JANG models, but closed-source runtime and no JANG/JANGTQ/`bailing_hybrid` support).

For uncensored llmster GGUFs (prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K, HauhauCS Qwen3.6-35B-A3B Aggressive Q6_K_P, HauhauCS Qwen3.6-27B Balanced Q8_K_P, etc.) use the matching templates under [`docs/models/uncen-model/client-configs/llmster/`](../docs/models/uncen-model/client-configs/llmster/). Custom K_P quant labels (HauhauCS family) mis-resolve through `lms get` — use direct Hub download + `lms import -L`. The current Mac Studio main is prithivMLmods Aggressive Q6_K (per [`docs/current.md`](../docs/current.md)) — copy the uncen-model template when you want OpenCode pointed at the live abliterated model.

Speaks **OpenAI-compatible** API on port **1234** (NOT 8000). No API key required. Default `lms server start` binds to `127.0.0.1`; LAN clients require `--bind 0.0.0.0`. Tool calling and `<think>` reasoning parsing are built into the MLX runtime — no parser flags needed. Full server runbook: [`docs/servers/llmster/summary.md`](../docs/servers/llmster/summary.md).

### `clients/dflash-mlx/` -- DFlash Speculative-Decoding Sidecar (Standard MLX, Port 8098)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Target:** `mlx-community/Qwen3.6-35B-A3B-4bit` (~22 GB, hybrid MoE 35B/3B + VL). **Drafter:** `z-lab/Qwen3.6-35B-A3B-DFlash` (~1 GB, 0.5B BF16). Standard MLX safetensors — no JANG/JANGTQ/`bailing_hybrid`/GGUF. **Currently OpenCode-only** — Claude Code, OpenClaw, Pi, qwen-code config files have not been added because dflash-mlx is provisional (decode-bound research server; loses to llmster on prefill-bound long-context multi-turn workloads).

Speaks **OpenAI-compatible** API on port **8098** (NOT 8000). No API key required. Wraps `mlx_lm.server` in 0.1.4.1+ (PyPI 0.1.0 has no tool-calling — install from `git+https://github.com/bstnxbt/dflash-mlx.git`). Three local patches required: `patch_dflash_mlx_serve.py`, `patch_mlx_lm_match.py`, `patch_dflash_mlx_host.py` (the last only for 0.1.0). The `--draft-model` flag is **required** for Qwen3.6 (built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family). Full server runbook: [`docs/servers/dflash-mlx/summary.md`](../docs/servers/dflash-mlx/summary.md).

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

# Switch to vmlx (current main: Osaurus Qwen3.6-35B-A3B JANGTQ4 — bundled-Python headless)
pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &

# Switch to llmster (LM Studio headless, port 1234 — separate from port 8000)
# Active main: prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K (26.56 GiB at 65K context)
# NOTE: if guardrail blocks load ("insufficient system resources"), temporarily set
#   modelLoadingGuardrails.mode to "off" in ~/.lmstudio/settings.json, load, then restore.
pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2
~/.lmstudio/bin/lms unload --all
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF', filename='Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf', local_dir='/Users/chanunc/.cache/prithiv-gguf')"
~/.lmstudio/bin/lms import -L --user-repo mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF -y ~/.cache/prithiv-gguf/Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf
~/.lmstudio/bin/lms load qwen3.6-35b-a3b-uncensored-aggressive --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors

# Switch to dflash-mlx (port 8098 — does not displace port 8000 but eats ~25 GB unified memory)
# First-time: pip install 'git+https://github.com/bstnxbt/dflash-mlx.git' in ~/dflash-mlx-env/,
#             then run patch_dflash_mlx_serve.py + patch_mlx_lm_match.py once.
# In practice on a 96 GB box, also stop the port-8000 server first if it's serving Ling (~80 GB).
pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2
nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512 \
  > /tmp/dflash-mlx.log 2>&1 &
```
