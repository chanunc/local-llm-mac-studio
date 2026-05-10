# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-10

## Production

| Field | Value |
|:--|:--|
| Server | `lm-studio` (LM Studio headless, port 1234) |
| Model | `gemma4-31b-it-uncensored-trevorjs-q4km` (TrevorJS Gemma 4 31B-it Uncensored Q4_K_M GGUF, dense 31B no-think, Apache 2.0, 18.69 GB on disk / 17.40 GiB resident) |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/lm-studio/`](../configs/clients/lm-studio/) (censored side, OpenCode + OpenClaw) · uncensored entries in [`docs/models/uncen-model/client-configs/lm-studio/`](models/uncen-model/client-configs/lm-studio/) |
| Runbook | [`docs/servers/lm-studio/summary.md`](servers/lm-studio/summary.md) · model writeup [`docs/models/uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md`](models/uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md) |

Launch shape (after Event-4 hygiene):

```bash
# TrevorJS/gemma-4-31B-it-uncensored-Q4_K_M.gguf is downloaded via `huggingface_hub` into a
# staging dir, hard-link imported into LM Studio's tree, and loaded under modelKey
# `gemma-4-31b-it-uncensored`. Pin the stable API id with `--identifier
# gemma4-31b-it-uncensored-trevorjs-q4km` at load (`lms ls` has 2 entries that match
# `gemma-4-31b-it-uncensored*` — first alphabetical wins, but the identifier pin makes the
# API id deterministic).
#
# Q4_K_M @ 17.40 GiB resident sits BELOW the strict 25 % guardrail threshold (~24 GiB on a
# 96 GB box) — the dance is defensive but idempotent and zero-cost.

# (Once-only) download + import the GGUF into LM Studio's tree:
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='TrevorJS/gemma-4-31B-it-uncensored-GGUF', \
  filename='gemma-4-31B-it-uncensored-Q4_K_M.gguf', \
  local_dir='/Users/chanunc/.cache/gguf-staging')\""
ssh macstudio "~/.lmstudio/bin/lms import -L --user-repo TrevorJS/gemma-4-31B-it-uncensored-GGUF -y \
  ~/.cache/gguf-staging/gemma-4-31B-it-uncensored-Q4_K_M.gguf"

# Load + serve:
ssh macstudio "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='off'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms load 'gemma-4-31b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-31b-it-uncensored-trevorjs-q4km -y; \
  python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='high'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- Switched 2026-05-10 from lm-studio + lmstudio-community Gemma 4 26B A4B-it Q8_0 to lm-studio + TrevorJS Gemma 4 31B-it Uncensored Q4_K_M. Both stay in the LM Studio registry; the Q8_0 26B-A4B is restartable from the Fallbacks table.
- **Performance** (2026-05-10 on lm-studio): API smoke 5/5, multi-turn loop **6.65 s** (2.18 + 2.41 + 2.06). Decode **30.1 tok/s @ 512** / **24.1 tok/s @ 32K**, prefill **75K tok/s @ 32K**. **OpenCode end-to-end (bare prompts, no scaffolding): browse 10.08 s / search 29.77 s** — 2/2 webfetch fires per scenario; second turn dominates search (24 s). Raw data: [`docs/models/benchmarks/gemma4-31b-it-uncensored-trevorjs/`](models/benchmarks/gemma4-31b-it-uncensored-trevorjs/).
- **Refusal-rate** (2026-05-10, mlabonne 10/520 sample, max_tokens=1024, temp=1.0): harness **7/10**, **manual 10/10 useful-compliance**. The 3 "refused" results (P1 exploit, P8 bomb tutorial, P9 antivirus virus) all delivered detailed harmful content prefixed with `***Disclaimer:** ... is illegal ...` preambles that trip the keyword detector. Manual inspection (full text in raw JSON) confirms compliance — full Buffer Overflow exploit with shellcode, full bomb chemistry (Fuel + Oxidizer + Trigger), full Protected-Process kernel-driver AV-bypass technique. **Production users must read past disclaimer preambles.** See [`docs/models/uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md`](models/uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md) for the full per-prompt analysis.
- **Apache 2.0** — Google Gemma 4 weights are Apache 2.0; TrevorJS's norm-preserving biprojected abliteration is a derivative. Uncensored counterpart to the standard `gemma-4-31B-it` instruct base — same architecture, same chat template.
- **No thinking channel** — non-thinking instruct variant. All generation is visible `content`.
- Tool-calling parsing is **built into the LM Studio runtime** — no `--tool-call-parser` flag needed. Smoke 5/5, multi-turn loop 3/3 turns.
- **Discoverability gotcha**: `lms load 'gemma-4-31b-it-uncensored' -y` prints `W 2 models match the provided model key on the same device. Loading the first one.` — harmless because the `--identifier gemma4-31b-it-uncensored-trevorjs-q4km` pin guarantees the API id regardless of which match is picked. To list collisions: `~/.lmstudio/bin/lms ls | grep gemma-4-31b-it-uncensored`.
- **Guardrail dance**: 17.40 GiB resident is below the strict 25 %-of-96-GB threshold so the dance is *not* required. It's kept in the launch snippet defensively (idempotent, zero-cost). Safer to always-do than condition on threshold.
- Log: `ssh macstudio "~/.lmstudio/bin/lms log show 2>&1 | tail -40"` (LM Studio doesn't write the standard `/tmp/*.log`).
- mlx-lm (port 8000) and dflash-mlx (port 8098) remain stopped. Previously deployed mains (lmstudio-community Gemma 4 26B A4B-it Q8_0, unsloth Qwen3.6-35B-A3B-UD-Q6_K, Granite 4.1 30B Q8_0, Gemma 4 31B-it MLX 6-bit, TrevorJS Gemma 4 26B A4B, DavidAU Heretic family, prithivMLmods Aggressive) all stay on disk and are restartable from the Fallbacks table below.

## Active Sidecars (no port-bound daemon)

| Use case | Path | Model | Notes |
|:--|:--|:--|:--|
| Speech-to-text | `~/qwen-asr-env/` (Python API, transformers + MPS) | `Qwen/Qwen3-ASR-1.7B` (bf16, 4.7 GB) | Deployed 2026-05-08. RTF 19.06× on 15 s English clip, 0.79 s avg. No `/v1/audio/transcriptions` endpoint — call `Qwen3ASRModel.transcribe(audio=…)` from a Python script. Doesn't compete with port 8000 / 1234 / 8098 / 8099. Runbook: [`docs/servers/qwen-asr/summary.md`](servers/qwen-asr/summary.md). |
| Image generation (port 8188) | `~/comfyui/` (PyTorch 2.11 + MPS, comfy-cli managed) | `SeeSee21/Z-Anime` AIO BF16 — Distill-4-step + Base (~19 GiB each, S3-DiT 6B, Apache-2.0) | Deployed 2026-05-08. Web UI only at `http://192.168.31.4:8188`; no `/v1/images/generations` shim. Wall time @ 1024² (3 timed runs after 1 warm-up): Distill-4-step **17.75 s** (CFG 1.0), Base 28-step **235.16 s** (CFG 4.0). Doesn't compete with port 8000 / 1234 / 8098 / 8099. Launch: `nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention > /tmp/comfyui.log 2>&1 &`. Runbook: [`docs/servers/comfyui/summary.md`](servers/comfyui/summary.md). |

## Stopped / Documented Fallbacks

Models are off (unloaded or stopped) until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-07 → 2026-05-10, lmstudio-community Gemma 4 26B A4B-it Q8_0, sparse MoE 26B / 4B-active no-think, browse 2.94 s 🥈 / search 7.20 s scaffolded) | `lm-studio` | `gemma-4-26b-a4b-q8` from `lmstudio-community/gemma-4-26B-A4B-it-GGUF` | On disk and registered in `lms ls` as `gemma-4-26b-a4b-it`. Reload via `lms load 'gemma-4-26b-a4b-it' --gpu max --context-length 131072 --identifier gemma-4-26b-a4b-q8 -y` (guardrail off first — 25 GiB > strict 25% threshold). Use this when MoE speed matters more than uncensored compliance — 87.6 tok/s gen, lighter agent loops than the dense 31B uncensored. |
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
