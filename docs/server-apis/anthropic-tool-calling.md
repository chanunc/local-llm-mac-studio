# Anthropic Tool Calling: Quick Mental Model

*Last updated: 2026-06-05.*

Tool calling is a loop. A tool schema lets the model **ask** for work. A client or agent must still **do** the work.

## Index

| Section | Use it for |
|:--|:--|
| [The Whole Thing](#the-whole-thing) | One-screen mental model |
| [Terms](#terms) | What `tools`, `tool_use`, and `tool_result` mean |
| [Why `ant "Browse Hacker News"` Can Fail](#why-ant-browse-hacker-news-can-fail) | Why `ant` does not browse automatically |
| [`ant` Is Manual](#ant-is-manual) | Difference between API client and agent runner |
| [Example: Ask For A URL Fetch](#example-ask-for-a-url-fetch) | First `ant --tool` call |
| [Execute The Tool](#execute-the-tool) | Where the real fetch/shell/browser action happens |
| [Send The Result Back](#send-the-result-back) | Second call with `tool_result` |
| [Claude Code And OpenCode](#claude-code-and-opencode) | How agent CLIs automate the loop |
| [Fabric-Style Prompt Runners](#fabric-style-prompt-runners) | Why Fabric is usually one-shot |
| [This Lab's Router Path](#this-labs-router-path) | `ant -> ccr -> LM Studio` bridge |
| [Pick The Right Tool](#pick-the-right-tool) | Quick CLI choice table |
| [Bonus: `ant` With Anthropic Server Tools](#bonus-ant-with-anthropic-server-tools) | Hosted web/search/code tools on real Anthropic |

## The Whole Thing

```
Prompt + tool schemas
        |
        v
Model returns tool_use
        |
        v
Client runs the tool
        |
        v
Client sends tool_result
        |
        v
Model answers, or asks for another tool
```

The model does not browse, run shell, read files, or call HTTP directly. It emits a structured request. The client decides whether to execute it.

## Terms

| Thing | Meaning | Who does it? |
|:--|:--|:--|
| `tools` / `--tool` | Tool names, descriptions, and JSON input schemas | You provide this |
| `tool_use` | Model asks to call one tool with JSON args | Model returns this |
| `tool_result` | Output from the tool call | Client sends this back |
| Agent loop | Repeats `tool_use -> execute -> tool_result` | Claude Code / OpenCode / your script |

One-line version:

```
--tool defines the socket; tool_use plugs into it; tool_result carries the data back.
```

## Why `ant "Browse Hacker News"` Can Fail

```
Plain prompt only
  "Browse Hacker News"
        |
        v
Model has no web tool
        |
        v
"I cannot browse"
```

Adding `--tool` changes the first step, but `ant` still does not run the tool:

```
Prompt + fetch_url schema
        |
        v
Model: tool_use fetch_url({"url":"https://news.ycombinator.com/"})
        |
        v
ant stops and prints JSON
```

An agent CLI keeps going:

```
Claude Code / OpenCode
        |
        v
Model: tool_use
        |
        v
CLI executes tool
        |
        v
CLI sends tool_result
        |
        v
Model summarizes
```

## `ant` Is Manual

`ant` is an API client. It sends one request and prints one response.

```
ant = API tester
Claude Code / OpenCode = agent runner
Fabric-style prompt command = usually one-shot text transform
```

So with `ant`, you manually do both halves of the tool loop.

## Example: Ask For A URL Fetch

First request: give the model a tool schema and ask it to use the tool.

```bash
ANTHROPIC_API_KEY=not-needed ant --base-url http://192.168.31.4:3456 \
  --format json messages create \
  --model gemma-4-12b-q6k \
  --max-tokens 256 \
  --tool '{"name":"fetch_url","description":"Fetch a URL and return readable page text.","input_schema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}' \
  --message '{"role":"user","content":"Use fetch_url to browse Hacker News, then summarize the top stories."}'
```

Expected shape:

```json
{
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_123",
      "name": "fetch_url",
      "input": {
        "url": "https://news.ycombinator.com/"
      }
    }
  ],
  "stop_reason": "tool_use"
}
```

That means:

```
Model did not browse.
Model asked you to run fetch_url("https://news.ycombinator.com/").
```

## Execute The Tool

Manual test:

```bash
curl -L https://news.ycombinator.com/
```

Real integration:

```
parse tool_use
run fetch_url
capture output
send tool_result
repeat if needed
```

## Send The Result Back

The Anthropic Messages API is stateless. The second request must replay enough conversation for the model to understand what happened.

```
User: asked to browse Hacker News
Assistant: requested fetch_url(...)
User: here is tool_result(...)
```

Template:

```bash
ANTHROPIC_API_KEY=not-needed ant --base-url http://192.168.31.4:3456 \
  --format json messages create \
  --model gemma-4-12b-q6k \
  --max-tokens 512 \
  --tool '{"name":"fetch_url","description":"Fetch a URL and return readable page text.","input_schema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}' \
  --message '{"role":"user","content":"Use fetch_url to browse Hacker News, then summarize the top stories."}' \
  --message '{"role":"assistant","content":[{"type":"tool_use","id":"toolu_123","name":"fetch_url","input":{"url":"https://news.ycombinator.com/"}}]}' \
  --message '{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_123","content":"Fetched Hacker News page text goes here..."}]}'
```

Critical link:

```json
{
  "tool_use.id": "toolu_123",
  "tool_result.tool_use_id": "toolu_123"
}
```

The IDs match so the model knows which result belongs to which tool call.

## Claude Code And OpenCode

Same protocol idea, automated loop:

```
You ask task
    |
    v
Model emits tool_use
    |
    v
CLI checks permissions
    |
    v
CLI runs Bash / Read / Edit / browser / search
    |
    v
CLI sends tool_result
    |
    v
Model continues
```

That is why Claude Code and OpenCode can feel like they browse or edit directly. The CLI is doing the execution; the model is deciding what to request next.

## Fabric-Style Prompt Runners

Typical flow:

```
prompt/context -> model response
```

Not usually:

```
prompt -> tool_use -> execute tool -> tool_result -> continue
```

Treat Fabric-style commands as one-shot unless that exact workflow documents an executor loop.

## This Lab's Router Path

Tested path:

```
ant
  |
  v
claude-code-router :3456
  |
  v
LM Studio :1234 /v1/chat/completions
  |
  v
gemma-4-12b-q6k
```

Protocol translation:

```
Anthropic tools/tool_use/tool_result
        <->
OpenAI tools/tool_calls/tool messages
```

Smoke test:

```bash
ANTHROPIC_API_KEY=not-needed ant --base-url http://192.168.31.4:3456 \
  --format json messages create \
  --model gemma-4-12b-q6k \
  --max-tokens 128 \
  --tool '{"name":"get_weather","description":"Get weather for a city.","input_schema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}' \
  --message '{"role":"user","content":"Use the get_weather tool for London."}'
```

Good result:

```json
{
  "content": [
    {
      "type": "tool_use",
      "name": "get_weather",
      "input": {
        "city": "London"
      }
    }
  ],
  "stop_reason": "tool_use"
}
```

This proves structured tool-call translation works. It does not prove automatic tool execution, because `ant` does not execute tools.

## Pick The Right Tool

| Goal | Use |
|:--|:--|
| Inspect Anthropic request/response shape | `ant` |
| Manually test tool schema behavior | `ant --tool` |
| Build a custom tool loop | `ant` plus a script |
| Run coding/file/shell/browser loops | Claude Code or OpenCode |
| Run one-shot prompt transforms | Fabric-style prompt runner |

## Bonus: `ant` With Anthropic Server Tools

Anthropic also has hosted tools. These are different from client tools.

```
Client tool:
  model asks -> you execute -> you send tool_result

Server tool:
  model asks -> Anthropic executes -> model receives result in same API call
```

So this is the one case where `ant` can look more automatic.

Important boundary:

```
Real Anthropic API: server tools can work
Local ccr -> LM Studio: server tools do not exist there
```

Server tools use `type` instead of `input_schema`.

### Web Search

```bash
ANTHROPIC_API_KEY=sk-ant-... ant \
  --format json messages create \
  --model <claude-model-that-supports-web-search> \
  --max-tokens 1024 \
  --tool '{"type":"web_search_20250305","name":"web_search","max_uses":3}' \
  --message '{"role":"user","content":"Search the web and summarize the current top Hacker News stories."}'
```

Visual flow:

```
ant -> Anthropic API
        |
        v
Claude decides search query
        |
        v
Anthropic runs web_search
        |
        v
Claude answers with citations
```

### Web Fetch

Web fetch reads a URL the user provides, or a URL found by previous web search/fetch results.

```bash
ANTHROPIC_API_KEY=sk-ant-... ant \
  --format json messages create \
  --model <claude-model-that-supports-web-fetch> \
  --max-tokens 1024 \
  --tool '{"type":"web_fetch_20250910","name":"web_fetch","max_uses":3}' \
  --message '{"role":"user","content":"Fetch and summarize https://news.ycombinator.com/"}'
```

For beta server tools, the CLI may need a beta header:

```bash
ant beta:messages create \
  --beta web-fetch-2025-09-10 \
  ...
```

### Code Execution

Code execution runs inside Anthropic's sandbox, not on your Mac.

```bash
ANTHROPIC_API_KEY=sk-ant-... ant \
  --format json messages create \
  --model <claude-model-that-supports-code-execution> \
  --max-tokens 1024 \
  --tool '{"type":"code_execution_20250825","name":"code_execution"}' \
  --message '{"role":"user","content":"Run code to calculate the mean and standard deviation of [1,2,3,4,5,6,7,8,9,10]."}'
```

Rule of thumb:

| Tool kind | Runs where? | Works through local LM Studio bridge? |
|:--|:--|:--|
| Client tool with `input_schema` | Your script / agent CLI | Yes, if your client runs it |
| Anthropic server tool with `type` | Anthropic backend | No |

Refs: Anthropic docs for [web search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool), [web fetch](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool), and [code execution](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool).
