# llmster (LM Studio Headless) Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Starting the server](#starting-the-server)
- [Tool use and reasoning](#tool-use-and-reasoning)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`llmster` is the **headless daemon** of [LM Studio](https://lmstudio.ai) — Electron app installed via Homebrew Cask, but the inference path runs entirely from the bundled `~/.lmstudio/bin/lms` CLI plus a separate MLX runtime extension (`mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`) and bundled CPython (`cpython3.11-mac-arm64@10`). No GUI session needed after first-run bootstrap.

Speaks **OpenAI-compatible** API on port **1234** (note: not 8000 — different from every other server in this stack). Closed-source MLX runtime, but ships excellent prefill performance: **47K tok/s @ 32K context** with TTFT staying flat at ~0.7 s, which makes it **3-5× faster end-to-end than vllm-mlx on the OpenCode agent loop** for standard MLX models.

Best for: standard MLX safetensors and GGUF that don't need JANG/JANGTQ/`bailing_hybrid` patches. Tool-call + reasoning parsing is built into the runtime — no parser flags required.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌────────────────────────────────────────┐
│ Claude Code    │            │ lms server (port 1234)                 │
│ OpenCode       │─── LAN ───>│   ~/.lmstudio/bin/lms                  │
│ OpenClaw       │            │   MLX runtime extension (closed-src)   │
│ Pi             │            │   Bundled cpython3.11 + libpython3.11  │
└────────────────┘            │   OpenAI API only (no Anthropic)       │
                              └────────────────────────────────────────┘
```

The server process is `~/.lmstudio/bin/lms` invoking `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`'s `llm_engine_mlx_amphibian.node` against `libpython3.11.dylib` from `~/.lmstudio/extensions/backends/vendor/_amphibian/cpython3.11-mac-arm64@10/lib/`. Models live at `~/.lmstudio/models/<org>/<repo>/` — separate from the HuggingFace cache (no dedup).

## Installation

**Homebrew Cask** (preferred — see project-wide preference):

```bash
ssh macstudio "/opt/homebrew/bin/brew install --cask lm-studio"
```

**Bootstrap the `lms` CLI.** The cask installs `/Applications/LM Studio.app` but does NOT add `lms` to `PATH`. The Electron app needs **one** local launch to materialise `~/.lmstudio/bin/lms` and the `~/.lmstudio/` directory tree. Over SSH:

```bash
ssh macstudio "open -a 'LM Studio' && sleep 8 && osascript -e 'quit app \"LM Studio\"'"
ssh macstudio "~/.lmstudio/bin/lms --version"   # should report a CLI commit hash
```

If the runtime extension is missing or broken (`Library not loaded: @rpath/libpython3.11.dylib` from `llm_engine_mlx_amphibian.node`), force-reinstall:

```bash
ssh macstudio "rm -rf ~/.lmstudio/extensions/backends/mlx-llm-mac-arm64-apple-metal-advsimd-1.6.0 \
  ~/.lmstudio/extensions/backends/vendor/_amphibian/* && \
  ~/.lmstudio/bin/lms runtime get 'mlx' -y && \
  ~/.lmstudio/bin/lms runtime select mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0"
```

The `cpython3.11-mac-arm64@10` bundled Python is included in the runtime tarball — verify it lands under `~/.lmstudio/extensions/backends/vendor/_amphibian/` after `lms runtime get`.

## Starting the server

**Download a model** (uses LM Studio's catalog, not HF cache — see [Known limitations](#known-limitations)):

```bash
# Browse-friendly: pulls MLX variant via LM Studio catalog/HuggingFace
ssh macstudio "~/.lmstudio/bin/lms get 'https://huggingface.co/mlx-community/Qwen3.6-27B-6bit' -y"
ssh macstudio "~/.lmstudio/bin/lms ls"
```

**Custom GGUFs with nonstandard quant labels** may need a direct Hub download plus import. On 2026-05-01, `lms get --gguf 'https://huggingface.co/HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced@Q8_K_P' -y` mis-resolved to `Q2_K_P`, so the exact `Q8_K_P` file was deployed like this:

```bash
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced', filename='Qwen3.6-27B-Uncensored-HauhauCS-Balanced-Q8_K_P.gguf', local_dir='/Users/chanunc/.cache/hauhau-gguf')\""
ssh macstudio "~/.lmstudio/bin/lms import -L --user-repo HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced -y ~/.cache/hauhau-gguf/Qwen3.6-27B-Uncensored-HauhauCS-Balanced-Q8_K_P.gguf"
```

**Load and start** (keep this idempotent — `lms ps` shows current state):

```bash
# Load with explicit context length (default is 4096 — too small for agent prompts)
ssh macstudio "~/.lmstudio/bin/lms load 'qwen3.6-27b' --gpu max --context-length 65536 -y"

# Current GGUF sidecar (2026-05-01): pin a stable API identifier so client configs
# do not depend on LM Studio's generated model id.
ssh macstudio "~/.lmstudio/bin/lms load 'qwen3.6-27b-uncensored-hauhaucs-balanced' --gpu max --context-length 65536 --identifier 'qwen3.6-27b-uncensored-balanced-q8kp' -y"

# Start the OpenAI-compatible server. --bind 0.0.0.0 is REQUIRED for LAN access
# (default binds to 127.0.0.1 only). --cors enables web-app clients.
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

**Stop / unload:**

```bash
ssh macstudio "~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all"
```

## Tool use and reasoning

**No parser flags needed.** LM Studio's MLX runtime detects the model's chat-template format (Qwen3 XML, Hermes JSON, etc.) and converts emitted tool calls into OpenAI `tool_calls[]` automatically. `<think>` reasoning blocks are exposed as `reasoning_content` separate from `content`.

Verified on 2026-04-30 with `mlx-community/Qwen3.6-27B-6bit`:
- API-level harness (`scripts/bench/bench_api_tool_call.py`): 5/5 single-call pass, clean 3-turn agentic loop in 20.28 s
- OpenCode end-to-end browse: **31.96 s wall** (vs vllm-mlx 97.93 s on the same model file — **3.1× faster**)
- OpenCode end-to-end search: **25.71 s wall** (vs vllm-mlx 127.28 s — **4.9× faster**)
- Reasoning tokens captured: 70-79 per scenario (vllm-mlx + `--reasoning-parser qwen3` on the same model emitted 0)

Smoke-tested on 2026-05-01 with `HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced` `Q8_K_P`:
- `/v1/models` exposed the pinned id `qwen3.6-27b-uncensored-balanced-q8kp`
- First `/v1/chat/completions` turn returned `finish_reason: "tool_calls"` with `get_weather({"location":"Paris"})`
- Tool-result replay produced a normal final answer and separate `reasoning_content`

Full bench: [`docs/models/benchmarks/model-benchmark-agent-tool-call.md` § Server comparison](../../models/benchmarks/model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30).

## Health check

No API key required.

```bash
# From MacBook over LAN — lists loaded model + the embedded nomic embedding model
curl -s http://<MAC_STUDIO_IP>:1234/v1/models | python3 -m json.tool

# Plain chat round-trip
curl -s http://<MAC_STUDIO_IP>:1234/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.6-27b-uncensored-balanced-q8kp","messages":[{"role":"user","content":"Say hello"}],"max_tokens":50}' \
  | python3 -m json.tool

# Live request/response stream (the tail -f equivalent)
ssh macstudio "~/.lmstudio/bin/lms log stream"

# Daily persisted log file (rolled per-day)
ssh macstudio "tail -f ~/.lmstudio/server-logs/\$(date +%Y-%m)/\$(date +%Y-%m-%d).1.log"
```

## Performance (Mac Studio M3 Ultra, 96 GB)

`mlx-community/Qwen3.6-27B-6bit` on llmster v0.4.12 + MLX runtime 1.6.0, streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 1 cold + 2 warm runs per context. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-llmster.json`](../../models/benchmarks/qwen36-27b-6bit/api-server-llmster.json).

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **29.9** | 1,086 | 0.49 |
| 4K | 29.3 | 8,031 | 0.51 |
| 8K | 28.8 | 15,321 | 0.54 |
| 32K | 26.3 | **47,143** | 0.70 |

**Headline:** TTFT stays effectively flat from 512 → 32K (0.49 → 0.70 s). Compare to `Qwen3.6-27B JANG 4M` on vllm-mlx where 32K TTFT is **104 s** at 314 tok/s prefill — llmster's prefill kernel is roughly **150× faster** at long context. Decode is ~10-20 % slower than vllm-mlx + JANG 4M (29.9 vs 36.5 tok/s @ 512), but for agent workloads where prefill dominates the 10K-token system prompt + tool catalog, the prefill win compensates ~10× over.

## Known limitations

- **MLX safetensors / GGUF only.** No JANG, no JANGTQ, no `bailing_hybrid`. Closed-source MLX runtime — model architectures not on LM Studio's supported list will fail to load. Use vllm-mlx, vmlx, or oMLX for those.
- **`lms get` re-downloads from HuggingFace** into `~/.lmstudio/models/` even when the same repo is already in `~/.cache/huggingface/hub/` (no dedup, no symlink option). For a 22 GB model this means 22 GB of duplicate disk usage.
- **Custom quant names can confuse LM Studio's resolver.** HauhauCS `K_P` quants currently do not round-trip cleanly through `lms get ...@Q8_K_P`; the resolver tried to download `Q2_K_P` instead. Work around this by downloading the exact GGUF via `huggingface_hub` and importing it with `lms import -L`.
- **Model IDs are mangled.** LM Studio lowercases and strips the org prefix at load time: `mlx-community/Qwen3.6-27B-6bit` → `qwen3.6-27b`. Check `/v1/models` for the exact served identifier and use that in client configs / `--model` args.
- **Default context is 4096.** `lms load` without `--context-length` ships with a 4 K window, which fails on agent prompts. Always pass `--context-length 65536` (or larger) explicitly. Memory is allocated up front.
- **Default bind is 127.0.0.1.** `lms server start` without `--bind 0.0.0.0` will not accept LAN connections. There is no persistent server config file that survives across `start` invocations — pass `--bind 0.0.0.0 --cors` every time.
- **Electron Cask install needs one GUI launch.** First-time `~/.lmstudio/bin/lms` doesn't exist until the Electron app runs once locally. Headless-only macOS hosts will need a screen-share/VNC session for that initial launch (then it stays bootstrapped permanently).
- **Closed-source runtime.** No way to inspect the prefill kernel, no way to apply repo-managed patches. If a future LM Studio update changes runtime behavior, results may shift without notice.
- **No Anthropic API.** OpenAI `/v1/chat/completions` and `/v1/embeddings` only. Clients that prefer the Anthropic shape (Claude Code direct mode) need to use one of the other servers.
- **Single-port-1234 default** clashes with nothing in this stack today, but every other server in the repo is on port 8000 — be careful with client config templates and switching.

## See also

- [`docs/models/benchmarks/model-benchmark-agent-tool-call.md` § llmster vs vllm-mlx](../../models/benchmarks/model-benchmark-agent-tool-call.md#server-comparison-llmster-vs-vllm-mlx-same-model-file-2026-04-30) — full agent-bench comparison with raw numbers
- [`docs/models/benchmarks/model-benchmark-api-server.md` § Qwen3.6-27B 6-bit on llmster](../../models/benchmarks/model-benchmark-api-server.md#qwen36-27b-6-bit-standard-mlx-on-llmster-vs-vllm-mlx) — direct prompt benchmark detail
- [`configs/clients/llmster/opencode.json`](../../../configs/clients/llmster/opencode.json) — OpenCode client template (substitutes `<MAC_STUDIO_IP>` via `scripts/switch_opencode_config.py`)
- [`scripts/switch_opencode_config.py`](../../../scripts/switch_opencode_config.py) — handles `--server llmster` to swap OpenCode between vllm-mlx (port 8000) and llmster (port 1234)
- [LM Studio docs — headless `llmster`](https://lmstudio.ai/docs-md/developer/core/headless_llmster) — upstream reference (Linux/systemd-focused; macOS path documented here is the right one for this stack)
