#!/usr/bin/env python3
"""API-level tool-call harness for OpenAI-compatible servers.

Runs 5 single-call scenarios + a 3-turn agentic loop against
/v1/chat/completions (non-streaming, temperature 0). Output JSON
matches docs/models/benchmarks/qwen36-27b-jang4m/api-tool-test.json.

Usage:
  ./bench_api_tool_call.py \
    --base-url http://<MAC_STUDIO_IP>:8000/v1 \
    --model JANGQ-AI/Qwen3.6-27B-JANG_4M \
    --output docs/models/benchmarks/qwen36-27b-jang4m/api-tool-test.json
"""

import argparse
import json
import sys
import time
import urllib.request


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command and return stdout.",
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web and return results.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List entries in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


SINGLE_SCENARIOS = [
    ("Single tool (file read)", "Read the file /tmp/notes.txt and tell me its contents"),
    ("Single tool (command)", "Run uptime to check system status"),
    ("Multi-tool (search + read)", "Search the web for 'openai api docs' then read /tmp/notes.txt"),
    ("Multi-tool (list + read + write)", "List /tmp, then read the first .txt file, then write a summary back to /tmp/summary.txt"),
    ("Agentic reasoning", "Find the largest file in /tmp"),
]


def chat(base_url, model, messages, api_key=None, max_tokens=1024, timeout=600):
    body = json.dumps({
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    dt = time.perf_counter() - t0
    return data, dt


def extract(resp):
    choice = resp["choices"][0]
    msg = choice.get("message") or {}
    finish = choice.get("finish_reason")
    tcs = msg.get("tool_calls") or []
    names = [tc.get("function", {}).get("name") for tc in tcs]
    args = [tc.get("function", {}).get("arguments") for tc in tcs]
    usage = resp.get("usage") or {}
    return {
        "finish_reason": finish,
        "tool_calls": names,
        "tool_args": args,
        "output_tokens": usage.get("completion_tokens", 0),
        "content": msg.get("content"),
    }


def fmt_rate(tokens, secs):
    return round(tokens / secs, 1) if secs > 0 and tokens else 0.0


def run_single(base_url, model, api_key):
    out = []
    for scenario, prompt in SINGLE_SCENARIOS:
        print(f"  • {scenario} ... ", end="", flush=True)
        try:
            resp, dt = chat(base_url, model, [{"role": "user", "content": prompt}], api_key=api_key)
        except Exception as e:
            print(f"ERROR: {e}")
            out.append({
                "scenario": scenario,
                "prompt": prompt,
                "error": str(e),
            })
            continue
        info = extract(resp)
        rec = {
            "scenario": scenario,
            "prompt": prompt,
            "time_s": round(dt, 2),
            "output_tokens": info["output_tokens"],
            "rate_tps": fmt_rate(info["output_tokens"], dt),
            "finish_reason": info["finish_reason"],
            "tool_calls": info["tool_calls"],
            "tool_args": info["tool_args"],
        }
        out.append(rec)
        print(f"{dt:.2f}s, finish={info['finish_reason']}, tools={info['tool_calls']}")
    return out


def run_multi_turn(base_url, model, api_key):
    """3-turn read→write→summary loop with simulated tool results."""
    print("  • Multi-turn loop (read config → write port 8080 → summary)")
    sysmsg = {
        "role": "system",
        "content": "You are a config-fix assistant. Read /tmp/app/config.json, set port=8080, write it back, then summarize.",
    }
    user = {
        "role": "user",
        "content": "Read /tmp/app/config.json, change port to 8080, write back",
    }
    messages = [sysmsg, user]
    turns = []
    total_t = 0.0

    # Turn 1: expect read_file
    resp, dt = chat(base_url, model, messages, api_key=api_key)
    info = extract(resp)
    total_t += dt
    turns.append({
        "turn": 1,
        "time_s": round(dt, 2),
        "output_tokens": info["output_tokens"],
        "finish_reason": info["finish_reason"],
        "tool_calls": info["tool_calls"],
    })
    print(f"    turn 1: {dt:.2f}s, finish={info['finish_reason']}, tools={info['tool_calls']}")

    # Append assistant turn + simulated tool result
    asst1 = resp["choices"][0]["message"]
    messages.append(asst1)
    tcs = asst1.get("tool_calls") or []
    if not tcs:
        return {"turns": turns, "total_turns": len(turns), "total_time_s": round(total_t, 2),
                "aborted": "no tool call on turn 1"}
    messages.append({
        "role": "tool",
        "tool_call_id": tcs[0].get("id", "call_1"),
        "name": tcs[0]["function"]["name"],
        "content": json.dumps({"host": "0.0.0.0", "port": 8000, "debug": True}),
    })

    # Turn 2: expect write_file
    resp, dt = chat(base_url, model, messages, api_key=api_key)
    info = extract(resp)
    total_t += dt
    turns.append({
        "turn": 2,
        "time_s": round(dt, 2),
        "output_tokens": info["output_tokens"],
        "finish_reason": info["finish_reason"],
        "tool_calls": info["tool_calls"],
    })
    print(f"    turn 2: {dt:.2f}s, finish={info['finish_reason']}, tools={info['tool_calls']}")

    asst2 = resp["choices"][0]["message"]
    messages.append(asst2)
    tcs2 = asst2.get("tool_calls") or []
    if not tcs2:
        return {"turns": turns, "total_turns": len(turns), "total_time_s": round(total_t, 2),
                "aborted": "no tool call on turn 2"}
    messages.append({
        "role": "tool",
        "tool_call_id": tcs2[0].get("id", "call_2"),
        "name": tcs2[0]["function"]["name"],
        "content": json.dumps({"ok": True, "bytes_written": 64}),
    })

    # Turn 3: expect natural language summary (stop)
    resp, dt = chat(base_url, model, messages, api_key=api_key)
    info = extract(resp)
    total_t += dt
    turns.append({
        "turn": 3,
        "time_s": round(dt, 2),
        "output_tokens": info["output_tokens"],
        "finish_reason": info["finish_reason"],
        "tool_calls": info["tool_calls"],
    })
    print(f"    turn 3: {dt:.2f}s, finish={info['finish_reason']}, tools={info['tool_calls']}")

    return {
        "turns": turns,
        "total_turns": len(turns),
        "total_time_s": round(total_t, 2),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--api-key", default=None)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    print(f"Model:    {args.model}")
    print(f"Base URL: {args.base_url}")
    print()
    print("[1/2] Single-call scenarios")
    singles = run_single(args.base_url, args.model, args.api_key)
    print()
    print("[2/2] Multi-turn agentic loop")
    multi = run_multi_turn(args.base_url, args.model, args.api_key)

    payload = {
        "model": args.model,
        "base_url": args.base_url,
        "single_calls": singles,
        "multi_turn": multi.get("turns", []),
        "total_turns": multi.get("total_turns", 0),
        "total_time_s": multi.get("total_time_s", 0.0),
    }
    if "aborted" in multi:
        payload["aborted"] = multi["aborted"]

    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print()
    print(f"Wrote {args.output}")
    pass_count = sum(1 for s in singles if s.get("finish_reason") == "tool_calls")
    print(f"Single-call pass rate: {pass_count}/{len(singles)}")
    print(f"Multi-turn total: {multi.get('total_turns', 0)} turns, {multi.get('total_time_s', 0)}s")


if __name__ == "__main__":
    main()
