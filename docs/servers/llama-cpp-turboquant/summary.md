# llama-cpp-turboquant Server Summary

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

`llama-cpp-turboquant` is a research-grade KV-cache-compression server built from the [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant) fork (`feature/planarquant-kv-cache` branch) of upstream llama.cpp. It adds the **TurboQuant**, **PlanarQuant**, and **RotorQuant (IsoQuant)** family of KV-cache quantization types that are not yet in upstream — concretely, the `--cache-type-k` and `--cache-type-v` flags accept `turbo2/3/4`, `planar3/4`, **`iso3`**, **`iso4`** in addition to the standard `f16/q8_0/q4_0/...`.

> **Technique reference:** for what RotorQuant / IsoQuant / TurboQuant actually do at the algorithm level (Clifford rotors, quaternion rotation, Lloyd-Max codebooks, the cross-fork landscape across MLX vs llama.cpp), see [`docs/models/techniques/model-technique-rotorquant.md`](../../models/techniques/model-technique-rotorquant.md). This runbook covers operational steps only.

**Status: provisional sidecar — strong production-flip candidate as of 2026-05-06.** Used for KV-cache-compression experiments on Qwen3.6-class models. Exposes the full OpenAI semantics — `tools[]`, streaming, `reasoning_content` channel — via the standard `llama-server` binary, no patches required.

**Two forks installed in parallel** (cohabitate the port 8099 slot — only one can be live at a time):

| Fork | Branch | Path | Cache types | Verdict |
|:--|:--|:--|:--|:--|
| [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant) | `feature/planarquant-kv-cache` | `~/llama-cpp-turboquant/` | `iso3/4`, `turbo2/3/4`, `planar3/4` | First Apple-Silicon path for **RotorQuant**. iso3 cold-prefill regression at 32 K+. |
| [`TheTom/llama-cpp-turboquant`](https://github.com/TheTom/llama-cpp-turboquant) | `feature/turboquant-kv-cache` | `~/llama-cpp-thetom/` | `turbo2/3/4` only | **Auto-asymmetric `q8_0` K + turbo-V**, 4-mag LUT, sparse V dequant. **2× / 2.27× faster than Gemma 4 on browse / search.** |

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌─────────────────────────────────────────────┐
│ Claude Code    │            │ llama-server (port 8099, sidecar)           │
│ OpenCode       │─── LAN ───>│   ~/llama-cpp-turboquant/build/bin/         │
│ OpenClaw       │            │     llama-server                            │
│ Pi             │            │   model: Qwen3.6-35B-A3B Q6_K (~27 GB)      │
└────────────────┘            │   --cache-type-k iso3 --cache-type-v iso3   │
                              │   -ngl 99 -fa on                            │
                              │   OpenAI API only (no Anthropic)            │
                              └─────────────────────────────────────────────┘
```

Sidecar pattern — runs on port **8099**, coexisting with whatever server holds port 8000 (vllm-mlx / oMLX / vmlx / mlx-openai-server). dflash-mlx (8098) and lm-studio (1234) can also coexist.

GGUF weights live in `~/.cache/huggingface/hub/`. The fork's binary is fully self-contained — no Python venv, no upstream-package patches, no PyPI dependency.

## Installation

**One-time on Mac Studio:**

```bash
ssh macstudio "/opt/homebrew/bin/brew install cmake"   # if missing

ssh macstudio "cd ~ && git clone -b feature/planarquant-kv-cache --depth 1 \
  https://github.com/johndpope/llama-cpp-turboquant.git && \
  cd llama-cpp-turboquant && \
  cmake -B build \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON \
    -DLLAMA_BUILD_SERVER=ON && \
  cmake --build build --config Release -j 8"
```

Build time on M3 Ultra: ~30 sec. Outputs `~/llama-cpp-turboquant/build/bin/{llama-server,llama-cli}`.

**Pre-download a GGUF** (any quant works — KV cache is weight-format-agnostic):

```bash
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  print(hf_hub_download(repo_id='unsloth/Qwen3.6-35B-A3B-GGUF', \
    filename='Qwen3.6-35B-A3B-UD-Q6_K.gguf'))\""
```

`unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` is ~27 GB and downloads in 5–10 min on a fast HF link. Other supported quants on the same repo: `UD-Q4_K_M` (~21 GB), `UD-Q5_K_M` (~24 GB), `UD-Q6_K_XL` (~30 GB), `Q8_0` (~37 GB).

## Starting the server

### TheTom turbo3 (recommended — current speed leader)

```bash
ssh macstudio "GGUF=\$(ls ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/*/Qwen3.6-35B-A3B-UD-Q6_K.gguf); \
  nohup ~/llama-cpp-thetom/build/bin/llama-server \
    -m \"\$GGUF\" \
    --cache-type-k turbo3 --cache-type-v turbo3 \
    -ngl 99 -fa on \
    --host 0.0.0.0 --port 8099 \
    --alias qwen3.6-35b-a3b-turboquant-turbo3 \
    -c 65536 \
    --jinja \
    > /tmp/llama-cpp-thetom.log 2>&1 &"
```

Loader silently maps K to `q8_0` (asymmetric pairing is the default for low-bit weights — see launch log: `K (q8_0): 340 MiB, V (turbo3): 125 MiB`). Startup logs also confirm `turbo3 using 4-mag LUT (pre-M5 hardware)` + `turbo3 sparse V dequant enabled`.

### johndpope iso3 / planar3 (only path for RotorQuant)

```bash
ssh macstudio "GGUF=\$(ls ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/*/Qwen3.6-35B-A3B-UD-Q6_K.gguf); \
  nohup ~/llama-cpp-turboquant/build/bin/llama-server \
    -m \"\$GGUF\" \
    --cache-type-k iso3 --cache-type-v iso3 \
    -ngl 99 -fa on \
    --host 0.0.0.0 --port 8099 \
    --alias qwen3.6-35b-a3b-rotorquant-iso3 \
    -c 65536 \
    --jinja \
    > /tmp/llama-cpp-turboquant.log 2>&1 &"
```

Key flags:
- `--cache-type-k iso3 --cache-type-v iso3` — RotorQuant / IsoQuant 3-bit KV cache (the entire reason this server exists)
- `-ngl 99` — offload all 40 layers + embeddings to Metal
- `-fa on` — flash attention (default `auto` works too; explicit `on` documents intent). Note: `-fa` without a value errors on this build — must specify `on/off/auto`
- `-c 65536` — context limit. Higher is feasible on 96 GB Mac Studio but cold prefill cost rises super-linearly with iso3 K compression (see Performance)
- `--alias` — what `/v1/models` returns. Pick a stable identifier; clients reference it
- `--jinja` — apply the model's Jinja chat template, including `<think>` tag handling. Without it the server will not split the reasoning channel

Stop with: `ssh macstudio "pkill -f llama-cpp-turboquant"`.

## Tool use and reasoning

Both work out of the box on the fork:
- **Tool calls** — Qwen3.6's native `<tool_call>` XML parsed by `llama-server` into OpenAI-style `tool_calls[]`. Verified 5/5 on the API smoke harness.
- **Reasoning channel** — Qwen3.6's `<think>` blocks land in `choices[].message.reasoning_content` (separate from `content`). OpenCode renders this as the assistant's hidden thought bubble.

No parser flags needed — the chat template embedded in the GGUF (and applied via `--jinja`) handles the dispatch.

## Health check

```bash
curl -s http://<MAC_STUDIO_IP>:8099/v1/models | python3 -m json.tool
```

Expect a `data[0].id` of `qwen3.6-35b-a3b-rotorquant-iso3` (or whatever you passed to `--alias`).

Smoke a real generation:

```bash
curl -s http://<MAC_STUDIO_IP>:8099/v1/chat/completions \
  -H "Content-Type: application/json" -d '{
    "model": "qwen3.6-35b-a3b-rotorquant-iso3",
    "messages": [{"role":"user","content":"Reply with exactly: ok"}],
    "max_tokens": 200,
    "temperature": 0
  }' | python3 -m json.tool
```

Look for non-empty `choices[0].message.content` (or `reasoning_content` if the model is mid-thought) and `usage.completion_tokens > 0`.

## Performance (Mac Studio M3 Ultra, 96 GB)

Both forks tested on `unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` (same GGUF blob), 2026-05-06.

### TheTom turbo3 (current sidecar)

| Context | Cold prefill TTFT | Warm TTFT | Decode tok/s | Prefill tok/s |
|:--:|:--:|:--:|:--:|:--:|
| 512 | 0.37 s | 0.04 s | **68.4–69.2** | ~14,800 |
| 4 K | 2.41 s | 0.05 s | 64.3–64.4 | ~91,200 |
| 8 K | **5.07 s** | 0.06 s | 59.8 | ~148,800 |
| 32 K | **29.88 s** | 0.12 s | 44.0–44.1 | ~272,000 |
| 65 K | not measured (probe HTTP 400 — slot/parallel-seqs constraint at the `-c` ceiling) | | | |

Smoke (`bench_api_tool_call.py`): **4/5 single-call** (one length-cap fail on agentic-reasoning prose), multi-turn loop **5.57 s**.

OpenCode end-to-end: **browse 6.47 s 🥇 / search 15.64 s 🥇** — **2.07× / 2.27× faster than Gemma 4** (12.33 s / 35.55 s). New agent-loop speed leader.

Raw bench JSONs: [`docs/models/benchmarks/logs/qwen36-35b-a3b-turboquant-turbo3/`](../../models/benchmarks/qwen36-35b-a3b-turboquant-turbo3/).

### johndpope iso3 (prior sidecar — kept for RotorQuant comparison)

| Context | Cold prefill TTFT | Warm TTFT | Decode tok/s | Prefill tok/s |
|:--:|:--:|:--:|:--:|:--:|
| 512 | 0.63 s | 0.05 s | 46.3 | ~11,800 |
| 4 K | 15.5 s | 0.08 s | 32.0 | ~53,700 |
| 8 K | 56.6 s | 0.11 s | 23.2 | ~73,000 |
| 32 K | **>600 s (timeout)** | n/a | n/a | n/a |

Smoke: 5/5; multi-turn 8.48 s; OpenCode browse 20.5 s / search 151.18 s.

Raw bench JSONs: [`docs/models/benchmarks/logs/qwen36-35b-a3b-rotorquant-iso3/`](../../models/benchmarks/qwen36-35b-a3b-rotorquant-iso3/).

### Key takeaway

The cold-prefill regression on iso3 was the K-side compression compute, **not** the technique itself — TheTom's fork eliminates it by automatically dispatching K to `q8_0` while still compressing V. Net result: TheTom turbo3 wins on every workload tested (decode at every context size, cold prefill at every context size, warm cache, agent loops, multi-turn).

## Known limitations

- **iso3 cold prefill is slow at long contexts.** 32 K cold prefill exceeds 600 s on M3 Ultra. The fork's iso3 K dequant kernel is not yet as optimised as the `f16` baseline. Workaround: keep contexts ≤ 16 K cold, or warm the prompt cache before measuring.
- **Fork is a community port, not upstream.** Author `johndpope` actively maintains the branch (last commit 2026-04-15, with `Merge pull request #1 from alex-musick`). Re-pull + rebuild after upstream llama.cpp lands new features. There is no PyPI / Homebrew pin — track via `git log`.
- **No `--draft-model` speculative decoding tested with iso3.** The server *does* expose `--cache-type-{k,v}-draft`, but speculative decoding requires "the target context to support partial sequence removal" — and the iso3 cache currently does not. Server logs print `speculative decoding not supported by this context`.
- **No Anthropic API.** OpenAI-compatible only. For Claude Code, route via OpenAI provider.
- **GGUF only.** No MLX safetensors, no JANG, no JANGTQ.

## See also

- Technique reference: [`docs/models/techniques/model-technique-rotorquant.md`](../../models/techniques/model-technique-rotorquant.md)
- Upstream fork: [`johndpope/llama-cpp-turboquant`](https://github.com/johndpope/llama-cpp-turboquant)
- Original RotorQuant project: [`scrya-com/rotorquant`](https://github.com/scrya-com/rotorquant)
- TurboQuant paper: [arXiv 2504.19874](https://arxiv.org/abs/2504.19874) (ICLR 2026)
- Bench data: [`docs/models/benchmarks/logs/qwen36-35b-a3b-rotorquant-iso3/`](../../models/benchmarks/qwen36-35b-a3b-rotorquant-iso3/)
