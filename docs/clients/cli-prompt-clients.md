# CLI Prompt Clients (OpenAI HTTP path)

Lightweight CLIs for sending one-shot prompts to the Mac Studio servers over their **OpenAI-compatible HTTP API**. Use these when an agent harness (OpenCode, OpenClaw, Pi, Claude Code) is the wrong tool — non-agent models like `sulphur-2-base` (T2V prompt rewriter, 8 K context), interactive smoke tests, ad-hoc rewrites, shell pipelines.

*Last updated: 2026-05-07.*

## Index
- [Why these tools](#why-these-tools)
- [Top 3 recommended](#top-3-recommended)
  - [llm (Simon Willison) — pick this for scripting](#llm-simon-willison--pick-this-for-scripting)
  - [aichat — pick this for a single-binary install](#aichat--pick-this-for-a-single-binary-install)
  - [mods (Charmbracelet) — pick this for shell pipes](#mods-charmbracelet--pick-this-for-shell-pipes)
- [Honorable mentions](#honorable-mentions)
- [Skipped (wrong fit)](#skipped-wrong-fit)
- [Decision matrix](#decision-matrix)
- [When to reach for `lms chat -p` instead](#when-to-reach-for-lms-chat--p-instead)

## Why these tools

`lms chat -p` (the LM Studio CLI) is the shortest path to talk to a loaded LM Studio model, but it goes over LM Studio's **native SDK** (Unix-socket-style protocol), not the OpenAI HTTP endpoint. That's fine for LM Studio alone, but the Mac Studio also runs vllm-mlx, mlx-openai-server, oMLX, vmlx, dflash-mlx, and llama-cpp-turboquant — all of which speak the OpenAI HTTP API on port 8000 / 8098 / 1234 and **none** of which `lms` can talk to.

An OpenAI-API-only CLI that takes `OPENAI_BASE_URL` (or per-provider config) covers every server in this lab without touching agent harnesses or hand-building `curl` JSON.

It also dodges the agent-system-prompt problem. `opencode run` injects ~12 K tokens of "you are a coding agent, here are your tools…" before the user message, which overflows narrow-context models like Sulphur-2-base (8 K). A bare-bones OpenAI CLI sends only what you typed.

## Top 3 recommended

### `llm` (Simon Willison) — pick this for scripting

```bash
brew install llm
```

Bridge LM Studio (or any OpenAI-compat host) by adding it to `extra-openai-models.yaml`:

```bash
mkdir -p "$HOME/Library/Application Support/io.datasette.llm"
cat >> "$HOME/Library/Application Support/io.datasette.llm/extra-openai-models.yaml" <<'EOF'
- model_id: sulphur
  model_name: sulphur-2-base
  api_base: "http://192.168.31.4:1234/v1"
- model_id: gemma4
  model_name: gemma-4-26b-a4b-q8
  api_base: "http://192.168.31.4:1234/v1"
EOF
```

Then:

```bash
llm -m sulphur "a cat dancing"           # one-shot
llm -m sulphur -s "Rewrite as LTX-2.3 prompt" "a cat dancing"  # system prompt
echo "summarise" | llm -m gemma4         # stdin pipe
llm -c "make it 2× longer"               # follow-up in last conversation
llm logs -n 1                            # inspect last call (tokens, JSON)
```

| Trait | Notes |
|:--|:--|
| Streams | yes (default) |
| System prompt | `-s "..."` |
| Stdin | yes |
| Multi-turn | `-c` continues last conversation; SQLite-logged |
| Plugins | rich ecosystem (`llm-anthropic`, `llm-tools-*`) |
| License | Apache-2.0 |
| Last release | v0.31, 2026-04-24 |

**Why first:** `extra-openai-models.yaml` is the cleanest LM-Studio bridge in the field. Conversation logs as SQLite. Best Unix-tool feel.

### `aichat` — pick this for a single-binary install

```bash
brew install aichat
```

Config at `~/.config/aichat/config.yaml`:

```yaml
clients:
  - type: openai-compatible
    name: lmstudio
    api_base: http://192.168.31.4:1234/v1
    api_key: not-needed
```

Then:

```bash
aichat -m lmstudio:sulphur-2-base "a cat dancing"
aichat                                   # REPL
echo "explain" | aichat -m lmstudio:gemma-4-26b-a4b-q8
```

| Trait | Notes |
|:--|:--|
| Streams | yes |
| System prompt | `--prompt` / `-r <role>` (saved roles) |
| Stdin | yes |
| Multi-turn | sessions via REPL |
| RAG / agents | built-in (heavier than `llm`) |
| License | Apache-2.0 / MIT |
| Last release | v0.30.0, 2025-07-06 |

**Why second:** single static Rust binary, no Python toolchain. The `provider:model` syntax matches naturally when LM Studio holds multiple identifiers at once (e.g. `gemma-4-26b-a4b-q8` and `sulphur-2-base` simultaneously, see `lms ps`).

### `mods` (Charmbracelet) — pick this for shell pipes

```bash
brew install mods
mods --settings   # opens ~/.config/mods/mods.yml
```

Add an API entry under `apis:`:

```yaml
apis:
  lmstudio:
    base-url: http://192.168.31.4:1234/v1
    models:
      sulphur-2-base:
        max-input-chars: 30000
      gemma-4-26b-a4b-q8:
        max-input-chars: 400000
```

Then:

```bash
mods -a lmstudio -m sulphur-2-base "a cat dancing"
git diff | mods -a lmstudio -m gemma-4-26b-a4b-q8 "review"
mods -C                                  # continue last conversation
```

| Trait | Notes |
|:--|:--|
| Streams | yes (animated render) |
| System prompt | `-r <role>` (saved in settings) |
| Stdin | first-class (built for pipes) |
| Multi-turn | `-c <name>` / `-C` |
| Rendering | Glamour markdown |
| License | MIT |
| Last release | v1.8.1, 2025-07-10 |

**Why third:** best at `<thing> | mods "..."` shell composition. Glamour rendering is a quality-of-life win over raw stdout when the answer is markdown.

## Honorable mentions

- **`shell-gpt` / `sgpt`** — `pipx install shell-gpt`; set `API_BASE_URL` and `DEFAULT_MODEL` in `~/.config/shell_gpt/.sgptrc`. MIT, v1.5.1 (2026-05-06), 12k stars. Solid; Python-heavy and biased toward "generate shell command" use cases.
- **`gptme`** — agentic CLI (file ops, exec) with custom-provider support in `~/.config/gptme/config.toml`. Pick if you want a coding agent rather than a one-liner. Heavier than the rest.
- **`tgpt`** — GPL-3.0, v2.11.1 (2026-02-01). Custom-provider support exists but config is awkward.

## Skipped (wrong fit)

- **`ollama` CLI** — only talks to its own daemon, cannot point at LM Studio's port 1234.
- **`chatblade`** — not maintained recently.
- **`codex` / `gptme`** — agents, not prompt tools (mentioned twice — `gptme` is on the fence; `codex` is firmly an agent harness).
- **`opencode run`** — agent harness; injects ~12 K-token system prompt that overflows narrow-context models. Use only when you want tool calls.

## Decision matrix

| You want… | Reach for |
|:--|:--|
| One-shot prompt, scripting, conversation history in SQLite | `llm` |
| Single binary on a fresh machine, no Python | `aichat` |
| Pipe `git diff` / `cat log` / `kubectl logs` into a model | `mods` |
| Shell-command suggestions (`how do I tar this?`) | `sgpt` |
| Agent loop with tools, file edits, browse | `opencode` (see [opencode-setup.md](opencode-setup.md)) |
| Talk to LM Studio's loaded model via its native SDK, no HTTP | `lms chat -p` |
| Raw debugging of request/response shape | `curl` |

## When to reach for `lms chat -p` instead

`lms chat -p` is still the right answer when:
- The target model is loaded in LM Studio specifically (not vllm-mlx / oMLX / vmlx).
- You don't need OpenAI-specific knobs (`tools`, `response_format`, `stream` toggle, exact `usage` counters).
- You're on the Mac Studio itself and want to skip the network hop.

Use the OpenAI-API CLIs above when you need any of:
- Talking to a non-LM-Studio server (port 8000 / 8098).
- `temperature`, `top_p`, `tools`, `response_format`, streaming control, `usage` block.
- Conversation logs persisted on the client (SQLite via `llm`, sessions via `aichat`/`mods`).
- Cross-machine usage from a MacBook / Linux client where `lms` isn't installed.

## See also

- [`opencode-setup.md`](opencode-setup.md) — agent harness for tool-using models.
- [`opencode-analysis.md`](opencode-analysis.md) — OpenCode latency overhead vs raw API.
- [`docs/servers/lm-studio/summary.md`](../servers/lm-studio/summary.md) — LM Studio runbook (port 1234).
- [`docs/models/uncen-model/eval/prompt_enhancer_harness.py`](../models/uncen-model/eval/prompt_enhancer_harness.py) — example of bypassing agent harnesses for narrow-context models, the pattern these CLIs simplify.
