# Agent-tool-call failure triage: gemma-4-26b-a4b-q8 (lmstudio-community)

**Date:** 2026-05-07
**Model:** `lmstudio-community/gemma-4-26B-A4B-it-GGUF` (`gemma-4-26B-A4B-it-Q8_0.gguf`)
**Server:** lm-studio :1234, identifier `gemma-4-26b-a4b-q8`
**Branch:** censored (standardised Google RLHF instruct, not abliterated)

## Failure signature

| Bench layer | Result |
|:--|:--|
| API-level smoke (`bench_api_tool_call.py`) | ✅ **5/5 single-call**, 3/3 multi-turn, total 2.14 s — **tied with TrevorJS for gold** |
| API-level throughput (`bench_api_server.py`) | ✅ TTFT 0.18 s @ 512, gen 70–86 tok/s, prefill 158 K tok/s @ 32 K |
| OpenCode end-to-end (`bench_agent_tool_call.py`) | ⛔ **0/3 browse + 0/3 search fired any tool** (`tool_calls: []`, `agent_turns: 1`) |

## Root cause

Model output for "Browse www.example.com" (verbatim, first 200 chars):

> _"I cannot browse websites directly. However, if you provide a URL, I can use the `webfetch` tool to retriev…"_

The standardised Google RLHF instruct **understands** it has `webfetch` — it names the tool by string in its prose response — but does not autonomously fire it on a bare URL prompt. RLHF training has biased the model toward asking for clarification rather than taking side-effecting actions on first turn. This is exactly the safety behaviour Google's instruction-tuning is meant to produce.

**The abliteration in TrevorJS Gemma 4 26B A4B is doing real work in the agent loop, not just refusal-rate work.** TrevorJS fires `webfetch` cleanly on the same prompt (browse 2.93 s 🥇, 2/2 turns), because EGA abliteration removes the "ask for confirmation before acting" prior alongside the safety prior.

## Layer attribution

| Layer | Status | Evidence |
|:--|:--|:--|
| Model | OK at inference | API-level harness explicitly passes `tools[]` and the model emits well-formed `tool_calls`. Architecture, quant, and chat template all work. |
| LM Studio runtime | OK | The same template handles the explicit-tools API smoke without issue. |
| OpenCode tool injection | OK | Tool catalog reaches the model (10,781-token system prompt is delivered) and the model knows the tool's name (mentions `webfetch` by string in output). |
| **Model agent-loop policy** | ⛔ **Conservative** | Google RLHF doesn't fire side-effecting tools on bare prompts. The exact same model variant that emits `read_file` on "Read /tmp/foo.txt" (smoke scenario 1) refuses to emit `webfetch` on "Browse www.example.com" (agent scenario 1). |

**Conclusion:** This is not a bug or misconfiguration. It's the *standardised* behaviour the user explicitly asked for ("not uncensored"). Standardised Gemma 4 26B A4B is unsuitable for OpenCode-style agent loops that issue terse imperative URL prompts; suitable for explicit imperative prompts like _"Use webfetch to fetch www.example.com and summarize"_.

## Reproducer (verbatim opencode invocation)

```bash
opencode run --model macstudio/gemma-4-26b-a4b-q8 --format json "Browse www.example.com"
# → {"type":"text", ..., "text":"I cannot browse websites directly. However, if you provide a URL,
#    I can use the `webfetch` tool to retriev…"}
# turns=1, tool_calls=[], output_tokens≈40
```

## Recommended next steps

1. **For the user's "censored TrevorJS alternative" goal:** drop Gemma 4 26B A4B-it standardised. The architecture is the right speed-class, but the agent-loop policy difference is real and uniform across vanilla / unsloth / lmstudio-community / mlx-community quantizers (they all derive from `google/gemma-4-26B-A4B-it`).
2. **Alternatives to evaluate** for "Apache 2.0 + standardised + fast":
   - `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF` — Qwen3 instruct family is more aggressive about tool-firing on bare prompts (precedent: Qwen3.5/3.6 family rows in the OpenCode end-to-end table). MoE 30B/3B-active.
   - `lmstudio-community/Qwen3.6-35B-A3B-Instruct-GGUF` if it exists — same agent-loop ergonomics as our current main but standard instruct rather than the unsloth UD imatrix.
   - Granite 4.1 30B Q8_0 (already on disk as fallback) — Apache 2.0, dense, fires tools cleanly on bare prompts (browse 6.24 s, search 10.51 s — slower than Gemma 4 A4B but agent-functional).
3. **If sticking with Gemma 4 26B A4B-it standardised anyway:** OpenCode prompts must be re-phrased to explicit imperatives ("Use webfetch to fetch …"). This is a UX change, not a model fix.

## Cross-fork landscape

| Source | LM Studio template | Tool-firing on bare prompt |
|:--|:--|:--|
| `unsloth/gemma-4-26B-A4B-it-GGUF` | ❌ Broken jinja: "Cannot call something that is not a function: got UndefinedValue" — HTTP 400 on every API request with `tools[]` (deleted from disk 2026-05-07) | N/A |
| `lmstudio-community/gemma-4-26B-A4B-it-GGUF` | ✅ Works with `tools[]` | ⛔ **0/3 in OpenCode** (this triage) |
| `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | ✅ Works | ✅ 2/2 with webfetch (browse 2.93 s 🥇) |

## Status disposition

The bench JSONs (`api-tool-test.json`, `api-server-llmster.json`, `agent-bench.json`) are kept as durable artifacts. Per the skill's Phase 4b smoke-passed-agent-failed default, recommendation is **Skip docs, leave model running for manual debug** — but the user can elect "Continue with docs (caveats noted)" to document this finding alongside the magnum-v4-72b precedent (different mechanism but same observable: tools never fired in agent loop).
