# Benchmark: Agent Tool-Call Latency

Tested on **Mac Studio M3 Ultra (96 GB)**.

## Method

Real agent CLI invocation via `opencode run --format json`, measuring end-to-end response time including agent system prompts, tool definitions, agent loop turns, and reasoning overhead. This captures the actual latency a user experiences — not raw inference tok/s.

Script: [`scripts/bench_agent_tool_call.py`](../../scripts/bench_agent_tool_call.py)
Config switcher: [`scripts/switch_opencode_config.py`](../../scripts/switch_opencode_config.py)

**Why this matters:** Raw benchmarks show 45-85 tok/s for these models. But agent workloads include 2,000-4,000 token system prompts, multiple API round-trips, and reasoning amplification. Measured end-to-end, `opencode run "Hi"` takes 80s vs 2.7s raw curl for the same model — a 30x gap ([analysis](../../docs/clients/opencode-analysis.md)).

---

## Results: JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K

**Date:** 2026-04-21
**Server:** vllm-mlx with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.5 MoE — 35B total, 3B active (256 experts, 8/tok), 262K context

### Typical Inference (3 runs each, median)

| Scenario | Time | Output Tokens | Speed |
|:---------|:-----|:-------------|:------|
| Short Q&A | 2.23s | 216 | 96.6 tok/s |
| Code generation | 4.43s | 442 | 99.5 tok/s |
| Reasoning | 9.53s | 968 | 101.5 tok/s |
| Long output (2K tok) | 20.12s | 2,048 | 101.8 tok/s |

Thinking tokens (`<think>` block) included in output count. Model always generates reasoning preamble.

### API-Level Tool Calling (non-streaming, 5 tools available)

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:------------|:-------|
| Single tool (file read) | 1.21s | 54 | 44.6 tok/s | `read_file` | PASS |
| Single tool (command) | 1.18s | 81 | 68.6 tok/s | `run_command` | PASS |
| Multi-tool (search + read) | 1.51s | 115 | 76.1 tok/s | `search_web`, `read_file` | PASS |
| Multi-tool (list + read + write) | 1.53s | 117 | 76.2 tok/s | `list_directory`, `read_file` | PASS |
| Agentic reasoning | 1.29s | 92 | 71.3 tok/s | `list_directory` | PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, proper `finish_reason: tool_calls`.
Parallel tool calling works (multi-tool scenarios call 2+ tools in single response).

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read config, fix port to 8080, write back"

| Turn | Action | Time |
|:-----|:-------|:-----|
| 1 | `read_file("/tmp/app/config.json")` | 1.34s |
| 2 | `write_file(…, {"host":"0.0.0.0","port":8080,"debug":true})` | 2.04s |
| 3 | Natural language summary (stop) | 2.26s |
| **Total** | **3 turns, complete task** | **5.64s** |

### OpenCode Agent Benchmark (streaming via `opencode run`)

**Before patch** (unpatched vllm-mlx):

| Scenario | Response Time (median) | Turns | Tools Called |
|:---------|:----------------------|:------|:------------|
| Browse github.com | 24.69s | 1 | (none) |
| Search 3 latest AI tools | 49.32s | 1 | (none) |

Unpatched result: BLOCKED — vllm-mlx streaming path with `--reasoning-parser` bypasses tool-call parsing entirely. The `<tool_call>` XML leaks into `content` as plain text.

**After patch** (`scripts/patch_vllm_mlx_streaming_tools.py`):

| Scenario | Response Time (median) | Turns | Tools Called |
|:---------|:----------------------|:------|:------------|
| Browse github.com | 36.54s | 2 | `webfetch` |
| Search 3 latest AI tools | 59.50s | 2-4 | `bash`, `webfetch` |

Full agentic tool use works end-to-end through OpenCode.

### Key Findings

1. **Raw inference: ~97-102 tok/s** — fast and consistent for a 3B-active MoE on M3 Ultra.

2. **Tool calling works at API level** — 5/5 pass rate with correct tool selection, valid JSON args, and parallel multi-tool calling. Multi-turn agentic loop completes a 3-step task in 5.6s.

3. **vllm-mlx streaming bug (fixed by patch)** — the streaming path has two mutually exclusive branches: the reasoning parser path (`--reasoning-parser`) and the standard path with tool parsing. When both flags are set, reasoning wins and tool calls are never parsed. The patch (`scripts/patch_vllm_mlx_streaming_tools.py`) integrates tool-call detection into the reasoning path using the generic `parse_tool_calls()` function which handles the Nemotron/XML format (`<function=name><parameter=p>v</parameter>`) that Qwen3.5 MoE uses. Re-apply after `pip install -U vllm-mlx`.

4. **Agentic performance:** Browse task completes in ~37s (2 turns), search task in ~60s (2-4 turns). The model correctly selects appropriate tools and completes multi-step reasoning.

---

## Scenario 1: Browse github.com (Single Tool Call)

Prompt: `"Browse github.com"`

| Model | Server | Response Time | Turns | Tools | Tokens |
|:------|:-------|:-------------|:------|:------|:-------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 36.54s (median) | 2 | `webfetch` | 26,669 |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 93.63s (median) | 2 | `webfetch` | 26,750 |

---

## Scenario 2: Search 3 Latest AI Agentic Tools (Multi-Step)

Prompt: `"Search 3 latest ai agentic tools on github.com"`

| Model | Server | Response Time | Turns | Tools | Tokens | Context Growth |
|:------|:-------|:-------------|:------|:------|:-------|:---------------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 59.50s (median) | 2-4 | `bash`, `webfetch` | 32,032 | ~10K/turn |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 91.22s (median) | 2-3 | `bash`, `webfetch` | 26,411 | ~10K/turn |

---

## Results: dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK

**Date:** 2026-04-21
**Server:** vmlx (MLX Studio v1.3.65 bundled Python) with `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3`
**Architecture:** Qwen3.6 MoE+VL — 35B total, 3B active, 4-bit TurboQuant (JANGTQ4), CRACK abliterated, 262K context
**Model path:** `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` via HuggingFace cache

### OpenCode Agent Benchmark (streaming via `opencode run`)

| Scenario | Response Time (median) | Range (p5-p95) | Turns | Tools Called | Tokens | Errors |
|:---------|:----------------------|:----------------|:------|:------------|:-------|:-------|
| Browse github.com | 93.63s | 93.09 - 96.54s | 2 | `webfetch` | 26,750 | 0 |
| Search 3 latest AI tools | 91.22s | 89.04 - 124.71s | 2-3 | `bash`, `webfetch` | 26,411 | 0 |

### Per-Turn Breakdown (browse, sample run)

| Turn | Duration | Input Tokens | Output Tokens |
|:-----|:---------|:-------------|:-------------|
| 1 | 42.23s | 10,352 | 65 |
| 2 | 49.68s | 16,039 | 335 |

### Per-Turn Breakdown (search, 3-turn run)

| Turn | Duration | Input Tokens | Output Tokens |
|:-----|:---------|:-------------|:-------------|
| 1 | 51.62s | 10,641 | 254 |
| 2 | 34.94s | 11,138 | 244 |
| 3 | 36.95s | 11,633 | 303 |

### Key Findings

1. **Tool calling works reliably** — 0 errors across 6 measured runs. The MLLM tools patch (`scripts/patch_vmlx_jangtq_mllm_tools.py`) is required for vmlx to forward tool definitions to the model.

2. **Reasoning tokens: 0** — despite `--reasoning-parser qwen3`, the model did not emit `<think>` blocks in these short agentic tasks. This may be task-dependent.

3. **2.5x slower than JANG 4K on vllm-mlx** — browse 93.63s vs 36.54s, search 91.22s vs 59.50s. The gap is likely a combination of the vmlx MLLM code path overhead and TurboQuant inference vs standard JANG format.

4. **Consistent browse, variable search** — browse stddev 1.86s (tight), search stddev 19.99s (one run took 3 turns / 124.71s instead of the usual 2).
