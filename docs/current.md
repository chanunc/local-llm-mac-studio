# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-02

## Production

| Field | Value |
|:--|:--|
| Server | `llmster` / LM Studio headless |
| Model | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/llmster/`](../configs/clients/llmster/) |
| Runbook | [`docs/servers/llmster/summary.md`](servers/llmster/summary.md) |

Launch shape (after Event-4 hygiene):

```bash
# Hub download (lms get mis-resolves K_P labels)
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive', \
  filename='Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q6_K_P.gguf', \
  local_dir='/Users/chanunc/.cache/hauhau-gguf')\""

ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive -y \
  ~/.cache/hauhau-gguf/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q6_K_P.gguf"

ssh macstudio "~/.lmstudio/bin/lms load 'qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive' \
  --gpu max --context-length 131072 \
  --identifier 'qwen3.6-35b-a3b-uncensored-aggressive-q6kp' -y"

ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

Notes:
- HauhauCS Qwen3.6-35B-A3B Uncensored Aggressive (Q6_K_P GGUF, ~31 GB on disk, 28.5 GiB resident at 131 K context) deployed 2026-05-02 as the active Mac Studio LLM process, replacing both the prior vmlx-Osaurus production main and the Balanced llmster sidecar.
- LM Studio handles Qwen3 chat-template tool-calls + `<think>` natively — **no parser flags required**.
- Current benchmarks: API tool harness 5/5 single-call + 3/3 multi-turn; refusal rate 10/10 complied with 0 refused (`max_tokens=1024`); throughput 82 tok/s @ 512, 70 tok/s @ 32 K, 61 tok/s @ 65 K with 113 K – 134 K tok/s prefill; **OpenCode browse 5.14 s** (essentially tied with Gemma 4 31B-it on llmster, the dense leader at 5.11 s) **/ search 12.01 s** (2nd behind Gemma's 6.37 s, but 14× the prior vmlx-Osaurus production main and 6× the prior fastest non-Gemma llmster entry). Aggressive is the fastest **uncensored / GGUF** option in the stack; Gemma still wins the dense non-thinking text-only path. Raw data: [`docs/models/benchmarks/qwen36-35b-a3b-hauhaucs-aggressive/`](models/benchmarks/qwen36-35b-a3b-hauhaucs-aggressive/).
- Active sidecar promotion: the experiment-lab framing in [`CLAUDE.md`](../CLAUDE.md#project) means whatever model is currently loaded is the production main. vmlx (port 8000) and dflash-mlx (port 8098) were stopped per Event-4 hygiene before this run and remain stopped — restart them only if you need parallel servers.

## Stopped / Documented Fallbacks

These were live before the 2026-05-02 deploy-and-benchmark run and remain **off** until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
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
