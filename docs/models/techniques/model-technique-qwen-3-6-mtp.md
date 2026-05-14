# Multi-Token Prediction (MTP) — Qwen3.6 Speculative Decoding via llama.cpp

Last updated: 2026-05-14.

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
| **Model** | `unsloth/Qwen3.6-27B-MTP-GGUF` — Qwen3.6-27B with MTP heads, quantized to GGUF via Unsloth Dynamic 2.0 | HF, not yet on Mac Studio disk |
| **Runtime** | Custom llama.cpp build from `mtp-clean` branch (`am17an/llama.cpp`) | Not built on Mac Studio yet |
| **Server compat** | Requires `--spec-type mtp --spec-draft-n-max 2` at launch; `-np > 1` and `--mmproj` not yet supported with MTP | N/A — not deployed |
| **Patches** | None needed beyond building the right branch. Patch-free, unlike DFlash (3 patches) or JANG (per-server .pth patches). | N/A |

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

## Launch shape (when deployed on llama.cpp)

```bash
# Build from MTP branch
git clone -b mtp-clean https://github.com/am17an/llama.cpp.git
cmake llama.cpp -B llama.cpp/build -DBUILD_SHARED_LIBS=OFF -DGGML_METAL=ON
cmake --build llama.cpp/build --config Release -j --target llama-server

# Serve with MTP speculative decoding
./llama.cpp/build/bin/llama-server \
    -hf unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL \
    -ngl 99 -c 8192 -fa on -np 1 \
    --spec-type mtp --spec-draft-n-max 2
```

Note: `-DGGML_METAL=ON` for Apple Silicon (not `-DGGML_CUDA`). The unsloth card's example uses CUDA but the Mac Studio requires Metal. Also, `--reasoning-parser qwen3` and `--tool-call-parser qwen3_coder` should be added for agent use — same parser flags as any Qwen3.6 model in this lab.

## Known limitations

- **Stock llama.cpp incompatible:** Must build from the MTP PR branch. No Homebrew one-liner path.
- **-np > 1 unsupported with MTP:** Cannot run multi-pipeline parallel with speculative decoding enabled — single pipeline only (`-np 1`).
- **--mmproj unsupported with MTP:** The vision encoder dispatch is broken when MTP is active; multimodal input (images/video) will not work. This matters because Qwen3.6-27B is a vision-language model.
- **TurboQuant integration unknown:** Neither johndpope nor TheTom forks have merged the MTP PR. If TurboQuant KV compression + MTP are desired, someone needs to cherry-pick or wait for upstream merge.
- **No MLX path today:** `mlx_lm` and `vllm-mlx` do not appear to support Qwen3.6 MTP in GGUF form. The native safetensors path via SGLang/vLLM does, but those require CUDA (SGLang) or multi-GPU tensor parallelism (8× GPU recommended by Qwen).
- **No 35B-A3B MoE MTP variant exists:** Unsloth has not released `Qwen3.6-35B-A3B-MTP-GGUF`. The 27B dense is the largest available.

## Fit for this lab

MTP on Qwen3.6-27B is a **candidate worth investigating** but with lower priority than current sidecars:

1. **Pro:** Patch-free, no drafter download, self-consistent acceptance rates. If the ~1.5–2× speedup materializes on M3 Ultra Metal, it would be a straightforward win over stock Qwen3.6-27B.
2. **Con:** Requires custom llama.cpp build — adds maintenance burden when llama.cpp updates. The TurboQuant fork ecosystem (already two forks) may fragment further if someone needs to merge MTP + TurboQuant.
3. **Con:** Vision input is broken with MTP active on this branch, which removes the VL advantage of Qwen3.6-27B over text-only models.

If the speedup justifies the build maintenance, a natural experiment would be: benchmark `unsloth/Qwen3.6-27B-MTP-GGUF` (MTP llama.cpp) vs `unsloth/Qwen3.6-27B-GGUF` (stock llama.cpp) on the same M3 Ultra Metal hardware, using the lab's existing bench drivers adapted for a local llama.cpp server.

## See also

- [`model-summary-qwen-3-6.md`](../per-model/model-summary-qwen-3-6.md) — Qwen3.6 family-wide pitfalls and deployment notes
- [`model-technique-dflash.md`](model-technique-dflash.md) — DFlash speculative decoding comparison (drafter-based, MLX-native)
- Unsloth MTP guide: https://unsloth.ai/docs/models/qwen3.6#mtp-guide
- llama.cpp MTP PR: https://github.com/ggml-org/llama.cpp/pull/22673
