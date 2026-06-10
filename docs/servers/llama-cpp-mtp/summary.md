# llama-cpp-mtp Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Download the MTP GGUF](#download-the-mtp-gguf)
- [Starting the server](#starting-the-server)
- [Gemma 4 31B external MTP drafter](#gemma-4-31b-external-mtp-drafter)
- [Tool use and reasoning](#tool-use-and-reasoning)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`llama-cpp-mtp` is a sidecar `llama-server` for **Multi-Token Prediction (MTP) speculative decoding**: self-drafting heads for Qwen3.6 and an external assistant for Gemma 4. Two binaries are available:

- **Mainline `ggml-org/llama.cpp`** (preferred) — Qwen MTP merged upstream in May; Gemma 4 external-drafter MTP merged in [PR #23398](https://github.com/ggml-org/llama.cpp/pull/23398) on 2026-06-07. The pre-upgrade research baseline recorded on 2026-06-09 was commit `510b5c2` (2026-05-20).
- **`am17an/llama.cpp@mtp-clean`** (legacy fork) — [PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673). Built at `~/llama-cpp-mtp/` (build tag `b9172`).

Both support `--spec-type draft-mtp` for Qwen. Only a post-2026-06-07 mainline build supports the Gemma 4 `gemma4_assistant` external drafter. The mainline binary is preferred for new models.

> **Technique reference:** for what MTP / Next-n prediction actually does at the algorithm level — extra prediction heads on the target model's hidden states, single-pass N-token drafts verified autoregressively, why acceptance rates are higher than drafter-based methods — see [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](../../models/techniques/model-technique-qwen-3-6-mtp.md). This runbook covers operational steps only.

**Status: provisional sidecar — deployed 2026-05-15.** Standalone validation only (no production-flip). Patch-free apart from building the right branch — no Python venv, no upstream-package patches, no PyPI pin.

Bound to port **8100**, OpenAI API only. Coexists with `vllm-mlx` / `mlx-openai-server` / `oMLX` / `vmlx` on port 8000 (one at a time), with `lm-studio` on 1234, `dflash-mlx` on 8098, `llama-cpp-turboquant` on 8099, `vmlx-swift-lm` / Osaurus on 1337, and `comfyui` on 8188.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌─────────────────────────────────────────────┐
│ Claude Code    │            │ llama-server (port 8100, sidecar)           │
│ OpenCode       │─── LAN ───>│   ~/llama-cpp-mainline/build/bin/llama-server│
│ OpenClaw       │            │   models: unsloth UD-Q6_K_XL (dense 27B)   │
│ Pi             │            │     llmfan46 heretic-v2 Q6_K (dense 27B)   │
│                │            │     huihui-ai Q6_K (MoE 35B/3B, ~27 GB)   │
│                │            │     Gemma 4 31B + external assistant       │
└────────────────┘            │   --spec-type draft-mtp                     │
                              │   --spec-draft-n-max 2                      │
                              │   -ngl 99 -fa on -np 1                      │
                              │   --jinja --reasoning on                    │
                              │   OpenAI API only (no Anthropic)            │
                              └─────────────────────────────────────────────┘
```

Sidecar pattern. Qwen3.6 MTP heads live inside the target GGUF, so Qwen needs no separate drafter file. Gemma 4 uses a different design: a separate `gemma4_assistant` GGUF consumes target activations and shares selected target KV-cache state. Gemma therefore requires `--spec-draft-model` / `-md`, and acceptance depends on the target/drafter pairing.

## Installation

### Mainline `ggml-org/llama.cpp` (preferred)

MTP support merged upstream. The 2026-06-09 pre-upgrade baseline was `510b5c2` (2026-05-20), before Gemma 4 support.

```bash
ssh macstudio "/opt/homebrew/bin/brew install cmake"   # if missing

ssh macstudio "cd ~ && git clone --depth 1 https://github.com/ggml-org/llama.cpp.git llama-cpp-mainline && \
  cd llama-cpp-mainline && \
  /opt/homebrew/bin/cmake -B build \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON \
    -DLLAMA_BUILD_SERVER=ON && \
  /opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server"
```

Build time on M3 Ultra: ~30 sec. Outputs `~/llama-cpp-mainline/build/bin/llama-server` (~17 MB). Re-pull + rebuild: `cd ~/llama-cpp-mainline && git pull && cmake --build build --target llama-server`.

For Gemma 4, pin or verify a revision containing both:

- [`#23398`](https://github.com/ggml-org/llama.cpp/pull/23398), merge `04eb4c446` — Gemma 4 MTP support.
- [`#24277`](https://github.com/ggml-org/llama.cpp/pull/24277), merge `379ac66` — avoids the expensive KV-cell copy introduced by the initial merge.

Preserve the old binary before rebuilding so Qwen MTP has an immediate rollback:

```bash
ssh macstudio "cd ~/llama-cpp-mainline && \
  cp build/bin/llama-server build/bin/llama-server-510b5c2 && \
  git pull --ff-only && \
  git merge-base --is-ancestor 379ac66 HEAD && \
  /opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server && \
  ./build/bin/llama-server --version"
```

### Legacy `am17an/llama.cpp@mtp-clean` (fallback)

The original MTP fork. Built at `~/llama-cpp-mtp/` (build tag `b9172`). Preserved as fallback.

```bash
ssh macstudio "cd ~ && git clone -b mtp-clean https://github.com/am17an/llama.cpp.git llama-cpp-mtp && \
  cd llama-cpp-mtp && \
  /opt/homebrew/bin/cmake -B build \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON \
    -DLLAMA_BUILD_SERVER=ON && \
  /opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server"
```

Use the full `/opt/homebrew/bin/cmake` path — non-interactive SSH sessions do not inherit Homebrew's PATH. There is no PyPI / Homebrew pin.

## Download the MTP GGUF

`unsloth/Qwen3.6-27B-MTP-GGUF` ships **single-file GGUFs** (no sharding) for every quant tier. The Unsloth-Dynamic 2.0 `UD-Q6_K_XL` is the deploy default — 26 GB, selective layer upcasting, ~0.4 % MMLU gain over `UD-Q4_K_XL` per the Unsloth card. Alternatives: `Q6_K` (22.9 GB, static), `UD-Q4_K_XL` (17.9 GB, recommended for tight disk), `BF16` (54.7 GB, no quant loss).

```bash
ssh macstudio "~/vllm-mlx-env/bin/hf download unsloth/Qwen3.6-27B-MTP-GGUF \
  --include 'Qwen3.6-27B-UD-Q6_K_XL.gguf' \
  --local-dir ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main"
```

The `hf` CLI binary lives inside the python envs (`~/vllm-mlx-env/`, `~/dflash-mlx-env/`, `~/qwen-asr-env/`, `~/comfyui/.venv/`, `~/mlx-vlm-env/`, `~/vmlx-env/`, `~/mlx-openai-server-env/`) — any of them works. **Skip `mmproj-*.gguf`** — the vision encoder dispatch is broken on the MTP branch.

26 GB download takes ~4 minutes on a fast HF link.

## Starting the server

```bash
ssh macstudio "GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf; \
  nohup ~/llama-cpp-mtp/build/bin/llama-server \
    -m \"\$GGUF\" \
    -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type draft-mtp --spec-draft-n-max 2 \
    --host 0.0.0.0 --port 8100 \
    --alias qwen3.6-27b-mtp-ud-q6kxl \
    --jinja --reasoning on \
    > /tmp/llama-cpp-mtp.log 2>&1 &"
```

Key flags:
- **`--spec-type draft-mtp`** — engages the MTP self-drafting path (the canonical mtp-clean PR adds `draft-mtp` to the `--spec-type` enum alongside `draft-simple`, `draft-eagle3`, ngram variants).
- **`--spec-draft-n-max 2`** — Unsloth's HF card caps useful draft depth at 2 for Qwen3.6-27B-MTP; higher values drop acceptance to ~50 %. Default is 16, **must override**.
- **`-np 1`** — multi-pipeline (`-np > 1`) is unsupported with MTP active per the PR description.
- **`-ngl 99`** — offload all layers + embeddings to Metal.
- **`-fa on`** — flash attention (explicit `on/off/auto` required; bare `-fa` errors).
- **`-c 32768`** — conservative context limit. The model's `n_ctx_train` is 262 144, so this can be raised on 96 GB Mac Studio if needed.
- **`--alias qwen3.6-27b-mtp-ud-q6kxl`** — stable identifier for `/v1/models`.
- **`--jinja`** — apply the GGUF's embedded chat template. Required for Qwen3.6 tool-call XML → `tool_calls[]` conversion and the `<think>` reasoning channel.
- **`--reasoning on`** — exposes the `<think>` block as `reasoning_content` separate from `content`. Required for agent / tool use; **see Known limitations** for a perf-bench-specific caveat.

Stop with: `ssh macstudio "pkill -f 'llama-cpp-mainline/build/bin/llama-server'; pkill -f 'llama-cpp-mtp/build/bin/llama-server'"`.

## Gemma 4 31B external MTP drafter

This is the main reason to upgrade the source-built mainline binary. PR #23398 does not make ordinary Gemma decoding faster automatically; the gain appears only when a compatible external assistant is loaded.

Download the small Q8 assistant first. It is 491 MB and is sufficient to test any Gemma 4 31B target quant:

```bash
ssh macstudio "~/vllm-mlx-env/bin/hf download unsloth/gemma-4-31B-it-GGUF \
  MTP/gemma-4-31B-it-MTP-Q8_0.gguf \
  --local-dir ~/.cache/huggingface/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/main"
```

The standard `unsloth/gemma-4-31B-it-GGUF Q4_K_M` (17.0 GiB) is the tested control target. Start with MTP disabled:

```bash
ssh macstudio "TARGET=~/.cache/huggingface/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/main/gemma-4-31B-it-Q4_K_M.gguf; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server \
    -m \"\$TARGET\" -ngl 99 -fa on -np 1 -c 65536 \
    --host 0.0.0.0 --port 8100 \
    --alias gemma4-31b-q4km-baseline \
    --jinja --reasoning on > /tmp/llama-cpp-gemma4-baseline.log 2>&1 &"
```

Then restart with the assistant using the **measured winning depth** (`n=1`):

```bash
ssh macstudio "TARGET=~/.cache/huggingface/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/main/gemma-4-31B-it-Q4_K_M.gguf; \
  DRAFT=~/.cache/huggingface/hub/models--unsloth--gemma-4-31B-it-GGUF/snapshots/main/MTP/gemma-4-31B-it-MTP-Q8_0.gguf; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server \
    -m \"\$TARGET\" -md \"\$DRAFT\" \
    -ngl 99 --spec-draft-ngl 99 -fa on -np 1 -c 65536 \
    --spec-type draft-mtp --spec-draft-n-max 1 \
    --host 0.0.0.0 --port 8100 \
    --alias gemma4-31b-q4km-mtp-n1 \
    --jinja --reasoning on > /tmp/llama-cpp-gemma4-mtp.log 2>&1 &"
```

`--spec-draft-n-max 1` is the measured optimum on M3 Ultra — deeper drafts (`n=2`, `n=4`) regress vs no-MTP because Q4_K_M target logits diverge enough from the Q8_0 drafter that extra candidates are rejected. Do not use the 26B-A4B MoE as the first test: upstream and Google both report weak batch-1 economics, while this lab's agent benchmark is single-request.

For optional extension to TrevorJS Gemma 4 31B-it Uncensored Q4_K_M (already downloaded at `~/.lmstudio/models/TrevorJS/gemma-4-31B-it-uncensored-GGUF/`), substitute that target path — but measure acceptance separately since abliteration changes target logits and acceptance must be verified rather than assumed.

### 2026-06-09 measured result: Gemma worked, upgrade did not survive the Qwen guard

Ran the standard control on `unsloth/gemma-4-31B-it-GGUF` `Q4_K_M` plus the `MTP/gemma-4-31B-it-MTP-Q8_0.gguf` assistant on **mainline commit `961e9a3`** (which contains both `#23398` and `#24277`). The old default executable from `510b5c2` was copied aside before the rebuild and restored afterward.

Measured decode tok/s:

| Context | Baseline | MTP `n=1` | MTP `n=2` | MTP `n=4` |
|:--|--:|--:|--:|--:|
| 512 | 29.89 | **33.51** | 31.85 | 23.76 |
| 4096 | 28.61 | **32.07** | 28.81 | 20.24 |
| 8192 | 27.84 | **32.02** | 28.98 | 21.11 |
| 32768 | 23.75 | **25.44** | 23.39 | 17.27 |

Winner on this machine: **`--spec-draft-n-max 1`**. The direct completion probe on that config reported `draft_n=41`, `draft_n_accepted=38` (92.7% acceptance on the sampled request). Tool smoke stayed clean at **5/5** for both baseline and MTP. OpenCode browse improved from **15.39 s** to **13.75 s** median, but search did not improve on median (**38.20 s** baseline vs **39.45 s** with MTP).

The decisive blocker was the post-upgrade Qwen regression check. The final validated comparison used the preserved **`510b5c2` binary** against a fresh out-of-tree **`961e9a3` candidate build** on the same machine:

- Tool correctness stayed **5/5** on both, and the candidate's tool multi-turn loop improved slightly (**20.91 s → 19.26 s**).
- Real-prompt decode also improved modestly (**26.10 → 27.17 tok/s** at ~512 and **23.98 → 25.58 tok/s** at ~8K).
- But OpenCode browse regressed hard: baseline **28.38 s**, candidate reruns **56.62 s** and **59.93 s**.

The browse slowdown came with a much larger first-turn prompt footprint on the candidate runs: baseline browse used **118 input tokens** total, while both candidate runs expanded to about **8.9K input tokens** before `webfetch` completed. Because the existing Qwen MTP sidecar regressed materially on that real agent path, the upgraded binary was **not** kept as the default `~/llama-cpp-mainline/build/bin/llama-server`. The source tree remains at `961e9a3` for follow-up work, but the default executable stays on the old `510b5c2` build.

Raw logs and summary: [`../../models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/`](../../models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/)

## Tool use and reasoning

Both work out of the box on the mtp-clean branch — same plumbing as `llama-cpp-turboquant`:
- **Tool calls** — Qwen3.6's native `<tool_call>` XML parsed by `llama-server` into OpenAI-style `tool_calls[]`. Verified **5/5** on the single-call API smoke harness + **3/3** on the multi-turn loop. No `--tool-call-parser` flag exists on this build (the chat template embedded in the GGUF and applied via `--jinja` handles dispatch).
- **Reasoning channel** — `--reasoning on` puts `<think>…</think>` content into `choices[].message.reasoning_content` (separate from `content`). On the very first decoded chat (with the MTP draft context warming up), the model includes a visible reasoning trace before the tool call.

The first turn of any tool-using flow shows MTP engaged via the response's `timings` block: `draft_n` and `draft_n_accepted` (e.g. `100/84` = 84 % acceptance).

## Health check

```bash
curl -s http://<MAC_STUDIO_IP>:8100/v1/models | python3 -m json.tool
```

Expect a `data[0].id` of `qwen3.6-27b-mtp-ud-q6kxl` and `meta.n_ctx = 32768`. The launch log should contain three confirmations of MTP activation:

```
srv    load_model: creating MTP draft context against the target model …
common_speculative_init: adding speculative implementation 'draft-mtp'
srv    load_model: speculative decoding context initialized
```

Smoke a real generation:

```bash
curl -s http://<MAC_STUDIO_IP>:8100/v1/chat/completions \
  -H "Content-Type: application/json" -d '{
    "model": "qwen3.6-27b-mtp-ud-q6kxl",
    "messages": [{"role":"user","content":"Count from one to ten."}],
    "max_tokens": 50,
    "temperature": 0.0
  }' | python3 -m json.tool
```

`choices[0].message.content` should hold the digit sequence; `usage.completion_tokens` should be > 1.

## Performance (Mac Studio M3 Ultra, 96 GB)

Tested on `unsloth/Qwen3.6-27B-MTP-GGUF` `UD-Q6_K_XL` (2026-05-15). Pre-bench hygiene: LM Studio stopped, no other LLM processes alive.

### Decode + prefill (real-content prompt, see [Known limitations](#known-limitations) §1)

| Context (input tokens) | Warm TTFT | Decode tok/s | Prefill tok/s | MTP draft acceptance |
|:--:|:--:|:--:|:--:|:--:|
| 414 | 0.15 s | **22.9** | 2,746 | 31/35 = **88.6 %** |
| 3 648 | 0.16 s | 22.3 | 23,453 | 31/36 = 86.1 % |
| 7 274 | 0.16 s | 22.0 | 44,954 | 31/36 = 86.1 % |
| 29 128 | 0.21 s | 20.0 | 139,320 | 31/36 = 86.1 % |

Smoke (`bench_api_tool_call.py`): **5/5 single-call**, multi-turn loop **21.92 s** across 3 turns. All probes finished with `finish_reason=tool_calls`.

OpenCode end-to-end (`bench_agent_tool_call.py`, opencode 1.14.50, 1 warmup + 3 measured): **browse 35.98 s / search 35.24 s** median wall, 2 turns + `webfetch` fired on every measured run. Slower than the Q4_K_M-class builds on lm-studio (e.g. GLM-5.1-DA browse 11.62 s / search 19.47 s) because UD-Q6_K_XL is a heavier weight bundle and the dense 27 B layer count means MTP's ~1.5–2× speedup isn't enough to close the gap. The MTP heads themselves work as advertised — 84–89 % acceptance is at the upper end of Unsloth's claim.

Raw bench JSONs: [`docs/models/benchmarks/logs/qwen36-27b-mtp/`](../../models/benchmarks/logs/qwen36-27b-mtp/).

## Known limitations

- **Standard `bench_api_server.py` methodology hits filler-EOS for this quant.** At `temperature=0` with the script's `"Hello world. " * N` filler padding, the model deterministically picks `<|im_end|>` as the first decoded token and emits 1-token replies regardless of `--reasoning on/off`. The custom real-content perf rig in [`docs/models/benchmarks/logs/qwen36-27b-mtp/perf-llama-cpp-mtp.json`](../../models/benchmarks/logs/qwen36-27b-mtp/perf-llama-cpp-mtp.json) (varied English passage + summarization instruction) avoids the issue at the same context targets. Other models in this repo (`llama-cpp-turboquant` Qwen3.6-35B-A3B Q6_K, lm-studio Q4_K_M) tolerate the filler at temp=0; this is specific to the 27B dense + MTP-heads + Unsloth Dynamic 2.0 6-bit combo.
- **No multi-pipeline.** `-np > 1` is unsupported with MTP active — single pipeline only.
- **No multimodal.** `--mmproj` is broken with MTP active; the GGUF's `mmproj-*.gguf` companions cannot be loaded. This removes Qwen3.6-27B's vision-language capability when running on this sidecar.
- **No `draft-mtp` + KV-cache compression combined build.** Neither `johndpope/llama-cpp-turboquant` (`feature/planarquant-kv-cache`) nor `TheTom/llama-cpp-turboquant` (`feature/turboquant-kv-cache`) has merged PR #22673. Stacking TurboQuant + MTP requires a manual cherry-pick or waiting for upstream.
- **No MLX path.** `mlx_lm` and `vllm-mlx` do not support Qwen3.6 MTP in GGUF form. The native safetensors path via SGLang `--speculative-algo NEXTN` or vLLM `qwen3_next_mtp` requires CUDA — neither runs on Apple Silicon today.
- **~~No 35B-A3B MoE MTP variant~~ RESOLVED:** `huihui-ai/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF` provides MoE 35B/3B with MTP heads (Q6_K = ~27 GB). Deployed 2026-05-20 on mainline binary: 83% acceptance, 78.5 tok/s, browse 4.74 s / search 12.11 s.
- **Fork is a community port, not upstream.** The mtp-clean branch is maintained by `am17an` against PR #22673 (commit pinned to `08b147428` at deploy time, `b9172` build tag). Re-pull + rebuild after upstream `llama.cpp` lands new features.
- **Gemma 4 requires a post-`#24277` build.** The initial #23398 merge caused severe regressions in configurations that copied large KV-cell maps. Do not benchmark the merge commit without the June 7 follow-up.
- **Gemma 4 fine-tune acceptance is not guaranteed.** The published 31B assistant is trained against the standard target. It should load with TrevorJS/DavidAU variants that retain the architecture and vocabulary, but abliteration/fine-tuning can reduce token agreement enough to erase the speedup.
- **No Anthropic API.** OpenAI-compatible only. For Claude Code, route via OpenAI provider (`CLAUDE_CODE_USE_OPENAI=1` env path).
- **GGUF only.** No MLX safetensors, no JANG, no JANGTQ, no `bailing_hybrid`.

## See also

- Technique reference: [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](../../models/techniques/model-technique-qwen-3-6-mtp.md)
- Family doc: [`docs/models/per-model/model-summary-qwen-3-6.md`](../../models/per-model/model-summary-qwen-3-6.md)
- Upstream PR: [`ggml-org/llama.cpp#22673`](https://github.com/ggml-org/llama.cpp/pull/22673)
- Gemma 4 MTP merge: [`ggml-org/llama.cpp#23398`](https://github.com/ggml-org/llama.cpp/pull/23398)
- Gemma 4 post-merge KV fix: [`ggml-org/llama.cpp#24277`](https://github.com/ggml-org/llama.cpp/pull/24277)
- Gemma 4 MTP GGUFs: <https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/tree/main/MTP>
- Upstream fork: [`am17an/llama.cpp@mtp-clean`](https://github.com/am17an/llama.cpp/tree/mtp-clean)
- Unsloth MTP guide: <https://unsloth.ai/docs/models/qwen3.6#mtp-guide>
- HF model card: <https://huggingface.co/unsloth/Qwen3.6-27B-MTP-GGUF>
- Bench data: [`docs/models/benchmarks/logs/qwen36-27b-mtp/`](../../models/benchmarks/logs/qwen36-27b-mtp/)
