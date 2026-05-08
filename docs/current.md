# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-08

## Production

| Field | Value |
|:--|:--|
| Server | `lm-studio` (LM Studio headless, port 1234) |
| Model | `gemma-4-26b-a4b-q8` (lmstudio-community Gemma 4 26B A4B-it Q8_0 GGUF, sparse MoE 26B / 4B-active, Apache 2.0, 25.02 GiB on disk) |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/lm-studio/`](../configs/clients/lm-studio/) (OpenCode + OpenClaw) |
| Runbook | [`docs/servers/lm-studio/summary.md`](servers/lm-studio/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# lmstudio-community/gemma-4-26B-A4B-it-Q8_0.gguf is downloaded via `hf` CLI into LM Studio's
# tree and registered under modelKey `gemma-4-26b-a4b-it`. Pin the stable API id with
# `--identifier gemma-4-26b-a4b-q8` at load (the modelKey prefix-collides with
# `gemma-4-26b-a4b-it-uncensored` (TrevorJS); first-alphabetical wins).
#
# IMPORTANT: do NOT use the unsloth/gemma-4-26B-A4B-it-GGUF variant — its chat template
# raises `Cannot call something that is not a function: got UndefinedValue` (jinja error)
# on every request with `tools[]`. lmstudio-community's variant has the fixed template.
#
# Guardrail must be temporarily set to "off" in ~/.lmstudio/settings.json before initial load
# (25.02 GiB > 25 % of 96 GB unified memory), then restored to "high" once IDLE.

# (Once-only) download + import the GGUF into LM Studio's tree:
ssh macstudio "~/dflash-mlx-env/bin/hf download lmstudio-community/gemma-4-26B-A4B-it-GGUF \
  gemma-4-26B-A4B-it-Q8_0.gguf --local-dir /tmp/gemma4-lmstudio-community"
ssh macstudio "~/.lmstudio/bin/lms import -L --user-repo lmstudio-community/gemma-4-26B-A4B-it-GGUF -y \
  /tmp/gemma4-lmstudio-community/gemma-4-26B-A4B-it-Q8_0.gguf"

# Load + serve:
ssh macstudio "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='off'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms load 'gemma-4-26b-a4b-it' --gpu max --context-length 131072 --identifier gemma-4-26b-a4b-q8 -y; \
  python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='high'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- Switched 2026-05-07 from lm-studio + unsloth Qwen3.6-35B-A3B-UD-Q6_K to lm-studio + lmstudio-community Gemma 4 26B A4B-it Q8_0. Both stay in the LM Studio registry; qwen3.6 is restartable from the Fallbacks table.
- **Performance** (2026-05-07 on lm-studio): API smoke 5/5, multi-turn loop **2.14 s 🏆 tied with TrevorJS**. Decode 70–86 tok/s, prefill 158 K tok/s @ 32 K. **OpenCode end-to-end under scaffolded prompts: browse 2.94 s 🥈 / search 7.20 s** (3/3 webfetch fires, ~7.20 s search includes fetch + final summary). Raw data: [`docs/models/benchmarks/gemma-4-26b-a4b-q8/`](models/benchmarks/gemma-4-26b-a4b-q8/).
- **Prompt convention required for OpenCode use** — the model has a self-imposed _"I am not permitted to guess or generate URLs"_ rule (verbatim from a refusal). Bare prompts like `Browse www.example.com` hit 0/3 tool fires; scaffolded prompts hit 3/3:
  - Browse: `Browse <literal url> using tool you have` (the "using tool" hint is load-bearing)
  - Search/multi-step: `Use webfetch to browse <literal url> and tell me <X>` (URL must be literal — never `Hackernews`, always `https://news.ycombinator.com/`)
  - Both rules together fire 3/3; either alone hits 1/3 or 0/3.
- **Apache 2.0** — Google Gemma 4 weights are Apache 2.0; lmstudio-community's quantization is a derivative (no additional license restrictions). Standardised RLHF instruct (the censored counterpart to TrevorJS's EGA-abliterated variant of the same base model).
- Tool-calling and reasoning parsing are **built into the LM Studio runtime** — no `--tool-call-parser` / `--reasoning-parser` flags needed. Non-thinking model (no `<think>` block).
- **Discoverability gotcha**: `lms ls` does not surface HF-cached blobs — `lms import -L` is required once before the first load. The `lms` CLI in LM Studio 0.3.x has no `rm`/`uninstall`/`remove` subcommand; cleanup is `rm -rf <model-container-dir>`. Two `gemma-4-26b-a4b-it`-prefix entries exist in `lms ls` (this one + TrevorJS's `-uncensored` suffix); `lms load 'gemma-4-26b-a4b-it' -y` picks first alphabetically (this one).
- **Guardrail dance**: LM Studio's resource-guardrail (default `mode: "high"`) blocks loading a 25 GiB model on a 96 GB box. The launch snippet flips it `off` for the load and restores `high` immediately after; safer than leaving guardrails disabled.
- Log: `ssh macstudio "~/.lmstudio/bin/lms log show 2>&1 | tail -40"` (LM Studio doesn't write the standard `/tmp/*.log`).
- mlx-lm (port 8000) and dflash-mlx (port 8098) remain stopped. Previously deployed mains (unsloth Qwen3.6-35B-A3B-UD-Q6_K, Granite 4.1 30B Q8_0, Gemma 4 31B-it MLX 6-bit, TrevorJS Gemma 4 26B A4B, DavidAU Heretic family, prithivMLmods Aggressive) all stay on disk and are restartable from the Fallbacks table below.

## Active Sidecars (no port-bound daemon)

| Use case | Path | Model | Notes |
|:--|:--|:--|:--|
| Speech-to-text | `~/qwen-asr-env/` (Python API, transformers + MPS) | `Qwen/Qwen3-ASR-1.7B` (bf16, 4.7 GB) | Deployed 2026-05-08. RTF 19.06× on 15 s English clip, 0.79 s avg. No `/v1/audio/transcriptions` endpoint — call `Qwen3ASRModel.transcribe(audio=…)` from a Python script. Doesn't compete with port 8000 / 1234 / 8098 / 8099. Runbook: [`docs/servers/qwen-asr/summary.md`](servers/qwen-asr/summary.md). |
| Image generation (port 8188) | `~/comfyui/` (PyTorch 2.11 + MPS, comfy-cli managed) | `SeeSee21/Z-Anime` AIO BF16 — Distill-4-step + Base (~19 GiB each, S3-DiT 6B, Apache-2.0) | Deployed 2026-05-08. Web UI only at `http://192.168.31.4:8188`; no `/v1/images/generations` shim. Wall time @ 1024² (3 timed runs after 1 warm-up): Distill-4-step **17.75 s** (CFG 1.0), Base 28-step **235.16 s** (CFG 4.0). Doesn't compete with port 8000 / 1234 / 8098 / 8099. Launch: `nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention > /tmp/comfyui.log 2>&1 &`. Runbook: [`docs/servers/comfyui/summary.md`](servers/comfyui/summary.md). |

## Stopped / Documented Fallbacks

Models are off (unloaded or stopped) until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-07 morning → 2026-05-07 evening, unsloth Qwen3.6-35B-A3B UD-Q6_K, sparse MoE 35B/3B-active think-on, browse 4.92 s / search 12.08 s) | `lm-studio` | `qwen3.6-35b-a3b-ud-q6` from `unsloth/Qwen3.6-35B-A3B-GGUF` | On disk and registered in `lms ls` as `qwen3.6-35b-a3b`. Reload via `lms load 'qwen3.6-35b-a3b' --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-ud-q6 -y` (guardrail off first). Use this when bare imperative prompts matter — Qwen3.6 fires tools without scaffolding. |
| Prior production main (2026-05-06 → 2026-05-07, IBM Granite 4.1 30B Q8_0, Apache 2.0, dense, browse 6.24 s / search 10.51 s) | `lm-studio` | `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF` | On disk and registered in `lms ls` as `granite-4.1-30b`. Reload via `lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y` (guardrail off first). Stays as the Apache-2.0 fallback when the production main is unloaded for an experiment. |
| Prior production main (2026-05-06, Gemma 4 31B-it MLX 6-bit on mlx-lm, thinking ON, browse 12.33 s / search 35.55 s) | `mlx-lm` (port 8000) | `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk at `~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit`. Restart via the launch shape preserved in this file's git history (commit `1584c46` had the Cellar libexec `mlx_lm.server` invocation as the active Production block). |
| Prior lm-studio main (Gemma 4 31B-it MLX 6-bit, thinking OFF, browse **5.11 s 🥇** / search **6.37 s 🏆**) | `lm-studio` | `gemma-4-31b-it-mlx` from `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk — reload via `lms load 'gemma-4-31b-it-mlx' --gpu max --context-length 65536 -y`; then `lms server start --bind 0.0.0.0 --cors`. Guardrail may block — set `modelLoadingGuardrails.mode = "off"` before load, restore after. Verify context with `lms ps` (first load sometimes ignores `--context-length`). |
| Prior lm-studio main (TrevorJS Gemma 4 26B A4B Uncensored, EGA abliteration, 8/10, browse 2.93 s 🥇) | `lm-studio` | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | On disk — reload via `lms load 'gemma-4-26b-a4b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-26b-a4b-trevorjs-uncen-q8 -y` (guardrail off first) |
| Prior lm-studio main (DavidAU 40B Heretic, thinking + content channel, 9/10) | `lm-studio` | `qwen36-40b-davidau-heretic-q6k` from `DavidAU/Qwen3.6-40B-...IMatrix-MAX-GGUF` | On disk — reload via `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier qwen36-40b-davidau-heretic-q6k -y` (guardrail off first) |
| Gemma 4 31B Heretic (benchmarked 2026-05-03, 7/10 compliance, Thinking variant) | `lm-studio` | `gemma4-31b-davidau-heretic-q6k` from `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` | On disk — reload via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier gemma4-31b-davidau-heretic-q6k -y` |
| Prior lm-studio main (prithivMLmods Aggressive, prior browse leader, 10/10) | `lm-studio` | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --gpu max --context-length 65536 -y` |
| Prior lm-studio main (HauhauCS Aggressive, search leader) | `lm-studio` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
| Prior production main (JANGTQ4 reference) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Stopped 2026-05-02 |
| DFlash speculative decoding sidecar | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash` | Stopped 2026-05-02. **Target removed from disk 2026-05-07** — re-download via `huggingface-cli download mlx-community/Qwen3.6-35B-A3B-4bit` before restart. Drafter (`z-lab/Qwen3.6-35B-A3B-DFlash`, 905 MiB) still on disk. |
| Previous Ling primary | `vllm-mlx` | `mlx-community/Ling-2.6-flash-mlx-6bit` | Stopped earlier (2026-05-01) |
| Dense Qwen3.6 fallback | `vllm-mlx` | `JANGQ-AI/Qwen3.6-27B-JANG_4M` | Stopped earlier |

To restart vmlx (port 8000):

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  --continuous-batching \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &
```

To restart dflash-mlx (port 8098): see [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md).

## Other Documented Server Roles (all currently stopped)

| Use case | Server | Model | Notes |
|:--|:--|:--|:--|
| DFlash speculative decoding sidecar (port 8098) | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` target *(removed from disk 2026-05-07 — re-download required)* + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter | Decode-bound win on math / constrained JSON (1.46–1.61× at 4–8 K), regresses on prose (0.62–0.98×). Loses to lm-studio on prefill-bound agent loops. Three local patches required first. See [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md). |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` when live | Brew service; restart with `brew services start omlx`. |
| JANGTQ reference | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | On disk — see restart command above. MiniMax-M2.7-JANGTQ-CRACK and Qwen3.6-35B-A3B-JANGTQ4-CRACK removed from disk 2026-05-05. |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` when running | YAML-config multi-model server. |
| RotorQuant / TurboQuant / PlanarQuant KV-cache experiments (port 8099) | `llama-cpp-turboquant` | `unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` + KV-cache compression — see runbook | Provisional sidecar, currently stopped. **Two forks installed:** (a) `johndpope/llama-cpp-turboquant` `feature/planarquant-kv-cache` at `~/llama-cpp-turboquant/` — supports `iso3/4`, `turbo2/3/4`, `planar3/4`; iso3 is slow on 32 K cold prefill (>600 s timeout). (b) `TheTom/llama-cpp-turboquant` `feature/turboquant-kv-cache` at `~/llama-cpp-thetom/` — supports `turbo2/3/4` only with auto-asymmetric `q8_0` K dispatch + 4-magnitude LUT for pre-M5 + sparse V dequant. **TheTom turbo3 was the agent-loop speed leader on 2026-05-06: browse 6.47 s / search 15.64 s — 2× / 2.27× faster than Gemma 4 baseline.** See [`docs/servers/llama-cpp-turboquant/summary.md`](servers/llama-cpp-turboquant/summary.md) and [`docs/models/techniques/model-technique-rotorquant.md`](models/techniques/model-technique-rotorquant.md). |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
