# vmlx-swift-lm (via Osaurus)

OpenAI / Anthropic / Ollama-compatible MLX-Swift inference server on **port 1337** (default). Engine = [`osaurus-ai/vmlx-swift-lm`](https://github.com/osaurus-ai/vmlx-swift-lm) — the only runtime in this lab that natively supports Zyphra ZAYA1's CCA (Compressed Convolutional Attention) cache contract. Consumed via the **Osaurus** macOS app (`brew install --cask osaurus`).

## Overview

- [What this server is](#what-this-server-is) — engine, app wrapper, model formats supported
- [Why it exists in this lab](#why-it-exists-in-this-lab) — ZAYA1 / Hy3 / MiniMax-M2.7 paths that aren't in stock `mlx_lm`
- [Installation](#installation) — one-line cask install
- [Starting the server](#starting-the-server) — the `OSU_MODELS_DIR` path-bug workaround
- [Pulling models](#pulling-models) — `osaurus pull` and where files land
- [Health check](#health-check) — `/v1/models`, `/health`, `/api/tags`
- [Tool use and reasoning](#tool-use-and-reasoning) — built-in parsers, no flags needed
- [Performance](#performance) — measured numbers + known JANGTQ HTTP-path regression
- [Known limitations](#known-limitations) — path mismatch, --expose, JANGTQ B=1 fast path missing
- [Coexistence with other servers](#coexistence-with-other-servers) — port 1337 is free of conflicts
- [See also](#see-also)

## What this server is

| Layer | Identity |
|:--|:--|
| Engine | [`osaurus-ai/vmlx-swift-lm`](https://github.com/osaurus-ai/vmlx-swift-lm) — Osaurus's fork of [`ml-explore/mlx-swift-lm`](https://github.com/ml-explore/mlx-swift-lm). MIT, Swift, native MLX. Adds BatchEngine, multi-tier KV cache (L1 paged + L2 SQLite-on-disk + SSM-companion), TurboQuant KV compression, speculative decoding (DFlash + DDTree), JANG mixed-precision, and the model families that aren't in upstream: Gemma 4, Mistral Small 4, Qwen 3.5 / 3.6, DeepSeek-V4, NemotronH, Hunyuan v3 (Hy3), MiniMax M2 / M2.5 / M2.7, **ZAYA / ZAYA1-VL**. |
| App | [`osaurus-ai/osaurus`](https://github.com/osaurus-ai/osaurus) — macOS GUI + CLI harness around the engine. Cask version 0.18.13 (released 2026-05-08) pins vmlx-swift-lm at commit `b9da180` via [PR #1037](https://github.com/osaurus-ai/osaurus/pull/1037). |
| API surfaces | **OpenAI-compatible** (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`) · **Anthropic-compatible** · **Ollama-compatible** (`/api/tags`, `/api/show`) · MCP server (`osaurus mcp`). |
| Port | **1337** by default (configurable via `--port`). No conflict with 8000 / 1234 / 8098 / 8099 / 8188 on this stack. |
| Auth | None. Default bind is `127.0.0.1`. |

Model formats: **BF16 safetensors** · **Standard MLX (4/6/8-bit)** · **JANG mixed-precision** · **JANGTQ2 / JANGTQ4 / MXFP4 routed-expert** · with per-family contracts (CCA cache for ZAYA, ArraysCache for hybrid SSM, MambaCache for SSM, RotatingKVCache for sliding-window).

## Why it exists in this lab

Three workloads can't run on the existing port-8000 servers:

1. **ZAYA1 / ZAYA1-VL** (Zyphra; top-1 CCA + MoE) — needs the `ZayaCCACache` contract that vmlx-swift-lm vendors. Not in stock `mlx_lm` ([PR #1261](https://github.com/ml-explore/mlx-lm/pull/1261) in review) and not in `llama.cpp` ([issue #22776](https://github.com/ggml-org/llama.cpp/issues/22776) open, no PR).
2. **Hunyuan v3 (Hy3)** — dense GQA + 192-expert MoE, not in `mlx_lm` and not in `llama.cpp`.
3. **MiniMax M2.7-JANGTQ** — the published JANGTQ Hadamard kernel optimization lives in the Swift engine, not in Python `mlx_lm`.

For workloads that already run on `mlx_lm` / `vllm-mlx` / `lm-studio`, this server doesn't add value — overhead from the GUI app wrapper makes it a strictly-second choice on Apple Silicon for those.

## Installation

```bash
ssh macstudio "/opt/homebrew/bin/brew install --cask osaurus"
```

Requires macOS ≥ 15 and Apple Silicon. Cask installs to `/Applications/Osaurus.app` and links the CLI at `/opt/homebrew/bin/osaurus` (a symlink to the bundled `Contents/Helpers/osaurus` binary).

Verify:

```bash
ssh macstudio "/opt/homebrew/bin/osaurus --help | head -20"
ssh macstudio "strings /Applications/Osaurus.app/Contents/MacOS/osaurus | grep -E '^Zaya[A-Z]' | head -5"
# Should list ZayaConfiguration, ZayaCCAAttention, ZayaCCACache, ZayaMoEContext etc.
```

## Starting the server

Default `osaurus serve` binds **127.0.0.1:1337**. To make the server LAN-reachable, see [Known limitations § `--expose` doesn't rebind](#known-limitations) below.

Critical caveat — **path mismatch between `pull` and `serve`**: `osaurus pull` writes models into `~/.osaurus/models/`, but the server's `effectiveModelsDirectory()` defaults to `~/MLXModels/`. Without overriding, pulled models are invisible to the running server. Fix by exporting `OSU_MODELS_DIR`:

```bash
ssh macstudio "OSU_MODELS_DIR=\$HOME/.osaurus/models \
  nohup /opt/homebrew/bin/osaurus serve --port 1337 \
  > /tmp/osaurus.log 2>&1 &"
```

Stop:

```bash
ssh macstudio "/opt/homebrew/bin/osaurus stop"
# If the GUI-helper process survives (it sometimes does on cask upgrades):
ssh macstudio "pkill -9 osaurus"
```

Status / runtime config:

```bash
ssh macstudio "/opt/homebrew/bin/osaurus status"
ssh macstudio "cat ~/.osaurus/runtime/*/configuration.json"
```

## Pulling models

```bash
ssh macstudio "/opt/homebrew/bin/osaurus pull <hf-repo-id>"
```

Saves to `~/.osaurus/models/<owner>/<name>/`. The downloader pulls all files referenced by the HF repo tree — including JANGTQ sidecars (`jangtq_runtime.safetensors`, `jang_config.json`) when present.

Verify after pull:

```bash
ssh macstudio "ls -la ~/.osaurus/models/<owner>/<name>/"
ssh macstudio "curl -s http://127.0.0.1:1337/v1/models | python3 -m json.tool"
```

The OpenAI `/v1/models` id is the *bundle id* derived from `config.json`, not the HF repo path. For ZAYA1-8B-JANGTQ4 the registered id is `zaya1-8b-jangtq4`.

## Health check

```bash
curl -s http://127.0.0.1:1337/v1/models | python3 -m json.tool   # OpenAI catalog
curl -s http://127.0.0.1:1337/api/tags | python3 -m json.tool    # Ollama-style (includes family metadata)
curl -s http://127.0.0.1:1337/health                              # liveness + loaded model list
tail -20 /tmp/osaurus.log                                          # serve stdout/stderr
```

The Ollama-format `/api/tags` returns `family: "unknown"` and empty `quantization_level` for JANGTQ bundles — the runtime serves them fine; only the catalog metadata is missing.

## Tool use and reasoning

Built into the engine. **No `--tool-call-parser` or `--reasoning-parser` flags needed** — vmlx-swift-lm ships per-family parsers wired through `LLMTypeRegistry`:

- ZAYA → `tool_parser=zaya_xml` (declared in the JANGTQ4 sidecar's capabilities)
- Qwen3 / Qwen3.5 / Qwen3.6 → qwen3 XML
- Hermes families → `<tool_call>{json}</tool_call>`
- Hunyuan v3 → Hunyuan tool/reasoning parser

Reasoning channel is opt-in per family. ZAYA1's capabilities sidecar declares `supports_thinking=false` — the model still does internal reasoning, but it's not surfaced via a separate `reasoning` field.

## Performance

### ZAYA1-8B-JANGTQ4 on M3 Ultra (this lab, Osaurus 0.18.13 at engine pin `b9da180`)

`bench_api_server.py`, 50-token generations, 1 warmup + 2 timed runs, median reported. Raw JSON at [`docs/models/benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json`](../../models/benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json).

| Context | TTFT | Decode tok/s | Prefill tok/s |
|---:|---:|---:|---:|
| 512 | 2.73 s | 7.3 | 208 |
| 4096 | 5.09 s | 7.0 | 876 |
| 8192 | 8.00 s | 7.9 | 1112 |
| 32768 | 31.66 s | 7.8 | 1122 |

### Agent loop bench

`bench_agent_tool_call.py` against OpenCode 1.14.48 → SSH-tunneled Osaurus, `--scenario browse --runs 1 --warmup 0`. Raw JSON: [`docs/models/benchmarks/zaya1-8b/agent-bench-vmlx-swift-lm.json`](../../models/benchmarks/zaya1-8b/agent-bench-vmlx-swift-lm.json).

| Scenario | Wall time | Turns | Tools fired | Tokens out |
|:--|---:|:--:|:--|---:|
| `Browse www.example.com` | **300.04 s (OpenCode wall-time killed)** | 1 (`step_start: 1, step_finish: 0`) | none | 0 |

The agent run hit OpenCode's 300 s wall before producing any output. Same wall-time failure mode previously documented for Gemma 4 31B-it bf16 + MTP drafter — the bottleneck is the regressed decode speed against OpenCode's large tool-definition system prompt, not ZAYA1's tool-calling capability per se. Re-run after the engine pin moves to `cb8b3df`.

### Known regression

**These numbers are gated by a known regression** — see [Known limitations § JANGTQ HTTP-path regression](#known-limitations). The engine's own `RunBench` evidence pass at the same commit on M4 Max 128 GB reports **57.2 tok/s** decode for ZAYA1-8B JANGTQ4 ([fork README perf table](https://github.com/osaurus-ai/vmlx-swift-lm#single-stream-decode-sustained-toks)). The HTTP-API path is 7-8× slower because the pin is missing the `BatchEngine.generate` B=1 solo fast path and the JANGTQ Hadamard / cached-meta kernel optimization. Both fixes are queued in [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) (open at time of writing; bumps to `cb8b3df`).

### Reference numbers from the fork's evidence pass (M4 Max 128 GB, `RunBench` harness, not HTTP)

| Model | Format | TTFT | Decode |
|:--|:--|---:|---:|
| ZAYA1-8B | JANGTQ2 | 64-68 ms | 57.1 tok/s |
| ZAYA1-8B | JANGTQ4 | 63-66 ms | 57.2 tok/s |
| ZAYA1-8B | MXFP4 | 73-75 ms | 71.8 tok/s |
| Ling-2.6-flash | JANGTQ2 | 151-171 ms | 57.5 tok/s |
| Nemotron-Omni-Nano | JANGTQ | 86-92 ms | 117.3 tok/s |

## Known limitations

- **`osaurus pull` / `osaurus serve` directory mismatch.** `pull` writes to `~/.osaurus/models/`; `serve` reads `~/MLXModels/` by default. Pulled models are invisible until `OSU_MODELS_DIR` is set. Considered a bug, not yet filed upstream as of 2026-05-12.
- **`--expose` doesn't actually rebind.** Passing `osaurus serve --expose --yes` flips `exposeToNetwork: true` in `~/.osaurus/runtime/*/configuration.json` but the listener stays on `127.0.0.1`. Likely needs GUI confirmation that doesn't trigger over SSH. Workaround: run benches from the Mac Studio over loopback, or `ssh -L 1337:127.0.0.1:1337 macstudio` from clients.
- **JANGTQ HTTP-path regression at pin `b9da180`.** The Swift-side `BatchEngine.generate` B=1 fast path and the JANGTQ Hadamard kernel optimization are absent from the pinned source. Real HTTP-API decode is 7-8 tok/s on ZAYA1 JANGTQ4 vs the 57 tok/s the fork's own `RunBench` reports. Fix lands in cask version that picks up [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) (vmlx-swift-lm pin `cb8b3df`). Until then, treat this server as **functional but speed-degraded** for JANGTQ workloads on the OpenAI HTTP API.
- **Multiple `osaurus --launched-by-cli` processes.** `osaurus stop` sometimes leaves the prior GUI-helper process running while the new one starts — both end up holding the model in unified memory. Verify with `ps -axm -o pid,rss,command | grep osaurus` and `pkill -9 osaurus` before each restart while the regression persists.
- **`osaurus list` only shows models from a blessed catalog**, not arbitrary pulled HF bundles. `/v1/models` is the authoritative live-model list.

## Coexistence with other servers

Port 1337 has no conflict with the rest of the stack (8000 / 1234 / 8098 / 8099 / 8188 / no-port). Memory-wise the running app holds the loaded model in wired/active memory the same way the other servers do — Event-4 hygiene applies if total wired memory will exceed ~70 GB across servers. The bench above was run after stopping LM Studio's llmworker (which was holding 61 GB) — speed didn't change, confirming the slowdown was server-internal, not memory pressure.

## See also

- [Per-model deployment writeup: ZAYA1-8B](../../models/per-model/model-summary-zaya1-8b.md)
- [Raw API server benchmark JSON](../../models/benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json)
- [vmlx-swift-lm fork README (perf tables, evidence logs)](https://github.com/osaurus-ai/vmlx-swift-lm)
- [Osaurus PR #1037 — vmlx-swift-lm bump to `b9da180` (Ling/ZAYA hardening)](https://github.com/osaurus-ai/osaurus/pull/1037)
- [Osaurus PR #1057 — vmlx-swift-lm bump to `cb8b3df` (MiniMax + JANGTQ fast-path restore)](https://github.com/osaurus-ai/osaurus/issues/1057)
- [Upstream `ml-explore/mlx-swift-lm`](https://github.com/ml-explore/mlx-swift-lm)
- [Zyphra/ZAYA1-8B](https://huggingface.co/Zyphra/ZAYA1-8B)
