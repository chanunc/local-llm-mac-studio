# Zyphra ZAYA1-8B

Reasoning-tuned sparse MoE released by **Zyphra on 2026-05-06** ([blog](https://www.zyphra.com/post/zaya1-8b), [tech report arXiv:2605.05365](https://arxiv.org/abs/2605.05365), [model card](https://huggingface.co/Zyphra/ZAYA1-8B)). **8.4 B total / 760 M active** with a custom attention block (Compressed Convolutional Attention, "CCA") and top-1 MoE routing — neither part is stock `mlx_lm` or `llama.cpp`. Apache-2.0.

## Overview

- [Architecture](#architecture) — what's actually in the model (CCA layers, top-1 MoE, learned residual scaling)
- [Markovian RSA — how the headline numbers are produced](#markovian-rsa--how-the-headline-numbers-are-produced) — recursive self-aggregation with bounded tails, *not* trained-in
- [Performance claim legitimacy](#performance-claim-legitimacy) — vendor numbers, what they cost, third-party reproduction
- [Quantization candidates](#quantization-candidates) — JANGTQ4 vs MXFP4 vs kyr0 8-bit MLX vs lainlives "GGUF"
- [Server-fit matrix on this stack](#server-fit-matrix-on-this-stack) — which runtimes can actually load it today
- [Chosen path — vmlx-swift-lm via Osaurus](#chosen-path--vmlx-swift-lm-via-osaurus) — why Osaurus, measured performance + known JANGTQ HTTP-path regression
- [Deploy recipe (as executed 2026-05-12)](#deploy-recipe-as-executed-2026-05-12) — exact commands that produced the bench numbers
- [Open questions](#open-questions)
- [See also](#see-also)

## Architecture

From the JANGTQ4 card and the technical report:

- **80 decoder layers**, alternating CCA attention + top-1 MoE
- Hidden size **2048**, **16 query heads / 2 KV heads**, head dim 128
- **16 routed experts per MoE layer**, top-1 routing with a "MOD" skip route
- **Compressed Convolutional Attention** state per attn layer: standard KV plus `conv_state [B,1280,2]` and `prev_hs [B,2048]` — i.e. the cache is *not* a flat KV tensor, it carries a tiny per-layer recurrent state alongside KV
- Context length **131,072**, `rope_theta=5_000_000`
- Novel **MLP-based expert router** + **learned residual scaling** to control depth-wise norm growth
- Tokenizer + `chat_template.jinja` carried verbatim from the upstream source bundle
- Capabilities sidecar: `family=zaya`, `supports_thinking=False`, `tool_parser=zaya_xml`

The CCA state is the load-bearing reason this model needs new runtime code in every server family — flat KV cache loaders silently corrupt turn 2+.

## Markovian RSA — how the headline numbers are produced

User asked specifically about "Markovian RSA Boost" — the technique is just **Markovian RSA** in the paper. **RSA = Recursive Self-Aggregation** (not Rational Speech Acts). It is an **inference-time** scheme; training-time involvement is limited to SFT + RL teaching the model to follow the aggregation prompts.

Mechanism (Zyphra blog, verbatim phrasing kept):

> "generate multiple traces in parallel, extract fixed-length tail segments from the traces, and then create new aggregation prompts by sub-sampling a few references from the candidate pool"

Operationally:

1. Generate N parallel CoT traces.
2. Keep only the last 4K tokens of each (the "Markovian" piece — borrowed from Markovian Thinker; only the bounded tail crosses the boundary).
3. Sub-sample tails as references, build a fresh aggregation prompt, re-run.
4. Recurse until a budget is exhausted.

Cost shape: a "normal" run uses a **40 K intermediate-CoT budget / 4 K tail**. The frontier-matching headline numbers (AIME'25 91.9, HMMT'25 89.6) use **~5.5 M tokens per problem total** on the "APEX extra-high compute" setting. So "boost" = trading wall-time and tokens for accuracy. None of the lab's existing benchmark harnesses (`bench_api_server.py`, `bench_agent_tool_call.py`) implement this loop — they'd measure the *base* model only.

## Performance claim legitimacy

Vendor-reported only. Treat the headline numbers as Zyphra-attested. As of 2026-05-12 no third-party reproduction has surfaced.

**Model-card headlines** ([HF card](https://huggingface.co/Zyphra/ZAYA1-8B)):

| Benchmark | Score |
|:--|:--|
| AIME'26 | 89.1 |
| HMMT Feb.'26 | 71.6 |
| IMO-AnswerBench | 59.3 |
| LiveCodeBench-v6 | 65.8 |
| GPQA-Diamond | 71.0 |
| MMLU-Pro | 74.2 |
| IFEval | 85.58 |

**Blog headlines** push higher with Markovian RSA at extreme TTC: HMMT'25 89.6 vs Claude 4.5 Sonnet 88.3, AIME'25 91.9, "approaching DeepSeek-V3.2" on APEX-shortlist. Those are the 5.5 M-tokens-per-problem numbers, not single-shot decode.

Reading: the model is competitive with Mistral-Small-4-119B at normal decode budgets and approaches frontier scores only when you pay for Markovian RSA. The "60 M active parameters punching at Sonnet weight" framing is real but conditional.

## Quantization candidates

User-provided candidates plus one extra surfaced by the runtime research:

| Quant | Repo | Size | Notes |
|:--|:--|:--|:--|
| **JANGTQ4** | [JANGQ-AI/ZAYA1-8B-JANGTQ4](https://huggingface.co/JANGQ-AI/ZAYA1-8B-JANGTQ4) | **4.65 GiB** | 4-bit MXTQ routed experts + 8-bit affine non-routed (attn 8, router 16, embed/lm_head 8, cca_conv 16, norms_residual 16). Pre-stacked `zaya_block.experts.switch_mlp` layout. Includes `jangtq_runtime.safetensors` sidecar. **Bound to the Swift runtime** by the README. |
| **JANGTQ2** | (same family, surfaced in the engine's evidence pass) | smaller | 2-bit routed experts. Decode parity with JANGTQ4 per the fork's 2026-05-09 evidence pass. |
| **MXFP4** | (Zyphra-/community-published; surfaced as the perf-leading format in the vmlx-swift-lm evidence pass) | ~larger | Microscaling 4-bit. **Fastest** of the three on the Swift engine — 71.8 tok/s vs 57.2 tok/s for JANGTQ4 at b9da180. |
| **MLX 8-bit** | [kyr0/zaya1-base-8b-8bit-MLX](https://huggingface.co/kyr0/zaya1-base-8b-8bit-MLX) | 9.43 GB | Base (not instruct). Requires [mlx-lm PR #1261](https://github.com/ml-explore/mlx-lm/pull/1261) or kyr0's `feat/zaya-support` fork. |
| **GGUF (lainlives)** | [lainlives/ZAYA1-8B-GGUF](https://huggingface.co/lainlives/ZAYA1-8B-GGUF/tree/main) | **empty repo** | Only `.gitattributes` (1.5 KB) + `README.md` (713 B). No `.gguf` blobs. **Unusable artifact today.** Even if blobs existed, llama.cpp has no ZAYA arch — see [issue #22776](https://github.com/ggml-org/llama.cpp/issues/22776), open with no PR. |

JANGTQ4 over JANGTQ2: same decode speed in the fork's published numbers, JANGTQ4 has more headroom on quality (no published perplexity but 4-bit MXTQ is the better-understood tier in this lab via Qwen3.6 JANGTQ4 / Ling JANGTQ2). MXFP4 is the speed leader but Zyphra hasn't published a quality table for it on the reasoning benchmarks; defer until the JANGTQ4 baseline is in place.

## Server-fit matrix on this stack

| Server | Status | What it would need |
|:--|:--|:--|
| **llama.cpp / lm-studio / llama-cpp-turboquant / ollama** | ❌ blocked | Port CCA layer + top-1 MoE block to llama.cpp ([issue #22776](https://github.com/ggml-org/llama.cpp/issues/22776), no PR). Also re-generate GGUFs — the lainlives repo is empty. Multi-week upstream port. |
| **`vmlx` (our bundled-Python `vmlx_engine.cli`)** | ⚠️ partial | The [jjang-ai/vmlx](https://github.com/jjang-ai/vmlx) README lists `ZAYA (CCA + MoE)` under Text LLMs, but the MLX Studio DMG we run is older. Would need a DMG bump first, plus a non-JANGTQ4 bundle (the JANGTQ4 pre-stacked layout is Swift-only). Candidate: bf16 source or kyr0 8-bit MLX. |
| **`mlx-lm.server` (libexec)** | ⚠️ patch path | Pip-install kyr0's `feat/zaya-support` fork into a fresh venv, launch via the libexec binary per the CLAUDE.md note about `/opt/homebrew/bin/mlx_lm.server` being a python3.11 symlink. Waits on [PR #1261](https://github.com/ml-explore/mlx-lm/pull/1261) for upstream. Quant: kyr0 8-bit MLX. |
| **`mlx-openai-server`** | ⚠️ patch path | Same fork install in its venv; its trie cache + JANG patch can conflict with custom architectures, verify on load. Quant: kyr0 8-bit MLX. |
| **`vllm-mlx`** | ⚠️ port path | Vendor ZAYA modeling code the way `bailing_hybrid` was vendored from [mlx-lm PR #1227](https://github.com/ml-explore/mlx-lm/pull/1227) for Ling. CCA cache needs a new KV-cache class. Medium-high effort. |
| **`dflash-mlx`** | ❌ no drafter | Wraps mlx-lm — depends on the libexec path above *and* a published ZAYA drafter (none exists). |
| **`vmlx-swift-lm` (new server type)** | ✅ supported today | Native ZAYA path via [osaurus-ai/vmlx-swift-lm](https://github.com/osaurus-ai/vmlx-swift-lm) (commit `b9da180`, 2026-05-07). Files: `Libraries/MLXLLM/Models/Zaya.swift` (48,586 B), `Libraries/MLXLMCommon/Cache/ZayaCCACache.swift`, `Libraries/BatchEngine/BatchZayaCCACache.swift`. Quants: JANGTQ4 / JANGTQ2 / MXFP4 all benched. Consumed by the **Osaurus** macOS app (`brew install --cask osaurus`) which exposes OpenAI + Anthropic + Ollama-compatible APIs. |

## Chosen path — vmlx-swift-lm via Osaurus

**Why Osaurus over building the Swift package directly:**

1. **No Xcode build step.** `brew install --cask osaurus` ships the same `vmlx-swift-lm` engine compiled and signed. The CLI front-door is `osaurus serve`.
2. **OpenAI + Anthropic + Ollama API surface.** Plugs into the existing client templates (OpenCode, OpenClaw, Claude Code) the same way oMLX / lm-studio do — no new client config shapes to invent.
3. **Engine pin matches the JANGTQ4 README.** The fork's evidence pass at commit `b9da180` is the runtime-pin that JANGTQ4 explicitly calls for. The released Osaurus cask tracks the same fork.
4. **Continuous batching, multi-tier KV cache, TurboQuant KV compression** are all built in — same engine that powers Osaurus's stress harness (199/199 mixed-concurrent in their published `STRESS-TEST-RESULTS.md`).

**Measured performance on M3 Ultra 96 GB** — `bench_api_server.py` against `http://127.0.0.1:1337/v1`, 50-token generations, 1 warmup + 2 timed runs, median. Raw JSON: [`docs/models/benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json`](../benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json).

| Context | TTFT | Decode tok/s | Prefill tok/s |
|---:|---:|---:|---:|
| 512 | 2.73 s | 7.3 | 208 |
| 4096 | 5.09 s | 7.0 | 876 |
| 8192 | 8.00 s | 7.9 | 1112 |
| 32768 | 31.66 s | 7.8 | 1122 |

**Known JANGTQ HTTP-path regression.** The fork's own `RunBench` evidence pass at the same commit on M4 Max reports **57.2 tok/s** decode for JANGTQ4 — **8× our measured HTTP number**. Root cause documented in [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057): cask 0.18.13 / engine pin `b9da180` is missing both the `BatchEngine.generate` B=1 solo fast path *and* the JANGTQ Hadamard `newv[8]` + cached-meta kernel optimization. PR #1057 bumps the engine to `cb8b3df` and restores both. Until that ships, treat ZAYA1 via Osaurus as **functional but speed-degraded** on the OpenAI HTTP API. The regression is engine-internal — it persists after Event-4 hygiene (verified by killing LM Studio's 61 GB llmworker mid-bench; numbers were identical before and after).

**Agent loop bench (OpenCode → ZAYA1 via the SSH-tunneled HTTP path)** — `bench_agent_tool_call.py --scenario browse --runs 1 --warmup 0`. Raw JSON: [`docs/models/benchmarks/zaya1-8b/agent-bench-vmlx-swift-lm.json`](../benchmarks/zaya1-8b/agent-bench-vmlx-swift-lm.json).

| Scenario | Wall time | Turns | Tools fired | Output tokens | Exit code |
|:--|---:|:--:|:--|---:|:--:|
| `Browse www.example.com` | **300.04 s** (OpenCode wall-time killed) | 1 (`step_start: 1, step_finish: 0`) | none | 0 | -1 |

**The agent loop never completed.** OpenCode terminates a run at 300 s if no `step_finish` event has fired. At the regressed 7-8 tok/s decode + a ~10K-token system prompt full of tool definitions, ZAYA1 never reaches the first tool-call decision in time. Same shape as the failure mode previously documented for Gemma 4 31B-it bf16 + MTP drafter — the bottleneck is wall-time vs OpenCode's hard cap, not the model's tool-calling competence. End-to-end agent benchmarks against ZAYA1 are blocked until [PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) lands and restores the JANGTQ B=1 fast path. Re-run this bench (and add the `search` scenario) once the cask picks up `cb8b3df`.

**Reference numbers from the fork's evidence pass** (M4 Max 128 GB, `RunBench` harness, not HTTP):

| Quant | TTFT | Decode tok/s |
|:--|---:|---:|
| JANGTQ4 | 63-66 ms | 57.2 |
| JANGTQ2 | 64-68 ms | 57.1 |
| MXFP4 | 73-75 ms | 71.8 |

Memory-bandwidth scaling implies M3 Ultra should match or exceed those numbers (~1.5× bandwidth vs M4 Max), so the post-fix expected ceiling is **~75-110 tok/s** depending on quant. Re-bench after the cask picks up the `cb8b3df` pin.

**Coexistence:** Osaurus binds **port 1337** by default — no conflict with the rest of the stack (8000 / 1234 / 8098 / 8099 / 8188). Default bind address is **127.0.0.1** and `osaurus serve --expose --yes` does *not* actually rebind off loopback (flips `exposeToNetwork: true` in the runtime config but the listener stays on 127.0.0.1; appears to need GUI confirmation that doesn't fire over SSH). LAN clients: tunnel with `ssh -L 1337:127.0.0.1:1337 macstudio` until the rebind path is fixed.

## Deploy recipe (as executed 2026-05-12)

```bash
# 1. Install Osaurus cask (one-time).
ssh macstudio "/opt/homebrew/bin/brew install --cask osaurus"

# 2. Pull the JANGTQ4 bundle. Saves to ~/.osaurus/models/JANGQ-AI/ZAYA1-8B-JANGTQ4
#    (NOT ~/MLXModels — see path-mismatch caveat below).
ssh macstudio "/opt/homebrew/bin/osaurus pull JANGQ-AI/ZAYA1-8B-JANGTQ4"

# 3. Event-4 hygiene — kill memory-hungry servers. lm-studio was holding
#    61 GB with its prior main loaded; unload it first.
ssh macstudio "~/.lmstudio/bin/lms server stop; ~/.lmstudio/bin/lms unload --all"

# 4. Start Osaurus. OSU_MODELS_DIR override is REQUIRED — osaurus serve
#    defaults to reading ~/MLXModels/ which doesn't exist.
ssh macstudio "/opt/homebrew/bin/osaurus stop 2>/dev/null; sleep 2; \
  OSU_MODELS_DIR=\$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 \
  > /tmp/osaurus.log 2>&1 &"

# 5. Smoke (loopback — --expose doesn't actually rebind):
ssh macstudio "curl -s http://127.0.0.1:1337/v1/models | python3 -m json.tool"
ssh macstudio "curl -s -X POST http://127.0.0.1:1337/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{\"model\":\"zaya1-8b-jangtq4\",\"messages\":[{\"role\":\"user\",\"content\":\"2+2?\"}],\"max_tokens\":32}' \
  | python3 -m json.tool"

# 6. Bench. Stage the script on Mac Studio (bench scripts use urllib only;
#    loopback works fine because Osaurus listens on 127.0.0.1).
scp scripts/bench/bench_api_server.py macstudio:/tmp/
ssh macstudio "/usr/bin/python3 /tmp/bench_api_server.py \
  --base-url http://127.0.0.1:1337/v1 --model zaya1-8b-jangtq4 \
  --contexts 512,4096,8192,32768 --max-tokens 50 --warmup 1 --runs 2 \
  --output /tmp/zaya-api-server.json"
scp macstudio:/tmp/zaya-api-server.json docs/models/benchmarks/zaya1-8b/api-server-vmlx-swift-lm.json
```

**Verified behaviors after this sequence:**
- `osaurus list` returns "(no models found)" because Osaurus's catalog filter doesn't include arbitrary HF bundles — use `/v1/models` instead, which correctly reports `zaya1-8b-jangtq4`.
- `/health` confirms `"current_model": "zaya1-8b-jangtq4"` and `"loaded": ["zaya1-8b-jangtq4"]`.
- `/api/tags` (Ollama-style) reports `family: "unknown"` and empty `quantization_level` — runtime works fine; only catalog metadata is missing.
- Tool calling will use the `zaya_xml` parser from the JANGTQ4 capabilities sidecar. Not yet exercised end-to-end through OpenCode given the speed regression; defer the agent-loop bench until [PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) lands.

## Open questions

- **Tool-call shape:** JANGTQ4 sidecar declares `tool_parser=zaya_xml`. Does Osaurus translate that into OpenAI `tool_calls` JSON for OpenCode, or does it surface raw XML in `content` (the failure mode that bit JANGTQ4-CRACK on the Python vmlx)? Verify on first agent run before claiming OpenCode compatibility.
- **Thinking trace:** capabilities sidecar sets `supports_thinking=False`. The model's higher-budget reasoning still happens — just not via `<think>…</think>`. Confirm Osaurus doesn't try to parse a non-existent reasoning channel.
- **Markovian RSA harness:** none of the current benchmark scripts wrap multi-trace aggregation. To reproduce *any* of the headline numbers, build a small harness that runs N parallel completions and re-prompts with last-4K-token tails. Not a launch blocker, but the comparison to other models in the lab without it is decode-loop only.
- **Quant choice for first bench:** start with JANGTQ4 (matches the user's pointer and the README's runtime contract). MXFP4 is the speed leader in the fork's evidence pass but has no published quality table on ZAYA's reasoning benchmarks yet — second comparison run, not first.

## See also

- [Zyphra/ZAYA1-8B (model card)](https://huggingface.co/Zyphra/ZAYA1-8B)
- [ZAYA1-8B blog](https://www.zyphra.com/post/zaya1-8b)
- [ZAYA1-8B Technical Report (arXiv:2605.05365)](https://arxiv.org/abs/2605.05365)
- [JANGQ-AI/ZAYA1-8B-JANGTQ4 (Swift-runtime bundle)](https://huggingface.co/JANGQ-AI/ZAYA1-8B-JANGTQ4)
- [kyr0/zaya1-base-8b-8bit-MLX (Python-mlx-lm fork path)](https://huggingface.co/kyr0/zaya1-base-8b-8bit-MLX)
- [lainlives/ZAYA1-8B-GGUF (empty placeholder)](https://huggingface.co/lainlives/ZAYA1-8B-GGUF)
- [osaurus-ai/vmlx-swift-lm (Swift runtime, pin commit `b9da180`)](https://github.com/osaurus-ai/vmlx-swift-lm)
- [osaurus-ai/osaurus (Homebrew cask `osaurus`)](https://github.com/osaurus-ai/osaurus)
- [llama.cpp issue #22776 — ZAYA1 support request (open, no PR)](https://github.com/ggml-org/llama.cpp/issues/22776)
- [mlx-lm PR #1261 — ZAYA support (in review)](https://github.com/ml-explore/mlx-lm/pull/1261)
