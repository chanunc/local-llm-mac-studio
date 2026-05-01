# Plan: Diagnose and fix DFlash regression on Mac Studio M3 Ultra

Status: active
Created: 2026-05-01
Canonical: no

## Context

Standalone `dflash-benchmark` runs on the Mac Studio M3 Ultra do not reproduce the upstream `bstnxbt/dflash-mlx` Qwen3.6-35B-A3B-4bit claim. Upstream reports `133.20 -> 177.45 tok/s` at 8192 output tokens on M5 Max with `87.01%` acceptance. Local M3 Ultra runs show default DFlash below baseline at 1k-8k output horizons, with worst case `0.62x` at 4096 tokens and only `1.05x` at 8192 when `--quantize-draft` is enabled.

External reports point to several likely causes:

- DFlash only wins when draft acceptance is high enough to amortize draft + verify overhead.
- Open-ended prose prompts can regress, while deterministic code/math/structured prompts do better.
- Quantized targets can make the bf16 draft model the bottleneck on Apple unified memory.
- Thinking-mode and chat-template mismatches can collapse acceptance.
- Qwen3.6 DFlash drafters add sliding-window attention behavior that may be more fragile than Qwen3.5 drafters.
- Long context and long generation remain active optimization areas upstream.

The current operational posture is conservative: keep `dflash-mlx` as an upstream-feature-tracking sidecar, not a throughput default, until this plan identifies a safe enablement profile.

## Goal

Find whether the regression is caused by benchmarking mismatch, prompt/task mix, runtime configuration, model/draft pairing, MLX version, hardware behavior, or a real `dflash-mlx` limitation on M3 Ultra. Produce one of these outcomes:

1. A validated DFlash configuration that beats plain `mlx_lm` for a specific workload class.
2. A gating rule that enables DFlash only when acceptance is high enough.
3. A documented upstream issue with a minimal reproducer and local fallback recommendation.

## Non-goals

- No production promotion of `dflash-mlx` unless benchmark evidence changes materially.
- No replacement of the Ling primary on `vllm-mlx:8000`.
- No broad client config expansion for `dflash-mlx`; it remains provisional.
- No custom drafter training in this pass.

## Phase 1 - Reproduce upstream exactly

Run from the Mac Studio `~/dflash-mlx-env/` with the same methodology as upstream:

```bash
PROMPT='The function $f$ satisfies the functional equation \[ f(x) + f(y) = f(x + y) - xy - 1 \] for all real numbers $x$ and $y$. If $f(1) = 1$, then find all integers $n$ such that $f(n) = n$. Enter all such integers, separated by commas. Please reason step by step, and put your final answer within \boxed{}.'

~/dflash-mlx-env/bin/dflash-benchmark \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft z-lab/Qwen3.6-35B-A3B-DFlash \
  --prompt "$PROMPT" \
  --max-tokens 8192 \
  --repeat 3 \
  --cooldown 60 \
  --no-eos
```

Capture:

- Exact `dflash-mlx` git commit or package version.
- `mlx`, `mlx-lm`, Python, macOS, and Metal driver versions.
- Baseline t/s, DFlash t/s, speedup, acceptance ratio, tokens/cycle, first/last-20-cycle acceptance.
- Whether the prompt produces a repeated tail that inflates late acceptance.

Save raw JSON as:

```text
docs/models/benchmarks/qwen36-35b-a3b-4bit/standalone-dflash-upstream-prompt-m3ultra.json
```

## Phase 2 - Prompt and workload sweep

Run the same model/draft pair across representative prompt classes:

| Class | Purpose |
|:--|:--|
| Upstream math | Checks benchmark comparability |
| Code generation | Likely high acceptance, production-relevant |
| Structured JSON/list | Tests constrained decoding |
| Agent tool-style answer | Tests OpenCode-like distribution |
| Open-ended prose essay | Current local regression case |
| Random/creative prose | Expected worst case |

For each class, run `1024`, `2048`, `4096`, and `8192` output horizons with `repeat=3` and `cooldown=60`.

Save one JSON per class under:

```text
docs/models/benchmarks/qwen36-35b-a3b-4bit/standalone-dflash-sweep-<class>.json
```

Decision rule:

- If speedup is `>= 1.15x` and acceptance is stable on code/structured prompts, DFlash can be documented as workload-gated.
- If only open-ended prose regresses, keep it disabled for prose but allow task-specific manual use.
- If all classes regress, treat this as M3 Ultra/backend-specific and file upstream.

## Phase 3 - Template and thinking-mode sweep

Run the best and worst prompt classes with these template settings:

- Chat template default.
- `enable_thinking=true`.
- `enable_thinking=false`.
- Raw prompt without chat template, if the CLI supports it.

Reason: external reports show thinking-mode mismatch can change acceptance from speedup to severe regression. Qwen3.6-specific DFlash notes also warn that think-wrapped distributions can collapse acceptance depending on the drafter.

Record:

- Acceptance ratio.
- Average accepted tokens per cycle.
- Visible `<think>` behavior.
- Whether tool/structured outputs require `enable_thinking=false`.

## Phase 4 - Runtime and version sweep

Compare the current local stack to upstream's stated stack.

Matrix:

| Variable | Values |
|:--|:--|
| MLX | current local, upstream `0.31.1` if feasible |
| `dflash-mlx` | current main, latest main |
| Draft quant | bf16/default, `--quantize-draft` |
| Verify linear kernel | default, `DFLASH_VERIFY_LINEAR=0`, `DFLASH_VERIFY_LINEAR=1` |
| Output length | 1024, 4096, 8192 |

Do not churn the production venv blindly. Use a separate throwaway venv if downgrading MLX or changing package versions.

## Phase 5 - Server-path validation

If standalone DFlash finds a winning profile, validate the same profile through `dflash-serve` on port `8098`.

Run:

- `scripts/bench/bench_api_server.py` against `dflash-mlx`.
- `scripts/bench/bench_api_tool_call.py` for tool parsing.
- A short OpenCode run only if API tool calling works.

Compare against:

- Plain `mlx_lm.server`, if available.
- `llmster` Qwen/Gemma baselines for agent-loop relevance.

## Phase 6 - Upstream issue package

If the regression remains unexplained, file a concise upstream issue with:

- Hardware and software versions.
- Exact model and draft IDs.
- Exact prompts and commands.
- JSON summaries for upstream prompt and local prose prompt.
- Acceptance-per-cycle evidence showing where acceptance collapses or late repetition inflates throughput.
- Comparison to upstream M5 Max README numbers.

Link the issue from:

- `docs/models/techniques/model-technique-dflash.md`
- `docs/servers/dflash-mlx/summary.md`
- `docs/models/per-model/model-summary-qwen-3-6.md`

## Documentation updates

After each benchmark batch:

- Add raw JSON files under `docs/models/benchmarks/qwen36-35b-a3b-4bit/`.
- Update `docs/models/benchmarks/model-benchmark-standalone.md`.
- Update `docs/models/techniques/model-technique-dflash.md` with the current root-cause table.
- Update `docs/current.md` only if operational posture changes.

## Verification

- All new JSON parses with `jq empty`.
- `model-benchmark-standalone.md` links every raw JSON.
- `docs/models/techniques/model-technique-dflash.md` states whether DFlash is disabled, gated, or recommended for each workload class.
- Ling on `vllm-mlx:8000` remains untouched throughout.
