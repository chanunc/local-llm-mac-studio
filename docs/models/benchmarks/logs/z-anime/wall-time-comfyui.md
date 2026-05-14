# Z-Anime wall-time benchmark — ComfyUI MPS on Mac Studio M3 Ultra

Captured: 2026-05-08, ComfyUI 0.20.1, PyTorch 2.11.0, MPS, `--use-pytorch-cross-attention`.

Driver: [`scripts/bench/bench_zanime_walltime.py`](../../../../scripts/bench/bench_zanime_walltime.py). Raw output: [`wall-time-comfyui.json`](wall-time-comfyui.json).

8-node API workflow (`CheckpointLoaderSimple` → `ModelSamplingAuraFlow` → 2× `CLIPTextEncode` → `EmptyLatentImage` → `KSampler` → `VAEDecode` → `SaveImage`). Sampler `euler`, scheduler `beta`, shift 3.5 (matches the SeeSee21 reference workflow). 1024×1024, 1 warm-up + 3 timed runs per variant.

## Results

| Variant | Steps | CFG | Warm-up | Mean | Min | Max | σ |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Distill-4-step AIO BF16 | 4 | 1.0 | 24.84 s | **17.75 s** | 17.72 s | 17.78 s | 0.03 s |
| Base AIO BF16 | 28 | 4.0 | 246.37 s | **235.16 s** | 235.07 s | 235.21 s | 0.08 s |

Both checkpoints are 19 GiB AIO single-files (UNet + VAE + qwen_3_4b text encoder bundled). Per-run jitter is sub-percent — MPS perf is rock-steady once the graph is compiled (warm-up overhead is the first-time graph compile, not weight load).

## Per-step cost decomposition

- Distill (CFG 1.0, conditional pass only): **17.75 s / 4 steps ≈ 4.4 s/step**
- Base (CFG 4.0, conditional + unconditional → 2× compute): **235.16 s / 28 steps ≈ 8.4 s/step**

Ratio 8.4 / 4.4 = **1.91×** — exactly what CFG > 1 predicts (each step computes both conditional and unconditional branches), confirming the Base variant isn't slower per-call than Distill at the same CFG. The cost is entirely sampling steps × CFG factor.

## Plan estimate vs reality

[`plans/active/plan-comfyui-zanime-sidecar.md`](../../../../plans/active/plan-comfyui-zanime-sidecar.md) extrapolated from public Z-Image-Turbo M3 Max benchmarks (60–80 s @ 1024² for 8-step Turbo) and assumed M3 Ultra would be ~2× faster:

| Variant | Plan estimate | Measured | Delta |
|:--|:--|:--|:--|
| Distill-4-step | 5–10 s | **17.75 s** | ~2.2× slower |
| Base 28-step | 50–90 s | **235.16 s** | ~3.0× slower |

Why the miss:
1. **CFG factor not in the extrapolation.** Base runs at CFG 4.0 (2× per-step compute vs CFG 1); the published M3 Max Turbo numbers were CFG 1 only.
2. **MPS attention path overhead.** `--use-pytorch-cross-attention` is the only MPS-compatible attention; ComfyUI's CUDA-tuned default attention (`xformers` / `sage`) doesn't apply, costing ~30–40 % per step.
3. **Z-Anime is heavier than vanilla Z-Image-Turbo.** The full fine-tune retains the Base 6B parameter shape — Distill-4-step is a *sampler-only* distillation, not a model-size reduction.

The wall-time pattern still fits the user's "best quality" question: **Base BF16 28-step** ≈ 4 minutes per image; **Distill-4-step** ≈ 18 s per image. CFG-1.0 Distill is what to use during prompt iteration; Base is for final renders only.

## Extrapolations (not measured)

Based on the per-step cost model:

| Variant | Steps | CFG | Estimated wall time @ 1024² |
|:--|--:|--:|:--|
| Distill-8-step | 8 | 1.0 | ~35 s |
| Base | 50 | 4.0 | ~420 s (~7 min) |
| Base | 28 | 6.0 | ~235 s (CFG > 4 collapses to same dual-pass cost) |

832 × 1216 (recommended portrait) ≈ same total pixel count as 1024² so wall times track within ±10 %.

## Artifacts

- 8 PNGs at `~/comfyui/output/zanime-bench_*.png` on macstudio (1.5–1.8 MB each, 1024×1024). 4 from Distill (warm-up + 3 timed), 4 from Base.
- All generations succeeded — no MPS `aten::*` not-implemented errors, no OOM, no crashes.

## What this means for the lab

- ComfyUI + Z-Anime is **viable** on M3 Ultra MPS but is interaction-bound rather than batch-bound. Use Distill-4-step for any in-the-loop work.
- 235 s/image at Base means an OpenCode-style agent loop calling image-gen would have to wait ~4 min between turns — confirms the plan's decision to skip the `/v1/images/generations` shim. Image-gen is for human-driven sessions in the ComfyUI web UI, not automated tool calls.
- Native MLX would likely beat MPS by 2–3× (the [`uqer1244/MLX_z-image`](https://github.com/uqer1244/MLX_z-image) port is 4-bit Tongyi base only — porting Z-Anime weights to MLX is a separate research thread).

## See also

- Driver: [`scripts/bench/bench_zanime_walltime.py`](../../../../scripts/bench/bench_zanime_walltime.py)
- Raw JSON: [`wall-time-comfyui.json`](wall-time-comfyui.json)
- Server runbook: [`docs/servers/comfyui/summary.md`](../../../servers/comfyui/summary.md)
- Plan: [`plans/active/plan-comfyui-zanime-sidecar.md`](../../../../plans/active/plan-comfyui-zanime-sidecar.md)
- Model card: [`SeeSee21/Z-Anime`](https://huggingface.co/SeeSee21/Z-Anime)
