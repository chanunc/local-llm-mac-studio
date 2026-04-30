# API-Level Tool-Call Benchmark

Cross-model summary of single-call and multi-turn results from [`scripts/bench/bench_api_tool_call.py`](../../../scripts/bench/bench_api_tool_call.py). Drives the model with a 5-tool fixture (read_file, write_file, run_command, search_web, list_directory) and a 3-turn agentic loop.

For the OpenCode end-to-end agent loop instead, see [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md). For raw decode/prefill throughput, see [`model-benchmark-api-server.md`](model-benchmark-api-server.md).

## Method

- **Single-call scenarios** (5): single tool, multi-tool combos, agentic reasoning. Each issues one POST to `/v1/chat/completions` with `tools=[…]`, `tool_choice="auto"`, `max_tokens=1024`, `temperature=0.0`, `stream=false`. Pass criterion: `finish_reason: "tool_calls"` with at least one well-formed entry in `message.tool_calls[]`.
- **Multi-turn agentic loop** (3 turns): simulates `read_file → write_file → final answer`. Server feeds tool results back via `role: "tool"` messages between turns.
- **Reported numbers**: total wall time, single-call pass rate, per-turn latency for the multi-turn loop.

## Cross-model summary

| Model | Server | Single-call pass | Multi-turn (3 turns, total) | Notes |
|:------|:-------|:-----------------|:----------------------------:|:------|
| Qwen3.6-35B-A3B 4-bit + DFlash drafter | dflash-mlx | **5/5** | **5.9 s** | Tool-call detection driven by `mlx_lm.server` + `mlx_lm.generate.match()`; requires `patch_mlx_lm_match.py` (else `KeyError: None` after first match). Single-call latencies 1.68-6.08 s. Raw: [`api-tool-test-dflash-mlx.json`](qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json) |

(More rows will land here as other servers are re-benched against this harness — historically tool-call benches have been recorded inline in [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md) per-model `### API-Level Tool Calling` subsections.)

## Results: dflash-mlx + mlx-community/Qwen3.6-35B-A3B-4bit + z-lab/Qwen3.6-35B-A3B-DFlash

Tested on **Mac Studio M3 Ultra (96 GB)** — April 30, 2026.

**Server:** dflash-mlx 0.1.4.1 (`pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'`) + three local patches: [`patch_dflash_mlx_serve.py`](../../../scripts/patches/patch_dflash_mlx_serve.py), [`patch_mlx_lm_match.py`](../../../scripts/patches/patch_mlx_lm_match.py), and (only for 0.1.0) [`patch_dflash_mlx_host.py`](../../../scripts/patches/patch_dflash_mlx_host.py). Started with `--host 0.0.0.0 --port 8098 --temp 0.0 --chat-template-args '{"enable_thinking":false}'`. Raw JSON: [`api-tool-test-dflash-mlx.json`](qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json).

### Single-call scenarios (1 tool catalog, 5 prompts)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.84 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.88 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 2.23 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.68 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 6.08 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool calls are well-formed — JSON-encoded `arguments`, correct `function.name`, `type: "function"`, UUID `id`. Reasoning routed to `message.reasoning` (separate from `content`).

### Multi-turn agentic loop (3 turns, total 5.9 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 2.39 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 1.43 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 2.09 | `stop` | — final answer |

The state-machine reset patch (`patch_mlx_lm_match.py`) is what unblocks turn 2 onward — without it, the second invocation of `match()` after a tool-call match terminal hits `KeyError: None`. The fix is `mlx_lm.generate.match()`'s state machine, not dflash-mlx-specific.

### Caveats

- **Greedy only.** `--temp 0.0` is the bench setting. Higher temperature reduces draft acceptance below 86%, eroding DFlash's win.
- **Disable thinking for tool-call benches.** `--chat-template-args '{"enable_thinking":false}'` keeps the model from emitting long `<think>` blocks before each tool call. This is informational — tool-call correctness is unaffected — but it speeds the bench by 2-4× per turn.
- **Server log telemetry** confirms DFlash is active: per-request lines like `122.3 tok/s | 81.2% accepted | 695 tokens` appear in `/tmp/dflash-mlx.log`.

## See also

- [`docs/servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md) — server runbook
- [`model-benchmark-api-server.md`](model-benchmark-api-server.md) — raw decode / prefill throughput for the same target
- [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md) — OpenCode end-to-end agent loop (browse / search scenarios)
- [`qwen36-35b-a3b-4bit/`](qwen36-35b-a3b-4bit/) — all raw JSONs for this target+drafter pair
