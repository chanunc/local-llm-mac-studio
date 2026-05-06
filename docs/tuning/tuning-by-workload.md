# Tuning by workload

Same knobs behave differently across workload types. Pick the regime first, then the knobs. For knob-by-knob detail (what each one does and our local measurements), see [`tuning-by-knob.md`](tuning-by-knob.md).

## Three workload regimes

The Mac Studio LLM stack runs three distinct workloads, each measured by a different bench script:

| Regime | What it is | Bench script | Example |
|:--|:--|:--|:--|
| **Generic prompt** | Single-turn chat, no tools | [`scripts/bench/bench_api_server.py`](../../scripts/bench/bench_api_server.py) | "Summarise this article" |
| **Agent tool prompt** | Single-turn with tool definitions | [`scripts/bench/bench_api_tool_call.py`](../../scripts/bench/bench_api_tool_call.py) | One-shot weather query |
| **Agent loop** | Multi-turn with tools, results fed back | [`scripts/bench/bench_agent_tool_call.py`](../../scripts/bench/bench_agent_tool_call.py) | OpenCode browse / search |

If a benchmark says a server is "fast", check which regime it tested — a generic-prompt win does not transfer to an agent-loop win, and vice versa.

## Knob × workload matrix

Severity of impact per regime:

| Knob | Generic prompt | Agent tool prompt | Agent loop |
|:--|:--|:--|:--|
| Thinking flag | Medium — adds latency | Medium — extra tokens before tool call | **Dominant** — multiplied across N turns |
| Tool-call parser | None | **Critical** — wrong/missing = tool call rendered as text | **Critical** — same per turn |
| Reasoning parser | Low — only a clean-output convenience | Medium — prevents `<think>` leaking into tool args | Medium — prevents thoughts from polluting subsequent turns |
| Speculative drafter | Helps if output is long, wash on short replies | Often loses to overhead — outputs short | Mixed — depends on tool-result-summarisation length |
| Quantisation | Linear effect on decode | Linear effect on decode | Linear effect on decode |
| Context length cap | Only the OOM ceiling | Sets headroom for tool catalog + system prompt | **Constraint** — grows turn-by-turn with tool results |
| Prompt cache size | Helps multi-conversation reuse | Small win | **Big win** — system prompt + tool catalog re-prefilled every turn otherwise |
| `--prefill-step-size` | Matters at >2K input | Matters (agent system + tools = 5–15K typical) | Matters early; later turns hit prompt cache anyway |

## Per-regime guidance

### Generic prompt

The simplest regime. Parsers do not apply, prompt cache barely helps (you only ask once), and the conversation does not loop.

Knobs that move the needle, in priority order:

1. **Quantisation** — pick the lowest bit count whose quality you can tolerate. Memory bandwidth is the bottleneck on Apple Silicon.
2. **Speculative drafter** — only if your output is long (>200 tokens). Drafter overhead dominates on short replies.
3. **Thinking flag** — adds latency without changing correctness. Turn off if you want a fast plain answer.

**Diagnostic value**: this regime cleanly isolates **raw prefill / decode rates** without parser or thinking-mode confounders. We used `bench_api_server.py` to verify `mlx_lm.server` already beats lm-studio on prefill at every context for Gemma 4 31B-it 6-bit (1.74× at 32K), demystifying the apparent lm-studio speed advantage in agent loops as not-a-prefill-issue. See [`../servers/lm-studio/prefill-speed-technique.md` § Local measurement](../servers/lm-studio/prefill-speed-technique.md#local-measurement-on-mac-studio-m3-ultra-96-gb-2026-05-06).

### Agent tool prompt (single turn)

Adds the parser axis. Most "fast server, zero tool calls" debugging time has gone here.

Knobs in priority order:

1. **Tool-call parser** — must match the model's output shape. If the model emits `<function=name>…</function>` (Qwen3.5/3.6) and you pass `--tool-call-parser qwen` (which expects JSON inside `<tool_call>` tags), you get 0 tool calls. Verify with `bench_api_tool_call.py`'s 5-tool harness — should hit 5/5.
2. **Reasoning parser** — needed in addition to the tool-call parser for any thinking model, otherwise `<think>` content leaks into tool arguments.
3. **Quantisation** — same as generic.
4. **Thinking flag** — non-trivial tax (extra tokens before the tool call) but acceptable as a one-time cost on a single-turn prompt.

**Diagnostic value**: this regime isolates **server-level tool-handling correctness** from agent-loop dynamics. Pass means "the server can produce a tool call from a single turn"; fail at this layer means parser flags or chat-template handling is broken regardless of agent behaviour. The JANGTQ4-CRACK example in [project memory](../../../.claude/projects/-Users-chanunc-cc-prjs-cc-claude-setup-llm-macstu/memory/project_jangtq4_search_hang_layer.md) — model passed 5/5 here while still hanging in OpenCode — demonstrates the failure can live above this layer.

### Agent loop (multi-turn)

Compounds everything. Where most production tuning lives.

Knobs in priority order:

1. **Thinking flag** — single biggest agent-loop lever. 3–4× output tokens × N turns. Gemma 4 on `mlx_lm.server` (thinking ON) is 2.4–5.6× slower on OpenCode than the same weights on lm-studio (thinking OFF), driven entirely by this knob.
2. **Prompt cache size** — system prompt + tool catalog gets re-prefilled every turn unless cached. The difference between 5 s and 25 s per turn at long contexts.
3. **Tool-call parser** + **reasoning parser** — same as single-turn but matters per turn. A parser bug compounds across the loop.
4. **Context length cap** — load-bearing because tool results pile up turn by turn. Set it to 65K+ for OpenCode-style workloads.
5. **Speculative drafter** — diminishing returns; the short tool-result-summarisation outputs between tool calls do not amortise drafter overhead well.

**Diagnostic value**: this regime is **the production gate** — if a model fails the OpenCode browse/search bench, it does not matter how fast it is at the lower layers. But agent-loop wall time is also the *least* useful layer for diagnosing *what* is wrong, because thinking-mode bloat, parser bugs, prompt-cache misses, and decode-rate gaps all show up as the same symptom (slow). When `bench_agent_tool_call.py` regresses, drop down to `bench_api_tool_call.py` (parser correctness) and `bench_api_server.py` (raw rates) to localise the cause.

## Summary

> The same knob has very different impact in each regime. Pick the regime first, then the knobs.

Practical mental model:

- **Generic prompt** → quant + drafter + thinking flag.
- **Agent tool prompt** → above + parsers (the new axis).
- **Agent loop** → above + prompt cache (becomes load-bearing) + thinking flag (becomes dominant).

The corollary: **never claim "server X is faster than server Y" without naming the regime.** lm-studio is faster than `mlx_lm.server` on Gemma 4 agent loops (because of thinking-mode-off default, not the kernel). `mlx_lm.server` is faster than lm-studio on Gemma 4 generic prompts (because of upstream prefill tuning). Both are true; neither generalises.

## Cross-references

- [`tuning-by-knob.md`](tuning-by-knob.md) — same knobs, organized by individual lever.
- [`../models/benchmarks/`](../models/benchmarks/) — raw JSON outputs from each of the three bench scripts.
- [`../servers/`](../servers/) — per-server runbooks; launch shapes show which flags get set by default for each workload regime.
- [`../models/per-model/model-summary-gemma.md`](../models/per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) — clean side-by-side of the same Gemma 4 weights running both fast (lm-studio, thinking OFF) and slow (mlx_lm.server, thinking ON), demonstrating the workload-vs-knob interaction.
