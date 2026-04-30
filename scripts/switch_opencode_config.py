#!/usr/bin/env python3
"""Switch OpenCode client config between server backends.

Reads template configs from this repo's configs/client/<server>/opencode.json,
resolves placeholders with real values from the live config, and writes to
~/.config/opencode/opencode.json.

Usage:
    python3 scripts/switch_opencode_config.py --list
    python3 scripts/switch_opencode_config.py --current
    python3 scripts/switch_opencode_config.py --server vmlx
    python3 scripts/switch_opencode_config.py --server omlx --model JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

LIVE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIGS_DIR = REPO_ROOT / "configs" / "client"
SERVERS = ["vllm-mlx", "omlx", "mlx-openai-server", "vmlx", "llmster"]


def read_live_config():
    if not LIVE_CONFIG.exists():
        print(f"Error: live config not found at {LIVE_CONFIG}", file=sys.stderr)
        sys.exit(1)
    return json.loads(LIVE_CONFIG.read_text())


def extract_real_ip(live_config):
    for pconfig in live_config.get("provider", {}).values():
        url = pconfig.get("options", {}).get("baseURL", "")
        match = re.search(r"https?://([^:/]+)", url)
        if match:
            return match.group(1)
    return None


def extract_api_key(live_config):
    for pconfig in live_config.get("provider", {}).values():
        key = pconfig.get("options", {}).get("apiKey", "")
        if key and key not in ("not-needed", "<YOUR_API_KEY>"):
            return key
    return None


def read_template(server):
    path = CONFIGS_DIR / server / "opencode.json"
    if not path.exists():
        print(f"Error: template not found at {path}", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def resolve_template(template, real_ip, api_key=None):
    raw = json.dumps(template)
    raw = raw.replace("<MAC_STUDIO_IP>", real_ip)
    if api_key:
        raw = raw.replace("<YOUR_API_KEY>", api_key)
    else:
        raw = raw.replace("<YOUR_API_KEY>", "not-needed")
    return json.loads(raw)


def list_servers():
    live = read_live_config()
    current_model = live.get("model", "")
    current_url = ""
    for pconfig in live.get("provider", {}).values():
        current_url = pconfig.get("options", {}).get("baseURL", "")
        break

    print(f"Current: {current_model}")
    print(f"Server:  {current_url}")
    print()
    print("Available server configs:")

    for server in SERVERS:
        path = CONFIGS_DIR / server / "opencode.json"
        if not path.exists():
            continue
        template = json.loads(path.read_text())
        models = []
        for pconfig in template.get("provider", {}).values():
            for mid, minfo in pconfig.get("models", {}).items():
                name = minfo.get("name", mid)
                models.append(name)
        default = template.get("model", "").split("/", 1)[-1] if "/" in template.get("model", "") else template.get("model", "")
        print(f"  {server:<22} {len(models)} model(s)  default: {default}")
        for m in models:
            print(f"    - {m}")


def show_current():
    live = read_live_config()
    model = live.get("model", "(not set)")
    small = live.get("small_model", "(not set)")

    for pname, pconfig in live.get("provider", {}).items():
        url = pconfig.get("options", {}).get("baseURL", "")
        key = pconfig.get("options", {}).get("apiKey", "")
        models = list(pconfig.get("models", {}).keys())
        print(f"Provider: {pname}")
        print(f"Server:   {url}")
        print(f"API key:  {key or '(none)'}")
        print(f"Model:    {model}")
        print(f"Small:    {small}")
        print(f"Available ({len(models)}):")
        for mid in models:
            minfo = pconfig["models"][mid]
            name = minfo.get("name", mid)
            flags = []
            if minfo.get("tools"):
                flags.append("tools")
            if minfo.get("reasoning"):
                flags.append("reasoning")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"  - {mid}{flag_str}")
            print(f"    {name}")


def switch_server(server, model_override=None):
    if server not in SERVERS:
        print(f"Error: unknown server '{server}'. Choose from: {', '.join(SERVERS)}", file=sys.stderr)
        sys.exit(1)

    live = read_live_config()
    real_ip = extract_real_ip(live)
    if not real_ip:
        print("Error: could not extract real IP from live config", file=sys.stderr)
        sys.exit(1)

    api_key = extract_api_key(live)
    template = read_template(server)
    resolved = resolve_template(template, real_ip, api_key)

    if model_override:
        provider_name = None
        for pname, pconfig in resolved.get("provider", {}).items():
            for mid in pconfig.get("models", {}).keys():
                if mid == model_override or model_override in mid:
                    provider_name = pname
                    model_override = mid
                    break
            if provider_name:
                break

        if not provider_name:
            print(f"Error: model '{model_override}' not found in {server} config", file=sys.stderr)
            available = [mid for p in resolved["provider"].values() for mid in p.get("models", {})]
            print(f"Available: {', '.join(available)}", file=sys.stderr)
            sys.exit(1)

        resolved["model"] = f"{provider_name}/{model_override}"
        resolved["small_model"] = f"{provider_name}/{model_override}"

    # Preserve permission setting from live config
    if "permission" in live:
        resolved["permission"] = live["permission"]

    # Backup
    if LIVE_CONFIG.exists():
        backup = LIVE_CONFIG.with_suffix(".json.bak")
        shutil.copy2(LIVE_CONFIG, backup)
        print(f"Backed up: {backup}")

    LIVE_CONFIG.write_text(json.dumps(resolved, indent=2) + "\n")

    model = resolved.get("model", "")
    url = ""
    for pconfig in resolved.get("provider", {}).values():
        url = pconfig.get("options", {}).get("baseURL", "")
        break

    print(f"Switched to: {server}")
    print(f"Server:      {url}")
    print(f"Model:       {model}")


def main():
    parser = argparse.ArgumentParser(description="Switch OpenCode client config between server backends")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List available server configs")
    group.add_argument("--current", action="store_true", help="Show current config")
    group.add_argument("--server", choices=SERVERS, help="Switch to a server config")
    parser.add_argument("--model", help="Override default model (partial match supported)")
    args = parser.parse_args()

    if args.list:
        list_servers()
    elif args.current:
        show_current()
    elif args.server:
        switch_server(args.server, args.model)


if __name__ == "__main__":
    main()
