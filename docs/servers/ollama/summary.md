# Ollama

Ollama OpenAI-compatible sidecar on port `11434`, now viable on Apple Silicon through the post-0.19 MLX backend. This runbook is for the Homebrew formula installed on the Mac Studio (`ollama 0.24.0`, dependency `mlx-c`).

## Role

- OpenAI-compatible API on `http://<MAC_STUDIO_IP>:11434/v1`
- Best current fit here: `qwen3.6:35b-mlx`
- No API key
- Sidecar port; does not contend for port `8000`
- Useful for testing Ollama's MLX cache/runtime path against OpenCode, Codex, Claude Code, and OpenClaw

## Install

```bash
ssh macstudio "/opt/homebrew/bin/brew install ollama"
```

The formula caveat recommends explicit runtime flags for Apple Silicon:

```bash
ssh macstudio "nohup env \
  OLLAMA_HOST=0.0.0.0:11434 \
  OLLAMA_FLASH_ATTENTION=1 \
  OLLAMA_KV_CACHE_TYPE=q8_0 \
  /opt/homebrew/opt/ollama/bin/ollama serve \
  > /tmp/ollama.log 2>&1 &"
```

## Qwen3.6 MLX

```bash
ssh macstudio "/opt/homebrew/opt/ollama/bin/ollama pull qwen3.6:35b-mlx"
curl -s http://<MAC_STUDIO_IP>:11434/v1/models | python3 -m json.tool
```

Validated on 2026-05-30:

- API smoke: 5/5 single-call tool pass; 3-turn loop 5.96 s
- Throughput: 101.9 tok/s at 512, 83.9 tok/s at 32K, 72.5 tok/s at 65K
- OpenCode: browse 9.75 s median, search 18.4 s median, real `webfetch` calls

Raw benchmark JSONs:

- [`api-tool-test-ollama.json`](../../models/benchmarks/logs/qwen36-35b-mlx-ollama/api-tool-test-ollama.json)
- [`api-server-ollama.json`](../../models/benchmarks/logs/qwen36-35b-mlx-ollama/api-server-ollama.json)
- [`agent-bench-ollama.json`](../../models/benchmarks/logs/qwen36-35b-mlx-ollama/agent-bench-ollama.json)

## OpenCode

Template:

```bash
python3 scripts/switch_opencode_config.py --server ollama
```

Manual model id:

```bash
opencode run --model "macstudio-ollama/qwen3.6:35b-mlx" "Browse www.example.com"
```

## Stop

```bash
ssh macstudio "pkill -f '/opt/homebrew.*/ollama serve'; pkill -f 'ollama runner'"
```

## Notes

- Ollama's `/v1/models` exposes the tag as `qwen3.6:35b-mlx`.
- The `qwen3.6:35b-mlx` library entry is text-only, unlike GGUF `qwen3.6:35b` entries that advertise image input. For this lab entry the target is OpenCode tool calling, not vision.
- The OpenAI-compatible tool path passes the local API smoke cleanly. Keep the API smoke before OpenCode agent benchmarks when testing new Ollama tags.
