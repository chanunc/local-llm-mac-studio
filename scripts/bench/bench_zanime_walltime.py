#!/usr/bin/env python3
"""ComfyUI Z-Anime wall-time benchmark.

Drives ComfyUI's `/prompt` HTTP API to time txt2img wall clock for the two
Z-Anime AIO BF16 checkpoint variants on the Mac Studio M3 Ultra:

  - Distill-4-step AIO BF16 — 4 steps, CFG 1.0  (fast iteration)
  - Base       AIO BF16     — 28 steps, CFG 4.0 (best quality)

Posts an 8-node API workflow per generation, polls `/history/<id>` until the
prompt finishes, captures wall-clock means over N runs (default 5). One warm-up
generation per variant is run and discarded before timing — the AIO checkpoint
is ~19 GiB and first load to MPS dominates the first sample.

Usage:
  scripts/bench/bench_zanime_walltime.py [--host URL] [--runs N] [--width W]
                                         [--height H] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid


def workflow(ckpt: str, steps: int, cfg: float, width: int, height: int,
             seed: int, prompt: str, negative: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.5}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": prompt}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["2", 0], "positive": ["3", 0], "negative": ["4", 0],
            "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": "euler", "scheduler": "beta", "denoise": 1.0,
        }},
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage",
              "inputs": {"images": ["7", 0], "filename_prefix": "zanime-bench"}},
    }


def post(host: str, prompt_obj: dict) -> str:
    client_id = str(uuid.uuid4())
    body = json.dumps({"prompt": prompt_obj, "client_id": client_id}).encode()
    req = urllib.request.Request(f"{host}/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"POST /prompt failed: {e}\n{e.read().decode(errors='replace')}\n")
        raise
    return json.loads(resp.read())["prompt_id"]


def wait(host: str, prompt_id: str, timeout: float = 600.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = json.loads(urllib.request.urlopen(
                f"{host}/history/{prompt_id}", timeout=10).read())
        except urllib.error.URLError:
            time.sleep(0.5)
            continue
        if prompt_id in data and data[prompt_id].get("status", {}).get("completed"):
            return data[prompt_id]
        time.sleep(0.5)
    raise TimeoutError(f"prompt {prompt_id} did not complete in {timeout}s")


def run_variant(host: str, label: str, ckpt: str, steps: int, cfg: float,
                width: int, height: int, runs: int, prompt: str, negative: str) -> dict:
    print(f"\n=== {label} :: {ckpt} ({steps} steps, CFG {cfg}, {width}x{height}) ===")
    print("  warm-up (excluded from mean) ...", flush=True)
    t0 = time.time()
    wait(host, post(host, workflow(ckpt, steps, cfg, width, height, 999, prompt, negative)))
    print(f"  warm-up: {time.time() - t0:.2f}s")

    times: list[float] = []
    for i in range(runs):
        seed = 1000 + i
        t0 = time.time()
        wait(host, post(host, workflow(ckpt, steps, cfg, width, height, seed, prompt, negative)))
        dt = time.time() - t0
        print(f"  run {i + 1}/{runs}: {dt:.2f}s  (seed={seed})", flush=True)
        times.append(dt)

    return {
        "label": label, "ckpt": ckpt, "steps": steps, "cfg": cfg,
        "width": width, "height": height, "runs": runs, "times": times,
        "mean": statistics.mean(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0.0,
        "min": min(times), "max": max(times),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="http://192.168.31.4:8188")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--out", default="/tmp/zanime-walltime.json")
    ap.add_argument("--prompt", default=("anime girl in a flower field, soft lighting, "
                                          "vibrant colors, masterpiece, highly detailed"))
    ap.add_argument("--negative", default=("blurry, low-quality, noisy, distorted, "
                                            "bad anatomy, deformed hands, extra fingers"))
    ap.add_argument("--skip-base", action="store_true",
                    help="Skip the Base BF16 variant (only run Distill-4-step)")
    args = ap.parse_args()

    results = {
        "host": args.host, "width": args.width, "height": args.height, "runs": args.runs,
        "prompt": args.prompt, "negative": args.negative,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "variants": [],
    }
    results["variants"].append(run_variant(
        args.host, "distill-4-step", "z-anime-distill-4step-aio-bf16.safetensors",
        4, 1.0, args.width, args.height, args.runs, args.prompt, args.negative))
    if not args.skip_base:
        results["variants"].append(run_variant(
            args.host, "base-bf16", "z-anime-base-aio-bf16.safetensors",
            28, 4.0, args.width, args.height, args.runs, args.prompt, args.negative))

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {args.out}")
    print(f"\n{'variant':20s}  {'mean':>7s}  {'min':>7s}  {'max':>7s}  {'stdev':>6s}")
    for v in results["variants"]:
        print(f"{v['label']:20s}  {v['mean']:6.2f}s  {v['min']:6.2f}s  "
              f"{v['max']:6.2f}s  {v['stdev']:5.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
