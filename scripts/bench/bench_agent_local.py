#!/usr/bin/env python3
"""In-process agent tool-call harness via gary149/llama-agent.

Runs 5 single-call scenarios + a 3-turn agentic loop against the
`llama-agent` CLI (https://github.com/gary149/llama-agent), which embeds
llama.cpp inference and the agent loop in one process — no OpenAI-
compatible server in the path.

Mode: resident-PTY. The model loads once, then each scenario runs as a
turn in the same TUI session, with /clear between scenarios to wipe
context. /stats captures per-turn token counts. Posix-only (uses pty,
select, os.fork via pty.fork). macOS / Linux.

Differences from bench_api_tool_call.py:
  * Tools execute for real (bash/read/write/edit/glob), not synthesized.
    A sandbox dir is created/torn down per scenario.
  * The 3-turn loop is one prompt; the agent runs read→edit→summary
    autonomously. We verify post-conditions on the sandbox files.

Tools available in llama-agent (vs bench_api_tool_call.py's stub list):
  bash, read, write, edit, glob, update_plan  (no search_web)

Prereqs:
  Pre-built binary from https://github.com/gary149/llama-agent/releases
  (the brew formula at b9121 fails to build — duplicate stb_image syms).

Usage:
  ./bench_agent_local.py \
    --bin ~/llama-agent-bin/llama-agent \
    --model ~/.lmstudio/models/unsloth/granite-4.1-30b-GGUF/granite-4.1-30b-Q8_0.gguf \
    --output docs/models/benchmarks/granite-4.1-30b-q8/agent-local.json
"""

import argparse
import json
import os
import pty
import re
import select
import shutil
import sys
import time
from pathlib import Path


# On macOS /tmp is a symlink to /private/tmp. llama-agent (b9121) compares
# file paths against its cwd literally, so a path under /tmp/... is flagged
# "external" even when cwd is /tmp/bench-llama-agent (cwd resolves to
# /private/tmp/bench-llama-agent at exec). --yolo does NOT auto-approve
# the external-file warning, so the run hangs on the permission box.
# Resolving the sandbox path to its realpath fixes both: prompts reference
# /private/tmp/... and the agent's in-tree check passes.
SANDBOX = Path(os.path.realpath("/tmp/bench-llama-agent"))
NOTES_TXT = SANDBOX / "notes.txt"
APP_DIR = SANDBOX / "app"
CONFIG_JSON = APP_DIR / "config.json"
SUMMARY_TXT = SANDBOX / "summary.txt"

NOTES_CONTENT = "alpha\nbravo\ncharlie\ndelta\n"
CONFIG_INITIAL = {"host": "0.0.0.0", "port": 8000, "debug": True}
CONFIG_TARGET_PORT = 8080


SINGLE_SCENARIOS = [
    (
        "Single tool (file read)",
        f"Read the file {NOTES_TXT} and tell me its contents",
        {"read"},
    ),
    (
        "Single tool (command)",
        "Run uptime to check system status",
        {"bash"},
    ),
    (
        "Multi-tool (grep + read)",
        f"Search for the string 'charlie' under {SANDBOX} and read the file you find",
        {"bash", "read", "glob"},
    ),
    (
        "Multi-tool (list + read + write)",
        f"List {SANDBOX}, read the first .txt file, then write a one-line "
        f"summary to {SUMMARY_TXT}",
        {"bash", "glob", "read", "write"},
    ),
    (
        "Agentic reasoning",
        f"Find the largest file under {SANDBOX} and report its name",
        {"bash", "glob", "read"},
    ),
]


MULTI_TURN_PROMPT = (
    f"Read {CONFIG_JSON}, change port to {CONFIG_TARGET_PORT}, "
    "write the modified config back to the same path, then summarize."
)


# Strip CSI / OSC / single-char escapes the TUI emits for spinners,
# colors, cursor moves. Does NOT strip the literal spinner glyphs
# ('|', '/', '-', '\') — they don't interfere with our markers.
ANSI_RE = re.compile(
    rb"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[=>()][0-9A-Za-z]?"
)
# llama-agent (b9121) renders tool calls as one of:
#   › read /path
#   › bash <cmd>
TOOL_LINE_RE = re.compile(
    r"^\s*[›>]\s+(bash|read|write|edit|glob|update_plan)\b",
    re.MULTILINE,
)
ITER_RE = re.compile(r"\[Completed in (\d+) iteration", re.IGNORECASE)
STATS_FIELDS = {
    "prompt_tokens": re.compile(r"Prompt tokens:\s*(\d+)"),
    "output_tokens": re.compile(r"Output tokens:\s*(\d+)"),
    "prompt_time_s": re.compile(r"Prompt time:\s*([\d.]+)s"),
    "gen_time_s":    re.compile(r"Gen time:\s*([\d.]+)s"),
    "avg_speed_tps": re.compile(r"Avg speed:\s*([\d.]+)\s*tok/s"),
}
COMPLETED_MARKER = "[Completed in"
READY_PROMPT_MARKER = "› "


def reset_sandbox():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    APP_DIR.mkdir(parents=True)
    NOTES_TXT.write_text(NOTES_CONTENT)
    CONFIG_JSON.write_text(json.dumps(CONFIG_INITIAL, indent=2))


def cleanup_sandbox():
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)


def strip_ansi(b: bytes) -> str:
    return ANSI_RE.sub(b"", b).decode("utf-8", errors="replace").replace("\r", "\n")


def parse_tools(text: str) -> list[str]:
    raw = [m.group(1).lower() for m in TOOL_LINE_RE.finditer(text)]
    out = []
    for t in raw:
        if not out or out[-1] != t:
            out.append(t)
    return out


def parse_iterations(text: str):
    m = ITER_RE.search(text)
    return int(m.group(1)) if m else None


def parse_stats(text: str):
    out = {}
    for key, rx in STATS_FIELDS.items():
        m = rx.search(text)
        if not m:
            out[key] = None
        elif key.endswith("_tokens"):
            out[key] = int(m.group(1))
        else:
            out[key] = float(m.group(1))
    if out["prompt_tokens"] is None and out["output_tokens"] is None:
        return None
    return out


class LlamaAgentSession:
    """Resident llama-agent process driven via PTY."""

    BANNER_MARKER = "mode       : YOLO"

    def __init__(self, bin_path: str, model: str, max_iter: int, load_timeout: int = 120):
        self.bin_path = bin_path
        self.model = model
        self.max_iter = max_iter
        self.load_timeout = load_timeout
        self.fd = None
        self.pid = None

    def _model_args(self):
        if Path(os.path.expanduser(self.model)).exists():
            return ["-m", os.path.expanduser(self.model)]
        return ["-hf", self.model]

    def __enter__(self):
        # Ensure SANDBOX exists before we fork — the child chdir's into it
        # so that all sandbox file paths are "inside" the agent's working
        # tree and --yolo can actually auto-approve them. Without this,
        # llama-agent flags external paths and pauses on a permission box
        # that --yolo does NOT bypass (build b9121 only suppresses
        # in-tree dangerous-op warnings).
        SANDBOX.mkdir(parents=True, exist_ok=True)
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(str(SANDBOX))
            os.environ["DYLD_LIBRARY_PATH"] = (
                str(Path(self.bin_path).resolve().parent)
                + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
            )
            os.environ["TERM"] = "xterm-256color"
            argv = [
                self.bin_path,
                *self._model_args(),
                "--yolo",
                "--max-iterations", str(self.max_iter),
            ]
            try:
                os.execv(self.bin_path, argv)
            except Exception as e:
                sys.stderr.write(f"exec failed: {e}\n")
                os._exit(127)
        self.pid = pid
        self.fd = fd
        # wait for banner so we know the model finished loading
        _, status = self._read_until(self.BANNER_MARKER, self.load_timeout)
        if status != "found":
            raise RuntimeError(f"llama-agent failed to start (status={status})")
        # After the banner, the agent draws a '›' input prompt. Drain the
        # PTY until that prompt has fully rendered AND the buffer goes
        # quiet for ~0.5s — only then is the agent actually ready to
        # receive the first user input. Without this, the very first
        # prompt sometimes lands in a half-rendered state and never
        # produces a [Completed in ...] marker.
        self._wait_for_idle_prompt(timeout=15)
        return self

    def _wait_for_idle_prompt(self, timeout: float, idle_window: float = 0.5):
        """Read until '›' prompt is drawn and PTY is quiet for idle_window."""
        t0 = time.time()
        last_byte = time.time()
        saw_prompt = False
        while time.time() - t0 < timeout:
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if self.fd in r:
                try:
                    chunk = os.read(self.fd, 65536)
                    if chunk:
                        last_byte = time.time()
                        if "› " in strip_ansi(chunk):
                            saw_prompt = True
                except OSError:
                    return
            elif saw_prompt and (time.time() - last_byte) > idle_window:
                return

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fd is not None:
                try:
                    os.write(self.fd, b"/exit\r")
                except OSError:
                    pass
                time.sleep(1)
        finally:
            if self.fd is not None:
                try: os.close(self.fd)
                except OSError: pass
            if self.pid is not None:
                try:
                    os.waitpid(self.pid, os.WNOHANG)
                except OSError:
                    pass

    def _read_until(self, markers, timeout: float):
        if isinstance(markers, str):
            markers = [markers]
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            r, _, _ = select.select([self.fd], [], [], 0.3)
            if self.fd in r:
                try:
                    chunk = os.read(self.fd, 65536)
                    if not chunk:
                        return buf, "eof"
                    buf += chunk
                    txt = strip_ansi(buf)
                    for m in markers:
                        if m in txt:
                            return buf, "found"
                except OSError:
                    return buf, "err"
        return buf, "timeout"

    def _drain(self, seconds: float) -> bytes:
        buf = b""
        t0 = time.time()
        while time.time() - t0 < seconds:
            r, _, _ = select.select([self.fd], [], [], 0.1)
            if self.fd in r:
                try:
                    chunk = os.read(self.fd, 65536)
                    if not chunk:
                        break
                    buf += chunk
                except OSError:
                    break
        return buf

    def run_turn(self, prompt: str, timeout: int):
        """Send prompt, return raw stdout bytes + wall-clock time.

        Wraps the prompt in bracketed-paste escapes (\\e[200~ ... \\e[201~)
        so the TUI's slash-command autocomplete does not trigger on every
        '/' and triple it (build b9121 reproducibly turns '/tmp' into
        '///tmp' without bracketed paste).
        """
        payload = b"\x1b[200~" + prompt.encode("utf-8") + b"\x1b[201~\r"
        os.write(self.fd, payload)
        t0 = time.perf_counter()
        buf, status = self._read_until(COMPLETED_MARKER, timeout)
        # drain a bit more to capture lines after the marker
        buf += self._drain(0.5)
        dt = time.perf_counter() - t0
        return strip_ansi(buf), dt, status

    def stats(self):
        os.write(self.fd, b"/stats\r")
        time.sleep(0.3)
        buf, _ = self._read_until("Avg speed", 8)
        buf += self._drain(0.5)
        return parse_stats(strip_ansi(buf))

    def clear(self):
        os.write(self.fd, b"/clear\r")
        buf, _ = self._read_until(["Conversation cleared", "› "], 5)
        self._drain(0.3)
        return buf


def run_single(sess: LlamaAgentSession, timeout: int, debug_log=None):
    out = []
    for scenario, prompt, expected_any in SINGLE_SCENARIOS:
        reset_sandbox()
        print(f"  • {scenario} ... ", end="", flush=True)
        text, dt, status = sess.run_turn(prompt, timeout)
        if debug_log:
            with open(debug_log, "a") as f:
                f.write(f"\n===== {scenario} =====\n{text}\n")
        tools = parse_tools(text)
        iters = parse_iterations(text)
        stats = sess.stats() or {}
        passed = bool(set(tools) & expected_any) and status == "found"
        rec = {
            "scenario": scenario,
            "prompt": prompt,
            "time_s": round(dt, 2),
            "iterations": iters,
            "prompt_tokens": stats.get("prompt_tokens"),
            "output_tokens": stats.get("output_tokens"),
            "prompt_time_s": stats.get("prompt_time_s"),
            "gen_time_s": stats.get("gen_time_s"),
            "avg_speed_tps": stats.get("avg_speed_tps"),
            "tool_sequence": tools,
            "expected_any_of": sorted(expected_any),
            "passed": passed,
            "status": status,
        }
        out.append(rec)
        st = "PASS" if passed else f"FAIL ({status})"
        speed = stats.get("avg_speed_tps")
        print(
            f"{dt:.2f}s tools={tools} iter={iters} "
            f"out_tok={stats.get('output_tokens')} "
            f"speed={speed} {st}"
        )
        sess.clear()
    return out


def run_multi_turn(sess: LlamaAgentSession, timeout: int, debug_log=None):
    reset_sandbox()
    print("  • Multi-turn agentic loop (read config → port=8080 → summarize)")
    text, dt, status = sess.run_turn(MULTI_TURN_PROMPT, timeout)
    if debug_log:
        with open(debug_log, "a") as f:
            f.write(f"\n===== multi-turn =====\n{text}\n")
    tools = parse_tools(text)
    iters = parse_iterations(text)
    stats = sess.stats() or {}

    config_after = None
    port_correct = False
    try:
        config_after = json.loads(CONFIG_JSON.read_text())
        port_correct = config_after.get("port") == CONFIG_TARGET_PORT
    except Exception:
        pass

    has_read = "read" in tools
    has_mutate = any(t in {"write", "edit"} for t in tools)
    passed = has_read and has_mutate and port_correct and status == "found"

    speed = stats.get("avg_speed_tps")
    print(
        f"    {dt:.2f}s tools={tools} iter={iters} "
        f"out_tok={stats.get('output_tokens')} speed={speed} "
        f"port_after={(config_after or {}).get('port')} "
        f"{'PASS' if passed else 'FAIL'}"
    )
    sess.clear()
    return {
        "prompt": MULTI_TURN_PROMPT,
        "time_s": round(dt, 2),
        "iterations": iters,
        "prompt_tokens": stats.get("prompt_tokens"),
        "output_tokens": stats.get("output_tokens"),
        "prompt_time_s": stats.get("prompt_time_s"),
        "gen_time_s": stats.get("gen_time_s"),
        "avg_speed_tps": stats.get("avg_speed_tps"),
        "tool_sequence": tools,
        "config_after": config_after,
        "port_rewritten": port_correct,
        "passed": passed,
        "status": status,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--bin", default=shutil.which("llama-agent") or "llama-agent",
                   help="Path to llama-agent binary.")
    p.add_argument("--model", required=True,
                   help="Local .gguf path OR hugging-face id like 'repo/name:Q8_0'.")
    p.add_argument("--output", required=True)
    p.add_argument("--max-iterations", type=int, default=12)
    p.add_argument("--timeout", type=int, default=120,
                   help="Per-scenario wall-clock timeout (s).")
    p.add_argument("--debug-log", default=None,
                   help="If set, append raw stripped PTY bytes per turn for debugging.")
    p.add_argument("--load-timeout", type=int, default=180,
                   help="Initial model-load timeout (s).")
    p.add_argument("--keep-sandbox", action="store_true")
    args = p.parse_args()

    if not Path(args.bin).exists() and not shutil.which(args.bin):
        print(f"ERROR: llama-agent binary not found at {args.bin}", file=sys.stderr)
        sys.exit(2)

    print(f"Binary:  {args.bin}")
    print(f"Model:   {args.model}")
    print(f"Sandbox: {SANDBOX}")
    print()
    print("[0/2] Loading model (resident PTY session)...")
    t0 = time.perf_counter()
    with LlamaAgentSession(args.bin, args.model, args.max_iterations,
                           load_timeout=args.load_timeout) as sess:
        load_dt = time.perf_counter() - t0
        print(f"      ready in {load_dt:.2f}s")
        print()
        print("[1/2] Single-call scenarios")
        singles = run_single(sess, args.timeout, debug_log=args.debug_log)
        print()
        print("[2/2] Multi-turn agentic loop")
        multi = run_multi_turn(sess, args.timeout, debug_log=args.debug_log)

    payload = {
        "harness": "llama-agent (resident PTY, in-process, no API server)",
        "harness_repo": "https://github.com/gary149/llama-agent",
        "model": args.model,
        "binary": args.bin,
        "max_iterations": args.max_iterations,
        "model_load_s": round(load_dt, 2),
        "single_calls": singles,
        "multi_turn": multi,
        "summary": {
            "single_pass": sum(1 for s in singles if s["passed"]),
            "single_total": len(singles),
            "multi_pass": multi["passed"],
            "scenarios_wall_s": round(
                sum(s["time_s"] for s in singles) + multi["time_s"], 2
            ),
        },
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print()
    print(f"Wrote {args.output}")
    print(f"Single-call pass rate: {payload['summary']['single_pass']}/{payload['summary']['single_total']}")
    print(f"Multi-turn:            {'PASS' if multi['passed'] else 'FAIL'}")
    print(f"Model load:            {load_dt:.2f}s")
    print(f"Scenarios wall:        {payload['summary']['scenarios_wall_s']:.2f}s")

    if not args.keep_sandbox:
        cleanup_sandbox()


if __name__ == "__main__":
    main()
