# OpenAI Responses API (and what local servers in this lab speak it)

What the **Responses API** is, how it differs from Chat Completions, which Mac Studio servers implement it, what agent tooling actually works against it, and the shim path for the servers that don't.

*Last updated: 2026-05-08.*

## TL;DR

- **Responses API** (`POST /v1/responses`) is OpenAI's stateful successor to Chat Completions, launched March 2025. Server-side conversation state via `previous_response_id`, typed `output[]` items, typed event stream, and four hosted tools: `web_search_preview`, `file_search`, `code_interpreter`, `computer_use_preview`.
- In this lab, **only `lm-studio:1234` (≥ v0.3.29) serves `/v1/responses` natively** — with custom function tools and **Remote MCP** (no hosted tools). The other six servers (`vllm-mlx`, `mlx-openai-server`, `oMLX`, `vmlx`, `dflash-mlx`, `llama-cpp-turboquant`) speak Chat Completions only.
- Hosted tools (`web_search_preview` etc.) are **OpenAI infrastructure**, not a wire format you can implement locally. They only work against `api.openai.com`.
- For local agent-style browsing/tool use against LM Studio, pair the Responses request with a **Remote MCP** server (e.g. `playwright-mcp`, `firecrawl-mcp`).
- For Responses semantics against the other six lab servers, front them with a translator: [`chutesai/responses-proxy`](https://github.com/chutesai/responses-proxy) or [LiteLLM proxy](https://docs.litellm.ai/docs/response_api).
- `openai-cli` (the official CLI) is **not** an agent harness — it sends one request, prints one response. For local agent loops use `opencode`, `claude-code`, or OpenAI's separate `codex` CLI.

## Index

- [What the Responses API is](#what-the-responses-api-is)
- [Responses vs Chat Completions](#responses-vs-chat-completions)
- [Hosted tools (and why you can't run them locally)](#hosted-tools-and-why-you-cant-run-them-locally)
- [Local server support matrix](#local-server-support-matrix)
- [Shim path for Chat-Completions-only servers](#shim-path-for-chat-completions-only-servers)
- [Recipe: `openai-cli` against vllm-mlx via shim](#recipe-openai-cli-against-vllm-mlx-via-shim)
- [References](#references)

For the agent-loop angle (where the loop runs, custom function calling, Remote MCP / browser, hosted tools) see [`openai-agent-tooling.md`](openai-agent-tooling.md).

## What the Responses API is

OpenAI introduced `/v1/responses` in March 2025 as a unified replacement for **Chat Completions + Assistants**. The shape is intentionally different from Chat Completions because OpenAI wanted to expose:

- **Server-side conversation state.** Pass `previous_response_id` and the server retrieves the prior turn's reasoning/messages. Clients no longer hand-track `messages[]`.
- **Typed `output[]` items** — heterogeneous, one per "thing the model did": `message`, `reasoning`, `function_call`, `web_search_call`, `file_search_call`, `computer_call`, `mcp_tool_call`. This is what makes reasoning models (`o1`, `o3`, `gpt-5`) addressable as first-class items rather than buried in `content`.
- **Typed event stream.** Streaming SSE emits `response.created`, `response.output_text.delta`, `response.function_call_arguments.delta`, `response.reasoning.delta`, `response.completed`, etc. — vs Chat Completions' single-shape `choices[0].delta.{content,tool_calls}`.
- **Hosted agentic tools** baked into the platform: `web_search_preview`, `file_search`, `code_interpreter`, `computer_use_preview`.
- **Background mode** (submit, poll, retrieve) and **encrypted reasoning summaries** for o-series persistence.

This is the API surface OpenAI's own [`openai/openai-cli`](https://github.com/openai/openai-cli) is opinionated toward (`openai response create --input "..." --model ...`). The CLI also exposes `openai chat-completion create` as a fallback subcommand.

## Responses vs Chat Completions

| Axis | Chat Completions | Responses |
|:--|:--|:--|
| **Endpoint** | `POST /v1/chat/completions` | `POST /v1/responses` |
| **State** | Stateless — client resends full `messages[]` each turn | Stateful — pass `previous_response_id` to continue |
| **Input shape** | `messages: [{role, content}]` | `input: string` *or* typed array of `message`/`function_call`/`reasoning`/`image` items |
| **Output shape** | `choices[0].message.{content, tool_calls}` | `output: []` heterogeneous typed items |
| **Built-in tools** | None — function calling only | Hosted: `web_search_preview`, `file_search`, `code_interpreter`, `computer_use_preview` |
| **Reasoning** | Convention only (`reasoning` field where servers attach it) | First-class `reasoning` items, `reasoning.effort`, encrypted summaries |
| **Streaming** | `data: {choices[0].delta.content / tool_calls[…]}` | Typed events: `response.output_text.delta`, `response.function_call_arguments.delta`, … |
| **Background mode** | No | Yes |
| **Structured output** | `response_format: {type:"json_schema", …}` | `text.format: {type:"json_schema", …}` |
| **Multi-turn primitive** | Client tracks history | Server tracks; client passes `previous_response_id` |

## Hosted tools (and why you can't run them locally)

The four hosted tools are **OpenAI server-side infrastructure**, not a wire format:

| Hosted tool | What it does | Where execution happens |
|:--|:--|:--|
| `web_search_preview` | Live web search + page fetch + cite | OpenAI's backend |
| `file_search` | RAG over uploaded vector store | OpenAI's backend |
| `code_interpreter` | Sandboxed Python | OpenAI's backend |
| `computer_use_preview` | Screenshot + mouse/keyboard agent | OpenAI's backend (requires `computer-use-preview` model + your VM as the screen target) |

When a request says `tools: [{"type":"web_search_preview"}]`, the model decides whether to call it; OpenAI's servers execute the search; the result comes back as a `web_search_call` output item. None of this is reproducible locally — there's no "implement `web_search_preview` for LM Studio" on the table. The local equivalent is **Remote MCP** (see below).

## Local server support matrix

| Server | Native `/v1/responses`? | Notes |
|:--|:--|:--|
| **LM Studio** ≥ 0.3.29 | ✅ stable | Streaming, `previous_response_id`, custom function tools, **Remote MCP** opt-in via Developer Settings. No hosted tools. Open bugs: `text.format`, `instructions`, Codex-CLI tool `type:"namespace"`. |
| **vLLM** mainline | ✅ implemented, ⚠️ rough | `openai_responses_client` example shipped. Open issues: parallel tool-call streaming crashes, `truncation:"auto"` 400s, MM input, `DELETE /v1/responses/{id}`. Best with `gpt-oss`. **`vllm-mlx` does NOT inherit this** — Responses lives in upstream's OpenAI frontend, not the MLX backend tree. |
| **SGLang** | ✅ day-0 for gpt-oss | Custom function tools landed Nov 2025. `previous_response_id` flaky on gpt-oss-120B. |
| **HF `huggingface/responses`** | ✅ reference impl | Implements the [OpenResponses](https://www.openresponses.org/) open spec (HF-sponsored superset). |
| **llama.cpp** `llama-server` | 🔄 in flight | Tracking issue [#19138](https://github.com/ggml-org/llama.cpp/issues/19138), PRs [#18486](https://github.com/ggml-org/llama.cpp/pull/18486) / [#19720](https://github.com/ggml-org/llama.cpp/pull/19720) stalled on streaming-event compliance + `text.format`. |
| **Ollama** | 🔄 open | [#10309](https://github.com/ollama/ollama/issues/10309) — Codex CLI wants `wire_api = "responses"`. |
| **Jan** | 🔄 blocked | [janhq/jan#7413](https://github.com/janhq/jan/issues/7413), waiting on llama.cpp #19138. |
| **vllm-mlx** (this lab) | ❌ | MLX backend fork doesn't inherit upstream's Responses frontend. No tracking issue. |
| **mlx-openai-server** (this lab) | ❌ | No tracking issue. |
| **oMLX** (this lab) | ❌ | No tracking issue. |
| **vmlx** (this lab) | ❌ | No tracking issue. |
| **dflash-mlx** (this lab) | ❌ | No tracking issue — this is a `mlx_lm.server` wrapper, inherits its Chat-Completions-only surface. |
| **llama-cpp-turboquant** (this lab) | 🔄 (transitive) | Both forks inherit llama.cpp's tracking issue #19138; not implemented in either fork's branches. |

## Shim path for Chat-Completions-only servers

Two production-grade Responses → Chat-Completions translators. Drop one of them in front of any of the six lab servers that don't speak Responses, and `openai-cli` (or any Responses-native client) works against the lot.

### `chutesai/responses-proxy`

Rust, self-contained. Accepts `POST /v1/responses` with the full request shape, re-emits it as a Chat Completions request, reconstructs the typed event stream (`response.output_text.delta`, …) on the way back. Closest thing to a "drop-in adapter."

```bash
# Run the proxy on :8200, pointing at vllm-mlx :8000
./responses-proxy \
  --upstream-base-url http://192.168.31.4:8000/v1 \
  --bind 0.0.0.0:8200

# Then talk Responses to the proxy
openai response create \
  --base-url http://192.168.31.4:8200/v1 \
  --model JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --input "summarize this file" \
  --input '@notes.md'
```

Repo: <https://github.com/chutesai/responses-proxy>.

### LiteLLM proxy

More general (also bridges Anthropic ↔ OpenAI ↔ Ollama). Per-provider config flag `use_chat_completions_api: true` forces the Responses → Chat bridge. Already widely deployed and pip-installable.

```yaml
# litellm-config.yaml
model_list:
  - model_name: vllm-mlx
    litellm_params:
      model: openai/JANGQ-AI/Qwen3.6-27B-JANG_4M
      api_base: http://192.168.31.4:8000/v1
      api_key: not-needed
      use_chat_completions_api: true
```

```bash
litellm --config litellm-config.yaml --port 8201
```

Docs: <https://docs.litellm.ai/docs/response_api>.

### Caveats common to both shims

- **No hosted tools.** A shim cannot conjure `web_search_preview` — the closest local substitute is wiring the request through Remote MCP (LM Studio path) or doing client-side function calling.
- **Reasoning items lossy.** Chat Completions has no first-class `reasoning` item; shims usually fold model-emitted `<think>…</think>` into `output[].type=="reasoning"` heuristically. Quality varies by model.
- **`previous_response_id` requires the shim to store state.** Both projects do, but you give up the ability to scale the shim horizontally without sticky sessions or shared state.

## Recipe: `openai-cli` against vllm-mlx via shim

For agent-loop recipes (custom function tools, Remote MCP browser, hosted tools against real OpenAI), see [`openai-agent-tooling.md`](openai-agent-tooling.md). This section keeps just the protocol-shape recipe — proving Responses semantics work against a Chat-Completions-only server once you put a shim in front of it.

```bash
# 1. Run the shim
docker run -p 8200:8200 chutesai/responses-proxy \
  --upstream-base-url http://192.168.31.4:8000/v1

# 2. Talk Responses to the shim
openai response create \
  --base-url http://localhost:8200/v1 \
  --model JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --input "ping"
```

`previous_response_id` works (shim stores state); typed event stream works; hosted tools do not (no shim can implement them).

## References

### OpenAI platform docs

- [Responses API reference](https://platform.openai.com/docs/api-reference/responses) — endpoint spec for `/v1/responses`
- [Responses streaming events catalog](https://platform.openai.com/docs/api-reference/responses-streaming) — every typed SSE event (`response.output_text.delta`, `response.function_call_arguments.delta`, …)
- [Chat Completions reference](https://platform.openai.com/docs/api-reference/chat) — legacy `/v1/chat/completions` for comparison
- [Responses vs Chat Completions](https://platform.openai.com/docs/guides/responses-vs-chat-completions) — feature/cost comparison from OpenAI
- [Migrate to the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses) — Chat Completions → Responses migration walkthrough
- [Hosted tools index](https://developers.openai.com/api/docs/guides/tools) — gateway page for `web_search`, `file_search`, `code_interpreter`, `computer_use`
- [Web search tool guide](https://developers.openai.com/api/docs/guides/tools-web-search) — `web_search_preview` request shape and citations
- [Models API reference](https://platform.openai.com/docs/api-reference/models) — `/v1/models` list + retrieve
- [Realtime API reference](https://platform.openai.com/docs/api-reference/realtime) — adjacent low-latency surface (WebSocket / WebRTC)
- [Agents SDK (Python) docs site](https://openai.github.io/openai-agents-python/) — multi-agent orchestration framework canonical docs
- [OpenAI Cookbook: Responses + web search example](https://cookbook.openai.com/examples/responses_api/responses_example) — runnable hosted-tool flow

### Local server runbooks (this repo)

- [`docs/servers/lm-studio/summary.md`](../servers/lm-studio/summary.md) — only lab server with native Responses today
- [LM Studio Responses API docs](https://lmstudio.ai/docs/developer/openai-compat/responses) — vendor docs for the lab's only native implementation
- [LM Studio v0.3.29 / OpenResponses launch](https://lmstudio.ai/blog/openresponses) — version that shipped `/v1/responses`
- [vLLM Responses client example](https://docs.vllm.ai/en/latest/examples/online_serving/openai_responses_client/) — mainline vLLM (NOT the `vllm-mlx` MLX backend fork)

### Community analysis

- [Simon Willison — Responses vs Chat Completions](https://simonwillison.net/2025/Mar/11/responses-vs-chat-completions/) — best-known third-party walkthrough at launch
- [Sean Goedecke — Responses API hides reasoning traces](https://www.seangoedecke.com/responses-api/) — critical analysis of design motivations
- [OpenAI Developer Community — launch thread (Responses + tools + Agents SDK)](https://community.openai.com/t/new-tools-for-building-agents-responses-api-web-search-file-search-computer-use-and-agents-sdk/1140896) — canonical announcement
- [OpenAI Developer Community — token cost comparison](https://community.openai.com/t/responses-api-vs-completions-no-token-savings/1295425) — empirical price/token data
- [OpenAI Developer Community — Web search in Responses](https://community.openai.com/t/web-search-in-responses-api/1371488) — hosted `web_search` quirks in practice
- [Hacker News — Chat vs Responses split discussion](https://news.ycombinator.com/item?id=44052947) — long thread debating the API split

### Tracking issues for not-yet-implemented servers

- [llama.cpp #19138 — original Responses support tracker](https://github.com/ggml-org/llama.cpp/issues/19138)
- [llama.cpp #22389 — server tool-call format for Responses](https://github.com/ggml-org/llama.cpp/issues/22389) (current)
- [llama.cpp #19173 — Responses stream-cancel bug](https://github.com/ggml-org/llama.cpp/issues/19173)
- [Ollama #10309 — Responses API for Codex CLI](https://github.com/ollama/ollama/issues/10309)
- [Ollama #15921 — tool-call namespace parity](https://github.com/ollama/ollama/issues/15921)
- [Ollama #15635 — `reasoning_effort:"none"` ignored on `/v1/responses`](https://github.com/ollama/ollama/issues/15635)
- [Jan #7413 — blocked on llama.cpp](https://github.com/janhq/jan/issues/7413)
- [SGLang #15735 — `previous_response_id` w/ gpt-oss-120B](https://github.com/sgl-project/sglang/issues/15735)
- [SGLang #17853 — array-input compat gap](https://github.com/sgl-project/sglang/issues/17853)
- [vLLM #32850 — RFC: Open Responses API extensions](https://github.com/vllm-project/vllm/issues/32850) (canonical vLLM tracker)
- [vLLM #23218 — streaming ID alignment gap](https://github.com/vllm-project/vllm/issues/23218)
- [vLLM #27263, #39584 — open Responses bugs](https://github.com/vllm-project/vllm/issues/27263)
- [unsloth #5141 — Codex local llama.cpp Responses guide broken](https://github.com/unslothai/unsloth/issues/5141) — concrete Codex CLI ↔ local server failure case

### Shim/proxy projects (Responses → Chat Completions, or self-hosted Responses)

- [chutesai/responses-proxy](https://github.com/chutesai/responses-proxy) — Rust Responses → Chat Completions translator with full SSE event reconstruction
- [LiteLLM Responses bridge docs](https://docs.litellm.ai/docs/response_api)
- [LiteLLM provider-side Responses docs](https://docs.litellm.ai/docs/providers/openai/responses_api)
- [huggingface/responses.js](https://github.com/huggingface/responses.js) — express.js Responses-on-top-of-Chat-Completions, powered by HF Inference Providers
- [HF blog: Open Responses](https://huggingface.co/blog/open-responses) — write-up behind `responses.js`
- [open-responses/open-responses](https://github.com/open-responses/open-responses) — self-hosted Responses spec/server compatible with Agents SDK across Claude / R1 / Qwen / Ollama
- [OpenResponses open spec site](https://www.openresponses.org/) — HF-aligned open superset
- [mudler/LocalAGI](https://github.com/mudler/LocalAGI) — drop-in local Responses replacement aimed at consumer-grade hardware

### OpenAI SDKs and tooling

- [openai/openai-openapi](https://github.com/openai/openai-openapi) — public OpenAPI YAML spec for the entire OpenAI API (the source of truth)
- [openai/openai-cli](https://github.com/openai/openai-cli) — official CLI, Apache-2.0, Go, Responses-first
- [openai/openai-python](https://github.com/openai/openai-python) — official Python SDK
- [openai/openai-node](https://github.com/openai/openai-node) — official TypeScript / JavaScript SDK
- [openai/openai-go](https://github.com/openai/openai-go) — official Go SDK (the one `openai-cli` links against)
- [openai/openai-agents-python](https://github.com/openai/openai-agents-python) — multi-agent orchestration framework
- [openai/codex](https://github.com/openai/codex) — agentic coding CLI, requires `wire_api = "responses"`
- [openai/completions-responses-migration-pack](https://github.com/openai/completions-responses-migration-pack) — Codex-CLI-driven migration toolkit
- [openai/openai-cookbook](https://github.com/openai/openai-cookbook) — examples corpus including Responses recipes
- [openai/harmony](https://github.com/openai/harmony) — renderer for gpt-oss harmony response format (relevant to Responses framing)
- [openai/openai-realtime-agents](https://github.com/openai/openai-realtime-agents) — Realtime API agentic patterns demo

### This repo

- [`docs/clients/cli-prompt-clients.md`](../clients/cli-prompt-clients.md) — broader CLI prompt-client survey; explains why `openai-cli` is an honorable mention rather than a top-3 pick for this lab

## See also

- [`openai-agent-tooling.md`](openai-agent-tooling.md) — agent-loop angle: where the loop runs, custom function calling, Remote MCP / browser, hosted tools
- [`docs/clients/cli-prompt-clients.md`](../clients/cli-prompt-clients.md) — `llm` / `aichat` / `mods` for Chat-Completions one-shots
- [`docs/clients/opencode-setup.md`](../clients/opencode-setup.md) — agent harness over Chat Completions
- [`docs/servers/lm-studio/summary.md`](../servers/lm-studio/summary.md) — runbook for the only lab server with native Responses today
