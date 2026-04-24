# Benchmark: Agent Tool-Call Latency

Tested on **Mac Studio M3 Ultra (96 GB)**.

## Method

Real agent CLI invocation via `opencode run --format json`, measuring end-to-end response time including agent system prompts, tool definitions, agent loop turns, and reasoning overhead. This captures the actual latency a user experiences — not raw inference tok/s.

Script: [`scripts/bench_agent_tool_call.py`](../../scripts/bench_agent_tool_call.py)
Config switcher: [`scripts/switch_opencode_config.py`](../../scripts/switch_opencode_config.py)

**Why this matters:** Raw benchmarks show 45-85 tok/s for these models. But agent workloads include 2,000-4,000 token system prompts, multiple API round-trips, and reasoning amplification. Measured end-to-end, `opencode run "Hi"` takes 80s vs 2.7s raw curl for the same model — a 30x gap ([analysis](../../docs/clients/opencode-analysis.md)).

---

## Cross-Model Summary

All numbers below are medians; per-model detail sections follow further down.

### API-level tool calling (direct `/v1/chat/completions`, 5-tool harness)

| Model | Server | Pass rate | Single-tool latency | Multi-tool latency | Agentic loop (3-turn `read→write→summary`) |
|:------|:-------|:---------:|:-------------------:|:------------------:|:------------------------------------------:|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | **5/5** | 1.18 - 1.21 s | 1.51 - 1.53 s | **5.64 s** |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | **5/5** | 3.44 - 3.76 s | 4.23 - 8.13 s | 14.84 s |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | n/a (not run) | n/a | n/a | n/a |

### OpenCode end-to-end (`opencode run --format json`, real agent loop)

| Model | Server | Browse github.com (median) | Search 3 latest AI tools (median) | Notes |
|:------|:-------|:-------------------------:|:--------------------------------:|:------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | **42.58 s** | **70.61 s** | 2 / 2 turns; `webfetch`, `task`, `bash`; fastest of the three (sparse 3B-active MoE) |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 88.94 s ⚠ | ⛔ hung | Browse: 2 good runs + 1 300s bash-loop timeout (median of 2). Search: 0 turns on all attempts (model emitted no tool call) — needs diagnosis. See partial results in [qwen36-35b-a3b-jangtq4-crack-agent-bench.json](qwen36-35b-a3b-jangtq4-crack-agent-bench.json). |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 114.25 s | 163.59 s | 2 / 3 turns; `webfetch`, `bash`; dense model — slowest; one 250s browse outlier and one 262s search warmup outlier (9-turn bash loop) |

### Server / parser flag matrix

| Model | Server | `--tool-call-parser` | `--reasoning-parser` | Required patch |
|:------|:-------|:---------------------|:---------------------|:--------------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx | `qwen3_coder` | `qwen3` | `scripts/patch_vllm_mlx_streaming_tools.py` |
| Qwen3.6-27B JANG 4M | vllm-mlx | `qwen3_coder` | `qwen3` | same as above |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | `qwen3` | `qwen3` | `scripts/patch_vmlx_jangtq_mllm_tools.py` |

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
| Browse github.com | 36.54s (2026-04-21) / 42.58s (2026-04-24) | 2 | `webfetch` |
| Search 3 latest AI tools | 59.50s (2026-04-21) / 70.61s (2026-04-24) | 2 | `bash`, `webfetch`, `task` |

Full agentic tool use works end-to-end through OpenCode. The 2026-04-24 re-run used `--print-logs --log-level=INFO` captured per-run to [`qwen35-35b-a3b-jang4k-agent-bench.logs/`](qwen35-35b-a3b-jang4k-agent-bench.logs/); raw JSON in [`qwen35-35b-a3b-jang4k-agent-bench.json`](qwen35-35b-a3b-jang4k-agent-bench.json). The ~15 % increase vs 2026-04-21 mostly reflects higher-token OpenCode system prompts in the newer 1.14.21 client (10.8k-token first-turn prefill vs ~9k earlier).

### Key Findings

1. **Raw inference: ~97-102 tok/s** — fast and consistent for a 3B-active MoE on M3 Ultra.

2. **Tool calling works at API level** — 5/5 pass rate with correct tool selection, valid JSON args, and parallel multi-tool calling. Multi-turn agentic loop completes a 3-step task in 5.6s.

3. **vllm-mlx streaming bug (fixed by patch)** — the streaming path has two mutually exclusive branches: the reasoning parser path (`--reasoning-parser`) and the standard path with tool parsing. When both flags are set, reasoning wins and tool calls are never parsed. The patch (`scripts/patch_vllm_mlx_streaming_tools.py`) integrates tool-call detection into the reasoning path using the generic `parse_tool_calls()` function which handles the Nemotron/XML format (`<function=name><parameter=p>v</parameter>`) that Qwen3.5 MoE uses. Re-apply after `pip install -U vllm-mlx`.

4. **Agentic performance:** Browse task completes in ~37s (2 turns), search task in ~60s (2-4 turns). The model correctly selects appropriate tools and completes multi-step reasoning.

---

## Scenario 1: Browse github.com (Single Tool Call)

Prompt: `"Browse github.com"`

| Model | Server | Response Time (2026-04-24 median) | Turns | Tools | Tokens |
|:------|:-------|:---------------------------------:|:------|:------|:-------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | **42.58 s** | 2 | `webfetch` | 27,528 |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 88.94 s (2 good runs + 1 timeout) | 2-3 | `webfetch`, `bash` | 27,650 |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 114.25 s | 2 | `webfetch` | 27,503 |

---

## Scenario 2: Search 3 Latest AI Agentic Tools (Multi-Step)

Prompt: `"Search 3 latest ai agentic tools on github.com"`

| Model | Server | Response Time (2026-04-24 median) | Turns | Tools | Tokens | Context Growth |
|:------|:-------|:---------------------------------:|:------|:------|:-------|:---------------|
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | **70.61 s** | 2 | `task`, `bash` | 22,743 | ~10K/turn |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | ⛔ hung (0 tool calls on all attempts) | — | — | — | — |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 163.59 s | 3 | `bash`, `webfetch` | 35,063 | ~10K/turn |

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

---

## Results: JANGQ-AI/Qwen3.6-27B-JANG_4M

**Date:** 2026-04-23
**Server:** vllm-mlx v0.2.6 (`run_vllm_jang.py` wrapper) with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.6 dense — 27.3B params, hybrid (48 Gated DeltaNet + 16 full-attention) layers, ViT vision encoder, 4.45 bits/param JANG mixed 4/8-bit, 262K native context (1M YaRN). Loaded as `MLLM=False` (text-only — vllm-mlx does not expose the vision tower).
**Model path:** `~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M` (downloaded via `huggingface_hub.snapshot_download`)

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via `docs/models/qwen36-27b-jang4m-api-tool-test.json`. Direct `/v1/chat/completions` invocation, mirroring the API-level table above.

| Scenario | Time | Output Tokens | Speed | Tools Called | Result |
|:---------|:-----|:--------------|:------|:------------|:-------|
| Single tool (file read) | 3.76s | 65 | 17.3 tok/s | `read_file` | PASS |
| Single tool (command) | 3.44s | 64 | 18.6 tok/s | `run_command` | PASS |
| Multi-tool (search + read) | 8.13s | 228 | 28.0 tok/s | `search_web`, `read_file` | PASS (parallel) |
| Multi-tool (list + read + write) | 4.23s | 89 | 21.1 tok/s | `list_directory` | PASS (chose serial — 1 tool/turn) |
| Agentic reasoning | 13.47s | 421 | 31.3 tok/s | `run_command` | PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, `finish_reason: tool_calls`. Parallel calling demonstrated in scenario 3.

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 4.42s | 97 |
| 2 | `write_file({...port:8080...})` | 5.89s | 144 |
| 3 | Natural language summary (stop) | 4.53s | 85 |
| **Total** | **3 turns, complete task** | **14.84s** | 326 |

For comparison: the same task on `Qwen3.5-35B-A3B JANG 4K` (sparse 3B-active MoE) finished in 5.64s — dense 27B is ~2.6x slower per turn but completes the loop with the same correctness.

### Streaming Tool Calls (direct curl validation)

Verified independently of OpenCode: a streaming `/v1/chat/completions` request with `stream=true` and a `webfetch` tool returns reasoning chunks (sent as `reasoning` + `reasoning_content` deltas) followed by a `tool_calls` delta and `finish_reason: tool_calls`. End-to-end ~5s for the "Browse github.com" prompt with 283 prompt tokens / 83 completion tokens.

### OpenCode End-to-End Agent Benchmark

**Date:** 2026-04-24 (re-run with `--print-logs --log-level=INFO` captured per-run under [`qwen36-27b-jang4m-agent-bench.logs/`](qwen36-27b-jang4m-agent-bench.logs/), after the NordVPN Shield block was cleared by uninstalling the app + rebooting the client MacBook — see history note below).

Captured via `scripts/bench_agent_tool_call.py` (1 warmup + 3 measured per scenario, `-v` enables opencode INFO logs per run). Raw JSON: [`qwen36-27b-jang4m-agent-bench.json`](qwen36-27b-jang4m-agent-bench.json).

| Scenario | Median | p5 – p95 | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:--------:|:-----:|:-----------|:----------------------:|
| Browse github.com | **114.25 s** | 89.4 – 250.7 s | 2 | `webfetch` | 27,503 |
| Search 3 latest AI agentic tools on github.com | **163.59 s** | 162.31 – 265.76 s | 3 | `bash`, `webfetch` | 35,063 |

Per-turn breakdown (browse, representative run): turn 1 prefill=10,791 tokens → 193.1 s (one `webfetch` tool call, routed through the dense 27B with ~80-200 token `<think>` preamble); turn 2 prefill=16,478 → 56.4 s (final text, 233 output tokens). Search variance is high because some runs chose `bash` shell pipelines (gh-style search via curl/grep) and some chose a single `webfetch` — on runs that chain 4+ web fetches or shell steps, wall time pushes toward the 300 s timeout ceiling.

Cross-model comparison on the same scenarios (all captured 2026-04-24 with the same bench script):

| Model | Server | Browse | Search | vs. this model |
|:------|:-------|:------:|:------:|:--------------|
| Qwen3.5-35B-A3B JANG 4K (sparse MoE, 3B active) | vllm-mlx | 42.58 s | 70.61 s | **~2.7× faster** browse, **~2.3× faster** search |
| Qwen3.6-35B-A3B JANGTQ4-CRACK (sparse MoE, 3B active, TurboQuant 4-bit) | vmlx | 88.94 s ⚠ (2 good + 1 timeout) | ⛔ hung (0 tool calls) | search scenario failed on vmlx — separate issue, not a model-quality signal |
| **Qwen3.6-27B JANG 4M (this model, dense 27B)** | vllm-mlx | **114.25 s** | **163.59 s** | baseline |

### History: NordVPN Shield block (resolved 2026-04-24)

The 2026-04-23 bench run timed out at 300 s on every invocation with `turns=0, tools=[]` and OpenCode `FailedToOpenSocket errno=0`. The block recurred on 2026-04-24 after NordVPN auto-upgraded from v9.15.0 → v10.0.4 (the v10 client no longer ships the "App Exceptions" UI). Root cause was the macOS **NordVPN Threat Protection Pro** system extension (`com.nordvpn.macos.Shield`) silently dropping outbound LAN traffic from `node`/`bun` binaries at the socket layer (returns `EHOSTUNREACH` from `connect()` before the packet leaves the host). Bisection matrix:

| From the MacBook (192.168.31.181) | Result |
|----|----|
| `curl` / `python3 urllib` / Docker container → vllm-mlx | ✅ <1 s |
| `node` / `bun` / `pi` / `opencode` → vllm-mlx | ⛔ EHOSTUNREACH / FailedToOpenSocket |

**Fix applied 2026-04-24:** uninstalled the NordVPN app and rebooted the MacBook (macOS does not unload system extensions on app uninstall alone; reboot purges any entry already marked `terminated waiting to uninstall on reboot`). Post-reboot `systemextensionsctl list | grep Shield` shows the v10.0.4 entry as `[activated disabled]` and `node` LAN `connect()` succeeds in ~7 ms. A prior attempt to allowlist binaries in v9.15.0's "App Exceptions" UI worked per-binary-signature but broke on every `brew upgrade` of node/opencode; the v10 client removed the feature so allowlisting is no longer an option. See `project_opencode_vllm_socket_regression.md` memory for the full triage chain.

### Key Findings

1. **API-level tool calling works perfectly** — 5/5 single-call pass + 3-turn loop completes correctly. Streaming `tool_calls` delta is emitted (verified via curl). Same `qwen3_coder` tool parser + `qwen3` reasoning parser as the Qwen3.5 setup.

2. **Dense 27B latency is ~2.7× sparse 3B-active MoE on end-to-end OpenCode** — browse 114.25 s vs 42.58 s for Qwen3.5-35B-A3B JANG 4K; search 163.59 s vs 70.61 s. The inner 3-turn agentic loop (no OpenCode harness) measured 14.84 s vs 5.64 s. Per-turn time is dominated by full-attention prefill of growing context (turns 1-2 prefill 10-17k tokens × 16 full-attention layers).

3. **High single-run variance (89 – 265 s browse, 162 – 266 s search)** — caused by non-deterministic branching in the agent loop. When the model chooses a single `webfetch` the run finishes in ~90 s; when it chooses a `bash` loop of 5-9 shell calls (observed once in browse warmup and one measured run), wall time pushes toward the 300 s timeout. Median is a more robust metric than mean for this model.

4. **Verbose reasoning preamble** — the model emits ~80-200 tokens of `<think>`-equivalent reasoning (routed to `reasoning_content` by the `qwen3` parser) before the tool call, even on simple prompts. This adds ~1-3s of fixed overhead per turn versus a non-thinking equivalent.

5. **Client-config hygiene** — previously the local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` defaulted to `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`, which is not served by the single-model vllm-mlx. Calls without an explicit `--model` returned 404 from the server ("The model … does not exist"). Both local configs were realigned with the repo canonical (`configs/client/vllm-mlx/`) to default to the live 27B model; this must be repeated whenever the vllm-mlx primary model changes.
