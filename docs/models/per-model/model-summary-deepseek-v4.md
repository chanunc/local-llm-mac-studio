# DeepSeek-V4 Family

## Overview

This document covers DeepSeek-V4-Flash deployment on the Mac Studio LLM lab:

- [What it is](#what-it-is) — the `deepseek4` architecture and why it needs a custom engine
- [Quantization landscape](#quantization-landscape) — every published GGUF/MLX quant and what fits 96 GB
- [Server landscape](#server-landscape) — the three community forks and why `ds4` is the Apple-Silicon path
- [Deployment recipe](#deployment-recipe-ds4--q2-imatrix) — build, download, launch
- [Benchmarks](#benchmarks-2026-05-18) — smoke, throughput, agent tool loop
- [Caveats](#caveats)
- [See also](#see-also)

---

## What it is

**`deepseek-ai/DeepSeek-V4-Flash`** (released 2026-04-24, MIT) is a **284 B-total / 13 B-active, 256-expert Mixture-of-Experts** model with a 1 M-token context. It is a reasoning model with three modes (`non-think` / `think-high` / `think-max`; Think Max needs ≥ 384 K context). The architecture is novel — **Hybrid Attention (Compressed Sparse Attention + Heavily Compressed Attention), Manifold-Constrained Hyper-Connections (mHC), Muon optimizer** — and registers as `model_type: deepseek4`, which **upstream `llama.cpp` does not implement** ([tracking issue #22319](https://github.com/ggml-org/llama.cpp/issues/22319)). Official quants are FP8/FP4 mixed precision; the official recommended loaders are vLLM and SGLang (both CUDA-only). Running it on Apple Silicon therefore requires a custom V4-aware engine.

The KV cache is extremely compressed by design (full 1 M context's compressed indexer ≈ 22 GB), which is what makes local long-context inference feasible and motivates on-disk KV persistence.

## Quantization landscape

All published GGUF/MLX quants of DeepSeek-V4-Flash, with on-disk size vs the 96 GB-class Mac Studio (≈ 103 GB reported unified memory, ~85 GB usable for weights+KV after OS):

| Repo | Quant | Size | Fits 96 GB? | Engine |
|:--|:--|:--:|:--:|:--|
| **`antirez/deepseek-v4-gguf`** | **IQ2XXS-w2Q2K-AProjQ8-SExpQ8-OutQ8-chat-v2-imatrix** | **81 GB** | ✅ (deploy choice) | `ds4` |
| `antirez/deepseek-v4-gguf` | IQ2XXS …chat-v2 (legacy, non-imatrix) | 81 GB | ✅ (prefer imatrix) | `ds4` |
| `antirez/deepseek-v4-gguf` | Q4KExperts-F16HC-…-chat-v2 | 153–165 GB | ❌ | `ds4` (≥256 GB) |
| `antirez/deepseek-v4-gguf` | MTP-Q4K-Q8_0-F32 | 3.5 GB | n/a | `ds4` speculative add-on only |
| `persadian/DeepSeek-V4-Flash-GGUF` | IQ1_S-XL (2 shards) | 61.5 GB | ✅ size, ❌ engine | `arishma108/llama.cpp feat/v4-port-cuda` — **CUDA-only, no Metal** |
| `batiai/DeepSeek-V4-Flash-GGUF` | Q3_K_M | 135 GB | ❌ | (needs upstream `deepseek4`) |
| `batiai/DeepSeek-V4-Flash-GGUF` | Q4_K_M / Q5_K_M / Q6_K / Q8_0 | 172 / 202 / 233 / 302 GB | ❌ | (needs upstream `deepseek4`) |

**Net:** the persadian IQ1_S-XL (the smallest, 61.5 GB) is dead on Apple Silicon because its only engine is CUDA-only and its 1-bit weights are calibrated for that fork; the batiai Q3–Q8 GGUFs assume upstream `deepseek4` (unmerged) and all exceed RAM anyway. **The single viable Mac Studio combo is `antirez` `q2-imatrix` (81 GB) on the `ds4` engine** — antirez's own quant on antirez's own engine, the only author-matched + RAM-fitting + Apple-Silicon + tool-call-capable pairing.

## Server landscape

Three community DeepSeek-V4 implementations exist:

| Project | Type | Backend | Tool calling | Verdict |
|:--|:--|:--|:--|:--|
| [`antirez/ds4`](https://github.com/antirez/ds4) | Standalone native engine (C + Metal) | **Metal** / CUDA | **Native DSML ↔ OpenAI/Anthropic mapping** | ✅ chosen — see [`docs/servers/ds4/summary.md`](../../servers/ds4/summary.md) |
| [`antirez/llama.cpp-deepseek-v4-flash`](https://github.com/antirez/llama.cpp-deepseek-v4-flash) | Standalone `llama.cpp`-derived fork | Metal | Undocumented for V4 (`--jinja` not confirmed) | ⚠ untested fallback — likely tool-call failure point |
| [`arishma108/llama.cpp`](https://github.com/arishma108/llama.cpp) `feat/v4-port-cuda` | `llama.cpp` fork (parent `cchuter/llama.cpp`) | **CUDA only** | Not documented | ❌ no Metal — cannot run on Apple Silicon |

`ds4` ("DwarfStar 4") is purpose-built for this one model: DS4-specific GGUF loading, DSML prompt rendering, an unguessable-tool-ID → exact-sampled-DSML replay map (so multi-turn KV prefixes stay byte-aligned across stateless agent requests), RAM + on-disk KV state, and an OpenAI + Anthropic + Responses HTTP server with documented opencode/Pi/Codex integration. It is the only candidate that both runs on Metal and has working agent tool calling, so the "try all combinations" search collapses to one viable combo.

## Deployment recipe (`ds4` + q2-imatrix)

Full operational runbook: [`docs/servers/ds4/summary.md`](../../servers/ds4/summary.md). Summary:

```bash
# 1. Build (pure C + Metal, ~3 s, no cmake)
ssh macstudio "cd ~ && git clone --depth 1 https://github.com/antirez/ds4.git && cd ds4 && make -j8"

# 2. Download the 81 GB q2-imatrix GGUF (resumable; symlinks ./ds4flash.gguf)
ssh macstudio "cd ~/ds4 && ./download_model.sh q2-imatrix"

# 3. Launch the sidecar on port 8101
ssh macstudio "cd ~/ds4 && nohup ./ds4-server --host 0.0.0.0 --port 8101 \
  --ctx 65536 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192 \
  --trace /tmp/ds4-trace.txt > /tmp/ds4-server.log 2>&1 &"

# Stop
ssh macstudio "pkill -f 'ds4-server'"
```

API model id: **`deepseek-v4-flash`** (OpenAI `/v1/chat/completions` with `tools`/`tool_choice`; also `/v1/messages`, `/v1/responses`). Thinking is on by default at "high" effort; pass `model=deepseek-chat` or `think=false` for non-reasoning replies.

## Benchmarks (2026-05-18)

`antirez/deepseek-v4-gguf` IQ2XXS-imatrix on `ds4` port 8101, Mac Studio M3 Ultra 96 GB-class. Pre-bench hygiene applied (all other LLM servers stopped, 97 % memory free). Raw JSON: [`docs/models/benchmarks/deepseek-v4-flash/`](../benchmarks/deepseek-v4-flash/).

**Smoke (`bench_api_tool_call.py`):** ✅ **5/5 single-call**, each `finish_reason=tool_calls` (2.2–5.4 s); multi-turn 3 turns / 8.95 s clean (`read_file → write_file → stop`).

**Throughput (`bench_api_server.py`, 50-tok gen, temp 0):**

| Context | Median TTFT | Decode tok/s | Prefill tok/s |
|:--:|:--:|:--:|:--:|
| 529 | 0.12 s | **34.6** | 4,512 |
| 4,114 | 5.58 s | 26.9 | 737 |
| 8,209 | 16.0 s | 26.6 | 513 |
| 32,785 | 6.8 s warm / 37.9 s cold | 25.4 | 4,851 warm / 864 cold |

Flat ~25–35 tok/s decode (excellent for 284 B @ 2-bit — the 13 B-active MoE path carries it). Cold long-context prefill is the cost (~860 tok/s @ 32 K); the disk KV cache cuts a 37.9 s cold 32 K prefill to 6.8 s warm (5.5×).

**Agent loop (`bench_agent_tool_call.py`, opencode, 1 warmup + 3 measured):**

| Scenario | Wall median | LLM median | Turns | Tools |
|:--|:--:|:--:|:--:|:--|
| Browse www.example.com | **18.78 s** (11.24–21.69 p5–p95) | 17.96 s | 2 | `webfetch` |
| Browse Hackernews latest topic | **28.22 s** (25.58–31.97 p5–p95) | 27.39 s | 3 | `webfetch` |

Zero errors, `webfetch` fired every measured run, well under the 250 s p95 ceiling. **DeepSeek-V4-Flash runs the agent tool loop end-to-end on Apple Silicon** — mid-pack latency (slower than the leanest lm-studio MLX mains, faster than several 70 B+ dense uncensored models), which is competitive for a 284 B knowledge-class model at 2-bit on a personal machine.

## Caveats

- **`ds4` is GGUF-locked** to `antirez/deepseek-v4-gguf` — no persadian/batiai/unsloth GGUF, no generic GGUF.
- **Only `q2-imatrix` fits** 96 GB-class RAM; `q4-imatrix` (153 GB) and third-party Q3–Q8 (135–302 GB) do not.
- **Cold 32 K prefill ≈ 38 s.** Warm the prompt or accept first-hit latency; disk KV makes subsequent hits cheap.
- **Single graph worker** — concurrent requests serialize, no batching.
- **Alpha engine** — days-old, "alpha quality" per its own README, GPT-5.5-assisted; behaviour can change across `git pull`s. Capture `--trace` for upstream issues.
- **Never run the CPU path** (`make cpu` / `--cpu`) on macOS — documented macOS VM bug kernel-panics the machine. Metal only.
- **2-bit quality** — objective-vector validated against the official implementation; antirez reports quasi-frontier behaviour, but it is still an aggressive 2-bit routed-expert quant.

## See also

- Server runbook: [`docs/servers/ds4/summary.md`](../../servers/ds4/summary.md)
- Catalog entry: [`docs/models/model-summary.md`](../model-summary.md#deepseek-v4-flash-284b13b-active-moe-ds4)
- Bench data: [`docs/models/benchmarks/deepseek-v4-flash/`](../benchmarks/deepseek-v4-flash/)
- Engine: [`antirez/ds4`](https://github.com/antirez/ds4) · GGUF: [`antirez/deepseek-v4-gguf`](https://huggingface.co/antirez/deepseek-v4-gguf) · Official: [`deepseek-ai/DeepSeek-V4-Flash`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
