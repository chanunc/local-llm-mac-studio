# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-04-30

## Production

| Field | Value |
|:--|:--|
| Server | `vllm-mlx` |
| Model | `mlx-community/Ling-2.6-flash-mlx-6bit` |
| Port | `8000` |
| Auth | None |
| Client template set | [`configs/clients/vllm-mlx/`](../configs/clients/vllm-mlx/) |
| Runbook | [`docs/servers/vllm-mlx/summary.md`](servers/vllm-mlx/summary.md) |

Launch shape:

```bash
~/vllm-mlx-env/bin/vllm-mlx serve mlx-community/Ling-2.6-flash-mlx-6bit \
  --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes
```

Notes:
- Ling needs the `bailing_hybrid` vendor file plus the thread-local-stream and inline-generation patches documented in [`models/per-model/model-summary-ling.md`](models/per-model/model-summary-ling.md).
- Practical context ceiling on the 96 GB Mac Studio is about 64K; 128K OOMs.

## Sidecar

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

## Fallbacks

| Use case | Server | Model |
|:--|:--|:--|
| Dense Qwen3.6 fallback | `vllm-mlx` | `JANGQ-AI/Qwen3.6-27B-JANG_4M` |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` |
| JANGTQ CRACK models | `vmlx` | `dealignai/MiniMax-M2.7-JANGTQ-CRACK` |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
