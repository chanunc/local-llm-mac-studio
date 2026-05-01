# dflash-mlx Server Summary

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

`dflash-mlx` is a research-grade speculative-decoding server for Apple Silicon. It pairs a **target model** (standard MLX safetensors) with a small **DFlash drafter** (block-diffusion drafter from [arXiv:2602.06036](https://arxiv.org/abs/2602.06036)) to verify drafted token blocks against the target. On Qwen3.6-35B-A3B-4bit + the matching `z-lab/Qwen3.6-35B-A3B-DFlash` drafter, the runtime sustains **~89 tok/s decode at 512-token context** with **86.7% draft acceptance** on a single-shot prompt.

> **Technique reference:** for what DFlash is at the algorithm level, the cross-fork landscape (bstnxbt vs Aryagm), and the M3 Ultra workload-gated regression analysis, see [`docs/models/techniques/model-technique-dflash.md`](../../models/techniques/model-technique-dflash.md). This runbook covers operational steps only.

The PyPI package (`pip install dflash-mlx`) is published by [bstnxbt](https://github.com/bstnxbt/dflash-mlx). Version **0.1.4.1+** (from main branch) wraps `mlx_lm.server` and exposes the full OpenAI semantics — `tools[]`, `temperature`, `top_p`, `prompt_cache_size`, etc. — while the older 0.1.0 PyPI release uses a custom HTTPServer with no tool-call surface.

**Status: provisional sidecar.** Used for single-shot decode-throughput experiments and Qwen3.6 family DFlash benchmarks. Not yet a production candidate — depends on three local patches against upstream packages (see [Known limitations](#known-limitations)).

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌────────────────────────────────────────┐
│ Claude Code    │            │ dflash-serve (port 8098)               │
│ OpenCode       │─── LAN ───>│   ~/dflash-mlx-env/bin/dflash-serve    │
│ OpenClaw       │            │   wraps mlx_lm.server                  │
│ Pi             │            │   target: Qwen3.6-35B-A3B-4bit (~22GB) │
└────────────────┘            │   draft : Qwen3.6-35B-A3B-DFlash       │
                              │           (0.5B BF16, ~1GB)            │
                              │   OpenAI API only (no Anthropic)       │
                              └────────────────────────────────────────┘
```

`dflash-serve` runs out of `~/dflash-mlx-env/` (Python 3.11, separate from `vllm-mlx-env` / `mlx-openai-server-env` to avoid mlx-version conflicts). The server is a thin extension of `mlx_lm.server`'s `ModelProvider` + HTTP infrastructure — `DFlashModelProvider` swaps the generation engine to `stream_dflash_generate`. Models live in `~/.cache/huggingface/hub/` (no separate cache like LM Studio).

## Installation

**One-time on Mac Studio:**

```bash
ssh macstudio "/opt/homebrew/bin/python3.11 -m venv ~/dflash-mlx-env && \
  ~/dflash-mlx-env/bin/pip install -U pip && \
  ~/dflash-mlx-env/bin/pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'"
```

The PyPI release (`pip install dflash-mlx` → 0.1.0) lacks tool-calling support — install from main-branch git instead. Verified working at commit pinned by 0.1.4.1.

**Apply the patches** that `dflash-mlx 0.1.4.1` and `mlx-lm 0.31.3` need:

```bash
ssh macstudio "~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_dflash_mlx_serve.py && \
  ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_mlx_lm_match.py"
```

Both are idempotent. Re-run after `pip install -U dflash-mlx` or `pip install -U mlx-lm`.

**Pre-download the model pair** (~20 GB):

```bash
ssh macstudio "HF_HUB_ENABLE_HF_TRANSFER=1 ~/dflash-mlx-env/bin/python -c '
from huggingface_hub import snapshot_download
snapshot_download(\"mlx-community/Qwen3.6-35B-A3B-4bit\")
snapshot_download(\"z-lab/Qwen3.6-35B-A3B-DFlash\")
'"
```

## Starting the server

```bash
ssh macstudio "nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 \
  --max-tokens 512 \
  --log-level INFO \
  > /tmp/dflash-mlx.log 2>&1 &"
```

**`--draft-model` is required** for Qwen3.6 — the built-in `DRAFT_REGISTRY` in dflash-mlx 0.1.4.1 only auto-resolves Qwen3.5 family pairs. Without an explicit `--draft-model`, the server falls back to baseline (autoregressive) generation, defeating the point of running dflash-mlx.

**`--port 8098`** — explicitly avoid port 8000 (production primary on `vllm-mlx`) and port 1234 (`llmster`).

**Stop:** `ssh macstudio "pkill -f dflash-serve"`.

The startup banner prints target + draft + server framework + port. If you see `RuntimeError: DFlash server requires a resolved draft model before startup`, run `patch_dflash_mlx_serve.py` — that's bug #2 in the patch script.

## Tool use and reasoning

Tool use **works** in 0.1.4.1+ via `mlx_lm.server`'s built-in tokenizer detection. Verified on `mlx-community/Qwen3.6-35B-A3B-4bit`:

```bash
curl -s http://<MAC_STUDIO_IP>:8098/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model":"mlx-community/Qwen3.6-35B-A3B-4bit",
    "messages":[{"role":"user","content":"What is the weather in Paris?"}],
    "tools":[{"type":"function","function":{"name":"get_weather",
      "parameters":{"type":"object","properties":{"location":{"type":"string"}},"required":["location"]}}}],
    "temperature":0.0
  }' | python3 -m json.tool
```

Returns `finish_reason: "tool_calls"`, `tool_calls[0].function.name: "get_weather"`, `arguments: '{"location": "Paris"}'`. Reasoning blocks (`<think>…</think>`) are routed to `message.reasoning` separately from `message.content` (note: `reasoning`, not `reasoning_content` — mlx-lm naming, differs from llmster). Streaming uses `delta.reasoning` and `delta.content` deltas.

**Tool-call detection** is driven by `mlx_lm.generate.match()`. Without the [`patch_mlx_lm_match.py`](../../../scripts/patches/patch_mlx_lm_match.py) fix, multi-call benches crash with `KeyError: None` after the first tool-call match completes — discovered while running Phase 4 of the deploy plan. After the patch, 5/5 single-call scenarios pass and 3-turn multi-turn loops complete cleanly.

To **disable thinking** for benches that don't measure reasoning:

```bash
--chat-template-args '{"enable_thinking":false}'
```

This shrinks output token counts but does not affect tool-call correctness.

## Health check

No API key required.

```bash
# List models (target + everything else mlx_lm.server enumerates from the HF cache)
curl -s http://<MAC_STUDIO_IP>:8098/v1/models | python3 -m json.tool

# Plain chat round-trip
curl -s http://<MAC_STUDIO_IP>:8098/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"mlx-community/Qwen3.6-35B-A3B-4bit","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}' \
  | python3 -m json.tool

# Server log (server prefill timings + draft acceptance per request)
ssh macstudio "tail -f /tmp/dflash-mlx.log"
```

The server logs **per-request DFlash telemetry**: `122.3 tok/s | 81.2% accepted | 695 tokens | 6.0s | prompt: 528 tokens` plus a `prefill: 569/569 tokens | 0.3s` line. Draft acceptance under 50% suggests target/draft mismatch — verify the registry pair.

## Performance (Mac Studio M3 Ultra, 96 GB)

`mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash` on dflash-mlx 0.1.4.1, `temperature=0.0`, `block_tokens=16`. Bench script: [`scripts/bench/bench_api_server.py`](../../../scripts/bench/bench_api_server.py). Raw JSON: [`api-server-dflash-mlx.json`](../../models/benchmarks/qwen36-35b-a3b-4bit/api-server-dflash-mlx.json).

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512  | **89.5** | 1,366 | 0.39 |
| 4K   | 88.4 | **1,812** | 2.27 |
| 8K   | 87.0 | 1,524 | 5.40 |
| 32K  | 74.1 | 837 | 39.2 |

**Headline:** sustained decode rate stays above **74 tok/s even at 32K context** at 86.7% draft acceptance. Compare to llmster on `Qwen3.6-27B-6bit` at 32K: 26.3 tok/s decode (3.4× slower decode at the cost of 56× faster prefill). DFlash wins on decode-bound single-turn workloads; llmster wins on prefill-bound long-context multi-turn workloads.

**Workload-gated, not universally faster on M3 Ultra.** Local essay prompts regress (0.62×–0.98× across 1k–8k horizons) while math/reasoning and structured JSON reproduce upstream's wins (1.61× / 1.46×). Treat as a workload-gated throughput tool for deterministic reasoning or structured-output tasks, not a default replacement for plain `mlx_lm.server`. Full analysis + cross-fork comparison: [`docs/models/techniques/model-technique-dflash.md`](../../models/techniques/model-technique-dflash.md).

**Tool-call latency** ([`api-tool-test-dflash-mlx.json`](../../models/benchmarks/qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json)): 5/5 single-call scenarios pass at 1.68-6.08 s, 3-turn multi-turn loop completes in 5.9 s.

**Agent-bench** ([`agent-bench-dflash-mlx.json`](../../models/benchmarks/qwen36-35b-a3b-4bit/agent-bench-dflash-mlx.json)): browse 27.59 s wall median (13% faster than llmster on the smaller dense Qwen3.6-27B-6bit), search 54.78 s wall median (2.1× slower — 3-turn loop with 10K → 16K growing prefill favors llmster).

## Known limitations

- **Three local patches required.** `dflash-mlx 0.1.4.1` ships two bugs and `mlx-lm 0.31.3` ships one — see [Installation](#installation) and the patch scripts under [`scripts/patches/`](../../../scripts/patches/). Re-apply after every `pip install -U`.
- **`DRAFT_REGISTRY` does not include Qwen3.6 pairs.** Always pass `--draft-model` explicitly. The drafter architecture is supported; only the auto-resolve map is stale (PR-able upstream).
- **`bench_api_server.py` requires an enhancement.** `mlx_lm.server` emits reasoning under `delta.reasoning` (not `delta.reasoning_content`). The bench script was updated to recognize both — do not run an older bench script against this server or TTFT will measure as None.
- **MLX safetensors only.** No GGUF, no JANG, no JANGTQ, no `bailing_hybrid`. The drafter must match the target's hidden architecture (Qwen3.5 hybrid → Qwen3.6 hybrid is the only known-working family transfer in the registry).
- **No Anthropic API.** OpenAI `/v1/chat/completions`, `/v1/models`, `/v1/embeddings` (inherited from `mlx_lm.server`) only.
- **Model load is lazy.** First request after server start triggers the target + drafter load (target ~22 GB, drafter ~1 GB). Cold-start TTFT is ~3-5 s higher than the warm-cache numbers above.
- **Single greedy default.** `--temp 0.0` is the bench-friendly default; sampling controls work but DFlash's published numbers assume greedy decoding. Higher temperature reduces draft acceptance (drafter generations diverge from target's argmax path).
- **OpenCode tool-call benches need a `--base-url` override.** The agent-bench script's `discover_config()` reads the global OpenCode config's `baseURL`, not the project-local one — patched to accept `--base-url` as an override.
- **Closed acceptance for Qwen3.6-27B target.** No `z-lab/Qwen3.6-27B-DFlash` in any of the three MLX implementations' supported lists. Use Qwen3.6-35B-A3B (this server) or Qwen3.5-27B (via `ddtree-mlx`) instead.
- **Aryagm fork is not used here.** Cross-fork landscape (bstnxbt vs Aryagm — `tools[]` support, `qwen3_5_moe` adapter, decode tok/s) is in [`docs/models/techniques/model-technique-dflash.md`](../../models/techniques/model-technique-dflash.md#cross-fork-landscape-2026-04-30).

## See also

- [`docs/models/techniques/model-technique-dflash.md`](../../models/techniques/model-technique-dflash.md) — DFlash technique reference + M3 Ultra regression analysis
- [`docs/models/per-model/`](../../models/per-model/) — per-model deep dives (catalog stub: [`docs/models/model-summary.md`](../../models/model-summary.md))
- [`docs/models/benchmarks/qwen36-35b-a3b-4bit/`](../../models/benchmarks/qwen36-35b-a3b-4bit/) — raw bench JSONs
- [`docs/models/benchmarks/model-benchmark-api-server.md`](../../models/benchmarks/model-benchmark-api-server.md) — cross-server prefill / decode comparison
- [`docs/models/benchmarks/model-benchmark-api-tool-call.md`](../../models/benchmarks/model-benchmark-api-tool-call.md) — cross-server tool-call latency
- [`docs/models/benchmarks/model-benchmark-agent-tool-call.md`](../../models/benchmarks/model-benchmark-agent-tool-call.md) — end-to-end agent loop
- [`configs/clients/dflash-mlx/opencode.json`](../../../configs/clients/dflash-mlx/opencode.json) — OpenCode template (provisional, mirrors llmster posture)
- [`scripts/patches/patch_dflash_mlx_serve.py`](../../../scripts/patches/patch_dflash_mlx_serve.py) — dflash-mlx 0.1.4.1 startup + load fixes
- [`scripts/patches/patch_mlx_lm_match.py`](../../../scripts/patches/patch_mlx_lm_match.py) — mlx-lm tool-detection trie reset
- [`scripts/patches/patch_dflash_mlx_host.py`](../../../scripts/patches/patch_dflash_mlx_host.py) — only needed for dflash-mlx 0.1.0; obsoleted by `--host` flag in 0.1.4.1+
- [bstnxbt/dflash-mlx](https://github.com/bstnxbt/dflash-mlx) — upstream PyPI package
- [z-lab/dflash](https://github.com/z-lab/dflash) — original DFlash research repo
- [arXiv:2602.06036](https://arxiv.org/abs/2602.06036) — DFlash: Block Diffusion for Flash Speculative Decoding
