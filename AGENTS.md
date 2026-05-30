# AGENTS.md

This file provides guidance to Codex (codex.ai/code) and other agentic CLIs that follow the AGENTS.md convention when working with code in this repository. Content is kept in sync with `CLAUDE.md` — when you edit either, mirror the change to the other.

## Project

Operations notebook for a personal LLM **experimentation lab** on a **Mac Studio M3 Ultra (96GB)**. The work is **running and benchmarking new LLM models, and trying new inference techniques** (DFlash speculative decoding, JANG / TurboQuant quantisation, `bailing_hybrid` MoE, etc.). **There is no "production" model** — whatever is loaded is the latest experiment. Docs capture *what was tried, how it was deployed, and how it benchmarked* so future experiments don't re-discover the same patches and gotchas.

### Servers

Only one of vllm-mlx, mlx-openai-server, oMLX, or vmlx can hold **port 8000** at a time — kill the current before starting another (see Event 4 for pre-benchmark hygiene). All other servers coexist on dedicated ports.

- **vllm-mlx** (8000, OpenAI+Anthropic) — primary sparse-MoE / `bailing_hybrid` server. Venv `~/vllm-mlx-env/`. JANG models need `run_vllm_jang.py` wrapper. Flags: `--enable-auto-tool-choice --tool-call-parser hermes`.
- **mlx-openai-server** (8000, OpenAI) — multi-model YAML config (`~/mlx-openai-server-multimodel.yaml`), trie prompt cache, speculative decoding. Venv `~/mlx-openai-server-env/`. JANG via `.pth` patch (`JANG_PATCH_ENABLED=1`). Incompatible with `bailing_hybrid`. Binary: `/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server` (**not** `/opt/homebrew/bin/mlx_lm.server` — wrong python3.11 install).
- **oMLX** (8000, OpenAI+Anthropic) — Homebrew + AlexTzk fork (PR #364) for JANG. Multi-model with SSD caching. Config in `~/.omlx/` on Mac Studio.
- **vmlx** (8000, OpenAI+Anthropic+Ollama) — MLX Studio bundled Python for JANGTQ/TurboQuant CRACK models. Invoke as `$BP/bin/python3 -m vmlx_engine.cli serve` (**not** bundled `bin/vmlx` — broken shebang). `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python`. `--smelt`/`--flash-moe` incompatible with `weight_format=mxtq`.
- **lm-studio** (1234, OpenAI) — closed-source MLX/GGUF, built-in parsers (no flags needed). Guardrail `"high"` blocks large loads — flip to `"off"` in `~/.lmstudio/settings.json`, load, restore immediately. No JANG/JANGTQ/`bailing_hybrid`.
- **ollama** (11434, OpenAI) — Homebrew Ollama 0.24.0 + `mlx-c`, Apple-Silicon MLX backend. Start with `OLLAMA_HOST=0.0.0.0:11434 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0`. `qwen3.6:35b-mlx` passes API tool smoke 5/5 and OpenCode browse/search with `webfetch`. [Runbook](docs/servers/ollama/summary.md).
- **dflash-mlx** (8098, OpenAI) — DFlash speculative decoding sidecar. Venv `~/dflash-mlx-env/`. Needs `patch_dflash_mlx_serve.py`. `--draft-model` required for Qwen3.6 (DRAFT_REGISTRY auto-resolves Qwen3.5 only). Regresses vs baseline on M3 Ultra — upstream-tracking only. Provisional — `configs/clients/dflash-mlx/opencode.json` only.
- **llama-cpp-turboquant** (8099, OpenAI) — two forks: johndpope (`~/llama-cpp-turboquant/`, iso3/4+turbo2-4+planar3/4) and TheTom (`~/llama-cpp-thetom/`, turbo2-4, auto-asymmetric q8_0 K). **TheTom turbo3 = agent-loop speed leader** (68 tok/s decode, browse 6.47s). johndpope iso3: cold-prefill regression at 32K+. [Runbook](docs/servers/llama-cpp-turboquant/summary.md), [technique](docs/models/techniques/model-technique-rotorquant.md).
- **llama-cpp-mtp** (8100, OpenAI) — MTP self-drafting speculative decoding sidecar. Two binaries: **mainline `ggml-org/llama.cpp`** (`~/llama-cpp-mainline/`, preferred) and legacy `am17an/llama.cpp@mtp-clean` (`~/llama-cpp-mtp/`, [PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673)). Models: unsloth Qwen3.6-27B-MTP UD-Q6_K_XL (dense 27B, 22.9 tok/s), llmfan46 Qwen3.6-27B Heretic v2 MTP Q6_K (dense 27B, 24.6 tok/s, ~74% MTP, Heretic v1.3.0 MPOA abliteration, browse 38.99s), Jackrong Qwopus3.6-27B v2 MTP Q6_K (dense 27B, 25.7 tok/s, browse 16.96s / search 27.62s — fastest dense-27B-MTP in agent loops), huihui-ai Qwen3.6-35B-A3B-MTP Q6_K (MoE 35B/3B, 78.5 tok/s, 83% MTP, browse 4.74s), and LiquidAI LFM2.5-8B-A1B Q8_0 (MoE 8.3B/1.5B, 190 tok/s, no MTP — plain `--jinja`, patched template required, browse 11.1s). `--spec-type draft-mtp --spec-draft-n-max 2` for MTP models. No `--tool-call-parser` — uses `--jinja`. Provisional. [Runbook](docs/servers/llama-cpp-mtp/summary.md), [technique](docs/models/techniques/model-technique-qwen-3-6-mtp.md).
- **mlx-lm** (8080, OpenAI) — ChindaMT-4B Thai↔EN translation sidecar. Model at `~/mlx-models/chindamt-4b-4bit/`. **Model ID must be full absolute path** in API calls (short alias → HF 404). `--chat-template-args '{"enable_thinking":false}'` required (else translation lands in `reasoning`). 186 tok/s, 2.5 GB.
- **vmlx-swift-lm** (1337, OpenAI+Anthropic+Ollama) — MLX-Swift via Osaurus app (`brew install --cask osaurus`). Only runtime for ZAYA1 `ZayaCCACache`. `OSU_MODELS_DIR=$HOME/.osaurus/models` required (path-mismatch bug). JANGTQ HTTP speed-regressed at cask 0.18.13 (7-8 tok/s vs 57 native — fix in PR #1057). [Runbook](docs/servers/vmlx-swift-lm/summary.md).
- **comfyui** (8188, web UI) — ComfyUI 0.20.1 + SeeSee21/Z-Anime (S3-DiT 6B). `--use-pytorch-cross-attention` required on MPS. **No OpenAI API shim** — browser UI only. [Runbook](docs/servers/comfyui/summary.md).
- **ds4** (8101, OpenAI+Anthropic+Responses) — DwarfStar 4, only Apple-Silicon path for DeepSeek-V4-Flash (284B/13B-active `deepseek4` MoE). Built at `~/ds4/` with `make -j8`. Only `q2-imatrix` (81 GB) fits 96 GB. `--host 0.0.0.0` required for LAN. Native DSML tool-call mapping (no parser flags). **Never run CPU path** — kernel-panics macOS. [Runbook](docs/servers/ds4/summary.md).
- **qwen-asr** (no port, Python API) — Qwen3-ASR-1.7B speech-to-text in `~/qwen-asr-env/`. `qwen-asr-serve` is CUDA-only; use `Qwen3ASRModel.transcribe(audio=…)` with MPS. RTF 19.06×. [Runbook](docs/servers/qwen-asr/summary.md).
- **litert-lm** (9379, OpenAI alpha) — Google LiteRT-LM edge runtime v0.12.0. Gemma 4 E4B (~4B, 3.66 GB). CPU/XNNPACK only (GPU produces garbage on Apple Silicon). 71.5 tok/s prefill, 13.85 tok/s decode. No `tools` param, no GET /v1/models, max ~3K context. Provisional. [Runbook](docs/servers/litert-lm/summary.md).
- **sglang** (30000, OpenAI) — SGLang source install with Apple-Silicon / MLX backend. Venv `~/sglang/sglang-mps/`. Provisional MiniCPM5 parser path: `SGLANG_USE_MLX=1`, `--tool-call-parser minicpm5`, model `openbmb/MiniCPM5-1B` (HF checkpoint, not GGUF). Exact Q8_0 GGUF fails under MLX runner (`config.json` directory expected). No Think mode required for local tool harness. [Runbook](docs/servers/sglang/summary.md).

**Skills:** `/deploy-run-benchmark-uncen-model` automates uncensored model deploys (HauhauCS, dealignai-CRACK, Hermes, Dolphin, abliterated, magnum) — runs Events 3+4+6. `/deploy-run-benchmark-model` handles both censored and uncensored.

**Data flow:**
```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
  Claude Code                            vllm-mlx :8000          ┐
  OpenCode                               mlx-openai-server :8000  │  one at a time
  OpenClaw                               oMLX (multi-model) :8000 │  on port 8000
  Pi                                     vmlx (JANGTQ) :8000     ┘
                                         lm-studio :1234
                                         ollama :11434
                                         dflash-mlx :8098
                                         llama-cpp-turboquant :8099
                                         llama-cpp-mtp :8100
                                         vmlx-swift-lm / Osaurus :1337
                                         mlx-lm (ChindaMT) :8080
                                         qwen-asr (no port)
                                         comfyui (web UI) :8188
                                         ds4 / DwarfStar 4 :8101
                                         litert-lm (Gemma 4 E4B) :9379
                                         sglang (MiniCPM5 parser) :30000
```

SSH aliases: `macstudio` (LAN), `macstudio-ts` (Tailscale), `narutaki` (Linux client). Use `macstudio-ts` when connected over Tailscale.

**Client configs** (`configs/clients/<server>/`): organized by server type. IPs/keys stored as placeholders (`<MAC_STUDIO_IP>`, `<YOUR_API_KEY>`) — never commit real values.

**Scripts** (`scripts/`): `bench/` for benchmark drivers, `patches/` for monkey-patches (re-apply after upstream upgrades), top-level for client helpers. See `scripts/README.md`.

**Plans** (`plans/`): `active/` → `done/` → `archive/`. Non-canonical research docs. See `plans/README.md`.

**Live run-state is not tracked** — run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) to check. No doc may assert which model is "current" / "primary" / "production".

## Common Commands

```bash
# SSH
ssh macstudio                # LAN
ssh macstudio-ts             # Tailscale
ssh narutaki                 # Linux client

# Health check
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool                                            # vllm-mlx (no key)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool  # oMLX (needs key)

# Start vllm-mlx — qwen3_coder parser handles XML tool calls; qwen parser does NOT work
ssh macstudio "nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M \
  --served-model-name JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &"

# Switch to mlx-openai-server
ssh macstudio "pkill -f vllm-mlx; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &"

# Switch to oMLX
ssh macstudio "pkill -f mlx-openai-server; pkill -f vllm-mlx; pkill -f vmlx_engine; sleep 2; /opt/homebrew/bin/brew services start omlx"

# Switch to vmlx — tool-call-parser + reasoning-parser required, else raw XML in content
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204; \
  nohup \$BP/bin/python3 -m vmlx_engine.cli serve \$SNAP --host 0.0.0.0 --port 8000 \
    --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
    --continuous-batching > /tmp/vmlx.log 2>&1 &"

# Switch back to vllm-mlx (kill others first, then start vllm-mlx as above)
ssh macstudio "pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2"

# lm-studio (port 1234) — guardrail dance for large models, substitute modelKey + identifier
ssh macstudio "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='off'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y; \
  python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='high'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
ssh macstudio "~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all"  # stop

# ollama (port 11434) — Apple-Silicon MLX backend; qwen3.6:35b-mlx passes OpenCode tools
ssh macstudio "nohup env OLLAMA_HOST=0.0.0.0:11434 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 \
  /opt/homebrew/opt/ollama/bin/ollama serve > /tmp/ollama.log 2>&1 &"
ssh macstudio "/opt/homebrew/opt/ollama/bin/ollama pull qwen3.6:35b-mlx"
ssh macstudio "pkill -f '/opt/homebrew.*/ollama serve'; pkill -f 'ollama runner'"  # stop

# dflash-mlx (port 8098) — apply patch first: ~/dflash-mlx-env/bin/python scripts/patches/patch_dflash_mlx_serve.py
ssh macstudio "nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512 > /tmp/dflash-mlx.log 2>&1 &"
ssh macstudio "pkill -f dflash-serve"  # stop

# vmlx-swift-lm / Osaurus (port 1337) — OSU_MODELS_DIR required
ssh macstudio "OSU_MODELS_DIR=\$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 > /tmp/osaurus.log 2>&1 &"
ssh macstudio "/opt/homebrew/bin/osaurus stop; pkill -9 osaurus 2>/dev/null"  # stop

# llama-cpp-mtp (port 8100) — spec-type is draft-mtp NOT mtp, draft-n-max must be 2
# Mainline binary (preferred) — huihui-ai MoE 35B/3B MTP Q6_K
ssh macstudio "GGUF=~/.cache/huggingface/hub/models--huihui-ai--Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF/snapshots/main/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-Q6_K.gguf; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type draft-mtp --spec-draft-n-max 2 --host 0.0.0.0 --port 8100 \
    --alias huihui-qwen36-35b-mtp-abliterated-q6k --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &"
# Legacy binary — unsloth dense 27B MTP UD-Q6_K_XL
ssh macstudio "GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf; \
  nohup ~/llama-cpp-mtp/build/bin/llama-server -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type draft-mtp --spec-draft-n-max 2 --host 0.0.0.0 --port 8100 \
    --alias qwen3.6-27b-mtp-ud-q6kxl --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &"
# LiquidAI LFM2.5-8B-A1B Q8_0 (no MTP, 190 tok/s, patched template — see docs/models/per-model/model-summary-lfm2.md)
ssh macstudio "GGUF=~/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q8_0-fixed.gguf; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 65536 \
    --host 0.0.0.0 --port 8100 --alias lfm2.5-8b-a1b-q8 --jinja --reasoning-format auto \
    > /tmp/lfm-q8fixed.log 2>&1 &"
ssh macstudio "pkill -f 'llama-cpp-mainline/build/bin/llama-server'; pkill -f 'llama-cpp-mtp/build/bin/llama-server'"  # stop

# comfyui (port 8188) — --use-pytorch-cross-attention required on MPS
ssh macstudio "nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py \
  --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention > /tmp/comfyui.log 2>&1 &"
ssh macstudio "pkill -f 'comfyui/main.py'"  # stop

# mlx-lm / ChindaMT (port 8080) — model ID must be full path, thinking must be off
ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/mlx-models/chindamt-4b-4bit --host 0.0.0.0 --port 8080 \
  --chat-template-args '{\"enable_thinking\":false}' > /tmp/chindamt.log 2>&1 &"
ssh macstudio "pkill -f 'mlx_lm.server.*chindamt'"  # stop

# ds4 / DwarfStar 4 (port 8101) — --host 0.0.0.0 required, NEVER use CPU path
ssh macstudio "cd ~/ds4 && nohup ./ds4-server --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt > /tmp/ds4-server.log 2>&1 &"
ssh macstudio "pkill -f 'ds4-server'"  # stop

# litert-lm (port 9379) — Google edge runtime, CPU/XNNPACK only
ssh macstudio "export PATH=\"/Users/chanunc/.local/bin:\$PATH\" && \
  nohup litert-lm serve --api openai --host 0.0.0.0 --port 9379 --verbose \
  > /tmp/litert-lm.log 2>&1 &"
ssh macstudio "pkill -f 'litert-lm serve'"  # stop

# sglang (port 30000) — MiniCPM5 tool parser path, HF checkpoint only (not GGUF)
ssh macstudio "cd ~/sglang && . sglang-mps/bin/activate && \
  nohup env SGLANG_USE_MLX=1 python -m sglang.launch_server \
    --model-path openbmb/MiniCPM5-1B \
    --tool-call-parser minicpm5 \
    --host 0.0.0.0 --port 30000 > /tmp/sglang-minicpm5.log 2>&1 &"
ssh macstudio "pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'"  # stop

# View logs
ssh macstudio "tail -20 /tmp/vllm-mlx.log"            # vllm-mlx
ssh macstudio "tail -20 /tmp/mlx-openai-server.log"    # mlx-openai-server
ssh macstudio "tail -20 ~/.omlx/logs/server.log"       # oMLX
ssh macstudio "tail -20 /tmp/vmlx.log"                 # vmlx
ssh macstudio "tail -20 /tmp/dflash-mlx.log"           # dflash-mlx
ssh macstudio "tail -20 /tmp/llama-cpp-mtp.log"        # llama-cpp-mtp
ssh macstudio "tail -20 /tmp/chindamt.log"             # mlx-lm / ChindaMT
ssh macstudio "tail -20 /tmp/comfyui.log"              # comfyui
ssh macstudio "tail -20 /tmp/osaurus.log"              # Osaurus
ssh macstudio "tail -20 /tmp/ds4-server.log"           # ds4
ssh macstudio "tail -20 /tmp/litert-lm.log"            # litert-lm
ssh macstudio "tail -20 /tmp/sglang-minicpm5.log"       # sglang

# Upgrades
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent  # MacBook
ssh macstudio "/opt/homebrew/bin/brew upgrade omlx"               # Mac Studio
```

## Editing Workflow

### Sync Policy

**Run-state is deliberately not recorded in any doc** — the Mac Studio is a personal machine. Check what's running via [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py). Docs track the *catalog* in evergreen terms.

**Hard rule:** No doc may assert which model/server is "current", "primary", "production", "currently running", or "stopped".

#### Canonical layers

1. **Sub-root README.md indexes** — update the folder's README.md when adding/removing/renaming files:

   | Folder | README | Indexes |
   |:--|:--|:--|
   | `docs/servers/` | [`docs/servers/README.md`](docs/servers/README.md) | Server runbooks + maintenance |
   | `docs/models/` | [`docs/models/README.md`](docs/models/README.md) | Catalog, `per-model/`, `techniques/`, `benchmarks/`, `how-to/` |
   | `docs/clients/` | [`docs/clients/README.md`](docs/clients/README.md) | Client setup ↔ template mapping |
   | `docs/server-apis/` | [`docs/server-apis/README.md`](docs/server-apis/README.md) | Wire-protocol references |
   | `configs/` | [`configs/README.md`](configs/README.md) | Server Roles + Switching Servers |
   | `configs/clients/` | [`configs/clients/README.md`](configs/clients/README.md) | Per-server template layout |
   | `scripts/` | [`scripts/README.md`](scripts/README.md) | `bench/`, `patches/`, `switch_opencode_config.py` |
   | `plans/` | [`plans/README.md`](plans/README.md) | `active/`, `done/`, `archive/` |

2. **Top-level docs** — `README.md`, `CLAUDE.md`, `AGENTS.md`. CLAUDE.md and AGENTS.md must stay content-identical except for lines 1–3.

#### Event 1: New server type

Update in the same commit:
- `README.md` — data flow, Quick Start, Health Check, Servers table, maintenance, Known Limitations
- `CLAUDE.md` **+ `AGENTS.md`** — server bullet, data flow, Common Commands. Mirror edits.
- `configs/README.md` — Server Roles row, `clients/<name>/` section, Switching Servers
- `configs/clients/<name>/opencode.json` (minimum; other clients deferred)
- `configs/clients/README.md` — Layout table row
- `scripts/switch_opencode_config.py` — append to `SERVERS` list
- `docs/servers/<name>/summary.md` — full runbook
- `docs/servers/README.md` — index row + Maintenance if applicable

If the new server doesn't support JANG/JANGTQ/`bailing_hybrid`, update the "All servers except lm-studio support JANG…" line in `README.md`.

#### Event 2: Model swap

No documentation cascade. Run-state is not tracked. If the model is new, catalog per Event 3. If benchmarked, record per Event 4. `configs/clients/<server>/*.json` model fields track the *compatible roster*, not the live model.

#### Event 3: New model

**Precondition — read the family doc first** under `docs/models/per-model/`:

| Family | Doc |
|:--|:--|
| Qwen3.6 | [`model-summary-qwen-3-6.md`](docs/models/per-model/model-summary-qwen-3-6.md) — parser flags, K_P trap, guardrail dance |
| Qwen3.5 | [`model-summary-qwen-3-5.md`](docs/models/per-model/model-summary-qwen-3-5.md) |
| Qwen3-Coder | [`model-summary-qwen-3-coder.md`](docs/models/per-model/model-summary-qwen-3-coder.md) |
| Qwen3-ASR | [`model-summary-qwen3-asr.md`](docs/models/per-model/model-summary-qwen3-asr.md) |
| Gemma 4 | [`model-summary-gemma.md`](docs/models/per-model/model-summary-gemma.md) — bf16+MTP streaming hang |
| Granite 4.1 | [`model-summary-granite-4.1.md`](docs/models/per-model/model-summary-granite-4.1.md) |
| Ling / `bailing_hybrid` | [`model-summary-ling.md`](docs/models/per-model/model-summary-ling.md) — 3 patches, mlx-openai-server incompatible |
| MiMo V2.5 | [`model-summary-mimo-v2.5.md`](docs/models/per-model/model-summary-mimo-v2.5.md) |
| NemotronH | [`model-summary-nemotron.md`](docs/models/per-model/model-summary-nemotron.md) |
| ZAYA1 | [`model-summary-zaya1-8b.md`](docs/models/per-model/model-summary-zaya1-8b.md) — Osaurus only |
| HyperNova | [`model-summary-hypernova.md`](docs/models/per-model/model-summary-hypernova.md) — analysis only |

If no family doc exists and the deploy uncovers non-trivial gotchas, create one. One-off variants go in the family doc, not their own file.

Update checklist:
- `docs/models/model-summary.md` — Index entry + per-model section with standard spec table
- `docs/models/per-model/model-summary-<slug>.md` — only if >150 lines of detail needed
- `docs/models/README.md` — Per-model deep dives row if `per-model/` file created
- `README.md` Models table — size, context, "Best For", link
- `configs/clients/<server>/*.json` — add to `models` map (oMLX = all 4 files)
- No "now primary" markers — see Event 2
- **Deploy + benchmark**: do Event 4 pre-benchmark hygiene first

Technique docs → `docs/models/techniques/`; server integration steps → `docs/servers/<server>/`. See Events 5–7.

#### Event 4: New benchmark

**Pre-benchmark hygiene (mandatory):** stop all Mac Studio LLM servers first.
```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx|sglang.launch_server|sglang serve' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

Do **not** restore the prior model after. Do not update any doc to reflect live state.

Recording results from `bench_api_server.py`, `bench_api_tool_call.py`, or `bench_agent_tool_call.py`:
- Raw JSON → `docs/models/benchmarks/logs/<model-slug>/<benchmark-type>.json`
- Summary row → `docs/models/benchmarks/model-benchmark-<type>.md`
- New extremes → update README Benchmarks headlines
- Impactful findings → update `model-summary.md` caveats (evergreen)

#### Events 5–7: Scripts / Plans / Techniques

- **Scripts** — `scripts/bench/` for benchmarks, `scripts/patches/` for monkey-patches, top-level for helpers. Update `scripts/README.md`. Link patches from server runbooks. On rename: `grep -rn "scripts/<old-name>" --include="*.md" --include="*.json" --include="*.py"`.
- **Plans** — new at `plans/active/plan-<slug>.md`; completed → `plans/done/`; abandoned → `plans/archive/`. Update `plans/README.md` index. Plans never claim live state.
- **Techniques** — canonical references in `docs/models/techniques/` with prefix `model-technique-`, `model-quantization-`, or `model-architecture-`. Add to `docs/models/techniques/README.md` index. Server-specific steps go in server runbooks. Update technique file (not per-model files) for regressions.

### Pre-commit drift check

```bash
grep -n "<old-model-name>\|<old-primary>" README.md AGENTS.md CLAUDE.md configs/README.md docs/models/model-summary.md
grep -rn "current production\|production main\|production primary\|currently running\|currently stopped\|Last main\|Active model:" README.md AGENTS.md CLAUDE.md configs/README.md docs/ || true
```

### Server-specific config rules

- **oMLX** (`configs/clients/omlx/`): sync all 4 files (`opencode.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json`) + README Models table + `model-summary.md`. `claude-code-settings.json` only if default changes.
- **mlx-openai-server**: stable superset of compatible model IDs, not a live mirror. Update only when compatible set changes.
- **vllm-mlx**: single-model, update only if primary changes.
- **vmlx**: update model ID across all 4 files + README when served JANGTQ model changes.
- **lm-studio**: full 5-file template set. `claude-code-settings.json` uses OpenAI-compat env-var path (LM Studio doesn't speak Anthropic API).
- **Mac Studio** `~/.omlx/model_settings.json`: edited via SSH, separate from client configs.

## oMLX Limitations

- No GGUF — MLX safetensors and JANG only
- MXFP8 unconfirmed — use 4/6/8-bit MLX
- JANG + Nemotron-H: matmul shape mismatch (PR #364 weight mapping bug)
- Qwen3.5-122B + OpenClaw: HTTP 500 with large system prompts ([#42](https://github.com/jundot/omlx/issues/42))
- Dense 27B + OpenClaw: too slow (no MoE sparsity)
- Starlette 1.0 dashboard bug: `pip install "starlette==0.46.2"` ([#361](https://github.com/jundot/omlx/issues/361))

## Known Issues

- **SSH timeouts**: `sudo pmset -a sleep 0 disksleep 0 displaysleep 10` on Mac Studio
- **Hot cache patch**: `scripts/patches/patch_omlx_cache.py` — re-apply after `brew upgrade omlx`. In v0.2.20, `parse_size` moved to `omlx.config`.
- **JANG fork overlay**: AlexTzk/omlx PR #364 over Homebrew v0.2.20. `brew upgrade omlx` overwrites — re-apply fork + patches.
- **vmlx shebang**: always `$BP/bin/python3 -m vmlx_engine.cli serve`, never `bin/vmlx`. Re-applies on DMG upgrade.
- **vmlx MLLM tools-dropped**: `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` for `is_mllm=True` models. Re-apply after DMG upgrade. [Details](docs/models/techniques/model-quantization-turboquant.md#mllm-tool-use-bugs).
- **dflash-mlx patches**: `patch_dflash_mlx_serve.py` required (+ `patch_dflash_mlx_host.py` on 0.1.0). Install from git main, not PyPI. Qwen3.6 needs explicit `--draft-model`. [Details](docs/models/techniques/model-technique-dflash.md).
- **llama-cpp-turboquant**: `-fa on` not bare `-fa`. iso3 cold-prefill >600s at 32K. [Details](docs/models/techniques/model-technique-rotorquant.md).
- **Ling-2.6-flash**: 3 patches (vendor bailing_hybrid.py PR #1227, threadlocal-stream, inline-gen). `--tool-call-parser hermes` not qwen3. 64K max (128K OOMs). mlx-openai-server incompatible. [Details](docs/models/techniques/model-architecture-bailing-hybrid.md).
- **bench_agent_tool_call.py PWD**: OpenCode 1.14.50+ reads `PWD` not `cwd`; bench sets `env["PWD"] = cwd`. [Details](docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md#bench-rig-regression-discovered-during-this-deploy-2026-05-14).
