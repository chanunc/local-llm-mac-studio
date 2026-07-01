# Gemma4-12B Agentic v2 Q8_0 + TurboQuant: OpenCode Failure Triage

Date: 2026-06-24

## Setup

- Model: `yuxinlu1/gemma-4-12B-agentic-fable5-composer2.5-v2-3.5x-tau2-GGUF`
- File: `gemma4-v2-Q8_0.gguf`
- Server: `llama-cpp-turboquant` :8099, TheTom fork `69d8e4b`
- Launch: `--cache-type-k turbo3 --cache-type-v turbo3 -ngl 99 -fa on -c 262144 --jinja --reasoning on`
- OpenCode model: `macstudio-llama-cpp-turboquant/gemma4-12b-agentic-v2-q8-turbo3-256k`

## API Layer

The direct OpenAI-compatible tool-call smoke is clean:

- Single-call pass rate: 5/5
- Multi-turn loop: 3 turns / 6.99 s
- Finish reason: `tool_calls` for all single-call scenarios

This rules out a basic llama.cpp Gemma 4 parser or `tools[]` transport failure.

## Agent Failure Signature

OpenCode end-to-end is unstable:

| Scenario | Median | Signature |
|:--|--:|:--|
| Browse `www.example.com` | 300.02 s | 2/3 measured runs hit OpenCode's 300 s wall. Runs repeatedly called `webfetch`, then drifted into `write`, `bash`, `read`, `glob`, and `edit`. |
| Browse Hacker News latest topic | 69.40 s | Completed 3/3 but used 7-8 turns with repeated `webfetch` and extra `skill`, `read`, `bash`, `task`, `glob`. |

The model does call web tools, but it does not stop efficiently after gathering enough information. The failure is an agent-policy / loop-control mismatch, not an API parser failure.

## Interpretation

This model is viable for direct API tool calls and local coding-style experiments, but it is not a good OpenCode backend as configured. The fine-tune's "read / reason / act / verify" bias appears to over-expand simple browse tasks into repeated verification and local workspace inspection.

## Follow-Up Options

- Test with `--reasoning off` or a bounded `--reasoning-budget` to see whether the loop-control issue improves.
- Compare LM Studio or stock mainline llama.cpp on the same GGUF to separate TheTom server behavior from model policy.
- Run a scaffolded OpenCode prompt variant that explicitly says "fetch once, summarize, and stop" before rejecting the model for all agent use.
