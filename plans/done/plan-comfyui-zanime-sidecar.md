# ComfyUI sidecar for Z-Image / Z-Anime image generation

Status: done
Created: 2026-05-08
Completed: 2026-05-08
Canonical: no

## Context

The lab has zero diffusion / image-generation runtimes. All eight existing servers (vllm-mlx, mlx-openai-server, oMLX, vmlx, lm-studio, dflash-mlx, llama-cpp-turboquant, qwen-asr) are LLM-only or speech-to-text. The user wants to evaluate [`SeeSee21/Z-Anime`](https://huggingface.co/SeeSee21/Z-Anime) — a full fine-tune of Alibaba's [`Tongyi-MAI/Z-Image`](https://huggingface.co/Tongyi-MAI/Z-Image) (S3-DiT Single-Stream Diffusion Transformer, 6B params, Apache-2.0).

Z-Anime ships in ComfyUI-shaped formats (BF16 / FP8 safetensors, GGUF Q8_0/Q4_K_S, AIO single-file, diffusers folder), uses `qwen_3_4b.safetensors` text encoder + `ae.safetensors` VAE, and offers Distill-4-step / Distill-8-step / Base variants. ComfyUI gained native Z-Image-Turbo support in November 2025 — the model loads with first-party nodes, not third-party loaders.

Goal: stand up ComfyUI as a documented sidecar (matching qwen-asr's minimal posture — no port-8000 contention, no OpenAI-compat shim, no `configs/clients/comfyui/` entries), deploy both Z-Anime Distill-4-step (fast iteration) and Z-Anime Base BF16 (best-quality reference), and benchmark wall time on the M3 Ultra so future image-model work has a baseline.

## Approach

Mirror the qwen-asr sidecar pattern, not a full Event 1 server-type deploy:

- ComfyUI native web UI only (`http://<MAC_STUDIO_IP>:8188`); no `/v1/images/generations` shim, no `configs/clients/comfyui/` directory, no entry in `scripts/switch_opencode_config.py`. Not a chat-client target.
- Install via `comfy-cli` (the official supported path; no Homebrew formula or cask exists) into a dedicated `~/comfyui-env/` venv on macstudio, mirroring `~/qwen-asr-env/`, `~/dflash-mlx-env/`, `~/vllm-mlx-env/` layout.
- Run on port **8188** — collision-free (8000 / 1234 / 8098 / 8099 untouched), can coexist with any port-8000 LLM. No Event 4 LLM-process kill needed.
- Two model variants downloaded: Base BF16 is the documented "best-quality" reference, Distill-4-step is the everyday iteration target.
- Document under `docs/servers/comfyui/summary.md` following the runbook structure of `docs/servers/qwen-asr/summary.md`.
- Wall-time numbers captured as a one-shot benchmark write-up, not a re-runnable `bench_*.py` (image-gen has no driver yet).

### Best-quality generation time — estimate to verify in Phase 4

Published Z-Image-Turbo (8 steps) numbers on M3 Max land at ~60–80 s @ 1024². The M3 Ultra has roughly 2× the GPU cores (80 vs 40), so the rough envelope on the lab's box is:

| Variant | Steps | Estimated M3 Ultra wall time @ 1024² | Notes |
|:--|--:|:--|:--|
| Distill-4-step | 4 | **~5–10 s** | CFG 1.0, negative prompt has limited effect |
| Distill-8-step | 8 | **~10–20 s** | Quality/speed sweet spot |
| Base BF16 | 28 | **~50–90 s** | Full CFG 3–9, full negative-prompt support |
| Base BF16 | 50 | **~90–180 s** | Diminishing returns past 28 in the SeeSee21 card |

Numbers above are extrapolations from public M3 Max benches; Phase 4 of this plan replaces them with measured values for the Mac Studio.

## Implementation steps

### Phase 1 — Install ComfyUI on macstudio (no doc edits yet)

1. Pre-install hygiene: confirm port 8188 is free —
   `ssh macstudio "lsof -nP -iTCP:8188 -sTCP:LISTEN"` (should print nothing). No Event 4 LLM-server kill required; ComfyUI does not touch port 8000.
2. Create venv: `ssh macstudio "python3 -m venv ~/comfyui-env"`.
3. Install ComfyUI via `comfy-cli`:
   ```
   ~/comfyui-env/bin/pip install comfy-cli
   ~/comfyui-env/bin/comfy --workspace ~/comfyui install --nvidia=False
   ```
   (`--nvidia=False` forces the MPS / CPU PyTorch wheels.)
4. Smoke test: `~/comfyui-env/bin/python ~/comfyui/main.py --listen 127.0.0.1 --port 8188`, check `http://127.0.0.1:8188` loads in a local browser, kill.

### Phase 2 — Download Z-Anime weights into ComfyUI's expected layout

ComfyUI expects:
- `~/comfyui/models/diffusion_models/` — Z-Anime safetensors / GGUF
- `~/comfyui/models/text_encoders/qwen_3_4b.safetensors`
- `~/comfyui/models/vae/ae.safetensors`

```
huggingface-cli download SeeSee21/Z-Anime \
  --include 'Z-Anime-Distill-4-Step-AIO*.safetensors' 'Z-Anime-Base-BF16*.safetensors' \
  --local-dir ~/comfyui/models/diffusion_models
```

AIO files bundle VAE + text encoder, so external `qwen_3_4b.safetensors` and `ae.safetensors` are only needed for the Base BF16 variant. Verify what SeeSee21 actually ships under each filename before downloading externals (the model card lists `Z-Anime` and `Engineer V4` text encoders — pick the SeeSee21-recommended one).

Disk budget: ~12 GB Distill-4-step AIO + ~13 GB Base BF16 + ~4 GB `qwen_3_4b` text encoder + ~300 MB `ae` VAE ≈ **~30 GB**. Run `df -h ~` first and use the `/list-model-to-remove` skill to free space if `~/.cache/huggingface/` is tight (the lab routinely runs hot on SSD).

### Phase 3 — Bind LAN-wide and capture launch / stop shape

1. Launch (this is the snippet that will land in README + CLAUDE.md / AGENTS.md Common Commands in Phase 5):
   ```
   ssh macstudio "nohup ~/comfyui-env/bin/python ~/comfyui/main.py \
     --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention \
     > /tmp/comfyui.log 2>&1 &"
   ```
   `--use-pytorch-cross-attention` forces the MPS-compatible attention path; the default xformers path errors on Apple Silicon.
2. Stop:
   ```
   ssh macstudio "pkill -f 'comfyui/main.py'"
   ```
3. Health check:
   ```
   curl -s http://<MAC_STUDIO_IP>:8188/system_stats | python3 -m json.tool
   ```
   Returns ComfyUI's CPU / RAM / GPU JSON — lightweight LAN ping.

### Phase 4 — Benchmark wall time for both variants (deliverable)

One-shot run, not a recurring scripted bench:
1. Load `martin-rizzo/AmazingZImageWorkflow`'s default JSON in the web UI, point the Diffusion node at Distill-4-step AIO, run 5 generations at 1024×1024 with CFG 1.0, capture wall-time mean from `/tmp/comfyui.log`.
2. Swap Diffusion node to Base BF16 + `qwen_3_4b` text encoder + `ae` VAE, set steps=28 / CFG=4.0, run 5 generations same resolution, capture mean.
3. Repeat (2) at steps=50 if the 28-step result is borderline (e.g. plates of text, hands).
4. Write findings to `docs/models/benchmarks/z-anime/wall-time-comfyui.md` (markdown — image-gen has no JSON bench schema yet).

### Phase 5 — Documentation (Event 1 partial — qwen-asr scope)

Per the qwen-asr precedent, **skip** these Event 1 items (they don't apply to a UI-only sidecar):

- ❌ `configs/clients/comfyui/` — no chat-client config files
- ❌ `configs/clients/README.md` — no Layout-table row needed
- ❌ `scripts/switch_opencode_config.py` — not a switchable LLM server
- ❌ `configs/README.md` Server Roles table / Switching Servers — not on port 8000

**Do** update:

- ✅ `README.md` — data-flow diagram (add `comfyui :8188` under sidecars), Quick Start launch + stop, Health Check curl + log tail, Servers table row (link to `docs/servers/comfyui/summary.md`), Known Limitations entry ("no OpenAI `/v1/images/generations` API — web UI only")
- ✅ run-state is probed via `scripts/chk_llm_macstu.py`, not tracked in docs
- ✅ `CLAUDE.md` **and** `AGENTS.md` — overview paragraph (ComfyUI sentence after qwen-asr in the server list), Architecture bullet, data-flow diagram, Common Commands launch + stop, Editing Workflow scope note. Mirror edits between the two files.
- ✅ `docs/servers/comfyui/summary.md` — **NEW** runbook (Overview / Architecture / Installation / Starting the server / Health check / Performance / Known limitations / See also), matching `docs/servers/qwen-asr/summary.md` shape
- ✅ `docs/servers/README.md` — runbook index row
- ✅ `docs/models/model-summary.md` — Z-Anime entry under a new "Image generation" section (and Z-Image base if useful as a reference row)
- ✅ `docs/models/per-model/model-summary-z-anime.md` — **only if** the deploy reveals enough gotchas to warrant > 150 lines (MPS regressions, weight-layout issues). Otherwise keep specs inline in `model-summary.md`.
- ✅ `docs/models/README.md` — Per-model deep-dives table row, **only** if a per-model file is created
- ✅ `docs/models/benchmarks/z-anime/wall-time-comfyui.md` — **NEW** benchmark notes from Phase 4
- ✅ Update the "All servers except lm-studio support JANG…" line in `README.md` to also exclude `comfyui` (image-gen runtime; JANG / JANGTQ / `bailing_hybrid` are LLM concepts and don't apply)

## Critical files to modify

- `README.md` — data flow, Servers table, Quick Start, Health Check, Known Limitations
- `CLAUDE.md` and `AGENTS.md` — overview, Architecture, data flow, Common Commands (mirror; lines must stay content-identical except header)
- `docs/servers/comfyui/summary.md` — **NEW** runbook
- `docs/servers/README.md` — runbook index
- `docs/models/model-summary.md` — Z-Anime + Z-Image base entries
- `docs/models/benchmarks/z-anime/wall-time-comfyui.md` — **NEW** benchmark notes

## Existing patterns and files to reuse

- Runbook structure: `docs/servers/qwen-asr/summary.md` — closest sidecar precedent (non-port-8000, no OpenAI chat surface, no per-client templates)
- Sidecar venv layout: `~/qwen-asr-env/`, `~/dflash-mlx-env/`, `~/vllm-mlx-env/`
- `huggingface-cli download` flow: same as qwen-asr's `Qwen3-ASR-1.7B` weight pull
- Workflow JSON: [`martin-rizzo/AmazingZImageWorkflow`](https://github.com/martin-rizzo/AmazingZImageWorkflow) — community, GGUF + safetensors variants, no need to write a workflow from scratch
- `/list-model-to-remove` skill — run before Phase 2 if `~/.cache/huggingface/` free space < 50 GB

## Verification

Service alive (after Phase 3):
```
curl -s http://<MAC_STUDIO_IP>:8188/system_stats | python3 -m json.tool
ssh macstudio "tail -20 /tmp/comfyui.log"
```
Expect a JSON body with `system.os == 'Darwin'` and no `aten::*` not-implemented tracebacks.

Functional smoke (after Phase 4):
1. Open `http://<MAC_STUDIO_IP>:8188` in a browser on the MacBook.
2. Load the AmazingZImageWorkflow JSON.
3. Generate one image with Distill-4-step AIO, prompt `"anime girl in a flower field, soft lighting"`. Confirm wall time is in the **5–15 s** range; > 30 s flags MPS fallback or CPU execution and needs the `--use-pytorch-cross-attention` / `--force-fp16` flags re-checked.
4. Generate one image with Base BF16, 28 steps, CFG 4.0, same prompt. Confirm wall time is in the **50–120 s** range.
5. Capture both means in `docs/models/benchmarks/z-anime/wall-time-comfyui.md`.

Drift check (Sync Policy compliance, run before commit):
```
grep -n "comfyui\|ComfyUI\|Z-Anime\|Z-Image" \
  README.md AGENTS.md CLAUDE.md \
  docs/servers/README.md docs/models/README.md \
  docs/models/model-summary.md
```
Every doc above should mention the new sidecar after Phase 5.

## Risks and decisions

- **MPS regression on S3-DiT**: ComfyUI's first-party Z-Image nodes were tuned on CUDA. MPS fallback paths may hit unsupported ops (sliding-window attention, custom Triton-style kernels). Mitigation: `--use-pytorch-cross-attention` flag forces the MPS-friendly attention path; watch for `aten::*` not-implemented errors on first run and re-fall back to `--cpu` for the offending node only.
- **Disk pressure**: ~30 GB across two variants + text encoder + VAE. The Mac Studio routinely runs near full on the LLM side; gate Phase 2 on `df -h ~` and the `/list-model-to-remove` skill.
- **Z-Anime not yet MLX-ported**: only `uqer1244/MLX_z-image` exists, and only for the Tongyi base. Native MLX would likely beat MPS by 2–3× but porting Z-Anime weights is a separate research thread, not Phase 1–5 scope.
- **No OpenAI-compat shim**: per the user's explicit choice, chat clients (OpenCode, llm CLI, Lobehub) cannot trigger generations. Re-opening this is a future plan, not a Phase 5 item.
- **Lobehub plan unaffected**: `plan-lobehub-macstudio-setup.md` covers chat-only providers and does not collide with this sidecar (different ports, different surface).

## Out of scope (explicit)

- OpenAI-compat `/v1/images/generations` wrapper (e.g. `comfyui-openai-api`).
- `configs/clients/comfyui/` directory and per-client templates.
- Inclusion in `scripts/switch_opencode_config.py`.
- Native MLX port of the Z-Anime weights.
- Z-Anime LoRA training (the model card mentions support; not a deploy target).
- Distill-8-step variant — covered by interpolating between Distill-4-step and Base benchmarks.

## See also

- [`SeeSee21/Z-Anime` model card](https://huggingface.co/SeeSee21/Z-Anime)
- [`Tongyi-MAI/Z-Image-Turbo`](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) — base architecture
- [Z-Image paper (arXiv 2511.22699)](https://arxiv.org/abs/2511.22699)
- [ComfyUI Z-Image-Turbo official workflow](https://docs.comfy.org/tutorials/image/z-image/z-image-turbo)
- [Z-Image-Turbo + ComfyUI on Apple Silicon Macs 2026 (Medium)](https://medium.com/@tchpnk/z-image-turbo-comfyui-on-apple-silicon-2026-0aa78d05132d)
- [`martin-rizzo/AmazingZImageWorkflow`](https://github.com/martin-rizzo/AmazingZImageWorkflow)
- [`OrdinarySF/z-image-inference`](https://github.com/OrdinarySF/z-image-inference) — alternative Gradio + FastAPI MPS runtime, kept in reserve if ComfyUI stalls
- `docs/servers/qwen-asr/summary.md` — runbook structure precedent
- `plans/active/plan-lobehub-macstudio-setup.md` — chat UI plan (non-overlapping)
