# Server API Surfaces

Wire-protocol references for the HTTP APIs that the Mac Studio servers serve and that the lab's clients target. These are protocol-shape docs — what the request/response JSON looks like, which servers implement which surface, and what the gaps are. Pair with [`docs/servers/`](../servers/) (per-server runbooks) and [`docs/clients/`](../clients/) (per-client setup).

| API | Doc | Status in this lab |
|:--|:--|:--|
| OpenAI Responses API (`POST /v1/responses`) | [`openai-responses.md`](openai-responses.md) | Native only on `lm-studio:1234` (≥ v0.3.29). Six other servers are Chat-Completions-only — shim with [`chutesai/responses-proxy`](https://github.com/chutesai/responses-proxy) or LiteLLM. |
| Agent tooling with the Responses API | [`openai-agent-tooling.md`](openai-agent-tooling.md) | Where the loop runs (client vs server vs OpenAI infra), Remote MCP browser recipes, function-calling loop, hosted tools. |

## When to add a new doc here

Add a new `*.md` here when a wire-protocol surface needs cross-cutting treatment that doesn't fit cleanly under a single server's runbook or a single client's setup doc — typically when:

- Multiple lab servers implement (or fail to implement) the same surface and a comparison matrix is useful.
- Clients in `docs/clients/` need to know which lab servers they can target.
- Shim/proxy projects exist to bridge the surface to Chat Completions (or to another protocol).

Candidate future entries: OpenAI Chat Completions, Anthropic Messages API, Ollama API, OpenAI Realtime, Assistants v2 (deprecated path).

Update the table above and add a row to the [Sub-root README index](../../CLAUDE.md#canonical-layers-and-where-they-live) row in `CLAUDE.md` / `AGENTS.md` if you create a new `docs/server-apis/<file>.md`.
