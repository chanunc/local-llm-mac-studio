# OpenCode Latency Analysis

Performance characteristics of OpenCode against the Mac Studio M3 Ultra servers, with particular focus on the MiniMax-M2.7-JANGTQ-CRACK reasoning model.

*Last updated: 2026-04-20.*

---

## Benchmark Command

Time any OpenCode prompt from the terminal:

```bash
time opencode run "<your prompt>"
```

Time the raw API directly (bypasses OpenCode overhead, shows actual model latency):

```bash
time curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<MODEL_ID>","messages":[{"role":"user","content":"<PROMPT>"}],"temperature":1.0}' \
| python3 -c "
import sys, json
d = json.load(sys.stdin)
m = d['choices'][0]['message']
u = d.get('usage', {})
print('reasoning_content tokens:', len((m.get('reasoning_content') or '').split()))
print('content tokens:          ', len((m.get('content') or '').split()))
print('total completion_tokens: ', u.get('completion_tokens'))
print()
print('ANSWER:', m.get('content', ''))
"
```

---

## MiniMax-M2.7-JANGTQ-CRACK: OpenCode vs Raw API

Measured on Mac Studio M3 Ultra (96 GB), vmlx server, 2026-04-20.

### Results

| | OpenCode `run "Hi"` | Raw `curl` "Hi" |
|--|---------------------|-----------------|
| Wall time | **1 min 20 s** | **2.7 s** |
| Prompt tokens | ~2,000–4,000 (with agent system prompt) | 40 |
| Completion tokens | ~3,600 (estimated from wall time × tok/s) | 79 |
| API calls made | **4** (agent loop) | 1 |
| Model throughput | ~45 tok/s | ~45 tok/s |

Raw API response for "Hi" (79 total completion tokens):

```
reasoning_content: "The user says 'Hi'. It's a greeting. We can respond
with a greeting and ask how we can help. There's no request for anything
specific. So the assistant should respond politely, possibly offering
assistance. No need for any special content. Just greeting.

Make sure no policy issues. It's fine."

content: "Hi there! How can I help you today?"
```

### Why OpenCode is ~30× slower than raw API

**1. Large agent system prompt.**
OpenCode injects tool definitions (bash, file read/write, glob, grep, …),
current directory context, and conversation history into every request.
A typical OpenCode system prompt is 2,000–4,000 tokens vs 40 for a bare
curl. More prompt tokens → the model reasons longer before answering.

**2. Multiple agent loop turns.**
The vmlx server log shows 4 separate `POST /v1/chat/completions` requests
for a single `opencode run "Hi"`. OpenCode runs an agent loop: send
completion → check for tool calls → send tool results → repeat. Even for
a prompt that needs no tools, the loop still completes multiple round-trips.

**3. Reasoning token amplification.**
MiniMax-M2.7 generates an invisible `<think>` block before every visible
reply. With a 40-token prompt the think block was ~65 tokens (fast). With
a 4,000-token agent system prompt it expands proportionally — the model
has more context to reason about before committing to an answer.

The model throughput (tok/s) is identical in both cases — the server is
working efficiently. The latency difference is entirely token-count driven.

---

## When to use MiniMax-M2.7-JANGTQ-CRACK with OpenCode

| Use case | Verdict |
|----------|---------|
| Short chat / quick questions ("Hi", "what file is X in?") | **Poor fit** — 30–80 s per turn; use Hermes 4 70B or the primary vllm-mlx model instead |
| Complex multi-file refactors, long-context analysis | **Good fit** — the reasoning overhead is amortised over a large task; the 230B MoE parameter count and 128 K context pay off |
| Uncensored content generation (CRACK abliteration) | **Best option** — no other available server path serves JANGTQ weights; 10/10 compliance on mlabonne sample |

---

## Comparison: MiniMax vs vllm-mlx Primary (Qwen3.5-122B-A10B JANG 2S)

| Metric | MiniMax-M2.7-JANGTQ (vmlx) | Qwen3.5-122B-A10B JANG 2S (vllm-mlx) |
|--------|----------------------------|---------------------------------------|
| Short-prompt latency | Slow (reasoning overhead) | Fast |
| Long-context coding | Strong (128 K, 230B params) | Strong (200 K+, 122B params) |
| Uncensored output | Yes (CRACK + abliteration) | No |
| API key required | No | No |
| Server | vmlx (bundled Python) | vllm-mlx |

---

## See Also

- [`docs/server/vmlx/summary.md`](../server/vmlx/summary.md) — vmlx server overview and perf numbers
- [`docs/server/vmlx/maintenance.md`](../server/vmlx/maintenance.md) — start/stop/switch commands
- [`docs/clients/opencode-setup.md`](opencode-setup.md) — OpenCode installation and configuration
