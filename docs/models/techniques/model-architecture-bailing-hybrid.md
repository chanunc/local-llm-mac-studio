# bailing_hybrid — Hybrid MoE Architecture

`bailing_hybrid` is InclusionAI's hybrid sparse-MoE architecture used by the Ling-2.6 family. It is **neither a quantisation format nor a generation-time technique** — it is the model's *architecture* (`BailingMoeV2_5ForCausalLM`, `model_type=bailing_hybrid`). It lives in the techniques folder because deploying it on Apple Silicon requires a cross-cutting set of *runtime* patches that affect any MLX server hosting it.

This file covers the architecture, why it needs patches, the canonical 3-patch recipe, and which servers are compatible. For Ling-specific deployment numbers and the model spec table, see [`../per-model/model-summary-ling.md`](../per-model/model-summary-ling.md).

## Architecture

| Property | Value |
|:--|:--|
| Layer count | 32 — **4 MLA layers** (idx 4/15/23/31) + **28 Lightning linear-attention** recurrence layers |
| MLA shape | `q_lora_rank=1536`, `kv_lora_rank=512`, `qk_rope/nope/v` head dims 64/128/128 |
| Experts | 256 routed (top-8, group-limited across 8 groups) + 1 shared |
| Routing | Sigmoid `noaux_tc` with router-bias term |
| Reasoning emission | None — model never emits `<think>` |
| Vision | No — text-only |
| Family | Ling-2.6-flash (104 B / 7.4 B active), Ling-mini, others on the inclusionAI org |

The hybrid layout matters operationally because:

- **MLA layers use a normal KVCache** — KV memory grows with context length.
- **Linear-attention layers use `ArraysCache(size=1)`** — fixed-size recurrent state, KV memory does **not** grow with context.

The result is gen tok/s that stays remarkably **flat across context lengths** compared to full-attention stacks, but practical context ceiling on M3 Ultra (96 GB) sits around **64K** because the MLA layers' KV plus the 80 GB of weights still squeezes the unified-memory budget at 128K (OOM observed).

## Why deploying it on Apple Silicon needs patches

`bailing_hybrid` ships **two custom `mx.fast.metal_kernel` objects** — a GLA SSM kernel and a Lightning linear-attention recurrence kernel. Combined with mlx-lm's threading model, this triggers a **thread-bound stream + thread-bound kernel** problem on every MLX server that runs inference off the main thread:

- `mlx_lm.generate.generation_stream = mx.new_thread_local_stream(...)` is created at **module import time on the main thread**. Any worker thread that picks up generation cannot reach it.
- Each `mx.fast.metal_kernel` registers itself on the thread that *built* the kernel object. A worker thread that didn't build it cannot invoke it regardless of which stream is current.

Both problems are silent until first use, then surface as `RuntimeError: There is no Stream(gpu, N) in current thread`.

## The 3-patch recipe (canonical)

This recipe currently runs Ling-2.6-flash production on `vllm-mlx`. mlx-openai-server is **incompatible** (see below).

### Patch 1 — Vendor `bailing_hybrid` into mlx-lm

mlx-lm 0.31.3 does not ship a `bailing_hybrid` model module. Source it from open PR [`ml-explore/mlx-lm#1227`](https://github.com/ml-explore/mlx-lm/pull/1227) (~748 lines, single file under `mlx_lm/models/`):

```bash
ssh macstudio "~/vllm-mlx-env/bin/pip install --upgrade mlx-lm==0.31.3"
# extract bailing_hybrid.py from PR #1227 and copy to:
#   ~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/models/bailing_hybrid.py
```

Without this: `ValueError: Model type bailing_hybrid not supported`.

### Patch 2 — Thread-local stream

Convert `generation_stream` from a module-level singleton into a per-thread lazy accessor.

```bash
ssh macstudio "~/vllm-mlx-env/bin/python3 \
  ~/setup-llm-macstu/scripts/patches/patch_mlx_lm_threadlocal_stream.py \
  ~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/generate.py"
```

Without this: `RuntimeError: There is no Stream(gpu, 1) in current thread` from the worker thread's first `mx.eval`. Idempotent (sentinel comment).

### Patch 3 — Inline generation on the asyncio loop

Replace every `await asyncio.to_thread(...)` in `vllm_mlx/engine/simple.py` with direct synchronous calls. Generation now blocks the asyncio loop, which is fine for single-stream inference servers.

```bash
ssh macstudio "~/vllm-mlx-env/bin/python3 \
  ~/setup-llm-macstu/scripts/patches/patch_vllm_mlx_inline_gen.py \
  ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/engine/simple.py"
```

Without this: `RuntimeError: There is no Stream(gpu, 0) in current thread` even after Patch 2 — because the kernel itself was registered on the main thread, the worker thread can't reach it regardless of which stream is current. Idempotent (sentinel comment).

**Re-apply order after upgrades:** Patch 1 needs the vendored file re-copied if `pip install -U mlx-lm` rebuilds the venv's `mlx_lm/models/`. Patches 2 and 3 must be re-applied after `pip install -U vllm-mlx` or `pip install -U mlx-lm`.

## Server compatibility

| Server | bailing_hybrid? | Reason |
|:--|:-:|:--|
| `vllm-mlx` | ✅ | Patches 1 + 2 + 3 work. Production primary for Ling-2.6-flash. |
| `mlx-openai-server` | ❌ | Prompt-cache prefill (`mx.eval([c.state for c in model_cache])` in `app/models/mlx_lm.py`) runs on a dedicated inference-worker thread that is more deeply thread-coupled than vllm-mlx's `asyncio.to_thread`. Patch 3 doesn't apply directly. Crashes with the same `Stream(gpu, 1)` error. |
| `oMLX` | ❌ | Same kind of worker-thread isolation as mlx-openai-server. Not validated. |
| `dflash-mlx` | ❌ | Wraps `mlx_lm.server`, MLX safetensors only — no `bailing_hybrid` model module path. No DFlash drafter exists for the architecture either. |
| `llmster` (LM Studio) | ❓ | Closed-source MLX runtime. Not tested. |
| `vmlx` | ❌ | JANGTQ-only effectively; no `bailing_hybrid` adapter. |

## Server flags for the Ling family

| Flag | Value | Why |
|:--|:--|:--|
| `--enable-auto-tool-choice` | (boolean) | Required to surface OpenAI-style `tool_calls` |
| `--tool-call-parser` | `hermes` | Ling emits `<tool_call>{json}</tool_call>` (Hermes/qwen2 format). `qwen3_coder` expects XML body, not JSON. `qwen3` is not a vllm-mlx 0.2.6 tool-call parser choice. |
| `--reasoning-parser` | (omitted) | Model never emits `<think>`. Adding `--reasoning-parser qwen3` is harmless but pointless. |
| **No JANG wrapper** | — | Plain MLX safetensors, not JANG. Use `vllm-mlx serve` directly. |

Every other Qwen3.5/3.6 model in this repo uses `--tool-call-parser qwen3_coder --reasoning-parser qwen3`. Ling differs on **both** axes.

## Known caveats

- **128K context OOMs on M3 Ultra (96 GB).** Practical ceiling ≈ 64K. OpenCode never approaches that limit (max ~63K observed in search workloads).
- **`usage.prompt_tokens=0`** in both streaming SSE chunks and non-streaming responses — vllm-mlx field-fill bug (also present for JANG_4M / JANG_2S). Use the model's tokeniser to compute actual prefill rates.
- **No vision input** despite the InclusionAI Ling family's broader multimodal stack.
- **No `<think>` reasoning emitted** — lower per-turn overhead vs Qwen3 thinking models, trade-off is no chain-of-thought visibility for downstream consumers that key off `reasoning_content`.

## Currently deployed bailing_hybrid models

| Model | On-disk | Server | Status |
|:--|--:|:--|:--|
| [`mlx-community/Ling-2.6-flash-mlx-6bit`](https://huggingface.co/mlx-community/Ling-2.6-flash-mlx-6bit) | ~80 GB | vllm-mlx (port 8000) | **Production primary** since 2026-04-29 |

## See also

- [`../per-model/model-summary-ling.md`](../per-model/model-summary-ling.md) — Ling-2.6-flash spec table, benchmark links, when-to-use
- [`../../servers/vllm-mlx/`](../../servers/vllm-mlx/) — vllm-mlx server runbook
- [`../../current.md`](../../current.md) — live production state
- [`../benchmarks/model-benchmark-api-server.md` § Ling](../benchmarks/model-benchmark-api-server.md#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid) — gen / prefill / TTFT across context lengths
- [`../benchmarks/model-benchmark-agent-tool-call.md`](../benchmarks/model-benchmark-agent-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit) — agent-loop tool calling
- [`../../../scripts/patches/patch_mlx_lm_threadlocal_stream.py`](../../../scripts/patches/patch_mlx_lm_threadlocal_stream.py)
- [`../../../scripts/patches/patch_vllm_mlx_inline_gen.py`](../../../scripts/patches/patch_vllm_mlx_inline_gen.py)
- [`ml-explore/mlx-lm#1227`](https://github.com/ml-explore/mlx-lm/pull/1227) — upstream `bailing_hybrid` model module PR
- [`inclusionAI/Ling-2.6-flash`](https://huggingface.co/inclusionAI/Ling-2.6-flash) — base model card
