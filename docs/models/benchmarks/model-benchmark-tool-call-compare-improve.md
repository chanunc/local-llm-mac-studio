# Tool-Call Benchmark — Comparison vs. Public Suites + Improvement Plan

Side-by-side review of this repo's two tool-call harnesses ([`scripts/bench/bench_api_tool_call.py`](../../../scripts/bench/bench_api_tool_call.py), [`scripts/bench/bench_agent_tool_call.py`](../../../scripts/bench/bench_agent_tool_call.py)) against the public function-calling / agent benchmarks shipped on HuggingFace and GitHub, with a prioritised list of upgrades and the evaluation gain each unlocks for this lab.

## Overview

- **What we measure today** — single-call + 3-turn multi-turn API harness, plus a 2-prompt OpenCode-driven agent harness; scoring is "tool was called / didn't time out", with rich latency stats.
- **Public benchmarks surveyed** — BFCL v3/v4, NexusRaven, ToolBench / StableToolBench, API-Bank, MetaTool, T-Eval, ToolEyes, τ-bench, AgentBench, GAIA, MCP-Bench / MCP-Universe (SWE-bench listed as adjacent comparator).
- **Side-by-side comparison table** — axis-by-axis: tool count, scenario count, scoring style, execution mode, arg-correctness check, negative tests, user simulation, repeat-pass stability, perf metrics.
- **Where this lab's harness already wins** — first-class latency metrics (median/p5/p95), full client-stack coverage, server-portable across OpenAI-compatible endpoints.
- **Where it lags** — no arg-correctness check, no negative/relevance test, no parallel-call scenario, no `Pass^k`, simulated tools without end-state diffing, no per-category scoring.
- **Improvement options ranked by ROI** — seven additions stolen from BFCL / τ-bench / StableToolBench, each with the new evaluation it unlocks for this lab.
- **Recommendation** — adopt arg-AST scoring + a relevance/negative scenario first; ~50 LoC total, biggest gain in what the benchmark table actually means.

## What this lab measures today

**[`bench_api_tool_call.py`](../../../scripts/bench/bench_api_tool_call.py)** — 5 single-call scenarios + a 3-turn `read → write → summary` loop against `/v1/chat/completions`. Scoring is `finish_reason == "tool_calls"` plus presence of the expected entry in `tool_calls[].function.name`. The 5 declared tools (`read_file`, `write_file`, `run_command`, `search_web`, `list_directory`) are **not executed** — turns 2 and 3 use simulated tool results.

**[`bench_agent_tool_call.py`](../../../scripts/bench/bench_agent_tool_call.py)** — 2 prompts (`"Browse www.example.com"`, `"Browse Hackernews, get the only one latest topic"`) driven through real `opencode run --format json`. Captures wall time, LLM time (sum of per-turn assistant durations), turns, tool names, tokens, per-turn detail. No correctness scoring — a pass means "didn't time out, no error event". 1 warmup + 3 measured runs, results aggregated as median / p5 / p95.

## Public benchmarks surveyed

| Benchmark | Repo | What it measures | Scoring |
|---|---|---|---|
| **BFCL v3 / v4** | [ShishirPatil/gorilla](https://github.com/ShishirPatil/gorilla) | Single, parallel, multiple, relevance, multi-turn, multi-step calls; Py/Java/JS/REST | AST match + executable subset + multi-turn state |
| **NexusRaven V2** | [nexusflowai/NexusRaven-V2](https://github.com/nexusflowai/NexusRaven-V2) | Zero-shot single / parallel / nested calls on held-out APIs | Static exact-call accuracy |
| **ToolBench / ToolLLM** | [OpenBMB/ToolBench](https://github.com/OpenBMB/ToolBench) | Open-domain RapidAPI tool use, retrieval + multi-tool plans | LLM-judge (Pass Rate + Win Rate); live RapidAPI |
| **StableToolBench** | [THUNLP-MT/StableToolBench](https://github.com/THUNLP-MT/StableToolBench) | Reproducible variant of ToolBench | LLM-judge (SoPR / SoWR / FAC); simulated API server (MirrorAPI) |
| **API-Bank** | [AlibabaResearch/DAMO-ConvAI/api-bank](https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/api-bank) | Plan / retrieve / call, 3 difficulty tiers | Exact-match + executable + LLM-judge |
| **MetaTool** | [HowieHwong/MetaTool](https://github.com/HowieHwong/MetaTool) | Tool-use *awareness* and selection (not execution) | Static classification accuracy |
| **T-Eval** | [open-compass/T-Eval](https://github.com/open-compass/T-Eval) | 6-axis decomposition (plan/reason/retrieve/understand/instruct/review) | Per-dimension rubric, rule-based + match |
| **ToolEyes** | [Junjie-Ye/ToolEyes](https://github.com/Junjie-Ye/ToolEyes) | 7 real-world scenarios × 5 capability dimensions | Multi-dimension scoring |
| **τ-bench / τ³-bench** | [sierra-research/tau-bench](https://github.com/sierra-research/tau-bench) | Multi-turn agent vs. LLM-simulated user under domain policies | End-state DB match + `Pass^k` for stability |
| **AgentBench** | [THUDM/AgentBench](https://github.com/THUDM/AgentBench) | 8 environments (OS, DB, KG, ALFWorld, WebShop, Mind2Web, …) | Per-env success rate; live Dockerized envs |
| **GAIA** | [gaia-benchmark/GAIA](https://huggingface.co/gaia-benchmark) | General-assistant reasoning + tool use (web, files, multimodal) | Exact-match final answer |
| **MCP-Bench / MCPAgentBench** | [arxiv 2508.20453](https://arxiv.org/abs/2508.20453), [arxiv 2512.24565](https://arxiv.org/pdf/2512.24565) | Tool-using agents over real MCP servers; parallel-call efficiency | Task success + rubric / LLM-judge; live MCP |
| **SWE-bench** *(comparator)* | [princeton-nlp/SWE-bench](https://github.com/princeton-nlp/SWE-bench) | Real GitHub-issue code-agent fixes | Unit-test pass; live Docker repo eval |

Scoring-style summary:
- **Static AST / exact match** — BFCL non-exec, NexusRaven, MetaTool, T-Eval, ToolEyes, GAIA (answer-level)
- **Live executable, end-state graded** — τ-bench, AgentBench, SWE-bench, MCP-Bench, API-Bank exec subset, BFCL v4 multi-turn
- **LLM-judge** — ToolBench, StableToolBench, API-Bank judge mode

## Side-by-side comparison

| Axis | This lab | BFCL v4 | τ-bench | ToolBench / Stable | API-Bank | T-Eval |
|---|---|---|---|---|---|---|
| Tool count | 5 hand-written | 1,000+ APIs across 4 langs | ~20 domain APIs (retail/airline) | 16k+ RapidAPI | 73 runnable APIs | static |
| Scenarios | 5 single + 1 multi-turn (+2 agent) | ~2k Q-fn-A pairs | hundreds of policy-bound dialogs | 126k instructions | 314 dialogs / 753 calls | 6 capability axes |
| Scoring | `finish_reason` + name match | AST + executable subset + multi-turn state | end-state DB equality, `Pass^k` | LLM-judge (SoPR / SoWR) | exact-match + exec + judge | per-dimension rubric |
| Tool execution | simulated (hard-coded results) | partial sandbox | **live** | live (flaky) / simulated (Stable) | live | none |
| Arg correctness | not checked | AST-checked | end-state-checked | judged | exact-match | matched |
| Categories tested | single, multi-tool sequencing | single / parallel / multiple / relevance / multi-turn / multi-step | policy adherence, long-horizon | retrieval + planning | plan / retrieve / call | 6 axes |
| Negative tests | none | "relevance" category (no-call-needed) | yes (refuse off-policy) | weakly | yes | no |
| User simulator | none | none | LLM-simulated user | none | none | none |
| Repeat-pass stability | runs×3, median/p5/p95 | single | **`Pass^k`** by design | none | none | none |
| Perf metrics | wall, LLM time, turns, tokens, tps | not perf-focused | not perf-focused | not perf-focused | not perf-focused | not perf-focused |

## Where this harness already wins

1. **Latency is a first-class output** — median / p5 / p95 wall + LLM-only time, tokens/s, per-turn duration. Public benchmarks are correctness-focused; perf is incidental. Without this we couldn't have caught the Gemma 4 MTP streaming SSE bug or the OpenCode 1.14.50 PWD double-bootstrap regression.
2. **Exercises the full client stack** — `opencode run` → SSE → server → parser. BFCL / Nexus / T-Eval test the model in isolation and miss real-world bugs at the wire-format boundary.
3. **Server-portable** — works against any OpenAI-compatible endpoint (vllm-mlx, oMLX, vmlx, llama-cpp-mtp, ds4) with one CLI flag. BFCL needs per-model adapters.

## Where it lags — improvement options, prioritised

### 1 · Add argument-correctness check *(biggest gap)*

`bench_api_tool_call.py` logs `tool_args` but never asserts they're right. A model that calls `read_file({"path":"/etc/passwd"})` on the "read /tmp/notes.txt" prompt currently passes.

- **Steal from**: BFCL AST/JSON match against expected args per scenario.
- **Cost**: ~30 LoC; add `expected_args` to each `SINGLE_SCENARIOS` entry and a JSON-subset matcher.
- **Catches**: quant-induced arg drift (Q2/Q3 corruption, IQ2_XXS hallucinations); explains why DeepSeek-V4-Flash Q2 can win on call-emission but degrade downstream. Would have surfaced the GLM-5.1-DA misbehaviour earlier.

### 2 · Add a negative / relevance scenario

Every current scenario expects a tool call. A model that always tool-calls (over-triggering) gets 5/5.

- **Steal from**: BFCL "relevance" category.
- **Cost**: 1–2 scenarios where the right answer is plain text (e.g. `"What's 2+2?"` with full tool set declared).
- **Catches**: over-triggering in abliterated / uncensored fine-tunes (HauhauCS, Hermes, magnum) where refusal-to-call has been ablated alongside refusal-to-answer.

### 3 · Add a parallel-tool-call scenario

BFCL v3 + MCP-Bench both score parallel calls; relevant for Qwen3.6 / Gemma 4 which advertise `parallel_tool_calls`. Today nothing in the harness distinguishes single-emit serial models from native-parallel ones.

- **Steal from**: BFCL "parallel" category.
- **Cost**: 1 scenario expecting ≥2 calls in a single assistant message (`"read /tmp/a.txt AND /tmp/b.txt"`).
- **Catches**: real parallel-emit MoE wins vs. serial fakes — directly relevant to MoE bench comparisons.

### 4 · Report `Pass^k` stability

The harness already runs 3× but reports median, not pass-consistency.

- **Steal from**: τ-bench `Pass^k` ("all k runs passed identically").
- **Cost**: free — same data, new aggregate (`pass_at_3 = all(r.tool_calls == expected for r in runs)`).
- **Catches**: format flakes (raw XML leak, wrong parser branch) that median papers over. Distinguishes "consistently 3/3" from "median-fast, p95-timeout".

### 5 · Route web-fetch through a captured fixture

`bench_agent_tool_call.py` hits the live web (Hackernews). Great for OpenCode-loop testing, bad for reproducibility — the HN front page changes and a tool failure can't be attributed to the model.

- **Steal from**: StableToolBench's MirrorAPI / cache strategy.
- **Cost**: small local HTTP fixture + an env var to redirect `webfetch`.
- **Catches**: makes the HN scenario actually reproducible; isolates LAN / upstream blips from model regressions. Keep the live variant for "real-world feel" runs.

### 6 · Multi-turn end-state diff

The 3-turn loop checks `finish_reason` per turn but doesn't verify the synthesised config contents.

- **Steal from**: τ-bench end-state DB equality.
- **Cost**: snapshot `/tmp/agent-bench/` after each run, diff against expected JSON.
- **Catches**: "model did the right tool calls but with wrong content" — a class of bug single-call AST scoring misses. Pinpoints client-parser bugs (qwen3 vs qwen3_coder vs hermes) vs. true model errors.

### 7 · Tag scenarios with categories

BFCL / T-Eval slice scores by category; this harness collapses to one wall-time.

- **Steal from**: BFCL `category` field.
- **Cost**: add `category: ["single","multi","parallel","negative","multi-turn"]` to each scenario; emit per-category columns in `model-benchmark-tool-call.md`.
- **Catches**: per-axis regressions instead of one blended "got slower" delta.

## Evaluation gain summary

| Add | New evaluation gain |
|---|---|
| Arg-AST check | Detect quant-induced arg drift in Q2/Q3/IQ2_XXS variants |
| Relevance category | Validate abliterated / uncensored fine-tunes haven't broken refusal-to-call |
| Parallel-call scenario | Separate true MTP / parallel-emit MoE wins from serial fakes |
| `Pass^k` | Catch "median fast, p95 timeout" flakes (Gemma 4 MTP pre-fix class) |
| Captured-fixture webfetch | Reproducible HN scenario; isolate LAN / upstream blips |
| End-state diff | Pinpoint client-parser bugs vs. model errors |
| Category tags | Per-axis columns in benchmark table instead of one blended number |

## Recommendation

Adopt **(1) arg-AST scoring** and **(2) a relevance / negative scenario** first. Combined they're ~50 LoC, change no infrastructure, and immediately upgrade what the benchmark table actually means — moving from *"did it tool-call?"* to *"did it tool-call correctly, and did it know when not to?"*. That is the same step BFCL v2 → v3 took, and it's the change that made BFCL the canonical leaderboard.

The remaining five upgrades (parallel scenario, `Pass^k`, captured fixture, end-state diff, category tags) compose cleanly on top and can be landed individually as separate PRs.
