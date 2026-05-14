# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-14 (lm-studio swap to prithivMLmods Q3.6-27B-GLM-5.1-DA — agent-functional after bench-rig fix)

## Production

| Field | Value |
|:--|:--|
| Server | `lm-studio` (LM Studio headless, port 1234) |
| Model | `qwen3.6-27b-glm51-da-q4km` (prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M — dense 27 B + ViT, prithivMLmods abliteration on Qwen3.6-27B + GLM-5.1 reasoning-trace distillation, think-on, Apache 2.0, 15.41 GB on disk / 15.41 GiB resident) |
| Port | `1234` (LAN-bound `0.0.0.0:1234`, CORS on, no auth) |
| Auth | None |
| Client template set | [`docs/models/uncen-model/client-configs/lm-studio/`](models/uncen-model/client-configs/lm-studio/) — uncensored-side templates; OpenCode entry updated, default unchanged |
| Runbook | [`docs/servers/lm-studio/summary.md`](servers/lm-studio/summary.md) · model writeup [`docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md`](models/uncen-model/qwen36-27b-glm51-da-benchmark.md) · per-model section [`docs/models/per-model/model-summary-qwen-3-6.md`](models/per-model/model-summary-qwen-3-6.md) |

> 🟢 **Agent-loop verified.** OpenCode 1.14.50 + macstudio-lm-studio provider: browse **11.62 s** wall (9.95 s LLM) / search **19.47 s** wall (17.37 s LLM), 2 turns, `webfetch` fired correctly across all 3 runs of each scenario. API harness `bench_api_tool_call.py` passes **5/5** single-call + **3/3** multi-turn at the OpenAI layer; `harmful_behaviors` refusal slice **9/10 keyword-complied / 38.4 s avg** at `max_tokens=1024`. Earlier `agent_turns=0` reading was a bench-script regression on OpenCode 1.14.50 — `subprocess.run(env=os.environ.copy())` inherited the parent's `PWD`, OpenCode bootstrapped in the wrong project dir and sank its JSON event stream into the wrong session DB. Fix landed in `scripts/bench/bench_agent_tool_call.py` (pin `env["PWD"] = cwd`); benefits every future agent-bench run on opencode 1.14.50+.

Launch shape (Event-4 hygiene already done — Osaurus + ZAYA1-8B were stopped 2026-05-14 before this deploy):

```bash
# One-time download (15.41 GB Q4_K_M GGUF):
ssh macstudio "mkdir -p ~/.cache/hauhau-gguf; \
  ~/comfyui/.venv/bin/hf download prithivMLmods/Q3.6-27B-GLM-5.1-DA-GGUF \
  Q3.6-27B-GLM-5.1-DA.Q4_K_M.gguf --local-dir ~/.cache/hauhau-gguf"

# Hard-link import into LM Studio's registry (no duplicate on disk):
ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo prithivMLmods/Q3.6-27B-GLM-5.1-DA-GGUF -y \
  ~/.cache/hauhau-gguf/Q3.6-27B-GLM-5.1-DA.Q4_K_M.gguf"

# Load with stable identifier + 65K context (15.4 GiB ≪ guardrail threshold, no dance):
ssh macstudio "~/.lmstudio/bin/lms load 'q3.6-27b-glm-5.1-da' \
  --gpu max --context-length 65536 \
  --identifier 'qwen3.6-27b-glm51-da-q4km' -y"

# Start server (LAN-bound, CORS):
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- Switched 2026-05-14 from vmlx-swift-lm + Zyphra ZAYA1-8B JANGTQ4 to lm-studio + prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M. ZAYA1 was agent-broken at Osaurus pin `b9da180`; the new main is agent-functional after a session-2 bench-script `PWD` fix. TrevorJS Gemma 4 31B-it Uncensored is still on disk as the alt-fallback if you want a smaller, non-thinking dense Gemma.
- **API-level performance** (2026-05-14 on LM Studio headless via port 1234, single live process): smoke 5/5 single-call + 3/3 multi-turn at the OpenAI API layer. `bench_api_server.py` 1+2 runs at 512 / 4 K / 8 K / 32 K: **TTFT 0.36 / 0.35 / 0.38 / 0.55 s**, **decode 31.0 / 29.7 / 29.3 / 26.7 tok/s** (dense 27 B Q4_K_M, ~2.7× slower than the 35B-A3B MoE sibling), **prefill 1 476 / 11 950 / 21 611 / 59 464 tok/s**. Refusal-rate harness: **9/10 keyword-complied** at `max_tokens=1024 temp=1.0` (P10 refusal phrase leaked into `reasoning_content` only, visible `content` empty). Raw data: [`docs/models/benchmarks/qwen36-27b-glm51-da/`](models/benchmarks/qwen36-27b-glm51-da/).
- **Agent-loop (post bench-rig fix).** OpenCode 1.14.50: browse **11.62 s wall / 9.95 s LLM**, search **19.47 s wall / 17.37 s LLM**, 2 turns + `webfetch` fired on every run. Lands between Dolphin 3.0 R1 Mistral 24B (7.5 / 34.5 s) and HauhauCS Qwen3.6-27B Balanced Q8_K_P (11.16 / 28.91 s) — search is 9.4 s faster than HauhauCS Balanced thanks to Q4_K_M vs Q8_K_P. First reading reported `agent_turns=0` because `subprocess.run(env=os.environ.copy())` inherited the parent shell's `PWD` and OpenCode 1.14.50+ honours `PWD` over `cwd` when bootstrapping, sinking the JSON stream into the wrong session DB. Fix landed in `scripts/bench/bench_agent_tool_call.py` — `env["PWD"] = cwd`. Full triage in [`docs/models/uncen-model/qwen36-27b-glm51-da-benchmark.md#bench-rig-regression-discovered-during-this-deploy-2026-05-14`](models/uncen-model/qwen36-27b-glm51-da-benchmark.md#bench-rig-regression-discovered-during-this-deploy-2026-05-14).
- **Apache 2.0** — prithivMLmods/Q3.6-27B-GLM-5.1-DA is Apache 2.0. Dense 27 B Qwen3.6 base with prithivMLmods refusal-direction abliteration (`Qwen3.6-27B-abliterated-rMAX`) + GLM-5.1 reasoning-trace distillation on `Jackrong/GLM-5.1-Reasoning-1M-Cleaned` (572 K). Includes vision projector (`mmproj-f16.gguf`, 870 MB, loaded text-only here).
- **Reasoning channel** — LM Studio auto-detects Qwen `<think>` and exposes `reasoning_content` to OpenAI-compat clients. Median reasoning trace ~4 700 chars at `max_tokens=1024`; very long internal monologue style courtesy of the GLM-5.1 distillation.
- Tool-calling parsing is **built into LM Studio** (no `--tool-call-parser` flag) — model emits Qwen XML, parser converts to `tool_calls[]` at the API layer.
- **Disk pressure** — chose Q4_K_M (15.4 GB) over Q6_K (20.6 GB) because `/System/Volumes/Data` was at 95 % full pre-deploy. Re-bench at Q6_K once disk is cleared.
- Log: `ssh macstudio "~/.lmstudio/bin/lms log stream | tail -30"` (LM Studio doesn't write to `/tmp/`).
- Other servers stopped: port 8000 free (vllm-mlx / mlx-openai-server / oMLX / vmlx all stopped), port 1337 free (Osaurus stopped 2026-05-14 as part of pre-bench hygiene), port 8098 / 8099 free. comfyui (port 8188) is still up and orthogonal. Previously deployed mains (Zyphra ZAYA1-8B on Osaurus, TrevorJS Gemma 4 31B-it Uncensored, lmstudio-community Gemma 4 26B A4B-it Q8_0, unsloth Qwen3.6-35B-A3B-UD-Q6_K, Granite 4.1 30B Q8_0, Gemma 4 31B-it MLX 6-bit, DavidAU Heretic family, prithivMLmods Aggressive) all stay on disk and are restartable from the Fallbacks table below.

## Active Sidecars (no port-bound daemon)

| Use case | Path | Model | Notes |
|:--|:--|:--|:--|
| Speech-to-text | `~/qwen-asr-env/` (Python API, transformers + MPS) | `Qwen/Qwen3-ASR-1.7B` (bf16, 4.7 GB) | Deployed 2026-05-08. RTF 19.06× on 15 s English clip, 0.79 s avg. No `/v1/audio/transcriptions` endpoint — call `Qwen3ASRModel.transcribe(audio=…)` from a Python script. Doesn't compete with port 8000 / 1234 / 8098 / 8099. Runbook: [`docs/servers/qwen-asr/summary.md`](servers/qwen-asr/summary.md). |
| Image generation (port 8188) | `~/comfyui/` (PyTorch 2.11 + MPS, comfy-cli managed) | `SeeSee21/Z-Anime` AIO BF16 — Distill-4-step + Base (~19 GiB each, S3-DiT 6B, Apache-2.0) | Deployed 2026-05-08. Web UI only at `http://192.168.31.4:8188`; no `/v1/images/generations` shim. Wall time @ 1024² (3 timed runs after 1 warm-up): Distill-4-step **17.75 s** (CFG 1.0), Base 28-step **235.16 s** (CFG 4.0). Doesn't compete with port 8000 / 1234 / 8098 / 8099. Launch: `nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention > /tmp/comfyui.log 2>&1 &`. Runbook: [`docs/servers/comfyui/summary.md`](servers/comfyui/summary.md). |

## Stopped / Documented Fallbacks

Models are off (unloaded or stopped) until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-12 → 2026-05-14, Zyphra ZAYA1-8B JANGTQ4 on Osaurus, top-1 CCA + MoE 8.4B/760M, Apache 2.0, 4.99 GB on disk, **agent-broken** at cask 0.18.13 / engine pin `b9da180`) | `vmlx-swift-lm` (Osaurus) | `zaya1-8b-jangtq4` from `JANGQ-AI/ZAYA1-8B-JANGTQ4` | On disk at `~/.osaurus/models/JANGQ-AI/ZAYA1-8B-JANGTQ4`. Osaurus stopped 2026-05-14 in this skill's pre-bench hygiene. Restart with: `OSU_MODELS_DIR=$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 > /tmp/osaurus.log 2>&1 &`. Same JANGTQ HTTP-path regression as documented for ZAYA1: 7-8 tok/s vs M4-Max-RunBench 57 tok/s — wait for [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) to ship `cb8b3df` before relying on it. |
| Prior production main (2026-05-10 → 2026-05-12, TrevorJS Gemma 4 31B-it Uncensored Q4_K_M, dense 31B no-think, Apache 2.0, 17.40 GiB resident, harness 6-7/10 / manual 10/10 useful-compliance, browse 6.63 s warm) | `lm-studio` | `gemma4-31b-it-uncensored-trevorjs-q4km` from `TrevorJS/gemma-4-31B-it-uncensored-GGUF` | On disk and registered in `lms ls` as `gemma-4-31b-it-uncensored`. Reload via `lms load 'gemma-4-31b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-31b-it-uncensored-trevorjs-q4km -y` (guardrail dance optional — 17.4 GiB sits below the 25 % threshold). Use this when you want a faster non-thinking dense Gemma alternative to the current GLM-5.1-DA main — 30 tok/s decode, browse 6.63 s warm. **Note:** loading this displaces the current GLM-5.1-DA main (only one model fits on LM Studio per port-1234 instance unless you raise the parallel-model limit). |
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
