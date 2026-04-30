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

## Community research (2026-04-20)

Researched Reddit (r/LocalLLaMA), GitHub (MiniMax-AI/MiniMax-M2, sst/opencode, vllm-project/vllm, can1357/oh-my-pi), HuggingFace discussions, and blog posts for others running MiniMax-M2 / M2.5 / M2.7 with OpenCode, Pi, Claude Code, aider, or Cline.

### Headline findings

- The 30× agent-loop latency blowup is **the generic MiniMax-M2 family problem**, not a JANGTQ or MiniMax-M2.7 quirk. Reproduces on SGLang, vLLM, Ollama, LM Studio, and OpenCode regardless of quantization.
- **No working "disable thinking" switch exists** as of April 2026. `/nothink`, `enable_thinking: false`, and Pi's `thinking: off` are explicitly ignored by the model ([oh-my-pi#626](https://github.com/can1357/oh-my-pi/issues/626), [MiniMax-M2#68](https://github.com/MiniMax-AI/MiniMax-M2/issues/68)).
- **Zero public reports on `dealignai/MiniMax-M2.7-JANGTQ-CRACK` specifically.** This Mac Studio + vmlx + OpenCode combination appears unique in the public record. The HF page has a single open discussion and it is about file-size accounting, not latency.

### Key evidence from the community

- **[MiniMax-M2#77](https://github.com/MiniMax-AI/MiniMax-M2/issues/77)** — 29-case agent benchmark (M2.5): simple greeting 2.2 s vs Qwen Plus 0.76 s; file read 15.1 s vs 2.9 s; disk space query **195 s vs 0.6 s (325× slower)**. Root cause explicitly identified as `<think>` "adds verification steps even after a task is already complete."
- **[MiniMax-M2#52](https://github.com/MiniMax-AI/MiniMax-M2/issues/52)** — SGLang: "`<think>` consumes nearly all `max_tokens`; 'LOW reasoning mode' system prompts did not prevent excessive thinking."
- **[sst/opencode#3555](https://github.com/sst/opencode/issues/3555)** — **directly relevant to this setup**: OpenCode's OpenAI-compatible mode leaves `<think>` inside `delta.content` instead of routing it to `delta.reasoning_content`. The think block then re-enters the next agent turn as regular content, compounding the blowup across all 4 loop turns.
- **[vllm-project/vllm#34625](https://github.com/vllm-project/vllm/issues/34625)** — the `minimax_m2_append_think` parser is itself broken when the think tag shares a token boundary.
- **[purplemaia blog — From Benchmarks to Builders](https://blog.labs.purplemaia.org/from-benchmarks-to-builders-running-minimax-m2-1-on-our-mac-studio/)** — Mac Studio M3 Ultra **512 GB** running MiniMax-M2.1 on LM Studio (MLX 5-bit) ran the Harbor terminal-bench suite 11/18. Toggling LM Studio's "Separate reasoning from content" on MLX **caused a 10× slowdown and 5/10 timeouts** — a reasoning-parser misconfiguration hazard worth noting on Apple Silicon.

### Mitigations ranked by reported effectiveness

1. **Trim the agent system prompt.** MiniMax's own docs say: *"When using tools that support context compression (such as Claude Code), it's recommended to control the number of tokens in system prompts. M2.7 may terminate tasks early when approaching context capacity thresholds."* — [platform.minimax.io best-practices](https://platform.minimax.io/docs/token-plan/best-practices). This is the single biggest lever the community agrees on.
2. **Server-side reasoning parser.** vLLM's recommended flags: `--reasoning-parser minimax_m2_append_think --tool-call-parser minimax_m2 --enable-auto-tool-choice` ([vLLM recipe](https://docs.vllm.ai/projects/recipes/en/latest/MiniMax/MiniMax-M2.html)). Moves `<think>` into a separate `reasoning_content` field so clients can strip it before the next turn. **Unknown whether vmlx exposes an equivalent flag** — worth checking before the next deploy.
3. **Client-side strip of `<think>…</think>`** from prior turns before re-sending the conversation. OpenCode does not do this automatically (#3555).
4. **`max_tokens` caps.** Widely tried, widely reported as partial at best — the model can hit the cap mid-think and still return nothing useful.
5. **Prompt-side `/nothink` / `enable_thinking: false`.** Confirmed **ineffective** on MiniMax-M2 family. Do not rely on it.

### Hardware profiles of people not hitting the latency wall

| Setup | Stack | Notes |
|-------|-------|-------|
| Mac Studio M3 Ultra 512 GB | LM Studio v0.4, MLX 5-bit, MiniMax-M2.1 | 11/18 on Harbor terminal-bench; reported more stable than vllm-mlx. 5× our RAM. |
| 4× H100 (TP4+EP4) or 2× B200 | vLLM with official reasoning parser | Official recommended config; 400 K KV cache. |
| OpenRouter hosted API | MiniMax-hosted server with proper parser | `reasoning.effort=high` stable at ~1,000 think tokens per turn — same weights, parser is the difference. |
| Cline v3.35 on hosted MiniMax-M2 | Native tool-calling, not OpenAI-compat | ~100 tok/s reported against the hosted endpoint. |

### Implications for this setup

- Your 80 s OpenCode latency is a **known OpenCode-specific compounding** of the generic MiniMax-M2 thinking problem. sst/opencode#3555 is the tracker to follow.
- Two concrete next steps worth trying:
  1. Check whether `vmlx_engine` exposes an equivalent of vLLM's `--reasoning-parser minimax_m2_append_think` flag. If yes, OpenCode's `reasoning_content` handling may already route correctly and the per-turn think cost should drop.
  2. If OpenCode's agent system prompt is configurable, trim it aggressively — this is the community's single strongest recommendation, straight from MiniMax's own docs.
- Hermes 4 70B on vllm-mlx (no reasoning overhead) remains the right choice for short interactive OpenCode turns until one of the above lands.

---

## See Also

- [`docs/servers/vmlx/summary.md`](../server/vmlx/summary.md) — vmlx server overview and perf numbers
- [`docs/servers/vmlx/maintenance.md`](../server/vmlx/maintenance.md) — start/stop/switch commands
- [`docs/clients/opencode-setup.md`](opencode-setup.md) — OpenCode installation and configuration
- [sst/opencode#3555](https://github.com/sst/opencode/issues/3555) — OpenCode `<think>` handling in OpenAI-compat mode
- [MiniMax-AI/MiniMax-M2#77](https://github.com/MiniMax-AI/MiniMax-M2/issues/77) — 29-case agent benchmark showing 325× regression on trivial prompts
- [vLLM MiniMax-M2 recipe](https://docs.vllm.ai/projects/recipes/en/latest/MiniMax/MiniMax-M2.html) — the recommended server-side parser config
