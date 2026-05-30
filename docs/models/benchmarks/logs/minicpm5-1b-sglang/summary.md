# MiniCPM5-1B SGLang Follow-up

Date: 2026-05-30

## What Was Tested

The original LM Studio deployment used `openbmb/MiniCPM5-1B-GGUF` / `MiniCPM5-1B-Q8_0.gguf` and failed OpenAI API tool-call smoke (`0/5`). The model card's Tool Calling section recommends SGLang with the `minicpm5` parser, so SGLang was installed from source on the Mac Studio and tested separately.

The exact Q8_0 GGUF did **not** load under SGLang's Apple/MLX backend. SGLang accepted `--quantization gguf`, but the MLX runner delegated to `mlx_lm.load()` and expected a model directory with `config.json`, not a `.gguf` file:

```text
NotADirectoryError: ... MiniCPM5-1B-Q8_0.gguf/config.json
```

The successful SGLang route uses the HF checkpoint:

```bash
cd ~/sglang
. sglang-mps/bin/activate
SGLANG_USE_MLX=1 python -m sglang.launch_server \
  --model-path openbmb/MiniCPM5-1B \
  --tool-call-parser minicpm5 \
  --host 0.0.0.0 --port 30000
```

SGLang reported:

```json
{"id":"openbmb/MiniCPM5-1B","owned_by":"sglang","max_model_len":131072}
```

## API Tool Calling

Raw default-template smoke partially worked but did not meet the repo's pass gate:

- [`api-tool-test.json`](api-tool-test.json): **3/5**, multi-turn 3 turns / 1.64 s

MiniCPM5's model card recommends No Think mode for tool calling. Passing SGLang `chat_template_kwargs={"enable_thinking": false}` fixed the API layer:

- [`api-tool-test-no-think.json`](api-tool-test-no-think.json): **5/5**, multi-turn 3 turns / 0.78 s

The benchmark harness now has `--chat-template-kwargs` so SGLang/OpenAI-compatible endpoints can be tested with template toggles:

```bash
python3 scripts/bench/bench_api_tool_call.py \
  --base-url http://<MAC_STUDIO_IP>:30000/v1 \
  --model openbmb/MiniCPM5-1B \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --output docs/models/benchmarks/logs/minicpm5-1b-sglang/api-tool-test-no-think.json
```

## Throughput

Raw JSON: [`api-server-sglang.json`](api-server-sglang.json)

| Context | Prompt tokens | TTFT | Gen tok/s |
|:--|--:|--:|--:|
| 512 | 535 | 0.015 s | 246.5 |
| 4K | 4,120 | 0.019 s | 222.0 |
| 8K | 8,215 | 0.026 s | 203.7 |
| 32K | 32,791 | 0.057 s | 135.1 |
| 65K | 65,560 | 0.116 s | 85.1 |

## OpenCode Agent

Raw JSON: [`agent-bench-sglang.json`](agent-bench-sglang.json)

OpenCode was pointed at SGLang with a temporary local config and restored after the run.

| Scenario | Median wall | p95 | Turns | Tool calls | Notes |
|:--|--:|--:|--:|:--|:--|
| Browse `www.example.com` | 7.28 s | 7.32 s | 2 | `read` | Stable 3/3 |
| Browse Hacker News latest topic | 10.40 s | 300.03 s | 2 median | `webfetch` | 2/3 normal; 1/3 hit the 300 s harness timeout after one `webfetch` |

The agent layer is therefore usable but not clean enough for a normal cross-model leaderboard row without a caveat.
