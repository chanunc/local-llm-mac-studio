"""Qwen3-ASR-1.7B RTF benchmark on M3 Ultra MPS.

Measures Real-Time Factor (RTF) = audio_seconds / wall_seconds over 3 warm
passes against the official asr_en.wav clip. Captures peak resident memory
and writes the result to a JSON file.

RTF > 1.0 means faster than realtime; the official open-asr-leaderboard
RTFx of 147.93 was measured on H100. M3 Ultra MPS is the comparison floor.
"""
import json
import os
import resource
import sys
import time
import urllib.request
import wave
from pathlib import Path

import torch
from qwen_asr import Qwen3ASRModel

MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
CLIP_URL = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_en.wav"
CLIP_LOCAL = Path("/tmp/asr_en.wav")
OUT = Path("/tmp/qwen_asr_rtf.json")

# Cache the clip locally so transcribe isn't paying re-download.
if not CLIP_LOCAL.exists():
    print(f"[rtf] downloading clip to {CLIP_LOCAL}", flush=True)
    urllib.request.urlretrieve(CLIP_URL, CLIP_LOCAL)

with wave.open(str(CLIP_LOCAL), "rb") as w:
    n_frames = w.getnframes()
    rate = w.getframerate()
    audio_seconds = n_frames / rate
    n_channels = w.getnchannels()
    sampwidth = w.getsampwidth()
print(f"[rtf] clip {CLIP_LOCAL} dur={audio_seconds:.2f}s rate={rate}Hz ch={n_channels} sampwidth={sampwidth}", flush=True)

device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"[rtf] device={device} torch={torch.__version__}", flush=True)

t0 = time.time()
model = Qwen3ASRModel.from_pretrained(
    MODEL_ID, dtype=torch.bfloat16, device_map=device,
    max_inference_batch_size=8, max_new_tokens=256,
)
t_load = time.time() - t0
print(f"[rtf] model loaded in {t_load:.1f}s", flush=True)

# Warm-up pass (MPS shader compile etc.) — discard timing.
print("[rtf] warm-up pass…", flush=True)
t = time.time()
warmup = model.transcribe(audio=str(CLIP_LOCAL), language="English")
print(f"[rtf] warm-up done in {time.time()-t:.2f}s text_len={len(warmup[0].text)}", flush=True)

times = []
for i in range(3):
    t = time.time()
    res = model.transcribe(audio=str(CLIP_LOCAL), language="English")
    dt = time.time() - t
    times.append(dt)
    rtf = audio_seconds / dt
    print(f"[rtf] pass {i+1}/3 t={dt:.2f}s rtf={rtf:.2f}x text={res[0].text[:80]!r}", flush=True)

# Peak RSS in KB on Linux, bytes on macOS.
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
peak_gb = peak / (1024**3) if sys.platform == "darwin" else peak / (1024**2)

avg = sum(times) / len(times)
out = {
    "model": MODEL_ID,
    "device": device,
    "torch": torch.__version__,
    "clip": str(CLIP_LOCAL),
    "audio_seconds": round(audio_seconds, 3),
    "load_seconds": round(t_load, 2),
    "passes_seconds": [round(x, 3) for x in times],
    "avg_seconds": round(avg, 3),
    "rtf_min": round(audio_seconds / max(times), 2),
    "rtf_max": round(audio_seconds / min(times), 2),
    "rtf_avg": round(audio_seconds / avg, 2),
    "peak_rss_gb": round(peak_gb, 2),
    "transcript": res[0].text,
}
OUT.write_text(json.dumps(out, indent=2))
print(f"[rtf] DONE avg={avg:.2f}s rtf_avg={out['rtf_avg']}x peak_rss={out['peak_rss_gb']}GB → {OUT}", flush=True)
