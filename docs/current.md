# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-06

## Production

| Field | Value |
|:--|:--|
| Server | `mlx_lm.server` (homebrew Cellar libexec binary, direct) |
| Model | `lmstudio-community/gemma-4-31B-it-MLX-6bit` (Google Gemma 4 31B-it, 6-bit MLX, Apache 2.0) |
| Port | `8000` |
| Auth | None |
| Client template set | [`configs/clients/mlx-openai-server/`](../configs/clients/mlx-openai-server/) |
| Runbook | [`docs/servers/`](servers/) — no dedicated mlx-lm server runbook yet; see mlx-openai-server for the underlying mlx-lm ecosystem |

Launch shape (after Event-4 hygiene):

```bash
# Model is already on disk at ~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit
# (downloaded via snapshot_download 2026-05-01)

ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit \
  --host 0.0.0.0 --port 8000 \
  --max-tokens 8192 \
  > /tmp/mlx-lm-server.log 2>&1 &"
```

Notes:
- Gemma 4 31B-it MLX 6-bit deployed 2026-05-06 on mlx-lm server (direct `mlx_lm.server`). Using the simpler mlx-lm server path (not mlx-openai-server) because: (1) `mlx_lm.server` supports `--draft-model` for future MTP speculative decoding; (2) mlx-openai-server YAML config doesn't expose the same flag.
- **Production-ready binary path**: `/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server` (Python 3.14 venv inside the homebrew formula). The system `python3 -m mlx_lm` and `/opt/homebrew/bin/mlx_lm.server` (which links to python3.11/oMLX's older `mlx_lm`) both fail — the python3.11 install lacks Gemma 4 support. Always launch via the Cellar libexec binary.
- **MTP drafter experiment (2026-05-06) — failed agent-incompatible.** Tried `mlx-community/gemma-4-31B-it-assistant-bf16` (`gemma4_assistant` MTP drafter) paired with the bf16 base via `mlx-vlm 0.5.0` from main (PyPI 0.4.4 lacks the `speculative` submodule). Install includes [PR #1112](https://github.com/Blaizzy/mlx-vlm/pull/1112) (drafter), [#1115](https://github.com/Blaizzy/mlx-vlm/pull/1115) (server dispatch), [#1117](https://github.com/Blaizzy/mlx-vlm/pull/1117) (batching follow-up + `MLX_VLM_SPEC_BATCH_WAIT_MS`). Two passes done — *with* and *without* the coalesce env var — both yielded **8/8 opencode timeouts**. The drafter itself works at upstream-expected efficiency (12.3 tok/s @ 8K, 3.07–4.29 acc/round, matches maintainer's PR #1115 B=1 reference). Two blockers diagnosed, both independent of the drafter PRs:
   1. **mlx-vlm streaming hangs on long-reasoning prompts.** Trivial prompts stream cleanly (`"Reply ok"` → 35 chunks in 2.69 s, `finish_reason: stop`). Agent-style prompts (`"Browse www.example.com"`) flush 0 SSE chunks for 360 s. Server returns 200 eventually but no chunks during generation. Reproducible. `chat_template.jinja` verified byte-identical to 6-bit's working template (16,448 bytes, no diff) — issue [#941](https://github.com/Blaizzy/mlx-vlm/issues/941) ruled out. Likely an upstream bug in mlx-vlm's speculative streaming flush path on long-reasoning generations; worth filing.
   2. **Even with streaming fixed, decode is too slow for agent loops.** Server logs show `[MTP] batch=1 tokens=8192 accept=4.29 rounds=1549` per opencode turn — the model burns through its full `max_tokens=8192` reasoning budget before any content. At 12.3 tok/s = 666 s/turn, exceeds opencode's 300 s wall. `MLX_VLM_SPEC_BATCH_WAIT_MS=10` doesn't help (it coalesces concurrent requests into MTP batches, but agent loops are sequential).
   3. **bf16 OOMs at 32 K+ context** (~118 GB allocation vs 62 GB Metal cap). Independent of the streaming issue.

   Reverted to 6-bit on mlx-lm. mlx-vlm-from-main install kept at `~/mlx-vlm-env/`; bf16 base + drafter weights kept at `~/.cache/huggingface/hub/`. Detail: [`docs/models/per-model/model-summary-gemma.md`](models/per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment) and [bench JSONs](models/benchmarks/gemma-4-31b-bf16-mtp/).
- **Thinking mode ON** — mlx-lm serves Gemma 4 with thinking active by default (via `enable_thinking: true` in chat template). Outputs 3–4× more tokens per turn than the prior lm-studio run (thinking OFF). This explains the higher agent-loop latency.
- Current benchmarks: API tool harness 5/5 single-call (20.73 s multi-turn loop); throughput **20.4 tok/s @ 512**, 14.7 tok/s @ 65K; **OpenCode browse 12.33 s / search 35.55 s** (thinking ON). Raw data: [`docs/models/benchmarks/gemma-4-31b-it-mlx-6bit/`](models/benchmarks/gemma-4-31b-it-mlx-6bit/).
- Prior run on lm-studio (2026-05-01, thinking OFF): browse **5.11 s / search 6.37 s** — fastest agent-loop in this doc. Restart via `lms load` if low-latency thinking-off is needed (see Fallbacks below).
- Log: `ssh macstudio "tail -f /tmp/mlx-lm-server.log"`
- lm-studio (port 1234) and dflash-mlx (port 8098) remain stopped per Event-4 hygiene.

## Stopped / Documented Fallbacks

These were live before the 2026-05-05 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-06, Gemma 4 31B-it thinking OFF, browse **5.11 s 🥇** / search **6.37 s 🏆**) | `lm-studio` | `gemma-4-31b-it-mlx` from `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk — reload via `lms load 'gemma-4-31b-it-mlx' --gpu max --context-length 65536 -y`; then `lms server start --bind 0.0.0.0 --cors`. Guardrail may block — set `modelLoadingGuardrails.mode = "off"` before load, restore after. Verify context with `lms ps` (first load sometimes ignores `--context-length`). |
| Prior production main (2026-05-05, IBM Granite 4.1 30B Q8_0, 24.8 tok/s, browse 6.24 s) | `lm-studio` | `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF` | On disk — reload via `lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y` (guardrail off first; set `modelLoadingGuardrails.mode = "off"` in `~/.lmstudio/settings.json`, then restore to `"high"` after load) |
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

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
