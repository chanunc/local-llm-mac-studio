# Tuning by knob

Knob-by-knob reference for the Mac Studio LLM stack. Bucketed by *measured impact on our hardware*, not by what looks tunable on paper. For the inverse view (what to tune for a given workload), see [`tuning-by-workload.md`](tuning-by-workload.md).

## High-impact knobs

These move agent-loop wall time by 1.5–4× when set wrong. Always check these first.

### Thinking flag (`enable_thinking` in chat template)

- **What**: Per-model Jinja chat template variable that decides whether the model wraps its reply in `<think>…</think>` blocks (Qwen3-style) or routes reasoning to a separate `reasoning_content` field (Gemma 4-style).
- **Where**: Server-side chat template (e.g. `~/.lmstudio/models/<repo>/chat_template.jinja`), or per-request override on some servers.
- **Effect**: Output token count goes up 3–4× when ON. For agent-loop workloads with N turns, total wall time scales roughly linearly with output tokens, so this knob alone is the biggest single lever we have on agent-loop latency.
- **Local measurement**: Gemma 4 31B-it 6-bit on `mlx_lm.server` with thinking ON: OpenCode browse 12.33 s / search 35.55 s. Same weights on lm-studio with thinking OFF: 5.11 s / 6.37 s. The 2.4–5.6× wall-time gap is almost entirely thinking-mode output bloat. See [`../models/per-model/model-summary-gemma.md`](../models/per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit).
- **Watch out**: Some servers (`mlx_lm.server`) default thinking ON; some (lm-studio on Gemma 4) default OFF. Same weights, different default — measure both before crediting a server with a "speed advantage".

### Tool-call parser (`--tool-call-parser`)

- **What**: Tells the server how to extract tool calls from raw model output and convert them into OpenAI `tool_calls[]` shape.
- **Where**: vllm-mlx, vmlx, dflash-mlx, mlx-vlm. lm-studio does this automatically and exposes no flag.
- **Effect**: Wrong or missing parser = silent failure. The model emits a perfectly correct tool call as raw XML / JSON inside `content`, the agent client renders it as prose, and the model "hallucinates" tool names from the user's perspective.
- **Pick the right parser**:
    - `qwen3_coder` (aliased to `hermes`) for Qwen3.5 / Qwen3.6 family — they emit XML `<function=name><parameter=key>value</parameter></function>`
    - `qwen3` for Qwen3.5-VL CRACK and JANGTQ4 — emits `<tool_call>{json}</tool_call>`
    - `hermes` for Ling-2.6 (`bailing_hybrid`) — same Hermes shape
    - `gemma4` for Gemma 4 on vllm-mlx 0.2.9+
- **Watch out**: `--tool-call-parser qwen` ≠ `qwen3_coder`. The plain `qwen` parser expects JSON inside `<tool_call>` tags and does not work on Qwen3.5/3.6 XML output.

### Reasoning parser (`--reasoning-parser`)

- **What**: Routes `<think>…</think>` blocks into the `reasoning_content` SSE field instead of leaking into `content`.
- **Where**: Same servers as tool-call parser.
- **Effect**: Without it, the agent client renders the chain-of-thought as the assistant's visible reply ("model talking nonsense"). On agent loops, the thoughts also get fed back as user-visible context on subsequent turns.
- **Pick**: `qwen3` for any Qwen3 thinking model (Qwen3.5-VL CRACK, JANGTQ4, etc.).
- **Watch out**: Without `--reasoning-parser`, even with the right `--tool-call-parser`, a thinking model will pollute the conversation. Both flags are needed together for thinking + tool-using models.

### Speculative drafter (`--draft-model`, MTP, DFlash)

- **What**: Pairs a small "drafter" model with the target model; the drafter speculates K tokens ahead, the target verifies in one forward pass. K-token win on accept, fall back to 1-token on reject.
- **Where**: `mlx_lm.server --draft-model …` (DFlash, MTP), `dflash-mlx`, mlx-vlm 0.5.0+ for `gemma4_assistant`.
- **Effect**: 1.3–2× decode-bound speedup when acceptance is high; can *regress* below 1× on prose where acceptance is poor.
- **Local measurement**:
    - DFlash on `Qwen3.6-35B-A3B-4bit`: 86.7% acceptance, 74-89 tok/s sustained decode at 32K (1.46–1.61× on math/JSON, 0.62–0.98× on prose).
    - Gemma 4 MTP on `mlx_vlm 0.5.0`: 4.29 acc/round at upstream-expected efficiency, but blocked by streaming SSE tool-call emission bug for agent clients. See [`../models/per-model/model-summary-gemma.md`](../models/per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment) and [`../models/techniques/model-technique-dflash.md`](../models/techniques/model-technique-dflash.md).
- **Watch out**: Drafter only matters when decode dominates wall time. Agent loops with short replies between tool calls do not amortise drafter overhead well.

### Quantisation (4-bit / 6-bit / 8-bit / bf16)

- **What**: Bits per weight on disk. Lower bits = smaller activation memory, faster decode, slight quality loss.
- **Where**: Model side; chosen at download time.
- **Effect**: Roughly linear decode tok/s gain with fewer bits. Memory bandwidth is the bottleneck on Apple Silicon, so weight size dominates decode rate.
- **Local measurement**: Gemma 4 31B-it bf16 + MTP drafter capped at 12.3 tok/s decode and OOMs at 32K+ context; the 6-bit variant runs 20.4 tok/s decode and fits 65K. Sweet spot for 30B-class on 96 GB is 6-bit MLX.
- **Watch out**: 8-bit GGUF on `llama.cpp`-derived stacks can be faster than 6-bit MLX on the same model — quantisation interacts with runtime. Always benchmark both formats on the same weights when in doubt.

## Medium-impact knobs

These set ceilings or unlock multi-turn caching, but rarely move single-turn wall time more than ~10–20%.

### Context length cap (`--context-length`, `--max-tokens`, `--max-model-len`)

- **What**: KV-cache + position-encoding ceiling.
- **Effect**: Bigger = more agent-loop headroom for tool results to accumulate; costs unified RAM per token of cache. Setting it bigger than needed wastes memory.
- **Local measurement**: lm-studio default is 4096 — silently truncates agent prompts. Always pass `--context-length 65536` or larger explicitly. Gemma 4 31B 6-bit fits 65K on 96 GB but bf16 OOMs above 32K.
- **Watch out**: `mlx_lm.server`'s `--max-tokens` is the *output* cap, not the context cap. The context cap is implicit (model architecture max).

### Prompt cache size (`--prompt-cache-size`)

- **What**: Number of distinct KV caches to keep across requests for prefix reuse.
- **Where**: `mlx_lm.server`, `mlx-openai-server`.
- **Effect**: Big win on agent loops where the same system prompt + tool catalog is re-sent every turn. First turn pays full prefill cost, subsequent turns hit the cache.
- **Local measurement**: Gemma 4 31B 6-bit holds ~22 GB of prompt cache for 10 sequences on `mlx_lm.server` default. Reducing this frees RAM for KV cache headroom on long context.
- **Watch out**: Cache hit requires byte-exact prefix match. Anything that varies the system prompt across turns (timestamps, random IDs) defeats the cache.

### GPU memory split (`--gpu max`)

- **What**: Maximum unified-memory wired allocation for model weights on Apple Silicon.
- **Where**: lm-studio (`lms load --gpu max`).
- **Effect**: Too low = weights swap out, decode tanks. Too high = no headroom for activation buffers, prefill OOMs.
- **Local measurement**: `--gpu max` on M3 Ultra 96 GB lets a 30B 6-bit fit comfortably with 32K context.

### Continuous batching (`--continuous-batching`)

- **What**: Allows multiple in-flight requests to share GPU dispatches.
- **Where**: vmlx, vllm-mlx.
- **Effect**: Helps when there is request concurrency; agent loops are sequential so it is mostly free overhead.
- **Watch out**: Mostly a no-op for our single-client lab benchmarks. Worth flipping on if multi-tenant workloads land later.

## Low-impact / not worth tuning

These look tunable but do not move the needle on our hardware, or have already been pre-tuned upstream.

### `--prefill-step-size` (mlx_lm.server)

- **What**: Tokens per prefill GPU dispatch.
- **Why historically a knob**: Public LM Studio patches show 512 → 4096–8192 yields up to 2× prefill speedup; see [`../servers/lm-studio/prefill-speed-technique.md`](../servers/lm-studio/prefill-speed-technique.md).
- **Why we do not tune it**: `mlx_lm.server` 0.31.3 already defaults to **2048** (verified 2026-05-06). Raising to 8192 OOMs on Gemma 4 31B-it 6-bit at 65K context (`[METAL] kIOGPUCommandBufferCallbackErrorOutOfMemory`). The remaining lift available between 2048 → 8192 either does not measurably help or breaks long context.

### Sampler defaults (`temperature`, `top_p`, `top_k`)

- **Why not tuned server-side**: These are per-request and set by the agent client (OpenCode, Claude Code, Pi). Server-side defaults are a no-op once the client overrides them. Tune at the client config layer if needed.

### `MLX_VLM_SPEC_BATCH_WAIT_MS`

- **What**: Coalesces concurrent MTP draft requests into a batch.
- **Why not useful**: Agent loops are sequential. There is nothing to batch. Verified no effect on Gemma 4 MTP drafter testing 2026-05-06.

## Cannot tune

Surface area where you do not have a knob, even though the behaviour matters.

- **Server choice**: locked in by which model architecture you want to run. `bailing_hybrid` → vllm-mlx; JANGTQ → vmlx; standard MLX safetensors → lm-studio or `mlx_lm.server`; multimodal Gemma 4 vision → mlx-vlm.
- **Chat template content**: the model-author-shipped Jinja decides what goes to `reasoning` vs `content` vs `tool_calls`. You can override but it is brittle and breaks on every model swap.
- **Streaming SSE emission cadence**: server-side, opaque to the client. The Gemma 4 MTP drafter mlx-vlm streaming bug we hit lives here — the server generates 8192 tokens but emits the `delta.tool_calls` only as a final post-loop chunk, exceeding the agent's wall clock. No client-side fix possible.
- **Closed runtimes' internal heuristics**: lm-studio's chat-template auto-detection routes Qwen3 / Hermes / Gemma 4 channels without flags. The detection logic is not published.

## Cross-references

- [`tuning-by-workload.md`](tuning-by-workload.md) — same knobs, organized by which workload they dominate.
- [`../servers/lm-studio/prefill-speed-technique.md`](../servers/lm-studio/prefill-speed-technique.md) — full decomposition of why `--prefill-step-size` is no longer a useful lever on current `mlx-lm`.
- [`../models/techniques/model-technique-dflash.md`](../models/techniques/model-technique-dflash.md) — drafter workload-gating and cross-fork landscape.
- [`../servers/`](../servers/) — per-server runbooks with launch shapes that show which flags get set by default.
