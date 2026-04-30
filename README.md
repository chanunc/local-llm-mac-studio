# 🦙 Mac Studio AI Stack Playground

Run large language models locally on a **Mac Studio M3 Ultra (96GB)** and connect coding agents over LAN.

> **Mistral Small 4 note:** On Apple Silicon, MLX support is still incomplete. Prefer `GGUF` on `llama.cpp` / `LM Studio` / `Ollama` for local use, or `vLLM` for Mistral's official full-feature self-deployment path.

```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (96GB)
  Claude Code                            vllm-mlx (primary) :8000
  OpenCode                               mlx-openai-server :8000
  OpenClaw                               oMLX (multi-model) :8000
  Pi                                     vmlx (JANGTQ) :8000
                                         llmster (LM Studio) :1234
                                         OpenAI + Anthropic API (+ Ollama for vmlx)
```

## 🗂️ Repository Map

This repository is primarily an **operations notebook + config bundle** for the Mac Studio inference stack, not a single application codebase.

### What lives where

| Path | Purpose | Start Here |
|:-----|:--------|:-----------|
| `docs/current.md` | Current live server / model / client-template state | Read before changing production |
| `docs/servers/` | Server runbooks, setup, maintenance, and JANG patches | `docs/servers/README.md` |
| `docs/models/` | Model catalog, compatibility notes, conversion guides, benchmarks | `docs/models/README.md` |
| `docs/clients/` | Client-side setup for Claude Code, OpenCode, OpenClaw, and Pi | `docs/clients/README.md` |
| `configs/` | Ready-to-copy client config templates grouped by server type | `configs/README.md` |
| `scripts/` | Patch helpers, benchmark drivers, and config-switching utilities | `scripts/README.md` |
| `plans/` | Research notes and future work, not live runbooks | `plans/README.md` |

### Canonical reading order

1. Read this `README.md` for the stack overview.
2. Read [`docs/current.md`](docs/current.md) for the current live production and sidecar state.
3. Read one server runbook from [`docs/servers/README.md`](docs/servers/README.md).
4. Read [`configs/README.md`](configs/README.md) for the matching client config templates.
5. Read [`docs/models/README.md`](docs/models/README.md) when choosing, adding, or benchmarking models.
6. Read the relevant maintenance or patch docs only when upgrading or debugging.

### Summary vs maintenance vs plans

- `summary.md` files are the main operational entry points.
- `maintenance.md` and `jang-patch.md` files are task-specific follow-ups.
- [`docs/current.md`](docs/current.md) is the concise live-state pointer.
- `plans/` captures ideas, experiments, and pending investigations; it is not the live runbook layer.

## ⚡ Quick Start

### 🚀 Start a Server

Pick one — all serve on port 8000. Stop others first if switching.

```bash
# vllm-mlx — fastest, single model. Current production primary:
# Ling-2.6-flash mlx-6bit (see Ling block below). Qwen3.6-27B JANG 4M is the
# go-to dense+VL fallback (17.5 GB, switched from Qwen3.5-122B-JANG_2S on 2026-04-23).
# Qwen3.5/3.6 need --tool-call-parser qwen3_coder (NOT qwen — they emit XML
# tool calls, not JSON). --reasoning-parser qwen3 extracts <think> blocks.
# See docs/servers/vllm-mlx/maintenance.md#8-qwen35-tool-calling--reasoning-parsers
nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M \
  --served-model-name JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &

# vllm-mlx — Qwen3.6-35B-A3B Rust LoRA (jedisct1, 8-bit MoE 35B/3B active, 35 GB).
# Standard MLX safetensors — no patches needed. Same parser flags as the JANG line
# (qwen3_coder + qwen3); the wrapper handles non-JANG paths fine. Best wall-time
# for browse/search agent loops (memory #1467, bench 2026-04-27).
nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/jedisct1--Qwen3.6-35B-rust.mlx \
  --served-model-name jedisct1/Qwen3.6-35B-rust.mlx \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &

# vllm-mlx — Ling-2.6-flash mlx-6bit (bailing_hybrid MoE 104B/7.4B active, ~80 GB).
# No JANG wrapper (plain MLX safetensors). --tool-call-parser hermes — Ling emits
# <tool_call>{json}</tool_call>, not the qwen3_coder XML body. No --reasoning-parser
# (model never emits <think>). Requires three patches first (vendored bailing_hybrid
# + thread-local stream + inline-gen) — see docs/models/per-model/model-summary-ling.md.
nohup ~/vllm-mlx-env/bin/vllm-mlx serve mlx-community/Ling-2.6-flash-mlx-6bit \
  --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > /tmp/vllm-mlx.log 2>&1 &

# mlx-openai-server — multi-model, low overhead
JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &

# oMLX — 9 models, hot-swap
/opt/homebrew/bin/brew services start omlx

# vmlx — JANGTQ CRACK (MLX Studio bundled Python, headless)
# Tool use + Qwen3 thinking require all three parser flags AND a one-time
# source patch (scripts/patches/patch_vmlx_jangtq_mllm_tools.py). See
# docs/servers/vmlx/maintenance.md#tool-use-and-reasoning-mllm-models.
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx.log 2>&1 &

# llmster — LM Studio headless on port 1234 (NOT 8000). Standard MLX safetensors
# only; no JANG/JANGTQ/bailing_hybrid support. Tool-call + reasoning parsing
# built into the MLX runtime — no parser flags needed. First-time setup:
#   brew install --cask lm-studio
#   open -a 'LM Studio' && sleep 8 && osascript -e 'quit app "LM Studio"'   # bootstraps ~/.lmstudio/bin/lms
#   ~/.lmstudio/bin/lms get https://huggingface.co/<org>/<repo> -y          # downloads to ~/.lmstudio/models/
# Launch sequence (per model):
~/.lmstudio/bin/lms load qwen3.6-27b --gpu max --context-length 65536 -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors                          # default port 1234

pkill -f vllm-mlx                                                                # stop vllm-mlx
pkill -f mlx-openai-server                                                       # stop mlx-openai-server
/opt/homebrew/bin/brew services stop omlx                                        # stop oMLX
pkill -f vmlx_engine                                                             # stop vmlx
~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all              # stop llmster
```

### 🩺 Health Check

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool            # vllm-mlx / mlx-openai-server
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool               # oMLX (auth required)
curl -s http://<MAC_STUDIO_IP>:1234/v1/models | python3 -m json.tool            # llmster (port 1234)

open http://<MAC_STUDIO_IP>:8000/admin                                            # oMLX dashboard

tail -f /tmp/vllm-mlx.log                                                       # vllm-mlx logs
tail -f /tmp/mlx-openai-server.log                                              # mlx-openai-server logs
tail -f ~/.omlx/logs/server.log                                                 # oMLX logs
tail -f /tmp/vmlx.log                                                           # vmlx logs
~/.lmstudio/bin/lms log stream                                                  # llmster live request/response stream
tail -f ~/.lmstudio/server-logs/$(date +%Y-%m)/$(date +%Y-%m-%d).1.log          # llmster daily log file
```

### 💬 Quick Test

Works on all servers — swap `<MODEL_NAME>` from `/v1/models`. Add auth header for oMLX.

```bash
# Plain chat round-trip
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<MODEL_NAME>","messages":[{"role":"user","content":"Say hello"}],"max_tokens":50}' \
  | python3 -m json.tool

# End-to-end agent + tool-call test via OpenCode (requires the model to be
# present in ~/.config/opencode/opencode.json under the `macstudio` provider).
# "Browse www.example.com" reliably triggers webfetch (a concrete URL avoids
# the model asking the user to clarify which page to fetch); confirms the
# server's tool-call parser flag (qwen3_coder / hermes / qwen3 depending on
# model) is wired correctly end-to-end.
opencode run --model "macstudio/<MODEL_NAME>" "Browse www.example.com"
```

---

## 🖥️ Servers

| Server | Speed | Models | API | Best For |
|:-------|:-----:|:------:|:----|:---------|
| **[vllm-mlx](docs/servers/vllm-mlx/summary.md)** | ⚡ Fastest | Single | OpenAI + Anthropic | Daily use — lowest overhead on Apple Silicon |
| **[mlx-openai-server](docs/servers/mlx-openai-server/summary.md)** | 🟢 Fast | Multi (YAML) | OpenAI | Prompt caching, speculative decoding |
| **[mlx-lm](docs/servers/mlx-lm/summary.md)** | 🟡 Good | Single | OpenAI | Lightweight dev/testing |
| **[oMLX](docs/servers/omlx/summary.md)** | 🔴 Slower | 9 hot-swap | OpenAI + Anthropic | Model variety with SSD caching |
| **[vmlx](docs/servers/vmlx/summary.md)** (MLX Studio bundled) | 🟢 Fast | JANGTQ only | OpenAI + Anthropic + Ollama | TurboQuant CRACK models — 43.7 tok/s on MiniMax-M2.7 |
| **[llmster](docs/servers/llmster/summary.md)** ([LM Studio](https://lmstudio.ai/) headless, :1234) | ⚡ Fastest agent loop | Standard MLX / GGUF | OpenAI | **3-5× faster than vllm-mlx end-to-end** on Qwen3.6-27B-6bit (47K tok/s prefill @ 32K). Brew cask install. No JANG/JANGTQ/bailing_hybrid. See [bench](docs/models/benchmarks/model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30) |

All servers except llmster support [JANG](https://jangq.ai/) mixed-precision models via patches:
[vllm-mlx](docs/servers/vllm-mlx/jang-patch.md) ·
[oMLX](docs/servers/omlx/jang-fork.md) ·
[mlx-openai-server](docs/servers/mlx-openai-server/jang-patch.md) ·
[mlx-lm](docs/servers/mlx-lm/jang-patch.md)

Server maintenance: [vllm-mlx](docs/servers/vllm-mlx/maintenance.md) · [oMLX](docs/servers/omlx/maintenance.md) · [mlx-openai-server](docs/servers/mlx-openai-server/maintenance.md) · [vmlx](docs/servers/vmlx/maintenance.md) · [llmster](docs/servers/llmster/summary.md) (no separate maintenance doc — single `summary.md` covers install, runtime recovery, and limitations)

Current `vllm-mlx` production primary: `mlx-community/Ling-2.6-flash-mlx-6bit` (sparse 104B / 7.4B-active `bailing_hybrid`, 6-bit MLX, ~80 GB on disk; deployed 2026-04-29 via three local patches — see [model-summary-ling.md](docs/models/per-model/model-summary-ling.md)). The Qwen3.6-27B JANG 4M dense+VL variant remains a documented fallback for VL workloads ([model-summary.md](docs/models/model-summary.md#qwen36-27b-jang-4m-dense--vl), [bench](docs/models/benchmarks/model-benchmark-agent-tool-call.md#results-jangq-aiqwen36-27b-jang_4m)).

Current `mlx-openai-server` roster: `mlx-community/Qwen3.6-35B-A3B-6bit` (single-model, Qwen3.6-only mode — switched 2026-04-18 for through-server benchmarking).


---

## 🤖 Models

All models fit in **96GB unified memory**.

| Model | Type | Size&#124;GB | Context | Best For |
|:--------------------------------------|:------------|----------:|--------:|:---------|
| [Gemma 4 26B-A4B (4-bit)](docs/models/model-summary.md#gemma-4-26b-a4b-4-bit) | MoE 26B/4B | 15 | 256K | Vision + video + reasoning + tool use |
| [Qwen3.5-122B-A10B JANG 2S](docs/models/model-summary.md#qwen35-122b-a10b-jang-2s) | MoE 122B/10B | 35 | 200K+ | Compact 122B, instant load |
| [Qwen3-Coder-Next 6-bit](docs/models/model-summary.md#qwen3-coder-next-6-bit) | Dense 80B | 60 | 170K | Coding specialist |
| [Qwen3-Coder-30B-A3B Instruct 4-bit](docs/models/model-summary.md#qwen3-coder-30b-a3b-instruct-4-bit) | MoE 30.5B/3.3B | 17.2 | 262K | Compact coding model |
| [Qwen3.5-122B-A10B 4-bit](docs/models/model-summary.md#qwen35-122b-a10b-4-bit) | MoE 122B/10B | 65 | 128K | Full-precision alternative |
| [Qwen3.5-27B Opus Distilled](docs/models/model-summary.md#qwen35-27b-claude-opus-distilled-qx64-hi) | Dense 27B | 19 | 128K | Reasoning / chain-of-thought |
| [OmniCoder-9B 8-bit](docs/models/model-summary.md#omnicoder-9b-8-bit) | Dense 9B | 9.5 | 262K | Lightweight coding agent |
| [Qwen3.5-35B-A3B JANG 4K](docs/models/model-summary.md#qwen35-35b-a3b-jang-4-bit-mixed-precision) | MoE 35B/3B | 19 | 262K | Fast small MoE |
| [Qwen3.6-35B-A3B 6-bit](docs/models/model-summary.md#qwen36-35b-a3b-6-bit) | Hybrid MoE 35B/3B + VL | 27 | 262K (1M YaRN) | Vision + hybrid linear attention |
| [Qwen3.6-27B JANG 4M](docs/models/model-summary.md#qwen36-27b-jang-4m-dense--vl) | Dense 27B + VL | 17.5 | 262K (1M YaRN) | Dense Qwen3.6 hybrid; JANG 4/8-bit (vllm-mlx text-only) |
| [Nemotron 3 Super 120B](docs/models/model-summary.md#nemotron-3-super-120b-a12b-45-bit) | MoE 120B/12B | 66.5 | 200K | Mamba-2 hybrid |
| [Nemotron 3 Nano 30B](docs/models/model-summary.md#nemotron-3-nano-30b-a3b-8-bit) | MoE 32B/3B | 34 | 262K | NVIDIA MoE |
| [Nemotron Cascade 2 30B](docs/models/model-summary.md#nemotron-cascade-2-30b-a3b-nvfp4) | Hybrid 30B/3B | 17 | 262K | Mamba-2 + MoE |
| MiniMax-M2.7 JANGTQ-CRACK | MoE 230B/10B | 57 | 128K | Uncensored, TurboQuant (vmlx only) — see [uncen-model](docs/models/uncen-model/) |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | MoE 35B/3B + VL | 19.7 | 262K | Uncensored efficiency winner (vmlx only) |
| Qwen3.6-35B-A3B JANGTQ2-CRACK | MoE 35B/3B + VL | 11.6 | 262K | Fastest CRACK, quality-impaired (vmlx only) |

Full specs and per-model details: [Model Summary](docs/models/model-summary.md)

**Quantization key**: *JANG* = adaptive mixed-precision ([jangq.ai](https://jangq.ai)), *MoE* = Mixture of Experts (total/active params), *nvfp4* = NVIDIA 4-bit float.

---

## 📊 Benchmarks

### Generation Speed (tokens/sec)

**Qwen3-Coder-Next 6-bit** (dense 60GB):

| Server | 512 | 8K | 32K | 64K |
|:-------|:---:|:--:|:---:|:---:|
| vllm-mlx | **68.8** 🥇 | **63.8** 🥇 | **56.4** 🥇 | **51.7** 🥇 |
| mlx-lm | 68.4 🥈 | 62.7 🥈 | 54.0 🥈 | 47.7 🥈 |
| oMLX | 66.5 | 56.9 | 40.4 | 34.8 |

**Gemma 4 26B-A4B 4-bit** (MoE, multimodal — mlx-openai-server 1.7.1, Apr 2026):

> Tokens include both reasoning (`reasoning_content`) and output (`content`) phases. 512 warm values shown (run 1 cold-start: 59.4 tok/s / 28 tok/s prefill / 18.7s TTFT).

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|:---:|:---:|:---:|
| 512 | **62.5** | 1,710 | 0.30 |
| 4K | 54.6 | 3,117 | 1.32 |
| 8K | **60.6** | **3,154** | 2.60 |
| 32K | 50.6 | 2,892 | 11.34 |
| 64K | 42.0 | 2,542 | 25.78 |
| 128K | 27.1 | 1,995 | 65.70 |

**Qwen3.6-35B-A3B 6-bit** (Hybrid MoE, multimodal — mlx-openai-server 1.7.1, Apr 2026):

> Tokens include both `reasoning_content` (always-on `<think>`) and `content`. Server-validated; standalone-only Apr 17 numbers in [standalone benchmarks](docs/models/benchmarks/model-benchmark-standalone.md#qwen36-35b-a3b-6-bit-vs-qwen35-35b-a3b-jang-4k) carry a VLM double-prefill artefact and are not directly comparable.

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|:---:|:---:|:---:|
| 512 | **52.5** | 1,401 | 0.34 |
| 4K | **53.0** | **2,237** | 1.64 |
| 8K | 51.3 | 2,197 | 3.32 |
| 32K | 46.3 | 1,798 | 16.22 |
| 64K | 40.3 | 1,408 | 41.40 |
| 128K | 35.6 | 927 | 125.73 |

Hybrid Gated DeltaNet pays off at long context — Qwen3.6's 35.6 tok/s @ 128K is **31% faster than Gemma 4** at the same context, despite Qwen3.6 carrying a vision encoder.

**Qwen3.5-35B-A3B JANG** (MoE, primary architecture):

| Server | 32K | 64K |
|:-------|:---:|:---:|
| vllm-mlx | **83.8** 🥇 | **71.6** 🥇 |
| mlx-openai-server | 81.3 🥈 | 62.8 |
| mlx-lm | 77.6 | 65.1 🥈 |
| oMLX | 59.9 | 49.0 |

**128K cross-model** (long-context comparison — all measured through-server, Apr 2026):

| Model | Server | Gen tok/s | Prefill tok/s | TTFT (s) |
|:-------|:-------|:---:|:---:|:---:|
| Qwen3-Coder-Next 6-bit (Dense 80B) | vllm-mlx | **44.2** 🥇 | **736** 🥇 | **158** 🥇 |
| Qwen3.6-35B-A3B 6-bit (Hybrid MoE + VL) | mlx-openai-server | 35.6 🥈 | 927 | 126 🥈 |
| Qwen3.5-122B JANG 2S | vllm-mlx (JANG) | 34.5 | 405 | 324 |
| Qwen3.5-35B-A3B JANG 4K | oMLX (Mar leaderboard) | 33.8 | 295 | — |
| Gemma 4 26B-A4B 4-bit (MoE + VL) | mlx-openai-server | 27.1 | 1,995 | 66 |

Full results: [Standalone](docs/models/benchmarks/model-benchmark-standalone.md) · [API Server](docs/models/benchmarks/model-benchmark-api-server.md) · [TurboQuant KV Cache](docs/models/benchmarks/model-benchmark-turboquant-jang.md) · [Agent Tool-Call](docs/models/benchmarks/model-benchmark-agent-tool-call.md)

---

## 🛠️ Coding Agents

| Agent | Description | Setup |
|:------|:------------|:------|
| **Claude Code** | Anthropic's official CLI | [Guide](docs/clients/new-client-machine-setup.md) |
| **OpenCode** | Autonomous coding agent | [Guide](docs/clients/opencode-setup.md) |
| **OpenClaw** | Multi-agent framework | [Guide](docs/clients/openclaw-setup.md) |
| **Pi** | Coding assistant | [Guide](docs/clients/pi-setup.md) |
| **Qwen Code** | Qwen-tuned terminal agent (OpenAI-compatible) | [Guide](docs/clients/qwen-code-setup.md) |

---

## ⚠️ Known Limitations

**Server constraints:**
- **oMLX** — No GGUF, no MXFP8, starlette 1.0 dashboard bug ([#361](https://github.com/jundot/omlx/issues/361)). JANG+Nemotron-H matmul mismatch ([details](docs/servers/omlx/jang-fork.md)). [Maintenance](docs/servers/omlx/maintenance.md)
- **mlx-openai-server** — No Anthropic API, single-request queue, 15% overhead at 64K context, tool arg string bug ([patch](scripts/patches/patch_mlx_openai_tool_args.py)). [Maintenance](docs/servers/mlx-openai-server/maintenance.md)
- **vllm-mlx** — Single model only, no dashboard, manual start, v0.2.6 return bug needs patch. Qwen3.5 tool use requires `--tool-call-parser qwen3_coder` (not `qwen`); see [maintenance §8](docs/servers/vllm-mlx/maintenance.md#8-qwen35-tool-calling--reasoning-parsers). [Maintenance](docs/servers/vllm-mlx/maintenance.md)
- **vmlx** — JANGTQ only (MLX Studio DMG bundled Python), no GUI but overwritten on every DMG upgrade. MLLM path drops `tools[]`, ignores `tools=` in chat template, and crashes on multi-turn tool replay — fix with [`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`](scripts/patches/patch_vmlx_jangtq_mllm_tools.py) ([detail](docs/servers/vmlx/maintenance.md#tool-use-and-reasoning-mllm-models)). Requires `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3`. [Maintenance](docs/servers/vmlx/maintenance.md)
- **llmster** — Standard MLX / GGUF only (no JANG/JANGTQ/`bailing_hybrid`). Closed-source MLX runtime. `lms get` re-downloads from HuggingFace into `~/.lmstudio/models/` even when present in `~/.cache/huggingface/` (no dedup). Model IDs are lowercased and org-prefix-stripped on load (`mlx-community/Qwen3.6-27B-6bit` → `qwen3.6-27b`). Default `lms server start` binds to `127.0.0.1`; LAN clients need `--bind 0.0.0.0`. First-time install needs one GUI launch to bootstrap `~/.lmstudio/bin/lms`. [Bench](docs/models/benchmarks/model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30)

**Model compatibility:**
- **Nemotron family** — Only works on vllm-mlx (chat template not packaged in MLX weights). [Details](docs/models/model-summary.md#nemotron-server-compatibility)
- **Mistral Small 4** — Broken on current MLX servers here (missing native `mistral4` MLA support in upstream `mlx-lm`). For Apple Silicon, the practical local path is `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`; Mistral's official full-feature deployment guidance still points to `vLLM`. [Details](docs/models/model-summary.md#mistral-small-4-119b-a6b-jang-2l)
- **Qwen3.5-122B + OpenClaw** — HTTP 500 with large system prompts ([#42](https://github.com/jundot/omlx/issues/42))

**Maintenance:**
- **JANG fork overlay** — `brew upgrade omlx` overwrites the fork; re-apply after every upgrade. [Guide](docs/servers/omlx/jang-fork.md)
- **Hot cache patch** — `scripts/patches/patch_omlx_cache.py` must re-run after every `brew upgrade omlx`. [Guide](docs/servers/omlx/maintenance.md)
- **SSH timeouts** — Fix: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10` on Mac Studio
