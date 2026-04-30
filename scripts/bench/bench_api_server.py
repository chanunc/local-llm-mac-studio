#!/usr/bin/env python3
"""Benchmark a chat-completions server via streaming SSE.

Measures TTFT, prefill tok/s, and gen tok/s at multiple context lengths.
Matches the methodology used in docs/models/benchmarks/model-benchmark-api-server.md
(streaming /v1/chat/completions, 50 generated tokens, temperature 0.0,
1 cold + warm runs per context, median reported).
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone


def make_padding(tokens):
    # ~0.75 token per word for english; build a deterministic filler that
    # the tokenizer compresses predictably. "Hello world. " ~= 3 tokens.
    word = "Hello world. "
    return word * (tokens // 3 + 1)


def probe_prompt_tokens(base_url, model, prompt, api_key=None, timeout=600):
    """Non-streaming probe to capture actual prompt_tokens from server usage block.

    Some servers (vllm-mlx) return prompt_tokens=0 in streaming SSE chunks; the
    non-streaming path reports it correctly.
    """
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1,
        "temperature": 0.0,
        "stream": False,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base_url}/chat/completions", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return (data.get("usage") or {}).get("prompt_tokens", 0)


def stream_request(base_url, model, prompt, max_tokens, api_key=None, timeout=600):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }).encode()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(f"{base_url}/chat/completions", data=body, headers=headers, method="POST")

    t0 = time.perf_counter()
    ttft = None
    n_tokens = 0
    usage = None

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            if evt.get("usage"):
                usage = evt["usage"]
            for choice in evt.get("choices", []):
                delta = choice.get("delta", {})
                if delta.get("content") or delta.get("reasoning_content"):
                    if ttft is None:
                        ttft = time.perf_counter() - t0
                    n_tokens += 1

    total = time.perf_counter() - t0
    return {"ttft_s": ttft, "total_s": total, "delta_tokens": n_tokens, "usage": usage}


def median(xs):
    return round(statistics.median(xs), 3) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="e.g. http://10.0.0.5:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--contexts", default="512,4096,8192,32768,65536",
                    help="Comma-separated prompt context lengths in tokens")
    ap.add_argument("--max-tokens", type=int, default=50)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    contexts = [int(x) for x in args.contexts.split(",")]
    out = {
        "benchmark": "api-server-streaming",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "max_tokens": args.max_tokens,
            "warmup": args.warmup,
            "runs": args.runs,
            "contexts": contexts,
        },
        "results": {},
    }

    for ctx in contexts:
        prompt = make_padding(ctx) + "\n\nReply with exactly 50 short tokens of filler text."
        print(f"\n=== Context ~{ctx} tokens ===", file=sys.stderr)

        actual_input = probe_prompt_tokens(args.base_url, args.model, prompt, args.api_key)
        print(f"  probe: prompt_tokens={actual_input}", file=sys.stderr)

        for w in range(args.warmup):
            print(f"  warmup {w+1}/{args.warmup}...", file=sys.stderr, end=" ", flush=True)
            r = stream_request(args.base_url, args.model, prompt, args.max_tokens, args.api_key)
            print(f"ttft={r['ttft_s']:.2f}s total={r['total_s']:.2f}s tok={r['delta_tokens']}", file=sys.stderr)

        runs = []
        for i in range(args.runs):
            print(f"  run {i+1}/{args.runs}...", file=sys.stderr, end=" ", flush=True)
            r = stream_request(args.base_url, args.model, prompt, args.max_tokens, args.api_key)
            usage = r["usage"] or {}
            input_tokens = usage.get("prompt_tokens") or actual_input
            output_tokens = usage.get("completion_tokens") or r["delta_tokens"]
            ttft = r["ttft_s"] or 0.0
            gen_time = max(r["total_s"] - ttft, 1e-6)
            gen_tps = output_tokens / gen_time if output_tokens else 0.0
            prefill_tps = input_tokens / ttft if ttft and input_tokens else 0.0
            runs.append({
                "ttft_s": round(ttft, 3),
                "total_s": round(r["total_s"], 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "gen_tps": round(gen_tps, 2),
                "prefill_tps": round(prefill_tps, 1),
            })
            print(f"ttft={ttft:.2f}s gen={gen_tps:.1f} tok/s prefill={prefill_tps:.0f} tok/s in={input_tokens}", file=sys.stderr)

        out["results"][str(ctx)] = {
            "runs": runs,
            "median_ttft_s": median([r["ttft_s"] for r in runs]),
            "median_gen_tps": median([r["gen_tps"] for r in runs]),
            "median_prefill_tps": median([r["prefill_tps"] for r in runs]),
            "input_tokens": runs[0]["input_tokens"] if runs else None,
            "output_tokens": runs[0]["output_tokens"] if runs else None,
        }

    text = json.dumps(out, indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(text + "\n")
        print(f"\nSaved: {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
