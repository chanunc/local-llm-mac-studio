# Gemma 4 26B-A4B via Ollama

Run date: 2026-05-31  
Server: `ollama` on `:11434`  
Model: `gemma4:26b`

## What was recorded

- [`api-tool-test-ollama.json`](api-tool-test-ollama.json)
- [`api-server-ollama.json`](api-server-ollama.json)
- [`agent-bench-ollama.json`](agent-bench-ollama.json)

## Gate Results

- API tool smoke: 5/5 pass
- Multi-turn loop: 3 turns, 6.11 s
- OpenCode browse: 16.7 s median, `webfetch`
- OpenCode search: 26.37 s median, `webfetch`

## Throughput Snapshot

- 512 context: 77.9 tok/s
- 4K context: 70.0 tok/s
- 8K context: 68.7 tok/s
- 32K context: 49.4 tok/s
- 65K context: 36.5 tok/s

