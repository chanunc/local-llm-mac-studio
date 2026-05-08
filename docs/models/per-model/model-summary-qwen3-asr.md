# Qwen3-ASR Family

Speech-to-text models released by Qwen on **2026-01-30** (Apache-2.0). Two checkpoints + an optional forced-aligner; this lab targets the 1.7B variant on the Mac Studio M3 Ultra MPS path.

## Index

- [Family overview](#family-overview)
- [Quantization fit — stay bf16](#quantization-fit--stay-bf16)
- [Server fit — no existing server speaks audio](#server-fit--no-existing-server-speaks-audio)
- [Deploy recipe — 1.7B on M3 Ultra MPS](#deploy-recipe--17b-on-m3-ultra-mps)
- [Smoke results](#smoke-results)
- [RTF benchmark](#rtf-benchmark)
- [Caveats](#caveats)
- [See also](#see-also)

## Family overview

| Model | Params | Disk (bf16) | Reference WER | Throughput claim |
|:--|:--|:--|:--|:--|
| `Qwen/Qwen3-ASR-1.7B` | 1.7 B | ~4.7 GB | competitive w/ GPT-4o & Gemini | RTFx 147.93 (open-asr-leaderboard, H100) |
| `Qwen/Qwen3-ASR-0.6B` | 0.6 B | ~1.2 GB | LibriSpeech 2.11 / 4.55 (clean / other) · GigaSpeech 8.88 · WenetSpeech 5.97 / 6.88 | 2000× throughput @ concurrency=128 |
| `Qwen/Qwen3-ForcedAligner-0.6B` | 0.6 B | optional | — (timestamps only, ≤ 5 min) | — |

Languages: 30 (zh, en, yue, ar, de, fr, es, pt, id, it, ko, ru, th, vi, ja, tr, hi, ms, nl, sv, da, fi, pl, cs, fil, fa, el, hu, mk, ro). Plus 22 Chinese dialects. Inputs: speech, singing voice, songs with BGM. Internal sample rate: 16 kHz mono (auto-resampled).

## Quantization fit — stay bf16

The HF collection lists "21 quantized variants" alongside the official checkpoints. **None are recommended for this lab.** Reasoning:

1. **The base model is already tiny.** 1.7 B in bf16 is 4.7 GB. Quantizing to 4-bit saves ~3 GB on a machine with 96 GB unified memory — savings are noise. Latency wins from quantization on an MPS-bottlenecked single-clip path are similarly negligible (compute is dominated by the audio encoder + autoregressive decode of ≤ 256 tokens).
2. **ASR is quality-sensitive in a way text chat isn't.** A wrong logit in a chat reply gets paraphrased away; a wrong logit in ASR is a transcript word error that compounds into WER. Qwen has not published WER numbers for any quantized variant, so adopting one would mean throwing away the published 2.11/4.55 LibriSpeech baseline with no replacement evidence.
3. **No MLX/GGUF port exists yet.** The model is ~3 months old. Only blessed paths are vLLM (CUDA) and transformers (CUDA-favored, MPS/CPU possible). Building an MLX port is a separate research project, not a deployment task.

**Decision: deploy `Qwen/Qwen3-ASR-1.7B` in bf16, transformers backend, MPS device.**

## Server fit — no existing server speaks audio

| Server | Verdict | Reason |
|:--|:--|:--|
| `vllm-mlx` | ❌ | The MLX fork. The `qwen-asr[vllm]` path expects CUDA-vLLM audio kernels; the `qwen3_omni` audio frontend isn't registered in vllm-mlx 0.2.5 on Mac Studio. |
| `lm-studio` | ❌ | Chat/tool-call only. No audio model support. |
| `mlx-openai-server` / `oMLX` / `vmlx` / `dflash-mlx` / `llama-cpp-turboquant` | ❌ | All text-only completion paths. No `/v1/audio/transcriptions` endpoint on any of them. |
| `qwen-asr-serve` (CLI bundled with `qwen-asr` package) | ❌ on M3 Ultra | Wraps CUDA-vLLM. Won't start without an NVIDIA GPU. |
| **Dedicated `~/qwen-asr-env/` venv, Python API** | ✅ | Only working path on Apple Silicon today. |

**Decision: dedicated venv, no port-bound daemon.** Clients invoke the Python API directly (or `scp` clips and run `bench_asr_*.py`). The closest structural sibling in this lab is the dflash-mlx sidecar — own venv, own purpose — but unlike dflash-mlx there's no LAN-reachable port for now.

## Deploy recipe — 1.7B on M3 Ultra MPS

Hygiene: no Event-4 server kill needed. Qwen3-ASR doesn't compete with port 8000 / 1234 / 8098 / 8099. Deploy alongside whatever chat server is current.

```bash
# 1. Build the venv (Python 3.12 — qwen-asr declares <3.14, and brew has 3.11/3.12/3.14).
ssh macstudio "/opt/homebrew/bin/python3.12 -m venv ~/qwen-asr-env && \
  ~/qwen-asr-env/bin/pip install -U pip wheel && \
  ~/qwen-asr-env/bin/pip install qwen-asr"

# 2. Smoke test (downloads the 4.7 GB checkpoint on first run).
scp scripts/bench/bench_asr_smoke.py macstudio:/tmp/
ssh macstudio "~/qwen-asr-env/bin/python /tmp/bench_asr_smoke.py"

# 3. RTF benchmark (3 warm timed passes).
scp scripts/bench/bench_asr_rtf.py macstudio:/tmp/
ssh macstudio "~/qwen-asr-env/bin/python /tmp/bench_asr_rtf.py"
scp macstudio:/tmp/qwen_asr_rtf.json docs/models/benchmarks/qwen3-asr-1.7b/
```

The pip resolve pulls torch 2.11.0 + transformers 4.57.6 + librosa + soundfile + the `qwen-asr` 0.0.6 package. No flash-attn, no vllm extra. Clean install on a stock Homebrew Python.

## Smoke results

`Qwen/Qwen3-ASR-1.7B`, bf16, MPS, against Qwen's official `asr_en.wav` (15.05 s mono 48 kHz English):

```
[smoke] device=mps torch=2.11.0
[smoke] model loaded in 42.0s        # cold (includes 4.7 GB download)
[smoke] WARM lang='English' t=18.36s  # cold transcription incl. MPS shader compile
[smoke] TIMED lang='English' t=3.19s  # second pass, warm
text="Hmm. Oh yeah, yeah. He wasn't even that big when I started listening to him,
but and his solo music didn't do overly well, but he did very well when he started
writing for other people."
```

Auto-detect picked `English` correctly. Transcript matches the reference clip fully. No FlashAttention warnings (FlashAttention isn't installed; transformers uses the SDPA path).

## RTF benchmark

Three warm timed passes after the first warm-up burns in MPS shaders. Same 15.05-second clip, `language="English"` to bypass auto-detect overhead.

| Pass | Wall time | RTF |
|:--|:--|:--|
| 1 | 0.790 s | 19.06× |
| 2 | 0.788 s | 19.10× |
| 3 | 0.791 s | 19.03× |
| **avg** | **0.790 s** | **19.06×** |

- Model load on warm cache: 3.2 s
- Peak Python RSS: 1.1 GB (model weights live in MPS unified memory, not counted)
- Disk: 4.4 GB at `~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-1.7B`

vs Qwen's published H100 RTFx of 147.93: M3 Ultra MPS lands at ~13 % of H100 throughput on a single-clip path. Still 19× realtime — a 1-hour podcast transcribes in ~3 min. Batching (`max_inference_batch_size=8` is set; not exercised in this run) could close the gap on multi-clip workloads.

Raw: [`docs/models/benchmarks/qwen3-asr-1.7b/rtf-mps.json`](../benchmarks/qwen3-asr-1.7b/rtf-mps.json).

## Caveats

- **Streaming is vLLM-only** (= CUDA-only). Not available on MPS. Real-time microphone transcription needs a different path on Apple Silicon.
- **5-minute audio cap per call.** Longer files must be chunked client-side; the `Qwen3-ForcedAligner-0.6B` companion handles per-segment timestamping if needed.
- **No `/v1/audio/transcriptions` endpoint.** Unlike Whisper-compatible servers, Qwen3-ASR on MPS exposes only the Python API. A FastAPI wrapper would close the gap if a LAN-reachable transcription endpoint becomes useful.
- **`device_map="cuda:0"` from the official docs does not apply.** Pass `device_map="mps"` instead. The first call after `from_pretrained()` is slow (MPS shader compile, ~18 s on a 15 s clip); from the second call onward the warm path is sub-second.

## See also

- [Server runbook: `docs/servers/qwen-asr/summary.md`](../../servers/qwen-asr/summary.md) — install, run, health check
- [Qwen3-ASR-1.7B card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) · [Qwen3-ASR-0.6B card](https://huggingface.co/Qwen/Qwen3-ASR-0.6B) · [Qwen blog](https://qwen.ai/blog?id=qwen3asr)
- [`qwen-asr` PyPI](https://pypi.org/project/qwen-asr/) (0.0.6, 2026-01-30)
- [open-asr-leaderboard](https://huggingface.co/spaces/hf-audio/open_asr_leaderboard) — H100 RTFx baselines
