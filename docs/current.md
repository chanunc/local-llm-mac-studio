# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-06

## Production

| Field | Value |
|:--|:--|
| Server | `lm-studio` (LM Studio headless, port 1234) |
| Model | `granite-4.1-30b-q8` (IBM Granite 4.1 30B Q8_0 GGUF, dense instruct, Apache 2.0, 28.57 GiB on disk) |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/lm-studio/`](../configs/clients/lm-studio/) (OpenCode + OpenClaw) |
| Runbook | [`docs/servers/lm-studio/summary.md`](servers/lm-studio/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# Granite 4.1 30B GGUF is on disk in LM Studio's model registry as `granite-4.1-30b`.
# Guardrail must be temporarily set to "off" in ~/.lmstudio/settings.json before initial load,
# then restored to "high" once IDLE.

ssh macstudio "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='off'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y; \
  python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; d=json.loads(p.read_text()); d['modelLoadingGuardrails']['mode']='high'; p.write_text(json.dumps(d, indent=2))\"; \
  ~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- Switched 2026-05-06 from mlx-lm + Gemma 4 31B-it MLX 6-bit to lm-studio + Granite 4.1 30B Q8_0 after Event-4 hygiene (`pkill -f mlx_lm.server`). Granite was previously the lm-studio main on 2026-05-05; the model file remained on disk so the swap was a `lms load` away.
- **Performance** (from prior 2026-05-05 deploy on lm-studio): 24.8 tok/s gen, **OpenCode browse 6.24 s / search 10.51 s**, 2/2 turns, non-thinking. Raw data: [`docs/models/benchmarks/granite-4.1-30b-it-q8-gguf/`](models/benchmarks/granite-4.1-30b-it-q8-gguf/).
- **Apache 2.0 license** — fully permissive for derivative work and hosted re-deployment, unlike Gemma's Google-specific terms.
- Tool-calling and reasoning parsing are **built into the LM Studio runtime** for Granite — no `--tool-call-parser` / `--reasoning-parser` flags needed.
- **Guardrail dance**: LM Studio's resource-guardrail (default `mode: "high"`) blocks loading a 28 GB model on a 96 GB box. The launch snippet above flips it `off` for the load and restores `high` immediately after; safer than leaving guardrails disabled.
- Log: `ssh macstudio "~/.lmstudio/bin/lms log show 2>&1 | tail -40"` (LM Studio doesn't write the standard `/tmp/*.log`).
- mlx-lm (port 8000) and dflash-mlx (port 8098) are now stopped. The previous main (Gemma 4 31B-it MLX 6-bit on mlx-lm) remains on disk and is restartable from the Fallbacks table below.

## Stopped / Documented Fallbacks

These were live before the 2026-05-05 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-06, Gemma 4 31B-it MLX 6-bit on mlx-lm, thinking ON, browse 12.33 s / search 35.55 s) | `mlx-lm` (port 8000) | `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk at `~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit`. Restart via the launch shape preserved in this file's git history (commit `1584c46` had the Cellar libexec `mlx_lm.server` invocation as the active Production block). |
| Prior lm-studio main (Gemma 4 31B-it MLX 6-bit, thinking OFF, browse **5.11 s 🥇** / search **6.37 s 🏆**) | `lm-studio` | `gemma-4-31b-it-mlx` from `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk — reload via `lms load 'gemma-4-31b-it-mlx' --gpu max --context-length 65536 -y`; then `lms server start --bind 0.0.0.0 --cors`. Guardrail may block — set `modelLoadingGuardrails.mode = "off"` before load, restore after. Verify context with `lms ps` (first load sometimes ignores `--context-length`). |
| Prior lm-studio main (TrevorJS Gemma 4 26B A4B Uncensored, EGA abliteration, 8/10, browse 2.93 s 🥇) | `lm-studio` | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | On disk — reload via `lms load 'gemma-4-26b-a4b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-26b-a4b-trevorjs-uncen-q8 -y` (guardrail off first) |
| Prior lm-studio main (DavidAU 40B Heretic, thinking + content channel, 9/10) | `lm-studio` | `qwen36-40b-davidau-heretic-q6k` from `DavidAU/Qwen3.6-40B-...IMatrix-MAX-GGUF` | On disk — reload via `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier qwen36-40b-davidau-heretic-q6k -y` (guardrail off first) |
| Gemma 4 31B Heretic (benchmarked 2026-05-03, 7/10 compliance, Thinking variant) | `lm-studio` | `gemma4-31b-davidau-heretic-q6k` from `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` | On disk — reload via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier gemma4-31b-davidau-heretic-q6k -y` |
| Prior lm-studio main (prithivMLmods Aggressive, prior browse leader, 10/10) | `lm-studio` | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --gpu max --context-length 65536 -y` |
| Prior lm-studio main (HauhauCS Aggressive, search leader) | `lm-studio` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
| Prior production main (JANGTQ4 reference) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Stopped 2026-05-02 |
| DFlash speculative decoding sidecar | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash` | Stopped 2026-05-02 |
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
| DFlash speculative decoding sidecar (port 8098) | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` target + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter | Decode-bound win on math / constrained JSON (1.46–1.61× at 4–8 K), regresses on prose (0.62–0.98×). Loses to lm-studio on prefill-bound agent loops. Three local patches required first. See [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md). |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` when live | Brew service; restart with `brew services start omlx`. |
| JANGTQ reference | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | On disk — see restart command above. MiniMax-M2.7-JANGTQ-CRACK and Qwen3.6-35B-A3B-JANGTQ4-CRACK removed from disk 2026-05-05. |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` when running | YAML-config multi-model server. |
| RotorQuant / TurboQuant / PlanarQuant KV-cache experiments (port 8099) | `llama-cpp-turboquant` | `unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` + KV-cache compression — see runbook | Provisional sidecar, currently stopped. **Two forks installed:** (a) `johndpope/llama-cpp-turboquant` `feature/planarquant-kv-cache` at `~/llama-cpp-turboquant/` — supports `iso3/4`, `turbo2/3/4`, `planar3/4`; iso3 is slow on 32 K cold prefill (>600 s timeout). (b) `TheTom/llama-cpp-turboquant` `feature/turboquant-kv-cache` at `~/llama-cpp-thetom/` — supports `turbo2/3/4` only with auto-asymmetric `q8_0` K dispatch + 4-magnitude LUT for pre-M5 + sparse V dequant. **TheTom turbo3 was the agent-loop speed leader on 2026-05-06: browse 6.47 s / search 15.64 s — 2× / 2.27× faster than Gemma 4 baseline.** See [`docs/servers/llama-cpp-turboquant/summary.md`](servers/llama-cpp-turboquant/summary.md) and [`docs/models/techniques/model-technique-rotorquant.md`](models/techniques/model-technique-rotorquant.md). |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
