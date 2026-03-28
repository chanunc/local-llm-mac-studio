# Plan: Add Mistral 4 MLA Support for mlx-openai-server

## Goal

Make `mlx-openai-server` serve `JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L` correctly on the Mac Studio by adding missing `mistral4` / MLA support in the underlying `mlx-lm` stack, then fixing the smaller OpenAI request-translation bug around `reasoning_effort`.

## Current State

- The model loads but produces garbage with direct `mlx_lm.generate()`.
- `mlx-openai-server` starts and exposes the model, but completions fail with HTTP 500 due to `reasoning_effort` handling.
- The repo already documents this model as broken on all MLX servers because `mlx-lm` lacks `mistral4` MLA support.

## Confirmed Technical Facts

### Local environment

- The installed JANG model config reports:
  - top-level `model_type = "mistral3"`
  - text `model_type = "mistral4"`
  - `kv_lora_rank = 256`
  - `q_lora_rank = 1024`
- `mlx_lm` in the `mlx-openai-server` venv currently has:
  - `mistral3.py`
  - no `mistral4.py`
  - reusable MLA helpers in `mla.py`
  - a working MLA implementation in `deepseek_v3.py`
- The same venv already has `transformers 5.4.0`, including:
  - `transformers.models.mistral4.configuration_mistral4`
  - `transformers.models.mistral4.modeling_mistral4`

### External references

- Mistral's model page says `reasoning_effort` is model-specific and expects `none` or `high`, and recommends `vLLM` for production-ready inference:
  - https://huggingface.co/mistralai/Mistral-Small-4-119B-2603
- The same model page says local serving may still be subpar and recommends the Mistral API when that happens.
- Hugging Face Transformers added Mistral 4 support in PR `#44760`, merged on March 16, 2026:
  - https://github.com/huggingface/transformers/pull/44760
- `llama.cpp` added Mistral Small 4 support in PR `#20649`, merged on March 16, 2026, and explicitly references the Transformers PR:
  - https://github.com/ggml-org/llama.cpp/pull/20649
- `llama.cpp` notes this model needs MLA-specific handling and backend specialization for unusual attention dimensions.
- Unsloth's GGUF page points users to `llama.cpp` / vLLM paths and says it includes chat-template fixes, but it does not provide an MLX patch path:
  - https://huggingface.co/unsloth/Mistral-Small-4-119B-2603-GGUF

## Root Cause

This is primarily an `mlx-lm` model-support gap, not an `mlx-openai-server` feature gap.

Today, `mlx_lm.models.mistral3` falls back to non-MLA text implementations (`ministral3` or `llama`) and ignores the `mistral4` text architecture encoded in `text_config`.

That means the current stack does not implement:

- query LoRA projection path (`q_a_proj` + `q_b_proj`)
- compressed KV / MLA path (`kv_a_proj_with_mqa`)
- the split between non-RoPE and RoPE query/key dimensions
- Mistral 4 MoE routing and shared experts
- Mistral 4 rope/interleave details
- Mistral 4 reasoning template semantics

The separate `reasoning_effort` HTTP 500 is a smaller server bug:

- `mlx-openai-server` schema currently models `reasoning_effort` as `low | medium | high`
- Mistral 4 expects `none | high`
- the Responses-to-Chat translation path appears to ignore the supplied field and later defaults to an unsupported value

## Proposed Approach

### Strategy

Implement a correctness-first `mistral4` text backend in `mlx-lm`, then patch `mlx-openai-server` request handling for Mistral 4 chat templates.

Do not start with full optimization. First get coherent greedy outputs. Optimize later if needed.

### Why this approach

- It reuses the existing MLX codebase instead of inventing a model runner from scratch.
- The installed `transformers` package already provides a reference implementation.
- `mlx_lm` already has MLA building blocks (`mla.py`) and a close MLA relative (`deepseek_v3.py`).
- The repo already accepts site-packages patching for JANG and tool-arg fixes, so a local patch path is operationally consistent.

## Implementation Plan

### Phase 1: Correctness spike in `mlx-lm`

1. Add a new `mlx_lm.models.mistral4` module in the `mlx-openai-server` venv or a repo-managed patch layer.
2. Port the text path from `transformers.models.mistral4` into MLX:
   - `ModelArgs`
   - `Attention`
   - `MLP`
   - `MoE`
   - decoder layer
   - text `LanguageModel`
3. Reuse these existing MLX pieces where possible:
   - `mla.py` for multi-linear MLA projections
   - `deepseek_v3.py` as the MLA reference
   - `mistral3.py` for rope scaling and model wrapper structure
4. Update `mlx_lm.models.mistral3.Model` dispatch:
   - if `text_config.model_type == "mistral4"`, route text weights to the new `mistral4` module
5. Start with text-only support.
   - Vision can remain unsupported in `mlx-openai-server` `lm` mode for the first patch.

### Phase 2: Minimal server compatibility fixes

1. Patch `mlx-openai-server` request schema / translation for Mistral 4:
   - allow `reasoning_effort = "none"` where appropriate
   - avoid defaulting to `"medium"` for Mistral 4 chat-template kwargs
   - preserve `"high"` when explicitly requested
2. Verify `chat_template_kwargs` passed into the tokenizer template match Mistral 4 expectations.
3. Keep this patch as narrow as possible so it does not regress Qwen or other families.

### Phase 3: Validation

1. Direct load test:
   - `mlx_lm.load()` on the JANG model
   - greedy generation on short prompts
2. Server smoke test:
   - `/v1/models`
   - `/v1/chat/completions`
   - `/v1/responses`
3. Reasoning mode test:
   - `reasoning_effort = "none"`
   - `reasoning_effort = "high"`
4. Regression test:
   - existing `Qwen3.5-35B-A3B JANG 4K` still works on `mlx-openai-server`

### Phase 4: Hardening

1. Add a repo-managed patch script similar to the existing JANG and tool-arg patches.
2. Document:
   - what files are patched
   - how to re-apply after upgrades
   - known limitations
3. Optionally upstream:
   - `mlx-lm` Mistral 4 support
   - `mlx-openai-server` reasoning-effort fix

### Phase 5: Upgrade resilience

1. Make the local patch scripts version-aware:
   - detect installed `mlx-lm` and `mlx-openai-server` versions
   - refuse to patch unknown layouts without an explicit override
2. Match on stable code anchors instead of raw line numbers where possible.
3. Add a post-upgrade verification command set:
   - import / load smoke test
   - short generation test
   - `/v1/models`
   - `/v1/chat/completions`
4. Keep a compatibility note in this repo for:
   - known-good `mlx-lm` versions
   - known-good `mlx-openai-server` versions
   - any upstream versions where the patch is no longer needed
5. Prefer shrinking the local patch over time:
   - if upstream adds native `mistral4` support, drop the local `mlx-lm` patch
   - if upstream fixes `reasoning_effort`, drop the local server patch

## Recommended Patch Shape

### Short-term

Use a local patch layered onto the installed `mlx-openai-server` venv on the Mac Studio.

Reason:

- fastest path to proof of correctness
- aligns with existing patch-based operations in this repo
- avoids blocking on upstream review

### Medium-term

If the spike succeeds, convert it into:

1. a clean patch script in this repo, and
2. an upstreamable PR against `mlx-lm`

This is intended to survive routine package updates, but not silently. The patch layer should fail closed on unexpected upstream refactors and require a quick review rather than pretending compatibility.

## Validation Gates

Proceed only if each gate passes:

1. `mlx_lm.generate()` must stop producing repetitive nonsense.
2. Short deterministic prompts must produce coherent answers matching the prompt intent.
3. `mlx-openai-server` must return HTTP 200 for simple completions.
4. `reasoning_effort = "none"` must not trigger server errors.
5. Existing working models must still load and answer normally.

If Phase 1 fails, stop and do not continue patching the server layer. At that point the right answer is likely:

- wait for upstream `mlx-lm` support, or
- run this model on a non-MLX backend such as vLLM / llama.cpp / Mistral API instead

## Risks

- The Mistral 4 MLA path may need more than a straightforward port from Transformers to MLX.
- Full correctness may require cache behavior changes, not just attention math.
- Vision-related wrapper logic may complicate the `mistral3` container model, even if we only want text.
- The unusual attention dimensions may expose backend performance or correctness issues on Apple Silicon.
- The server `reasoning_effort` bug may involve both schema defaults and chat-template invocation.

## Time Estimate

- Research + port spike: 0.5 to 1.5 days
- Server fix + validation: 0.5 day
- Hardening + docs: 0.5 day

Best case: 1 day to first coherent local output.
More realistic: 2 to 3 days including regressions and packaging.

## Search Outcome Summary

- GitHub and Hugging Face provide actionable information.
- Unsloth confirms alternate supported runtimes, but not an MLX solution.
- Reddit is useful only as ecosystem signal that `llama.cpp` support landed quickly.
- I did not find an actionable existing fix on dev.to or X for MLX / `mlx-lm` specifically.

## Recommendation

Proceed with a correctness-first local patch to `mlx-lm` plus a very small `mlx-openai-server` request-handling fix.

Do not try to patch `mlx-openai-server` alone. That will not solve the underlying MLA problem.
