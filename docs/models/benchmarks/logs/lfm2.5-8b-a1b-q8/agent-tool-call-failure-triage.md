# LFM2.5-8B-A1B Q8_0 — tool-call failure triage

## Overview

This document triages why `LiquidAI/LFM2.5-8B-A1B-GGUF` Q8_0 on llmster (LM Studio) scored **0/5** on the smoke tool-call benchmark. It covers:

- **Failure signature** — what the bench and a manual probe observed
- **Layer attribution** — model emits tool calls correctly; the failure is in template + parser layer
- **Root cause** — broken embedded chat template + LM Studio `<think>`-block parser bug
- **Related findings** — HF discussion + LM Studio bug-tracker references
- **Recommended next steps** — the fixed-template GGUF and other options
- **Reproducer** — exact request that demonstrates the bug

## Failure signature

| Field | Value |
|:--|:--|
| Model id | `lfm2.5-8b-a1b-q8` |
| Server | llmster (LM Studio headless, port 1234) |
| Quant | Q8_0 (9.01 GB) |
| Context | 65536 |
| Arch | `lfm2moe` (32×959M experts, 8.3B total / ~1.5B active) — recognized by LM Studio's bundled llama.cpp |
| Smoke result | **single-call 0/5**, multi-turn 1 turn |
| Per-scenario | every scenario: `finish_reason=stop`, `tool_calls=[]`, latency 1.0–3.6 s |
| Layer | **not the model** — model emits a syntactically valid tool call, but into `reasoning_content` |

## Layer attribution — the MODEL is correct; both runtimes' parsers are not

**The template is NOT the problem.** Extracting `tokenizer.chat_template` from the canonical-repo Q8_0 GGUF and from the community "fixed" GGUF (`nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2`) and diffing them shows they are **functionally identical** — both contain `render_tool_calls()`, the native `<|tool_call_start|>` format, and a `preserve_thinking` variable. The only difference is a single no-op Jinja comment line (`{# List of tools: [ #}`). The canonical repo has already absorbed the fix that HF discussion #1 was asking for. **Deploying the "fixed" variant changes nothing.**

The actual failure is in the **runtime tool-call parsers**, and it differs by server:

### LM Studio (llmster, port 1234) — injects its own format

A manual probe (`tool_choice:auto`, single `read_file` tool) shows LM Studio **ignores the model's native template** and injects its generic `[TOOL_REQUEST]` / `[END_TOOL_REQUEST]` instruction format (LM Studio doesn't detect `lfm2moe` as tool-capable — see bug #458). Because LFM2.5-8B-A1B is **reasoning-only** (always opens a `<think>` block), the model writes the injected `[TOOL_REQUEST]` block *inside* its reasoning and emits EOS without closing the think block. LM Studio then classifies the whole output (tool call included) as `reasoning_content`:

```
reasoning_content: "...[TOOL_REQUEST]\n{\"name\":\"read_file\",\"arguments\":{\"path\":\"/tmp/config.json\"}}\n[END_TOOL_REQUEST]"
content: ""
tool_calls: []   finish_reason: "stop"
```

Disabling thinking did not help: neither `chat_template_kwargs:{enable_thinking:false}` nor a `/no_think` prefix changed the behavior — the model is reasoning-only with no documented disable toggle (per the official LFM2.5 card).

### llama.cpp `--jinja` (the model's designed path) — recognizes tokens, can't parse the Pythonic list

Serving the same Q8_0 GGUF via `~/llama-cpp-mainline/build/bin/llama-server … --jinja` (build `510b5c2`) uses the **embedded native template**, and the model emits the **correct** native call:

```
HTTP 500: Failed to parse input at pos 1206:
<|tool_call_start|>[read_file(path="/tmp/config.json")]<|tool_call_end|>
```

llama.cpp recognizes the `<|tool_call_start|>` / `<|tool_call_end|>` tokens but its PEG grammar **cannot parse LFM2.5's Pythonic call list** (`[func(arg="...")]`, à la Llama-3.2 pythonic tools). This is the exact upstream bug **[ggml-org/llama.cpp #20245 — "autoparser breaks tool calls from LFM2.5-Instruct"](https://github.com/ggml-org/llama.cpp/issues/20245)**. (Same build also fails to split the `<think>` block into `reasoning_content` for this model — `--reasoning-format auto` leaves it in `content` — a related LFM2.5 chat-format gap.)

**Conclusion:** the model itself produces spec-correct tool calls. Tool calling is blocked by an upstream parser gap present in *both* lab GGUF runtimes for this <24h-old architecture. No template/quant/config swap on the Mac Studio fixes it today.

## Related findings

- **HF discussion #1** — [LiquidAI/LFM2.5-8B-A1B-GGUF · "Tool calling and thinking not working in llama.cpp"](https://huggingface.co/LiquidAI/LFM2.5-8B-A1B-GGUF/discussions/1) (opened ~2026-05-28, 12 👍, 6 replies). Confirms: the original repo's chat template is broken for both `<think>` tags and tool calls; `chatml` override does not fix it.
- **Community fix** — [`nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2`](https://huggingface.co/nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2) ships a corrected template: a `render_tool_calls()` macro emitting `<|tool_call_start|>[...]<|tool_call_end|>`, a `preserve_thinking` variable, and proper `<|im_start|>`/`<|im_end|>` delimiters. Reported "working very well" though "not perfect."
- **LM Studio bug #1592** — [Tool call parser scans inside `<think>` blocks](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1592) (opened 2026-03-02, unresolved). Names LFM2.5's `<|tool_call_start|>` among the formats whose `</think>` boundary handling is buggy. Workaround: disable reasoning in the prompt template (`{%- set enable_thinking = false %}`) → 20+ consecutive tool calls succeed.
- **LM Studio bug #1358** — [LFM2.5-1.2b-instruct / Model failed to generate a tool call](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1358) — same family, intermittent tool-call generation.
- **LM Studio bug #1593** — [Multi-MCP-server registration breaks tool call parsing for LFM2.5](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1593) — second MCP server breaks the special-token parsing.

## Recommended next steps

1. **Deploy the fixed-template variant** — re-run this skill against `nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2` (Q8_0). The embedded corrected template emits native `<|tool_call_start|>` syntax, which LM Studio parses; the `preserve_thinking` switch lets the think block close before the tool call. This is the highest-probability path to real bench numbers.
2. **Or override the chat template in LM Studio** — point this model's prompt template at the fixed jinja (`models/templates/LFM2-8B-A1B.jinja` corrected variant). Not scriptable via `lms` headless; requires GUI or manifest edit.
3. **Wait for upstream** — LiquidAI is expected to push a corrected template to the canonical repo given the open discussion; re-pull then.

## Reproducer

```bash
curl -s http://<MAC_STUDIO_IP>:1234/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model":"lfm2.5-8b-a1b-q8",
  "messages":[{"role":"user","content":"Read /tmp/config.json and tell me what port it uses. Use the read_file tool."}],
  "tools":[{"type":"function","function":{"name":"read_file","description":"Read a file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}}],
  "tool_choice":"auto","max_tokens":300,"temperature":0
}'
# Observed: content="", tool_calls=[], and the [TOOL_REQUEST]{...}[END_TOOL_REQUEST] block lands inside reasoning_content.
# Expected: tool_calls=[{function:{name:"read_file",arguments:"{\"path\":\"/tmp/config.json\"}"}}]
```

Bug is upstream (broken template in the canonical repo + LM Studio `<think>`-boundary parser); not filed by this run — the canonical-repo discussion #1 already tracks it.
