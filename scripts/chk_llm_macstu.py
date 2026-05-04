#!/usr/bin/env python3
"""Probe the Mac Studio over SSH and report the live LLM stack.

Reports which LLM server (vllm-mlx / mlx-openai-server / oMLX / vmlx / llmster /
dflash-mlx) is currently running on ports 8000 / 1234 / 8098, the loaded model,
and (in --all / --client / --logs modes) the matching client config or log-tail
command for the detected server.

Usage:
    python3 scripts/chk_llm_macstu.py                              # status report
    python3 scripts/chk_llm_macstu.py --json                       # JSON status
    python3 scripts/chk_llm_macstu.py --verbose                    # + full model lists
    python3 scripts/chk_llm_macstu.py --client opencode            # emit resolved opencode.json
    python3 scripts/chk_llm_macstu.py --client all                 # all client configs (JSON)
    python3 scripts/chk_llm_macstu.py --logs                       # emit log-tail command
    python3 scripts/chk_llm_macstu.py --all                        # bundled text report
    python3 scripts/chk_llm_macstu.py --all --json                 # bundled JSON
    python3 scripts/chk_llm_macstu.py --ssh-host macstudio-ts      # over Tailscale
    python3 scripts/chk_llm_macstu.py --no-ssh                     # run locally on the Mac Studio

Exit codes:
    0  status mode: at least one LLM server up; --client/--logs/--all: emission ok
    1  no known LLM server up
    2  SSH / connection error (could not even probe)
    3  --client: detected server has no template for the requested client; or
       --client/--logs with multiple servers up and no --port given
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs" / "clients"
LIVE_OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"

# (process pattern, server label, server folder name, port)
# Order matters: check more-specific patterns first.
SERVER_PATTERNS = [
    ("vllm-mlx",          "vllm-mlx",          "vllm-mlx",          8000),
    ("mlx-openai-server", "mlx-openai-server", "mlx-openai-server", 8000),
    ("vmlx_engine",       "vmlx",              "vmlx",              8000),
    ("dflash-serve",      "dflash-mlx",        "dflash-mlx",        8098),
    ("lms server",        "llmster",           "llmster",           1234),
]

# When a port is listening but no SERVER_PATTERNS process matches, fall back here.
FALLBACK_SERVER_BY_PORT = {
    8000: ("oMLX", "omlx"),  # brew-managed; process name varies
    1234: ("llmster", "llmster"),  # LM Studio app holds the socket; daemon may not be visible
}

# Server label → log-tail command (gets `ssh <host> "..."`-wrapped unless --no-ssh).
SERVER_LOGS = {
    "vllm-mlx":          "tail -f /tmp/vllm-mlx.log",
    "mlx-openai-server": "tail -f /tmp/mlx-openai-server.log",
    "oMLX":              "tail -f ~/.omlx/logs/server.log",
    "vmlx":              "tail -f /tmp/vmlx.log",
    "dflash-mlx":        "tail -f /tmp/dflash-mlx.log",
    "llmster":           "~/.lmstudio/bin/lms log stream --source server",
}

# --client name → filename under configs/clients/<server>/
CLIENT_FILES = {
    "opencode":     "opencode.json",
    "pi":           "pi-models.json",
    "openclaw":     "openclaw-provider.json",
    "qwen-code":    "qwen-code-settings.json",
    "claude-code":  "claude-code-settings.json",
}

DEFAULT_PORTS = [8000, 1234, 8098]

# Servers that hold exactly one model in memory at a time → overlay rewrites the default.
# Multi-model servers (mlx-openai-server, oMLX) only get roster-sync (append missing models).
SINGLE_MODEL_SERVERS = {"vllm-mlx", "vmlx", "dflash-mlx", "llmster"}

# Substrings (lowercase) that flip the reasoning flag on overlay stub injection.
REASONING_KEYWORDS = ("thinking", "reasoning", "heretic-thinking", "-r1", "cot", "deepseek-r1")


# ---------- SSH + remote probe ----------

def run_remote(host, cmd, no_ssh=False, timeout=10):
    argv = ["sh", "-c", cmd] if no_ssh else ["ssh", host, cmd]
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def probe(host, no_ssh=False):
    """Single SSH round-trip — processes, listening ports (with PIDs), and `lms ps`."""
    sep = "---SEP---"
    cmd = (
        "ps -axo pid=,rss=,command= 2>/dev/null | "
        "grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|\\.lmstudio|omlx' | "
        "grep -v grep || true; "
        f"echo '{sep}'; "
        "lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | "
        "grep -E ':(8000|8098|1234) \\(LISTEN\\)' || true; "
        f"echo '{sep}'; "
        "if [ -x ~/.lmstudio/bin/lms ]; then ~/.lmstudio/bin/lms ps 2>/dev/null; fi; "
        f"echo '{sep}'; "
        # Enrich any lsof-detected PIDs with their RSS + full command line.
        "PIDS=$(lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | "
        "grep -E ':(8000|8098|1234) \\(LISTEN\\)' | awk '{print $2}' | sort -u); "
        "if [ -n \"$PIDS\" ]; then ps -p $(echo $PIDS | tr ' ' ',') -o pid=,rss=,command= 2>/dev/null; fi"
    )
    try:
        result = run_remote(host, cmd, no_ssh=no_ssh)
    except subprocess.TimeoutExpired:
        print(f"Error: probe to {host} timed out after 10s", file=sys.stderr)
        sys.exit(2)
    except FileNotFoundError:
        print("Error: ssh executable not found", file=sys.stderr)
        sys.exit(2)

    if result.returncode != 0 and not result.stdout:
        print(f"Error: probe to {host} failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(2)

    parts = result.stdout.split(sep)
    if len(parts) < 4:
        print(f"Error: probe to {host} returned malformed output", file=sys.stderr)
        sys.exit(2)

    grep_procs = parse_processes(parts[0])
    listen_pids = parse_listening(parts[1])
    lms_models = parse_lms_ps(parts[2])
    socket_procs = parse_processes(parts[3])

    # Merge: dedupe by PID, prefer grep-side info but include socket-side PIDs.
    by_pid = {p["pid"]: p for p in grep_procs}
    for p in socket_procs:
        by_pid.setdefault(p["pid"], p)

    return {
        "processes":   list(by_pid.values()),
        "listening":   listen_pids,
        "lms_models":  lms_models,
    }


def parse_processes(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(.+)", line)
        if m:
            pid, rss_kib, cmd = m.groups()
            out.append({"pid": int(pid), "rss_bytes": int(rss_kib) * 1024, "command": cmd.strip()})
    return out


def parse_listening(text):
    """Return list of {port, pid, command} dicts, one per LISTEN row."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+(\d+)\s.*\sTCP\s+\S*?:(\d+)\s+\(LISTEN\)", line)
        if m:
            out.append({"command": m.group(1), "pid": int(m.group(2)), "port": int(m.group(3))})
    return out


def parse_lms_ps(text):
    """Parse `lms ps` table (whitespace-aligned columns)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    out = []
    for line in lines[1:]:
        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) < 3:
            continue
        ctx = None
        if len(cols) > 4 and cols[4].isdigit():
            ctx = int(cols[4])
        out.append({
            "id":       cols[0],
            "model":    cols[1] if len(cols) > 1 else None,
            "status":   cols[2] if len(cols) > 2 else None,
            "size_str": cols[3] if len(cols) > 3 else None,
            "context":  ctx,
        })
    return out


# ---------- Per-port HTTP probe ----------

def fetch_models(base_url, api_key=None, timeout=3):
    headers = {}
    if api_key and api_key != "not-needed":
        headers["Authorization"] = f"Bearer {api_key}"
    url = base_url.rstrip("/") + "/models"  # base_url already includes /v1
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    return [m.get("id") for m in data.get("data", []) if m.get("id")]


# ---------- Local opencode config (for placeholder resolution) ----------

def load_opencode_config():
    if not LIVE_OPENCODE_CONFIG.exists():
        return None
    try:
        return json.loads(LIVE_OPENCODE_CONFIG.read_text())
    except Exception:
        return None


def extract_real_ip(opencode_cfg):
    if not opencode_cfg:
        return None
    for pcfg in opencode_cfg.get("provider", {}).values():
        url = pcfg.get("options", {}).get("baseURL", "")
        m = re.search(r"https?://([^:/]+)", url)
        if m:
            return m.group(1)
    return None


def extract_api_key(opencode_cfg):
    if not opencode_cfg:
        return None
    for pcfg in opencode_cfg.get("provider", {}).values():
        key = pcfg.get("options", {}).get("apiKey", "")
        if key and key not in ("not-needed", "<YOUR_API_KEY>"):
            return key
    return None


def resolve_template(template_obj, real_ip, api_key):
    raw = json.dumps(template_obj)
    raw = raw.replace("<MAC_STUDIO_IP>", real_ip or "127.0.0.1")
    raw = raw.replace("<YOUR_API_KEY>", api_key or "not-needed")
    return json.loads(raw)


# ---------- Server identification ----------

def identify_servers(probe_data, want_ports):
    """Return list of dicts: [{port, server, server_dir, processes, ...}, ...]."""
    listen_by_port = {l["port"]: l for l in probe_data["listening"]}
    procs_by_pid = {p["pid"]: p for p in probe_data["processes"]}

    out = []
    for port in want_ports:
        if port not in listen_by_port:
            out.append({"port": port, "server": None, "server_dir": None, "up": False, "processes": []})
            continue
        listener = listen_by_port[port]
        label = server_dir = None
        port_procs = []
        owner = procs_by_pid.get(listener["pid"])
        if owner:
            port_procs.append(owner)
        for pattern, srv_label, srv_dir, expected_port in SERVER_PATTERNS:
            if expected_port != port:
                continue
            if owner and pattern in owner["command"]:
                label, server_dir = srv_label, srv_dir
                continue
            for p in probe_data["processes"]:
                if pattern in p["command"] and p["pid"] != listener["pid"]:
                    port_procs.append(p)
                    if not label:
                        label, server_dir = srv_label, srv_dir
        # LM Studio app shows up as `LM Studio` in command line — special-case it for llmster.
        if not label and port == 1234 and owner and "LM Studio" in owner.get("command", ""):
            label, server_dir = "llmster", "llmster"
        if not label and port in FALLBACK_SERVER_BY_PORT:
            label, server_dir = FALLBACK_SERVER_BY_PORT[port]
        out.append({
            "port":       port,
            "server":     label,
            "server_dir": server_dir,
            "up":         True,
            "processes":  port_procs,
        })
    return out


def stragglers(probe_data, identified):
    """LLM-related processes not bound to any of the identified ports."""
    claimed_pids = {p["pid"] for entry in identified for p in entry["processes"]}
    return [p for p in probe_data["processes"] if p["pid"] not in claimed_pids]


# ---------- Loaded model resolution ----------

def loaded_model_for(entry, probe_data, base_url, api_key):
    """Return (loaded_model_dict_or_None, available_models_list)."""
    if not entry["up"]:
        return None, []
    avail = fetch_models(base_url, api_key=api_key) or []
    loaded = None
    if entry["server"] == "llmster" and probe_data["lms_models"]:
        loaded = probe_data["lms_models"][0]
    elif entry["server"] in ("vllm-mlx", "vmlx", "dflash-mlx") and len(avail) == 1:
        loaded = {"id": avail[0], "model": avail[0]}
    return loaded, avail


# ---------- Live-state overlay (Fix B) ----------
#
# Each client has a different schema. After resolving placeholders (<MAC_STUDIO_IP>
# / <YOUR_API_KEY>), we overlay the actually-running model on top of the template:
#  - Single-model server: inject the loaded model into the client's models map/list
#    if it's not already there, then flip the client's "default model" field to it.
#  - Multi-model server: roster-sync only — append any /v1/models entries that the
#    template doesn't list (so the client at least *knows* about every available
#    model). Don't touch the default; "loaded" is ambiguous on a multi-model server.

def model_stub_heuristics(loaded_id, loaded_info):
    """Derive (tools, reasoning, context, output) for stub injection."""
    name_lower = (loaded_id or "").lower()
    reasoning = any(kw in name_lower for kw in REASONING_KEYWORDS)
    context = (loaded_info or {}).get("context") or 32768
    return {"tools": True, "reasoning": reasoning, "context": context, "output": 4096}


def overlay_opencode(cfg, loaded_id, heur, single_model, provider_default):
    """opencode: provider.<n>.models is dict-keyed; default is top-level model+small_model."""
    notes = []
    for pname, pcfg in cfg.get("provider", {}).items():
        models = pcfg.setdefault("models", {})
        if loaded_id not in models:
            models[loaded_id] = {
                "name": f"{loaded_id} (live, injected by chk_llm_macstu.py)",
                "tools": heur["tools"],
                "reasoning": heur["reasoning"],
                "limit": {"context": heur["context"], "output": heur["output"]},
            }
            notes.append(f"opencode: injected stub for '{loaded_id}' under provider '{pname}'")
        if single_model:
            cfg["model"] = f"{pname}/{loaded_id}"
            cfg["small_model"] = f"{pname}/{loaded_id}"
        break  # only first provider — opencode templates have one
    return cfg, notes


def overlay_pi(cfg, loaded_id, heur, single_model, _):
    """pi: providers.<n>.models is a list of {id, name, ...}."""
    notes = []
    for pname, pcfg in cfg.get("providers", {}).items():
        models = pcfg.setdefault("models", [])
        if not any(m.get("id") == loaded_id for m in models):
            models.insert(0, {
                "id": loaded_id,
                "name": f"{loaded_id} (live, injected)",
                "reasoning": heur["reasoning"],
                "input": ["text"],
                "contextWindow": heur["context"],
                "maxTokens": heur["output"],
            })
            notes.append(f"pi: injected stub for '{loaded_id}' under provider '{pname}'")
        if single_model:
            pcfg["defaultModel"] = loaded_id
        break
    return cfg, notes


def overlay_openclaw(cfg, loaded_id, heur, single_model, _):
    """openclaw: <n>.models is a list."""
    notes = []
    for pname, pcfg in cfg.items():
        if not isinstance(pcfg, dict) or "models" not in pcfg:
            continue
        models = pcfg["models"]
        if not any(m.get("id") == loaded_id for m in models):
            models.insert(0, {
                "id": loaded_id,
                "name": f"{loaded_id} (live, injected)",
                "reasoning": heur["reasoning"],
                "input": ["text"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": heur["context"],
                "maxTokens": heur["output"],
            })
            notes.append(f"openclaw: injected stub for '{loaded_id}' under provider '{pname}'")
        if single_model:
            pcfg["defaultModel"] = loaded_id
        break
    return cfg, notes


def overlay_qwen_code(cfg, loaded_id, heur, single_model, _):
    """qwen-code: modelProviders.<n> is a list of model objects (each has id, name, baseUrl)."""
    notes = []
    for pname, plist in cfg.get("modelProviders", {}).items():
        if not isinstance(plist, list):
            continue
        if not any(m.get("id") == loaded_id for m in plist):
            template_entry = plist[0] if plist else {}
            stub = {
                "id": loaded_id,
                "name": f"{loaded_id} (live, injected)",
                "description": "Auto-injected from chk_llm_macstu.py live state",
                "baseUrl": template_entry.get("baseUrl", ""),
                "envKey": template_entry.get("envKey", ""),
                "contextWindow": heur["context"],
                "maxTokens": heur["output"],
            }
            plist.insert(0, stub)
            notes.append(f"qwen-code: injected stub for '{loaded_id}' under '{pname}'")
        if single_model and isinstance(cfg.get("model"), dict):
            cfg["model"]["id"] = loaded_id
        break
    return cfg, notes


def overlay_claude_code(cfg, loaded_id, heur, single_model, _):
    """claude-code: env.ANTHROPIC_MODEL is a single string."""
    notes = []
    env = cfg.setdefault("env", {})
    if single_model:
        prev = env.get("ANTHROPIC_MODEL")
        env["ANTHROPIC_MODEL"] = loaded_id
        if prev and prev != loaded_id:
            notes.append(f"claude-code: ANTHROPIC_MODEL flipped from '{prev}' to '{loaded_id}'")
    return cfg, notes


CLIENT_OVERLAY = {
    "opencode":    overlay_opencode,
    "pi":          overlay_pi,
    "openclaw":    overlay_openclaw,
    "qwen-code":   overlay_qwen_code,
    "claude-code": overlay_claude_code,
}


def apply_overlay(client_name, resolved_cfg, server_label, loaded_id, loaded_info, available_models):
    """Apply per-client overlay; for multi-model servers, roster-sync /v1/models too."""
    notes = []
    single = server_label in SINGLE_MODEL_SERVERS
    overlay = CLIENT_OVERLAY.get(client_name)
    if not overlay:
        return resolved_cfg, notes
    if loaded_id:
        heur = model_stub_heuristics(loaded_id, loaded_info)
        resolved_cfg, n = overlay(resolved_cfg, loaded_id, heur, single, server_label)
        notes.extend(n)
    if not single:
        # Multi-model server roster sync: every /v1/models entry that's not in the template
        for mid in available_models or []:
            if mid == loaded_id:
                continue
            heur = model_stub_heuristics(mid, None)
            resolved_cfg, n = overlay(resolved_cfg, mid, heur, False, server_label)
            notes.extend(n)
    return resolved_cfg, notes


# ---------- Formatting helpers ----------

def fmt_bytes(n):
    if n is None:
        return "?"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def base_url_for(entry, real_ip):
    return f"http://{real_ip or '127.0.0.1'}:{entry['port']}/v1"


# ---------- Status mode (default) ----------

def render_status_text(host, identified, probe_data, real_ip, verbose):
    lines = [f"Mac Studio LLM status (via {host})", "=" * 36, ""]
    for entry in identified:
        if not entry["up"]:
            lines.append(f"Port {entry['port']} — DOWN")
            continue
        lines.append(f"Port {entry['port']} — {entry['server']}")
        for p in entry["processes"]:
            lines.append(f"  Process : PID {p['pid']}, RSS {fmt_bytes(p['rss_bytes'])}")
        avail = entry.get("_available", [])
        loaded = entry.get("_loaded")
        if loaded:
            ctx = loaded.get("context")
            ctx_str = f", {ctx} ctx" if ctx else ""
            size_str = f", {loaded.get('size_str')}" if loaded.get("size_str") else ""
            status = f" ({loaded.get('status')})" if loaded.get("status") else ""
            lines.append(f"  Loaded  : {loaded['id']}{status}{size_str}{ctx_str}")
        if avail:
            if verbose:
                lines.append(f"  Available ({len(avail)}):")
                for m in avail:
                    lines.append(f"    - {m}")
            else:
                lines.append(f"  Available: {len(avail)} model(s) via /v1/models  (use --verbose to list)")
    strag = probe_data.get("_stragglers", [])
    if strag:
        lines.append("")
        lines.append("Other LLM processes:")
        for p in strag:
            cmd = p["command"]
            if len(cmd) > 90:
                cmd = cmd[:87] + "..."
            lines.append(f"  PID {p['pid']}  {fmt_bytes(p['rss_bytes'])}  {cmd}")
    return "\n".join(lines) + "\n"


def render_status_json(host, identified, probe_data):
    return {
        "ssh_host": host,
        "ports": {
            str(e["port"]): {
                "up":               e["up"],
                "server":           e["server"],
                "processes":        e["processes"],
                "loaded_model":     e.get("_loaded"),
                "available_models": e.get("_available", []),
            } for e in identified
        },
        "other_processes": probe_data.get("_stragglers", []),
    }


# ---------- --client mode ----------

def emit_client(server_dir, client_name, real_ip, api_key, as_json_with_meta=False,
                server_label=None, loaded_id=None, loaded_info=None, available_models=None):
    if client_name == "all":
        out = {}
        all_notes = []
        for cname, fname in CLIENT_FILES.items():
            path = CONFIGS_DIR / server_dir / fname
            if path.exists():
                tpl = json.loads(path.read_text())
                resolved = resolve_template(tpl, real_ip, api_key)
                resolved, notes = apply_overlay(cname, resolved, server_label, loaded_id, loaded_info, available_models)
                out[cname] = resolved
                all_notes.extend(notes)
        for note in all_notes:
            print(f"Note: {note}", file=sys.stderr)
        if not out:
            print(f"Error: server '{server_dir}' has no client templates under configs/clients/{server_dir}/", file=sys.stderr)
            sys.exit(3)
        if as_json_with_meta:
            return {"server": server_label, "client": "all", "configs": out}
        return out

    fname = CLIENT_FILES.get(client_name)
    if not fname:
        print(f"Error: unknown client '{client_name}'. Choose from: {', '.join(CLIENT_FILES)}", file=sys.stderr)
        sys.exit(3)
    path = CONFIGS_DIR / server_dir / fname
    if not path.exists():
        avail = sorted(c for c, fn in CLIENT_FILES.items() if (CONFIGS_DIR / server_dir / fn).exists())
        avail_str = ", ".join(avail) if avail else "(none)"
        print(f"Error: server '{server_dir}' has no {fname} template; available: {avail_str}", file=sys.stderr)
        sys.exit(3)
    tpl = json.loads(path.read_text())
    resolved = resolve_template(tpl, real_ip, api_key)
    resolved, notes = apply_overlay(client_name, resolved, server_label, loaded_id, loaded_info, available_models)
    for note in notes:
        print(f"Note: {note}", file=sys.stderr)
    if as_json_with_meta:
        return {"server": server_label, "client": client_name, "config": resolved}
    return resolved


# ---------- --logs mode ----------

def logs_command(server_label, host, no_ssh):
    inner = SERVER_LOGS.get(server_label)
    if not inner:
        print(f"Error: no log path mapping for server '{server_label}'", file=sys.stderr)
        sys.exit(3)
    if no_ssh:
        return inner
    return f'ssh {host} "{inner}"'


# ---------- --all mode ----------

def build_all_entry(entry, probe_data, real_ip, host, no_ssh, api_key):
    """Return one --all dict per up server."""
    base = base_url_for(entry, real_ip)
    clients = {}
    loaded = entry.get("_loaded") or {}
    available = entry.get("_available", [])
    if entry["server_dir"]:
        for cname, fname in CLIENT_FILES.items():
            path = CONFIGS_DIR / entry["server_dir"] / fname
            if path.exists():
                tpl = json.loads(path.read_text())
                resolved = resolve_template(tpl, real_ip, api_key)
                resolved, notes = apply_overlay(cname, resolved, entry["server"], loaded.get("id"), loaded, available)
                for note in notes:
                    print(f"Note: {note}", file=sys.stderr)
                clients[cname] = resolved
    return {
        "ssh_host":         host,
        "port":             entry["port"],
        "server":           entry["server"],
        "server_dir":       entry["server_dir"],
        "base_url":         base,
        "processes":        entry["processes"],
        "loaded_model":     entry.get("_loaded"),
        "available_models": entry.get("_available", []),
        "clients":          clients,
        "logs_command":     logs_command(entry["server"], host, no_ssh),
    }


def render_all_text(entries):
    blocks = []
    for entry in entries:
        rows = [
            ("Server",   entry["server"]),
            ("Port",     str(entry["port"])),
            ("Base URL", entry["base_url"]),
        ]
        for p in entry["processes"]:
            rows.append((f"PID {p['pid']}", fmt_bytes(p["rss_bytes"])))

        keylen = max(len(k) for k, _ in rows)
        section = []
        for k, v in rows:
            section.append(f"{k.ljust(keylen)} : {v}")

        loaded = entry["loaded_model"]
        if loaded:
            section.append("")
            section.append("Loaded model")
            section.append("-" * 12)
            lrows = [("ID", loaded.get("id"))]
            if loaded.get("model"):
                lrows.append(("Name", loaded["model"]))
            if loaded.get("status"):
                lrows.append(("Status", loaded["status"]))
            if loaded.get("size_str"):
                lrows.append(("Size", loaded["size_str"]))
            if loaded.get("context") is not None:
                lrows.append(("Context", str(loaded["context"])))
            lkeylen = max(len(k) for k, _ in lrows)
            for k, v in lrows:
                section.append(f"{k.ljust(lkeylen)} : {v}")

        section.append("")
        section.append("Logs (copy and run)")
        section.append("-" * 19)
        section.append(entry["logs_command"])

        avail = entry["available_models"]
        if avail:
            section.append("")
            section.append(f"Available models ({len(avail)})")
            section.append("-" * (len(f"Available models ({len(avail)})")))
            for m in avail:
                section.append(f"  - {m}")

        if entry["clients"]:
            section.append("")
            section.append("Client configs")
            section.append("-" * 14)
            for cname, cfg in entry["clients"].items():
                fname = CLIENT_FILES[cname]
                section.append(f"{cname}  →  configs/clients/{entry['server_dir']}/{fname}")
                if cname == "opencode":
                    section.append(f"  Apply: python3 scripts/switch_opencode_config.py --server {entry['server_dir']}")
                section.append("  Or paste below into the live config:")
                section.append("")
                for ln in json.dumps(cfg, indent=2, ensure_ascii=False).splitlines():
                    section.append("  " + ln)
                section.append("")
        else:
            section.append("")
            section.append("(no client templates ship for this server)")

        blocks.append("\n".join(section))

    header = f"Mac Studio LLM status (via {entries[0]['ssh_host']})\n" + "=" * 36 + "\n\n"
    return header + ("\n\n" + ("=" * 36) + "\n\n").join(blocks) + "\n"


# Lookup so render_all_text can map labels back to server-dir names.
SERVER_FOLDER_LOOKUP = {label: srv_dir for _, label, srv_dir, _ in SERVER_PATTERNS}
SERVER_FOLDER_LOOKUP.update({label: srv_dir for label, srv_dir in FALLBACK_SERVER_BY_PORT.values()})


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser(description="Probe Mac Studio LLM server + model state.")
    ap.add_argument("--ssh-host", default="macstudio", help="SSH alias (default: macstudio; also try macstudio-ts over Tailscale)")
    ap.add_argument("--no-ssh", action="store_true", help="Run probes locally (use when invoked on the Mac Studio itself)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    ap.add_argument("--verbose", action="store_true", help="Status mode: list all available models per port")
    ap.add_argument("--ports", default=None, help="Comma-separated port list (default: 8000,1234,8098)")
    ap.add_argument("--port", type=int, default=None, help="--client/--logs: disambiguate when multiple servers up")

    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--client", choices=list(CLIENT_FILES) + ["all"], help="Emit resolved client config(s) for the detected server")
    mode.add_argument("--logs", action="store_true", help="Emit log-tail command for the detected server")
    mode.add_argument("--all", action="store_true", help="Bundle status + all client configs + log command (text by default; pair with --json)")

    args = ap.parse_args()

    want_ports = DEFAULT_PORTS if not args.ports else [int(x) for x in args.ports.split(",")]

    probe_data = probe(args.ssh_host, no_ssh=args.no_ssh)
    identified = identify_servers(probe_data, want_ports)
    probe_data["_stragglers"] = stragglers(probe_data, identified)

    opencode_cfg = load_opencode_config()
    real_ip = extract_real_ip(opencode_cfg)
    api_key = extract_api_key(opencode_cfg)
    if api_key is None and (args.client or args.all):
        print("Warning: no API key found in ~/.config/opencode/opencode.json — using 'not-needed'", file=sys.stderr)

    for entry in identified:
        if not entry["up"]:
            continue
        loaded, avail = loaded_model_for(entry, probe_data, base_url_for(entry, real_ip), api_key)
        entry["_loaded"] = loaded
        entry["_available"] = avail

    up_entries = [e for e in identified if e["up"]]

    # --- --client mode ---
    if args.client:
        chosen = pick_one_or_die(up_entries, args.port, "--client")
        loaded = chosen.get("_loaded") or {}
        out = emit_client(
            chosen["server_dir"], args.client, real_ip, api_key,
            as_json_with_meta=args.json, server_label=chosen["server"],
            loaded_id=loaded.get("id"), loaded_info=loaded,
            available_models=chosen.get("_available", []),
        )
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        sys.exit(0)

    # --- --logs mode ---
    if args.logs:
        chosen = pick_one_or_die(up_entries, args.port, "--logs")
        print(logs_command(chosen["server"], args.ssh_host, args.no_ssh))
        sys.exit(0)

    # --- --all mode ---
    if args.all:
        if not up_entries:
            print("Warning: no LLM servers detected", file=sys.stderr)
            if args.json:
                json.dump([], sys.stdout, indent=2)
                sys.stdout.write("\n")
            sys.exit(1)
        bundle = [build_all_entry(e, probe_data, real_ip, args.ssh_host, args.no_ssh, api_key) for e in up_entries]
        if args.json:
            json.dump(bundle, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            sys.stdout.write(render_all_text(bundle))
        sys.exit(0)

    # --- default status mode ---
    if args.json:
        json.dump(render_status_json(args.ssh_host, identified, probe_data), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_status_text(args.ssh_host, identified, probe_data, real_ip, args.verbose))

    sys.exit(0 if up_entries else 1)


def pick_one_or_die(up_entries, port_filter, mode_name):
    if not up_entries:
        print(f"Error: no LLM server detected; cannot use {mode_name}", file=sys.stderr)
        sys.exit(1)
    if port_filter is not None:
        match = [e for e in up_entries if e["port"] == port_filter]
        if not match:
            print(f"Error: no server on port {port_filter}; up: {[e['port'] for e in up_entries]}", file=sys.stderr)
            sys.exit(3)
        return match[0]
    if len(up_entries) > 1:
        ports = [e["port"] for e in up_entries]
        print(f"Error: multiple servers up ({ports}); pass --port N to choose", file=sys.stderr)
        sys.exit(3)
    return up_entries[0]


if __name__ == "__main__":
    main()
