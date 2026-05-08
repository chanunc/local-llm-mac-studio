# ComfyUI Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Running image generation](#running-image-generation)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`ComfyUI` is the lab's **image-generation sidecar** on port **8188**. Native node-based diffusion runtime (`comfyanonymous/ComfyUI`), installed via `comfy-cli` into a project-local `~/comfyui/.venv/`. Currently serving the SeeSee21/Z-Anime fine-tune of Alibaba's Z-Image (S3-DiT, 6B parameters, Apache-2.0).

**Status: research-grade sidecar, web UI only.** Not a chat/agent server; doesn't compete with the port-8000 / port-1234 / port-8098 / port-8099 stack. End users interact via ComfyUI's bundled browser UI (`http://<MAC_STUDIO_IP>:8188`). The lab does not expose an OpenAI `/v1/images/generations` shim — Base BF16 wall-time (~4 min/image) makes automated agent-loop integration impractical, and the Distill variant is fast enough for interactive work without a translation layer.

> **Why no MLX port?** [`uqer1244/MLX_z-image`](https://github.com/uqer1244/MLX_z-image) exists as a 4-bit MLX quantization of Tongyi's base Z-Image, but the SeeSee21 Z-Anime fine-tune has no MLX upload. Porting would beat MPS by an estimated 2–3× but is a separate research thread.

## Architecture

```
MacBook                            Mac Studio M3 Ultra (192.168.31.4)
┌──────────────────────┐           ┌─────────────────────────────────────────────┐
│ Browser → :8188 ─────┼── LAN ───>│ ~/comfyui/  (workspace, comfy-cli managed)  │
│ (ComfyUI web UI)     │           │   .venv/   torch 2.11.0 + MPS                │
│ scripts/bench/       │           │   main.py  (--listen 0.0.0.0 --port 8188)    │
│   bench_zanime_…     │           │   models/checkpoints/  (Z-Anime AIO BF16)    │
│   (HTTP /prompt API) │           │   models/vae/          (ae.safetensors)      │
└──────────────────────┘           │   models/text_encoders/                       │
                                   │   user/default/workflows/                     │
                                   │   output/  (generated PNGs)                   │
                                   └─────────────────────────────────────────────┘
```

Inference path: workflow JSON → POST `/prompt` → ComfyUI queues + executes → `/history/<id>` reports completion → PNG lands in `~/comfyui/output/`. No Anthropic API, no OpenAI `/v1/chat/completions` surface — only ComfyUI's own JSON endpoints.

## Installation

```bash
# 1. Disk: confirm ≥40 GiB free for two Z-Anime AIO BF16 variants (~19 GiB each).
ssh macstudio "df -h ~ | tail -1"

# 2. Mac Studio uses Homebrew Python 3.12 (matches qwen-asr / dflash-mlx pattern).
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/comfyui-env && \
  ~/comfyui-env/bin/pip install --upgrade pip && \
  ~/comfyui-env/bin/pip install comfy-cli"

# 3. comfy-cli creates its own project venv at ~/comfyui/.venv/ (separate from the
#    bootstrap venv above; this is comfy-cli's normal pattern). --m-series picks the
#    Apple Silicon torch wheel; --fast-deps uses uv for ~30s vs ~4min pip resolve.
ssh macstudio "printf 'n\n' | ~/comfyui-env/bin/comfy --skip-prompt \
  --workspace ~/comfyui install --m-series --fast-deps"

# 4. Verify MPS is the active device.
ssh macstudio "~/comfyui/.venv/bin/python -c \
  'import torch; print(\"mps_available=\", torch.backends.mps.is_available())'"
# → mps_available= True
```

ComfyUI lands at `~/comfyui/`. The `~/comfyui-env/` bootstrap venv only holds `comfy-cli` itself; the actual ComfyUI runtime (PyTorch 2.11, transformers 5.8, etc.) lives at `~/comfyui/.venv/`. **Don't conflate the two when installing extra deps.**

The `comfy-aimdo unsupported operating system: Darwin` warning at boot is informational — it's a Linux/Windows-only NV-FP8 quantization plugin that doesn't apply on Mac.

### Z-Anime weights

```bash
# AIO files (single-file diffusion + VAE + text encoder bundle, the cleanest loader path)
# go in models/checkpoints/, NOT models/diffusion_models/. The latter is for split-file
# UNet-only safetensors that pair with separate VAELoader + CLIPLoader nodes.

ssh macstudio "~/comfyui/.venv/bin/hf download SeeSee21/Z-Anime \
  aio/z-anime-distill-4step-aio-bf16.safetensors --local-dir ~/zanime-stage && \
  ~/comfyui/.venv/bin/hf download SeeSee21/Z-Anime \
  aio/z-anime-base-aio-bf16.safetensors --local-dir ~/zanime-stage && \
  ~/comfyui/.venv/bin/hf download SeeSee21/Z-Anime \
  vae/ae.safetensors --local-dir ~/zanime-stage && \
  mkdir -p ~/comfyui/models/checkpoints && \
  mv ~/zanime-stage/aio/z-anime-distill-4step-aio-bf16.safetensors ~/comfyui/models/checkpoints/ && \
  mv ~/zanime-stage/aio/z-anime-base-aio-bf16.safetensors ~/comfyui/models/checkpoints/ && \
  mv ~/zanime-stage/vae/ae.safetensors ~/comfyui/models/vae/ && \
  rm -rf ~/zanime-stage"
```

`hf download` with multiple `--include` patterns is brittle (the `huggingface_hub` 1.14 CLI mixes positional and pattern args and silently ignores `--include` when both are present). Per-file invocations as above are the unambiguous shape.

The ae.safetensors VAE is included in the AIO file too — keep the standalone copy only as a backup or for the split-file workflow path.

## Running image generation

### Web UI (intended end-user path)

```bash
ssh macstudio "nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py \
  --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention \
  > /tmp/comfyui.log 2>&1 &"
```

`--use-pytorch-cross-attention` is **required** on Apple Silicon — it forces the MPS-compatible attention path. The default attention backend (xformers / sage / SDP) errors or runs on CPU.

Open `http://192.168.31.4:8188` in a browser on the MacBook. The official Z-Anime workflow JSON is at `~/comfyui/user/default/workflows/Z-Anime-Workflow-v1.json` — load it, swap the `CheckpointLoaderSimple` to point at `z-anime-distill-4step-aio-bf16.safetensors` (or `z-anime-base-aio-bf16.safetensors` for best quality), hit "Queue Prompt".

### Programmatic (benchmark, not a chat-client surface)

[`scripts/bench/bench_zanime_walltime.py`](../../../scripts/bench/bench_zanime_walltime.py) drives ComfyUI's `/prompt` endpoint with an 8-node API workflow and times wall clock per generation. Use only for benchmarking — not as a substitute for the web UI in production sessions.

```bash
python3 scripts/bench/bench_zanime_walltime.py --runs 3 --out /tmp/zanime-walltime.json
```

### Stop

```bash
ssh macstudio "pkill -f 'comfyui/main.py'"
```

## Health check

```bash
curl -s http://192.168.31.4:8188/system_stats | python3 -m json.tool
```

Returns ComfyUI's JSON device snapshot — confirms MPS is active and reports VRAM (M3 Ultra reports unified RAM as `vram_total`, ~96 GiB). Looks like:

```json
{
  "system": {"os": "darwin", "comfyui_version": "0.20.1", "pytorch_version": "2.11.0", ...},
  "devices": [{"name": "mps", "type": "mps", "vram_total": 103079215104, ...}]
}
```

There's no `/v1/models` endpoint. To list installed checkpoints:

```bash
curl -s http://192.168.31.4:8188/models/checkpoints | python3 -m json.tool
```

Logs:

```bash
ssh macstudio "tail -40 /tmp/comfyui.log"
```

## Performance (Mac Studio M3 Ultra, 96 GB)

ComfyUI 0.20.1 + PyTorch 2.11.0 + MPS, `--use-pytorch-cross-attention`. SeeSee21 Z-Anime AIO BF16, 1024×1024, sampler `euler` / scheduler `beta` / shift 3.5. 1 warm-up + 3 timed runs each:

| Variant | Steps | CFG | Warm-up | Mean | σ |
|:--|--:|--:|--:|--:|--:|
| Distill-4-step AIO BF16 | 4 | 1.0 | 24.84 s | **17.75 s** | 0.03 s |
| Base AIO BF16 | 28 | 4.0 | 246.37 s | **235.16 s** | 0.08 s |

Per-step cost: **4.4 s/step** at CFG 1.0 (Distill), **8.4 s/step** at CFG 4.0 (Base). The 1.91× ratio matches CFG > 1's doubled forward-pass exactly — there's no architecture penalty between Distill and Base, only the sampler-step count and the CFG branch count differ.

For "best quality": Base 28-step ≈ **4 minutes per image**. For interactive iteration: Distill-4-step ≈ **18 seconds per image**.

Raw JSON: [`docs/models/benchmarks/z-anime/wall-time-comfyui.json`](../../models/benchmarks/z-anime/wall-time-comfyui.json). Detailed write-up: [`wall-time-comfyui.md`](../../models/benchmarks/z-anime/wall-time-comfyui.md).

## Known limitations

- **No OpenAI-compatible API.** ComfyUI exposes `/prompt` (queue submit), `/history/<id>` (status + outputs), `/system_stats`, `/models/<type>` — but no `/v1/images/generations`. Existing chat clients (OpenCode, llm CLI, Lobehub) cannot trigger generations. To bridge would need `comfyui-openai-api` or similar; deferred per the deploy plan.
- **No JANG / JANGTQ / `bailing_hybrid` support.** ComfyUI is a diffusion runtime — the LLM-side patches and architectures from the rest of the lab don't apply. Don't try to point JANG-format weights at it.
- **AIO checkpoint reload is slow.** Switching between Distill-4-step and Base BF16 in the web UI re-loads ~19 GiB to MPS each time (~25 s warm-up per swap). Plan benchmark batches by variant, not interleaved.
- **Default attention backend is broken on MPS.** Always launch with `--use-pytorch-cross-attention`. Without it, ComfyUI tries xformers / sage / SDP, errors, and falls back to CPU — dropping 4-step Distill from 18 s to many minutes.
- **GGUF Q8_0 / Q4_K_S Z-Anime variants on disk are unused.** SeeSee21 ships them but the ComfyUI GGUF UNet loader (`UnetLoaderGGUF`) requires `ComfyUI-GGUF` custom nodes that aren't installed. Add via `comfy node install ComfyUI-GGUF` if you need the lower-VRAM variants — but at 96 GB unified memory, BF16 AIO wins on quality.
- **MPS unified memory accounting is loose.** `system_stats` reports the same value for `ram_total` and `vram_total` (~96 GiB) — both share the same unified pool. Activity Monitor's "Memory Pressure" graph is the actual ground-truth pressure indicator during long Base runs.
- **Z-Image-style workflow only.** ComfyUI 0.20.1 has first-party Z-Image-Turbo nodes (`ModelSamplingAuraFlow` for the AuraFlow-style scheduler that Z-Image uses). Don't try to load Flux / SDXL / Pony / Illustrious workflows against the Z-Anime checkpoint — different architectures.

## See also

- [`scripts/bench/bench_zanime_walltime.py`](../../../scripts/bench/bench_zanime_walltime.py) — wall-time benchmark driver
- [`docs/models/benchmarks/z-anime/wall-time-comfyui.md`](../../models/benchmarks/z-anime/wall-time-comfyui.md) — benchmark write-up
- [`plans/active/plan-comfyui-zanime-sidecar.md`](../../../plans/active/plan-comfyui-zanime-sidecar.md) — deploy plan
- [SeeSee21/Z-Anime model card](https://huggingface.co/SeeSee21/Z-Anime) (Apache-2.0, S3-DiT 6B, AIO + diffusers + GGUF)
- [Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) — base architecture
- [Z-Image paper (arXiv 2511.22699)](https://arxiv.org/abs/2511.22699) — S3-DiT design
- [ComfyUI Z-Image-Turbo official workflow](https://docs.comfy.org/tutorials/image/z-image/z-image-turbo)
- [`martin-rizzo/AmazingZImageWorkflow`](https://github.com/martin-rizzo/AmazingZImageWorkflow) — community workflow with extras
- [`uqer1244/MLX_z-image`](https://github.com/uqer1244/MLX_z-image) — alternative MLX runtime (Tongyi base only, not Z-Anime)
