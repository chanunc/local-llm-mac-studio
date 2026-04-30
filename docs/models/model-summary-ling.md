# Model Summary: Ling-2.6-flash mlx-6bit

InclusionAI's `bailing_hybrid` MoE — 104 B total / 7.4 B active — running on this Mac Studio via vllm-mlx. Sparse-expert hybrid that mixes 4 MLA layers (absorbed-form Multi-head Latent Attention) with 28 Lightning-style linear-attention recurrence layers. 256 routed experts (8/tok, group-limited top-8) + 1 shared, sigmoid noaux_tc routing. 6-bit MLX uniform quant, ~80 GB on disk. Text-only, no `<think>` reasoning emitted. Deployed 2026-04-29.

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

This model needs **three local patches** before it will load and serve. mlx-openai-server is **incompatible** (different threading model, see Caveats); vllm-mlx is the only viable host today.

### Step 1 — Vendor `bailing_hybrid` into mlx-lm

mlx-lm 0.31.3 does not yet ship a `bailing_hybrid` model module. Source it from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227) (ivanfioravanti):

```bash
ssh macstudio "~/vllm-mlx-env/bin/pip install --upgrade mlx-lm==0.31.3"
curl -sL https://github.com/ml-explore/mlx-lm/pull/1227.diff -o /tmp/pr1227.diff
# extract the bailing_hybrid.py addition (~748 lines, single file under mlx_lm/models/)
# and copy into the venv
scp /tmp/bailing_hybrid.py macstudio:/tmp/
ssh macstudio "cp /tmp/bailing_hybrid.py ~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/models/bailing_hybrid.py"
```

Without this: `ValueError: Model type bailing_hybrid not supported`.

### Step 2 — Patch the thread-local stream bug in mlx-lm

Stock mlx-lm creates `generation_stream = mx.new_thread_local_stream(...)` at module import on the main thread. vllm-mlx (and mlx-openai-server) run inference in worker threads where that stream object is unreachable. The fix turns `generation_stream` into a per-thread lazy accessor.

```bash
ssh macstudio "~/vllm-mlx-env/bin/python3 ~/setup-llm-macstu/scripts/patches/patch_mlx_lm_threadlocal_stream.py \
  ~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/generate.py"
```

Without this: `RuntimeError: There is no Stream(gpu, 1) in current thread` from the worker thread's first `mx.eval`. Idempotent (sentinel comment).

### Step 3 — Patch vllm-mlx to run generation inline on the asyncio loop

Even after step 2, the model's custom `mx.fast.metal_kernel` objects (the GLA SSM kernel and the Lightning linear-attention recurrence kernel) are bound to the thread that built them. vllm-mlx invokes generation via `await asyncio.to_thread(self._model.chat, ...)`, so the kernel call lands on a worker thread that didn't build it. The fix replaces every `await asyncio.to_thread(...)` in `vllm_mlx/engine/simple.py` with a direct synchronous call. Generation now blocks the asyncio loop, which is fine for single-stream inference servers.

```bash
ssh macstudio "~/vllm-mlx-env/bin/python3 ~/setup-llm-macstu/scripts/patches/patch_vllm_mlx_inline_gen.py \
  ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/engine/simple.py"
```

Without this: `RuntimeError: There is no Stream(gpu, 0) in current thread` even after step 2 — because the kernel itself was registered on the main thread, the worker thread can't reach it regardless of which stream is current. Idempotent (sentinel comment).

### Step 4 — Launch the server

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  nohup ~/vllm-mlx-env/bin/vllm-mlx serve mlx-community/Ling-2.6-flash-mlx-6bit \
    --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
    --port 8000 --host 0.0.0.0 \
    --enable-auto-tool-choice --tool-call-parser hermes \
    > /tmp/vllm-mlx.log 2>&1 &"
```

Re-apply steps 2 and 3 after every `pip install -U vllm-mlx` or `pip install -U mlx-lm`. Step 1 needs the vendored file re-copied if the venv's `mlx_lm/models/` is rebuilt by an upgrade.

## Server Flags

| Flag | Value | Why |
|:-----|:------|:----|
| `--enable-auto-tool-choice` | (boolean) | Required to surface OpenAI-style `tool_calls` in responses when the model emits a tool-call envelope |
| `--tool-call-parser` | `hermes` | Ling emits `<tool_call>{json}</tool_call>` blocks (Hermes/qwen2 format). vllm-mlx 0.2.6 does not have `qwen3` as a *tool-call* parser choice (only `auto, mistral, qwen, qwen3_coder, llama, hermes, deepseek, kimi, granite, nemotron, xlam, functionary, glm47`); `qwen3_coder` expects `<function=name><parameter=k>v</parameter></function>` XML body, not JSON |
| `--reasoning-parser` | (omitted) | Model never emits `<think>…</think>`, so no reasoning parser is needed. Adding `--reasoning-parser qwen3` is harmless but pointless |
| `--port` | `8000` | Standard server port across this stack |
| `--host` | `0.0.0.0` | LAN-accessible from MacBook / Linux / Pi clients |
| **No JANG wrapper** | — | This is plain MLX safetensors, not JANG mixed-precision. Use `vllm-mlx serve` directly, not `~/run_vllm_jang.py serve` |

For comparison: every Qwen3.5/3.6 model in this repo uses `--tool-call-parser qwen3_coder --reasoning-parser qwen3`. Ling differs on both axes — tool-call parser (`hermes` vs `qwen3_coder` because of body format) and reasoning parser (none vs `qwen3` because no `<think>`).

## Benchmarks

- API server inference (gen / prefill / TTFT across context lengths, 128K OOM note): [`model-benchmark-api-server.md`](model-benchmark-api-server.md#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid)
- API-level + OpenCode end-to-end tool calling (5/5 pass, 3-turn loop, browse/search wall times): [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md#results-mlx-communityling-26-flash-mlx-6bit)

## Caveats

- **Three patches required to load.** Ranked by depth: PR #1227 vendor (architecture), thread-local stream patch (mlx-lm threading bug), inline-gen patch (vllm-mlx × thread-bound `metal_kernel` interaction). All idempotent. All must be re-applied after upgrading mlx-lm or vllm-mlx.
- **mlx-openai-server is NOT compatible.** Same root cause as the inline-gen patch: mlx-openai-server's prompt-cache prefill (`mx.eval([c.state for c in model_cache])` in `app/models/mlx_lm.py`) runs on a dedicated inference-worker thread, which is more deeply thread-coupled than vllm-mlx's `asyncio.to_thread`. The inline-gen patch doesn't apply directly there. Crashes with `RuntimeError: There is no Stream(gpu, 1) in current thread`.
- **128K context OOMs.** KV cache for the 4 MLA layers (KVCache) + ArraysCache(size=1) for the 28 linear-attention layers + 80 GB of weights pushes past the 96 GB unified-memory ceiling on M3 Ultra. Practical ceiling sits around 64K. OpenCode never approaches that limit (max ~63K observed in search).
- **`usage.prompt_tokens=0`** in both streaming SSE chunks and non-streaming responses — vllm-mlx field-fill bug (same as JANG_4M / JANG_2S). Use the model's own tokenizer to compute actual prefill rates.
- **No vision input.** `bailing_hybrid` is text-only despite the InclusionAI Ling family's broader multimodal stack.
- **No `<think>` reasoning emitted.** Lower per-turn overhead vs Qwen3 thinking models; trade-off is no chain-of-thought visibility for downstream consumers that key off `reasoning_content`.
- **Client-config sync.** As with all single-model vllm-mlx swaps, local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` defaults must be aligned with whatever is live on port 8000. Calls to a non-served model ID return HTTP 404 from `/v1/chat/completions`. The bench used a project-local `/tmp/agent-bench/opencode.json` to avoid touching the user's global config.
- **Production default remains Qwen3.6-27B JANG 4M.** Switching to Ling for daily code-agent use is a deliberate swap with ~3 min downtime to apply patches and restart; not the default.

## When to use

- **Best fit:** code-agent workflows where minimum API-level tool-call latency matters (read/write/edit loops). The 4.74 s 3-turn loop is the doc's best.
- **Good fit:** long-context generation up to 64K where you want stable tok/s — the recurrent linear-attention path keeps gen flat across context lengths better than the dense Qwen3.6 stack.
- **Poor fit:** vision tasks (no support), reasoning workflows that consume `reasoning_content` (no `<think>` emitted), workloads above 64K context (OOM).
