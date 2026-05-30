# 🦙 Mac Studio AI Stack Playground

Run large language models locally on a **Mac Studio M3 Ultra (96GB)** and connect coding agents over LAN.

> **Mistral Small 4 note:** On Apple Silicon, MLX support is still incomplete. Prefer `GGUF` on `llama.cpp` / `LM Studio` / `Ollama` for local use, or `vLLM` for Mistral's official full-feature self-deployment path.

```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (96GB)
  Claude Code                            vllm-mlx (primary) :8000
  OpenCode                               mlx-openai-server :8000
  OpenClaw                               oMLX (multi-model) :8000
  Pi                                     vmlx (JANGTQ) :8000
                                         lm-studio (LM Studio) :1234
                                         vmlx-swift-lm via Osaurus (sidecar) :1337
                                         dflash-mlx (sidecar) :8098
                                         llama-cpp-turboquant (sidecar) :8099
                                         llama-cpp-mtp (sidecar) :8100
                                         chindamt-4b (Thai↔EN translation, sidecar) :8080
                                         qwen-asr (speech→text, no port — Python API)
                                         comfyui (image-gen, sidecar) :8188
                                         ds4 / DwarfStar 4 (DeepSeek-V4-Flash, sidecar) :8101
                                         litert-lm (Gemma 4 E4B, sidecar) :9379
                                         sglang (MiniCPM5 parser, sidecar) :30000
                                         OpenAI + Anthropic API (+ Ollama for vmlx + Osaurus; Responses for ds4)
```

## 🗂️ Repository Map

This repository is primarily an **operations notebook + config bundle** for the Mac Studio inference stack, not a single application codebase.

### What lives where

| Path | Purpose | Start Here |
|:-----|:--------|:-----------|
| `scripts/chk_llm_macstu.py` | Probe the Mac Studio over SSH for the live server / model / client-template state (run-state is **not** stored in any doc) | `python3 scripts/chk_llm_macstu.py` |
| `docs/servers/` | Server runbooks, setup, maintenance, and JANG patches | `docs/servers/README.md` |
| `docs/models/` | Model catalog, compatibility notes, conversion guides, benchmarks | `docs/models/README.md` |
| `docs/clients/` | Client-side setup for Claude Code, OpenCode, OpenClaw, and Pi | `docs/clients/README.md` |
| `docs/server-apis/` | Wire-protocol references (Responses API, etc.) and which servers speak them | `docs/server-apis/README.md` |
| `configs/` | Ready-to-copy client config templates grouped by server type | `configs/README.md` |
| `scripts/` | Patch helpers, benchmark drivers, and config-switching utilities | `scripts/README.md` |
| `plans/` | Research notes and future work, not live runbooks | `plans/README.md` |

### Canonical reading order

1. Read this `README.md` for the stack overview.
2. Run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) to see which server/model is live right now (run-state is intentionally not recorded in docs — the Mac Studio is a personal machine).
3. Read one server runbook from [`docs/servers/README.md`](docs/servers/README.md).
4. Read [`configs/README.md`](configs/README.md) for the matching client config templates.
5. Read [`docs/models/README.md`](docs/models/README.md) when choosing, adding, or benchmarking models.
6. Read the relevant maintenance or patch docs only when upgrading or debugging.

### Summary vs maintenance vs plans

- `summary.md` files are the main operational entry points.
- `maintenance.md` and `jang-patch.md` files are task-specific follow-ups.
- [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) is the only source of truth for live run-state — it probes the Mac Studio over SSH; no doc asserts what is "current".
- `plans/` captures ideas, experiments, and pending investigations; it is not the live runbook layer.

## ⚡ Quick Start

### 🚀 Start a Server

Port-8000 servers are mutually exclusive — stop the current one before starting another. Sidecars run on their own ports and coexist: lm-studio `:1234`, ChindaMT mlx-lm `:8080`, dflash-mlx `:8098`, llama-cpp-turboquant `:8099`, llama-cpp-mtp `:8100`, ds4 / DwarfStar 4 `:8101`, Osaurus `:1337`, comfyui `:8188`, litert-lm `:9379`, sglang `:30000`, qwen-asr (no port). Each panel below carries the launch command(s) and the matching stop command.

<details>
<summary>⚡ <strong>lm-studio</strong> (:1234) — Huihui Gemma 4 26B-A4B launch recipe + other on-disk models + stop</summary>

```bash
# lm-studio (LM Studio headless, port 1234) — launch recipe for
# `mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF:i1-Q6_K`:
# huihui-ai refusal-direction abliteration on Gemma 4 26B-A4B sparse MoE
# (~4B active) + mradermacher imatrix Q6_K GGUF. 22.64 GB on disk, 21.08 GiB
# resident at 65 K context. 9/10 mlabonne (first Gemma 4 entry to clear 9/10),
# browse 2.55 s 🥇 all-time leader. (Run scripts/chk_llm_macstu.py to see what
# is live — run-state is not tracked in docs.)
# `lms get` mis-resolves i1-Q6_K — use direct Hub download + `lms import -L`.
# LM Studio guardrail dance only required on first load (subsequent reloads OK).
~/.lmstudio/bin/lms load 'huihui-gemma-4-26b-a4b-it-abliterated-i1' \
  --gpu max --context-length 65536 \
  --identifier 'gemma4-26b-a4b-huihui-abliterated-q6k' -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors

# Prior main (2026-05-14): prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M GGUF (Apache 2.0,
# dense 27B Qwen3.6 + ViT, prithivMLmods abliteration on Qwen3.6-27B + GLM-5.1
# reasoning-trace distillation, think-on, 15.41 GiB resident, decode 31 / 30 / 29 / 27
# tok/s @ 512/4K/8K/32K, API smoke 5/5 single-call + 3/3 multi-turn 16.88 s,
# refusal 9/10 @ max_tokens=1024, OpenCode 1.14.50 browse 11.62 s / search 19.47 s
# @ 2 turns + webfetch fired). Standard MLX / GGUF only; no JANG/JANGTQ/bailing_hybrid.
# Tool-call + reasoning parsing built into the LM Studio runtime — no parser flags needed.
# (Once-only) download + hard-link import:
ssh macstudio "mkdir -p ~/.cache/hauhau-gguf; \
  ~/comfyui/.venv/bin/hf download prithivMLmods/Q3.6-27B-GLM-5.1-DA-GGUF \
  Q3.6-27B-GLM-5.1-DA.Q4_K_M.gguf --local-dir ~/.cache/hauhau-gguf"
ssh macstudio "~/.lmstudio/bin/lms import -L --user-repo prithivMLmods/Q3.6-27B-GLM-5.1-DA-GGUF -y \
  ~/.cache/hauhau-gguf/Q3.6-27B-GLM-5.1-DA.Q4_K_M.gguf"
# Q4_K_M @ 15.41 GiB is BELOW the strict 25 % guardrail threshold (~24 GiB on 96 GB) — no dance.
ssh macstudio "~/.lmstudio/bin/lms load 'q3.6-27b-glm-5.1-da' --gpu max --context-length 65536 --identifier 'qwen3.6-27b-glm51-da-q4km' -y"
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"          # default port 1234

# Prior main (TrevorJS Gemma 4 31B-it Uncensored Q4_K_M) — fallback for working agent loops.
# Reload via: lms load 'gemma-4-31b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-31b-it-uncensored-trevorjs-q4km -y

~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all              # stop lm-studio

# health + logs:
curl -s http://<MAC_STUDIO_IP>:1234/v1/models | python3 -m json.tool             # health (port 1234)
~/.lmstudio/bin/lms log stream                                                   # live request/response stream
tail -f ~/.lmstudio/server-logs/$(date +%Y-%m)/$(date +%Y-%m-%d).1.log           # daily log file
```

</details>

<details>
<summary>⚡ <strong>vllm-mlx</strong> (:8000) — fastest, single model · 3 launch variants + stop</summary>

```bash
# vllm-mlx — fastest, single model. Example below serves Qwen3.6-27B JANG 4M
# (dense+VL, 17.5 GB); Ling-2.6-flash mlx-6bit is the bailing_hybrid path (see Ling
# block below). Run scripts/chk_llm_macstu.py to see what is live.
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

pkill -f vllm-mlx                                                                # stop vllm-mlx

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool             # health (port 8000)
tail -f /tmp/vllm-mlx.log                                                        # logs
```

</details>

<details>
<summary>🟢 <strong>mlx-openai-server</strong> (:8000) — multi-model, low overhead + stop</summary>

```bash
# mlx-openai-server — multi-model, low overhead
JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &

pkill -f mlx-openai-server                                                       # stop mlx-openai-server

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool             # health (port 8000)
tail -f /tmp/mlx-openai-server.log                                               # logs
```

</details>

<details>
<summary>🔴 <strong>oMLX</strong> (:8000) — 9 models, hot-swap + stop</summary>

```bash
# oMLX — 9 models, hot-swap
/opt/homebrew/bin/brew services start omlx

/opt/homebrew/bin/brew services stop omlx                                        # stop oMLX

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool               # health (auth required)
open http://<MAC_STUDIO_IP>:8000/admin                                            # dashboard
tail -f ~/.omlx/logs/server.log                                                  # logs
```

</details>

<details>
<summary>🟢 <strong>vmlx</strong> (:8000) — JANGTQ CRACK, MLX Studio bundled Python + stop</summary>

```bash
# vmlx — JANGTQ CRACK (MLX Studio bundled Python, headless)
# Tool use + Qwen3 thinking require all four flags AND a one-time
# source patch (scripts/patches/patch_vmlx_jangtq_mllm_tools.py). See
# docs/servers/vmlx/maintenance.md#tool-use-and-reasoning-mllm-models.
# --continuous-batching is mandatory on vmlx 1.5.20+: without it the MLLM/VLM
# path crashes (Qwen2Tokenizer.stopping_criteria) and bailing_hybrid text
# models crash mid-prefill (Stream(gpu, 1) not in thread).
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  --continuous-batching \
  > /tmp/vmlx.log 2>&1 &

pkill -f vmlx_engine                                                             # stop vmlx

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool             # health (port 8000)
tail -f /tmp/vmlx.log                                                            # logs
```

</details>

<details>
<summary>⚪ <strong>mlx-lm server (Gemma 4)</strong> (:8000) — STOPPED 2026-05-06, restart shape for reference</summary>

```bash
# mlx-lm server — STOPPED 2026-05-06 (was previous main with Gemma 4 31B-it MLX 6-bit).
# Restart shape kept here for reference. Direct mlx_lm.server binary, port 8000.
# IMPORTANT — launch via the Cellar libexec binary, NOT /opt/homebrew/bin/mlx_lm.server.
# /opt/homebrew/bin/mlx_lm.server symlinks to a python3.11 install whose mlx_lm lacks
# Gemma 4 (raises 'Model type gemma4 not supported'); the Cellar libexec uses python3.14
# which has full Gemma 4 support.
ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit \
  --host 0.0.0.0 --port 8000 \
  --max-tokens 8192 \
  > /tmp/mlx-lm-server.log 2>&1 &"

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool             # health (port 8000, when running)
tail -f /tmp/mlx-lm-server.log                                                   # logs
```

</details>

<details>
<summary>⚡ <strong>mlx-lm sidecar (ChindaMT-4B)</strong> (:8080, sidecar) — Thai↔EN translation + stop</summary>

```bash
# mlx-lm sidecar — iapp/ChindaMT-4B (Qwen3.5-4B hybrid SSM, MLX 4-bit, 2.2 GB) as a
# dedicated Thai ↔ English translation endpoint on port 8080 (coexists with every
# other server). --chat-template-args disables thinking server-wide so translations
# land in message.content not message.reasoning. Model ID in API calls must be the
# full path /Users/chanunc/mlx-models/chindamt-4b-4bit (short alias → HF 404).
# Launch via the Cellar libexec binary, NOT /opt/homebrew/bin/mlx_lm.server.
# Client guide: docs/clients/fabric-setup.md · catalog: docs/models/model-summary.md#chindamt-4b-thai--english-translation
nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/mlx-models/chindamt-4b-4bit \
  --host 0.0.0.0 --port 8080 \
  --chat-template-args '{"enable_thinking":false}' \
  > /tmp/chindamt.log 2>&1 &

pkill -f 'mlx_lm.server.*chindamt'                                               # stop mlx-lm ChindaMT sidecar

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool             # health (port 8080, ChindaMT Thai↔EN)
tail -f /tmp/chindamt.log                                                        # logs
```

</details>

<details>
<summary>🟢 <strong>dflash-mlx</strong> (:8098, sidecar) — speculative decoding (DFlash drafter) + stop</summary>

```bash
# dflash-mlx — speculative-decoding sidecar on port 8098 (NOT 8000). Pairs a
# standard MLX target with a DFlash drafter (block-diffusion verifier).
# Provisional, OpenCode-only client template. Requires three local patches
# (see docs/servers/dflash-mlx/summary.md). Currently set up for
# Qwen3.6-35B-A3B-4bit + z-lab/Qwen3.6-35B-A3B-DFlash. --draft-model is
# REQUIRED for Qwen3.6 (DRAFT_REGISTRY only auto-resolves Qwen3.5).
nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512 \
  > /tmp/dflash-mlx.log 2>&1 &

pkill -f dflash-serve                                                            # stop dflash-mlx

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8098/v1/models | python3 -m json.tool             # health (port 8098)
tail -f /tmp/dflash-mlx.log                                                      # logs (per-request DFlash telemetry)
```

</details>

<details>
<summary>⚡ <strong>llama-cpp-turboquant</strong> (:8099, sidecar) — TheTom turbo3 + johndpope iso3 + stop</summary>

```bash
# llama-cpp-turboquant — TurboQuant / RotorQuant KV-cache-compression sidecar on
# port 8099 (NOT 8000). Two forks installed: ~/llama-cpp-thetom/ (TheTom — turbo2/3/4,
# auto-asymmetric q8_0 K + sparse V, 4-mag LUT for pre-M5; CURRENT SPEED LEADER)
# and ~/llama-cpp-turboquant/ (johndpope — also exposes iso3/4 + planar3/4 for
# RotorQuant / IsoQuant / PlanarQuant Clifford-rotor variants). KV cache compression
# is weight-format-agnostic — same GGUF blob works on either fork. Provisional,
# OpenCode-only client template. -fa requires an explicit on|off|auto value
# (bare -fa errors out). See docs/servers/llama-cpp-turboquant/summary.md and
# docs/models/techniques/model-technique-rotorquant.md.

# Recommended — TheTom turbo3 (browse 6.47 s / search 15.64 s on Qwen3.6-35B-A3B
# Q6_K — 2.07x/2.27x faster than Gemma 4 mlx-lm baseline; agent-loop speed leader
# 2026-05-06). Loader silently auto-asymmetricizes K to q8_0 (log shows "K (q8_0):
# 340 MiB, V (turbo3): 125 MiB" even when launched with --cache-type-k turbo3).
GGUF=$(ls ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/*/Qwen3.6-35B-A3B-UD-Q6_K.gguf)
nohup ~/llama-cpp-thetom/build/bin/llama-server \
  -m "$GGUF" \
  --cache-type-k turbo3 --cache-type-v turbo3 \
  -ngl 99 -fa on \
  --host 0.0.0.0 --port 8099 \
  --alias qwen3.6-35b-a3b-turboquant-turbo3 \
  -c 65536 --jinja \
  > /tmp/llama-cpp-thetom.log 2>&1 &

# Alternative — johndpope's fork for RotorQuant iso3 (Clifford-rotor KV cache,
# the only Apple Silicon path for iso3/4 + planar3/4). Decode wins at small
# context (46.3 tok/s @ 512) but cold prefill regresses badly (>600 s timeout
# at 32 K — this fork lacks the auto-asymmetric K dispatch and graph-side WHT
# optimisation TheTom's branch carries). Same GGUF blob.
nohup ~/llama-cpp-turboquant/build/bin/llama-server \
  -m "$GGUF" \
  --cache-type-k iso3 --cache-type-v iso3 \
  -ngl 99 -fa on \
  --host 0.0.0.0 --port 8099 \
  --alias qwen3.6-35b-a3b-rotorquant-iso3 \
  -c 65536 --jinja \
  > /tmp/llama-cpp-turboquant.log 2>&1 &

pkill -f 'build/bin/llama-server'                                                # stop llama-cpp-turboquant or llama-cpp-mtp (matches both forks + MTP sidecar; if you have multiple llama-server processes alive, pkill -f 'llama-cpp-mtp/build/bin/llama-server' targets only the MTP one)

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8099/v1/models | python3 -m json.tool             # health (port 8099)
tail -f /tmp/llama-cpp-thetom.log                                                # logs (TheTom fork)
tail -f /tmp/llama-cpp-turboquant.log                                            # logs (johndpope fork)
```

</details>

<details>
<summary>🟢 <strong>llama-cpp-mtp</strong> (:8100, sidecar) — Qwen3.6 MTP self-drafting + stop</summary>

```bash
# llama-cpp-mtp — Qwen3.6 MTP (Multi-Token Prediction / Next-n) self-drafting
# speculative-decoding sidecar on port 8100 (NOT 8000/1234/8098/8099).
# Two binaries: mainline ggml-org/llama.cpp (~/llama-cpp-mainline/, preferred)
# and legacy am17an/llama.cpp@mtp-clean (~/llama-cpp-mtp/, PR #22673).
# Single-file GGUF carries both target weights and the MTP draft heads;
# no separate drafter file, no --spec-draft-model flag. Patch-free.
# -np > 1 and --mmproj unsupported with MTP active.
# Flag is --spec-type draft-mtp (NOT just "mtp"); default --spec-draft-n-max
# is 16, must override to 2. Provisional, OpenCode-only client template.
# See docs/servers/llama-cpp-mtp/summary.md and
# docs/models/techniques/model-technique-qwen-3-6-mtp.md.

# Recommended — huihui-ai MoE 35B/3B MTP Q6_K (mainline binary, 78.5 tok/s,
# 83% MTP acceptance, browse 4.74 s, 10/10 mlabonne, Claude 4.7 Opus distilled)
GGUF=~/.cache/huggingface/hub/models--huihui-ai--Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF/snapshots/main/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-Q6_K.gguf
nohup ~/llama-cpp-mainline/build/bin/llama-server \
  -m "$GGUF" \
  -ngl 99 -fa on -np 1 -c 32768 \
  --spec-type draft-mtp --spec-draft-n-max 2 \
  --host 0.0.0.0 --port 8100 \
  --alias huihui-qwen36-35b-mtp-abliterated-q6k \
  --jinja --reasoning on \
  > /tmp/llama-cpp-mtp.log 2>&1 &

# Alternative — unsloth dense 27B MTP UD-Q6_K_XL (legacy binary, 22.9 tok/s)
GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf
nohup ~/llama-cpp-mtp/build/bin/llama-server \
  -m "$GGUF" \
  -ngl 99 -fa on -np 1 -c 32768 \
  --spec-type draft-mtp --spec-draft-n-max 2 \
  --host 0.0.0.0 --port 8100 \
  --alias qwen3.6-27b-mtp-ud-q6kxl \
  --jinja --reasoning on \
  > /tmp/llama-cpp-mtp.log 2>&1 &

# Alternative — LiquidAI LFM2.5-8B-A1B Q8_0 (no MTP, 190 tok/s, patched template)
# Requires the {# List of tools: [ #} chat-template patch — see
# docs/models/per-model/model-summary-lfm2.md for the GGUF patch recipe.
GGUF=~/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q8_0-fixed.gguf
nohup ~/llama-cpp-mainline/build/bin/llama-server \
  -m "$GGUF" \
  -ngl 99 -fa on -np 1 -c 65536 \
  --host 0.0.0.0 --port 8100 \
  --alias lfm2.5-8b-a1b-q8 \
  --jinja --reasoning-format auto \
  > /tmp/lfm-q8fixed.log 2>&1 &

pkill -f 'llama-cpp-mainline/build/bin/llama-server'; pkill -f 'llama-cpp-mtp/build/bin/llama-server'  # stop

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8100/v1/models | python3 -m json.tool             # health (port 8100)
tail -f /tmp/llama-cpp-mtp.log                                                   # logs (port 8100, Qwen3.6 MTP sidecar)
```

</details>

<details>
<summary>🔴 <strong>vmlx-swift-lm / Osaurus</strong> (:1337, sidecar) — MLX-Swift engine (ZAYA1 / Hunyuan v3) + stop</summary>

```bash
# vmlx-swift-lm via Osaurus — MLX-Swift engine sidecar on port 1337 (NOT 8000).
# Only Mac Studio runtime that natively supports Zyphra ZAYA1 (top-1 CCA + MoE),
# Hunyuan v3 (Hy3), and the MiniMax-M2.7 JANGTQ Hadamard kernel path. Installed
# via `brew install --cask osaurus`; engine pin = osaurus-ai/vmlx-swift-lm commit
# b9da180. OpenAI + Anthropic + Ollama APIs. Tool-call + reasoning parsers are
# built-in per family (no flags). PATH-MISMATCH GOTCHA: `osaurus pull` writes to
# ~/.osaurus/models/ but `osaurus serve` defaults to ~/MLXModels/ which doesn't
# exist — set OSU_MODELS_DIR explicitly. JANGTQ HTTP-path is speed-regressed
# pending Osaurus PR #1057 (~7-8 tok/s on ZAYA1 JANGTQ4 vs the engine's own
# RunBench 57 tok/s). See docs/servers/vmlx-swift-lm/summary.md.
ssh macstudio "/opt/homebrew/bin/osaurus pull JANGQ-AI/ZAYA1-8B-JANGTQ4"
ssh macstudio "OSU_MODELS_DIR=\$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 \
  > /tmp/osaurus.log 2>&1 &"

/opt/homebrew/bin/osaurus stop; pkill -9 osaurus 2>/dev/null                     # stop vmlx-swift-lm / Osaurus

# health + logs:
curl -s http://127.0.0.1:1337/v1/models | python3 -m json.tool                   # health (port 1337, loopback-only by default)
tail -f /tmp/osaurus.log                                                         # logs (port 1337)
```

</details>

<details>
<summary>🟢 <strong>comfyui</strong> (:8188, sidecar) — image generation (Z-Anime) + stop</summary>

```bash
# comfyui — image-generation sidecar on port 8188 (NOT 8000/1234/8098/8099/8100, no
# collision with chat servers). ComfyUI 0.20+ has first-party Z-Image-Turbo nodes;
# Z-Anime is the SeeSee21 fine-tune (S3-DiT 6B, Apache-2.0). Web UI only — no
# OpenAI /v1/images/generations shim. --use-pytorch-cross-attention is REQUIRED on
# Apple Silicon (the default attention backend errors on MPS). Wall time @ 1024²:
# Distill-4-step 17.75 s (CFG 1.0), Base 28-step 235.16 s (CFG 4.0) — see
# docs/models/benchmarks/logs/z-anime/wall-time-comfyui.md.
nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py \
  --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention \
  > /tmp/comfyui.log 2>&1 &

pkill -f 'comfyui/main.py'                                                       # stop comfyui

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8188/system_stats | python3 -m json.tool           # health (port 8188; no /v1/models — use /models/checkpoints to list weights)
open http://<MAC_STUDIO_IP>:8188                                                  # web UI (image gen)
tail -f /tmp/comfyui.log                                                          # logs (port 8188 image gen)
```

</details>

<details>
<summary>🟢 <strong>ds4 / DwarfStar 4</strong> (:8101, sidecar) — DeepSeek-V4-Flash 284B/13B-active + stop</summary>

```bash
# ds4 — standalone native C+Metal engine for DeepSeek-V4-Flash on port 8101 (NOT
# 8000/1234/8098/8099/8100/8188). Only Apple-Silicon path for the deepseek4 arch:
# upstream llama.cpp doesn't implement it; vLLM/SGLang are CUDA-only; the persadian
# IQ1_S-XL GGUF's only engine (arishma108/llama.cpp feat/v4-port-cuda) has no Metal.
# One-time: git clone https://github.com/antirez/ds4.git && cd ds4 && make -j8;
#           ./download_model.sh q2-imatrix  (81 GB; only tier that fits 96 GB-class).
# Native DSML↔OpenAI tool calling (no parser flags). Default bind is 127.0.0.1 —
# --host 0.0.0.0 is REQUIRED for LAN (--cors only adds headers, does not rebind).
# See docs/servers/ds4/summary.md and docs/models/per-model/model-summary-deepseek-v4.md
cd ~/ds4 && nohup ./ds4-server \
  --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt \
  > /tmp/ds4-server.log 2>&1 &

pkill -f 'ds4-server'                                                            # stop ds4 / DwarfStar 4

# health + logs:
curl -s http://<MAC_STUDIO_IP>:8101/v1/models | python3 -m json.tool             # health (port 8101; model id deepseek-v4-flash)
tail -f /tmp/ds4-server.log                                                       # logs (port 8101, DeepSeek-V4-Flash)
```

</details>

<details>
<summary>🟢 <strong>qwen-asr</strong> (no port, sidecar) — speech→text, in-process Python API (no daemon)</summary>

```bash
# qwen-asr (speech→text sidecar) — no port-bound daemon. Transcribe in-process via
# the Python API. Three calls: build venv, smoke, RTF bench.
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/qwen-asr-env && \
  ~/qwen-asr-env/bin/pip install -U pip wheel && \
  ~/qwen-asr-env/bin/pip install qwen-asr"
scp scripts/bench/bench_asr_smoke.py macstudio:/tmp/
ssh macstudio "~/qwen-asr-env/bin/python /tmp/bench_asr_smoke.py"
scp scripts/bench/bench_asr_rtf.py macstudio:/tmp/
ssh macstudio "~/qwen-asr-env/bin/python /tmp/bench_asr_rtf.py"
```

</details>

### 💬 Quick Test

Works on all servers — swap `<MODEL_NAME>` from `/v1/models`. Add auth header for oMLX.

<details>
<summary>🌐 <strong>curl</strong> — raw HTTP chat round-trip (any server)</summary>

```bash
# Plain chat round-trip
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<MODEL_NAME>","messages":[{"role":"user","content":"Say hello"}],"max_tokens":50}' \
  | python3 -m json.tool
```

</details>

<details>
<summary>🧰 <strong>LiteRT-LM native tools</strong> — Gemma 4 E4B function-call smoke</summary>

```bash
# 1) Create a native LiteRT-LM tool preset on the Mac Studio.
ssh macstudio "cat >/tmp/litert_tools_preset.py <<'PY'
import urllib.request

def web_fetch(url: str) -> str:
    '''Fetch a web page and return the first 2000 characters of text.'''
    if not url.startswith(('http://', 'https://')):
        return 'blocked: URL must start with http:// or https://'
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read().decode('utf-8', errors='replace')[:2000]

def write_file(path: str, content: str) -> str:
    '''Write content to a local Markdown file.'''
    if not path.endswith('.md'):
        return 'blocked: output path must end with .md'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f'wrote {len(content)} bytes to {path}'

system_instruction = 'You are a helpful assistant with access to tools.'
tools = [web_fetch, write_file]
PY"

# 2) Run Gemma 4 E4B with native LiteRT-LM tools.
ssh macstudio "export PATH=\"\$HOME/.local/bin:\$PATH\" && \
  litert-lm run <MODEL_PATH>/model.litertlm \
    --backend=cpu \
    --preset=/tmp/litert_tools_preset.py \
    --prompt='Use tools to fetch https://news.ycombinator.com/, identify the top story, summarize it in 2 bullets, and write the result as Markdown to /tmp/hackernews-latest.md.'"
```

</details>

<details>
<summary>🔧 <strong>openai-cli</strong> — one-shot prompt test (any server, swap BASE_URL)</summary>

```bash
# openai-cli one-shot prompt test (works against any server — swap BASE_URL port/model).
# Pipe through jq -r to decode \uXXXX escapes for non-ASCII output (Thai, CJK, emoji).
OPENAI_API_KEY=not-needed \
OPENAI_BASE_URL=http://<MAC_STUDIO_IP>:8080/v1 \
openai chat:completions create \
  --model "/Users/chanunc/mlx-models/chindamt-4b-4bit" \
  --message '{"role":"user","content":"Translate to English: สวัสดีครับ"}' \
  --max-tokens 100 | jq -r '.choices[0].message.content'
```

</details>

<details>
<summary>🤖 <strong>OpenCode</strong> — end-to-end agent + tool-call test</summary>

```bash
# End-to-end agent + tool-call test via OpenCode (requires the model to be
# present in ~/.config/opencode/opencode.json under the `macstudio` provider).
# "Browse www.example.com" reliably triggers webfetch (a concrete URL avoids
# the model asking the user to clarify which page to fetch); confirms the
# server's tool-call parser flag (qwen3_coder / hermes / qwen3 depending on
# model) is wired correctly end-to-end.
opencode run --model "macstudio/<MODEL_NAME>" "Browse www.example.com"
```

</details>

<details>
<summary>🧵 <strong>Fabric</strong> — prompt-pattern CLI over any <code>/v1</code> server (full guide: <a href="docs/clients/fabric-setup.md"><code>docs/clients/fabric-setup.md</code></a>)</summary>

```bash
# Install (binary is `fabric-ai`; symlink to `fabric` once — it uses its own
# name as the default pattern, so bare `fabric-ai` errors without -p).
brew install fabric-ai && ln -s /opt/homebrew/bin/fabric-ai ~/.local/bin/fabric

# 1. Raw passthrough (NO pattern) — correct mode for ChindaMT translation
echo "Translate to Thai: Good evening" | fabric
fabric < document.txt

# 2. Pattern mode — wrap input in a curated prompt (250+ via `fabric -l`).
#    Patterns are general-LLM prompts → point at a GENERAL model, not ChindaMT.
echo "long article text" | fabric -p summarize -m "<general-model-id>"
fabric -y "https://youtube.com/watch?v=..." -p extract_wisdom -m "<general-model-id>"

# 3. Change model / server — edit ~/.config/fabric/.env (or run `fabric -S`):
#    DEFAULT_VENDOR=LM Studio
#    DEFAULT_MODEL=/Users/chanunc/mlx-models/chindamt-4b-4bit   # exact /v1/models ID
#    LM_STUDIO_API_URL=http://<MAC_STUDIO_IP>:8080/v1           # MUST end in /v1
#    LM_STUDIO_API_KEY=not-needed
#    → retarget another server by changing the URL (e.g. :8000/v1) + DEFAULT_MODEL.
#    → per-run override without editing .env:  ... | fabric -V "LM Studio" -m "<id>"
```

</details>

---

## 🖥️ Servers

The four port-8000 servers are **mutually exclusive** (one at a time); `lm-studio` (:1234) and every sidecar run on their own ports and coexist. Run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) to see what is live.

<details>
<summary>🧠 <strong>Main chat servers</strong> — full general-purpose inference</summary>

| Server | Port | Speed | API | Role |
|:-------|:----:|:-----:|:----|:-----|
| **[vllm-mlx](docs/servers/vllm-mlx/summary.md)** | 8000 | ⚡ Fastest | OpenAI+Anthropic | Daily use — lowest overhead; best for sparse-MoE / `bailing_hybrid` |
| **[lm-studio](docs/servers/lm-studio/summary.md)** | 1234 | ⚡ Fastest agent loop | OpenAI | Uncensored-compliance leader; built-in tool/reasoning parsers (no flags) |
| **[mlx-openai-server](docs/servers/mlx-openai-server/summary.md)** / **mlx-lm** | 8000 | 🟢 Fast | OpenAI | Single-model direct or YAML multi-model; prompt cache + speculative decoding |
| **[oMLX](docs/servers/omlx/summary.md)** | 8000 | 🔴 Slower | OpenAI+Anthropic | 9-model hot-swap with SSD caching |
| **[vmlx](docs/servers/vmlx/summary.md)** | 8000 | 🟢 Fast | OpenAI+Anthropic+Ollama | TurboQuant **JANGTQ** models (bundled MLX Studio Python) |

</details>

<details>
<summary>🧩 <strong>Sidecars</strong> — coexist on their own ports</summary>

| Server | Port | Speed | API | Role |
|:-------|:----:|:-----:|:----|:-----|
| **[dflash-mlx](docs/servers/dflash-mlx/summary.md)** | 8098 | 🟢 High-decode | OpenAI | DFlash speculative decoding (74–89 tok/s, ~87% draft accept) |
| **[llama-cpp-turboquant](docs/servers/llama-cpp-turboquant/summary.md)** | 8099 | ⚡ Fast agent loop | OpenAI | TurboQuant / RotorQuant / PlanarQuant KV cache — two forks (TheTom `turbo3`, johndpope `iso3`) |
| **[llama-cpp-mtp](docs/servers/llama-cpp-mtp/summary.md)** | 8100 | 🟢 84–89% MTP accept | OpenAI | Qwen3.6 Multi-Token-Prediction self-drafting (only Apple-Silicon path) |
| **[vmlx-swift-lm](docs/servers/vmlx-swift-lm/summary.md)** | 1337 | 🔴 HTTP 7–8 tok/s\* | OpenAI+Anthropic+Ollama | MLX-Swift via Osaurus — only runtime for ZAYA1 / Hunyuan v3 (\*JANGTQ HTTP regression, [PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057)) |
| **[mlx-lm](docs/servers/mlx-lm/summary.md)** | 8080 | ⚡ 186 tok/s | OpenAI | Thai ↔ English translation (`iapp/ChindaMT-4B`, 2.5 GB) |
| **[qwen-asr](docs/servers/qwen-asr/summary.md)** | — | 🟢 19× realtime | Python only | Speech → text (`Qwen3-ASR-1.7B`, 30 langs + 22 Chinese dialects) |
| **[comfyui](docs/servers/comfyui/summary.md)** | 8188 | 🟢 18 s/img | Web UI only | Image generation (`SeeSee21/Z-Anime`; no OpenAI image shim) |
| **[ds4](docs/servers/ds4/summary.md)** | 8101 | 🟢 25–35 tok/s | OpenAI + Anthropic + Responses | DeepSeek-V4-Flash 284B/13B-active `deepseek4` MoE (only Apple-Silicon path; native DSML tool calling) |
| **[litert-lm](docs/servers/litert-lm/summary.md)** | 9379 | 🔴 13.85 tok/s | OpenAI (alpha) | Google LiteRT-LM edge runtime — Gemma 4 E4B (~4B, CPU/XNNPACK). No tool calling. Evaluation only. |
| **[sglang](docs/servers/sglang/summary.md)** | 30000 | 🟢 246→85 tok/s | OpenAI | SGLang MLX sidecar — MiniCPM5 `minicpm5` parser path; HF checkpoint only, GGUF unsupported locally |

</details>

All servers except `lm-studio`, `dflash-mlx`, `llama-cpp-turboquant`, `llama-cpp-mtp`, `qwen-asr`, `comfyui`, `ds4` (GGUF-locked DeepSeek-V4-Flash engine), `litert-lm`, `sglang`, and `vmlx-swift-lm` (its JANG/JANGTQ support is native, not via patch) support [JANG](https://jangq.ai/) mixed-precision models via patches:
[vllm-mlx](docs/servers/vllm-mlx/jang-patch.md) ·
[oMLX](docs/servers/omlx/jang-fork.md) ·
[mlx-openai-server](docs/servers/mlx-openai-server/jang-patch.md) ·
[mlx-lm](docs/servers/mlx-lm/jang-patch.md)

Server maintenance: [vllm-mlx](docs/servers/vllm-mlx/maintenance.md) · [oMLX](docs/servers/omlx/maintenance.md) · [mlx-openai-server](docs/servers/mlx-openai-server/maintenance.md) · [vmlx](docs/servers/vmlx/maintenance.md) · [lm-studio](docs/servers/lm-studio/summary.md) · [dflash-mlx](docs/servers/dflash-mlx/summary.md) · [llama-cpp-turboquant](docs/servers/llama-cpp-turboquant/summary.md) · [sglang](docs/servers/sglang/summary.md) (`lm-studio`, `dflash-mlx`, `llama-cpp-turboquant`, and `sglang` keep install / runtime / limitations in their single `summary.md`)

**There is no fixed "production main".** The live server/model is whatever experiment is currently loaded, and the repo deliberately does not record it — the Mac Studio is a personal machine. Run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) to see what is live right now (it probes over SSH and can also emit the matching client config). Server capabilities are in the table above; per-model specs and benchmark numbers are in the [Models](#-models) and [Benchmarks](#-benchmarks) sections.

`mlx-openai-server` config templates expose a stable superset of compatible model IDs (e.g. `mlx-community/Qwen3.6-35B-A3B-6bit`); they are not a live mirror — check `/v1/models` (or `scripts/chk_llm_macstu.py`) for the actual roster.


---

## 🤖 Models

All models fit in **96GB unified memory**.

<details>
<summary>🧱 <strong>Dense</strong> — 13 models</summary>

| Model | Type | Size&#124;GB | Context | Best For |
|:--|:--|--:|--:|:--|
| [DavidAU Qwen3.6-40B Heretic Q6_K IMatrix](docs/models/per-model/model-summary-qwen-3-6.md#davidau-qwen36-40b-heretic-uncensored-thinking-q6_k-imatrix) | Dense 40B | 30.2 | 131K | Prior lm-studio main (2026-05-03) — Heretic recipe, 9/10 compliance, visible content, browse 18.73 s |
| [Gemma 4 31B-it (6-bit)](docs/models/per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) | Dense 31B | 29 | 64K | Fastest standard agent-loop model on lm-studio (5–6 s browse) |
| [HauhauCS Qwen3.6-27B Uncensored Balanced Q8_K_P](docs/models/per-model/model-summary-qwen-3-6.md#hauhaucs-qwen36-27b-uncensored-balanced-q8_k_p) | Dense 27B + VL | 32 | 262K (1M YaRN) | Prior lm-studio GGUF sidecar (superseded 2026-05-02) *(removed from disk 2026-05-05)* |
| [IBM Granite 4.1 30B Q8_0](docs/models/per-model/model-summary-granite-4.1.md) | Dense 30B | 29 | 65K | Prior production main (2026-05-06) — Apache 2.0 fallback, dense instruct, 24.8 tok/s, browse 6.24 s, search 10.51 s |
| [LiquidAI LFM2.5-8B-A1B Q8_0](docs/models/per-model/model-summary-lfm2.md) | MoE 8.3B/1.5B-active | 9.01 | 65K | Fast on-device MoE — 190 tok/s, browse 11.1 s / search 19.72 s. **`llama-cpp-mainline --jinja` only** (lm-studio tool calls broken); canonical GGUF needs the `{# List of tools: [ #}` chat-template patch for the LFM2 pythonic tool parser ([llama.cpp #20245](https://github.com/ggml-org/llama.cpp/issues/20245)) |
| [OmniCoder-9B 8-bit](docs/models/model-summary.md#omnicoder-9b-8-bit) | Dense 9B | 9.5 | 262K | Lightweight coding agent |
| [prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M](docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md) | Dense 27B + VL (think-on) | 15.41 | 65K | Prior production main (2026-05-14 → 2026-05-15 on lm-studio port 1234) — Apache 2.0, prithivMLmods abliteration + GLM-5.1 reasoning-trace distillation, decode 31 / 30 / 29 / 27 tok/s @ 512 / 4K / 8K / 32K, smoke 5/5 + multi-turn 3/3 at API layer, refusal 9/10 @ 1024 tok, OpenCode browse **11.62 s** / search **19.47 s** @ 2 turns w/ `webfetch`. Launch recipe: `lms load 'q3.6-27b-glm-5.1-da' --gpu max --context-length 65536 --identifier 'qwen3.6-27b-glm51-da-q4km' -y; lms server start --bind 0.0.0.0 --cors` |
| [Qwen3-Coder-Next 6-bit](docs/models/per-model/model-summary-qwen-3-coder.md#qwen3-coder-next-6-bit) | Dense 80B | 60 | 170K | Coding specialist |
| [Qwen3.5-27B Opus Distilled](docs/models/per-model/model-summary-qwen-3-5.md#qwen35-27b-claude-opus-distilled-qx64-hi) | Dense 27B | 19 | 128K | Reasoning / chain-of-thought |
| [Qwen3.6-27B JANG 4M](docs/models/per-model/model-summary-qwen-3-6.md#qwen36-27b-jang-4m-dense--vl) | Dense 27B + VL | 17.5 | 262K (1M YaRN) | Dense Qwen3.6 hybrid; JANG 4/8-bit (vllm-mlx text-only) |
| [TrevorJS Gemma 4 31B-it Uncensored Q4_K_M](docs/models/uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md) | Dense 31B | 17.4 | 65K | Prior production main (2026-05-10 → 2026-05-12) — Apache 2.0, abliteration, no-think, 30 tok/s @ 512, **API multi-turn 6.73 s**, OpenCode warm-cache browse **6.63 s** _(initial 10.08 s)_ / search 30.81 s; refusal **harness 6–7/10 / manual 10/10** (disclaimer-prefixed complies) |
| [unsloth Qwen3.6-27B-MTP UD-Q6_K_XL](docs/models/techniques/model-technique-qwen-3-6-mtp.md) | Dense 27B + MTP heads (vision broken under MTP) | 26 | 32K (262K train) | Prior production main (deployed 2026-05-15 on `llama-cpp-mtp` port 8100, superseded same day by lm-studio + Huihui) — Apache 2.0 base, Unsloth Dynamic 2.0 6-bit GGUF + Multi-Token Prediction self-drafting heads, **84–89 % MTP draft acceptance**, decode 22.9 / 22.3 / 22.0 / 20.0 tok/s @ 414 / 3 648 / 7 274 / 29 128 input tokens, smoke 5/5 + multi-turn 21.92 s, OpenCode browse **35.98 s** / search **35.24 s** @ 2 turns w/ `webfetch` (slower than the GLM-5.1-DA Q4_K_M build) |
| [llmfan46 Qwen3.6-27B Heretic v2 MTP Q6_K](docs/models/uncen-model/qwen36-27b-heretic-v2-mtp-benchmark.md) | Dense 27B + 15 native MTP params | 22.2 | 131K | Heretic v1.3.0 MPOA abliteration (`attn.o_proj`/`mlp.down_proj`) + MTP self-drafting, ~74% MTP acceptance, 24.6 tok/s, 10/10 mlabonne, browse 38.99 s / search 40.42 s on `llama-cpp-mtp` :8100. First Heretic-abliterated + MTP in lab. [Bench](docs/models/uncen-model/qwen36-27b-heretic-v2-mtp-benchmark.md) |
| [Gemma 4 E4B (LiteRT-LM)](docs/models/per-model/model-summary-gemma.md#gemma-4-e4b-litert-lm) | Dense ~4B | 3.66 | ~3K | Google LiteRT-LM edge runtime evaluation. CPU/XNNPACK 71.5 tok/s prefill, 13.85 tok/s decode. No tool calling via HTTP (alpha serve). Smallest model in lab. [Runbook](docs/servers/litert-lm/summary.md) |

</details>

<details>
<summary>🧬 <strong>Hybrid</strong> — 1 model</summary>

| Model | Type | Size&#124;GB | Context | Best For |
|:--|:--|--:|--:|:--|
| [Nemotron Cascade 2 30B](docs/models/per-model/model-summary-nemotron.md#nemotron-cascade-2-30b-a3b-nvfp4) | Hybrid 30B/3B | 17 | 262K | Mamba-2 + MoE |

</details>

<details>
<summary>🧩 <strong>Hybrid MoE</strong> — 4 models</summary>

| Model | Type | Size&#124;GB | Context | Best For |
|:--|:--|--:|--:|:--|
| [HauhauCS Qwen3.6-35B-A3B Uncensored Aggressive Q6_K_P](docs/models/per-model/model-summary-qwen-3-6.md#hauhaucs-qwen36-35b-a3b-uncensored-aggressive-q6_k_p) | Hybrid MoE 35B/3B + VL | 31 | 262K (1M YaRN) | Prior lm-studio main (superseded 2026-05-02) — uncensored search-speed leader (12.01 s) |
| [prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K](docs/models/per-model/model-summary-qwen-3-6.md#prithivmlmods-qwen36-35b-a3b-uncensored-aggressive-q6_k) | Hybrid MoE 35B/3B + VL | 28.5 | 65K | Prior lm-studio main (2026-05-02) — uncensored GGUF browse leader (browse 5.05 s, search 13.56 s) |
| [Qwen3.6-35B-A3B 4-bit](docs/models/per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-4-bit) | Hybrid MoE 35B/3B + VL | 22 | 262K (1M YaRN) | dflash-mlx target (74-89 tok/s + DFlash drafter) |
| [Qwen3.6-35B-A3B 6-bit](docs/models/per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-6-bit) | Hybrid MoE 35B/3B + VL | 27 | 262K (1M YaRN) | Vision + hybrid linear attention |

</details>

<details>
<summary>🔀 <strong>MoE</strong> — 15 models</summary>

| Model | Type | Size&#124;GB | Context | Best For |
|:--|:--|--:|--:|:--|
| [DeepSeek-V4-Flash IQ2XXS-imatrix](docs/models/per-model/model-summary-deepseek-v4.md) | MoE 284B/13B-active (256 experts, `deepseek4`) | 81 | 65K (1M model max) | Only Apple-Silicon path for DeepSeek-V4-Flash (`ds4` :8101, MIT) — 284 B knowledge-class model at 2-bit, native DSML tool calling, 25–35 tok/s, smoke 5/5, browse 18.78 s / search 28.22 s |
| [Gemma 4 26B-A4B (4-bit)](docs/models/per-model/model-summary-gemma.md#gemma-4-26b-a4b-4-bit) | MoE 26B/4B | 15 | 256K | Vision + video + reasoning + tool use |
| [lmstudio-community Gemma 4 26B A4B-it Q8_0](docs/models/benchmarks/model-benchmark-tool-call.md#results-lmstudio-community-gemma-4-26b-a4b-it-q8) | MoE 26B/4B active | 25 | 128K | Prior production main (2026-05-07 → 2026-05-10) — Apache 2.0, 70–86 tok/s, **API multi-turn 2.14 s 🏆**, OpenCode scaffolded browse 2.94 s 🥈 / search 7.20 s; bare prompts fail (needs "use webfetch" + literal URL) |
| [mradermacher Huihui Gemma 4 26B A4B Abliterated i1-Q6_K](docs/models/uncen-model/gemma4-26b-a4b-huihui-abliterated-benchmark.md) | MoE 26B/4B active | 22.64 | 65K | Apache 2.0 base, huihui-ai refusal-direction abliteration + mradermacher imatrix Q6_K GGUF (lm-studio); smoke 5/5 + multi-turn **1.93 s** (API-level leader), 91.6 / 72.2 tok/s @ 512 / 32K, **refusal 9/10** mlabonne (first Gemma 4 uncensored to clear 9/10), OpenCode browse **2.55 s 🥇** all-time leader / search 19.59 s (`task` subagent) |
| [Nemotron 3 Nano 30B](docs/models/per-model/model-summary-nemotron.md#nemotron-3-nano-30b-a3b-8-bit) | MoE 32B/3B | 34 | 262K | NVIDIA MoE |
| [Nemotron 3 Super 120B](docs/models/per-model/model-summary-nemotron.md#nemotron-3-super-120b-a12b-45-bit) | MoE 120B/12B | 66.5 | 200K | Mamba-2 hybrid |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | MoE 35B/3B + VL | 19.7 | 262K | Prior vmlx main (stopped 2026-05-02); tool-capable JANGTQ4, 64.9 tok/s @ 512, 52.6 tok/s @ 64K |
| [Qwen3-Coder-30B-A3B Instruct 4-bit](docs/models/per-model/model-summary-qwen-3-coder.md#qwen3-coder-30b-a3b-instruct-4-bit) | MoE 30.5B/3.3B | 17.2 | 262K | Compact coding model |
| [Qwen3.5-122B-A10B 4-bit](docs/models/per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-4-bit) | MoE 122B/10B | 65 | 128K | Full-precision alternative |
| [Qwen3.5-122B-A10B JANG 2S](docs/models/per-model/model-summary-qwen-3-5.md#qwen35-122b-a10b-jang-2s) | MoE 122B/10B | 35 | 200K+ | Compact 122B, instant load |
| [Qwen3.5-35B-A3B JANG 4K](docs/models/per-model/model-summary-qwen-3-5.md#qwen35-35b-a3b-jang-4-bit-mixed-precision) | MoE 35B/3B | 19 | 262K | Fast small MoE *(removed from disk 2026-05-05)* |
| Qwen3.6-35B-A3B JANGTQ2-CRACK | MoE 35B/3B + VL | 11.6 | 262K | Fastest CRACK, quality-impaired (vmlx only) |
| [TrevorJS Gemma 4 26B A4B Uncensored Q8_0](docs/models/uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md) | MoE 26B/4B active | 25 | 65K | Prior lm-studio main (2026-05-03) — EGA abliteration, 87.6 tok/s, browse 2.93 s 🥈 (no scaffolding needed), search 7.35 s 🥇, 8/10 compliance — uncensored search speed leader |
| [unsloth Qwen3.6-35B-A3B UD-Q6_K](docs/models/benchmarks/model-benchmark-tool-call.md#results-unsloth-qwen36-35b-a3b-ud-q6) | MoE 35B/3B | 29.31 | 65K | Prior production main (2026-05-07) — sparse MoE GGUF + Dynamic 2.0 imatrix, decode 44–71 tok/s, browse 4.92 s, search 12.08 s, think-on |
| [huihui-ai Qwen3.6-35B-A3B MTP Q6_K](docs/models/per-model/model-summary-qwen-3-6.md#huihui-ai-qwen36-35b-a3b-claude-47-opus-abliterated-mtp-q6_k) | MoE 35B/3B + MTP heads | 27 | 32K (262K train) | First MoE+MTP in lab — huihui-ai abliteration + Claude 4.7 Opus reasoning distillation + MTP self-drafting, 78.5 tok/s decode, 83% MTP acceptance, 10/10 mlabonne, browse 4.74 s / search 12.11 s on `llama-cpp-mtp` :8100 (mainline `ggml-org/llama.cpp`). [Uncen bench](docs/models/uncen-model/huihui-qwen36-35b-mtp-abliterated-benchmark.md) |
| [Zyphra ZAYA1-8B JANGTQ4](docs/models/per-model/model-summary-zaya1-8b.md) | MoE 8.4B / 760M-active | 4.65 | 131K | Prior production main (2026-05-12 → 2026-05-14, vmlx-swift-lm :1337) — Apache 2.0, top-1 CCA + MoE, `tool_parser=zaya_xml`. HTTP-path decode 7-8 tok/s pending [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) (engine's own `RunBench` reports 57.2 tok/s at the same commit; cask missing JANGTQ B=1 fast path). Also agent-broken at this pin |

</details>

Full specs and per-model details: [Model Summary](docs/models/model-summary.md)

**Quantization key**: *JANG* = adaptive mixed-precision ([jangq.ai](https://jangq.ai)), *MoE* = Mixture of Experts (total/active params), *nvfp4* = NVIDIA 4-bit float.

---

## 📊 Benchmarks

Headline metric is **agent-loop latency** (real `opencode run`), not raw tok/s — agent workloads add 2–4k-token system prompts and multi-turn round-trips, so decode speed alone doesn't predict what a user actually waits for.

**Fastest agent loop** (medians; lm-studio unless noted · API = 3-turn `read→write→summary` · browse = single `webfetch` · search = multi-step Hackernews scrape):

| Model | API loop | Browse | Search |
|:------|:--------:|:------:|:------:|
| Huihui Gemma 4 26B-A4B Abliterated i1-Q6_K | **1.93 s** 🏆 | **2.55 s** 🥇 | 19.59 s |
| TrevorJS Gemma 4 26B-A4B Uncensored Q8_0 | 2.14 s | 2.93 s 🥈 | **7.35 s** 🥇 |
| mlx-community Gemma 4 26B-A4B-it 4-bit MLX | — | 3.29 s | **3.23 s** 🏆 |
| unsloth Qwen3.6-35B-A3B UD-Q6_K GGUF | 7.65 s | 4.92 s | 12.08 s |
| Qwen3.6-35B-A3B Q6_K + TurboQuant `turbo3` (`llama-cpp-turboquant`) | 5.57 s | 6.47 s | 15.64 s |

Sparse-MoE **Gemma 4 26B-A4B** (~4 B active) on lm-studio dominates the agent loop; 30+ models across 10 servers were benchmarked, including ⛔ no-tool / timeout failures.

Full results: [Agent Tool-Call](docs/models/benchmarks/model-benchmark-tool-call.md) · [API Server](docs/models/benchmarks/model-benchmark-api-server.md) · [Standalone](docs/models/benchmarks/model-benchmark-standalone.md) · [TurboQuant KV Cache](docs/models/benchmarks/model-benchmark-turboquant-jang.md)

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
- **vmlx** — JANGTQ only (MLX Studio DMG bundled Python), no GUI but overwritten on every DMG upgrade. MLLM path drops `tools[]`, ignores `tools=` in chat template, and crashes on multi-turn tool replay — fix with [`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`](scripts/patches/patch_vmlx_jangtq_mllm_tools.py) ([detail](docs/servers/vmlx/maintenance.md#tool-use-and-reasoning-mllm-models)). Requires `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 --continuous-batching` (the last flag is mandatory on vmlx 1.5.20+ — without it MLLM/VLM models crash with `Qwen2Tokenizer.stopping_criteria` and `bailing_hybrid` text models crash with `Stream(gpu, 1) not in thread`). [Maintenance](docs/servers/vmlx/maintenance.md)
- **dflash-mlx** — Standard MLX safetensors only (no JANG/JANGTQ/`bailing_hybrid`/GGUF). PyPI 0.1.0 has no tool-calling — install 0.1.4.1+ from `git+https://github.com/bstnxbt/dflash-mlx.git`. One local patch required after install: [`patch_dflash_mlx_serve.py`](scripts/patches/patch_dflash_mlx_serve.py) (two upstream bugs in `DFlashModelProvider`). The mlx-lm tool-detection trie reset patch was retired 2026-05-08 — fix landed upstream in mlx-lm 0.31.3. Built-in `DRAFT_REGISTRY` does not include Qwen3.6 pairs — always pass `--draft-model` explicitly. OpenAI API only. [Runbook](docs/servers/dflash-mlx/summary.md)
- **llama-cpp-mtp** — Two binaries: **mainline `ggml-org/llama.cpp`** (`~/llama-cpp-mainline/`, preferred, MTP merged upstream) and legacy `am17an/llama.cpp@mtp-clean` (`~/llama-cpp-mtp/`, [PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673)). No JANG/JANGTQ/`bailing_hybrid`/MLX. `-np > 1` and `--mmproj` are unsupported with MTP active. The flag is `--spec-type draft-mtp` (not `mtp`); default `--spec-draft-n-max` is 16, must override to 2. Standard `bench_api_server.py` filler prompt at temp=0 triggers a first-token EOS on some MTP quants — use a real-content prompt rig for perf measurement. No Anthropic API. [Runbook](docs/servers/llama-cpp-mtp/summary.md)
- **lm-studio** — Standard MLX / GGUF only (no JANG/JANGTQ/`bailing_hybrid`). Closed-source MLX runtime. `lms get` re-downloads from HuggingFace into `~/.lmstudio/models/` even when present in `~/.cache/huggingface/` (no dedup), and custom HauhauCS `K_P` quants currently mis-resolve through the LM Studio catalog path, so import the exact GGUF with `lms import -L` after direct Hub download. Model IDs are lowercased and org-prefix-stripped on load (`mlx-community/Qwen3.6-27B-6bit` → `qwen3.6-27b`), but `lms load --identifier ...` can pin a stable API name. Default `lms server start` binds to `127.0.0.1`; LAN clients need `--bind 0.0.0.0`. First-time install needs one GUI launch to bootstrap `~/.lmstudio/bin/lms`. [Bench](docs/models/benchmarks/model-benchmark-tool-call.md#server-comparison-lm-studio-vs-vllm-mlx-same-model-file-2026-04-30)
- **comfyui** — Image-generation diffusion runtime, not a chat / agent server. No OpenAI `/v1/images/generations` API — clients can't trigger generations programmatically (web UI only at `:8188`). No JANG / JANGTQ / `bailing_hybrid` support (LLM concepts; doesn't apply to S3-DiT diffusion). Default attention backend errors on MPS — always launch with `--use-pytorch-cross-attention`. AIO checkpoint reload between Distill and Base BF16 variants takes ~25 s warm-up each swap (~19 GiB to MPS). Native MLX would beat MPS by an estimated 2–3× but Z-Anime has no MLX upload. [Runbook](docs/servers/comfyui/summary.md)
- **ds4 (DwarfStar 4)** — Single-model standalone engine for DeepSeek-V4-Flash only (the `deepseek4` arch is unmerged in upstream `llama.cpp`; vLLM/SGLang are CUDA-only; the persadian IQ1_S-XL GGUF's only engine, `arishma108/llama.cpp feat/v4-port-cuda`, has no Metal backend). GGUF-locked to `antirez/deepseek-v4-gguf` — only `q2-imatrix` (81 GB) fits a 96 GB-class machine (`q4-imatrix` 153 GB, batiai Q3–Q8 135–302 GB do not). Default bind is `127.0.0.1`; LAN clients need `--host 0.0.0.0` (`--cors` does not rebind). Cold 32 K prefill ≈ 38 s (disk-KV cuts the warm hit to 6.8 s). Single graph worker, no batching. Alpha-quality engine (days old, GPT-5.5-assisted) — behaviour may change across `git pull`. **Never run the CPU path** (`make cpu` / `--cpu`) — documented macOS VM bug kernel-panics the machine. No JANG/JANGTQ/`bailing_hybrid`/MLX. [Runbook](docs/servers/ds4/summary.md)
- **sglang** — Provisional source install at `~/sglang` with Python 3.11 venv `~/sglang/sglang-mps` and `SGLANG_USE_MLX=1`. OpenAI-compatible sidecar on port `30000`, currently validated for `openbmb/MiniCPM5-1B` with `--tool-call-parser minicpm5`. The exact Q8_0 GGUF does **not** work on SGLang's Apple/MLX backend because the MLX runner expects a model directory with `config.json`; use the HF checkpoint path. MiniCPM5 needs No Think mode (`chat_template_kwargs={"enable_thinking":false}`) for the local API tool harness. OpenCode browse passed; search had one 300 s timeout in 3 measured runs. [Runbook](docs/servers/sglang/summary.md)

**Model compatibility:**
- **Nemotron family** — Only works on vllm-mlx (chat template not packaged in MLX weights). [Details](docs/models/per-model/model-summary-nemotron.md#nemotron-server-compatibility)
- **Mistral Small 4** — Broken on current MLX servers here (missing native `mistral4` MLA support in upstream `mlx-lm`). For Apple Silicon, the practical local path is `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`; Mistral's official full-feature deployment guidance still points to `vLLM`. [Details](docs/models/model-summary.md#mistral-small-4-119b-a6b-jang-2l)
- **Qwen3.5-122B + OpenClaw** — HTTP 500 with large system prompts ([#42](https://github.com/jundot/omlx/issues/42))

**Maintenance:**
- **JANG fork overlay** — `brew upgrade omlx` overwrites the fork; re-apply after every upgrade. [Guide](docs/servers/omlx/jang-fork.md)
- **Hot cache patch** — `scripts/patches/patch_omlx_cache.py` must re-run after every `brew upgrade omlx`. [Guide](docs/servers/omlx/maintenance.md)
- **SSH timeouts** — Fix: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10` on Mac Studio
