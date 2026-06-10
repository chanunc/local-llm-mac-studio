# ds4 (DwarfStar 4) Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Download the GGUF](#download-the-gguf)
- [Starting the server](#starting-the-server)
- [Tool use and reasoning](#tool-use-and-reasoning)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`ds4` ("DwarfStar 4") is a **standalone, single-model native inference engine written specifically for DeepSeek-V4-Flash** — [`antirez/ds4`](https://github.com/antirez/ds4). It is not a generic GGUF runner and not a `llama.cpp` fork: `ds4.c` is self-contained C + a Metal backend (Objective-C), with DS4-specific GGUF loading, prompt rendering, DSML tool-call handling, RAM + on-disk KV state, and an OpenAI/Anthropic/Responses HTTP server. It only loads the DeepSeek-V4-Flash GGUFs published by the same project at [`antirez/deepseek-v4-gguf`](https://huggingface.co/antirez/deepseek-v4-gguf).

This is the **only Apple-Silicon path that runs DeepSeek-V4-Flash** today. The `deepseek4` architecture (Hybrid Compressed-Sparse-Attention + Heavily-Compressed-Attention + Manifold-Constrained Hyper-Connections) is not in upstream `llama.cpp`, so lm-studio, llama-cpp-turboquant, and llama-cpp-mtp cannot load it. The model-card-recommended `arishma108/llama.cpp` `feat/v4-port-cuda` fork is **CUDA-only** (no Metal). antirez ships two V4 projects: the `ds4` standalone engine (this runbook) and a separate experimental `antirez/llama.cpp-deepseek-v4-flash` Metal fork — `ds4` is the engine with native DSML↔OpenAI tool-call mapping and documented agent integration, so it is the chosen path.

**Status: provisional sidecar.** Standalone validation only — no production flip. Patch-free apart from the `make` build (pure C + Metal, no cmake, no Python venv, no upstream-package patches).

Bound to port **8101**, OpenAI + Anthropic + Responses APIs. Coexists with `vllm-mlx` / `mlx-openai-server` / `oMLX` / `vmlx` on port 8000 (one at a time), `lm-studio` on 1234, `dflash-mlx` on 8098, `llama-cpp-turboquant` on 8099, `llama-cpp-mtp` on 8100, `vmlx-swift-lm` / Osaurus on 1337, `mlx-lm` on 8080, and `comfyui` on 8188.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌─────────────────────────────────────────────┐
│ Claude Code    │            │ ds4-server (port 8101, sidecar)             │
│ OpenCode       │─── LAN ───>│   ~/ds4/ds4-server (native C + Metal)       │
│ OpenClaw       │            │   model: antirez/deepseek-v4-gguf           │
│ Pi / Codex     │            │     IQ2XXS-w2Q2K-…-chat-v2-imatrix (81 GB)  │
└────────────────┘            │   --host 0.0.0.0 --port 8101 --ctx 65536    │
                              │   --kv-disk-dir /tmp/ds4-kv (disk KV)       │
                              │   OpenAI + Anthropic + Responses APIs       │
                              └─────────────────────────────────────────────┘
```

Single-model sidecar. DeepSeek-V4-Flash is a **284 B-total / 13 B-active 256-expert MoE** (1 M context, MIT). The IQ2XXS-imatrix bundle is 2-bit routed experts with Q8 attention/shared/output (81 GB on disk). One mutable backend/KV checkpoint lives in memory; the **KV cache is treated as a first-class disk citizen** — long prefixes survive session switches and server restarts via SHA1-keyed `.kv` files. The single graph worker serializes concurrent requests (no batching).

## Installation

**One-time on Mac Studio** (Xcode command-line tools provide `cc` + Metal frameworks; no cmake needed):

```bash
ssh macstudio "cd ~ && git clone --depth 1 https://github.com/antirez/ds4.git && \
  cd ds4 && make -j8"
```

Build time on M3 Ultra: ~3 sec. Outputs `~/ds4/{ds4,ds4-server,ds4-bench,ds4-eval}`. The Darwin branch of the Makefile auto-selects the Metal core objects (`ds4_metal.o`); `--metal` is the default backend on macOS.

> **macOS CPU warning:** the project warns that current macOS versions have a virtual-memory bug that **kernel-panics** if the CPU path runs. Never build/run `make cpu` on the Mac Studio — always use the default Metal build.

Re-pull + rebuild after upstream updates (`git pull && make -j8`). There is no PyPI / Homebrew pin.

## Download the GGUF

`ds4` only runs the GGUFs from [`antirez/deepseek-v4-gguf`](https://huggingface.co/antirez/deepseek-v4-gguf). The bundled `download_model.sh` is the supported path — it `curl -C -` resumes, honours `~/.cache/huggingface/token`, downloads into `./gguf/`, and symlinks `./ds4flash.gguf` to the selected file.

```bash
ssh macstudio "cd ~/ds4 && ./download_model.sh q2-imatrix"
```

Quant tiers (`./download_model.sh --help`):

| Tier | File | Size | RAM target |
|:--|:--|:--:|:--|
| **`q2-imatrix`** (deploy default) | `…IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix.gguf` | **81 GB** | 96 / 128 GB |
| `q4-imatrix` | `…Q4KExperts-…-chat-v2-imatrix.gguf` | 153 GB | ≥ 256 GB |
| `q2` / `q4` | legacy non-imatrix | 81 / 153 GB | prefer the imatrix variants |
| `mtp` | `…MTP-Q4K-Q8_0-F32.gguf` | 3.5 GB | optional speculative add-on (`--mtp … --mtp-draft 2`) |

`q2-imatrix` (81 GB) is the only tier that fits the 96 GB-class Mac Studio; `q4-imatrix` (153 GB) and the batiai/unsloth Q3–Q8 GGUFs (135–302 GB) exceed unified memory. ~81 GB download at ~110 MB/s ≈ 13 min.

## Starting the server

```bash
ssh macstudio "cd ~/ds4 && nohup ./ds4-server \
  --host 0.0.0.0 --port 8101 \
  --ctx 65536 \
  --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt \
  > /tmp/ds4-server.log 2>&1 &"
```

Key flags:
- **`--host 0.0.0.0`** — default bind is `127.0.0.1` (localhost only). Required for LAN clients on the MacBook. `--cors` only adds CORS headers; it does **not** change the bind address.
- **`--port 8101`** — sidecar port (default is 8000, which collides with the one-at-a-time main servers).
- **`-c, --ctx 65536`** — context allocated at startup (default 32768). Full 1 M context's compressed indexer alone is ~22 GB; with the 81 GB weights on 96 GB-class RAM keep ctx in the 64 K–300 K range. **Think Max** reasoning requires `--ctx ≥ 393216`; smaller contexts cap at "high" thinking effort.
- **`--kv-disk-dir DIR` / `--kv-disk-space-mb N`** — enable the SHA1-keyed disk KV checkpoint cache. This is the design that makes an 81 GB model + long context fit a 96 GB machine; warm prefixes skip prefill entirely (see Performance).
- **`-m, --model FILE`** — defaults to `./ds4flash.gguf` (the symlink `download_model.sh` maintains). Launch from `~/ds4` (or pass `--chdir ~/ds4`) so `metal/*.metal` resolves.
- **`--trace FILE`** — human-readable session trace (prompts, cache decisions, tool calls). Include it when filing upstream issues.

Stop with: `ssh macstudio "pkill -f 'ds4-server'"`.

## Tool use and reasoning

Both work out of the box — `ds4` implements the DeepSeek DSML protocol natively:
- **Tool calls** — `/v1/chat/completions` accepts OpenAI `tools` + `tool_choice`. Tool schemas are rendered into DeepSeek's **DSML** tool format; generated DSML tool calls are mapped back to OpenAI `tool_calls[]`. An unguessable tool-ID → exact-sampled-DSML map (radix-tree backed, persisted in `.kv` files) gives byte-exact replay so multi-turn KV prefixes stay aligned across stateless agent requests. While emitting DSML structure the sampler is forced to `temperature=0` so calls stay parseable; argument payloads use the request's normal sampling. Verified **5/5** single-call + clean 3-turn multi-turn on `bench_api_tool_call.py`. No `--tool-call-parser` flag — it is intrinsic to the engine.
- **Reasoning channel** — DeepSeek-V4-Flash is a thinking model (`non-think` / `think-high` / `think-max`). Chat requests default to **thinking = high**. Reasoning is streamed in the native API shape (not mixed into final text). Disable per request with `model=deepseek-chat`, `think=false`, or `thinking={type:disabled}` for faster non-reasoning replies. In thinking mode the server uses fixed sampling (`temperature=1, top_p=1, min_p=0.05`) and ignores client sampling knobs, matching DeepSeek's official API behaviour.

The Anthropic endpoint (`/v1/messages`) returns `tool_use` blocks; the Responses endpoint (`/v1/responses`) drives Codex CLI.

## Health check

```bash
curl -s http://<MAC_STUDIO_IP>:8101/v1/models | python3 -m json.tool
```

Expect `data[0].id = "deepseek-v4-flash"`, `context_length = 65536`, and `supported_parameters` listing `tools`, `tool_choice`, `reasoning_effort`. Launch-log confirmations:

```
ds4: Metal device Apple M3 Ultra, 96.00 GiB RAM
ds4: Metal … (mapped 82697 MiB …)
ds4-server: context buffers … (ctx=65536, backend=metal …)
ds4-server: listening on http://0.0.0.0:8101
```

Smoke a real tool call:

```bash
curl -s http://<MAC_STUDIO_IP>:8101/v1/chat/completions \
  -H "Content-Type: application/json" -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role":"user","content":"Run uptime to check system status"}],
    "tools": [{"type":"function","function":{"name":"run_command",
      "parameters":{"type":"object","properties":{"cmd":{"type":"string"}}}}}],
    "max_tokens": 256, "temperature": 0.0
  }' | python3 -m json.tool
```

`choices[0].finish_reason` should be `tool_calls` with a `run_command` entry.

## Performance (Mac Studio M3 Ultra, 96 GB)

Tested on `antirez/deepseek-v4-gguf` `IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix` (2026-05-18). Pre-bench hygiene: all other LLM processes stopped, 97 % memory free at launch; 81 GB weights mapped + 1.3 GB context buffers at ctx=65536.

### Decode + prefill (`bench_api_server.py`, 50-token gen, temp 0)

| Context (input tokens) | Median TTFT | Decode tok/s | Prefill tok/s |
|:--:|:--:|:--:|:--:|
| 529 | 0.12 s | **34.6** | 4,512 |
| 4,114 | 5.58 s | 26.9 | 737 |
| 8,209 | 16.0 s | 26.6 | 513 |
| 32,785 | 6.8 s warm / 37.9 s cold | 25.4 | 4,851 warm / 864 cold |

Decode is a flat ~25–35 tok/s — strong for a 284 B model at 2-bit on Apple Silicon, thanks to the 13 B active MoE path. Cold prefill is the cost: dense compressed-attention prefill runs ~500–860 tok/s, but the **disk KV cache turns a 37.9 s cold 32 K prefill into a 6.8 s warm one** (5.5× speedup) — exactly the workload `ds4`'s on-disk-KV design targets.

### Smoke (`bench_api_tool_call.py`)

**5/5 single-call pass** (`read_file`, `run_command`, `search_web`+`read_file`, `list_directory`, `run_command`), each `finish_reason=tool_calls`, 2.2–5.4 s/call. Multi-turn loop: 3 turns / 8.95 s, clean `read_file → write_file → stop`.

### OpenCode end-to-end (`bench_agent_tool_call.py`, opencode, 1 warmup + 3 measured)

| Scenario | Wall median | LLM median | Turns | Tools |
|:--|:--:|:--:|:--:|:--|
| Browse www.example.com | **18.78 s** (11.24–21.69 p5–p95) | 17.96 s | 2 | `webfetch` |
| Browse Hackernews latest topic | **28.22 s** (25.58–31.97 p5–p95) | 27.39 s | 3 | `webfetch` |

Zero errors, `webfetch` fired on every measured run, well under the 250 s p95 / 300 s OpenCode wall. **DeepSeek-V4-Flash runs the agent tool loop end-to-end on Apple Silicon.** Mid-pack for the agent loop (slower than the leanest lm-studio MLX/GGUF mains, faster than several 70 B+ dense uncensored models) — competitive given it is a 284 B knowledge-class model running 2-bit on a personal machine.

Raw bench JSONs: [`docs/models/benchmarks/logs/deepseek-v4-flash/`](../../models/benchmarks/logs/deepseek-v4-flash/).

## Known limitations

- **GGUF lock-in.** `ds4` only loads the `antirez/deepseek-v4-gguf` files — not persadian's IQ1_S-XL, not batiai's Q3–Q8, not generic GGUF. Quants are calibrated per-engine; cross-fork GGUFs will not load.
- **No upstream `llama.cpp` / MLX path.** `deepseek4` is unmerged upstream ([issue #22319](https://github.com/ggml-org/llama.cpp/issues/22319)). vLLM/SGLang (the model card's recommended loaders) are CUDA-only. The persadian + `arishma108/llama.cpp feat/v4-port-cuda` pairing is **CUDA-only — no Metal**, so it does not run on this Mac Studio.
- **Only `q2-imatrix` fits.** `q4-imatrix` (153 GB) and third-party Q3–Q8 (135–302 GB) exceed 96 GB-class unified memory. The 2-bit routed-expert quant is the quality/RAM compromise (antirez reports "quasi-frontier vibes"; objective-vector validated against the official implementation).
- **Cold long-context prefill is slow.** 32 K cold prefill ≈ 38 s (~860 tok/s). Mitigated by the disk KV cache (warm = 6.8 s) — warm the prompt before latency-sensitive use, or accept the first-hit cost.
- **Single graph worker, no batching.** Concurrent requests serialize on one live graph/session. Not a multi-tenant server.
- **Alpha-quality engine.** The project is days old, "alpha quality" per its own README, GPT-5.5-assisted. Behaviour may change across `git pull`s; capture `--trace` when filing issues.
- **macOS CPU path kernel-panics.** Never run `make cpu` / `--cpu` on the Mac Studio (documented macOS VM bug). Metal only.
- **Memory headroom is tight.** 81 GB weights on a 96 GB-class machine. Keep other large processes off; antirez notes 250 K ctx is reachable on 96 GB only if competing memory is freed.

## See also

- Per-model deep dive: [`docs/models/per-model/model-summary-deepseek-v4.md`](../../models/per-model/model-summary-deepseek-v4.md)
- Catalog entry: [`docs/models/model-summary.md`](../../models/model-summary.md#deepseek-v4-flash-284b13b-active-moe-ds4)
- Bench data: [`docs/models/benchmarks/logs/deepseek-v4-flash/`](../../models/benchmarks/logs/deepseek-v4-flash/)
- Engine repo: [`antirez/ds4`](https://github.com/antirez/ds4)
- GGUF repo: [`antirez/deepseek-v4-gguf`](https://huggingface.co/antirez/deepseek-v4-gguf)
- Official model: [`deepseek-ai/DeepSeek-V4-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
- Alternative Metal fork (not used): [`antirez/llama.cpp-deepseek-v4-flash`](https://github.com/antirez/llama.cpp-deepseek-v4-flash)
- Upstream tracking issue: [`ggml-org/llama.cpp#22319`](https://github.com/ggml-org/llama.cpp/issues/22319)
