# Multi-Token Prediction (MTP) — Qwen3.6 Speculative Decoding via llama.cpp

Last updated: 2026-05-15 (deployed on Mac Studio as the `llama-cpp-mtp` sidecar — see `docs/servers/llama-cpp-mtp/summary.md`).

Multi-Token Prediction (MTP), also called Next-n prediction, is a **speculative-decoding** technique built into the model's architecture itself. Rather than requiring a separate drafter model, MTP trains additional output heads on top of existing hidden states to predict multiple future tokens in a single forward pass. The target model proposes *and* verifies its own draft — no drafter/trainer pairing needed.

The value proposition is **~1.5–2× faster decode tok/s without changing output quality**, with the added benefit that there's no drafter download, no acceptance-ratio dependency on prompt type, and no cross-model compatibility concern. MTP is a *model architecture feature*, not an external server technique — it lives in the weights, not in the runtime.

## Overview

| Aspect | Detail |
|---|---|
| **What it is** | Multi-Token Prediction (MTP) / Next-n: model predicts N tokens per forward pass instead of 1 |
| **Published as** | Qwen3.6-27B native architecture feature; SGLang `--speculative-algo NEXTN`, vLLM `qwen3_next_mtp` |
| **GGUF carrier** | `unsloth/Qwen3.6-27B-MTP-GGUF` (134 likes, 75k downloads, updated 2026-05-13) |
| **llama.cpp support** | Requires MTP PR branch (`am17an/llama.cpp@ mtp-clean`, [PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673)) — stock llama.cpp does NOT support it |
| **TurboQuant fork compat** | Unknown — neither johndpope nor TheTom forks have merged MTP. Requires investigation. |

## How MTP works (briefly)

Standard autoregressive decoding generates one token per forward pass: `x_t → p(x_t+1|x_≤t)`. MTP trains additional output heads at each layer to predict tokens further ahead: `h_l → p(x_t+2|≤t)`, `h_l → p(x_t+3|≤t)`, etc. During generation the model emits a draft of N candidate tokens in one pass, then verifies them autoregressively. Accepted tokens are kept; at the first mismatch it falls back to standard decoding from that point.

The key difference from DFlash or classic speculative decoding: **there is no separate drafter model**. The MTP heads are part of the target model's weights, so acceptance rates tend to be higher (the same parameterization proposes and verifies), and there's no cross-model compatibility concern.

## How it stacks in this repo

| Layer | What it is | Where it lives / status |
|---|---|---|
| **Model** | `unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL` — Qwen3.6-27B with MTP heads, Unsloth Dynamic 2.0 6-bit GGUF | `~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf` (26 GB) — deployed 2026-05-15 |
| **Runtime** | `am17an/llama.cpp@mtp-clean` branch (PR #22673), built with `-DGGML_METAL=ON` | `~/llama-cpp-mtp/build/bin/llama-server` (17 MB binary, b9172 build tag) |
| **Server** | `llama-cpp-mtp` sidecar, OpenAI API on port 8100, OpenCode-only client template at `configs/clients/llama-cpp-mtp/opencode.json` | Live, coexists with all other Mac Studio servers |
| **Server flags** | `--spec-type draft-mtp --spec-draft-n-max 2 -np 1 --jinja --reasoning on` (note: the flag is `draft-mtp`, not `mtp`; default `--spec-draft-n-max` is 16 — must override to 2 per HF card) | See `docs/servers/llama-cpp-mtp/summary.md` |
| **Patches** | None — building the mtp-clean branch is the only requirement. Patch-free, unlike DFlash (3 patches) or JANG (per-server `.pth` patches). | N/A |

## Comparison: MTP vs other speculative decoding in this lab

| Technique | Drafter model? | Acceptance dependency | Speedup claim | Patches/forks needed |
|---|---|---|---|---|
| **MTP (Qwen3.6)** | No — self-drafting | Low (self-consistent) | ~1.5–2× (Unsloth claim) | Custom llama.cpp branch |
| **DFlash** | Yes (`z-lab/*`) | High (>85% needed for win) | 1.33× M5 Max, regresses on M3 Ultra at ≤4k horizon | 2 patches + main-branch git install |
| **TurboQuant KV** | N/A (KV compression, not speculative) | N/A | 68 tok/s decode (TheTom turbo3 @ 512) | TheTom fork build |

## Unsloth Qwen3.6 MTP GGUF quantization options

| Bits | Variant | Size |
|---|---|---|
| 2-bit | UD-IQ2_XXS / UD-IQ2_M / UD-Q2_K_XL | 9.57–12 GB |
| 3-bit | Q3_K_S/M, UD-Q3_K_XL | 12.6–14.8 GB |
| 4-bit | Q4_0/K_S/M, IQ4_XS/NL, **UD-Q4_K_XL** (default) | 15.7–17.9 GB |
| 5-bit | Q5_K_S/M, UD-Q5_K_XL | 19.3–20.4 GB |
| 6-bit | Q6_K, UD-Q6_K_XL | 22.9–26 GB |
| 8-bit | Q8_0, UD-Q8_K_XL | 29–35.8 GB |
| 16-bit | **BF16** | 54.7 GB |

The recommended variant from Unsloth is `UD-Q4_K_XL` (17.9 GB). The UD (Unsloth Dynamic) quantizations use their Dynamic 2.0 algorithm, which claims SOTA accuracy for the bits used. At 17.9 GB, `UD-Q4_K_XL` fits comfortably within the Mac Studio's 96 GB unified memory even alongside sidecar processes.

## Launch shape (as deployed on this Mac Studio)

```bash
# Build from MTP branch (one-time, on Mac Studio)
git clone -b mtp-clean https://github.com/am17an/llama.cpp.git ~/llama-cpp-mtp
cd ~/llama-cpp-mtp
/opt/homebrew/bin/cmake -B build \
  -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON \
  -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=ON
/opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server

# Serve with MTP speculative decoding (sidecar on port 8100)
GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf
nohup ~/llama-cpp-mtp/build/bin/llama-server \
    -m "$GGUF" \
    -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type draft-mtp --spec-draft-n-max 2 \
    --host 0.0.0.0 --port 8100 \
    --alias qwen3.6-27b-mtp-ud-q6kxl \
    --jinja --reasoning on \
    > /tmp/llama-cpp-mtp.log 2>&1 &
```

Notes:
- **`--spec-type draft-mtp`, not `mtp`.** The unsloth README writes `--spec-type mtp` but on the mtp-clean branch the enum entry is `draft-mtp` (sibling of `draft-simple`, `draft-eagle3`, the ngram variants). The bare `mtp` errors out with `unknown speculative type`.
- **`-DGGML_METAL=ON` for Apple Silicon** — the unsloth card's example uses `-DGGML_CUDA=ON`, which is wrong for Mac Studio.
- **No `--tool-call-parser` / `--reasoning-parser` flags exist** on this `llama-server` build. Tool calls are dispatched from the GGUF's embedded chat template via `--jinja`; the reasoning channel is controlled with `--reasoning [on|off|auto]`. Both `tool_calls[]` parsing and `reasoning_content` separation work out of the box.
- **The build's `cmake` may not be on PATH for non-interactive SSH.** Use `/opt/homebrew/bin/cmake` explicitly.

## Known limitations

- **Stock llama.cpp incompatible:** Must build from the MTP PR branch. No Homebrew one-liner path.
- **-np > 1 unsupported with MTP:** Cannot run multi-pipeline parallel with speculative decoding enabled — single pipeline only (`-np 1`).
- **--mmproj unsupported with MTP:** The vision encoder dispatch is broken when MTP is active; multimodal input (images/video) will not work. This matters because Qwen3.6-27B is a vision-language model.
- **TurboQuant integration unknown:** Neither johndpope nor TheTom forks have merged the MTP PR. If TurboQuant KV compression + MTP are desired, someone needs to cherry-pick or wait for upstream merge.
- **No MLX path today:** `mlx_lm` and `vllm-mlx` do not appear to support Qwen3.6 MTP in GGUF form. The native safetensors path via SGLang/vLLM does, but those require CUDA (SGLang) or multi-GPU tensor parallelism (8× GPU recommended by Qwen).
- **No 35B-A3B MoE MTP variant exists:** Unsloth has not released `Qwen3.6-35B-A3B-MTP-GGUF`. The 27B dense is the largest available.

## Performance on this Mac Studio (2026-05-15)

`unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL` on `am17an/llama.cpp@mtp-clean` (build tag `b9172-08b147428`), M3 Ultra 96 GB, Metal, pre-bench hygiene done (lm-studio stopped, MTP sidecar alone on the GPU).

### Decode + prefill

Custom real-content prompt rig (see [Bench rig caveat](#bench-rig-caveat-filler-eos-at-temp0) below). Single warmup + 2 measured runs each context:

| Input tokens | Warm TTFT | Decode tok/s | Prefill tok/s | MTP draft acceptance |
|:--:|:--:|:--:|:--:|:--:|
| 414 | 0.15 s | **22.9** | 2,746 | 31/35 = **88.6 %** |
| 3 648 | 0.16 s | 22.3 | 23,453 | 31/36 = 86.1 % |
| 7 274 | 0.16 s | 22.0 | 44,954 | 31/36 = 86.1 % |
| 29 128 | 0.21 s | 20.0 | 139,320 | 31/36 = 86.1 % |

MTP draft acceptance is consistent at **84–89 %** across context sizes — exactly the upper-end of Unsloth's claim. Decode degrades gracefully from 22.9 → 20.0 tok/s across 0.5 K → 29 K input tokens.

### Smoke (`bench_api_tool_call.py`)

- Single-call: **5/5** scenarios pass, all `finish_reason=tool_calls`.
- Multi-turn loop: 3 turns, **21.92 s** total wall (read_file → write_file → summary). webfetch / read / write / list_directory all parsed.

### Agent loop (`bench_agent_tool_call.py`, OpenCode 1.14.50, 1 warmup + 3 measured)

| Scenario | Wall median | LLM median | Turns | Tool fired | p5–p95 wall |
|---|---|---|---|---|---|
| Browse `www.example.com` | **35.98 s** | 35.2 s | 2 | `webfetch` | 24.48 – 48.34 s |
| Search Hackernews | **35.24 s** | 34.45 s | 2 | `webfetch` | 29.42 – 70.45 s |

Slower than the current production main (`q3.6-27b-glm51-da-q4km` Q4_K_M on lm-studio: browse 11.62 s / search 19.47 s). The dense 27 B + 6-bit weight bundle is fundamentally heavier than the production Q4_K_M, and MTP's ~1.5–2× decode multiplier isn't enough to close the gap. The MTP heads themselves work as advertised; the model+quant combo is just not competitive with the lighter production option for agent loops.

Bench data: [`docs/models/benchmarks/logs/qwen36-27b-mtp/`](../benchmarks/logs/qwen36-27b-mtp/).

### Bench rig caveat: filler EOS at temp=0

The standard `scripts/bench/bench_api_server.py` driver uses `"Hello world. " * N` filler padding. At `temperature=0.0`, this MTP-quantized 27 B emits `<|im_end|>` deterministically as the first decoded token regardless of `--reasoning on/off`, returning `completion_tokens=1` and no usable streaming timings. Other models in the lab (lm-studio Q4_K_M, llama-cpp-turboquant Qwen3.6-35B-A3B Q6_K) tolerate this filler — the issue is specific to the 27 B dense + MTP heads + Unsloth Dynamic 6-bit combo. The perf table above was captured with a custom real-content prompt rig in `docs/models/benchmarks/logs/qwen36-27b-mtp/perf-llama-cpp-mtp.json` (variant: `1.0-mtp-realprompt`).

## Fit for this lab

MTP on Qwen3.6-27B is **deployed and operational** as a provisional sidecar, but not a production-main candidate at this quant:

1. **Pro:** Patch-free, no drafter download, 84–89 % draft acceptance materialised exactly as advertised on M3 Ultra Metal.
2. **Pro:** Single-file 26 GB bundle, single build. No drafter file to track, no `--spec-draft-model` flag.
3. **Con:** Requires custom llama.cpp build — adds maintenance burden when upstream llama.cpp updates. The TurboQuant fork ecosystem may fragment further if someone needs MTP + TurboQuant combined.
4. **Con:** Vision input broken with MTP active — removes the VL advantage of Qwen3.6-27B.
5. **Con:** Slower agent loops than the lm-studio Q4_K_M production main. The MTP speedup is real but the underlying 6-bit dense 27 B bundle is heavier than the production option.

The natural next experiment is the **stock-baseline comparison**: benchmark `unsloth/Qwen3.6-27B-GGUF:UD-Q6_K_XL` (no MTP) on stock llama.cpp at the same context targets to validate the MTP speedup in isolation. Queued for a follow-up plan.

## See also

- [`model-summary-qwen-3-6.md`](../per-model/model-summary-qwen-3-6.md) — Qwen3.6 family-wide pitfalls and deployment notes
- [`model-technique-dflash.md`](model-technique-dflash.md) — DFlash speculative decoding comparison (drafter-based, MLX-native)
- Unsloth MTP guide: https://unsloth.ai/docs/models/qwen3.6#mtp-guide
- llama.cpp MTP PR: https://github.com/ggml-org/llama.cpp/pull/22673
