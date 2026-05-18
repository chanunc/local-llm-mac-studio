# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This repo is the operations notebook for a personal LLM **experimentation lab** on a **Mac Studio M3 Ultra (96GB)**. The work is **running and benchmarking new LLM models, and trying new inference techniques** (DFlash speculative decoding, JANG / TurboQuant quantisation, `bailing_hybrid` MoE, etc.) against whichever server best supports them. **There is no "production" model** — whatever model is currently loaded on a given server is the latest experiment, and is expected to be swapped out for the next one. Docs capture *what was tried, how it was deployed, and how it benchmarked* so future experiments don't re-discover the same patches and gotchas.

The available servers on the Mac Studio are:

- **vllm-mlx** (port 8000, OpenAI + Anthropic API) — most capable server for sparse-MoE / `bailing_hybrid` work. Exercised with `mlx-community/Ling-2.6-flash-mlx-6bit` (104B/7.4B-active, ~80 GB), which needed three local patches — see Known Issues.
- **lm-studio** (LM Studio headless, port 1234, OpenAI only) — closed-source MLX/GGUF runtime with built-in tool-call + reasoning parsing (no parser flags). No JANG / JANGTQ / `bailing_hybrid`. Default `modelLoadingGuardrails.mode: "high"` blocks loading models > ~25 % of unified memory; flip to `"off"` in `~/.lmstudio/settings.json` for the load and restore `"high"` immediately. Models loaded via `~/.lmstudio/bin/lms load <name> --identifier <id> --gpu max --context-length <n>`; server bound LAN-wide via `~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors`.
- **dflash-mlx** (port 8098, OpenAI only) — DFlash speculative-decoding sidecar for single-shot decode-bound experiments. Standalone benchmarks on M3 Ultra (2026-05-01) show DFlash *regressing* vs baseline `mlx_lm` at 1k–4k token horizons; upstream's 1.33× speedup claim is M5-Max-specific. Kept as an upstream-feature-tracking sidecar, not a throughput win.
- **mlx-openai-server / mlx-lm server** (port 8000, OpenAI only) — two distinct entry points sharing the same MLX `mlx_lm` core. **mlx-lm direct**: `/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server` (Cellar libexec binary, **not** `/opt/homebrew/bin/mlx_lm.server` — that symlink resolves to a python3.11 mlx_lm install missing Gemma 4 support); single-model with `--draft-model` for MTP / speculative decoding, no parser flags needed for Gemma. **mlx-openai-server**: YAML-driven multi-model with trie-based prompt caching, speculative decoding, JANG support via `.pth` patch (`JANG_PATCH_ENABLED=1`); incompatible with `bailing_hybrid` (deeper thread coupling). Gemma 4 31B-it bf16 + `gemma4_assistant` MTP drafter via mlx-vlm 0.5.0 from main (PRs #1112/#1115/#1117) is documented as agent-incompatible: drafter runs at upstream-expected efficiency but mlx-vlm streaming hangs on long-reasoning prompts and bf16 decode budget exceeds opencode's 300 s wall — full analysis in [`docs/models/per-model/model-summary-gemma.md`](docs/models/per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment).
- **oMLX** (port 8000, OpenAI + Anthropic API) — multi-model server with SSD caching when model variety matters.
- **vmlx** (port 8000) — bundled-Python path for JANGTQ / TurboQuant CRACK models the public `jang-tools` package can't yet serve.
- **llama-cpp-turboquant** (port 8099, OpenAI only) — provisional **sidecar** with **two forks installed**: (a) [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant) `feature/planarquant-kv-cache` at `~/llama-cpp-turboquant/` (supports `iso3/4`, `turbo2/3/4`, `planar3/4`); (b) [`TheTom/llama-cpp-turboquant`](https://github.com/TheTom/llama-cpp-turboquant) `feature/turboquant-kv-cache` at `~/llama-cpp-thetom/` (`turbo2/3/4` only, auto-asymmetric `q8_0` K dispatch, 4-magnitude LUT for pre-M5, sparse V dequant). Both built 2026-05-06; **TheTom's `turbo3` is the runaway winner**: smoke 4/5 + multi-turn 5.57 s, **decode 68 tok/s @ 512 / 44 tok/s @ 32 K (warm)**, **OpenCode browse 6.47 s 🥇 / search 15.64 s 🥇** — beats Gemma 4 by 2.07× / 2.27× and is the new agent-loop speed leader. johndpope's `iso3` had cold-prefill regression at 32 K+ (>600 s timeout); TheTom's fork fixes it (29.88 s @ 32 K cold). Full analysis: [`docs/models/techniques/model-technique-rotorquant.md`](docs/models/techniques/model-technique-rotorquant.md) and [`docs/servers/llama-cpp-turboquant/summary.md`](docs/servers/llama-cpp-turboquant/summary.md).

- **llama-cpp-mtp** (port 8100, OpenAI only) — provisional **sidecar** built from [`am17an/llama.cpp@mtp-clean`](https://github.com/am17an/llama.cpp/tree/mtp-clean) ([PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673), unmerged upstream). Runs `unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL` (dense 27 B + MTP self-drafting heads in a single 26 GB GGUF) as the only Apple-Silicon path for Qwen3.6 Multi-Token Prediction. Patch-free apart from the build. **84–89 % MTP draft acceptance** (`draft-mtp` self-drafting), decode 22.9 → 20.0 tok/s @ 414 → 29 128 input tokens, smoke 5/5 single-call + 3-turn multi 21.92 s, OpenCode browse 35.98 s / search 35.24 s (slower than the lm-studio Q4_K_M baseline — MTP's ~1.5–2× speedup doesn't close the dense-27 B-Q6 weight-bundle gap). Server flag is `--spec-type draft-mtp` (not `mtp`), `--spec-draft-n-max` must be set to 2 (default 16 drops acceptance to ~50 %); `-np > 1` and `--mmproj` are unsupported with MTP active (no multi-pipeline, no vision). Standard `bench_api_server.py` filler prompt at temp=0 triggers a first-token EOS specific to this 6-bit MTP quant; custom real-content prompt rig used for perf. Full analysis: [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](docs/models/techniques/model-technique-qwen-3-6-mtp.md) and [`docs/servers/llama-cpp-mtp/summary.md`](docs/servers/llama-cpp-mtp/summary.md).

- **mlx-lm** (port 8080, OpenAI only) — lightweight single-model sidecar running `iapp/ChindaMT-4B` (Apache-2.0) as a dedicated Thai ↔ English machine translation endpoint. Model is a Qwen3.5-4B fine-tune with a **hybrid linear-attention + full-attention architecture** (24/32 layers are Mamba-style SSM; 8/32 are standard full attention) — this makes it incompatible with llama.cpp runtimes that lack SSM support. Converted from BF16 HF safetensors to MLX 4-bit (2.2 GB) at `~/mlx-models/chindamt-4b-4bit/`. **Conversion note:** mlx-lm 0.31.3's `qwen3_5` outer `sanitize()` does not pop `language_model.lm_head.weight` (tied embedding) before delegating to the inner sanitize; the stripped source is at `~/mlx-models/chindamt-4b-fixed-hf/`. **Chat template quirk:** the Qwen3.5 template opens a `<think>` block by default, so the translation appears in `message.reasoning` instead of `message.content`. Disable thinking server-wide with `--chat-template-args '{"enable_thinking":false}'` at launch (preferred); or per-request via `chat_template_kwargs: {"enable_thinking": false}` in the JSON body. **Model ID gotcha:** `mlx_lm.server` uses the exact string passed to `--model` as the model ID in `/v1/models` and routing — always send the full absolute path (`/Users/chanunc/mlx-models/chindamt-4b-4bit`) in API calls and client configs, not a short alias (short aliases trigger a HuggingFace 404). Decode **186 tok/s**, 2.5 GB peak memory — fits alongside any main model. Does not displace port 8000 / 1234 / 8098 / 8099 / 8100 / 1337 / 8188. Launch: `nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server --model ~/mlx-models/chindamt-4b-4bit --host 0.0.0.0 --port 8080 --chat-template-args '{"enable_thinking":false}' > /tmp/chindamt.log 2>&1 &`. Stop: `pkill -f 'mlx_lm.server.*chindamt'`. Runbook: [`docs/models/model-summary.md#chindamt-4b-thai--english-translation`](docs/models/model-summary.md#chindamt-4b-thai--english-translation).

- **qwen-asr** (no port, Python API only) — speech-to-text sidecar for **Qwen3-ASR** (Apache-2.0, released 2026-01-30). Variant: `Qwen/Qwen3-ASR-1.7B` bf16 (4.7 GB), 30 langs + 22 Chinese dialects, ≤ 5 min audio. Runs out of `~/qwen-asr-env/` on the transformers + MPS path. The package's `qwen-asr-serve` CLI requires CUDA-vLLM and **does not start on Apple Silicon**, so there's no `/v1/audio/transcriptions` endpoint — clients call `Qwen3ASRModel.transcribe(audio=…)` in-process. M3 Ultra MPS hits **RTF 19.06×** on a 15 s English clip (~13 % of Qwen's H100 RTFx 147.93). Quantization avoided on purpose: weights are already small (4.7 GB), and ASR is WER-sensitive (community 4-bit/8-bit uploads have no published WER baselines). Doesn't compete with the chat servers for any port. Full runbook: [`docs/servers/qwen-asr/summary.md`](docs/servers/qwen-asr/summary.md). Quantization + server-fit analysis: [`docs/models/per-model/model-summary-qwen3-asr.md`](docs/models/per-model/model-summary-qwen3-asr.md).

- **vmlx-swift-lm** (port 1337, OpenAI + Anthropic + Ollama API) — MLX-Swift inference engine consumed via the **Osaurus** macOS app (`brew install --cask osaurus`). Engine repo: [`osaurus-ai/vmlx-swift-lm`](https://github.com/osaurus-ai/vmlx-swift-lm) — a fork of `ml-explore/mlx-swift-lm` with BatchEngine, multi-tier KV cache (L1 paged + L2 SQLite + SSM-companion), TurboQuant KV compression, speculative decoding, JANG mixed-precision, plus model families absent from the upstream: Gemma 4, Mistral Small 4, Qwen 3.5 / 3.6, DeepSeek-V4, NemotronH, Hunyuan v3, MiniMax M2.7, **ZAYA / ZAYA1-VL**. **Only Mac Studio runtime that natively implements Zyphra ZAYA1's `ZayaCCACache` contract** — top-1 CCA + MoE doesn't run on stock `mlx_lm` ([PR #1261](https://github.com/ml-explore/mlx-lm/pull/1261) in review) or `llama.cpp` ([issue #22776](https://github.com/ggml-org/llama.cpp/issues/22776) open). Tool-call + reasoning parsers are built into the engine per family (no `--tool-call-parser` flags). Two operational gotchas: (1) `osaurus pull` writes to `~/.osaurus/models/` but `osaurus serve` reads `~/MLXModels/` — always set `OSU_MODELS_DIR=$HOME/.osaurus/models` on launch; (2) `osaurus serve --expose --yes` flips `exposeToNetwork: true` in the runtime config but leaves the listener on 127.0.0.1 — LAN clients need an `ssh -L` tunnel. JANGTQ HTTP-path is speed-regressed at cask 0.18.13's pin `b9da180` (Swift `RunBench` reports 57 tok/s on ZAYA1 JANGTQ4 but the OpenAI HTTP path delivers 7-8 tok/s because the cask is missing the `BatchEngine.generate` B=1 fast path + JANGTQ Hadamard kernel optimization — fix queued in [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057), bumping the engine pin to `cb8b3df`). Independent of port 8000, coexists with every other server. Full runbook: [`docs/servers/vmlx-swift-lm/summary.md`](docs/servers/vmlx-swift-lm/summary.md). Per-model writeup: [`docs/models/per-model/model-summary-zaya1-8b.md`](docs/models/per-model/model-summary-zaya1-8b.md).

- **comfyui** (port 8188, web UI only) — image-generation sidecar built on `comfyanonymous/ComfyUI` 0.20.1, installed via `comfy-cli` into `~/comfyui/.venv/` (PyTorch 2.11.0 + MPS). Model: `SeeSee21/Z-Anime` — full fine-tune of Alibaba's Tongyi-MAI Z-Image (S3-DiT Single-Stream Diffusion Transformer, 6B params, Apache-2.0). Two AIO BF16 variants on disk (~19 GiB each) at `~/comfyui/models/checkpoints/`: Distill-4-step (4 steps, CFG 1.0 — fast iteration) and Base (28+ steps, CFG 3–9 — best quality). Wall time @ 1024² on M3 Ultra: **Distill 17.75 s** / **Base 28-step 235.16 s** (per-step cost 4.4 s @ CFG 1, 8.4 s @ CFG > 1; CFG > 1 doubles forward-pass compute). End-user path is the browser UI at `http://<MAC_STUDIO_IP>:8188`; **no OpenAI `/v1/images/generations` shim** — chat clients (OpenCode, llm CLI, Lobehub) cannot trigger generations. Native MLX would beat MPS by an estimated 2–3× but Z-Anime has no MLX upload. `--use-pytorch-cross-attention` is required at launch (default attention errors on MPS). Full runbook: [`docs/servers/comfyui/summary.md`](docs/servers/comfyui/summary.md). Bench: [`docs/models/benchmarks/logs/z-anime/wall-time-comfyui.md`](docs/models/benchmarks/logs/z-anime/wall-time-comfyui.md).

- **ds4** (port 8101, OpenAI + Anthropic + Responses APIs) — "DwarfStar 4" ([`antirez/ds4`](https://github.com/antirez/ds4)), a **standalone single-model native C+Metal engine written specifically for DeepSeek-V4-Flash**. It is the **only Apple-Silicon path** for the `deepseek4` architecture (284 B-total / 13 B-active 256-expert MoE, 1 M ctx, MIT): upstream `llama.cpp` doesn't implement `deepseek4` ([issue #22319](https://github.com/ggml-org/llama.cpp/issues/22319)) so lm-studio / llama-cpp-* can't load it, the model card's vLLM/SGLang loaders are CUDA-only, and the persadian IQ1_S-XL GGUF's only engine (`arishma108/llama.cpp feat/v4-port-cuda`) has **no Metal backend**. GGUF-locked to [`antirez/deepseek-v4-gguf`](https://huggingface.co/antirez/deepseek-v4-gguf) — only the `q2-imatrix` tier (IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix, 81 GB, 2-bit routed experts) fits a 96 GB-class machine (`q4-imatrix` 153 GB and batiai Q3–Q8 135–302 GB do not). Pure `make` build (C + Metal, no cmake/Python/patches). Native DSML ↔ OpenAI/Anthropic tool-call mapping with an exact-sampled-DSML replay map (no parser flags). Default bind is `127.0.0.1` — `--host 0.0.0.0` is required for LAN (`--cors` only adds headers). Thinking on by default ("high"; `model=deepseek-chat`/`think=false` disables). Decode 25–35 tok/s, cold 32 K prefill ≈ 38 s but disk-KV cache cuts the warm hit to 6.8 s. Verified 5/5 smoke, OpenCode browse 18.78 s / search 28.22 s. Alpha-quality engine; **never run the CPU path** (`make cpu`/`--cpu`) — documented macOS VM bug kernel-panics the machine. Full runbook: [`docs/servers/ds4/summary.md`](docs/servers/ds4/summary.md). Per-model: [`docs/models/per-model/model-summary-deepseek-v4.md`](docs/models/per-model/model-summary-deepseek-v4.md).

Only one of vllm-mlx, mlx-openai-server, oMLX, or vmlx can hold port 8000 at a time — switch by killing the current process before starting another (and see Event 4 pre-benchmark hygiene before any benchmark run). dflash-mlx (8098), lm-studio (1234), llama-cpp-turboquant (8099), llama-cpp-mtp (8100), vmlx-swift-lm / Osaurus (1337), mlx-lm (8080), comfyui (8188), ds4 (8101), and qwen-asr (no port) can coexist with the port-8000 server.

**Skill: `/deploy-run-benchmark-uncen-model`** — for *uncensored* model deploys (HauhauCS, dealignai-CRACK, Hermes 4, Dolphin, abliterated, magnum, …) the six-phase recipe (hygiene → deploy → smoke + refusal + perf + agent → submodule + parent doc edits) is automated at `~/.claude/skills/deploy-run-benchmark-uncen-model/`. Runs Events 3 + 4 + 6 of the Sync Policy itself. Censored models still follow the manual flow under `configs/clients/<server>/`.

**Data flow:**
```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
  Claude Code                            vllm-mlx :8000          ┐
  OpenCode                               mlx-openai-server :8000  │  one at a time
  OpenClaw                               oMLX (multi-model) :8000 │  on port 8000
  Pi                                     vmlx (JANGTQ) :8000     ┘
                                         lm-studio (LM Studio) :1234
                                         dflash-mlx (sidecar) :8098
                                         llama-cpp-turboquant (sidecar) :8099
                                         llama-cpp-mtp (sidecar) :8100
                                         vmlx-swift-lm / Osaurus (sidecar) :1337
                                         mlx-lm sidecar (ChindaMT Thai↔EN translation) :8080
                                         qwen-asr (speech→text, no port — Python API)
                                         comfyui (image-gen, sidecar) :8188
                                         ds4 / DwarfStar 4 (DeepSeek-V4-Flash, sidecar) :8101
                                         OpenAI + Anthropic API native (lm-studio + dflash-mlx: OpenAI only; comfyui: web UI only; vmlx-swift-lm: OpenAI + Anthropic + Ollama; ds4: OpenAI + Anthropic + Responses)
```

SSH aliases: `macstudio` (Mac Studio over LAN), `macstudio-ts` (Mac Studio over Tailscale), `narutaki` (Linux client).

## Architecture

- **vllm-mlx:** pip-installed in `~/vllm-mlx-env/` on Mac Studio. Most capable server for sparse-MoE / `bailing_hybrid` work. **Exercised with** `mlx-community/Ling-2.6-flash-mlx-6bit` (104B/7.4B-active `bailing_hybrid` MoE, 6-bit MLX, ~80 GB; requires PR #1227 vendoring + threadlocal-stream patch + inline-gen patch, see Known Issues for the full recipe). Started manually via `~/vllm-mlx-env/bin/vllm-mlx serve` with `--enable-auto-tool-choice --tool-call-parser hermes`. The `run_vllm_jang.py` wrapper is used for JANG-format models (e.g. Qwen3.6-27B JANG 4M dense+VL fallback).
- **Feature-rich alternative:** mlx-openai-server pip-installed in `~/mlx-openai-server-env/` on Mac Studio. Trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, multi-model YAML config with process isolation. 4-15% overhead (worse than vllm-mlx at long contexts). OpenAI API only. JANG support via `.pth` patch (`jang_patch.pth` + `jang_mlx_patch.py` in venv site-packages), activated by `JANG_PATCH_ENABLED=1` env var. Survives pip upgrades. Current roster in `~/mlx-openai-server-multimodel.yaml`: `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit` (JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K removed from disk 2026-05-05 — update YAML before restarting mlx-openai-server).
- **Multi-model server:** oMLX installed via Homebrew on Mac Studio, with AlexTzk fork overlay for JANG support (PR #364). Config lives in `~/.omlx/` on the Mac Studio (not in this repo). Models are MLX safetensors or JANG mixed-precision format stored in `~/.omlx/models/`.
- **DFlash sidecar:** dflash-mlx pip-installed in `~/dflash-mlx-env/` on Mac Studio (Python 3.11). **Pair**: `mlx-community/Qwen3.6-35B-A3B-4bit` target + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter. Wraps `mlx_lm.server` (in 0.1.4.1+ from main-branch git only — PyPI 0.1.0 has no tool-calling). Speculative decoding via block-diffusion drafter, 86.7% draft acceptance on Qwen3.6, 74-89 tok/s sustained decode. OpenAI API on port **8098**. Requires `patch_dflash_mlx_serve.py` (two upstream bugs in `DFlashModelProvider` + startup banner) plus `patch_dflash_mlx_host.py` only if pinned to 0.1.0. (The mlx-lm tool-detection trie reset patch was retired 2026-05-08 — fix landed upstream in mlx-lm 0.31.3 stock.) `--draft-model` flag is **required** for Qwen3.6 (built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family pairs). Provisional posture (mirrors lm-studio) — `configs/clients/dflash-mlx/opencode.json` only.
- **JANGTQ server:** vmlx via the MLX Studio DMG (v1.3.65+) bundled Python at `/Applications/vMLX.app/Contents/Resources/bundled-python/python/`. Only route today for TurboQuant-weight models (`*JANGTQ*` / `*JANGTQ-CRACK*`) because the public `jang-tools` pypi package lacks `load_jangtq` + the `turboquant/*kernel*` Metal kernels ([jjang-ai/jangq#5](https://github.com/jjang-ai/jangq/issues/5)). Runs headlessly — no GUI session needed despite Electron packaging. Invoke as `python3 -m vmlx_engine.cli serve …` (the bundled `bin/vmlx` shebang points at the maintainer's build tree; the CLI module works fine). OpenAI + Anthropic + Ollama API compatible. Incompatible flags: `--smelt` and `--flash-moe` raise on `weight_format=mxtq` ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)).
- **qwen-asr sidecar:** `qwen-asr` 0.0.6 pip-installed in `~/qwen-asr-env/` (Python 3.12 from Homebrew — the package declares `python>=3.9,<3.14`, and `qwen-asr[vllm]` extra is skipped because its `vllm` dep needs CUDA kernels that don't build on Apple Silicon). Pulls torch 2.11.0 + transformers 4.57.6 + librosa + soundfile + the `qwen-asr` package. **Variant**: `Qwen/Qwen3-ASR-1.7B` bf16 (4.7 GB), Apache-2.0, 30 langs + 22 Chinese dialects, ≤ 5 min audio per call. **No port-bound daemon**: `qwen-asr-serve` is the upstream daemon CLI but it requires CUDA-vLLM, so on Mac Studio interaction is in-process Python only — `Qwen3ASRModel.from_pretrained(..., device_map="mps", dtype=torch.bfloat16)` then `.transcribe(audio=…)`. Streaming + microphone modes are CUDA-only. Quantization deliberately avoided (1.7 B is already tiny; ASR is WER-sensitive; community 4/8-bit uploads have no published WER baselines). Smoke + RTF rig at `scripts/bench/bench_asr_smoke.py` and `scripts/bench/bench_asr_rtf.py`. Runbook: [`docs/servers/qwen-asr/summary.md`](docs/servers/qwen-asr/summary.md). Quantization + server-fit analysis: [`docs/models/per-model/model-summary-qwen3-asr.md`](docs/models/per-model/model-summary-qwen3-asr.md).
- **vmlx-swift-lm sidecar:** [`osaurus-ai/vmlx-swift-lm`](https://github.com/osaurus-ai/vmlx-swift-lm) (MIT, Swift, native MLX) consumed via the Osaurus macOS app — installed with `brew install --cask osaurus`. Cask version 0.18.13 (released 2026-05-08) pins the engine at commit `b9da180` via [Osaurus PR #1037](https://github.com/osaurus-ai/osaurus/pull/1037). CLI front door: `/opt/homebrew/bin/osaurus` (symlink into `/Applications/Osaurus.app/Contents/Helpers/osaurus`); the running daemon is the GUI binary launched as `/Applications/Osaurus.app/Contents/MacOS/osaurus --launched-by-cli`. Models pulled with `osaurus pull <hf-repo-id>` land in `~/.osaurus/models/<owner>/<name>/`. **Path-mismatch bug**: the server's default models dir is `~/MLXModels/`, so pulled models are invisible unless `OSU_MODELS_DIR` is set. Engine surfaces include BatchEngine continuous batching, multi-tier KV cache (paged in-memory L1 + SQLite-on-disk L2 + SSM-companion tier), TurboQuant KV compression, speculative decoding (DFlash + DDTree + classic AR), and native handlers for ZAYA (top-1 CCA + MoE), Ling/Bailing-Hybrid (recurrent GLA + MoE), Hunyuan v3 (192-expert MoE), NemotronH-Omni, Mistral Small 4 (MLA + MoE), and MiniMax M2.7 — none of which run on stock `mlx_lm` or `llama.cpp` today. Model: `JANGQ-AI/ZAYA1-8B-JANGTQ4` (8.4B total / 760M active, 4.65 GiB bundle, JANGTQ format, `tool_parser=zaya_xml`, `supports_thinking=False`). Runbook: [`docs/servers/vmlx-swift-lm/summary.md`](docs/servers/vmlx-swift-lm/summary.md).

- **llama-cpp-mtp sidecar:** custom `llama.cpp` build from [`am17an/llama.cpp@mtp-clean`](https://github.com/am17an/llama.cpp/tree/mtp-clean) ([PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673), unmerged upstream), built with `-DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=ON`. Live binary at `~/llama-cpp-mtp/build/bin/llama-server` (~17 MB, b9172 build tag); cmake on non-interactive SSH lives at `/opt/homebrew/bin/cmake` (Homebrew PATH not inherited). **Model**: `unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL` (dense 27 B + MTP self-drafting heads in a single 26 GB GGUF; `~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf`). OpenAI API on port **8100**. Launch flags: `--spec-type draft-mtp --spec-draft-n-max 2 -np 1 -ngl 99 -fa on --jinja --reasoning on --alias qwen3.6-27b-mtp-ud-q6kxl` — the spec-type entry is `draft-mtp` (not `mtp`), default `--spec-draft-n-max` is 16 (must override to 2 per HF card), `-np > 1` and `--mmproj` unsupported with MTP active. **No `--tool-call-parser` / `--reasoning-parser` flags exist on this build** — both are dispatched from the GGUF's embedded chat template via `--jinja`. **84–89 % MTP draft acceptance** measured (`draft_n_accepted / draft_n`), decode 22.9 → 20.0 tok/s @ 414 → 29 128 input tokens, smoke 5/5 single-call + 3-turn multi 21.92 s, OpenCode browse 35.98 s / search 35.24 s (slower than the lm-studio Q4_K_M baseline — MTP speedup doesn't close the dense-27 B-Q6 gap). Standard `bench_api_server.py` filler prompt at temp=0 triggers a first-token EOS specific to this 6-bit MTP quant; custom real-content prompt rig used for perf. Provisional posture — `configs/clients/llama-cpp-mtp/opencode.json` only. Runbook: [`docs/servers/llama-cpp-mtp/summary.md`](docs/servers/llama-cpp-mtp/summary.md). Technique: [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](docs/models/techniques/model-technique-qwen-3-6-mtp.md).
- **comfyui sidecar:** `ComfyUI` 0.20.1 installed via `comfy-cli` (Python 3.12 from Homebrew bootstraps `~/comfyui-env/`; `comfy --workspace ~/comfyui install --m-series --fast-deps` then provisions the actual runtime venv at `~/comfyui/.venv/` — they are two distinct venvs and don't share packages). Pulls torch 2.11.0 + transformers 5.8.0 + safetensors 0.7.0 + `comfyui-manager` + `huggingface_hub` 1.14 (which provides the `hf` CLI; `huggingface-cli` is deprecated since hub 1.x). **Model**: `SeeSee21/Z-Anime` — full fine-tune of `Tongyi-MAI/Z-Image` (S3-DiT, 6B, Apache-2.0). Two AIO BF16 checkpoints at `~/comfyui/models/checkpoints/`: Distill-4-step (~19 GiB, 4 steps, CFG 1.0) and Base (~19 GiB, 28+ steps, CFG 3–9). VAE backup at `~/comfyui/models/vae/ae.safetensors` (the AIO files bundle the VAE + qwen_3_4b text encoder internally — keep the standalone VAE only for split-file workflows). **End-user path is the browser web UI** (`http://<MAC_STUDIO_IP>:8188`); ComfyUI's `/prompt` JSON API is used only by the wall-time benchmark driver — there is no OpenAI `/v1/images/generations` shim and no entry in `configs/clients/`. **Required at launch**: `--use-pytorch-cross-attention` (the default attention backend errors on MPS, dropping the runtime to CPU). Wall-time benchmark + driver at [`scripts/bench/bench_zanime_walltime.py`](scripts/bench/bench_zanime_walltime.py) writes raw output to `/tmp/zanime-walltime.json`; canonical results in [`docs/models/benchmarks/logs/z-anime/wall-time-comfyui.md`](docs/models/benchmarks/logs/z-anime/wall-time-comfyui.md). Runbook: [`docs/servers/comfyui/summary.md`](docs/servers/comfyui/summary.md).
- **ds4 sidecar:** [`antirez/ds4`](https://github.com/antirez/ds4) ("DwarfStar 4") cloned to `~/ds4`, built with plain `make -j8` (Darwin Makefile branch auto-selects the Metal core objects `ds4_metal.o`; pure C + Objective-C Metal, **no cmake, no Python venv, no patches** — ~3 s build producing `~/ds4/{ds4,ds4-server,ds4-bench,ds4-eval}`). It is a self-contained engine — `ds4.c` does not link GGML — written only for DeepSeek-V4-Flash, with DS4-specific GGUF loading, DSML prompt rendering, an unguessable-tool-ID → exact-sampled-DSML radix-tree replay map (keeps multi-turn KV prefixes byte-aligned across stateless agent requests), RAM + SHA1-keyed on-disk KV state, and an OpenAI/Anthropic/Responses HTTP server. **Model**: `antirez/deepseek-v4-gguf` `IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix` (DeepSeek-V4-Flash 284 B-total / 13 B-active 256-expert `deepseek4` MoE, 2-bit routed experts + Q8 attn/shared/out, 81 GB; pulled via the repo's `./download_model.sh q2-imatrix` which `curl -C -` resumes and symlinks `~/ds4/ds4flash.gguf`). Only the `q2-imatrix` tier fits a 96 GB-class machine. OpenAI + Anthropic + Responses APIs on port **8101**. Launch flags: `--host 0.0.0.0 --port 8101 --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 --trace /tmp/ds4-trace.txt` — default bind is `127.0.0.1` (must pass `--host 0.0.0.0` for LAN; `--cors` only adds headers), default ctx 32768, Metal is the macOS default backend. **No parser flags** — DSML ↔ OpenAI tool-call mapping is intrinsic; thinking is on by default at "high" effort (`model=deepseek-chat` / `think=false` selects non-think; Think Max needs `--ctx ≥ 393216`). Decode 25–35 tok/s, cold 32 K prefill ≈ 38 s but disk-KV cache cuts the warm hit to 6.8 s, smoke 5/5 single-call + multi-turn 8.95 s, OpenCode browse 18.78 s / search 28.22 s. **The CPU path (`make cpu` / `--cpu`) kernel-panics current macOS** (documented VM bug) — Metal only. Provisional posture — `configs/clients/ds4/opencode.json` only. Runbook: [`docs/servers/ds4/summary.md`](docs/servers/ds4/summary.md). Per-model: [`docs/models/per-model/model-summary-deepseek-v4.md`](docs/models/per-model/model-summary-deepseek-v4.md).
- **Client configs** (`configs/clients/`): Organized by server type — `configs/clients/vllm-mlx/` for primary server, `configs/clients/mlx-openai-server/` for feature-rich multi-model, `configs/clients/omlx/` for full multi-model roster, `configs/clients/vmlx/` for JANGTQ CRACK models, `configs/clients/lm-studio/` for LM Studio headless on port 1234 (full client template set: OpenCode, OpenClaw, Claude Code, Pi, qwen-code — Claude Code uses the OpenAI-compat env-var path since LM Studio does not speak the Anthropic API), `configs/clients/dflash-mlx/` for DFlash speculative-decoding sidecar on port 8098 (added 2026-04-30, currently OpenCode-only — same provisional posture). IPs and API keys are stored as placeholders (`<MAC_STUDIO_IP>`, `<YOUR_API_KEY>`) — never commit real values.
- **Live run-state is intentionally not tracked in this repo** (the Mac Studio is a personal machine). To see which servers/models are currently up, run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) (probes the Mac Studio over SSH). No doc may assert which model is "current" / "primary" / "production".
- **Scripts** (`scripts/`): Split into `scripts/patches/` (re-applied after upstream package upgrades — `patch_omlx_cache.py` runs after every `brew upgrade omlx`) and `scripts/bench/` (benchmark drivers). See `scripts/README.md`.
- **Plans** (`plans/`): Design documents for non-trivial changes before implementation. Plans are non-canonical; active plans live in `plans/active/`, completed in `plans/done/`, abandoned in `plans/archive/`.

## Common Commands

```bash
# SSH to machines
ssh macstudio
ssh macstudio-ts
ssh narutaki

# Health check (vllm-mlx — no API key)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool

# Health check (oMLX — needs API key)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool

# Start vllm-mlx (primary server — JANG model needs wrapper)
# --enable-auto-tool-choice + --tool-call-parser qwen3_coder are required for Qwen3.5/3.6 tool use.
#   The model emits XML tool calls (<function=name><parameter=key>value</parameter></function>),
#   not JSON. The qwen3_coder parser (aliased to HermesToolParser) handles this format.
#   Using --tool-call-parser qwen will NOT work (it expects JSON inside <tool_call> tags).
# --reasoning-parser qwen3 extracts <think>…</think> into the reasoning field.
ssh macstudio "nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M \
  --served-model-name JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &"

# To start the previous primary (Qwen3.5-122B-A10B-JANG_2S), swap both `~/.omlx/models/...` and `--served-model-name` to `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S`. Same parser flags.

# Switch to mlx-openai-server (multi-model, low overhead)
ssh macstudio "pkill -f vllm-mlx; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &"

# Switch to oMLX (multi-model, 9 models)
ssh macstudio "pkill -f mlx-openai-server; pkill -f vllm-mlx; pkill -f vmlx_engine; sleep 2; /opt/homebrew/bin/brew services start omlx"

# Switch to vmlx (JANGTQ CRACK models — bundled-Python headless path)
# --enable-auto-tool-choice + --tool-call-parser qwen3 are required for OpenCode / Claude Code tool use.
#   Without them the parser stays off and the model emits raw <tool_call>… XML inside `content`,
#   which clients render as plain text (model "hallucinates" tool names).
# --reasoning-parser qwen3 is required for Qwen3 thinking models (e.g. Qwen3.5-VL CRACK, JANGTQ4).
#   Without it the model's <think>…</think> block is dumped into `content` and OpenCode renders
#   the raw thought process as the assistant's visible reply ("thinking nonsense").
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204; \
  nohup \$BP/bin/python3 -m vmlx_engine.cli serve \$SNAP --host 0.0.0.0 --port 8000 \
    --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
    --continuous-batching > /tmp/vmlx.log 2>&1 &"

# Switch back to vllm-mlx
ssh macstudio "pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2"
# then start vllm-mlx as above

# Switch to lm-studio (port 1234 — does not displace port 8000). Run scripts/chk_llm_macstu.py
# to see the live model. Example below loads IBM Granite 4.1 30B Q8_0 — substitute the modelKey +
# identifier for the model you want. Guardrail mode "high" blocks any load > ~25 % of RAM; flip to "off" then restore.
ssh macstudio "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='off'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y; \
  python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='high'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"

# Stop lm-studio
ssh macstudio "~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all"

# Start dflash-mlx (provisional sidecar on port 8098 — does not displace port 8000)
# --draft-model REQUIRED for Qwen3.6 (DRAFT_REGISTRY auto-resolves Qwen3.5 only).
# Patch MUST be applied first (idempotent re-run is a no-op):
#   ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_dflash_mlx_serve.py
ssh macstudio "nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512 \
  > /tmp/dflash-mlx.log 2>&1 &"

# Stop dflash-mlx
ssh macstudio "pkill -f dflash-serve"

# Start vmlx-swift-lm via Osaurus (port 1337 — does not displace port 8000/1234/8098/8099/8188)
# One-time install: brew install --cask osaurus. Then pull the bundle:
#   /opt/homebrew/bin/osaurus pull <hf-repo-id>     # saves to ~/.osaurus/models/<owner>/<name>/
# OSU_MODELS_DIR override is REQUIRED — osaurus pull writes to ~/.osaurus/models/ but serve
# defaults to reading ~/MLXModels/ which doesn't exist (path-mismatch bug not yet upstreamed).
ssh macstudio "OSU_MODELS_DIR=\$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 \
  > /tmp/osaurus.log 2>&1 &"

# Stop vmlx-swift-lm / Osaurus
ssh macstudio "/opt/homebrew/bin/osaurus stop; pkill -9 osaurus 2>/dev/null"

# Start llama-cpp-mtp (Qwen3.6 MTP self-drafting speculative-decoding sidecar on port 8100 — does not displace port 8000/1234/8098/8099/8188/1337)
# Build is one-time (see Architecture / runbook docs/servers/llama-cpp-mtp/summary.md).
# --spec-type draft-mtp (NOT just "mtp"). --spec-draft-n-max default is 16 — must
# override to 2 per HF card. -np > 1 and --mmproj unsupported with MTP active.
ssh macstudio "GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf; \
  nohup ~/llama-cpp-mtp/build/bin/llama-server \
    -m \"\$GGUF\" \
    -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type draft-mtp --spec-draft-n-max 2 \
    --host 0.0.0.0 --port 8100 \
    --alias qwen3.6-27b-mtp-ud-q6kxl \
    --jinja --reasoning on \
    > /tmp/llama-cpp-mtp.log 2>&1 &"

# Stop llama-cpp-mtp (do NOT match bare 'llama-server' — that also kills llama-cpp-turboquant if running)
ssh macstudio "pkill -f 'llama-cpp-mtp/build/bin/llama-server'"

# Start comfyui (image-generation sidecar on port 8188 — does not displace port 8000/1234/8098/8099/8100)
# --use-pytorch-cross-attention is REQUIRED on Apple Silicon (default attention errors on MPS).
# Web UI only — chat clients cannot trigger generations (no /v1/images/generations shim).
ssh macstudio "nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py \
  --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention \
  > /tmp/comfyui.log 2>&1 &"

# Stop comfyui
ssh macstudio "pkill -f 'comfyui/main.py'"

# Start mlx-lm sidecar (ChindaMT-4B Thai↔English translation on port 8080 — does not displace any other server)
# --chat-template-args disables thinking server-wide so translations land in message.content not message.reasoning.
# Model ID in API calls must be the full path /Users/chanunc/mlx-models/chindamt-4b-4bit (short alias → HF 404).
ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/mlx-models/chindamt-4b-4bit \
  --host 0.0.0.0 --port 8080 \
  --chat-template-args '{\"enable_thinking\":false}' \
  > /tmp/chindamt.log 2>&1 &"

# Stop mlx-lm sidecar (ChindaMT)
ssh macstudio "pkill -f 'mlx_lm.server.*chindamt'"

# Start ds4 / DwarfStar 4 (DeepSeek-V4-Flash 284B/13B-active on port 8101 — does not displace any other server)
# Only Apple-Silicon path for the deepseek4 arch. One-time: git clone https://github.com/antirez/ds4.git
#   && cd ds4 && make -j8; ./download_model.sh q2-imatrix (81 GB, symlinks ./ds4flash.gguf).
# --host 0.0.0.0 is REQUIRED for LAN (default bind 127.0.0.1; --cors does not rebind). Model id: deepseek-v4-flash.
ssh macstudio "cd ~/ds4 && nohup ./ds4-server \
  --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt \
  > /tmp/ds4-server.log 2>&1 &"

# Stop ds4 / DwarfStar 4
ssh macstudio "pkill -f 'ds4-server'"

# View logs
ssh macstudio "tail -20 /tmp/vllm-mlx.log"            # vllm-mlx
ssh macstudio "tail -20 /tmp/mlx-openai-server.log"    # mlx-openai-server
ssh macstudio "tail -20 ~/.omlx/logs/server.log"       # oMLX
ssh macstudio "tail -20 /tmp/vmlx.log"                 # vmlx
ssh macstudio "tail -20 /tmp/dflash-mlx.log"           # dflash-mlx
ssh macstudio "tail -20 /tmp/llama-cpp-mtp.log"        # llama-cpp-mtp (port 8100, Qwen3.6 MTP sidecar)
ssh macstudio "tail -20 /tmp/chindamt.log"             # mlx-lm sidecar (port 8080, ChindaMT Thai↔EN translation)
ssh macstudio "tail -20 /tmp/comfyui.log"              # comfyui
ssh macstudio "tail -20 /tmp/osaurus.log"              # vmlx-swift-lm / Osaurus
ssh macstudio "tail -20 /tmp/ds4-server.log"           # ds4 / DwarfStar 4 (port 8101, DeepSeek-V4-Flash)

# Upgrade all client tools (MacBook)
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent

# Upgrade oMLX (Mac Studio)
ssh macstudio "/opt/homebrew/bin/brew upgrade omlx"
```

Use `macstudio-ts` instead of `macstudio` when you are connected over Tailscale rather than the local LAN.

## Editing Workflow

### Sync Policy (Read this first when changing the docs)

This repo is the operations notebook for a personal Mac Studio LLM lab. **Run-state is deliberately not recorded in any doc** — the Mac Studio is a personal machine and the repo must not disclose which model/server is up at any moment. To check what is actually running, run [`scripts/chk_llm_macstu.py`](scripts/chk_llm_macstu.py) (probes over SSH). The docs track the *catalog* of what was tried, how it was deployed, and how it benchmarked — in evergreen terms.

**Hard rule:** No doc may assert which model/server is "current", "primary", "production", "the main", "currently running", or "stopped". Describe capabilities, deploy recipes, and benchmark results without claiming any of them is live right now. When you add a model, benchmark, server type, script, plan, or technique, the catalog/index docs below must stay consistent — use the per-event checklists. Do not skip "minor" docs — drift compounds across sessions.

#### Canonical layers and where they live

The repo has two navigation layers. There is intentionally **no live-state pointer file** — current run-state is looked up via `scripts/chk_llm_macstu.py`, never asserted in a doc.

1. **Sub-root README.md indexes** — every top-level content folder has a `README.md` acting as its canonical index. When you add, remove, rename, or move a file inside one of these folders, update its README in the same commit:

   | Folder | README | Indexes |
   |:--|:--|:--|
   | `docs/servers/` | [`docs/servers/README.md`](docs/servers/README.md) | Server runbooks + maintenance docs |
   | `docs/models/` | [`docs/models/README.md`](docs/models/README.md) | Catalog, `per-model/`, `techniques/`, `benchmarks/`, `how-to/` |
   | `docs/clients/` | [`docs/clients/README.md`](docs/clients/README.md) | Client setup docs ↔ template mapping |
   | `docs/server-apis/` | [`docs/server-apis/README.md`](docs/server-apis/README.md) | Wire-protocol references (Responses API, …) ↔ which servers speak them |
   | `configs/` | [`configs/README.md`](configs/README.md) | Server Roles table + Switching Servers |
   | `configs/clients/` | [`configs/clients/README.md`](configs/clients/README.md) | Per-server template layout |
   | `scripts/` | [`scripts/README.md`](scripts/README.md) | `bench/`, `patches/`, `switch_opencode_config.py` |
   | `plans/` | [`plans/README.md`](plans/README.md) | `active/`, `done/`, `archive/` indexes |

2. **Top-level docs** — `README.md`, `CLAUDE.md`, `AGENTS.md`. CLAUDE.md and AGENTS.md must stay content-identical except for the agent-name header (lines 1–3).

#### Event 1: Deploying a new server type (e.g. lm-studio, future Ollama)

If you stand up a new server type on the Mac Studio, all of these must be updated in the same PR/commit:
- `README.md` — data flow diagram, Quick Start launch + stop snippets, Health Check (curl + log tail), Servers table row (with link to `docs/servers/<name>/summary.md`), maintenance line, Known Limitations entry, "What lives where" table only if a new top-level folder is introduced
- `CLAUDE.md` **and `AGENTS.md`** — overview paragraph, Architecture bullet, data flow diagram, Common Commands launch + stop, Editing Workflow scope note. Mirror edits between the two files.
- `configs/README.md` — bump `Last updated` date, Server Roles table row, new `clients/<name>/` config-files section, Switching Servers command block
- `configs/clients/<name>/opencode.json` — at minimum (other client configs are deferred until the server graduates to permanent status)
- `configs/clients/README.md` — add the new server row to the Layout table; note any deferred templates
- `scripts/switch_opencode_config.py` — append `"<name>"` to the hardcoded `SERVERS` list
- `docs/servers/<name>/summary.md` — full runbook matching the structure of `docs/servers/vmlx/summary.md` (Overview, Architecture, Installation, Starting the server, Tool use and reasoning, Health check, Performance, Known limitations, See also)
- `docs/servers/README.md` — add the new server row to the runbook index, and to Maintenance And Patches if maintenance/patch docs exist

If the new server does not support JANG/JANGTQ/`bailing_hybrid`, **also** update the "All servers support JANG…" line in `README.md` (currently reads "All servers except lm-studio support JANG…").

#### Event 2: Swapping the model running on a server

Run-state is **not** tracked in docs (privacy — see the Sync Policy intro). When you `pkill`/relaunch a server with a different model, do **not** add or update any "current / primary / production / main / stopped" marker in any doc, and do not record the live launch command anywhere in the repo. There is no documentation cascade for a model swap:

- If the model is new to the repo, catalog it per **Event 3** (capability/spec entry, evergreen — no "now primary" wording).
- If you benchmarked it, record results per **Event 4**.
- To recover a launch invocation later, derive it from the server runbook in `docs/servers/<server>/summary.md` (which documents launch *shape* in evergreen terms), or run `scripts/chk_llm_macstu.py` while the server is up.
- `configs/clients/<server>/*.json` model fields are templates of the *compatible* roster, not a live mirror — change them only when the compatible set changes (see Server-specific config rules), never to track which one is loaded.

#### Event 3: Adding a new model (any server)

**Precondition — read the family doc first (if one exists).** Before downloading, deploying, or benchmarking any new model, check whether its base architecture already has a per-model family doc under `docs/models/per-model/`. Family docs accumulate gotchas, parser flags, quant traps, and operational caveats discovered across every prior variant — re-reading them up front saves you from rediscovering the same patches and bench-rig regressions.

Current family / per-model docs in this repo:

| If the new model is in this family… | Read this first |
|:--|:--|
| Qwen3.6 (27B dense, 35B-A3B MoE, JANG / JANGTQ / CRACK variants, GLM-distilled / abliterated derivatives) | [`docs/models/per-model/model-summary-qwen-3-6.md`](docs/models/per-model/model-summary-qwen-3-6.md) — especially the **Family-wide pitfalls** section at the top (parser flags, K_P trap, guardrail dance, OpenCode `PWD` regression) |
| Qwen3.5 (27B Opus Distilled, 122B-A10B 4-bit / JANG_2S, 35B-A3B JANG_4K) | [`docs/models/per-model/model-summary-qwen-3-5.md`](docs/models/per-model/model-summary-qwen-3-5.md) |
| Qwen3-Coder | [`docs/models/per-model/model-summary-qwen-3-coder.md`](docs/models/per-model/model-summary-qwen-3-coder.md) |
| Qwen3-ASR (speech-to-text) | [`docs/models/per-model/model-summary-qwen3-asr.md`](docs/models/per-model/model-summary-qwen3-asr.md) |
| Gemma 4 (26B-A4B MoE, 31B-it dense, DavidAU Heretic / TrevorJS Uncensored derivatives) | [`docs/models/per-model/model-summary-gemma.md`](docs/models/per-model/model-summary-gemma.md) — note the bf16 + MTP streaming hang on long-reasoning prompts |
| IBM Granite 4.1 (dense instruct) | [`docs/models/per-model/model-summary-granite-4.1.md`](docs/models/per-model/model-summary-granite-4.1.md) |
| Ling-2.6-flash / `bailing_hybrid` derivatives | [`docs/models/per-model/model-summary-ling.md`](docs/models/per-model/model-summary-ling.md) — three patches required, mlx-openai-server incompatible |
| MiMo V2.5 (Xiaomi 130-expert MoE) | [`docs/models/per-model/model-summary-mimo-v2.5.md`](docs/models/per-model/model-summary-mimo-v2.5.md) |
| NemotronH / Nemotron-3 (hybrid Mamba-2 / MoE) | [`docs/models/per-model/model-summary-nemotron.md`](docs/models/per-model/model-summary-nemotron.md) |
| Zyphra ZAYA1 (top-1 CCA + MoE) | [`docs/models/per-model/model-summary-zaya1-8b.md`](docs/models/per-model/model-summary-zaya1-8b.md) — vmlx-swift-lm via Osaurus only; JANGTQ HTTP regression at pin `b9da180` |
| HyperNova (CompactifAI-compressed gpt-oss derivatives) | [`docs/models/per-model/model-summary-hypernova.md`](docs/models/per-model/model-summary-hypernova.md) — pre-deployment candidate analysis only, not yet benchmarked |

If a family doc does not yet exist for the new model's architecture and the deploy uncovers non-trivial gotchas, create one as part of the deploy commit (see the per-model section creation rule below). One-off variants of an existing family go in the family doc, not their own file.

When a new model file lands in `~/.cache/huggingface/`, `~/.omlx/models/`, or `~/.lmstudio/models/` and you serve it:
- `docs/models/model-summary.md` — add an Index entry **and** a per-model section with the standard spec table (Base Model, Quant, Format, Vendor, Parameters, Density, Quantization, Specialties, Tokens/sec, On-disk size, Context Size, License, Key Features), server config, performance numbers if benchmarked, caveats. Place the entry near siblings (Qwen3.6 family together, etc.)
- `docs/models/per-model/model-summary-<slug>.md` — only if the model needs more than ~150 lines of detail (deployment recipe, patch list, failure analysis). The catalog entry should then be a stub linking here.
- `docs/models/README.md` — add a row to the Per-model deep dives table if you created a `per-model/` file
- `README.md` Models table — one row with size, context, "Best For" cell, and a link to the new model-summary.md anchor
- The relevant `configs/clients/<server>/*.json` files — add the new model to the `models` map (oMLX requires updating all 4 client config files; vllm-mlx is single-model so only update if it becomes the primary)
- Do **not** add a "now primary / production / current" marker anywhere — see Event 2. Run-state is looked up via `scripts/chk_llm_macstu.py`, not asserted in docs.
- **If the user asks to "deploy and benchmark" a new model**, follow the pre-benchmark hygiene rule in Event 4 first: stop any other Mac Studio LLM server process before starting the new model, so the deploy-then-benchmark sequence runs on a clean machine.

If the model needs patches/wrappers (JANG, JANGTQ, `bailing_hybrid`, `mimo_v2`, etc.), the **technique-level explanation** belongs in `docs/models/techniques/model-<technique|quantization|architecture>-<name>.md` (canonical reference), and the **server-specific integration steps** in `docs/servers/<server>/jang-patch.md` or `docs/servers/<server>/summary.md`. Per-model deploy specifics (model ID, launch invocation) go in the model's own summary file. See Event 7 for the techniques-folder rules.

#### Event 4: Running a new benchmark

**Pre-benchmark hygiene (always do this first):** before launching the model under test, stop every other Mac Studio LLM server process so the benchmark reflects the target model alone, not residual GPU buffers, wired-memory KV cache, or file cache from a prior server. The Mac Studio has ~96 GB unified memory and most production models occupy 30–80 GB; leaving a prior server alive either OOMs the new launch or quietly contaminates tok/s, TTFT, and wired-memory readings. This is mandatory whenever the user asks to "deploy and benchmark" a new model — do it before the deploy step, not after.

```bash
# Stop everything benchmark-relevant on the Mac Studio, then verify the GPU/RAM is quiescent.
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

**Do not restore the previously running model after the benchmark.** The newly deployed-and-benchmarked model stays running on the Mac Studio; restarting the prior model would just re-contaminate memory and undo the clean run you just paid for. Do **not** update any doc to reflect which model is now live — run-state is not tracked here (see Event 2). Only restore the prior model if the user explicitly asks.

When you run `scripts/bench/bench_api_server.py`, `scripts/bench/bench_api_tool_call.py`, or `scripts/bench/bench_agent_tool_call.py`:
- Save raw JSON output to `docs/models/benchmarks/logs/<model-slug>/<benchmark-type>.json` (or `<benchmark-type>-<server>.json` for cross-server comparisons — see the `agent-bench-lm-studio.json` precedent)
- Update the matching `docs/models/benchmarks/model-benchmark-<type>.md` — add the row to the cross-model summary table, add a per-model results section if one doesn't exist, link the raw JSON
- If you introduce a new benchmark *type* (rare), add a row in `docs/models/README.md`'s Benchmarks table
- If the benchmark establishes a new fastest/slowest extreme, update the README Benchmarks section's headline tables
- If the benchmark reveals an impactful finding (faster server, broken model), update `docs/models/model-summary.md` caveats and the relevant `docs/models/per-model/model-summary-<slug>.md` detail file (evergreen — describe the finding, do not write "now primary")

Do not commit bench JSONs that contain secrets or PII (these scripts don't generate any today, but verify before committing).

#### Event 5: Adding, renaming, or removing a script

When you change anything under `scripts/`:
- Add new files into the matching subdir — `scripts/bench/` for benchmark drivers, `scripts/patches/` for monkey-patches against installed server packages. Top-level `scripts/` is reserved for client-side helpers like `switch_opencode_config.py`.
- `scripts/README.md` — update the Benchmarks, Patches, or Client Config table to add/rename/remove the script
- If the script is a patch, link it from the relevant `docs/servers/<server>/maintenance.md` or `jang-patch.md` so the runbook explains when to re-run it
- If the script is a benchmark driver, update Event 4's listed names and add an entry in `docs/models/README.md`'s Benchmarks table when a new type is introduced
- If you rename or move a script, grep for stale references: `grep -rn "scripts/<old-name>" --include="*.md" --include="*.json" --include="*.py"`

#### Event 6: Adding, completing, or abandoning a plan

Plans are non-canonical research docs. They live under `plans/active/` (planned or in progress), `plans/done/` (implemented and kept for context), or `plans/archive/` (superseded or abandoned).

- New plan: create at `plans/active/plan-<slug>.md` with the status block (`Status: active`, `Created: YYYY-MM-DD`, `Canonical: no`); add a row to `plans/README.md`'s Active index
- Completing a plan: `git mv plans/active/<file> plans/done/<file>`, move the row in `plans/README.md` from Active to Done, and link the implementation (commits, code locations) at the top of the plan body
- Abandoning a plan: `git mv plans/active/<file> plans/archive/<file>`, move the row in `plans/README.md` from Active to Archive, and add a one-line "Archived because…" note at the top of the plan body
- Plans never claim live state. Run-state is not recorded in any doc — it is looked up via `scripts/chk_llm_macstu.py`. A plan saying "production primary is X" does not make it so.

#### Event 7: Adding or updating a technique / quantisation / architecture reference

Cross-cutting reference docs for inference-side techniques, weight quantisation formats, KV-cache compression, and model architectures live under `docs/models/techniques/`. They are the **canonical *what-it-is* reference**; server runbooks and per-model files cross-link in for the explanation rather than duplicating it.

- Filename carries the category prefix: `model-technique-<name>.md` for generation-time techniques (DFlash, prompt caching), `model-quantization-<name>.md` for weight or activation formats (JANG, TurboQuant/JANGTQ), `model-architecture-<name>.md` for model architectures whose deployment requires cross-cutting treatment (`bailing_hybrid`).
- New technique doc: lead with **what it is** in one paragraph, then *how it integrates with this stack*, then performance / known limitations / cross-references. Add a row to `docs/models/techniques/README.md`'s Index table.
- When a technique gets a new server integration: update the technique file's "How servers integrate it" / "Server compatibility" table, then add the server-specific operational steps in `docs/servers/<server>/<name>-patch.md` or `docs/servers/<server>/summary.md`. Server doc opens with a callout pointing to the technique file for the conceptual content.
- When a regression / quality bug / performance characteristic is discovered for a technique, update the technique file (canonical) — do not bury the analysis in a per-model file or a server runbook. Cross-link from the relevant `docs/models/benchmarks/` write-up.
- If the technique becomes operationally adopted, update the relevant server runbook with a one-line conclusion + link back to the technique file (evergreen — do not assert it is "currently" running).
- Pre-commit drift check for technique-folder edits: grep for stale references to the technique file by name across `docs/`, `plans/`, `README.md`, `CLAUDE.md`, `AGENTS.md`.

### Pre-commit drift check

Before committing doc changes, grep for stale references and for accidentally-introduced run-state markers across the primary docs:
```bash
grep -n "<old-model-name>\|<old-primary>" README.md AGENTS.md CLAUDE.md configs/README.md docs/models/model-summary.md
# privacy guard — these should return nothing in committed docs:
grep -rn "current production\|production main\|production primary\|currently running\|currently stopped\|Last main\|Active model:" README.md AGENTS.md CLAUDE.md configs/README.md docs/ || true
```
Catch drift while the context is fresh, not three sessions later.

### Server-specific config rules

**oMLX models** (`configs/clients/omlx/`) — when adding or removing, keep all of these in sync:
- `configs/clients/omlx/opencode.json`
- `configs/clients/omlx/pi-models.json`
- `configs/clients/omlx/openclaw-provider.json`
- `configs/clients/omlx/qwen-code-settings.json`
- `README.md` — Models & Benchmarks table
- `docs/models/model-summary.md` — per-model specs

`configs/clients/omlx/claude-code-settings.json` only references one default model — update only if the default changes.

**mlx-openai-server configs** (`configs/clients/mlx-openai-server/`) intentionally expose a stable superset of commonly used **compatible** model IDs. They do not have to mirror the exact live YAML on the Mac Studio; check `/v1/models` for the current live roster. Update them only when the compatible superset changes.

**vllm-mlx configs** (`configs/clients/vllm-mlx/`) serve a single model and only need updating if the primary model changes (see Event 2 above).

**vmlx configs** (`configs/clients/vmlx/`) target the JANGTQ CRACK model served out of the MLX Studio bundled Python. Update the model ID across all four files + the `README.md` Models table when the served JANGTQ model changes.

**lm-studio configs** (`configs/clients/lm-studio/`) ship the full template set: `opencode.json`, `openclaw-provider.json`, `claude-code-settings.json`, `pi-models.json`, `qwen-code-settings.json`. `claude-code-settings.json` uses the OpenAI-compat env-var path (`CLAUDE_CODE_USE_OPENAI=1`, `OPENAI_BASE_URL`, `CLAUDE_CODE_OPENAI_MODEL`) because LM Studio does not speak the Anthropic API; pair with `claude-code-router` if you need true Anthropic-tool semantics. Update `model` / default-model fields plus the `models` map in all five whenever the lm-studio roster changes.

**Model settings on Mac Studio** (`~/.omlx/model_settings.json`) are edited directly via SSH, then oMLX is restarted to apply. Changes there are separate from the client configs in this repo.

## oMLX Limitations

- **GGUF format**: Not supported — oMLX only loads MLX safetensors and JANG format.
- **MXFP8 quantization**: Not confirmed to work; use 4/6/8-bit MLX quantizations.
- **JANG + Nemotron-H**: JANG models with Nemotron-H architecture (latent MoE gate) fail with matmul shape mismatch — bug in PR #364's weight mapping. Non-Nemotron JANG models (e.g., Qwen3.5) work fine.
- **Qwen3.5-122B + OpenClaw**: HTTP 500 errors with large system prompts ([oMLX #42](https://github.com/jundot/omlx/issues/42)).
- **Dense 27B model + OpenClaw**: Too slow (all 27B params per token, no MoE sparsity).
- **Starlette 1.0 dashboard bug**: oMLX v0.2.20 pulls starlette 1.0.0 which breaks the admin dashboard. Fix: `pip install "starlette==0.46.2"` in the oMLX venv ([oMLX #361](https://github.com/jundot/omlx/issues/361)).

## Known Issues

- **SSH timeouts**: Fixed by `sudo pmset -a sleep 0 disksleep 0 displaysleep 10` on Mac Studio. If it returns, verify with `ssh macstudio "pmset -g | grep sleep"`.
- **Hot cache patch**: `scripts/patches/patch_omlx_cache.py` must be re-applied after every `brew upgrade omlx` or fork reinstall. It patches `model_settings.py` and `engine_pool.py` inside the oMLX package to support per-model `hot_cache_max_size` in `~/.omlx/model_settings.json`. In v0.2.20, `parse_size` moved from `omlx.utils` to `omlx.config` — the patch script handles this.
- **JANG fork overlay**: oMLX currently runs with AlexTzk/omlx fork (PR #364) pip-installed over the Homebrew v0.2.20 base. The original omlx package is backed up at `/opt/homebrew/.../omlx.bak`. `brew upgrade omlx` will overwrite the fork — re-apply fork + patches after upgrades.
- **vmlx bundled-Python shebang**: the bundled `bin/vmlx` script has a hardcoded shebang pointing at the maintainer's build path (`/Users/eric/mlx/vllm-mlx/panel/bundled-python/python/bin/python3`). Always invoke via `$BP/bin/python3 -m vmlx_engine.cli serve …` (matches the CHANGELOG "Bundled spawn uses `python3 -m vmlx_engine.cli serve` (avoids shebang issues)" note). `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python`. Re-applies on each DMG upgrade — the app bundle is self-contained, no homebrew coupling.
- **vmlx MLLM tools-dropped bug**: vmlx 1.0.3 silently drops `tools[]` on the MLLM code path. Symptom: tiny `prompt_tokens`, model emits `curl`/`fetch` as prose. Fix: `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` (idempotent; re-apply after every DMG upgrade). Required for any `is_mllm=True` model. Full bug-by-bug breakdown: [`docs/models/techniques/model-quantization-turboquant.md` § MLLM tool-use bugs](docs/models/techniques/model-quantization-turboquant.md#mllm-tool-use-bugs).
- **dflash-mlx 0.1.4.1 + mlx-lm 0.31.3**: tool-calling end-to-end needs `patch_dflash_mlx_serve.py` (plus `patch_dflash_mlx_host.py` only on 0.1.0). The mlx-lm tool-detection trie reset patch (`patch_mlx_lm_match.py`) was retired 2026-05-08 — `mlx_lm/generate.py:992` now does `if s is None:` in stock 0.31.3 (likely landed via [PR #1170](https://github.com/ml-explore/mlx-lm/pull/1170)). PyPI ships 0.1.0 without tool-calling — install from main: `pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'`. `DRAFT_REGISTRY` auto-resolves Qwen3.5 only — Qwen3.6 targets must pass `--draft-model` explicitly. Re-apply patches after `pip install -U`. Full bug-by-bug breakdown + cross-fork landscape: [`docs/models/techniques/model-technique-dflash.md`](docs/models/techniques/model-technique-dflash.md).
- **llama-cpp-turboquant `-fa` flag and cold-prefill regression**: the `johndpope/llama-cpp-turboquant` fork's `llama-server` rejects bare `-fa` — must pass `-fa on` (or `off` / `auto`). The `iso3` K cache also has heavy compute on cold prefill; 32 K cold prefill exceeds 600 s on M3 Ultra so the standard `bench_api_server.py` probe times out. Workaround: keep contexts ≤ 16 K cold or warm the prompt cache before measuring. Speculative decoding is reported unsupported (`speculative decoding not supported by this context`). Full bug-by-bug breakdown + workload-fit analysis: [`docs/models/techniques/model-technique-rotorquant.md`](docs/models/techniques/model-technique-rotorquant.md).
- **Ling-2.6-flash deployment**: `mlx-community/Ling-2.6-flash-mlx-6bit` (`bailing_hybrid`) requires three patches: vendor `bailing_hybrid.py` from [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227), `patch_mlx_lm_threadlocal_stream.py`, `patch_vllm_mlx_inline_gen.py`. Server flags: `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits Hermes `<tool_call>{json}</tool_call>`, not Qwen3 XML). Caps at 64K context on M3 Ultra — 128K OOMs. mlx-openai-server incompatible (deeper thread coupling). Re-apply patches 2+3 after `pip install -U vllm-mlx` or `pip install -U mlx-lm`. Full architecture + threading rationale + server-compatibility matrix: [`docs/models/techniques/model-architecture-bailing-hybrid.md`](docs/models/techniques/model-architecture-bailing-hybrid.md).
- **`bench_agent_tool_call.py` + OpenCode 1.14.50+ PWD regression**: `subprocess.run(env=os.environ.copy())` inherits the caller's `PWD`. OpenCode 1.14.50+ reads `PWD` (not `cwd`) when bootstrapping its project context, so an inherited `PWD ≠ cwd` makes OpenCode double-bootstrap (once in the actual cwd, once in the inherited-PWD dir) and sink its JSON event stream into the wrong session DB — `proc.stdout` ends up empty and the bench reports `agent_turns=0 tool_calls=[]` even though the agent runs fine (you'll see the actual tool fire in the stderr log). Fix: bench script now sets `env["PWD"] = cwd` after `env = os.environ.copy()`. Discovered 2026-05-14 during the prithivMLmods/Q3.6-27B-GLM-5.1-DA deploy; full triage in [`docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md`](docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md#bench-rig-regression-discovered-during-this-deploy-2026-05-14).
