# Plan: Benchmark LM Studio and Ollama on the Mac Studio

## Goal

Measure whether `LM Studio` and `Ollama` reduce local inference performance on the Mac Studio compared with the current MLX-based stack (`vllm-mlx`, `mlx-openai-server`, `mlx-lm.server`, `oMLX`), and quantify the tradeoff against better Mistral Small 4 compatibility.

## Questions to Answer

1. Does `LM Studio` in `MLX` mode perform close to the existing MLX servers?
2. How much slower is `LM Studio` in `llama.cpp` mode than the current MLX servers?
3. How much slower is `Ollama` than the current MLX servers on Apple Silicon?
4. For `Mistral Small 4`, is the likely performance drop worth the gain in compatibility?

## Why This Needs Two Benchmark Tracks

A direct `Mistral Small 4` comparison across all runners is not fully apples-to-apples:

- the current repo state does not have a supported working MLX path for `Mistral Small 4`
- `LM Studio` and `Ollama` are most practical with `GGUF`
- quantization and runtime differences would blur the server-overhead result

To avoid a misleading conclusion, split the work into:

1. a **runtime-overhead track** using a model available in both MLX and GGUF form
2. a **Mistral-specific track** using the best practical format on each runner

## Benchmark Matrix

### Track A: Runtime-overhead benchmark

Use one model family that exists in both MLX and GGUF with roughly comparable quality targets.

Recommended options, in order:

1. `Qwen3.5-35B-A3B-4bit` or nearest equivalent GGUF
2. `Qwen3-Coder-Next` if a comparable GGUF build is easier to obtain
3. a smaller proxy model only if the larger shared model is unavailable on one stack

Runners to compare:

- `vllm-mlx`
- `mlx-openai-server`
- `mlx-lm.server`
- `oMLX` if the model is available there
- `LM Studio (MLX)`
- `LM Studio (llama.cpp)`
- `Ollama`

### Track B: Mistral Small 4 practical benchmark

Use the strongest realistic local setup for each runner:

- `LM Studio (llama.cpp)` with a `GGUF` build
- `Ollama` with a `GGUF` build if a working Modelfile or built-in import path exists

Optional:

- `LM Studio (MLX)` only if it can actually load a stable MLX Mistral Small 4 model on the Mac Studio
- `mlx-openai-server` only if upstream `mlx-lm` gains native `mistral4` support before the benchmark is run

This track is for practical decision-making, not strict apples-to-apples comparison.

## Metrics

Collect the same metrics for every run:

- time to first token (`TTFT`)
- decode speed (`output tok/s`)
- prefill speed (`prompt tok/s`) if exposed or derivable
- total wall time
- peak memory
- CPU / GPU utilization snapshot
- server startup time
- model load time
- request success / failure mode

For Mistral Small 4, also record:

- plain direct chat success
- reasoning-mode success
- tool-call or agent-loop behavior

## Test Prompts

Use a fixed prompt set:

1. **Short direct chat**: low-latency sanity check
2. **Code generation**: medium response length
3. **Long-context recall**: 8K, 32K, and 64K prompt windows where supported
4. **Reasoning**: a short deterministic math or logic task
5. **Tool-compat probe** for Mistral track: prompt that should emit a tool call if the stack supports it

Keep prompts identical per track where possible.

## Conditions and Controls

Keep these constant:

- same Mac Studio machine
- same background load state as much as possible
- same thermal condition if feasible
- one active inference server at a time
- identical request shape per OpenAI-compatible runner
- same token limits
- same sampling settings when the stack allows it

Recommended generation settings for baseline throughput:

- `temperature = 0.0` for deterministic decode tests when supported
- `max_tokens = 128` for short runs
- `max_tokens = 512` for sustained decode tests

For Mistral Small 4, also run a second pass at the model's preferred settings:

- `temperature = 1.0`
- `top_p = 0.95`
- `top_k = 40`

## Runner-Specific Notes

### vllm-mlx

- baseline for best current MLX server performance in this repo
- use the existing wrapper and benchmark method from `docs/models/model-benchmark-api-server.md`

### mlx-openai-server

- include the shared-model benchmark
- do not include Mistral Small 4 unless upstream native support lands first
- note if the inference worker queue affects long-context throughput

### mlx-lm.server

- use as the thinnest MLX server baseline
- helps separate model-runtime performance from server-framework overhead

### oMLX

- include only where the target model is actually available
- expect scheduler overhead and poorer TTFT at large context

### LM Studio

Benchmark separately in:

- `MLX` runtime
- `llama.cpp` runtime

Important:

- verify which runtime is active before each run
- record whether continuous batching is enabled
- record whether the local server is OpenAI-compatible or whether benchmarking needs the app runtime API path

### Ollama

- verify Metal is active and not silently falling back to CPU
- record the exact Ollama version
- record the exact GGUF quantization or model package used

## Measurement Method

### API benchmark

For OpenAI-compatible endpoints:

- reuse the existing SSE benchmark approach from `docs/models/model-benchmark-api-server.md`
- parse streamed chunks to measure TTFT and per-token timing
- store raw JSON per run

### Local system metrics

Capture:

- `powermetrics` or `pmset` snapshots if permitted
- `ps`, `top`, or `vm_stat` snapshots
- memory pressure before and after each run

If high-friction, keep this lightweight and focus on:

- model RSS
- total used memory
- confirmation that GPU acceleration is active

## Success Criteria

The benchmark should produce a clear answer in one of these forms:

1. `LM Studio (MLX)` is within roughly 5-10% of the current MLX servers, so it is viable when its UI or server ergonomics matter.
2. `LM Studio (llama.cpp)` and `Ollama` are materially slower, but still acceptable for `Mistral Small 4` because they improve compatibility.
3. The performance drop is too large to justify switching away from the current MLX stack for general use.

## Deliverables

1. Raw benchmark output files
2. A markdown results summary under `docs/models/`
3. An updated README note only if the result materially changes the current server recommendation
4. A short decision note for `Mistral Small 4`:
   - switch to `LM Studio`
   - switch to `Ollama`
   - wait for upstream MLX support
   - use both, depending on workload

## Execution Order

### Phase 1: Environment preparation

1. Confirm installed versions of:
   - `LM Studio`
   - `Ollama`
   - `vllm-mlx`
   - `mlx-openai-server`
   - `mlx-lm`
   - `oMLX`
2. Confirm which shared benchmark model exists in both MLX and GGUF
3. Confirm a working `Mistral Small 4` GGUF path for `LM Studio` and `Ollama`

### Phase 2: Shared-model runtime-overhead benchmark

1. Run the current MLX baselines
2. Run `LM Studio (MLX)`
3. Run `LM Studio (llama.cpp)`
4. Run `Ollama`
5. Normalize results into one table

### Phase 3: Mistral Small 4 practical benchmark

1. Run `LM Studio` on the best working Mistral path
2. Run `Ollama` on the best working Mistral path
3. Add `mlx-openai-server` only if native upstream support lands first
4. Record both performance and compatibility behavior

### Phase 4: Analysis

1. Separate `same-model server overhead` conclusions from `best practical Mistral setup` conclusions
2. Call out where results are inference-limited by quantization differences
3. Recommend the default server choice for:
   - general coding use
   - Mistral Small 4 direct chat
   - Mistral Small 4 agent/tool workflows

## Risks

- Comparable GGUF and MLX quantizations may still differ enough to distort the result
- `LM Studio` may not expose every metric cleanly
- `Ollama` may regress on Apple Silicon if Metal falls back to CPU
- `Mistral Small 4` may still be functionally better on `llama.cpp` even if it is slower
- very large models may hit memory-pressure effects that make repeated runs noisy

## Recommendation

Do not decide based on web benchmarks alone.

Use web research to set expectations:

- `LM Studio (MLX)` should be in the same performance class as the MLX servers
- `LM Studio (llama.cpp)` and `Ollama` will likely be slower on token generation

Then run this plan on the Mac Studio and make the final choice from local numbers.
