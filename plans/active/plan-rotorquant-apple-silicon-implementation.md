# RotorQuant on Apple Silicon: Implementation Plan for MLX, mlx-lm, mlx-openai-server, and vllm-mlx

## Context

This plan covers how to evaluate and potentially integrate **RotorQuant** into the Apple Silicon inference stack used in this repo.

**What RotorQuant is:** A KV-cache compression method that reworks TurboQuant's dense random rotation step using **Clifford rotors**. The claimed advantage is that the expensive rotation becomes much cheaper to compute, especially with fused CUDA or Metal kernels, while preserving similar real-model attention fidelity.

**Why this matters here:** The repo already explored TurboQuant in [plan-turboquant-mlx-implementation.md](plan-turboquant-mlx-implementation.md). That work showed TurboQuant was not worthwhile for the current Qwen3.5-122B-A10B target on the Mac Studio because the Python/MLX implementation was too slow and memory-unfriendly in practice. RotorQuant is interesting because it specifically claims a much cheaper kernel path, including **Metal** on Apple Silicon.

**Primary objective:** Determine whether RotorQuant can provide a practical Apple Silicon KV-cache compression path that is:
- faster to execute than the prior TurboQuant MLX approach
- memory-positive for long-context inference
- compatible with the actual server stack used here (`mlx-lm`, `mlx-openai-server`, `vllm-mlx`)

## Key Sources

- RotorQuant Reddit thread: [r/LocalLLaMA discussion](https://www.reddit.com/r/LocalLLaMA/comments/1s44p77/rotorquant_1019x_faster_alternative_to_turboquant/)
- RotorQuant paper: [rotorquant.pdf](https://www.scrya.com/rotorquant.pdf)
- RotorQuant code: [scrya-com/rotorquant](https://github.com/scrya-com/rotorquant)
- MLX: [ml-explore/mlx](https://github.com/ml-explore/mlx)
- mlx-lm: [ml-explore/mlx-lm](https://github.com/ml-explore/mlx-lm)
- vllm-mlx: [waybarrios/vllm-mlx](https://github.com/waybarrios/vllm-mlx)
- Existing repo context: [plan-turboquant-mlx-implementation.md](plan-turboquant-mlx-implementation.md)

## Summary Judgment Up Front

**Best prototype target:** `mlx-lm`

**Best server integration target after that:** `mlx-openai-server`

**Best production-style Apple serving target:** `vllm-mlx`

**Best long-term upstream home:** `MLX`

This ordering matters:
- `mlx-openai-server` is not the right first target because it mostly wraps `mlx-lm`; it should consume a working RotorQuant cache mode, not invent one.
- `vllm-mlx` is the most valuable end state, but it adds paged cache, prefix sharing, and continuous batching, which make the first implementation much harder.
- `mlx-lm` is the narrowest place to prove correctness, memory benefit, and decode cost on Apple Silicon.

## Why RotorQuant May Succeed Where TurboQuant Did Not

The prior TurboQuant exploration in this repo failed for practical reasons:
- decode overhead was too high
- temporary buffers pushed memory usage up
- the implementation path was not sufficiently kernel-fused

RotorQuant's appeal is specifically:
- much lower rotation compute
- far fewer parameters for the rotation path
- a Metal shader path already exists in the reference repo
- its best story is not just "compression works", but "the hot path is cheap enough to matter"

This does **not** guarantee success on MLX. It only justifies another attempt, because the current public RotorQuant project already includes the missing piece that TurboQuant lacked here: a purpose-built Apple Metal implementation.

## Constraints and Risks

### Main technical risks

1. **Decode-path integration risk**
   - Compressing KV cache offline is easier than reading it efficiently during decode.
   - If attention must materialize too much dequantized state, the memory and speed gains collapse.

2. **MLX integration risk**
   - RotorQuant's current implementation is PyTorch-first, not MLX-native.
   - A useful port likely needs either custom MLX/Metal kernels or a carefully designed fallback path.

3. **Paged-cache risk in `vllm-mlx`**
   - RotorQuant must cooperate with page allocation, prefix sharing, and continuous batching.
   - This is meaningfully harder than integrating into a simple rotating cache.

4. **Model-shape risk**
   - RotorQuant's public validation is still narrow.
   - Head dimension, KV-head count, and model architecture may expose edge cases not covered by the published tests.

### Main product risks

1. Good microbenchmarks but weak end-to-end generation benefit
2. Compression helps memory but hurts latency too much
3. Benefits only appear on a subset of models or only at very long context lengths

## Recommended Rollout Order

### Phase 1: `mlx-lm` proof of concept

**Goal:** Prove RotorQuant on Apple Silicon in the simplest possible MLX-based inference loop.

**Success criteria:**
- one text model runs end-to-end with RotorQuant KV cache enabled
- 4-bit path shows acceptable quality regression
- long-context memory use drops materially
- decode slowdown is small enough to remain interesting

**Why first:**
- `mlx-lm` already owns generation, rotating KV cache, and prompt caching
- it is the smallest Apple stack component where KV-cache behavior can be changed meaningfully

### Phase 2: `mlx-openai-server` integration

**Goal:** Expose the `mlx-lm` RotorQuant mode behind the existing OpenAI-compatible server.

**Success criteria:**
- server launch flag or YAML option enables RotorQuant
- simple chat and long-prompt flows work
- metrics/logging show cache mode and memory effects

**Why second:**
- almost all algorithmic work should already exist in `mlx-lm`
- the server layer should stay thin

### Phase 3: `vllm-mlx` integration

**Goal:** Make RotorQuant work in the higher-throughput Apple serving path with paged KV cache and continuous batching.

**Success criteria:**
- quantized paged cache works with shared prefixes
- no obvious correctness regressions under concurrency
- memory savings increase effective long-context serving capacity

**Why third:**
- highest complexity
- highest practical payoff if successful

### Phase 4: Optional `MLX` upstreaming

**Goal:** Move reusable low-level RotorQuant primitives into `MLX` if the design proves worthwhile.

**Success criteria:**
- reusable kernel or primitive exists below `mlx-lm`
- future MLX projects can use the same implementation

## Detailed Plan

## Phase 1: `mlx-lm` Prototype

### Scope

Start with:
- one text model
- one supported cache layout
- **4-bit only**
- **post-prefill quantization only**

Do **not** start with:
- multiple models
- aggressive low-bit settings
- paged cache
- server integration

### Likely areas to patch

The exact files may vary by upstream version, but the work will likely touch:
- cache classes
- cache creation path
- generation / decode loop
- attention path where keys and values are read from cache
- model-specific cache overrides where the default cache logic is bypassed

### Sub-phases

#### 1A. Add a new cache mode

Create a new cache type, conceptually:
- `RotorQuantKVCache`

It should store:
- quantized K and V payload
- rotor-related packed coefficients or metadata
- per-group or per-vector norm data
- QJL residual correction state where needed
- original shape metadata required for attention

#### 1B. Add post-prefill quantization

Match RotorQuant's current practical story:
- run prefill in fp16/bf16
- quantize the accumulated cache after prefill
- avoid quantizing token-by-token during prefill initially

This minimizes error compounding and keeps the first experiment closer to the public reference implementation.

#### 1C. Add decode-time read path

Two possible designs:

1. **Simple first-pass design**
   - dequantize the necessary K/V slices when attention reads them
   - easier to validate
   - less likely to preserve full speed gains

2. **Preferred design**
   - implement a fused gather-dot or fused attention-adjacent path over quantized cache
   - harder, but far more likely to preserve actual benefit

Recommendation:
- build the simple path first for correctness
- only continue if memory gains are real
- then replace the slow path with a fused read path

#### 1D. Add Metal-backed kernels

The current RotorQuant repo already includes a Metal shader. The Apple-side experiment should try to reuse the algorithmic structure of that shader, not invent a new math path.

Implementation options:
- direct custom Metal kernel integration if MLX permits it cleanly
- slower reference MLX ops path for correctness
- optional hybrid fallback: reference path for unsupported shapes, Metal path for supported ones

#### 1E. Validation

Validation set:
- cosine similarity on real KV cache data
- small perplexity check
- retrieval / needle tests
- long-context generation
- memory before/after
- decode tok/s before/after

### Exit criteria for Phase 1

Proceed only if all are true:
- quality is not obviously degraded
- memory improves at useful context lengths
- decode overhead is acceptable

Stop if:
- memory savings are erased by temp buffers
- decode becomes too slow
- only microbenchmarks improve while generation regresses materially

## Phase 2: `mlx-openai-server` Integration

### Scope

Assume `mlx-lm` already exposes a usable RotorQuant cache mode.

### Likely areas to patch

- server config parsing
- model launch / load options
- cache-mode plumbing into `mlx-lm`
- metrics and logs
- compatibility guards

### Proposed configuration shape

Examples:
- `kv_cache_quantization: rotorquant`
- `rotorquant_bits: 4`
- `rotorquant_mode: post_prefill`

### Required behavior

- default remains unchanged when the flag is absent
- fail closed for unsupported models or shapes
- clear logs when RotorQuant is enabled
- no silent fallback unless explicitly requested

### Validation

- `/v1/models`
- simple chat completion
- long system prompt + follow-up request
- repeated multi-turn request using cached prefix

### Exit criteria for Phase 2

Proceed only if:
- the server remains stable
- latency overhead is acceptable
- the cache mode is observable and controllable

## Phase 3: `vllm-mlx` Integration

### Scope

This is the highest-value Apple serving target, but also the highest-risk one.

`vllm-mlx` advertises:
- paged KV cache
- prefix sharing
- continuous batching

Those features are exactly what make RotorQuant integration more difficult.

### Likely areas to patch

- paged cache data structures
- page allocation / metadata
- page reuse and prefix-sharing logic
- decode attention kernels over paged cache
- scheduler logic around prefill-to-decode transition

### Sub-phases

#### 3A. Define quantized page format

Each page must be able to store:
- quantized K/V data
- rotor metadata
- residual correction state
- shape and paging metadata

This format must support:
- random access during decode
- shared-page reuse
- deterministic reconstruction or scoring

#### 3B. Add post-prefill page conversion

After prefill:
- convert filled pages into RotorQuant form
- avoid redundant work for shared prefixes
- avoid large scheduler stalls

#### 3C. Add decode support over quantized pages

Preferred behavior:
- operate directly on quantized pages during attention
- avoid full-page dequantization

Fallback:
- partial dequantization for correctness testing only

#### 3D. Prefix-sharing compatibility

This is a critical correctness area.

Must verify:
- shared prefixes are not requantized redundantly
- reference counts / ownership remain correct
- page eviction and reuse remain safe

#### 3E. Continuous batching validation

Test scenarios:
- mixed prefill and decode batches
- multiple requests sharing prefixes
- long-context requests coexisting with short ones
- scheduler behavior during quantization transitions

### Exit criteria for Phase 3

Proceed only if:
- correctness survives concurrency
- memory savings improve effective serving capacity
- throughput remains competitive

## Phase 4: Optional `MLX` Upstreaming

### Scope

Only worth doing if `mlx-lm` or `vllm-mlx` proves the design on real Apple workloads.

### Candidate upstream pieces

- low-level RotorQuant packing/unpacking primitives
- Metal kernel wrappers
- fused gather-dot or cache-read primitives
- reusable quantized-cache support hooks

### Why upstream at all

If the low-level implementation lives only in app-level repos:
- maintenance burden stays high
- every Apple inference stack repeats the same kernel work

If the useful pieces move into `MLX`:
- both `mlx-lm` and `vllm-mlx` become simpler to maintain

## Suggested Validation Matrix

### Models

Start with:
- one small text model with simple architecture

Then expand to:
- one medium text model
- one model with long-context use case
- one MoE model only after the dense-model path is stable

### Metrics

- prefill tok/s
- decode tok/s
- TTFT
- peak memory
- steady-state memory
- cache compression ratio
- perplexity delta
- retrieval / needle score
- qualitative response sanity

### Apple hardware targets

Minimum:
- one recent Apple Silicon machine

Preferred:
- test on both:
  - smaller Apple Silicon box
  - Mac Studio M3 Ultra 96GB

This matters because the RotorQuant paper's Apple result is on Apple M4, not on the exact Mac Studio hardware used here.

## Rollback Criteria

Abort or pause the effort if any of these hold:
- no convincing end-to-end win over fp16/bf16 cache
- memory savings disappear due to temp buffers or dequantization overhead
- integration requires invasive framework patches without a clear performance upside
- quality regression is material at the intended context lengths

## Repo-Level Deliverables

If implementation proceeds, the expected deliverables should be:

1. `plans/active/plan-rotorquant-apple-silicon-implementation.md`
2. prototype patch set or fork for `mlx-lm`
3. optional `mlx-openai-server` integration patch
4. optional `vllm-mlx` integration patch
5. benchmark notes for Apple Silicon
6. maintenance notes on supported models, bits, and failure cases

## Final Recommendation

Do **not** start with `mlx-openai-server`.

Do this instead:

1. prototype RotorQuant in `mlx-lm`
2. prove correctness and memory benefit on Apple Silicon
3. expose it through `mlx-openai-server`
4. only then consider `vllm-mlx`

That sequence gives the best chance of learning something useful without paying the full complexity cost of paged cache and continuous batching too early.
