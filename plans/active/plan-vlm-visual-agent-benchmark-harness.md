Status: active
Created: 2026-06-03
Canonical: no

# Visual Agent Benchmark Harness

Build a focused VLM benchmark script for OCR, chart, screenshot, and video tasks that mirrors the existing OpenCode agent tooling benchmark posture: small deterministic scenarios, real OpenAI-compatible API path, tool-use assertions, latency capture, and JSON logs suitable for model-to-model comparison.

This plan is not a live runbook. It defines the harness and fixture-selection workflow only.

## Goal

Create `scripts/bench/bench_vlm_agent_task.py` for local visual-agent evaluation:

- OCR: extract text/fields from images.
- Chart: answer visual/numeric chart questions.
- Screenshot: locate UI elements and return coordinates or structured actions.
- Video: answer short video or sampled-frame questions.
- HITL review: pause after candidate discovery and fixture shortlist generation so the user can review findings and approve the selected OCR/chart/screenshot/VDO test candidates before benchmark execution.
- Runtime control: support fast smoke, standard, and extended modes so the test does not become too slow for routine deploys.

## Why This Shape

The existing agent benchmark already measures the practical loop, not just raw tok/s. A VLM equivalent should do the same:

- Use fixed local fixtures to remove web drift.
- Drive the same model/server API path used by clients.
- Ask the model to produce structured output or call tools, not just free-form answers.
- Score correctness with deterministic checks where possible.
- Capture wall time, per-request LLM time, token usage, image/video payload size, tool calls, and failures.

Public benchmarks such as OCRBench, DocVQA, ChartQA, ScreenSpot, and Video-MME are useful comparators, but they are too large for every deploy. This harness should start with a small local suite and optionally provide hooks for sampled public tasks later.

## Proposed Script

Path: `scripts/bench/bench_vlm_agent_task.py`

Core options:

```bash
python3 scripts/bench/bench_vlm_agent_task.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --suite standard \
  --tasks ocr,chart,screenshot,video \
  --output docs/models/benchmarks/logs/<model-slug>/vlm-agent-task.json
```

Suggested modes:

| Mode | Fixtures | Purpose | Target Time |
|:--|--:|:--|:--|
| `smoke` | 1 per task | Deploy sanity check | < 5 min |
| `standard` | 5 per task | Routine model comparison | 10-20 min |
| `extended` | 10-20 per task | Deeper writeup / candidate promotion | 30-60 min |

Task filters:

- `--tasks ocr`
- `--tasks chart`
- `--tasks screenshot`
- `--tasks video`
- `--tasks all`

Execution controls:

- `--runs N`
- `--warmup N`
- `--timeout S`
- `--max-video-frames N`
- `--image-max-edge PX`
- `--continue-on-fail`
- `--hitl-review` to stop after fixture discovery and emit a candidate report.
- `--approved-fixtures <json>` to run a user-approved shortlist.

## Fixture Workflow

1. Discover candidate fixtures under `bench-fixtures/vlm/` or a new local-only fixture folder if large media should stay untracked.
2. Generate a candidate report:
   - fixture path
   - task family
   - prompt
   - expected answer / bbox / JSON fields
   - estimated payload size
   - estimated runtime bucket
3. HITL checkpoint:
   - ask the user to review the OCR, chart, screenshot, and VDO candidates.
   - allow replacing fixtures before any benchmark run.
4. Save the approved fixture manifest to a deterministic JSON file.
5. Run only approved fixtures in benchmark mode.

## Scoring

Output schema should include both raw model output and normalized scoring.

OCR:

- Structured answer with expected fields.
- Exact field match where possible.
- Character error rate for free text.
- Optional regex checks for dates, totals, IDs.

Chart:

- Exact category/label match.
- Numeric tolerance, default `abs_error <= 0.5` or `rel_error <= 5%`.
- Separate visual lookup from reasoning questions.

Screenshot:

- `click(x, y)` or JSON `{ "target": "...", "x": 123, "y": 456 }`.
- Pass when coordinate lands inside expected bounding box.
- Include miss distance from bbox center for partial diagnostics.

Video:

- First implementation should use sampled frames because it is easier to compare across servers.
- Native video input can be a separate mode when `mlx-vlm` server support is confirmed.
- Score exact multiple-choice answers, event ordering, or timestamp/frame tolerance.

## Tool Surface

For OpenAI-compatible servers, use synthetic tools similar to `bench_api_tool_call.py`:

- `write_result(json)` records final structured answer.
- `click(x, y, reason)` records screenshot grounding.
- `select_answer(choice, reason)` records multiple-choice outputs.

The pass criterion should not be "model wrote something"; it should be "model produced a valid tool call or strict JSON that scored correctly."

## Output

Write raw logs to:

```text
docs/models/benchmarks/logs/<model-slug>/vlm-agent-task.json
```

The JSON should include:

- model/server metadata
- benchmark version
- fixture manifest hash
- per-task correctness
- per-task latency
- tool-call validity
- token usage
- payload sizes
- errors/timeouts
- aggregate pass rates by family

## Refactor / Runtime Guardrails

The script should be factored so slow media tasks do not block routine deploys:

- Keep fixture loading, request building, scoring, and aggregation in separate functions/classes.
- Add per-task timeout defaults; video gets a longer timeout than OCR.
- Add `smoke` as the deploy default.
- Add `standard` as the promotion benchmark.
- Add `extended` only for writeups.
- Downsample video frames by default.
- Resize large images unless the fixture explicitly requires high-resolution OCR.
- Cache base64 payloads during a run to avoid repeated file IO.

## Acceptance Criteria

- `--suite smoke --tasks all` runs against a live OpenAI-compatible VLM server and writes JSON.
- HITL candidate mode emits a readable review report and exits before benchmarking.
- OCR/chart/screenshot/video scoring is deterministic for the initial fixture set.
- Runtime mode selection works and is documented in `scripts/README.md`.
- A failed task records enough raw response detail to debug parser vs model vs server failures.

## Follow-up Docs After Implementation

- Update `scripts/README.md`.
- Add benchmark summary rows only after a real model run.
- If the fixture folder is tracked, add a short fixture README.
- If large media is untracked, document where to place it and what manifest file records.
