# Ideogram 4 on Mac Studio: runtime, quantization, and design-improvement eval

Status: active
Created: 2026-06-06
Canonical: no

## Goal

Evaluate [`ideogram-ai/ideogram-4`](https://huggingface.co/collections/ideogram-ai/ideogram-4)
on the Mac Studio M3 Ultra (96 GB), choose the defensible Apple-Silicon
quantization/runtime, and add an agent-style image benchmark that can be driven
from a script in the same way `bench_agent_tool_call.py` drives OpenCode.

The first end-to-end task is a constrained redesign:

> Inspect a deliberately boring event flyer, preserve every factual detail, and
> regenerate it as a stronger professional design.

The deterministic source fixture is
[`docs/models/benchmarks/fixtures/ideogram4/boring-event-flyer.svg`](../../docs/models/benchmarks/fixtures/ideogram4/boring-event-flyer.svg).

## Release facts

Ideogram 4 was released on **2026-06-03**. It is a 9.3B, single-stream
flow-matching DiT trained from scratch. Its differentiators are directly
relevant to design work:

- structured JSON captions;
- literal text elements;
- normalized bounding-box layout;
- per-image and per-element color palettes;
- 256-2048 pixel dimensions in multiples of 16;
- aspect ratios up to 6:1;
- Qwen3-VL-8B-Instruct as the text encoder;
- separate conditional and unconditional transformer branches.

The weights are gated and use the **Ideogram 4 Non-Commercial** license. This is
appropriate for personal lab evaluation, but generated assets and deployment
must not be assumed safe for commercial use.

## Quantization decision

| Candidate | Vendor support | Apple Silicon | Runtime fit | Decision |
|:--|:--|:--|:--|:--|
| `ideogram-4-nf4` | CUDA + Diffusers | No | bitsandbytes `Linear4bit`; loader rejects non-CUDA devices | Reject for Mac Studio |
| `ideogram-4-fp8` | All hardware; official Python runtime | Yes | weight-only e4m3 FP8, BF16 activations and BF16 matmul | Supported reference |
| Comfy-Org FP8 scaled repack | ComfyUI 0.24.x native workflow | Yes | existing `:8188` MPS sidecar and `/prompt` API | **Recommended** |
| BF16 community conversion | Not an official release tier | Likely, but much larger | no quality reason to spend roughly 2x weight memory | Do not start here |
| SDNQ/other community 4-bit | Experimental community work | Unproven on MPS | no vendor quality or kernel validation | Revisit only after FP8 baseline |

### Why FP8 works without Apple FP8 tensor cores

The official `Fp8Linear` stores weights as `torch.float8_e4m3fn` with a
per-output-row FP32 scale. On every forward pass it dequantizes the weight to the
activation dtype and executes an ordinary BF16 linear operation. This saves
weight memory, but it is **not native FP8 compute** and may add substantial
dequantization overhead on MPS.

That makes FP8 a memory-compatible format, not a guaranteed speed optimization.
The benchmark must measure both wall time and peak unified-memory pressure.

### Why ComfyUI is the first deployment target

ComfyUI 0.24.0 added native Ideogram 4 support on release day. The official
workflow uses:

- `ideogram4_fp8_scaled.safetensors`;
- `ideogram4_unconditional_fp8_scaled.safetensors`;
- `qwen3vl_8b_fp8_scaled.safetensors`;
- `flux2-vae.safetensors`.

This reuses the existing ComfyUI service on port 8188, its programmatic
`POST /prompt` and `/history/<id>` surface, MPS launch flags, output handling,
and the existing Z-Anime wall-time benchmark pattern. A separate official
Python runtime is useful as a correctness cross-check, but creating another
daemon first would duplicate infrastructure.

`mlx-openai-server` is not the target: its Flux image support does not imply
Ideogram 4 architecture support. NF4 cannot run through it on MPS, and no
official MLX conversion exists.

## Deployment plan

### 1. Preconditions

1. Accept the gated model license using the Hugging Face account available on
   the Mac Studio.
2. Check free disk before downloading. Use a conservative **45 GiB** guard until
   exact Xet file sizes are recorded.
3. Record the existing ComfyUI revision and Python package lock.
4. Do not assert live state in documentation.

### 2. Upgrade the existing sidecar

Upgrade `~/comfyui/` from 0.20.1 to a tested 0.24.x revision. Keep the existing
launch shape:

```bash
ssh macstudio "nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py \
  --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention \
  > /tmp/comfyui.log 2>&1 &"
```

Before replacing the environment, capture `pip freeze` and the git revision so
Z-Anime can be regression-tested after the upgrade.

### 3. Install the official ComfyUI weights

Use the paths from `Comfy-Org/Ideogram-4`:

```text
~/comfyui/models/diffusion_models/ideogram4_fp8_scaled.safetensors
~/comfyui/models/diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors
~/comfyui/models/text_encoders/qwen3vl_8b_fp8_scaled.safetensors
~/comfyui/models/vae/flux2-vae.safetensors
```

Download the official `image_ideogram4_t2i.json` workflow from
`Comfy-Org/workflow_templates`. Export its API form after loading it in
ComfyUI; benchmark scripts should consume the API workflow, not patch the
116-KB UI graph.

### 4. Smoke gates

1. `GET /system_stats` reports MPS.
2. The Ideogram workflow queues and produces a 1024x1024 PNG.
3. No CPU fallback or MPS unsupported-operation traceback appears.
4. The exact text `DESIGN SYSTEMS NIGHT` is rendered legibly.
5. The existing Z-Anime Distill workflow still completes after the ComfyUI
   upgrade.

## Benchmark harness

Create `scripts/bench/bench_ideogram4_design.py`, modeled on
`bench_zanime_walltime.py`, with four stages:

1. **Analyze**: send the source image to an OpenAI-compatible VLM endpoint.
2. **Plan**: require a minified Ideogram JSON caption matching the official
   schema, including exact text and normalized bounding boxes.
3. **Generate**: inject the caption, seed, resolution, and sampler preset into
   the exported ComfyUI API workflow; submit to `/prompt`; poll
   `/history/<id>`; retrieve the PNG.
4. **Judge**: send source, candidate, and rubric to a VLM judge; validate exact
   text with OCR; record wall time and memory samples.

This is agent-like without coupling image generation to OpenCode internals. An
OpenCode tool can later wrap the same script:

```json
{
  "image_redesign": {
    "command": "python3 scripts/bench/bench_ideogram4_design.py --input \"$INPUT\" --brief \"$BRIEF\""
  }
}
```

The harness should support:

```text
--input PATH
--brief TEXT
--planner-base-url URL
--planner-model ID
--judge-base-url URL
--judge-model ID
--comfy-url URL
--preset turbo|default|quality
--seed INT
--runs INT
--out PATH
```

Persist:

```text
docs/models/benchmarks/logs/ideogram4-fp8/
  design-redesign-comfyui.json
  candidates/
  judge-transcripts/
```

## First test: boring flyer redesign

### Source

The SVG fixture is intentionally weak: gray background, centered Arial text,
poor hierarchy, no grid, no visual identity, and a generic black CTA. It has
unambiguous content that can be checked mechanically.

Required copy:

```text
DESIGN SYSTEMS NIGHT
Thursday 18 June, 7:00 PM
North Hall, Riverside Arts Centre
Three short talks, live critique, and practical takeaways.
Free entry - registration required
REGISTER NOW
```

### Brief

```text
Redesign this event flyer as a polished contemporary poster for a professional
design community. Preserve every factual detail and every character of the
copy. Improve hierarchy, spacing, composition, palette, and visual identity.
Keep it readable at phone size. Use a 4:5 portrait layout and do not invent
sponsors, prices, speakers, dates, addresses, or logos.
```

Ideogram 4 does not accept the source image as an img2img conditioning input.
The VLM planner therefore treats the image as a **requirements source**, then
Ideogram regenerates a new design from structured text and layout constraints.
This distinction must be explicit in reports.

### Matrix

Use the same structured caption and seeds across presets:

| Run | Preset | Steps | Resolution | Seeds | Purpose |
|:--|--:|--:|--:|--:|:--|
| Fast | Turbo | 12 | 1024x1280 | 3 fixed | agent-loop viability |
| Balanced | Default | 20 | 1024x1280 | 3 fixed | likely operational default |
| Quality | Quality | 48 | 1024x1280 | 3 fixed | quality ceiling |

Add one ablation at Default/20:

- plain brief directly to Ideogram;
- local VLM-generated structured JSON;
- official hosted magic-prompt output, only if an API key is deliberately
  configured.

This isolates model quality from prompt-expansion quality.

### Scoring

Use a 100-point rubric:

| Dimension | Weight | Method |
|:--|--:|:--|
| Exact text preservation | 25 | OCR plus normalized string comparison |
| Factual preservation/no inventions | 15 | deterministic required/forbidden checks + VLM |
| Visual hierarchy | 15 | blind VLM pairwise judge |
| Layout and spacing | 15 | blind VLM pairwise judge |
| Legibility at phone size | 10 | downscale to 320x400, OCR + judge |
| Aesthetic/professional quality | 15 | blind VLM pairwise judge |
| Brief adherence | 5 | VLM rubric |

Operational metrics:

- cold load time;
- warm generation wall time;
- peak memory pressure / swap;
- output file size;
- blocked/safety-filter rate;
- success rate across fixed seeds.

Pass criteria:

- candidate beats the source by at least **20 rubric points**;
- exact required-copy score is **100%**;
- no invented factual claims;
- warm Default/20 completes without swap growth or CPU fallback;
- at least 2 of 3 fixed seeds pass all hard constraints.

## Risks

- **MPS throughput**: FP8 dequantizes every linear weight every forward pass.
  Ideogram also evaluates separate positive and negative transformers, so a
  20-step run may be much slower than Z-Anime’s 4-step path.
- **Unified memory**: model, unconditional branch, Qwen3-VL encoder, VAE,
  dequantized temporaries, and activations coexist. The 96 GB capacity is
  probably sufficient, but headroom must be measured rather than inferred.
- **Text correctness**: strong typography quality is not guaranteed character
  perfect. OCR is a hard gate, not merely a judge-model opinion.
- **No true img2img**: visual identity from the source can only be translated by
  the VLM into JSON. Pixel-level preservation is out of scope.
- **License**: non-commercial model terms constrain downstream use.
- **ComfyUI regression**: upgrading from 0.20.1 may change the Z-Anime workflow
  or MPS behavior; rerun its smoke and wall-time baseline.

## Documentation cascade after measured deployment

After successful runs:

- update `docs/servers/comfyui/summary.md` for ComfyUI 0.24.x and Ideogram 4;
- add Ideogram 4 to `docs/models/model-summary.md`;
- add the benchmark driver to `scripts/README.md`;
- store raw results under `docs/models/benchmarks/logs/ideogram4-fp8/`;
- add a benchmark write-up under `docs/models/benchmarks/`;
- mirror any server-command changes in `CLAUDE.md` and `AGENTS.md`;
- update `README.md` only with measured, evergreen findings.

## Primary sources

- [Ideogram 4 collection](https://huggingface.co/collections/ideogram-ai/ideogram-4)
- [Official Ideogram 4 repository](https://github.com/ideogram-oss/ideogram4)
- [Official inference reference](https://github.com/ideogram-oss/ideogram4/blob/main/docs/inference.md)
- [Official prompting guide](https://github.com/ideogram-oss/ideogram4/blob/main/docs/prompting.md)
- [ComfyUI day-zero support announcement](https://blog.comfy.org/p/ideogram-4-day-0-support-in-comfyui)
- [Comfy-Org FP8 model layout](https://huggingface.co/Comfy-Org/Ideogram-4)
- [Official ComfyUI workflow](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_ideogram4_t2i.json)
