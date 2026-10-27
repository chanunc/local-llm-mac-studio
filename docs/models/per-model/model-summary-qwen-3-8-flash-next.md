# Qwen3.8-Flash-Next

## Overview

This document covers Qwen3.8-Flash-Next on the Mac Studio LLM lab:

- [What it is](#what-it-is): the `qwen4exp` architecture and why it needed a new engine path
- [Quantization landscape](#quantization-landscape): the published GGUFs and what fits 96 GB
- [Server landscape](#server-landscape): Strata vs llama.cpp master, and why MLX and the lab's older builds cannot load it
- [Deployment recipe](#deployment-recipe-strata--iq3_s): build, download, launch
- [Benchmarks](#benchmarks-2026-10-26): smoke, throughput, agent loop, against llama.cpp on the same GGUF
- [Caveats](#caveats)
- [See also](#see-also)

---

## What it is

**`Qwen/Qwen3.8-Flash-Next`** (Qwen license "other") is a **125B Mixture-of-Experts** model.

- **Experts:** 48 layers × 512 routed experts (24,576 in total), 10 routed per token, plus a shared expert.
- **Mixers:** it mixes Gated DeltaNet linear attention with QSA attention layers and adds hyper-connections.
- **Lookup table:** a per-token n-gram table is shipped as a separate 28.8 GB GGUF shard and read a few rows per token.
- **Other parts:** an MTP head for self-drafting and a vision projector.
- **Context:** 262K tokens.

The GGUF architecture name is **`qwen4exp`**. It is not a Qwen3.8-27B variant; that family lives in [`model-summary-qwen-3-8.md`](model-summary-qwen-3-8.md).

## Quantization landscape

[`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) (Apache-2.0, ungated). Every size ships as two shards: weights, plus the same 28.8 GB IQ4_NL n-gram table.

| Size | Shard 1 | Download | Fit on 96 GB (Strata `resident_cap` 72.2 GB) |
|:--|--:|--:|:--|
| Q2_0 | 37.6 GB | 66.4 GB | resident |
| IQ2_XS (= Swift 1.5 size) | 39.2 GB | 68.0 GB | resident (not offered on Mac by Strata setup) |
| IQ3_XXS | 47.0 GB | 75.8 GB | resident |
| **IQ3_S** (deployed) | **54.8 GB** | **83.6 GB** | resident, ~4.5 GB spare |
| Unsloth UD-Q4_K_XL | 82.6 GB (repacked) | 111 GB | experts stream from the SSD |

Other releases that Strata knows about: agentionai **Gyro-S / Gyro-M**, trellis experts in one file with the table inside. ISTA-DASLab also publishes a **Coder**, 256 of the 512 experts kept per layer for code. UkisAI publishes **Swift 1.5**, a fine-tune that thinks shorter. Strata's setup does not offer Coder or Swift on Mac yet.

## Server landscape

| Path | Loads it? | Notes |
|:--|:--|:--|
| **Strata v0.2.6** (`strata` :8102) | ✅ | Model-specific Metal engine with MTP `--spec 2`. About 1.8× llama.cpp decode on the same GGUF. [Runbook](../../servers/strata/summary.md). |
| llama.cpp master `d854d98` (2026-10-26) | ✅ | `qwen4exp` is in master. Built as the benchmark-only `~/llama-cpp-qwen4exp`. Plain decode, no MTP. |
| Lab llama.cpp `ac4cdde` / `4df29be` (`llama-cpp-mtp` :8100) | ❌ | Predate `qwen4exp`. |
| mlx-lm 0.31.3 / vllm-mlx / oMLX / vmlx | ❌ | No `qwen4exp` model class (only `qwen3_next`). |
| lm-studio | not checked | Depends on its bundled llama.cpp runtime version. |

## Deployment recipe (Strata + IQ3_S)

Full detail is in the [Strata runbook](../../servers/strata/summary.md). Short form:

```bash
ssh macstudio "git clone --branch v0.2.6 --depth 1 https://github.com/Niko1221/Strata.git ~/Strata && \
  cd ~/Strata && ./setup.sh --model IQ3_S --context 65536 --port 8102 --host 0.0.0.0 --vision no --no-browser --no-start --yes"
ssh macstudio "cd ~/Strata && STRATA_ALLOWED_HOSTS=<MAC_STUDIO_IP>,macstudio,<TAILSCALE_HOST> \
  nohup .venv/bin/python serve/server.py --engine strata --config strata-iq3_s.json --port 8102 > /tmp/strata.log 2>&1 &"
```

The llama.cpp baseline on the same files:

```bash
ssh macstudio "nohup ~/llama-cpp-qwen4exp/build/bin/llama-server \
  -m ~/Strata-data/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf \
  -ngl 99 -fa on -np 1 -c 65536 --jinja --alias qwen38-flash-next-iq3s-llamacpp \
  --host 0.0.0.0 --port 8100 > /tmp/llama-cpp-qwen4exp.log 2>&1 &"
```

## Benchmarks (2026-10-26)

Mac Studio M3 Ultra 96 GB, one server resident at a time, all other LLM servers stopped. Same IQ3_S GGUF for both engines. Strata v0.2.6 (`--spec 2` + MTP, ctx 65536); llama.cpp master `d854d98` (`-ngl 99 -fa on -np 1 -c 65536 --jinja`).

### Decode (`bench_api_server.py`, 50 tokens, medians)

| Context | Strata (MTP) | llama.cpp | Strata ÷ llama.cpp |
|:--:|:--:|:--:|:--:|
| 578 | **74.3** | 40.2 | 1.85× |
| 4,163 | **70.0** | 39.0 | 1.79× |
| 8,258 | **67.5** | 38.8 | 1.74× |
| 32,834 | **70.9** | 36.9 | 1.92× |
| 60,068 | **66.3** | 35.2 | 1.89× |

### Cold prefill (from the engine logs, untimed probe request)

| Prompt | Strata | llama.cpp | Strata ÷ llama.cpp |
|:--|:--:|:--:|:--:|
| ~4K new tokens | 741 tok/s (4,163) | 676 tok/s (4,101) | 1.10× |
| ~25–33K new tokens | 786 tok/s (32,834) | 653 tok/s (25,092) | 1.20× |
| ~27K new on a 32K cached prefix (60K total) | 755 tok/s (27,300) | 628 tok/s (27,750) | 1.20× |

The timed `bench_api_server.py` runs hit each server's prompt cache (TTFT 0.05–0.10 s), so their `prefill_tps` column is not prompt reading. Treat it as cache-hit TTFT only.

### API tool calls (`bench_api_tool_call.py`)

| | Single-call | Per call | Multi-turn |
|:--|:--:|:--:|:--:|
| Strata | ✅ 5/5 | 1.49–2.71 s | 3 turns, 4.83 s |
| llama.cpp | ✅ 5/5 | 1.82–2.97 s | 3 turns, 6.86 s |

### OpenCode agent loop (`bench_agent_tool_call.py`, 1 warmup + 3 measured)

| Engine | Browse (median) | Search (median) | Turn 1 input |
|:--|:--:|:--:|:--|
| Strata | 20.95 s (20.91–20.97) | 24.94 s (24.92–24.97) | ~11.9K tokens re-read every run (15.5 s) |
| Strata + `"env_to_user": true` | 20.99 s | 24.75 s | unchanged, still `0 reused` |
| llama.cpp | **9.67 s** (8.14–12.56) | **14.84 s** (11.56–34.53, one 3-turn outlier) | 4 new tokens (slot cache matched by LCP similarity) |

Both engines were 2 turns with `webfetch` and no errors.

- **llama.cpp wins the agent loop despite decoding at about half Strata's speed.** OpenCode's title request runs before each session, and Strata's Metal engine then loses the cached system prompt (see [Caveats](#caveats)).
- **Reasoning length differs between the two engines.** llama.cpp's turn 1 produced 146–252 tokens against Strata's 56–148, so the two are not doing identical work per turn.

### Against upstream's M5 Max numbers

Strata reports, for resident IQ3_S on a 128 GB M5 Max: decode 94–102 tok/s with MTP, and cold prefill about 1,140–1,320 tok/s. llama.cpp there gives 51.1 tok/s decode and 791 / 730 tok/s prefill at 4K / 32K.

On the M3 Ultra, the **decode ratio holds** (1.74–1.92× here against about 1.85× there). The **prefill advantage mostly disappears** (1.1–1.2× here against 1.6–1.8×). Strata's prompt kernels use Metal 4 `matmul2d`, which runs on the M5's GPU neural accelerators. The M3 has none, so they fall back to the plain simdgroup matrix units.

## Caveats

- **Strata's Mac engine reuses only the live session's prefix.** In a test of system prompt A (13,306 tokens), then an unrelated 19-token request, then A again, A was re-read from scratch both times (`0 reused`, 17.1 s). OpenCode sends a short title request (`small_model`) at the start of every session, so every new session re-reads its ~11.9K-token system prompt: about 15.6 s on the M3 Ultra, which is most of each agent-bench run. Strata's documented conversation checkpoints and system-prompt root, and its `"env_to_user": true` opt-in, made no difference here (measured: same wall time). This is observed behaviour of v0.2.6; the root cause is not investigated.
- **One request at a time** on Strata's Metal engine (`--parallel` not ported). `-np 1` was used on llama.cpp too, for a like-for-like comparison.
- **Context measured to 60K.** The model's 262K was not tried, because IQ3_S has about 4.5 GB of memory headroom under Strata's cap.
- **Vision off** in this deploy (`--vision no`). Strata's GPU vision reader (`strata-vision`) was not benchmarked.
- **One transient failure.** Two OpenCode runs timed out at 300 s with 0 turns right after a Strata restart, and no request reached the server. A rerun right after was clean, and a direct curl worked. The cause was not found.

## See also

- Strata runbook: [`docs/servers/strata/summary.md`](../../servers/strata/summary.md)
- Catalog entry: [`docs/models/model-summary.md`](../model-summary.md#qwen38-flash-next-125b-moe-strata)
- Raw JSON: [`docs/models/benchmarks/logs/qwen38-flash-next-iq3s/`](../benchmarks/logs/qwen38-flash-next-iq3s/)
- Deploy plan: [`plans/done/plan-strata-macstudio-deploy.md`](../../../plans/done/plan-strata-macstudio-deploy.md)
- GGUF: [`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) · Model: [`Qwen/Qwen3.8-Flash-Next`](https://huggingface.co/Qwen/Qwen3.8-Flash-Next) · Engine: [`Niko1221/Strata`](https://github.com/Niko1221/Strata)
