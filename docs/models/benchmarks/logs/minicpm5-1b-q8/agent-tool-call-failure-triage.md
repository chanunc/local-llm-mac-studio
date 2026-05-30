# MiniCPM5-1B Q8_0 Tool-Call Failure Triage

Date: 2026-05-30

## Failure Signature

| Field | Value |
|:--|:--|
| Model repo | `openbmb/MiniCPM5-1B-GGUF` |
| GGUF | `MiniCPM5-1B-Q8_0.gguf` |
| Server | `lm-studio` / LM Studio headless, port `1234` |
| API identifier | `minicpm5-1b-q8` |
| Context | `131072` |
| Smoke artifact | [`api-tool-test.json`](api-tool-test.json) |

API tool-call smoke failed before OpenCode was involved:

| Scenario | Time | Finish | Tool calls |
|:--|--:|:--|--:|
| Single tool (file read) | 4.48 s | `length` | 0 |
| Single tool (command) | 0.19 s | `stop` | 0 |
| Multi-tool (search + read) | 4.19 s | `length` | 0 |
| Multi-tool (list + read + write) | 0.34 s | `stop` | 0 |
| Agentic reasoning | 0.36 s | `stop` | 0 |

Single-call pass rate: **0/5**. Multi-turn aborted on turn 1 with `tools=[]`.

## Direct Probe

A direct `/v1/chat/completions` request with a single `run_command` tool returned no OpenAI `tool_calls`. LM Studio placed the model output in `reasoning_content`, and the content referenced MiniCPM-style `[TOOL_REQUEST]` examples rather than emitting structured OpenAI tool calls.

This confirms the failure is at the model-template/parser layer, not in `bench_agent_tool_call.py` or OpenCode.

## Related Upstream Finding

The model card's [Tool Calling](https://huggingface.co/openbmb/MiniCPM5-1B-GGUF#tool-calling) section explains the observed failure mode: MiniCPM5-1B emits XML-style tool calls, and SGLang is the recommended backend because its built-in `minicpm5` parser converts those calls to OpenAI-compatible `tool_calls`.

The card lists LM Studio as a GGUF deployment/runtime option, but the tool-calling section does not say LM Studio parses MiniCPM5 tool calls. The local smoke result matches that gap: LM Studio can load and generate with the GGUF, but it does not expose MiniCPM5 tool calls as OpenAI `tool_calls`.

## Recommended Next Steps

1. Do not add MiniCPM5-1B Q8_0 to the agent-capable lm-studio roster yet.
2. Re-test on SGLang with `--tool-call-parser minicpm5` before documenting agent-loop benchmarks.
3. If staying on GGUF/LM Studio, treat the model as a fast text-generation probe only unless LM Studio adds MiniCPM5 parser support.

## Follow-up: SGLang

SGLang source install on the Mac Studio succeeded, but the exact Q8_0 GGUF did not load under SGLang's Apple/MLX backend: the MLX runner delegated to `mlx_lm.load()` and expected a model directory with `config.json`, not a `.gguf` file.

The SGLang-supported HF checkpoint path (`openbmb/MiniCPM5-1B`, `SGLANG_USE_MLX=1`, `--tool-call-parser minicpm5`) did run and passed the API tool harness in No Think mode (`chat_template_kwargs={"enable_thinking": false}`): **5/5**, 3-turn loop in **0.78 s**. OpenCode browse was stable at **7.28 s** median; OpenCode search had two normal runs around **10.4 s** and one 300 s timeout.

See [`../minicpm5-1b-sglang/summary.md`](../minicpm5-1b-sglang/summary.md).

## Reproducer

```bash
curl -s http://<MAC_STUDIO_IP>:1234/v1/chat/completions \
  -H 'Content-Type: application/json' \
  --data '{
    "model": "minicpm5-1b-q8",
    "messages": [{"role": "user", "content": "Run uptime to check system status"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "run_command",
        "description": "Run a shell command",
        "parameters": {
          "type": "object",
          "properties": {"command": {"type": "string"}},
          "required": ["command"]
        }
      }
    }],
    "tool_choice": "auto",
    "max_tokens": 256
  }'
```
