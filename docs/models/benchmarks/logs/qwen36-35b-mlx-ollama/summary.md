# Qwen3.6 35B-A3B MLX on Ollama

Benchmarked on Mac Studio M3 Ultra 96 GB, Ollama 0.24.0 Homebrew formula with `mlx-c`, serving `qwen3.6:35b-mlx` on `0.0.0.0:11434`.

## Results

| Check | Result |
|:--|:--|
| API tool smoke | 5/5 single-call pass |
| API multi-turn | 3 turns, 5.96 s |
| Throughput @ 512 | 101.9 tok/s, TTFT 0.057 s |
| Throughput @ 32K | 83.9 tok/s, TTFT 0.099 s |
| Throughput @ 65K | 72.5 tok/s, TTFT 0.132 s |
| OpenCode browse | 9.75 s wall / 8.75 s LLM, 2 turns, `webfetch` |
| OpenCode search | 18.4 s wall / 17.42 s LLM, 4 turns median, `webfetch` |

Raw files:

- [`api-tool-test-ollama.json`](api-tool-test-ollama.json)
- [`api-server-ollama.json`](api-server-ollama.json)
- [`agent-bench-ollama.json`](agent-bench-ollama.json)
