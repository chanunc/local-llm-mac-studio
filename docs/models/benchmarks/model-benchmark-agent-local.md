# Agent Benchmark: In-Process (llama-agent, no API server)

Cross-model summary of the **resident in-process agent loop** using [`scripts/bench/bench_agent_local.py`](../../../scripts/bench/bench_agent_local.py). Drives [`gary149/llama-agent`](https://github.com/gary149/llama-agent) — a fork of `ggml-org/llama.cpp` that adds an agent loop in `tools/agent/` — directly over a PTY. There is **no OpenAI-compatible server** between the harness and the model: inference and the agent loop run in the same process.

For the API-level synthetic harness and the OpenCode end-to-end agent loop (HTTP-mediated), see [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md) — both methodologies live in that merged doc as of commit `68c0bfd`.
For raw decode/prefill throughput, see [`model-benchmark-api-server.md`](model-benchmark-api-server.md).

## Why this benchmark exists

`bench_api_tool_call.py` *simulates* tool execution — when the model emits a `tool_calls` response, the harness feeds back hardcoded JSON results without actually executing anything. That is fine for measuring whether the model emits well-formed tool calls, but it does not measure:

- whether the model picks **correct** arguments for a tool given a real filesystem,
- whether multi-turn loops converge to a real post-condition (e.g. "config.json now has port=8080"),
- the model's **steady-state generation rate** when freed of HTTP serialization, OpenAI protocol parsing, and the server's chat-template layer.

This harness fixes those by running tools for real against a sandbox and reading the model's own `/stats` for per-turn tokens + gen rate.

## Method

- **Harness**: pre-built `llama-agent` binary (build b9121, `gary149/llama-agent` releases). The brew formula at b9121 fails to link (duplicate `stb_image` symbols); use the GitHub Releases tarball.
- **Mode**: resident PTY. The model loads once; each scenario runs as a turn in the same TUI session, with `/clear` between scenarios to wipe context. `/stats` captures per-turn token counts and avg gen tok/s.
- **Tools available**: `bash`, `read`, `write`, `edit`, `glob`, `update_plan`. (No `search_web` — different surface from `bench_api_tool_call.py`'s OpenAI-style stubs.)
- **Sandbox**: `realpath("/tmp/bench-llama-agent")` so `/private/tmp/...` matches both prompts and the agent's resolved cwd. Without this, `--yolo` does NOT auto-approve the external-file warning and the run hangs on a permission box.
- **Prompt delivery**: each prompt is wrapped in bracketed-paste escapes (`\e[200~ … \e[201~`) so the TUI's slash-command autocomplete does not trigger on every `/` and triple it.
- **Pass criteria** (stricter than `bench_api_tool_call.py`):
  - Single-call: at least one tool from `expected_any_of` set actually invoked **and** `[Completed in N iteration(s)]` reached.
  - Multi-turn: `read` invoked, then `write` or `edit` invoked, **and** `config.json` has `port == 8080` after the run, **and** completion reached.
- **Cold-start variant**: a prior version of the script invoked `llama-agent` once per scenario via `subprocess.run`. Wall-clock is dominated by per-scenario model load (~5 s) on top of inference. Resident-PTY shaves ~30 % off the total. The script in this repo is the resident-PTY version; cold-start numbers are kept here for context.

## Cross-model summary

Rows ordered by multi-turn time (ascending); 5/5 single-call pass + ✅ port rewritten before partials. Steady gen tok/s is the median across the 6 scenarios via the agent's `/stats`.

| Model | Active params | Quant | Single-call pass | 5 single calls wall | Multi-turn (port=8080) | Steady gen tok/s | Model load | Notes |
|:------|:-------------:|:------|:----------------:|--------------------:|-----------------------:|-----------------:|-----------:|:------|
| prithivMLmods Qwen3.6-35B-A3B Aggressive | ~3 B (MoE) | Q6_K GGUF | **5/5** | 25.52 s | **5.10 s** 🥇 ✅ | 76.5–78.1 | 14.82 s | Tightest multi-turn (`read → edit` once and done). Uncensored fine-tune. Raw: [`agent-local.json`](qwen36-35b-a3b-prithiv-aggressive/agent-local.json) |
| HauhauCS Qwen3.6-35B-A3B Aggressive | ~3 B (MoE) | Q6_K_P GGUF | **5/5** | 25.48 s | **5.86 s** 🥈 ✅ | 75.6–78.0 | 15.71 s | Multi-turn `read → edit → read` (one read-after-write check). Uncensored. Raw: [`agent-local.json`](qwen36-35b-a3b-hauhaucs-aggressive/agent-local.json) |
| TrevorJS Gemma 4 26B A4B Uncensored | ~4 B (MoE) | Q8_0 GGUF | **5/5** | 19.24 s 🥇 | 7.92 s ✅ | **79.4–80.5** 🥇 | 11.86 s | Fastest single-call wall. Tool sequence shows the model leans heavily on `update_plan` between every tool call (turns up iteration count). Raw: [`agent-local.json`](gemma4-26b-a4b-trevorjs-uncen/agent-local.json) |
| IBM Granite 4.1 30B Q8_0 | 30 B (dense) | Q8_0 GGUF | **5/5** | 49.99 s | 15.35 s ✅ | 21.0–21.4 | 3.84 s | Dense 30B → ~3.5× slower decode than MoE siblings. Multi-turn `read → edit → read → edit` (double-checks). Smallest model load (no MoE expert routing tables). Raw: [`agent-local.json`](granite-4.1-30b-q8/agent-local.json) |
| Gemma 4 31B-it (lmstudio-community 6-bit) | — | **MLX** safetensors | N/A | — | — | — | — | **Not runnable** — llama-agent is built on `llama.cpp` and only loads GGUF. Use `model-benchmark-tool-call.md` (LM Studio MLX runtime) for this model's agent benchmark. |
| mlx-community/Qwen3.6-27B 6bit | 27 B (dense) | **MLX** safetensors | N/A | — | — | — | — | **Not runnable** — same llama.cpp/GGUF-only constraint. The `bench_api_tool_call.py` row in [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md) covers this model on vllm-mlx and llmster. |

## What the numbers mean (and don't)

- **Steady gen tok/s (~21 t/s for Granite)** is what the model actually generates inside the agent loop on M3 Ultra. Compare to ~24.8 tok/s from [`api-server-llmster.json`](granite-4.1-30b-q8/api-server-llmster.json) — the small gap reflects llama-agent's per-turn reset + tool-result re-prefill, not server overhead.
- **Single-call wall times include real tool execution.** `read /tmp/bench-llama-agent/notes.txt` actually reads the file and the model summarises the contents; the wall-clock therefore includes prefill of the file's tokens.
- **Iteration counts match the agent's own `[Completed in N iteration(s)]`.** Multi-turn shows `iter=5` for Granite — read → edit → read → edit → final summary.
- **Token counts come from the agent's `/stats` after each turn.** Resets to 0 on `/clear`, so values are per-scenario, not session-cumulative.

## Caveats specific to this harness

1. **macOS `/tmp` symlink** — sandbox path must be `realpath("/tmp/...")` or the agent flags every file as "external" and pauses on a permission box that `--yolo` does NOT bypass.
2. **TUI slash autocomplete** — without bracketed-paste escapes, `/tmp/foo` becomes `///tmp///foo` over the PTY and the model gets a corrupted prompt.
3. **`--simple-io` is not multi-turn** — it reads stdin to EOF as a single prompt. Use full TUI mode over a PTY for multi-turn benchmarks.
4. **brew formula b9121 build fails** — duplicate `stb_image` symbols between `tools/agent/stb-image-impl.cpp` and `tools/mtmd/libmtmd.a`. Use the pre-built tarball from GitHub Releases (`llama-agent-b9121-bin-macos-arm64.tar.gz`).
5. **No streaming SSE event log** — token counts and tool sequence are captured by parsing the TUI's stdout. The structured-event variant is `llama-agent-server` (`-DLLAMA_HTTPLIB=ON`) which exposes `/v1/agent/session/:id/chat` over SSE — not measured here because that re-introduces a (loopback) HTTP layer.
6. **GGUF only** — `llama-agent` is a fork of `ggml-org/llama.cpp` with an agent loop bolted on. It loads GGUF files; **MLX safetensors models are not supported** (no plan to add — `mlx-lm` lives in a separate ecosystem). For MLX models, use [`model-benchmark-tool-call.md`](model-benchmark-tool-call.md) (covers both the synthetic API-level harness and the OpenCode end-to-end agent loop).

## Adding a new model

```bash
# Pre-built binary one-time setup on Mac Studio
ssh macstudio "mkdir -p ~/llama-agent-bin && cd ~/llama-agent-bin && \
  curl -sSL -o llama-agent.tar.gz \
    'https://github.com/gary149/llama-agent/releases/download/b9121/llama-agent-b9121-bin-macos-arm64.tar.gz' && \
  tar -xzf llama-agent.tar.gz"

# Run the benchmark (model can be a local .gguf path OR a 'repo/name:Q8_0' HF id)
ssh macstudio "/usr/bin/python3 ~/setup-llm-macstu/scripts/bench/bench_agent_local.py \
  --bin ~/llama-agent-bin/llama-agent \
  --model /path/to/your-model.gguf \
  --output ~/setup-llm-macstu/docs/models/benchmarks/<model-slug>/agent-local.json \
  --timeout 120 --max-iterations 12"
```

Then add a row to the Cross-model summary above and follow [Sync Policy Event 4](../../../CLAUDE.md#event-4-running-a-new-benchmark) for catalog updates.
