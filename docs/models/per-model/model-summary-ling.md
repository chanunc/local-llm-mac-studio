# Model Summary: Ling-2.6-flash mlx-6bit

InclusionAI's `bailing_hybrid` MoE — 104 B total / 7.4 B active — running on this Mac Studio via vllm-mlx. Sparse-expert hybrid that mixes 4 MLA layers (absorbed-form Multi-head Latent Attention) with 28 Lightning-style linear-attention recurrence layers. 256 routed experts (8/tok, group-limited top-8) + 1 shared, sigmoid noaux_tc routing. 6-bit MLX uniform quant, ~80 GB on disk. Text-only, no `<think>` reasoning emitted. Deployed 2026-04-29.

> **Architecture reference:** for the `bailing_hybrid` architecture, the threading rationale behind the patches, and the server-compatibility matrix, see [`../techniques/model-architecture-bailing-hybrid.md`](../techniques/model-architecture-bailing-hybrid.md). This file covers Ling-2.6-flash's model-specific spec and deployment.

| Spec | Value |
|:-----|:------|
| Base Model | [inclusionAI/Ling-2.6-flash](https://huggingface.co/inclusionAI/Ling-2.6-flash) |
| Quant | [mlx-community/Ling-2.6-flash-mlx-6bit](https://huggingface.co/mlx-community/Ling-2.6-flash-mlx-6bit) |
| Format | MLX safetensors (uniform 6-bit) |
| Vendor | Ant Group / InclusionAI base; mlx-community quant |
| Architecture | `BailingMoeV2_5ForCausalLM`, `model_type=bailing_hybrid` |
| Parameters | 104 B total, 7.4 B active per token |
| Layers | 32 — 4 MLA (idx 4/15/23/31) + 28 Lightning linear-attention recurrence |
| Experts | 256 routed (top-8, group-limited across 8 groups) + 1 shared |
| Routing | Sigmoid `noaux_tc` with router-bias term |
| MLA | q_lora_rank=1536, kv_lora_rank=512, qk_rope/nope/v head dims 64/128/128 |
| Quantization | 6-bit uniform MLX (group_size=64) |
| On-disk size | ~80 GB |
| Context Size | 131,072 native; **64K practical ceiling on M3 Ultra (96 GB)** — 128K OOMs |
| Reasoning | None — model does not emit `<think>` blocks |
| Vision | No — text-only |
| License | MIT (base) |
| Key Features | Sparse 7.4 B-active gives strong tool-call latency; recurrent linear-attention path keeps gen tok/s flat across context lengths |

**vllm-mlx model ID:** `mlx-community/Ling-2.6-flash-mlx-6bit` (HF cache, `~/.cache/huggingface/hub/models--mlx-community--Ling-2.6-flash-mlx-6bit/`)

## Deploying to vllm-mlx

Three local patches are required, mlx-openai-server is incompatible, and tool-call/reasoning parser flags differ from the rest of the Qwen3.5/3.6 family. Full recipe + flag rationale + threading explanation: [`../techniques/model-architecture-bailing-hybrid.md`](../techniques/model-architecture-bailing-hybrid.md). Launch invocation specifically for this model:

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  nohup ~/vllm-mlx-env/bin/vllm-mlx serve mlx-community/Ling-2.6-flash-mlx-6bit \
    --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
    --port 8000 --host 0.0.0.0 \
    --enable-auto-tool-choice --tool-call-parser hermes \
    > /tmp/vllm-mlx.log 2>&1 &"
```

## Benchmarks

- API server inference (gen / prefill / TTFT across context lengths, 128K OOM note): [`model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid)
- API-level + OpenCode end-to-end tool calling (5/5 pass, 3-turn loop, browse/search wall times): [`model-benchmark-agent-tool-call.md`](../benchmarks/model-benchmark-agent-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit)

## Caveats

- **Architecture-level caveats** (3-patch deploy, mlx-openai-server incompatibility, server-compatibility matrix, 128K OOM, no `<think>`, no vision): see [`../techniques/model-architecture-bailing-hybrid.md`](../techniques/model-architecture-bailing-hybrid.md).
- **`usage.prompt_tokens=0`** in both streaming SSE chunks and non-streaming responses — vllm-mlx field-fill bug (same as JANG_4M / JANG_2S). Use the model's own tokenizer to compute actual prefill rates.
- **Client-config sync.** As with all single-model vllm-mlx swaps, local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` defaults must be aligned with whatever is live on port 8000. Calls to a non-served model ID return HTTP 404 from `/v1/chat/completions`. The bench used a project-local `/tmp/agent-bench/opencode.json` to avoid touching the user's global config.

## When to use

- **Best fit:** code-agent workflows where minimum API-level tool-call latency matters (read/write/edit loops). The 4.74 s 3-turn loop is the doc's best.
- **Good fit:** long-context generation up to 64K where you want stable tok/s — the recurrent linear-attention path keeps gen flat across context lengths better than the dense Qwen3.6 stack.
- **Poor fit:** vision tasks (no support), reasoning workflows that consume `reasoning_content` (no `<think>` emitted), workloads above 64K context (OOM).
