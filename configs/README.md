# Client Configs

Client config files for connecting to the Mac Studio M3 Ultra. Templates live under [`configs/clients/`](clients/), organized by server type — see [`clients/README.md`](clients/README.md) for the per-server layout. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` with the real IP.

**Censored vs uncensored:** templates in this folder pin **censored / standard / instruction-tuned** models per server (Ling, Gemma, Osaurus JANGTQ4, Qwen3-Coder, etc.). The matching **uncensored** roster (HauhauCS abliterations, dealignai CRACK variants, NousResearch Hermes, Dolphin, magnum, Huihui, etc.) lives in [`docs/models/uncen-model/client-configs/`](../docs/models/uncen-model/client-configs/). Pick the folder that matches the model class you want to talk to. The **live Mac Studio state** is independent of which template you use — run [`../scripts/chk_llm_macstu.py`](../scripts/chk_llm_macstu.py) to see what's actually running right now (run-state is intentionally not recorded in any doc).

## 🖥️ Server Roles

| Server | Port | Role | Representative model(s) | API Key |
|--------|------|------|----------|---------|
| **vllm-mlx** | 8000 | Fastest single-model inference; most capable for sparse-MoE / `bailing_hybrid` | Ling-2.6-flash mlx-6bit (~80GB) | Not needed |
| **mlx-openai-server / mlx-lm server** | 8000 | mlx-lm direct (single-model with `--draft-model` for MTP/spec-decode) or mlx-openai-server YAML multi-model (trie prompt cache, JANG via `.pth` patch). Launch via Cellar libexec `mlx_lm.server` only | Gemma 4 31B-it MLX 6-bit | Not needed |
| **oMLX** | 8000 | Multi-model — SSD cache, hot-swap, admin dashboard | 9 models (see below) | Required (`<YOUR_API_KEY>`) |
| **vmlx** | 8000 | JANGTQ — only route for TurboQuant-weight (JANGTQ) models; runs out of MLX Studio bundled Python | OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 (~19.7GB) | Not needed |
| **lm-studio** | **1234** | LM Studio headless — standard MLX/GGUF only; built-in tool-call + reasoning parsing; guardrail flip required for large loads (`mode:"high"` → `"off"` → `"high"`) | IBM Granite 4.1 30B Q8_0 (28.57 GiB, Apache 2.0); also Gemma 4 31B-it MLX 6-bit, TrevorJS Gemma 4 26B A4B, prithivMLmods/HauhauCS Aggressive variants | Not needed |
| **ollama** | **11434** | Ollama Apple-Silicon MLX sidecar — OpenAI-compatible endpoint with tool calling; useful for agent-client parity tests | `qwen3.6:35b-mlx` (21 GB, Qwen3.6 35B-A3B MLX, 256K library context) | Not needed |
| **dflash-mlx** | **8098** | DFlash speculative-decoding sidecar — target+drafter pair, wraps `mlx_lm.server` in 0.1.4.1+, requires 3 local patches | Qwen3.6-35B-A3B-4bit + DFlash drafter (~23GB) | Not needed |
| **llama-cpp-turboquant** | **8099** | TurboQuant / RotorQuant / PlanarQuant KV-cache sidecar — two forks installed: `TheTom/llama-cpp-turboquant` (`turbo2/3/4`, auto-asymm `q8_0` K, sparse V dequant, 4-mag LUT) and `johndpope/llama-cpp-turboquant` (`iso3/4`, `planar3/4`). See [`docs/servers/llama-cpp-turboquant/summary.md`](../docs/servers/llama-cpp-turboquant/summary.md) | unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf (~27 GB) | Not needed |
| **llama-cpp-mtp** | **8100** | llama.cpp sidecar for Qwen3.6 MTP self-drafting and mainline GGUF/runtime-LoRA experiments. MTP runs use `--spec-type draft-mtp`; plain GGUF and LoRA runs use mainline `--jinja` without speculative flags. See [`docs/servers/llama-cpp-mtp/summary.md`](../docs/servers/llama-cpp-mtp/summary.md) | unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL (~26 GB); unsloth/Qwen-AgentWorld-35B-A3B-GGUF UD-Q6_K (~27.3 GiB); hotdogs/qwen3.6-27b-fable5-lora over unsloth Qwen3.6-27B Q6_K (~22.5 GB + 76 MB) | Not needed |
| **qwen-asr** | — (no port, Python API only) | Speech-to-text sidecar — `qwen-asr` package in `~/qwen-asr-env/`, transformers + MPS backend. `qwen-asr-serve` daemon is CUDA-only and not usable on Apple Silicon; clients call `Qwen3ASRModel.transcribe(audio=…)` in-process. No client templates ship in `configs/clients/` for this server (no chat client speaks audio). See [`docs/servers/qwen-asr/summary.md`](../docs/servers/qwen-asr/summary.md) | `Qwen/Qwen3-ASR-1.7B` bf16 (4.7 GB) | Not needed |
| **vmlx-swift-lm** | **1337** | MLX-Swift engine via Osaurus macOS cask. Only Mac Studio runtime that natively supports Zyphra ZAYA1 (top-1 CCA + MoE), Hunyuan v3 (Hy3), and the MiniMax-M2.7 JANGTQ kernel optimization. Built-in tool/reasoning parsers (no flags). Independent of port 8000. See [`docs/servers/vmlx-swift-lm/summary.md`](../docs/servers/vmlx-swift-lm/summary.md) | `JANGQ-AI/ZAYA1-8B-JANGTQ4` (8.4B / 760M-active, 4.65 GiB) | Not needed |
| **ds4** | **8101** | DwarfStar 4 standalone native engine (pure C + Metal) — only Apple-Silicon path for DeepSeek-V4-Flash's `deepseek4` architecture (unmerged upstream; vLLM/SGLang CUDA-only). Native DSML ↔ OpenAI/Anthropic/Responses tool-call mapping with exact-DSML replay. GGUF-locked to `antirez/deepseek-v4-gguf`. Independent of port 8000. See [`docs/servers/ds4/summary.md`](../docs/servers/ds4/summary.md) | `antirez/deepseek-v4-gguf` IQ2XXS-imatrix (284B/13B-active, 81 GB) | Not needed |
| **litert-lm** | **9379** | Google LiteRT-LM edge runtime v0.12.0 — alpha OpenAI HTTP server, CPU/XNNPACK only (GPU broken on Apple Silicon). No `tools` param, no GET /v1/models, max ~3K context. Provisional evaluation. See [`docs/servers/litert-lm/summary.md`](../docs/servers/litert-lm/summary.md) | `litert-community/gemma-4-E4B-it-litert-lm` (~4B effective, 3.66 GB) | Not needed |
| **sglang** | **30000** | SGLang source install with Apple-Silicon / MLX backend. Provisional OpenAI-compatible sidecar for models needing SGLang parser support. MiniCPM5 uses `--tool-call-parser minicpm5`; use No Think mode for the local tool harness. See [`docs/servers/sglang/summary.md`](../docs/servers/sglang/summary.md) | `openbmb/MiniCPM5-1B` HF checkpoint (not GGUF) | Not needed |

Only one server can occupy port 8000 at a time (vllm-mlx, mlx-openai-server / mlx-lm server, oMLX, vmlx). **lm-studio (1234), ollama (11434), dflash-mlx (8098), llama-cpp-turboquant (8099), llama-cpp-mtp (8100), vmlx-swift-lm / Osaurus (1337), ds4 (8101), litert-lm (9379), sglang (30000), and qwen-asr (no port) each occupy their own slot** and can coexist with whichever port-8000 server is up — though the experimentation-lab framing in [`CLAUDE.md`](../CLAUDE.md#project) means we usually run only one model at a time to avoid cross-contaminated benchmarks. For what's actually live right now run [`../scripts/chk_llm_macstu.py`](../scripts/chk_llm_macstu.py).

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

**Templates pin the censored Osaurus JANGTQ4 fine-tune.** Default: `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` -- Qwen3.6 MoE+VL (35B total / ~3B active), JANGTQ4 / `mxtq`, ~19.7 GB on disk. API tool harness passes 5/5; OpenCode median is 72.75 s browse and 135.06 s search. Raw results: [`docs/models/benchmarks/logs/qwen36-35b-a3b-jangtq4-osaurus/`](../docs/models/benchmarks/logs/qwen36-35b-a3b-jangtq4-osaurus/). Launch shape: [`docs/servers/vmlx/summary.md`](../docs/servers/vmlx/summary.md).

For uncensored vmlx JANGTQ-CRACK variants use the matching templates under [`docs/models/uncen-model/client-configs/vmlx/`](../docs/models/uncen-model/client-configs/vmlx/). Note: `dealignai/MiniMax-M2.7-JANGTQ-CRACK` and `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` were removed from disk 2026-05-05; `dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK` remains on disk.

Speaks OpenAI + Anthropic + Ollama API on port 8000. No API key required. Runs out of the MLX Studio DMG's bundled Python (`/Applications/vMLX.app/Contents/Resources/bundled-python/python/`) because the TurboQuant loader (`jang_tools.load_jangtq`) and Metal kernels (`turboquant/{tq_kernel,hadamard_kernel,gather_tq_kernel,fused_gate_up_kernel}`) are not distributed via the public pypi `jang` or `vmlx` wheels ([`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5) tracks this).

**Not compatible with**: `--smelt` or `--flash-moe` flags ([`vmlx#81`](https://github.com/jjang-ai/vmlx/issues/81) -- both raise `ValueError` on `weight_format=mxtq`). Use the bundled `python3 -m vmlx_engine.cli serve` invocation only; the bundled `bin/vmlx` shebang points at the maintainer's build tree.

### `client/lm-studio/` -- LM Studio Headless (Standard MLX, Port 1234)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Templates pin censored / standard models on lm-studio.** Default: `granite-4.1-30b-q8` (IBM Granite 4.1 30B Q8_0, dense instruct, Apache 2.0). Also lists `gemma-4-31b-it-mlx` and `qwen3.6-27b`. Ships `opencode.json` and `openclaw-provider.json`; Claude Code, Pi, qwen-code config files remain deferred.

For uncensored lm-studio GGUFs (TrevorJS Gemma 4 31B-it Q4_K_M, TrevorJS Gemma 4 26B A4B Q8_0, prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K, HauhauCS Qwen3.6-35B-A3B Aggressive Q6_K_P, HauhauCS Qwen3.6-27B Balanced Q8_K_P, etc.) use the matching templates under [`docs/models/uncen-model/client-configs/lm-studio/`](../docs/models/uncen-model/client-configs/lm-studio/). Custom K_P quant labels (HauhauCS family) mis-resolve through `lms get` — use direct Hub download + `lms import -L`.

Speaks **OpenAI-compatible** API on port **1234** (NOT 8000). No API key required. Default `lms server start` binds to `127.0.0.1`; LAN clients require `--bind 0.0.0.0`. Tool calling and `<think>` reasoning parsing are built into the MLX runtime — no parser flags needed. Full server runbook: [`docs/servers/lm-studio/summary.md`](../docs/servers/lm-studio/summary.md).

### `clients/vmlx-swift-lm/` -- Osaurus MLX-Swift Engine (Port 1337)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Default model:** `zaya1-8b-jangtq4` — Zyphra ZAYA1-8B in JANGTQ4 format (8.4B total / 760M active, top-1 CCA + MoE, Apache 2.0). **OpenCode template only** — Claude Code, OpenClaw, Pi, qwen-code config files are deferred while this server type is provisional (the JANGTQ HTTP-path regression in Osaurus 0.18.13 / vmlx-swift-lm pin `b9da180` caps decode at ~7-8 tok/s pending [PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057)).

Speaks **OpenAI + Anthropic + Ollama** compatible APIs on port **1337**. No API key. Default bind is `127.0.0.1` — clients on the same Mac use the loopback URL; LAN clients require an `ssh -L` tunnel or the upcoming `--expose` flag landing properly (the current cask flips the runtime flag but doesn't rebind the listener). Tool-call + reasoning parsers are built into the engine — no flags needed (ZAYA emits `zaya_xml`; Qwen/Hermes/Hunyuan have their own parsers). Pulled models live in `~/.osaurus/models/` (not the documented `~/MLXModels`) — set `OSU_MODELS_DIR=$HOME/.osaurus/models` on `osaurus serve`. Full runbook: [`docs/servers/vmlx-swift-lm/summary.md`](../docs/servers/vmlx-swift-lm/summary.md).

### `clients/dflash-mlx/` -- DFlash Speculative-Decoding Sidecar (Standard MLX, Port 8098)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Target:** `mlx-community/Qwen3.6-35B-A3B-4bit` (~22 GB, hybrid MoE 35B/3B + VL). **Drafter:** `z-lab/Qwen3.6-35B-A3B-DFlash` (~1 GB, 0.5B BF16). Standard MLX safetensors — no JANG/JANGTQ/`bailing_hybrid`/GGUF. **Currently OpenCode-only** — Claude Code, OpenClaw, Pi, qwen-code config files have not been added because dflash-mlx is provisional (decode-bound research server; loses to lm-studio on prefill-bound long-context multi-turn workloads).

Speaks **OpenAI-compatible** API on port **8098** (NOT 8000). No API key required. Wraps `mlx_lm.server` in 0.1.4.1+ (PyPI 0.1.0 has no tool-calling — install from `git+https://github.com/bstnxbt/dflash-mlx.git`). Three local patches required: `patch_dflash_mlx_serve.py`, `patch_mlx_lm_match.py`, `patch_dflash_mlx_host.py` (the last only for 0.1.0). The `--draft-model` flag is **required** for Qwen3.6 (built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family). Full server runbook: [`docs/servers/dflash-mlx/summary.md`](../docs/servers/dflash-mlx/summary.md).

### `clients/ds4/` -- DwarfStar 4 Native DeepSeek-V4-Flash Engine (Port 8101)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Model:** `deepseek-v4-flash` — `antirez/deepseek-v4-gguf` IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix (DeepSeek-V4-Flash 284B-total / 13B-active 256-expert `deepseek4` MoE, 81 GB GGUF, MIT). **OpenCode template only** — Claude Code, OpenClaw, Pi, qwen-code deferred while this server type is provisional. This is the **only Apple-Silicon path** for `deepseek4`: upstream `llama.cpp` doesn't implement the architecture, the model card's vLLM/SGLang loaders are CUDA-only, and the persadian IQ1_S-XL GGUF's only engine (`arishma108/llama.cpp feat/v4-port-cuda`) has no Metal backend. Of the antirez quants only `q2-imatrix` (81 GB) fits a 96 GB-class machine.

Speaks **OpenAI + Anthropic + Responses** APIs on port **8101**. No API key. Default bind is `127.0.0.1` — LAN clients require `--host 0.0.0.0` (`--cors` only adds CORS headers, does not rebind). Tool calling is native DSML ↔ OpenAI mapping with an exact-sampled-DSML replay map (no parser flags). Thinking is on by default at "high"; `model=deepseek-chat` / `think=false` selects non-reasoning. Engine is pure C + Metal (`make`, no cmake, no Python, no patches); GGUF-locked to `antirez/deepseek-v4-gguf`. Full server runbook: [`docs/servers/ds4/summary.md`](../docs/servers/ds4/summary.md).

### `clients/sglang/` -- SGLang MLX Sidecar (Port 30000)

| File | Copy to | Used by |
|------|---------|---------|
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |

**Model:** `openbmb/MiniCPM5-1B` — the HF checkpoint served by SGLang's Apple-Silicon / MLX backend. This is **not** the Q8_0 GGUF path: `openbmb/MiniCPM5-1B-GGUF` loads in LM Studio, but SGLang's MLX runner expects a model directory with `config.json` and does not serve the `.gguf` file locally.

Speaks **OpenAI-compatible** API on port **30000**. No API key. Start with `SGLANG_USE_MLX=1` and `--tool-call-parser minicpm5` for MiniCPM5 tool calls. For the local API smoke harness, pass `--chat-template-kwargs '{"enable_thinking":false}'`; default-template MiniCPM5 only partially passes. **OpenCode template only** while this server type is provisional. Full runbook: [`docs/servers/sglang/summary.md`](../docs/servers/sglang/summary.md).

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

# Switch to vllm-mlx (example shape — Ling-2.6-flash mlx-6bit, the most-recently-exercised model)
pkill -f mlx-openai-server; pkill -f vmlx_engine; pkill -f lm-studio; /opt/homebrew/bin/brew services stop omlx; sleep 2
nohup ~/vllm-mlx-env/bin/vllm-mlx serve \
  ~/.cache/huggingface/hub/models--mlx-community--Ling-2.6-flash-mlx-6bit/snapshots/df79bba4bc9d3ea919afd7e017d8d262b0bbc995 \
  --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > /tmp/vllm-mlx.log 2>&1 &

# Switch to vmlx (example shape — Osaurus Qwen3.6-35B-A3B JANGTQ4, bundled-Python headless)
pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &

# Switch to lm-studio (LM Studio headless, port 1234 — separate from port 8000)
# Example shape: load IBM Granite 4.1 30B Q8_0 (already on disk in LM Studio's model registry).
# NOTE: if guardrail blocks load ("insufficient system resources"), temporarily set
#   modelLoadingGuardrails.mode to "off" in ~/.lmstudio/settings.json, load, then restore to "high".
~/.lmstudio/bin/lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors

# To swap to a HauhauCS / prithivMLmods GGUF that LM Studio doesn't auto-resolve via `lms get`,
# download via huggingface_hub then import:
#   python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF', filename='Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf', local_dir='/Users/chanunc/.cache/prithiv-gguf')"
#   ~/.lmstudio/bin/lms import -L --user-repo mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF -y ~/.cache/prithiv-gguf/Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf
#   ~/.lmstudio/bin/lms load qwen3.6-35b-a3b-uncensored-aggressive --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k -y

# Switch to vmlx-swift-lm via Osaurus (port 1337 — independent of port 8000).
# First-time: brew install --cask osaurus; then osaurus pull <hf-repo-id>.
# OSU_MODELS_DIR override is REQUIRED — osaurus pull writes to ~/.osaurus/models/
# but serve defaults to reading ~/MLXModels/ (path-mismatch bug not yet upstreamed).
OSU_MODELS_DIR=$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 \
  > /tmp/osaurus.log 2>&1 &

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

# Switch to ds4 / DwarfStar 4 (port 8101 — independent of port 8000; only DeepSeek-V4-Flash path).
# First-time: git clone https://github.com/antirez/ds4.git && cd ds4 && make -j8;
#             then ./download_model.sh q2-imatrix (81 GB, symlinks ./ds4flash.gguf).
# 81 GB weights on a 96 GB-class box — stop the port-8000 server if it's serving a large model.
cd ~/ds4 && nohup ./ds4-server --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt > /tmp/ds4-server.log 2>&1 &
# Stop: pkill -f 'ds4-server'
```
