# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-01

## Production

| Field | Value |
|:--|:--|
| Server | `vmlx` |
| Model | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` |
| Port | `8000` |
| Auth | None |
| Client template set | [`configs/clients/vmlx/`](../configs/clients/vmlx/) |
| Runbook | [`docs/servers/vmlx/summary.md`](servers/vmlx/summary.md) |

Launch shape:

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &
```

Notes:
- Osaurus Qwen3.6-35B-A3B JANGTQ4 is served through the MLX Studio bundled Python because JANGTQ / `mxtq` requires `jang_tools.load_jangtq_vlm` and TurboQuant Metal kernels.
- Tool use requires `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` plus `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3`.
- Current benchmark: API tool harness passes 5/5; OpenCode median is 72.75 s browse and 135.06 s search. Raw data: [`docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/`](models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/).

## Sidecars

### llmster (LM Studio headless)

| Field | Value |
|:--|:--|
| Server | `llmster` / LM Studio headless |
| Model | `qwen3.6-27b` from `mlx-community/Qwen3.6-27B-6bit` |
| Port | `1234` |
| Auth | None |
| Client template set | [`configs/clients/llmster/`](../configs/clients/llmster/) |
| Status | Provisional, OpenCode-only template |
| Runbook | [`docs/servers/llmster/summary.md`](servers/llmster/summary.md) |

Use llmster for standard MLX/GGUF models when the fast prefill path matters. It does not support JANG, JANGTQ, or `bailing_hybrid`.

### dflash-mlx (DFlash speculative decoding)

| Field | Value |
|:--|:--|
| Server | `dflash-mlx` / `dflash-serve` (wraps `mlx_lm.server`) |
| Target | `mlx-community/Qwen3.6-35B-A3B-4bit` (~22 GB) |
| Drafter | `z-lab/Qwen3.6-35B-A3B-DFlash` (~1 GB, 0.5B BF16) |
| Port | `8098` |
| Auth | None |
| Client template set | [`configs/clients/dflash-mlx/`](../configs/clients/dflash-mlx/) |
| Status | Provisional, OpenCode-only template; requires three local patches |
| Runbook | [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md) |

Launch shape:

```bash
~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512
```

Use dflash-mlx for workload-gated decode-bound tasks. It wins on high-agreement deterministic prompts such as math/reasoning (`1.61x` at 8192 tokens, `86.66%` acceptance) and constrained JSON (`1.46x` at 4096 tokens, `84.55%` acceptance), but regresses on open-ended prose (`0.62-0.98x`, `64-79%` acceptance). It still loses to llmster when prefill dominates (long-context multi-turn agent loops). See [`model-benchmark-standalone.md` § DFlash](models/benchmarks/model-benchmark-standalone.md#dflash-speculative-decoding--qwen36-35b-a3b-4bit--dflash-drafter).

## Fallbacks

| Use case | Server | Model |
|:--|:--|:--|
| Previous Ling primary | `vllm-mlx` | `mlx-community/Ling-2.6-flash-mlx-6bit` |
| Dense Qwen3.6 fallback | `vllm-mlx` | `JANGQ-AI/Qwen3.6-27B-JANG_4M` |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` |
| JANGTQ CRACK models | `vmlx` | `dealignai/MiniMax-M2.7-JANGTQ-CRACK` |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
