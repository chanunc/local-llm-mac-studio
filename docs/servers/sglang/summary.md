# SGLang Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Starting the server](#starting-the-server)
- [Health check](#health-check)
- [MiniCPM5 tool calling](#minicpm5-tool-calling)
- [Benchmarks](#benchmarks)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`sglang` is an OpenAI-compatible serving runtime with per-family tool-call parsers. In this lab it is a **provisional Apple-Silicon / MLX sidecar** on port **30000**, added to test MiniCPM5's `minicpm5` tool-call parser.

The local install lives at:

| Path | Purpose |
|:--|:--|
| `~/sglang/` | source checkout from `sgl-project/sglang` |
| `~/sglang/sglang-mps/` | Python 3.11 virtualenv |
| `/tmp/sglang-minicpm5.log` | launch log for the MiniCPM5 probe |

SGLang is useful here when the model emits a tool-call format that LM Studio or `llama.cpp` does not parse into OpenAI `tool_calls[]`. MiniCPM5 is the current example: LM Studio can load the Q8_0 GGUF, but it does not expose MiniCPM5 XML tool calls as structured OpenAI tool calls.

## Architecture

```
MacBook / Linux / WSL              Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────────┐             ┌──────────────────────────────────────────────┐
│ OpenCode            │── LAN ────>│ SGLang (port 30000, OpenAI /v1)              │
│ bench_api_tool_call │             │   SGLANG_USE_MLX=1                           │
│ bench_api_server    │             │   --tool-call-parser minicpm5                │
└────────────────────┘             │   model: openbmb/MiniCPM5-1B HF checkpoint   │
                                   └──────────────────────────────────────────────┘
```

## Installation

The Apple-Silicon path is source-based and uses Python 3.11:

```bash
ssh macstudio "/opt/homebrew/bin/brew install uv"
ssh macstudio "git clone https://github.com/sgl-project/sglang.git ~/sglang"
ssh macstudio "cd ~/sglang && /opt/homebrew/bin/uv venv -p /opt/homebrew/bin/python3.11 sglang-mps"
ssh macstudio "cd ~/sglang && . sglang-mps/bin/activate && \
  /opt/homebrew/bin/uv pip install --upgrade pip && \
  if [ -f python/pyproject_other.toml ]; then rm -f python/pyproject.toml && mv python/pyproject_other.toml python/pyproject.toml; fi && \
  /opt/homebrew/bin/uv pip install -e 'python[all_mps]'"
```

The install includes `mlx`, `mlx-lm`, `torch`, `transformers`, and SGLang's OpenAI server.

## Starting the server

MiniCPM5 route verified locally:

```bash
ssh macstudio "cd ~/sglang && . sglang-mps/bin/activate && \
  nohup env SGLANG_USE_MLX=1 python -m sglang.launch_server \
    --model-path openbmb/MiniCPM5-1B \
    --tool-call-parser minicpm5 \
    --host 0.0.0.0 --port 30000 \
    > /tmp/sglang-minicpm5.log 2>&1 &"
```

Stop:

```bash
ssh macstudio "pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'"
```

Logs:

```bash
ssh macstudio "tail -f /tmp/sglang-minicpm5.log"
```

## Health check

```bash
curl -s http://<MAC_STUDIO_IP>:30000/v1/models | python3 -m json.tool
```

Expected MiniCPM5 shape:

```json
{
  "data": [
    {
      "id": "openbmb/MiniCPM5-1B",
      "owned_by": "sglang",
      "max_model_len": 131072
    }
  ]
}
```

## MiniCPM5 tool calling

MiniCPM5 emits XML-style tool calls. The model card recommends SGLang's `minicpm5` parser for OpenAI-compatible tool calling.

Use **No Think mode** for the API tool-call harness:

```bash
python3 scripts/bench/bench_api_tool_call.py \
  --base-url http://<MAC_STUDIO_IP>:30000/v1 \
  --model openbmb/MiniCPM5-1B \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --output docs/models/benchmarks/logs/minicpm5-1b-sglang/api-tool-test-no-think.json
```

Without `chat_template_kwargs`, MiniCPM5 only partially passed the local smoke harness. With `{"enable_thinking": false}`, it passed **5/5** single-call scenarios and the 3-turn read/write loop.

## Benchmarks

Raw artifacts:

- [`../../models/benchmarks/logs/minicpm5-1b-sglang/api-tool-test-no-think.json`](../../models/benchmarks/logs/minicpm5-1b-sglang/api-tool-test-no-think.json)
- [`../../models/benchmarks/logs/minicpm5-1b-sglang/api-server-sglang.json`](../../models/benchmarks/logs/minicpm5-1b-sglang/api-server-sglang.json)
- [`../../models/benchmarks/logs/minicpm5-1b-sglang/agent-bench-sglang.json`](../../models/benchmarks/logs/minicpm5-1b-sglang/agent-bench-sglang.json)
- [`../../models/benchmarks/logs/minicpm5-1b-sglang/summary.md`](../../models/benchmarks/logs/minicpm5-1b-sglang/summary.md)

MiniCPM5-1B on SGLang / MLX:

| Metric | Result |
|:--|:--|
| API tool smoke, No Think | 5/5, 3-turn loop 0.78 s |
| Throughput @ 512 | 246.5 tok/s |
| Throughput @ 4K | 222.0 tok/s |
| Throughput @ 8K | 203.7 tok/s |
| Throughput @ 32K | 135.1 tok/s |
| Throughput @ 65K | 85.1 tok/s |
| OpenCode browse | 7.28 s median, stable 3/3 |
| OpenCode search | 10.40 s median, but 1/3 measured runs hit 300 s timeout after `webfetch` |

## Known limitations

- **GGUF does not work on SGLang's Apple/MLX backend locally.** The exact `openbmb/MiniCPM5-1B-GGUF` Q8_0 file failed because SGLang's MLX runner delegated to `mlx_lm.load()` and expected a directory with `config.json`, not a `.gguf` file.
- **Use the HF checkpoint path for MiniCPM5.** `openbmb/MiniCPM5-1B` works; `MiniCPM5-1B-Q8_0.gguf` does not on this backend.
- **Tool-call correctness depends on parser flags.** Start with `--tool-call-parser minicpm5`; generic OpenAI-compatible serving is not enough.
- **MiniCPM5 needs No Think for the local tool harness.** Pass `chat_template_kwargs={"enable_thinking": false}` where the client/harness supports it.
- **Provisional client templates.** Only an OpenCode template is provided. Do not assume Claude Code, OpenClaw, Pi, or qwen-code are validated on this server.
- **Not a port-8000 server.** SGLang is a sidecar on port 30000 and can coexist with the port-8000 family, though benchmarks should still stop other LLM servers first.

## See also

- [SGLang GitHub](https://github.com/sgl-project/sglang)
- [openbmb/MiniCPM5-1B-GGUF Tool Calling](https://huggingface.co/openbmb/MiniCPM5-1B-GGUF#tool-calling)
- [`../../models/benchmarks/logs/minicpm5-1b-q8/agent-tool-call-failure-triage.md`](../../models/benchmarks/logs/minicpm5-1b-q8/agent-tool-call-failure-triage.md)
- [`../../models/benchmarks/logs/minicpm5-1b-sglang/summary.md`](../../models/benchmarks/logs/minicpm5-1b-sglang/summary.md)
