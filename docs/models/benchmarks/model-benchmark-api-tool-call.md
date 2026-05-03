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
| Gemma 4 31B-it 6-bit | llmster | **5/5** | 9.8 s | LM Studio runtime handles Gemma 4 tool format; no thinking prelude on this prompt set. Single-call latencies 1.28-3.77 s. Raw: [`api-tool-test-llmster.json`](gemma-4-31b-it-6bit/api-tool-test-llmster.json) |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx | **5/5** | 11.65 s | Native JANGTQ VLM fast path through MLX Studio bundled Python; requires `patch_vmlx_jangtq_mllm_tools.py`. Single-call latencies 2.87-13.14 s. Raw: [`api-tool-test-vmlx.json`](qwen36-35b-a3b-jangtq4-osaurus/api-tool-test-vmlx.json) |
| Qwen3.6-35B-A3B 4-bit + DFlash drafter | dflash-mlx | **5/5** | **5.9 s** | Tool-call detection driven by `mlx_lm.server` + `mlx_lm.generate.match()`; requires `patch_mlx_lm_match.py` (else `KeyError: None` after first match). Single-call latencies 1.68-6.08 s. Raw: [`api-tool-test-dflash-mlx.json`](qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json) |
| DavidAU Qwen3.6-40B Heretic Q6_K IMatrix | llmster | **5/5** | 30.31 s | LM Studio GGUF runtime; no parser flags needed. Dense 40B — single-call latencies 6.39–17.63 s (5–8× slower than MoE siblings). Raw: [`api-tool-test.json`](qwen36-40b-davidau-heretic/api-tool-test.json) |
| DavidAU Gemma 4 31B Heretic Q6_k (Thinking) | llmster | **5/5** | 23.68 s | LM Studio GGUF runtime; Thinking model — `<\|channel>thought` budget adds latency invisible in output tokens. Single-call latencies 2.75–8.48 s. Raw: [`api-tool-test-llmster.json`](gemma4-31b-davidau-heretic/api-tool-test-llmster.json) |
| prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K | llmster | **5/5** | **5.9 s** | LM Studio GGUF runtime; no parser flags needed. Single-call latencies 1.60–5.79 s. Raw: [`api-tool-test.json`](qwen36-35b-a3b-prithiv-aggressive/api-tool-test.json) |

Historically, older tool-call benches were recorded inline in [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md) per-model `### API-Level Tool Calling` subsections. New runs should land here first, then be cross-linked from the OpenCode end-to-end doc.

## Results: Gemma 4 31B-it 6-bit on llmster

Tested on **Mac Studio M3 Ultra (96 GB)** — May 1, 2026.

**Server:** llmster / LM Studio headless on port 1234. Raw JSON: [`api-tool-test-llmster.json`](gemma-4-31b-it-6bit/api-tool-test-llmster.json).

### Single-call scenarios

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 3.77 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.28 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 2.41 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.41 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 2.40 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** The model goes straight to tool calls in this harness with no visible thinking prelude.

### Multi-turn agentic loop (3 turns, total 9.8 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 2.86 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 4.02 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 2.92 | `stop` | — final answer |

### Caveats

- The "multi-tool list + read + write" prompt emits only `list_directory` on the first turn. This is still a valid pass for the one-response API harness, but a real client would continue the loop after receiving the directory listing.
- Gemma 4 31B-it is opt-in in the llmster config; the default llmster OpenCode template remains Qwen3.6-27B unless explicitly switched.

## Results: OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 on vmlx

Tested on **Mac Studio M3 Ultra (96 GB)** — May 1, 2026.

**Server:** vmlx via MLX Studio bundled Python on port 8000, launched with `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3`. Raw JSON: [`api-tool-test-vmlx.json`](qwen36-35b-a3b-jangtq4-osaurus/api-tool-test-vmlx.json).

### Single-call scenarios

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 3.28 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 13.14 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 3.84 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 2.87 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 12.08 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool calls are well-formed through vmlx's qwen3 parser once the MLLM tool-template patch is applied.

### Multi-turn agentic loop (3 turns, total 11.65 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 3.02 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 4.39 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 4.24 | `stop` | — final answer |

### Caveats

- Requires MLX Studio bundled Python; public `jang-tools` does not ship `load_jangtq_vlm` or the TurboQuant Metal kernels.
- Requires [`patch_vmlx_jangtq_mllm_tools.py`](../../../scripts/patches/patch_vmlx_jangtq_mllm_tools.py) so the OpenAI `tools[]` array reaches the MLLM chat template.
- Simple chat can emit natural-language thinking in `content`, but this API tool harness and the OpenCode benchmark both produced structured tool calls correctly.

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

## Results: prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K on llmster

Tested on **Mac Studio M3 Ultra (96 GB)** — May 2, 2026.

**Server:** llmster / LM Studio headless on port 1234, GGUF runtime. Loaded with `--identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --context-length 65536`. Raw JSON: [`api-tool-test.json`](qwen36-35b-a3b-prithiv-aggressive/api-tool-test.json).

### Single-call scenarios

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.79 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.98 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 4.27 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.60 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 5.79 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool arguments are well-formed JSON; model emits `run_command` with a `find | sort | head` pipeline for the agentic scenario. LM Studio handles the Qwen3 chat-template tool-call format natively — no `--tool-call-parser` flag required.

### Multi-turn agentic loop (3 turns, total 5.87 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.67 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 2.44 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.77 | `stop` | — final answer |

### Caveats

- LM Studio's GGUF runtime handles `<think>` and tool calls natively for this Qwen3 GGUF — no parser flags at load time.
- Model key collision: `lms load qwen3.6-35b-a3b-uncensored-aggressive` matches both prithivMLmods and HauhauCS models; use `--identifier` to pin the stable API id, and `-y` to select non-interactively (picks first alphabetically, which is the prithivMLmods model).

## Results: DavidAU Qwen3.6-40B Heretic Q6_K IMatrix on llmster

Tested on **Mac Studio M3 Ultra (96 GB)** — May 3, 2026.

**Server:** llmster / LM Studio headless on port 1234, GGUF runtime. Loaded with `--identifier qwen36-40b-davidau-heretic-q6k --context-length 131072`. Raw JSON: [`api-tool-test.json`](qwen36-40b-davidau-heretic/api-tool-test.json).

### Single-call scenarios

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 7.47 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 6.39 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 17.63 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 7.74 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 15.90 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool calls are well-formed across all scenarios. Dense 40B at 8.8–9.7 tok/s: single-call latencies are 5–8× slower than MoE siblings (prithivMLmods 1.60–5.79 s vs 6.39–17.63 s). LM Studio handles Qwen3 tool-call format natively — no parser flags required.

### Multi-turn agentic loop (3 turns, total 30.31 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 10.35 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 11.88 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 8.08 | `stop` | — final answer |

### Caveats

- Dense 40B at 8.8–9.7 tok/s is expected. Reload prithivMLmods Aggressive Q6_K (`lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --context-length 65536 -y`) when throughput matters.
- LM Studio memory guardrail must be set to `"off"` before loading this model (dense 40B + 131K context) — see `docs/current.md` launch shape for the full toggle recipe.
- Thinking mode is on by default; the model produces `<think>` reasoning before each tool call, contributing to latency but not blocking tool-call correctness.

## See also

- [`docs/servers/dflash-mlx/summary.md`](../../servers/dflash-mlx/summary.md) — server runbook
- [`model-benchmark-api-server.md`](model-benchmark-api-server.md) — raw decode / prefill throughput for the same target
- [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md) — OpenCode end-to-end agent loop (browse / search scenarios)
- [`qwen36-35b-a3b-4bit/`](qwen36-35b-a3b-4bit/) — all raw JSONs for this target+drafter pair
