#!/usr/bin/env python3
"""Tool-call harness for OpenAI-compatible servers and native LiteRT-LM.

Runs 5 single-call scenarios + a 3-turn agentic loop against
/v1/chat/completions (non-streaming, temperature 0) by default.
Native LiteRT-LM mode uses the Python API and records Python tool
invocations, because the OpenAI finish_reason/tool_calls fields do not
exist on that path.

Usage:
  ./bench_api_tool_call.py \
    --base-url http://<MAC_STUDIO_IP>:8000/v1 \
    --model JANGQ-AI/Qwen3.6-27B-JANG_4M \
    --output docs/models/benchmarks/logs/qwen36-27b-jang4m/api-tool-test.json

  ./bench_api_tool_call.py \
    --mode litert-native \
    --native-model-path ~/.litert-lm/models/gemma4-e4b/model.litertlm \
    --model gemma4-e4b \
    --output docs/models/benchmarks/logs/gemma4-e4b-litert-lm/native-tool-test.json
"""

import argparse
import json
import os
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


FAKE_FILES = {
    "/tmp/notes.txt": "Benchmark note: LiteRT-LM native tool call smoke test.",
    "/tmp/app/config.json": json.dumps({"host": "0.0.0.0", "port": 8000, "debug": True}),
    "/tmp/alpha.txt": "alpha",
    "/tmp/beta.txt": "beta",
}


class ToolRecorder:
    """In-memory tool sandbox used by native LiteRT-LM mode."""

    def __init__(self):
        self.calls = []
        self.files = dict(FAKE_FILES)

    def _record(self, name, arguments, response):
        self.calls.append({
            "name": name,
            "arguments": arguments,
            "response": response,
        })
        return response

    def read_file(self, path: str) -> str:
        """Read the contents of a file from disk.

        Args:
            path: Absolute path to the file.
        """
        return self._record(
            "read_file",
            {"path": path},
            self.files.get(path, f"File not found in benchmark sandbox: {path}"),
        )

    def write_file(self, path: str, content: str) -> str:
        """Write content to a file on disk.

        Args:
            path: Absolute path to write.
            content: Content to write.
        """
        self.files[path] = content
        return self._record(
            "write_file",
            {"path": path, "content": content},
            json.dumps({"ok": True, "bytes_written": len(content)}),
        )

    def run_command(self, cmd: str) -> str:
        """Run a shell command and return stdout.

        Args:
            cmd: Command to run.
        """
        return self._record(
            "run_command",
            {"cmd": cmd},
            "13:37 up 10 days, 4 users, load averages: 1.23 1.10 0.98",
        )

    def search_web(self, query: str) -> str:
        """Search the web and return results.

        Args:
            query: Search query.
        """
        return self._record(
            "search_web",
            {"query": query},
            json.dumps([
                {"title": "OpenAI API documentation", "url": "https://platform.openai.com/docs"},
                {"title": "OpenAI API reference", "url": "https://platform.openai.com/docs/api-reference"},
            ]),
        )

    def list_directory(self, path: str) -> str:
        """List entries in a directory.

        Args:
            path: Absolute directory path.
        """
        entries = ["notes.txt", "alpha.txt", "beta.txt", "app"]
        return self._record("list_directory", {"path": path}, json.dumps(entries))

    @property
    def tools(self):
        return [
            self.read_file,
            self.write_file,
            self.run_command,
            self.search_web,
            self.list_directory,
        ]


def chat(base_url, model, messages, api_key=None, max_tokens=1024, timeout=600, chat_template_kwargs=None):
    body_payload = {
        "model": model,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False,
    }
    if chat_template_kwargs:
        body_payload["chat_template_kwargs"] = chat_template_kwargs
    body = json.dumps(body_payload).encode()
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


def litert_response_text(response):
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return str(response)
    parts = []
    for item in response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "".join(parts)


def import_litert_lm():
    try:
        import litert_lm  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "Native LiteRT-LM mode requires the Python API package. "
            "Install it on the runner with: pip install litert-lm-api"
        ) from e
    return litert_lm


def litert_backend(litert_lm, name):
    backend = name.lower()
    if backend == "cpu":
        return litert_lm.Backend.CPU()
    if backend == "gpu":
        return litert_lm.Backend.GPU()
    if backend == "npu":
        return litert_lm.Backend.NPU()
    raise ValueError(f"Unsupported LiteRT-LM backend: {name}")


def create_litert_conversation(engine, recorder, system_instruction=None):
    kwargs = {"tools": recorder.tools}
    if system_instruction:
        # LiteRT-LM exposes Message.system in the documented Python API.
        litert_lm = import_litert_lm()
        kwargs["messages"] = [litert_lm.Message.system(system_instruction)]
    return engine.create_conversation(**kwargs)


def run_single(base_url, model, api_key, chat_template_kwargs=None):
    out = []
    for scenario, prompt in SINGLE_SCENARIOS:
        print(f"  • {scenario} ... ", end="", flush=True)
        try:
            resp, dt = chat(
                base_url,
                model,
                [{"role": "user", "content": prompt}],
                api_key=api_key,
                chat_template_kwargs=chat_template_kwargs,
            )
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


def run_multi_turn(base_url, model, api_key, chat_template_kwargs=None):
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
    resp, dt = chat(base_url, model, messages, api_key=api_key, chat_template_kwargs=chat_template_kwargs)
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
    resp, dt = chat(base_url, model, messages, api_key=api_key, chat_template_kwargs=chat_template_kwargs)
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
    resp, dt = chat(base_url, model, messages, api_key=api_key, chat_template_kwargs=chat_template_kwargs)
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


def run_litert_single(engine):
    out = []
    for scenario, prompt in SINGLE_SCENARIOS:
        print(f"  • {scenario} ... ", end="", flush=True)
        recorder = ToolRecorder()
        try:
            with create_litert_conversation(engine, recorder) as conversation:
                t0 = time.perf_counter()
                response = conversation.send_message(prompt)
                dt = time.perf_counter() - t0
        except Exception as e:
            print(f"ERROR: {e}")
            out.append({
                "scenario": scenario,
                "prompt": prompt,
                "error": str(e),
            })
            continue
        names = [call["name"] for call in recorder.calls]
        args = [json.dumps(call["arguments"]) for call in recorder.calls]
        rec = {
            "scenario": scenario,
            "prompt": prompt,
            "time_s": round(dt, 2),
            "output_tokens": 0,
            "rate_tps": 0.0,
            "finish_reason": "native_response",
            "tool_calls": names,
            "tool_args": args,
            "content": litert_response_text(response),
        }
        out.append(rec)
        print(f"{dt:.2f}s, native tools={names}")
    return out


def run_litert_multi_turn(engine):
    print("  • Native multi-turn loop (read config → write port 8080 → summary)")
    recorder = ToolRecorder()
    system_instruction = (
        "You are a config-fix assistant. Read /tmp/app/config.json, set port=8080, "
        "write it back, then summarize."
    )
    prompt = "Read /tmp/app/config.json, change port to 8080, write back"
    try:
        with create_litert_conversation(engine, recorder, system_instruction) as conversation:
            t0 = time.perf_counter()
            response = conversation.send_message(prompt)
            dt = time.perf_counter() - t0
    except Exception as e:
        print(f"    native turn: ERROR: {e}")
        return {
            "turns": [{
                "turn": 1,
                "error": str(e),
                "tool_calls": [],
            }],
            "total_turns": 1,
            "total_time_s": 0.0,
            "aborted": str(e),
        }

    names = [call["name"] for call in recorder.calls]
    print(f"    native turn: {dt:.2f}s, tools={names}")
    return {
        "turns": [{
            "turn": 1,
            "time_s": round(dt, 2),
            "output_tokens": 0,
            "finish_reason": "native_response",
            "tool_calls": names,
            "content": litert_response_text(response),
        }],
        "total_turns": 1,
        "total_time_s": round(dt, 2),
    }


def run_litert_native(args):
    litert_lm = import_litert_lm()
    model_path = os.path.expanduser(args.native_model_path)
    if not os.path.exists(model_path):
        raise SystemExit(f"LiteRT-LM model path does not exist: {model_path}")

    print(f"Model:      {args.model}")
    print(f"Mode:       litert-native")
    print(f"Model path: {model_path}")
    print(f"Backend:    {args.native_backend}")
    print()

    engine_kwargs = {"backend": litert_backend(litert_lm, args.native_backend)}
    if args.native_cache_dir:
        engine_kwargs["cache_dir"] = os.path.expanduser(args.native_cache_dir)
    if args.enable_speculative_decoding:
        engine_kwargs["enable_speculative_decoding"] = True

    with litert_lm.Engine(model_path, **engine_kwargs) as engine:
        print("[1/2] Single-call scenarios")
        singles = run_litert_single(engine)
        print()
        print("[2/2] Native LiteRT-LM tool loop")
        multi = run_litert_multi_turn(engine)

    payload = {
        "benchmark": "api-tool-call",
        "mode": "litert-native",
        "model": args.model,
        "model_path": model_path,
        "backend": args.native_backend,
        "single_calls": singles,
        "multi_turn": multi.get("turns", []),
        "total_turns": multi.get("total_turns", 0),
        "total_time_s": multi.get("total_time_s", 0.0),
    }
    if "aborted" in multi:
        payload["aborted"] = multi["aborted"]
    return payload


def run_openai_http(args):
    print(f"Model:    {args.model}")
    print(f"Base URL: {args.base_url}")
    print(f"Mode:     openai-http")
    chat_template_kwargs = json.loads(args.chat_template_kwargs) if args.chat_template_kwargs else None
    print()
    print("[1/2] Single-call scenarios")
    singles = run_single(args.base_url, args.model, args.api_key, chat_template_kwargs=chat_template_kwargs)
    print()
    print("[2/2] Multi-turn agentic loop")
    multi = run_multi_turn(args.base_url, args.model, args.api_key, chat_template_kwargs=chat_template_kwargs)

    payload = {
        "benchmark": "api-tool-call",
        "mode": "openai-http",
        "model": args.model,
        "base_url": args.base_url,
        "single_calls": singles,
        "multi_turn": multi.get("turns", []),
        "total_turns": multi.get("total_turns", 0),
        "total_time_s": multi.get("total_time_s", 0.0),
    }
    if "aborted" in multi:
        payload["aborted"] = multi["aborted"]
    return payload


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["openai-http", "litert-native"], default="openai-http")
    p.add_argument("--base-url")
    p.add_argument("--model", required=True)
    p.add_argument("--api-key", default=None)
    p.add_argument("--chat-template-kwargs", default=None, help="JSON object passed through as OpenAI chat_template_kwargs")
    p.add_argument("--native-model-path", help="Path to a .litertlm bundle for --mode litert-native")
    p.add_argument("--native-backend", default="cpu", choices=["cpu", "gpu", "npu"])
    p.add_argument("--native-cache-dir", default=None)
    p.add_argument("--enable-speculative-decoding", action="store_true")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    if args.mode == "openai-http":
        if not args.base_url:
            p.error("--base-url is required for --mode openai-http")
        payload = run_openai_http(args)
    else:
        if not args.native_model_path:
            p.error("--native-model-path is required for --mode litert-native")
        payload = run_litert_native(args)

    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print()
    print(f"Wrote {args.output}")
    singles = payload["single_calls"]
    if payload["mode"] == "openai-http":
        pass_count = sum(1 for s in singles if s.get("finish_reason") == "tool_calls")
    else:
        pass_count = sum(1 for s in singles if s.get("tool_calls"))
    print(f"Single-call pass rate: {pass_count}/{len(singles)}")
    print(f"Multi-turn total: {payload.get('total_turns', 0)} turns, {payload.get('total_time_s', 0)}s")


if __name__ == "__main__":
    main()
