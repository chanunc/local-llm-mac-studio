# qwen-asr Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Running transcription](#running-transcription)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`qwen-asr` is the official Python package for **Qwen3-ASR**, Qwen's speech-to-text family released 2026-01-30 (Apache-2.0). On Apple Silicon, it runs the **transformers + MPS backend** — the package's `qwen-asr-serve` CLI uses CUDA-vLLM and is not usable on Mac Studio. Practical interface here is the in-process Python API or the bundled Gradio UI.

**Status: research-grade sidecar, no port-bound daemon.** Not a chat/agent server; doesn't compete with the port-8000 / port-1234 stack. Used for transcribing pre-recorded audio clips (≤5 min) — 30 languages + 22 Chinese dialects, 16 kHz mono, bf16 weights.

> **Why no quantization?** The 1.7B checkpoint is 4.7 GB in bf16 — MoE-quant savings are noise on a 96 GB box, and ASR is quality-sensitive (each wrong logit becomes a transcript word error that compounds into WER). Community 4-bit/8-bit uploads exist on HF but have no published WER baselines. See [`docs/models/per-model/model-summary-qwen3-asr.md`](../../models/per-model/model-summary-qwen3-asr.md) for the quantization analysis.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌────────────────────────────────────────┐
│ scp clip.wav ──┼─── LAN ───>│ ~/qwen-asr-env/                         │
│ ssh transcribe │            │   torch 2.11.0 + MPS                    │
└────────────────┘            │   transformers 4.57.6                   │
                              │   qwen-asr 0.0.6 (Python API)           │
                              │   Qwen/Qwen3-ASR-1.7B (4.7 GB bf16)     │
                              │   ~/.cache/huggingface/hub/             │
                              │   No port-bound daemon (CUDA-only path) │
                              └────────────────────────────────────────┘
```

Inference path: clip → `Qwen3ASRModel.transcribe(audio=..., language=None)` → `(language_id, transcript)`. Auto-detects language across 30 supported codes; pass `language="English"` (or other Qwen3-ASR language string) to skip detection and trim ~80 ms.

## Installation

Mac Studio currently has Python 3.11, 3.12, and 3.14 via Homebrew. Use **3.12** — `qwen-asr` declares `python>=3.9,<3.14`, so 3.14 is out of range.

```bash
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/qwen-asr-env && \
  ~/qwen-asr-env/bin/pip install -U pip wheel && \
  ~/qwen-asr-env/bin/pip install qwen-asr"
```

Skip the `qwen-asr[vllm]` extra — its `vllm` dependency expects CUDA kernels that don't build on Apple Silicon. Skip `flash-attn` for the same reason. The default torch wheel (2.11.0) ships with MPS support out of the box.

Verify:

```bash
ssh macstudio "~/qwen-asr-env/bin/python -c 'import torch; print(torch.backends.mps.is_available())'"
# → True
```

First model fetch (~4.7 GB) is implicit on first `from_pretrained()` — pre-warm by running the smoke script once.

## Running transcription

The Python API is the supported path on M3 Ultra:

```python
import torch
from qwen_asr import Qwen3ASRModel

model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-1.7B",
    dtype=torch.bfloat16,
    device_map="mps",                  # NOT "cuda:0"
    max_inference_batch_size=8,
    max_new_tokens=256,
)
result = model.transcribe(audio="/path/to/clip.wav", language=None)[0]
print(result.language, result.text)
```

Two ready-to-run scripts in [`scripts/bench/`](../../../scripts/bench/):
- `bench_asr_smoke.py` — load + 1 warm + 1 timed pass against Qwen's official `asr_en.wav`
- `bench_asr_rtf.py` — load + 1 warm-up + 3 timed passes, writes `/tmp/qwen_asr_rtf.json`

`scp` the clip to the Mac Studio first (or pass an HTTPS URL — `transcribe()` accepts both).

The bundled `qwen-asr-demo` CLI starts a Gradio UI bound to localhost; pass `--server-name 0.0.0.0` to expose over LAN. `qwen-asr-demo-streaming` requires the vLLM (CUDA) backend and **does not run on M3 Ultra**.

## Health check

```bash
ssh macstudio "~/qwen-asr-env/bin/python -c 'from qwen_asr import Qwen3ASRModel; print(\"qwen_asr import ok\")'"
ssh macstudio "du -sh ~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-1.7B"
```

There's no `/v1/models` to curl — see [Known limitations](#known-limitations).

## Performance (Mac Studio M3 Ultra, 96 GB)

`Qwen/Qwen3-ASR-1.7B`, bf16, MPS device, 15.05-second mono 48 kHz English clip (Qwen's `asr_en.wav`). Three timed passes after one warm-up:

| Metric | Value |
|:--|:--|
| Model load (warm filesystem cache) | 3.2 s |
| Model load (cold first run incl. download) | 42 s |
| Warm-up pass | 1.78 s |
| Timed pass 1 / 2 / 3 | 0.790 / 0.788 / 0.791 s |
| Average wall time | 0.790 s |
| **RTF (audio_seconds / wall_seconds)** | **19.06×** |
| Peak Python RSS | 1.1 GB |
| Disk footprint (bf16, 1.7B) | 4.4 GB |

For context, Qwen's published H100 RTFx is 147.93 — M3 Ultra MPS is ~13 % of that, but **19× realtime** still means a 1-hour clip transcribes in ~3 minutes. Variance across passes is sub-1 % so a single warm timing is representative.

Raw JSON: [`docs/models/benchmarks/logs/qwen3-asr-1.7b/rtf-mps.json`](../../models/benchmarks/qwen3-asr-1.7b/rtf-mps.json).

## Known limitations

- **No port-bound server on Apple Silicon.** `qwen-asr-serve` requires CUDA-vLLM. Inference is in-process Python — clients can't query an `/v1/audio/transcriptions` endpoint over LAN unless you write a FastAPI wrapper around the Python API.
- **Streaming requires vLLM.** Offline-only on MPS. Real-time microphone transcription via `qwen-asr-demo-streaming` does not run.
- **Audio length cap ≈ 5 minutes** per call. Longer clips need to be chunked client-side and stitched.
- **Not a chat/agent model.** Transcripts only — no tool-call surface, no Anthropic API, no place in the existing `bench_api_server.py` / `bench_agent_tool_call.py` rigs.
- **Sample rate is auto-resampled to 16 kHz internally.** Source rate is irrelevant; the smoke clip is 48 kHz mono and works fine.
- **Peak RSS understates real memory.** `getrusage(ru_maxrss)` reports the Python process resident set (~1.1 GB), but bf16 weights live in MPS unified memory and don't show up in that counter. Plan for ~5 GB total memory pressure.

## See also

- [Qwen3-ASR per-model deep dive](../../models/per-model/model-summary-qwen3-asr.md) — quantization justification, server fit analysis, full deploy log
- [`scripts/bench/bench_asr_smoke.py`](../../../scripts/bench/bench_asr_smoke.py) and [`scripts/bench/bench_asr_rtf.py`](../../../scripts/bench/bench_asr_rtf.py)
- [Qwen3-ASR-1.7B model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) (Apache-2.0, 4.7 GB bf16)
- [Qwen3-ASR-0.6B model card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) (smaller, throughput-focused)
- [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) — optional word-level timestamp companion
