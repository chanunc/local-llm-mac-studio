# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-06

## Production

| Field | Value |
|:--|:--|
| Server | `mlx-lm server` (`python -m mlx_lm server`, direct) |
| Model | `lmstudio-community/gemma-4-31B-it-MLX-6bit` (Google Gemma 4 31B-it, 6-bit MLX, Apache 2.0) |
| Port | `8000` |
| Auth | None |
| Client template set | [`configs/clients/mlx-openai-server/`](../configs/clients/mlx-openai-server/) |
| Runbook | [`docs/servers/`](servers/) — no dedicated mlx-lm server runbook yet; see mlx-openai-server for the underlying mlx-lm ecosystem |

Launch shape (after Event-4 hygiene):

```bash
# Model is already on disk at ~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit
# (downloaded via snapshot_download 2026-05-01)

ssh macstudio "nohup python3 -m mlx_lm server \
  --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit \
  --host 0.0.0.0 --port 8000 \
  --max-tokens 8192 --prompt-cache-size 5 \
  > /tmp/mlx-lm-server.log 2>&1 &"
```

Notes:
- Gemma 4 31B-it MLX 6-bit deployed 2026-05-06 on mlx-lm server (direct `python -m mlx_lm server`). Using the simpler mlx-lm server path (not mlx-openai-server) because: (1) `python -m mlx_lm server` supports `--draft-model` for future MTP speculative decoding; (2) mlx-openai-server YAML config doesn't expose the same flag. The MTP drafter (`mlx-community/gemma-4-31B-it-assistant-bf16`, 839 MB) is already cached at `~/.cache/huggingface/hub/models--mlx-community--gemma-4-31B-it-assistant-bf16/snapshots/28e92270316e89288579ec59c17939541d9ca433` — add `--draft-model <snap-path> --num-draft-tokens 3` once mlx-lm adds `gemma4_assistant` arch support.
- **Thinking mode ON** — mlx-lm serves Gemma 4 with thinking active by default (via `enable_thinking: true` in chat template). Outputs 3–4× more tokens per turn than the prior llmster run (thinking OFF). This explains the higher agent-loop latency.
- Current benchmarks: API tool harness 5/5 single-call (20.73 s multi-turn loop); throughput **20.4 tok/s @ 512**, 14.7 tok/s @ 65K; **OpenCode browse 12.33 s / search 35.55 s** (thinking ON). Raw data: [`docs/models/benchmarks/gemma-4-31b-it-mlx-6bit/`](models/benchmarks/gemma-4-31b-it-mlx-6bit/).
- Prior run on llmster (2026-05-01, thinking OFF): browse **5.11 s / search 6.37 s** — fastest agent-loop in this doc. Restart via `lms load` if low-latency thinking-off is needed (see Fallbacks below).
- Log: `ssh macstudio "tail -f /tmp/mlx-lm-server.log"`
- llmster (port 1234) and dflash-mlx (port 8098) remain stopped per Event-4 hygiene.

## Stopped / Documented Fallbacks

These were live before the 2026-05-05 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-06, Gemma 4 31B-it thinking OFF, browse **5.11 s 🥇** / search **6.37 s 🏆**) | `llmster` | `gemma-4-31b-it-mlx` from `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk — reload via `lms load 'gemma-4-31b-it-mlx' --gpu max --context-length 65536 -y`; then `lms server start --bind 0.0.0.0 --cors`. Guardrail may block — set `modelLoadingGuardrails.mode = "off"` before load, restore after. Verify context with `lms ps` (first load sometimes ignores `--context-length`). |
| Prior production main (2026-05-05, IBM Granite 4.1 30B Q8_0, 24.8 tok/s, browse 6.24 s) | `llmster` | `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF` | On disk — reload via `lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y` (guardrail off first; set `modelLoadingGuardrails.mode = "off"` in `~/.lmstudio/settings.json`, then restore to `"high"` after load) |
| Prior llmster main (TrevorJS Gemma 4 26B A4B Uncensored, EGA abliteration, 8/10, browse 2.93 s 🥇) | `llmster` | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | On disk — reload via `lms load 'gemma-4-26b-a4b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-26b-a4b-trevorjs-uncen-q8 -y` (guardrail off first) |
| Prior llmster main (DavidAU 40B Heretic, thinking + content channel, 9/10) | `llmster` | `qwen36-40b-davidau-heretic-q6k` from `DavidAU/Qwen3.6-40B-...IMatrix-MAX-GGUF` | On disk — reload via `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier qwen36-40b-davidau-heretic-q6k -y` (guardrail off first) |
| Gemma 4 31B Heretic (benchmarked 2026-05-03, 7/10 compliance, Thinking variant) | `llmster` | `gemma4-31b-davidau-heretic-q6k` from `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` | On disk — reload via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier gemma4-31b-davidau-heretic-q6k -y` |
| Prior llmster main (prithivMLmods Aggressive, prior browse leader, 10/10) | `llmster` | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --gpu max --context-length 65536 -y` |
| Prior llmster main (HauhauCS Aggressive, search leader) | `llmster` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
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
| DFlash speculative decoding sidecar (port 8098) | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` target + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter | Decode-bound win on math / constrained JSON (1.46–1.61× at 4–8 K), regresses on prose (0.62–0.98×). Loses to llmster on prefill-bound agent loops. Three local patches required first. See [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md). |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` when live | Brew service; restart with `brew services start omlx`. |
| JANGTQ reference | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | On disk — see restart command above. MiniMax-M2.7-JANGTQ-CRACK and Qwen3.6-35B-A3B-JANGTQ4-CRACK removed from disk 2026-05-05. |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` when running | YAML-config multi-model server. |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
