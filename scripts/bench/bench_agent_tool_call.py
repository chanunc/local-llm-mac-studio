#!/usr/bin/env python3
"""Benchmark AI agent tool-call response times through real agent CLI invocation.

Measures end-to-end response time when an AI coding agent (OpenCode, Pi) processes
prompts that require tool calls, capturing the full agent loop overhead.

Usage:
    # Auto-discover config, run both scenarios
    python3 scripts/bench/bench_agent_tool_call.py

    # Override model, single scenario
    python3 scripts/bench/bench_agent_tool_call.py --model macstudio/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S --scenario browse

    # Verbose single run for debugging
    python3 scripts/bench/bench_agent_tool_call.py --scenario browse --runs 1 --warmup 0 --verbose
"""

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCENARIOS = {
    "browse": "Browse www.example.com",
    "search": "Browse Hackernews, get the only one latest topic",
}


@dataclass
class TurnDetail:
    turn: int
    duration_s: float
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int


@dataclass
class RunResult:
    scenario: str
    prompt: str
    response_time_s: float
    llm_time_s: float
    agent_turns: int
    tool_calls: list
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    per_turn: list
    errors: list
    exit_code: int
    events_summary: dict = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    median: float
    p5: float
    p95: float
    mean: float
    stddev: float
    values: list


def aggregate(values):
    if not values:
        return AggregatedMetric(0, 0, 0, 0, 0, [])
    n = len(values)
    sorted_v = sorted(values)
    med = statistics.median(sorted_v)
    mean = statistics.mean(sorted_v)
    sd = statistics.stdev(sorted_v) if n > 1 else 0.0
    p5_idx = max(0, int(n * 0.05))
    p95_idx = min(n - 1, int(n * 0.95))
    return AggregatedMetric(
        median=round(med, 2),
        p5=round(sorted_v[p5_idx], 2),
        p95=round(sorted_v[p95_idx], 2),
        mean=round(mean, 2),
        stddev=round(sd, 2),
        values=[round(v, 2) for v in values],
    )


# --- Agent Runners ---


class AgentRunner:
    def discover_config(self):
        raise NotImplementedError

    def check_health(self, base_url):
        try:
            req = urllib.request.Request(f"{base_url}/models")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["id"] for m in data.get("data", [])]
                return {"ok": True, "models": models}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def run_prompt(self, prompt, model=None, working_dir=None, skip_permissions=False, verbose=False):
        raise NotImplementedError

    def parse_output(self, stdout, stderr):
        raise NotImplementedError

    def export_session(self):
        raise NotImplementedError


class OpenCodeRunner(AgentRunner):
    def __init__(self):
        self._last_session_id = None

    def discover_config(self):
        config_path = Path.home() / ".config" / "opencode" / "opencode.json"
        if not config_path.exists():
            return {"error": f"Config not found at {config_path}"}

        config = json.loads(config_path.read_text())
        default_model = config.get("model", "")
        provider_name = default_model.split("/")[0] if "/" in default_model else None

        base_url = ""
        if provider_name and provider_name in config.get("provider", {}):
            base_url = config["provider"][provider_name].get("options", {}).get("baseURL", "")

        models = {}
        for pname, pconfig in config.get("provider", {}).items():
            for mid, minfo in pconfig.get("models", {}).items():
                full_id = f"{pname}/{mid}"
                models[full_id] = {
                    "name": minfo.get("name", mid),
                    "tools": minfo.get("tools", False),
                    "reasoning": minfo.get("reasoning", False),
                }

        return {
            "base_url": base_url,
            "default_model": default_model,
            "models": models,
            "config_path": str(config_path),
        }

    def run_prompt(self, prompt, model=None, working_dir=None, skip_permissions=False, verbose=False, log_path=None):
        cmd = ["opencode", "run", "--format", "json"]
        if model:
            cmd += ["--model", model]
        if skip_permissions:
            cmd += ["--dangerously-skip-permissions"]
        if verbose:
            cmd += ["--print-logs", "--log-level", "INFO"]
        cmd.append(prompt)

        env = os.environ.copy()
        cwd = working_dir or tempfile.mkdtemp(prefix="agent-bench-")

        if verbose:
            print(f"  CMD: {' '.join(cmd)}", file=sys.stderr)
            print(f"  CWD: {cwd}", file=sys.stderr)

        t_start = time.perf_counter()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=env,
                timeout=300,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as e:
            timed_out = True
            stdout = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            stderr = (stderr or "") + "\n[bench] TIMEOUT after 300s"
            exit_code = -1
        t_end = time.perf_counter()

        if log_path:
            try:
                with open(log_path, "w") as f:
                    f.write(f"# bench stderr capture: {' '.join(cmd)}\n")
                    f.write(f"# cwd: {cwd}\n")
                    f.write(f"# exit_code: {exit_code}  elapsed_s: {t_end - t_start:.2f}  timed_out: {timed_out}\n\n")
                    f.write(stderr or "")
            except OSError as err:
                print(f"  [warn] could not write log {log_path}: {err}", file=sys.stderr)

        return {
            "response_time_s": t_end - t_start,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "log_path": log_path,
        }

    def parse_output(self, stdout, stderr):
        events = {"step_start": 0, "step_finish": 0, "text": 0, "tool_use": 0, "reasoning": 0, "error": 0, "other": 0}
        tool_calls = []
        errors = []
        session_id = None

        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue

            evt_type = evt.get("type", "other")
            if evt_type in events:
                events[evt_type] += 1
            else:
                events["other"] += 1

            if evt_type == "tool_use":
                part = evt.get("part", {})
                tool_name = part.get("tool", evt.get("properties", {}).get("tool", "unknown"))
                tool_calls.append(tool_name)

            if evt_type == "error":
                err = evt.get("error", evt.get("properties", {}))
                msg = err.get("data", {}).get("message", "") if isinstance(err, dict) else str(err)
                errors.append(msg or str(evt))

            if "sessionID" in evt:
                session_id = evt["sessionID"]

        self._last_session_id = session_id
        return {
            "events": events,
            "tool_calls": tool_calls,
            "errors": errors,
            "agent_turns": events["step_start"],
            "session_id": session_id,
        }

    def export_session(self):
        if not self._last_session_id:
            sid = self._get_latest_session_id()
            if not sid:
                return None
            self._last_session_id = sid

        try:
            proc = subprocess.run(
                ["opencode", "export", self._last_session_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                return None
            return json.loads(proc.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    def _get_latest_session_id(self):
        try:
            proc = subprocess.run(
                ["opencode", "session", "list"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            lines = proc.stdout.strip().split("\n")
            for line in lines:
                parts = line.strip().split()
                if parts and len(parts[0]) > 8:
                    return parts[0]
        except subprocess.TimeoutExpired:
            pass
        return None

    def extract_session_details(self, session_data):
        if not session_data:
            return {"per_turn": [], "total_input": 0, "total_output": 0, "total_reasoning": 0}

        turns = []
        total_input = 0
        total_output = 0
        total_reasoning = 0
        turn_num = 0

        for msg in session_data.get("messages", []):
            info = msg.get("info", msg)
            if info.get("role") != "assistant":
                continue

            turn_num += 1
            t = info.get("time", {})
            created = t.get("created", 0)
            completed = t.get("completed", 0)
            duration = (completed - created) / 1000.0 if created and completed else 0

            tokens = info.get("tokens", {})
            inp = tokens.get("input", tokens.get("total", 0))
            out = tokens.get("output", 0)
            reasoning = tokens.get("reasoning", 0)

            total_input += inp
            total_output += out
            total_reasoning += reasoning

            turns.append(TurnDetail(
                turn=turn_num,
                duration_s=round(duration, 2),
                input_tokens=inp,
                output_tokens=out,
                reasoning_tokens=reasoning,
            ))

        return {
            "per_turn": turns,
            "total_input": total_input,
            "total_output": total_output,
            "total_reasoning": total_reasoning,
        }


# --- Benchmark Engine ---


def run_scenario(runner, scenario_name, prompt, model, working_dir, warmup, runs, skip_permissions, verbose, log_dir=None):
    all_results = []
    total_iterations = warmup + runs

    for i in range(total_iterations):
        is_warmup = i < warmup
        label = f"warmup {i + 1}/{warmup}" if is_warmup else f"run {i - warmup + 1}/{runs}"
        slug = f"warmup-{i + 1}" if is_warmup else f"run-{i - warmup + 1}"
        print(f"  [{scenario_name}] {label}...", file=sys.stderr, end=" ", flush=True)

        log_path = None
        if verbose and log_dir:
            log_path = os.path.join(log_dir, f"{scenario_name}-{slug}.log")

        raw = runner.run_prompt(prompt, model=model, working_dir=working_dir,
                                skip_permissions=skip_permissions, verbose=verbose,
                                log_path=log_path)
        parsed = runner.parse_output(raw["stdout"], raw["stderr"])

        session_details = {"per_turn": [], "total_input": 0, "total_output": 0, "total_reasoning": 0}
        session_data = runner.export_session()
        if session_data:
            session_details = runner.extract_session_details(session_data)

        llm_time_s = round(sum(t.duration_s for t in session_details["per_turn"]), 2)

        result = RunResult(
            scenario=scenario_name,
            prompt=prompt,
            response_time_s=round(raw["response_time_s"], 2),
            llm_time_s=llm_time_s,
            agent_turns=parsed["agent_turns"],
            tool_calls=parsed["tool_calls"],
            total_input_tokens=session_details["total_input"],
            total_output_tokens=session_details["total_output"],
            total_reasoning_tokens=session_details["total_reasoning"],
            per_turn=[asdict(t) for t in session_details["per_turn"]],
            errors=parsed["errors"],
            exit_code=raw["exit_code"],
            events_summary=parsed["events"],
        )

        print(f"{result.response_time_s}s wall (llm {result.llm_time_s}s)  turns={result.agent_turns}  tools={result.tool_calls}", file=sys.stderr)

        if verbose:
            print(f"    tokens: in={result.total_input_tokens} out={result.total_output_tokens} reason={result.total_reasoning_tokens}", file=sys.stderr)
            if result.errors:
                print(f"    errors: {result.errors}", file=sys.stderr)

        if not is_warmup:
            all_results.append(result)

    return all_results


def aggregate_scenario(results):
    if not results:
        return {}

    return {
        "prompt": results[0].prompt,
        "runs": len(results),
        "response_time_s": asdict(aggregate([r.response_time_s for r in results])),
        "llm_time_s": asdict(aggregate([r.llm_time_s for r in results])),
        "agent_turns": asdict(aggregate([r.agent_turns for r in results])),
        "total_tokens": asdict(aggregate([r.total_input_tokens + r.total_output_tokens for r in results])),
        "input_tokens": asdict(aggregate([r.total_input_tokens for r in results])),
        "output_tokens": asdict(aggregate([r.total_output_tokens for r in results])),
        "reasoning_tokens": asdict(aggregate([r.total_reasoning_tokens for r in results])),
        "tool_calls_per_run": [r.tool_calls for r in results],
        "per_turn_samples": [r.per_turn for r in results],
        "error_count": sum(1 for r in results if r.errors),
        "raw_runs": [asdict(r) for r in results],
    }


def print_summary(config, scenario_results):
    print(file=sys.stderr)
    print("=== Agent Tool-Call Benchmark ===", file=sys.stderr)
    print(f"Agent:  {config['agent']}", file=sys.stderr)
    print(f"Server: {config.get('server_url', '(unknown)')}", file=sys.stderr)
    print(f"Model:  {config.get('model', '(default)')}", file=sys.stderr)
    print(file=sys.stderr)

    for name, agg in scenario_results.items():
        if not agg:
            continue
        rt = agg["response_time_s"]
        llm = agg.get("llm_time_s", {})
        turns = agg["agent_turns"]
        tokens = agg["total_tokens"]

        tools_flat = []
        for tc_list in agg.get("tool_calls_per_run", []):
            for t in tc_list:
                if t not in tools_flat:
                    tools_flat.append(t)
        tools_str = ", ".join(tools_flat) if tools_flat else "(none)"

        print(f"--- {SCENARIOS.get(name, name)} ---", file=sys.stderr)
        print(f"  Wall time: {rt['median']}s (median)  [{rt['p5']} - {rt['p95']} p5-p95]", file=sys.stderr)
        if llm.get("median", 0) > 0:
            print(f"  LLM time:  {llm['median']}s (median, sum of per-turn assistant durations — matches TUI status bar)", file=sys.stderr)
        print(f"  Turns: {turns['median']} (median) | Tools: {tools_str} | Tokens: {int(tokens['median']):,}", file=sys.stderr)

        reasoning = agg.get("reasoning_tokens", {})
        if reasoning.get("median", 0) > 0:
            print(f"  Reasoning tokens: {int(reasoning['median']):,} (median)", file=sys.stderr)

        if agg.get("per_turn_samples") and agg["per_turn_samples"][0]:
            sample = agg["per_turn_samples"][0]
            print("  Per-turn (sample):", file=sys.stderr)
            for turn in sample:
                print(f"    Turn {turn['turn']}: {turn['duration_s']}s  in={turn['input_tokens']} out={turn['output_tokens']}", file=sys.stderr)

        if agg.get("error_count", 0) > 0:
            print(f"  Errors: {agg['error_count']}/{agg['runs']} runs", file=sys.stderr)
        print(file=sys.stderr)


# --- Main ---


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark AI agent tool-call response times",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  %(prog)s                                    # auto-discover, both scenarios\n"
               "  %(prog)s --scenario browse --runs 1 -v      # single debug run\n"
               "  %(prog)s --model macstudio/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S\n",
    )
    parser.add_argument("--tool", default="opencode", choices=["opencode"], help="Agent CLI tool (default: opencode)")
    parser.add_argument("--model", help="Model override (default: from agent config)")
    parser.add_argument("--scenario", default="both", choices=["browse", "search", "both"], help="Benchmark scenario")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup runs (default: 1)")
    parser.add_argument("--runs", type=int, default=3, help="Measured runs (default: 3)")
    parser.add_argument("--skip-permissions", action="store_true", help="Pass --dangerously-skip-permissions to agent")
    parser.add_argument("--working-dir", help="Working directory for agent (default: /tmp/agent-bench)")
    parser.add_argument("--output", help="JSON output file (default: stdout)")
    parser.add_argument("--base-url", help="Override base_url for health check (default: from agent config)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.tool == "opencode":
        runner = OpenCodeRunner()
    else:
        print(f"Error: unsupported tool '{args.tool}'", file=sys.stderr)
        sys.exit(1)

    # Discover config
    print("Discovering config...", file=sys.stderr)
    config_info = runner.discover_config()
    if "error" in config_info:
        print(f"Error: {config_info['error']}", file=sys.stderr)
        sys.exit(1)

    model = args.model or config_info.get("default_model", "")
    base_url = args.base_url or config_info.get("base_url", "")

    print(f"  Config: {config_info.get('config_path', '')}", file=sys.stderr)
    print(f"  Server: {base_url}", file=sys.stderr)
    print(f"  Model:  {model}", file=sys.stderr)
    print(f"  Models available: {len(config_info.get('models', {}))}", file=sys.stderr)

    # Health check
    print("Health check...", file=sys.stderr)
    health = runner.check_health(base_url)
    if not health["ok"]:
        print(f"Error: server unreachable at {base_url}: {health['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"  Server OK, serving: {', '.join(health['models'][:3])}", file=sys.stderr)

    # Prepare working directory
    working_dir = args.working_dir or "/tmp/agent-bench"
    os.makedirs(working_dir, exist_ok=True)

    # Prepare per-run log directory when verbose — placed next to --output JSON
    log_dir = None
    if args.verbose:
        if args.output:
            base = Path(args.output)
            log_dir = str(base.with_suffix("")) + ".logs"
        else:
            log_dir = os.path.join(working_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        print(f"  Logs:   {log_dir}", file=sys.stderr)

    # Run scenarios
    scenarios_to_run = list(SCENARIOS.keys()) if args.scenario == "both" else [args.scenario]
    scenario_results = {}

    for scenario_name in scenarios_to_run:
        prompt = SCENARIOS[scenario_name]
        print(f"\nRunning scenario: {scenario_name} ({args.warmup} warmup + {args.runs} measured)", file=sys.stderr)
        results = run_scenario(
            runner, scenario_name, prompt,
            model=model if args.model else None,
            working_dir=working_dir,
            warmup=args.warmup,
            runs=args.runs,
            skip_permissions=args.skip_permissions,
            verbose=args.verbose,
            log_dir=log_dir,
        )
        scenario_results[scenario_name] = aggregate_scenario(results)

    # Build output
    output = {
        "benchmark": "agent-tool-call",
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "agent": args.tool,
            "model": model,
            "server_url": base_url,
            "discovered_from": config_info.get("config_path", ""),
            "warmup_runs": args.warmup,
            "measured_runs": args.runs,
            "log_dir": log_dir,
        },
        "scenarios": scenario_results,
    }

    # Print summary
    print_summary(output["config"], scenario_results)

    # Write JSON
    json_str = json.dumps(output, indent=2)
    if args.output:
        Path(args.output).write_text(json_str + "\n")
        print(f"Results saved to: {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
