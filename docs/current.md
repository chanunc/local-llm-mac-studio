# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-02

## Production

| Field | Value |
|:--|:--|
| Server | `llmster` / LM Studio headless |
| Model | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` (prithivMLmods abliteration) |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/llmster/`](../configs/clients/llmster/) |
| Runbook | [`docs/servers/llmster/summary.md`](servers/llmster/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# Unload any previously loaded models first
ssh macstudio "~/.lmstudio/bin/lms unload --all"

ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF', \
  filename='Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf', \
  local_dir='/Users/chanunc/.cache/prithiv-gguf')\""

ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF -y \
  ~/.cache/prithiv-gguf/Qwen3.6-35B-A3B-Uncensored-Aggressive.Q6_K.gguf"

# NOTE: LM Studio guardrail may block with 'insufficient system resources' (mode: "high" counts
# only free pages ~24 GB, ignoring ~60 GB inactive). Fix:
#   python3 -c "import json; s=json.load(open(f'{home}/.lmstudio/settings.json')); \
#     s['modelLoadingGuardrails']['mode']='off'; json.dump(s, open(f'{home}/.lmstudio/settings.json','w'), indent=2)"
# Restore 'mode' to 'high' after load.
ssh macstudio "~/.lmstudio/bin/lms load 'qwen3.6-35b-a3b-uncensored-aggressive' \
  --gpu max --context-length 65536 \
  --identifier 'qwen3.6-35b-a3b-prithiv-aggressive-q6k' -y"

ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- prithivMLmods Qwen3.6-35B-A3B Uncensored Aggressive (mradermacher Q6_K GGUF, 28.51 GB on disk, 26.56 GiB resident at 65 K context) deployed 2026-05-02, replacing HauhauCS Aggressive as the active Mac Studio LLM process.
- LM Studio handles Qwen3 chat-template tool-calls + `<think>` natively — **no parser flags required**.
- Current benchmarks: API tool harness 5/5 single-call + 3/3 multi-turn; refusal rate 10/10 complied with 0 refused (`max_tokens=1024`); throughput 83.6 tok/s @ 512, 70.6 tok/s @ 32 K, 113 K tok/s prefill; **OpenCode browse 5.05 s** (uncensored GGUF browse leader — 60 ms faster than Gemma 5.11 s and 90 ms faster than HauhauCS 5.14 s) **/ search 13.56 s** (+1.55 s vs HauhauCS 12.01 s; 2nd behind HauhauCS among uncensored GGUFs). Raw data: [`docs/models/benchmarks/qwen36-35b-a3b-prithiv-aggressive/`](models/benchmarks/qwen36-35b-a3b-prithiv-aggressive/).
- Key deployment gotcha: LM Studio guardrail `mode: "high"` blocked initial load (counts free pages ~24 GB only, ignores 60+ GB inactive). Temporarily set to `"off"` to load; restored to `"high"` after. See benchmark doc for recipe.
- vmlx (port 8000) and dflash-mlx (port 8098) remain stopped per Event-4 hygiene.

## Stopped / Documented Fallbacks

These were live before the 2026-05-02 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior llmster main (HauhauCS Aggressive, search-faster) | `llmster` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
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
