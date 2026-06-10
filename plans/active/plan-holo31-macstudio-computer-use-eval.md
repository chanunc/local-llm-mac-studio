Status: active
Created: 2026-06-07
Canonical: no

# Holo 3.1 Mac Studio Model And Computer-Use Evaluation

Evaluate the Holo 3.1 family on the Mac Studio M3 Ultra (96 GB), select the
best speed/quality variants, and build a repeatable computer-use benchmark
that follows the repository's existing API and OpenCode benchmark posture.

This is a research and execution plan, not a live-state runbook. Check the
machine with `scripts/chk_llm_macstu.py` before deployment.

## Executive Recommendation

Test three models, in this order:

| Role | Model | Format | Download | Why |
|:--|:--|:--|--:|:--|
| Speed candidate | `pipenetwork/Holo-3.1-4B-MLX-4bit` | MLX 4-bit | 3.97 GB | Best published family cost/performance point; likely fastest useful Holo 3.1 model on Apple Silicon |
| Quality candidate | `Hcompany/Holo-3.1-35B-A3B-GGUF` | Official Q4_K_M + F16 mmproj | 21.30 + 0.90 GB | Highest family score, only 3B active parameters, official consumer-hardware and Apple path |
| Grounding comparator | `pipenetwork/Holo-3.1-9B-MLX-4bit` | MLX 4-bit | 7.42 GB | Slightly stronger UI grounding and business/collaboration results than 4B |

Do not lead with:

- `Holo-3.1-0.8B`: fastest absolute model, but published overall performance
  is 47.5%, OSWorld is 34.6%, and Multi-Apps is 2.4%. Keep only as a latency
  floor or harness smoke model.
- 35B BF16: 69.38 GB before runtime/KV overhead. It technically fits 96 GB
  unified memory, but leaves poor operational headroom. Check disk space
  dynamically before any download.
- 35B FP8: NVIDIA-oriented compressed-tensors path, not an Apple-native speed
  choice.
- 35B NVFP4: NVIDIA Model Optimizer W4A16 checkpoint tested with vLLM on
  NVIDIA hardware. It is not a usable MLX or llama.cpp quantization.
- Community abliterated or coder derivatives: they change the model rather
  than only its representation, so they cannot answer the base-family
  speed/quality question.

The expected winner depends on the objective:

- **Fastest useful agent:** 4B MLX 4-bit.
- **Best task success with still-fast sparse decode:** 35B-A3B Q4 GGUF.
- **Best compact grounding specialist:** 9B MLX 4-bit, but only if its small
  grounding gain survives local testing.

## Published Family Results

H Company's Holo 3.1 table reports:

| Benchmark | 0.8B | 4B | 9B | 35B-A3B |
|:--|--:|--:|--:|--:|
| Overall | 47.5 | 72.6 | 73.0 | 78.3 |
| OSWorld | 34.6 | **75.8** | 71.5 | **80.0** |
| AndroidWorld | N/A | 72.4 | 72.4 | **79.3** |
| E-Commerce | 67.4 | **94.3** | 92.2 | **97.8** |
| Business Software | 62.6 | 86.4 | **87.8** | **90.1** |
| Collaboration | 42.3 | 73.4 | **79.8** | 75.3 |
| Multi-Apps | 2.4 | **46.8** | 45.2 | **65.5** |
| ScreenSpot-Pro | 54.3 | 66.5 | **69.1** | **71.5** |
| OSWorld-G | 57.5 | 73.1 | **75.7** | **78.8** |

Implications:

- The 9B model is only 0.4 points above 4B overall and is lower on OSWorld,
  e-commerce, and multi-app tasks. It is not an automatic upgrade.
- The 9B model's case is narrower: collaboration, business software, and
  static grounding.
- The 35B-A3B model adds meaningful long-horizon and multi-app capability
  while keeping only about 3B language parameters active per token.
- Published scores are model-plus-harness results. They must not be treated
  as guaranteed local scores under a different prompt, runtime, image policy,
  or action executor.

Sources:

- [Holo 3.1 model collection](https://huggingface.co/collections/Hcompany/holo31)
- [Holo 3.1 release and Apple reference chart](https://hcompany.ai/holo3.1)
- [Holo agent-loop contract](https://hub.hcompany.ai/agent-loop)
- [Holo quickstart and localization contract](https://hub.hcompany.ai/quickstart)

## Mac Runtime Assessment

### MLX 4-bit

Community MLX conversions exist for 4B, 9B, and 35B-A3B. The conversion author
reports that screenshots, UI button grounding, and on-screen text were tested.
The language weights are group-size-64 4-bit while the vision tower remains at
higher precision.

Current lab gap:

- Installed `mlx-vlm`: 0.5.0.
- Holo 3.1 requires Qwen3.5-VL support from `mlx-vlm` main.
- The conversion currently requires adding `qwen3_5_vision` and
  `qwen3_5_moe_vision` to the vision model-type allow-list.

Treat these conversions as provisional until the following pass:

1. Weight load without missing/unexpected tensors.
2. Text-only generation.
3. OCR sanity image.
4. Coordinate grounding image.
5. Multi-turn screenshot/action replay.
6. Native function-call or strict structured-output parsing.

MLX should be the first speed path for 4B and 9B because it avoids a separate
GGUF projector and is normally the strongest Apple-native throughput path.
That is a hypothesis to benchmark, not a measured Holo 3.1 result.

### Official 35B Q4 GGUF

Official files:

| File | Size |
|:--|--:|
| `q4_k_m.gguf` | 21.30 GB |
| `mmproj.f16.gguf` | 0.90 GB |
| `main.bf16.gguf` | 69.38 GB |

The installed llama.cpp build (`510b5c2`, 2026-05-20) supports multimodal
projectors, image token controls, and prompt caching. It is the lowest-risk
first deployment for the official 35B quant.

H Company's measured Apple reference is a MacBook M4 Pro running the 35B Q4
GGUF:

| Harness | Model requests/min | Mean request interval |
|:--|--:|--:|
| Default | 3.6 | 16.7 s |
| Fast | 5.5 | 10.9 s |

Do not extrapolate an M3 Ultra number before measuring it. The M3 Ultra has
more memory bandwidth and GPU resources, but end-to-end request rate also
depends on screenshot processing, output length, prompt/image caching, and
the executor.

The vendor notes that llama.cpp did not yet support prefix or image caching
for this Qwen architecture in its test. Verify the current build rather than
assuming generic `--cache-prompt` means vision embeddings are reused.

### 35B MLX 4-bit

`pipenetwork/Holo-3.1-35B-A3B-MLX-4bit` is 23.46 GB. It may beat GGUF on
Apple Silicon once Qwen3.5-VL support is stable, especially for repeated
screenshots and long prompts. It should be a second-round runtime comparison,
not the first deployment, because both the conversion and required runtime
support are newly published and third-party.

## Benchmark Design

Create `scripts/bench/bench_computer_use_agent.py`. Reuse the operational
shape of `bench_agent_tool_call.py`, but do not invoke OpenCode as the primary
agent. OpenCode's current benchmark proves generic tool selection; it does
not expose the model's screenshot grounding or normalized coordinate quality.

The new driver should:

- Call an OpenAI-compatible multimodal endpoint.
- Send real screenshots as base64 `image_url` blocks.
- Parse either native `tool_calls` or Holo's structured
  `{note, thought, tool_call}` output.
- Execute actions through a pluggable environment adapter.
- Reset each task to a deterministic initial state.
- Grade the actual environment state, not the wording of the final answer.
- Write raw JSON under
  `docs/models/benchmarks/logs/<model-slug>/computer-use-agent-<runtime>.json`.

### Holo Conversation Contract

Preserve H Company's documented conventions:

- Coordinates are normalized integers in `[0, 1000]`.
- Scale coordinates against the exact image bytes sent to the model.
- Keep at most the last three screenshots in context.
- Retain older observation wrappers but replace old images with text.
- Preserve `note` as durable task memory.
- Do not replay hidden reasoning into conversation history.
- In structured JSON mode, return action results as user
  `<tool_output>` messages.
- In native function-call mode, test the runtime's parser independently;
  do not mix output protocols inside a scored run.

Run two protocol tracks:

1. **Structured Holo JSON:** closest to the documented training harness.
2. **Native function calling:** closest to OpenCode and general agent clients.

Report them separately. Near-parity is a release claim that needs local
verification.

## Evaluation Layers

### Layer 0: API And Vision Contract

Fast fail checks, one run each:

- text completion
- screenshot OCR
- normalized coordinate output
- native function call
- structured JSON output
- second-turn screenshot/action replay

No model proceeds if image input or action parsing is unreliable.

### Layer 1: Static UI Grounding

Use a deterministic ScreenSpot-style local fixture set:

- 30 screenshots total: web, desktop, and mobile
- text buttons, icon-only controls, menus, small targets, high-DPI targets
- target bounding boxes recorded in a manifest
- pass when predicted point falls inside the target box

Metrics:

- hit rate
- mean distance to target center
- invalid/out-of-range coordinate rate
- median and p95 latency
- cold-image versus repeated-image latency

After the local set is stable, add an optional adapter for the official
[ScreenSpot-Pro](https://github.com/likaixin2000/ScreenSpot-Pro-GUI-Grounding)
evaluation set. Keep public-suite results separate from local fixtures.

### Layer 2: Deterministic Local Browser Tasks

Build 12-20 local HTML tasks served from a fixture server and controlled by
Playwright:

- click a named control
- fill and submit a form
- choose date/filter/sort values
- dismiss a modal and continue
- scroll to a target
- copy data between two pages
- recover after an injected stale click or obstructing overlay

Each task gets:

- deterministic reset
- task text
- maximum step count
- allowed action schema
- programmatic final-state grader
- expected minimal step count

This is the routine deploy benchmark. It is local, cheap, repeatable, and
close to the repository's OpenCode benchmark philosophy.

### Layer 3: BrowserGym / WorkArena

Add an environment adapter for
[BrowserGym](https://github.com/ServiceNow/BrowserGym). Start with a small
MiniWoB++ or open-ended browser subset. Use WorkArena only after the local
browser suite is stable because ServiceNow setup and task breadth add
substantial operational cost.

Run 10-20 fixed tasks for promotion; do not run thousands of WorkArena
instances on every model deployment.

### Layer 4: OSWorld-Verified

Use [OSWorld-Verified](https://os-world.github.io/) for the final desktop
promotion test:

- Start with 10 tasks across browser, file manager, office, and multi-app work.
- Run the environment on a Linux/VM host and call the Mac Studio model over
  its OpenAI-compatible LAN endpoint.
- Use OSWorld's execution-based graders.
- Keep the exact OSWorld commit, task IDs, image resolution, action space,
  max steps, and prompt hash in the result JSON.
- Expand to 30 tasks only for close candidates; full 361/369-task runs are
  release-grade, not routine local deploy checks.

### Layer 5: AndroidWorld

Holo 3.1 explicitly targets mobile. After desktop/browser evaluation, run a
10-task sample using
[AndroidWorld](https://github.com/google-research/android_world):

- contacts
- calendar
- files
- clock
- browser

Use the emulator's durable task reward as the score. Keep this optional
because emulator setup and reset cost are higher than browser fixtures.

## Metrics And Result Schema

Primary metrics:

- task success rate / pass@1
- grounding hit rate
- median successful-task wall time
- median model time per step
- median steps to success
- invalid action rate
- timeout rate
- recovery rate after one injected disturbance

Efficiency metrics:

- cold and warm TTFT
- requests/min
- input/output/reasoning tokens
- screenshot dimensions and encoded bytes
- peak resident/unified memory
- model load time
- repeated-image speedup

Store aggregate and per-step details. A task failure must preserve:

- screenshot hash/path
- raw model response
- parsed action
- executor result
- grader result
- timing and token usage
- parser/runtime errors

## Fair Comparison Rules

- Same task manifest and fixture commit for every model.
- Same screenshot bytes and resolution.
- Same action schema and executor.
- Temperature 0 for localization; fixed temperature for agent loops.
- Fixed thinking mode per protocol track.
- Same maximum steps and timeout.
- One cold run plus three measured warm runs for latency microbenchmarks.
- At least three seeds/instances for dynamic tasks.
- Report model, runtime, and harness separately.
- Never compare vendor OSWorld numbers directly with a different local
  harness as if they were the same experiment.

## Proposed CLI

```bash
python3 scripts/bench/bench_computer_use_agent.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model pipenetwork/Holo-3.1-4B-MLX-4bit \
  --runtime mlx-vlm \
  --suite local-browser \
  --protocol structured-json \
  --runs 3 \
  --max-steps 20 \
  --output docs/models/benchmarks/logs/holo31-4b-mlx4/computer-use-agent-mlx-vlm.json
```

Suggested suites:

| Suite | Scope | Target wall time |
|:--|:--|:--|
| `smoke` | Layer 0 + 3 static targets + 2 browser tasks | <5 min |
| `standard` | 30 static targets + 12 local browser tasks | 15-30 min |
| `promotion` | Standard + 10 BrowserGym + 10 OSWorld tasks | 1-3 hr |
| `mobile` | 10 AndroidWorld tasks | Separate run |

## Deployment And Test Order

1. Upgrade a separate `mlx-vlm` test environment from main and apply the
   temporary Qwen3.5 vision allow-list patch.
2. Run 4B MLX 4-bit through Layer 0, then `smoke` and `standard`.
3. Run 9B MLX 4-bit only if the 4B grounding failure rate leaves room for its
   published advantage to matter.
4. Update/build llama.cpp if required by Holo 3.1, then run the official 35B
   Q4 GGUF with its F16 projector.
5. Compare 4B MLX versus 35B GGUF on success per second, not tok/s alone.
6. If 35B wins on quality but llama.cpp request latency is weak, run the
   third-party 35B MLX 4-bit as a runtime comparison.
7. Promote at most two candidates to BrowserGym/OSWorld and one to
   AndroidWorld.

## Selection Gates

Promote the 4B model if:

- static grounding is within 5 absolute points of 9B,
- local-browser success is within 10 points of 35B,
- and median successful-task time is at least 25% lower than 35B.

Promote the 35B model if:

- it improves local-browser success by at least 10 points, or
- it materially reduces loops/recovery failures on multi-step tasks,
- while median step latency remains operationally acceptable.

Retain the 9B model only if:

- it improves static grounding by at least 5 points over 4B, or
- it closes at least half the 4B-to-35B success gap at substantially lower
  latency than 35B.

## Repository Changes After Execution

Implementation:

- `scripts/bench/bench_computer_use_agent.py`
- `scripts/README.md`
- deterministic fixture manifest and fixture README

After measured runs:

- raw JSON under `docs/models/benchmarks/logs/<model-slug>/`
- a computer-use benchmark summary under `docs/models/benchmarks/`
- Holo family section in `docs/models/model-summary.md`
- a Holo family deep dive under `docs/models/per-model/` if runtime and
  harness details exceed a compact model-summary section
- `docs/models/README.md` index update if a deep dive is added
- `README.md` model table only after a model has been deployed and measured

If a new persistent server type is introduced, follow Sync Policy Event 1.
Do not update canonical docs based on downloadability or vendor results alone.

## Acceptance Criteria

- 4B MLX, 9B MLX, and 35B official GGUF have explicit load/vision/tool
  compatibility results.
- `smoke` and `standard` run from one script and emit comparable JSON.
- Grounding is scored against bounding boxes.
- Browser tasks are scored by final environment state.
- Structured JSON and native function calling are reported separately.
- Cold/warm image behavior and end-to-end request rate are measured.
- At least 10 OSWorld-Verified tasks are run for the final two candidates.
- The selected model is justified by task success per wall-clock time, not
  parameter count or decode throughput alone.
