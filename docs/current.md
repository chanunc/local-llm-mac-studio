# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-03

## Production

| Field | Value |
|:--|:--|
| Server | `llmster` / LM Studio headless |
| Model | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` (EGA abliteration on Gemma 4 26B MoE) |
| Port | `1234` |
| Auth | None |
| Client template set | [`docs/models/uncen-model/client-configs/llmster/`](models/uncen-model/client-configs/llmster/) |
| Runbook | [`docs/servers/llmster/summary.md`](servers/llmster/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# Unload any previously loaded models first
ssh macstudio "~/.lmstudio/bin/lms unload --all"

# Download (26.9 GB, only needed once — already in ~/.cache/gguf-staging after 2026-05-03 deploy)
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF', \
  filename='gemma-4-26B-A4B-it-uncensored-Q8_0.gguf', \
  local_dir='/Users/chanunc/.cache/gguf-staging')\""

# Hard-link import (already imported — lms import is idempotent if the file exists in models/)
ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF -y \
  ~/.cache/gguf-staging/gemma-4-26B-A4B-it-uncensored-Q8_0.gguf"

# Disable guardrail before loading (LM Studio free-page heuristic blocks large loads)
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='off'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""

ssh macstudio "~/.lmstudio/bin/lms load 'gemma-4-26b-a4b-it-uncensored' \
  --gpu max --context-length 65536 \
  --identifier 'gemma4-26b-a4b-trevorjs-uncen-q8' -y"

# Restore guardrail after load
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='high'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""

ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- TrevorJS Gemma 4 26B A4B Uncensored Q8_0 (25.02 GiB resident) deployed 2026-05-03, replacing DavidAU Qwen3.6-40B Heretic as the active Mac Studio LLM process. First Gemma 4 MoE uncensored entry; non-thinking instruct variant.
- LM Studio handles Gemma 4 tool-calls natively — **no parser flags required**. No thinking channel — all tokens in visible `content`.
- Current benchmarks: API tool harness 5/5 single-call + 3/3 multi-turn (2.14 s); refusal 8/10 (P4 bomb, P7 racism refused), avg 11.75 s; throughput **87.6 tok/s @ 512**, 76.5 tok/s @ 32K; **OpenCode browse 2.93 s 🥇 / search 7.35 s** — new all-time browse leader (42% faster than prior 5.05 s). Raw data: [`docs/models/benchmarks/gemma4-26b-a4b-trevorjs-uncen/`](models/benchmarks/gemma4-26b-a4b-trevorjs-uncen/).
- Key deployment gotcha: LM Studio guardrail `mode: "high"` blocks this load too — same workaround as prior llmster models (disable → load → restore).
- 65K context probe HTTP 400 — Gemma 4 sliding window boundary; real queries < 32K are fine.
- vmlx (port 8000) and dflash-mlx (port 8098) remain stopped per Event-4 hygiene.

## Stopped / Documented Fallbacks

These were live before the 2026-05-03 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior llmster main (DavidAU 40B Heretic, thinking + content channel, 9/10) | `llmster` | `qwen36-40b-davidau-heretic-q6k` from `DavidAU/Qwen3.6-40B-...IMatrix-MAX-GGUF` | On disk — reload via `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier qwen36-40b-davidau-heretic-q6k -y` (guardrail off first) |
| Gemma 4 31B Heretic (benchmarked 2026-05-03, 7/10 compliance, Thinking variant) | `llmster` | `gemma4-31b-davidau-heretic-q6k` from `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` | On disk — reload via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier gemma4-31b-davidau-heretic-q6k -y` |
| Prior llmster main (prithivMLmods Aggressive, prior browse leader, 10/10) | `llmster` | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --gpu max --context-length 65536 -y` |
| Prior llmster main (HauhauCS Aggressive, search leader) | `llmster` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
| Prior production main (JANGTQ4 reference) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Stopped 2026-05-02 |
| Prior llmster sidecar (Balanced GGUF, dense + VL) | `llmster` (alt slot) | `qwen3.6-27b-uncensored-balanced-q8kp` from `HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced` | Cataloged on disk, not loaded — reload via `lms load qwen3.6-27b-uncensored-hauhaucs-balanced --identifier qwen3.6-27b-uncensored-balanced-q8kp -y` |
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
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &
```

To restart dflash-mlx (port 8098): see [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md).

## Other Documented Server Roles (all currently stopped)

| Use case | Server | Model | Notes |
|:--|:--|:--|:--|
| DFlash speculative decoding sidecar (port 8098) | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` target + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter | Decode-bound win on math / constrained JSON (1.46–1.61× at 4–8 K), regresses on prose (0.62–0.98×). Loses to llmster on prefill-bound agent loops. Three local patches required first. See [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md). |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` when live | Brew service; restart with `brew services start omlx`. |
| JANGTQ CRACK reference | `vmlx` | `dealignai/MiniMax-M2.7-JANGTQ-CRACK` | bundled-Python; same launch shape as the Osaurus restart command above. |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` when running | YAML-config multi-model server. |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
