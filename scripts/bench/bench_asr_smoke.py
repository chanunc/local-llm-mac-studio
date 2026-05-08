"""Qwen3-ASR-1.7B smoke test on M3 Ultra MPS.

Downloads the model on first run (~4.7 GB), transcribes the official
English sample, prints language ID + transcript + wall time.
"""
import sys
import time
import torch
from qwen_asr import Qwen3ASRModel

device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"[smoke] device={device} torch={torch.__version__}", flush=True)

t0 = time.time()
model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-1.7B",
    dtype=torch.bfloat16,
    device_map=device,
    max_inference_batch_size=8,
    max_new_tokens=256,
)
t_load = time.time() - t0
print(f"[smoke] model loaded in {t_load:.1f}s", flush=True)

clip_url = "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-ASR-Repo/asr_en.wav"

# Warm + 1 timed pass
print("[smoke] warm pass…", flush=True)
t1 = time.time()
results = model.transcribe(audio=clip_url, language=None)
t_warm = time.time() - t1
r = results[0]
print(f"[smoke] WARM lang={r.language!r} t={t_warm:.2f}s text={r.text!r}", flush=True)

print("[smoke] timed pass…", flush=True)
t2 = time.time()
results = model.transcribe(audio=clip_url, language=None)
t_timed = time.time() - t2
r = results[0]
print(f"[smoke] TIMED lang={r.language!r} t={t_timed:.2f}s text={r.text!r}", flush=True)
print(f"[smoke] DONE load={t_load:.1f}s warm={t_warm:.2f}s timed={t_timed:.2f}s", flush=True)
