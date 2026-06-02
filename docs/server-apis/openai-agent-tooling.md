# Agent tooling against the OpenAI Responses API

Where the agent loop actually runs (server, CLI, or your code), what `openai-cli` does and doesn't do, and how to drive browser-style agency from the CLI against the lab's LM Studio server. Companion piece to [`openai-responses.md`](openai-responses.md), which covers the protocol shape itself.

*Last updated: 2026-05-08.*

## TL;DR

- `openai-cli` is **not** an agent harness — it sends one request, prints the typed `output[]`, exits. If the response contains a `function_call` item, **your code** dispatches it; the CLI does not loop.
- For real agent loops:
  - **Real OpenAI API**: use [`openai/codex`](https://github.com/openai/codex) (Responses-native, hosted tools work out of the box).
  - **LM Studio + browser-style agency**: pair `openai-cli` with a **Remote MCP** server (e.g. `playwright-mcp`). LM Studio runs the loop server-side; the CLI just prints the final state.
  - **The other six lab servers**: keep using `opencode` / `claude-code` over Chat Completions — they implement the function-calling loop client-side, which is what every `configs/clients/<server>/opencode.json` template already does.
- Hosted tools (`web_search_preview`, `file_search`, `code_interpreter`, `computer_use_preview`) execute on OpenAI's backend and **do not** work against any local server. The local substitute is Remote MCP on LM Studio.

## Where does the agent loop live?

| | `openai-cli` | `codex` (OpenAI's agent CLI) | `opencode` / `claude-code` |
|:--|:--|:--|:--|
| Tool-call loop | ❌ | ✅ | ✅ |
| Local browser / shell exec | ❌ | ✅ (sandbox + browser) | ✅ |
| Multi-turn agent | server-side only via `previous_response_id` | ✅ | ✅ |
| File-edit loop | ❌ | ✅ | ✅ |
| Wire API | Responses (or Chat Completions) | Responses (`wire_api = "responses"`) | Chat Completions |
| Loop runs on | nowhere — single shot | client (the CLI process) | client |

`openai-cli` is auto-generated from the OpenAI OpenAPI spec — every API verb gets a subcommand, but no agent loop is bolted on top. That's by design: it's a CLI for *exercising the API*, not for *running an agent*. The agentic primitives the Responses API exposes (`previous_response_id` continuation, `function_call` items, `mcp_tool_call` items, hosted tools) all still work — but you wire the loop yourself, or you delegate to a server (LM Studio Remote MCP) or to `codex`.

## Three loop topologies

```
┌─────────────────────────────────────────────────────────────────────┐
│ A. Loop runs in YOUR CODE (Chat Completions function calling)       │
│                                                                      │
│   you → openai-cli ─── Chat Completions ───→ vllm-mlx / LM Studio   │
│    ↑           │                                  │                  │
│    └───────────┴───── tool exec (your code) ─────┘                  │
│                                                                      │
│   What `opencode`/`claude-code` already do for the six lab servers. │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ B. Loop runs on the SERVER (Responses + Remote MCP, LM Studio path) │
│                                                                      │
│   you → openai-cli ─── Responses ───→ LM Studio :1234               │
│                                            │                         │
│                                            └─→ Remote MCP server     │
│                                                  (playwright-mcp,    │
│                                                   firecrawl-mcp …)   │
│                                                                      │
│   CLI is single-shot; LM Studio drives tool calls until completion. │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ C. Loop runs on the CLI (codex / opencode / claude-code)            │
│                                                                      │
│   you → codex ─── Responses ───→ api.openai.com                     │
│            │           │                                             │
│            │           └─── hosted tools execute on OpenAI infra    │
│            │                                                         │
│            └── local sandbox: shell, file edits, browser            │
│                                                                      │
│   Native fit for real OpenAI; codex against local servers needs a   │
│   Responses backend (LM Studio :1234, or shim per openai-responses).│
└─────────────────────────────────────────────────────────────────────┘
```

## Recipe 1: client-side function calling with `openai-cli`

You stay in the loop. The CLI is just a JSON poster.

```bash
brew install openai/tools/openai

# Step 1: ask the model — it will emit a function_call item if needed
openai response create \
  --base-url http://192.168.31.4:1234/v1 \
  --model gemma-4-26b-a4b-q8 \
  --input "What's the weather in SF?" \
  --tools '[{
    "type": "function",
    "name": "get_weather",
    "description": "Get current weather for a city",
    "parameters": {
      "type": "object",
      "properties": {"city": {"type": "string"}},
      "required": ["city"]
    }
  }]'
```

The response `output[]` contains a `function_call` item with `name`, `arguments`, `call_id`. **Your code** executes `get_weather`, then continues:

```bash
# Step 2: feed the tool result back, referencing the prior response
openai response create \
  --base-url http://192.168.31.4:1234/v1 \
  --model gemma-4-26b-a4b-q8 \
  --previous-response-id resp_abc123 \
  --input '[{
    "type": "function_call_output",
    "call_id": "call_xyz789",
    "output": "{\"temp_f\": 62, \"condition\": \"foggy\"}"
  }]'
```

Repeat until the model emits a final `message` item instead of another `function_call`. `openai-cli` won't write that loop for you — but `previous_response_id` saves you from resending the full history each turn (Chat Completions' weakness).

## Recipe 2: server-side loop via Remote MCP (LM Studio + browser)

You hand the loop to LM Studio. The CLI fires once and prints the finished `output[]`.

Prereqs:
1. LM Studio ≥ 0.3.29 (any model loaded; Gemma 4 family in this lab works well).
2. Remote MCP enabled — Developer → Settings → Remote MCP → toggle on.
3. An MCP server you trust. `playwright-mcp` for browser; `firecrawl-mcp` for web scrape; `mcp-server-fetch` for plain HTTP.

```bash
# 1. Start the MCP browser server
npx @playwright/mcp@latest --port 3001 &

# 2. Ask via openai-cli — model decides whether to call browser tools
openai response create \
  --base-url http://192.168.31.4:1234/v1 \
  --model gemma-4-26b-a4b-q8 \
  --input "Browse https://news.ycombinator.com and summarize the top 3 stories" \
  --tools '[{"type":"mcp","server_url":"http://localhost:3001/sse"}]'
```

The returned `output[]` contains a sequence of `mcp_tool_call` items (`browser_navigate`, `browser_snapshot`, `browser_click`, …) followed by a final `message` item with the summary. The CLI never touched the browser; LM Studio drove the loop and only handed the final state back.

Useful Remote MCP servers in practice:

| Server | Use for | Repo / npm |
|:--|:--|:--|
| `@playwright/mcp` | Real browser (DOM, screenshot, click) | <https://github.com/microsoft/playwright-mcp> |
| `firecrawl-mcp` | Web scrape + Markdown extraction at scale | <https://github.com/mendableai/firecrawl-mcp-server> |
| `mcp-server-fetch` | Plain HTTP GET → markdown | <https://github.com/modelcontextprotocol/servers/tree/main/src/fetch> |
| `mcp-server-filesystem` | Local file read/write | <https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem> |
| `mcp-server-git` | git status/log/diff/blame | <https://github.com/modelcontextprotocol/servers/tree/main/src/git> |

LM Studio caveats:
- The MCP server has to be reachable from the LM Studio process (same machine, or accessible URL). For lab use, run it on the Mac Studio itself or expose it over the LAN.
- Tool calls are server-side: LM Studio sees and dispatches them. If you need an audit log, capture LM Studio's request log, not the CLI's.
- No streaming progress on the CLI side — `openai-cli` blocks until the loop finishes. Add `--format jsonl` or watch `tail -f /tmp/lmstudio.log` if you want intermediate visibility.

## Recipe 3: hosted tools against real OpenAI

Reference only — none of the lab servers implement these. Included so the contrast is concrete.

```bash
export OPENAI_API_KEY=sk-...

# Web search — runs on OpenAI's backend
openai response create \
  --model gpt-5 \
  --input "What launched at OpenAI DevDay 2026?" \
  --tools '[{"type":"web_search_preview"}]'

# Code interpreter — sandboxed Python on OpenAI's backend
openai response create \
  --model gpt-5 \
  --input "Compute the SHA256 of the string 'hello world' and verify against 7509e..." \
  --tools '[{"type":"code_interpreter","container":{"type":"auto"}}]'

# File search — RAG over a vector store on OpenAI's backend
openai response create \
  --model gpt-5 \
  --input "What does our refund policy say about lost packages?" \
  --tools '[{"type":"file_search","vector_store_ids":["vs_abc123"]}]'
```

The agent loop here lives on OpenAI's infrastructure. `openai-cli` is still single-shot from the client's perspective; what's different is that one request can fan out into many internal tool-call rounds before you see the response. For local equivalents see Recipe 2 (LM Studio Remote MCP) or use [`opencode`](../clients/opencode-setup.md) / `claude-code` against any of the lab's Chat-Completions servers.

## When to reach for which CLI

| You want… | Reach for | Wire API |
|:--|:--|:--|
| One-shot prompt, no loop | `openai-cli`, `llm`, `aichat`, `mods` | Chat Completions or Responses |
| Browser/scrape against a local model | `openai-cli` + Remote MCP on LM Studio | Responses |
| Coding agent against real OpenAI | `codex` | Responses |
| Coding agent against local lab servers | `opencode`, `claude-code` | Chat Completions |
| Custom function-calling loop in your script | any Chat Completions or Responses client; `openai-python` recommended | either |
| Multi-agent orchestration | `openai/openai-agents-python` (Responses) | Responses |

## See also

- [`openai-responses.md`](openai-responses.md) — protocol shape, local server support matrix, shim path
- [`../clients/cli-prompt-clients.md`](../clients/cli-prompt-clients.md) — broader CLI prompt-client survey
- [`../clients/opencode-setup.md`](../clients/opencode-setup.md) — agent harness over Chat Completions for the six non-Responses lab servers
- [`../servers/lm-studio/summary.md`](../servers/lm-studio/summary.md) — runbook for the only lab server with native Responses + Remote MCP
- [openai/codex](https://github.com/openai/codex) — OpenAI's official agentic CLI, requires `wire_api = "responses"`
- [openai/openai-agents-python](https://github.com/openai/openai-agents-python) — multi-agent orchestration framework
- [Model Context Protocol — server registry](https://github.com/modelcontextprotocol/servers) — canonical list of MCP servers
- [LM Studio Remote MCP docs](https://lmstudio.ai/docs/developer/openai-compat/responses) — vendor docs for the LM Studio path
