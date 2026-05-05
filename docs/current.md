# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-05

## Production

| Field | Value |
|:--|:--|
| Server | `llmster` / LM Studio headless |
| Model | `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF` (IBM Granite 4.1 30B instruct, Apache 2.0) |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/llmster/`](../configs/clients/llmster/) |
| Runbook | [`docs/servers/llmster/summary.md`](servers/llmster/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# Unload any previously loaded models first
ssh macstudio "~/.lmstudio/bin/lms unload --all"

# Download (30.7 GB, only needed once — already in ~/.cache/hauhau-gguf after 2026-05-05 deploy)
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='unsloth/granite-4.1-30b-GGUF', \
  filename='granite-4.1-30b-Q8_0.gguf', \
  local_dir='/Users/chanunc/.cache/hauhau-gguf')\""

# Hard-link import (already imported — lms import is idempotent if the file exists in models/)
ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo unsloth/granite-4.1-30b-GGUF -y \
  ~/.cache/hauhau-gguf/granite-4.1-30b-Q8_0.gguf"

# Disable guardrail before loading
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='off'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""

ssh macstudio "~/.lmstudio/bin/lms load 'granite-4.1-30b' \
  --gpu max --context-length 65536 \
  --identifier 'granite-4.1-30b-q8' -y"

# Restore guardrail after load
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='high'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""

ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- IBM Granite 4.1 30B Q8_0 (28.57 GiB resident) deployed 2026-05-05, replacing TrevorJS Gemma 4 26B A4B Uncensored as the active Mac Studio LLM process. First Granite family entry; censored RLHF-aligned instruct model, Apache 2.0 license.
- LM Studio handles Granite tool-calls natively — **no parser flags required**. No thinking channel.
- Current benchmarks: API tool harness 5/5 single-call + 3/3 multi-turn (10.37 s); throughput **24.8 tok/s @ 512**, 18.7 tok/s @ 32K; **OpenCode browse 6.24 s / search 10.51 s**. Raw data: [`docs/models/benchmarks/granite-4.1-30b-q8/`](models/benchmarks/granite-4.1-30b-q8/).
- Key deployment gotcha: LM Studio guardrail `mode: "high"` blocks this load too — same workaround (disable → load → restore).
- 65K context probe HTTP 400 — Granite 4.1 sliding window boundary; real queries < 32K are fine.
- vmlx (port 8000) and dflash-mlx (port 8098) remain stopped per Event-4 hygiene.

## Stopped / Documented Fallbacks

These were live before the 2026-05-05 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
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
