#!/usr/bin/env python3
"""Switch the Mac Studio to one of the top-5 fastest OpenCode-benchmark models.

Selection is driven by the live OpenCode end-to-end benchmark table
(`docs/models/benchmarks/model-benchmark-tool-call.md` → `### OpenCode end-to-end`),
*not* a hardcoded ranking: pick a model **type** (🧱 Dense / 🧩 Hybrid MoE / 🔀 MoE),
then one of the five fastest in that group by browse wall-time ascending. The script
then stops every running LLM server (frees unified memory), starts the right one,
syncs the OpenCode client config, and runs a single tool-call smoke test.

The ranking is re-parsed on every run — new/reordered rows and updated timings need no
script change. Only the per-model launch details (lms keys, GGUF paths, start commands)
live in the hand-maintained `LAUNCH_RECIPES` registry below, since the table can't carry
them. A model that enters a top-5 without a recipe is still listed (with timings) but is
not selectable until a ~6-line recipe is added.

Usage:
    python3 scripts/switch_top_model.py                       # interactive
    python3 scripts/switch_top_model.py --pick moe:1          # non-interactive
    python3 scripts/switch_top_model.py --pick moe:1 --dry-run  # print SSH cmds only
    python3 scripts/switch_top_model.py --pick moe:1 --debug  # per-step diagnostics on stderr
    python3 scripts/switch_top_model.py --list                # print the top-5 menus and exit
    python3 scripts/switch_top_model.py --ssh-host macstudio-ts --pick hybrid:1

On a `wait_ready` timeout the last lines of the target's remote log are tailed automatically
(even without --debug) — the timeout is the one place something is known-wrong and the log is
the only evidence. --debug additionally traces table parse, recipe match, every SSH call's
rc/stdout/stderr, readiness polls, and the smoke-test payload/response (API key always redacted).

Exit codes:
    0  switch + smoke test ok (or --list / --dry-run)
    1  selected model not on disk, or no recipe, or smoke test failed
    2  SSH / connection error
    3  benchmark table format changed — update parse_benchmark_table()
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
BENCH_TABLE = REPO_ROOT / "docs" / "models" / "benchmarks" / "model-benchmark-tool-call.md"

# Set from --debug in main(). When False, dbg() is a no-op and stdout is byte-identical
# to a non-debug run (debug output goes only to stderr).
DEBUG = False


def dbg(*parts):
    """Print a `[debug]` line to stderr; no-op unless --debug is set."""
    if DEBUG:
        print("[debug]", *parts, file=sys.stderr)


def _redact(key):
    """Render an API key safely for debug output — never the value (public mirror)."""
    if not key or key in ("not-needed", "<YOUR_API_KEY>"):
        return "(none)"
    return f"***redacted ({len(key)} chars)***"


def _trunc(text, cap=500):
    """Trim long captured output for debug; mark empty explicitly."""
    if text is None:
        return "(none)"
    text = text.strip()
    if not text:
        return "(empty)"
    return text if len(text) <= cap else text[:cap] + f"… (+{len(text) - cap} more)"

# Reuse the sibling helpers (probe / config sync). Same repo, same interpreter.
sys.path.insert(0, str(SCRIPTS_DIR))
import chk_llm_macstu as chk           # noqa: E402
import switch_opencode_config as swc   # noqa: E402

# Group heading (emoji-prefixed `#### ` lines) → canonical type key + menu label.
GROUP_HEADINGS = {
    "🧱": ("dense", "🧱 Dense"),
    "🧩": ("hybrid", "🧩 Hybrid MoE"),
    "🔀": ("moe", "🔀 MoE"),
}
TYPE_ORDER = ["dense", "hybrid", "moe"]

# One tool def, copied from scripts/bench/bench_api_tool_call.py TOOLS[0].
SMOKE_TOOL = {
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
}


# ---------------------------------------------------------------------------
# Launch registry — keyed by a distinctive substring of the table's model name.
# `server` = configs/clients/<folder> + label used by switch_opencode_config.
# `model_id` = served id (API /v1/models id AND opencode model_override).
# kind="lms"        → LM Studio guardrail-dance load by `lms_key`.
# kind="remote-cmd" → run `start_cmd` verbatim; availability-checked via `gguf_path`.
# `server_match` (optional) disambiguates rows that share a model name across servers.
# ---------------------------------------------------------------------------
LAUNCH_RECIPES = [
    # ---- 🔀 MoE ----
    {
        "match": "Huihui Gemma 4 26B A4B Abliterated",
        "server": "lm-studio", "port": 1234,
        "model_id": "gemma4-26b-a4b-huihui-abliterated-q6k",
        "kind": "lms", "lms_key": "huihui-gemma-4-26b-a4b-it-abliterated-i1",
        "context_length": 65536,
    },
    {
        "match": "TrevorJS Gemma 4 26B A4B Uncensored",
        "server": "lm-studio", "port": 1234,
        "model_id": "gemma4-26b-a4b-trevorjs-uncen-q8",
        "kind": "lms", "lms_key": "gemma-4-26b-a4b-it-uncensored",
        "context_length": 65536,
    },
    {
        "match": "lmstudio-community Gemma 4 26B A4B-it Q8_0",
        "server": "lm-studio", "port": 1234, "server_match": "lm-studio",
        "model_id": "gemma-4-26b-a4b-q8",
        "kind": "lms", "lms_key": "gemma-4-26b-a4b-it",
        "context_length": 65536,
    },
    {
        "match": "mlx-community Gemma 4 26B A4B-it 4-bit",
        "server": "lm-studio", "port": 1234,
        "model_id": "gemma-4-26b-a4b-it-mlx-4bit",
        "kind": "lms", "lms_key": "mlx-community/gemma-4-26b-a4b-it",
        "context_length": 65536, "no_guardrail": True,  # 14.57 GiB < 25% threshold
    },
    {
        "match": "lmstudio-community Gemma 4 26B A4B-it Q8_0",
        "server": "llama-cpp-mtp", "port": 8100, "server_match": "llama-cpp",
        "model_id": "gemma4-26b-a4b-q8-stock-llamacpp",
        "kind": "remote-cmd",
        "gguf_path": "~/.lmstudio/models/lmstudio-community/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-Q8_0.gguf",
        "start_cmd": (
            'GGUF=~/.lmstudio/models/lmstudio-community/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-Q8_0.gguf; '
            'nohup ~/llama-cpp-mainline/build/bin/llama-server -m "$GGUF" -ngl 99 -fa on -np 1 -c 65536 '
            '--host 0.0.0.0 --port 8100 --alias gemma4-26b-a4b-q8-stock-llamacpp --jinja '
            '> /tmp/llama-cpp-mtp.log 2>&1 &'
        ),
    },
    # ---- 🧩 Hybrid MoE ----
    {
        "match": "Huihui Qwen3.6-35B-A3B Claude-4.7-Opus abliterated MTP",
        "server": "llama-cpp-mtp", "port": 8100,
        "model_id": "huihui-qwen36-35b-mtp-abliterated-q6k",
        "kind": "remote-cmd",
        "gguf_path": "~/.cache/huggingface/hub/models--huihui-ai--Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF/snapshots/main/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-ggml-model-Q6_K.gguf",
        "start_cmd": (
            'GGUF=~/.cache/huggingface/hub/models--huihui-ai--Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF/snapshots/main/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-ggml-model-Q6_K.gguf; '
            'nohup ~/llama-cpp-mainline/build/bin/llama-server -m "$GGUF" -ngl 99 -fa on -np 1 -c 32768 '
            '--spec-type draft-mtp --spec-draft-n-max 2 --host 0.0.0.0 --port 8100 '
            '--alias huihui-qwen36-35b-mtp-abliterated-q6k --jinja --reasoning on '
            '> /tmp/llama-cpp-mtp.log 2>&1 &'
        ),
    },
    {
        "match": "unsloth Qwen3.6-35B-A3B UD-Q6_K",
        "server": "lm-studio", "port": 1234,
        "model_id": "qwen3.6-35b-a3b-ud-q6",
        "kind": "lms", "lms_key": "qwen3.6-35b-a3b",  # prefix-collides; --identifier pins API id
        "context_length": 65536,
    },
    {
        "match": "prithivMLmods Qwen3.6-35B-A3B Aggressive",
        "server": "lm-studio", "port": 1234,
        "model_id": "qwen3.6-35b-a3b-prithiv-aggressive-q6k",
        "kind": "lms", "lms_key": "qwen3.6-35b-a3b-uncensored-aggressive",
        "context_length": 65536,
    },
    {
        "match": "HauhauCS Qwen3.6-35B-A3B Aggressive",
        "server": "lm-studio", "port": 1234,
        "model_id": "qwen3.6-35b-a3b-uncensored-aggressive-q6kp",
        "kind": "lms", "lms_key": "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive",
        "context_length": 131072,
    },
    {
        "match": "Qwen3.6-35B-A3B Q6_K + TurboQuant",
        "server": "llama-cpp-turboquant", "port": 8099,
        "model_id": "qwen3.6-35b-a3b-turboquant-turbo3",
        "kind": "remote-cmd",
        "gguf_path": "~/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF",
        "start_cmd": (
            'GGUF=$(ls ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-35B-A3B-GGUF/snapshots/*/Qwen3.6-35B-A3B-UD-Q6_K.gguf); '
            'nohup ~/llama-cpp-thetom/build/bin/llama-server -m "$GGUF" '
            '--cache-type-k turbo3 --cache-type-v turbo3 -ngl 99 -fa on '
            '--host 0.0.0.0 --port 8099 --alias qwen3.6-35b-a3b-turboquant-turbo3 -c 65536 --jinja '
            '> /tmp/llama-cpp-thetom.log 2>&1 &'
        ),
    },
    # ---- 🧱 Dense ----
    {
        "match": "IBM Granite 4.1 30B Q8_0",
        "server": "lm-studio", "port": 1234,
        "model_id": "granite-4.1-30b-q8",
        "kind": "lms", "lms_key": "granite-4.1-30b",
        "context_length": 65536,
    },
    {
        "match": "Dolphin Venice 24B MLX-8bit",
        "server": "lm-studio", "port": 1234,
        "model_id": "dolphin-mistral-24b-venice-edition-mlx",
        "kind": "lms", "lms_key": "dolphin-mistral-24b-venice-edition-mlx",
        "context_length": 32768, "no_guardrail": True,  # 24B 8-bit fits comfortably
    },
    {
        "match": "TrevorJS Gemma 4 31B-it Uncensored",
        "server": "lm-studio", "port": 1234,
        "model_id": "gemma4-31b-it-uncensored-trevorjs-q4km",
        "kind": "lms", "lms_key": "gemma-4-31b-it-uncensored",
        "context_length": 65536,
    },
    {
        "match": "MiniCPM5-1B",
        "server": "sglang", "port": 30000,
        "model_id": "openbmb/MiniCPM5-1B",
        "kind": "remote-cmd",
        "gguf_path": None,  # HF checkpoint auto-resolved by SGLang; no single-file disk check
        "start_cmd": (
            'cd ~/sglang && . sglang-mps/bin/activate && '
            'nohup env SGLANG_USE_MLX=1 python -m sglang.launch_server '
            '--model-path openbmb/MiniCPM5-1B --tool-call-parser minicpm5 '
            '--host 0.0.0.0 --port 30000 > /tmp/sglang-minicpm5.log 2>&1 &'
        ),
    },
    {
        "match": "Dolphin 3.0 R1 Mistral 24B MLX-8bit",
        "server": "lm-studio", "port": 1234,
        "model_id": "dolphin3.0-r1-mistral-24b-mlxs",
        "kind": "lms", "lms_key": "dolphin3.0-r1-mistral-24b-mlxs",
        "context_length": 32768, "no_guardrail": True,
    },
]

# Stop EVERY LLM server before starting the target (Event-4-style hygiene → frees
# unified memory). Mirrors the CLAUDE.md pre-benchmark hygiene block, plus lms teardown.
STOP_ALL_CMD = (
    "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; "
    "pkill -f dflash-serve; pkill -f 'llama-cpp-mainline/build/bin/llama-server'; "
    "pkill -f 'llama-cpp-mtp/build/bin/llama-server'; "
    "pkill -f 'llama-cpp-turboquant/build/bin/llama-server'; "
    "pkill -f 'llama-cpp-thetom/build/bin/llama-server'; "
    "pkill -f 'mlx_lm.server'; pkill -f 'ds4-server'; pkill -f 'litert-lm serve'; "
    "pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'; pkill -9 osaurus 2>/dev/null; "
    "if [ -x ~/.lmstudio/bin/lms ]; then ~/.lmstudio/bin/lms unload --all 2>/dev/null; "
    "~/.lmstudio/bin/lms server stop 2>/dev/null; fi; "
    "/opt/homebrew/bin/brew services stop omlx 2>/dev/null; sleep 3"
)


# ---------- benchmark table parser ----------

def _clean_model_name(cell):
    """Strip medals, bold, turtle, and parenthetical asides from a Model cell."""
    s = cell
    for ch in ("🥇", "🥈", "🥉", "🏆", "🐢", "*"):
        s = s.replace(ch, "")
    s = re.sub(r"\(same GGUF[^)]*\)", "", s)  # the llama-cpp-mtp Gemma aside
    return s.strip()


def _first_seconds(cell):
    """First float immediately followed by an 's' unit; None on ⛔/no match."""
    if "⛔" in cell:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*s\b", cell)
    return float(m.group(1)) if m else None


def _locate_columns(header_cells):
    """Map required logical columns to indices by header substring (position-free)."""
    idx = {}
    for i, h in enumerate(header_cells):
        hl = h.lower()
        if "model" in hl and "model" not in idx:
            idx["model"] = i
        elif "server" in hl and "server" not in idx:
            idx["server"] = i
        elif "browse" in hl and "browse" not in idx:
            idx["browse"] = i
        elif "search" in hl and "search" not in idx:
            idx["search"] = i
    return idx


def _split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def parse_benchmark_table():
    """Return {type_key: [ {name, server, browse, search}, ... ]} for each group.

    Rows are sorted by browse wall ascending; browse-⛔ rows are dropped (ranking is
    browse-based). Fails loudly (exit 3) if the section or a column can't be found.
    """
    if not BENCH_TABLE.exists():
        print(f"Error: benchmark table not found at {BENCH_TABLE}", file=sys.stderr)
        sys.exit(3)
    lines = BENCH_TABLE.read_text().splitlines()

    # Find the `### OpenCode end-to-end` section and its end (next `### `).
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("### ") and "OpenCode end-to-end" in ln:
            start = i
            break
    if start is None:
        print("Error: '### OpenCode end-to-end' section not found — "
              "table format changed, update parse_benchmark_table()", file=sys.stderr)
        sys.exit(3)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("### "):
            end = i
            break
    dbg(f"table: '### OpenCode end-to-end' at line {start + 1} (section ends line {end})")
    section = lines[start:end]

    groups = {}
    cur_type = None
    cols = None
    for off, ln in enumerate(section):
        lineno = start + off + 1
        if ln.startswith("#### "):
            cur_type = None
            cols = None
            for emoji, (tkey, _label) in GROUP_HEADINGS.items():
                if emoji in ln:
                    cur_type = tkey
                    groups.setdefault(tkey, [])
                    dbg(f"table: group {emoji} {tkey} at line {lineno}")
                    break
            continue
        if cur_type is None or not ln.lstrip().startswith("|"):
            continue
        cells = _split_row(ln)
        # Header row: locate columns. Separator row: skip.
        if cols is None:
            if set(cells[0]) <= set(":- "):  # stray separator before header (unlikely)
                continue
            cols = _locate_columns(cells)
            missing = {"model", "server", "browse", "search"} - set(cols)
            if missing:
                print(f"Error: columns {sorted(missing)} not found in {cur_type} table header "
                      f"— update parse_benchmark_table()", file=sys.stderr)
                sys.exit(3)
            dbg(f"{cur_type}: columns " + " ".join(f"{k}={v}" for k, v in sorted(cols.items())))
            continue
        if set(cells[0]) <= set(":- "):  # the |:---|:---| separator
            continue
        need = max(cols.values())
        if len(cells) <= need:
            dbg(f"{cur_type}: skip (too-few-cells: {len(cells)} ≤ {need})")
            continue
        name = _clean_model_name(cells[cols["model"]])
        if not name:
            dbg(f"{cur_type}: skip (empty name)")
            continue
        browse = _first_seconds(cells[cols["browse"]])
        if browse is None:  # browse-⛔ → not rankable
            dbg(f"{cur_type}: skip '{name}' (browse ⛔ / no time)")
            continue
        server_cell = cells[cols["server"]].replace("**", "").strip()
        search = _first_seconds(cells[cols["search"]])
        dbg(f"{cur_type}: kept '{name}' browse={browse} search={search}")
        groups[cur_type].append({
            "name": name,
            "server": server_cell,
            "browse": browse,
            "search": search,
        })

    for tkey in groups:
        groups[tkey].sort(key=lambda r: r["browse"])
    return groups


def match_recipe(row):
    """Return the LAUNCH_RECIPES entry for a parsed row, or None."""
    name_l = row["name"].lower()
    server_l = row["server"].lower()
    for rec in LAUNCH_RECIPES:
        if rec["match"].lower() not in name_l:
            continue
        sm = rec.get("server_match")
        if sm and sm.lower() not in server_l:
            dbg(f"match: '{row['name']}' name-matched recipe '{rec['match']}' but "
                f"server_match '{sm}' ∉ '{row['server']}' — skipping (disambiguation)")
            continue
        sm_note = f" [server_match '{sm}']" if sm else ""
        dbg(f"match: '{row['name']}' → recipe '{rec['match']}' (server={rec['server']}){sm_note}")
        return rec
    return None


def top5(groups, tkey):
    rows = groups.get(tkey, [])[:5]
    out = []
    for r in rows:
        out.append((r, match_recipe(r)))
    return out


# ---------- presentation ----------

def fmt_secs(v):
    return f"{v:.2f}s" if v is not None else "—"


def print_menu(groups):
    for tkey in TYPE_ORDER:
        _, label = next(v for k, v in GROUP_HEADINGS.items() if v[0] == tkey)
        print(f"\n{label}")
        rows = top5(groups, tkey)
        if not rows:
            print("  (no rankable rows)")
            continue
        for n, (row, rec) in enumerate(rows, 1):
            tag = "" if rec else "   [no launch recipe — add to LAUNCH_RECIPES]"
            print(f"  {n}) {row['name']}  ·  {row['server']}  ·  "
                  f"browse {fmt_secs(row['browse'])} / search {fmt_secs(row['search'])}{tag}")


# ---------- selection ----------

def parse_pick(pick):
    m = re.match(r"^(dense|hybrid|moe):([1-5])$", pick.strip(), re.IGNORECASE)
    if not m:
        print(f"Error: --pick must be TYPE:N (TYPE ∈ dense|hybrid|moe, N ∈ 1-5); got '{pick}'",
              file=sys.stderr)
        sys.exit(1)
    return m.group(1).lower(), int(m.group(2))


def interactive_select(groups):
    if not sys.stdin.isatty():
        print("Error: not a TTY — pass --pick TYPE:N for non-interactive use", file=sys.stderr)
        sys.exit(1)
    print("Pick a model type:")
    for i, tkey in enumerate(TYPE_ORDER, 1):
        _, label = next(v for k, v in GROUP_HEADINGS.items() if v[0] == tkey)
        print(f"  {i}) {label}")
    raw = input("Type [1-3]: ").strip()
    if raw not in ("1", "2", "3"):
        print("Aborted.", file=sys.stderr)
        sys.exit(1)
    tkey = TYPE_ORDER[int(raw) - 1]
    rows = top5(groups, tkey)
    print(f"\nTop 5 {tkey} by browse wall (ascending):")
    for n, (row, rec) in enumerate(rows, 1):
        tag = "" if rec else "   [no launch recipe]"
        print(f"  {n}) {row['name']}  ·  {row['server']}  ·  "
              f"browse {fmt_secs(row['browse'])} / search {fmt_secs(row['search'])}{tag}")
    raw = input(f"Select [1-{len(rows)}]: ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(rows)):
        print("Aborted.", file=sys.stderr)
        sys.exit(1)
    return tkey, int(raw)


def resolve_selection(groups, tkey, n):
    rows = top5(groups, tkey)
    if n > len(rows):
        print(f"Error: {tkey} has only {len(rows)} ranked rows", file=sys.stderr)
        sys.exit(1)
    row, rec = rows[n - 1]
    if rec is None:
        print(f"\nSelected: {row['name']}", file=sys.stderr)
        print("No launch recipe for this model. Add a LAUNCH_RECIPES entry with:\n"
              '  match (substring of the table model name), server (configs/clients folder),\n'
              '  port, model_id (served id), kind ("lms"|"remote-cmd"), and either\n'
              '  lms_key+context_length (lms) or gguf_path+start_cmd (remote-cmd).', file=sys.stderr)
        sys.exit(1)
    return row, rec


# ---------- remote helpers ----------

def ssh(host, cmd, dry_run, timeout=600, check=False):
    if dry_run:
        print(f"[dry-run] ssh {host} \"{cmd}\"")
        return None
    # One-line echo (long pkill/start commands collapsed to first ~120 chars for readability).
    echo = cmd if len(cmd) <= 120 else cmd[:117] + "..."
    dbg(f"ssh {host}: {echo}")
    res = subprocess.run(["ssh", host, cmd], capture_output=True, text=True, timeout=timeout)
    dbg(f"  rc={res.returncode}  stdout={_trunc(res.stdout)}  stderr={_trunc(res.stderr)}")
    if check and res.returncode != 0:
        print(f"Error: remote command failed ({res.returncode}): {cmd}\n{res.stderr.strip()}",
              file=sys.stderr)
        sys.exit(2)
    return res


def check_on_disk(host, rec, dry_run):
    """True if the model is present on disk; False (with guidance) if missing."""
    if rec["kind"] == "lms":
        if dry_run:
            print(f"[dry-run] ssh {host} \"~/.lmstudio/bin/lms ls\"  # expect '{rec['lms_key']}'")
            return True
        dbg(f"check_on_disk(lms): ssh {host} \"~/.lmstudio/bin/lms ls\"")
        res = subprocess.run(["ssh", host, "~/.lmstudio/bin/lms ls"],
                             capture_output=True, text=True, timeout=30)
        key = rec["lms_key"].split("/")[-1].lower()
        listed = sum(1 for ln in res.stdout.splitlines() if ln.strip())
        if key in res.stdout.lower():
            dbg(f"  rc={res.returncode}  matched key '{key}' among {listed} listed lines")
            return True
        dbg(f"  rc={res.returncode}  key '{key}' NOT among {listed} listed lines; "
            f"lms ls=\n{_trunc(res.stdout, 800)}")
        print(f"Model not on disk in LM Studio (likely removed by storage cleanup).\n"
              f"  Expected lms key: {rec['lms_key']}\n"
              f"  Re-download, e.g.: lms get '{rec['lms_key']}'  (or hf_hub_download for custom quants)",
              file=sys.stderr)
        return False
    # remote-cmd
    gguf = rec.get("gguf_path")
    if not gguf:
        dbg(f"check_on_disk(remote-cmd): no gguf_path for '{rec['model_id']}' — "
            f"skipping disk check (HF checkpoint auto-resolves)")
        return True  # e.g. SGLang HF checkpoint auto-resolves; nothing to pre-check
    if dry_run:
        print(f"[dry-run] ssh {host} \"test -e {gguf}\"")
        return True
    dbg(f"check_on_disk(remote-cmd): ssh {host} \"test -e {gguf}\"")
    res = subprocess.run(["ssh", host, f"test -e {gguf} && echo OK || echo MISSING"],
                         capture_output=True, text=True, timeout=30)
    dbg(f"  rc={res.returncode}  → {res.stdout.strip() or '(no output)'}")
    if "OK" in res.stdout:
        return True
    print(f"Model not on disk (likely removed by storage cleanup).\n"
          f"  Expected path: {gguf}\n"
          f"  Re-download via huggingface-cli / the recipe's source repo.", file=sys.stderr)
    return False


def set_guardrail(host, mode, dry_run):
    """Flip LM Studio's modelLoadingGuardrails mode (off → load → high)."""
    one_liner = (
        "python3 -c \"import json,pathlib; p=pathlib.Path.home()/'.lmstudio/settings.json'; "
        "d=json.loads(p.read_text()); d.setdefault('modelLoadingGuardrails',{})['mode']='%s'; "
        "p.write_text(json.dumps(d, indent=2))\"" % mode
    )
    ssh(host, one_liner, dry_run, timeout=30)


def start_lms(host, rec, dry_run):
    guard = not rec.get("no_guardrail")
    if guard:
        set_guardrail(host, "off", dry_run)
    load = (f"~/.lmstudio/bin/lms load '{rec['lms_key']}' --gpu max "
            f"--context-length {rec['context_length']} --identifier '{rec['model_id']}' -y")
    ssh(host, load, dry_run, timeout=600)
    if guard:
        set_guardrail(host, "high", dry_run)
    ssh(host, "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors", dry_run, timeout=120)


def remote_log_path(rec):
    """Derive the recipe's log file from the `> /tmp/….log` redirect in its start_cmd."""
    m = re.search(r">\s*(/tmp/\S+\.log)", rec.get("start_cmd", ""))
    return m.group(1) if m else None


def tail_remote_log(host, rec, dry_run, lines=12, label="log-tail"):
    """Tail the recipe's remote log (best-effort). Used after launch (debug) and on timeout."""
    if dry_run:
        return
    log = remote_log_path(rec)
    if not log:
        return  # lms kind / no /tmp redirect — load errors already surface in the lms rc dump
    res = subprocess.run(["ssh", host, f"tail -n {lines} {log} 2>/dev/null"],
                         capture_output=True, text=True, timeout=20)
    body = res.stdout.strip()
    if not body:
        print(f"{label} {log}: (empty or absent)", file=sys.stderr)
        return
    print(f"{label} {log} (last {lines} lines):", file=sys.stderr)
    for ln in body.splitlines():
        print(f"  | {ln}", file=sys.stderr)


def start_remote_cmd(host, rec, dry_run):
    ssh(host, rec["start_cmd"], dry_run, timeout=120)
    if DEBUG and not dry_run:
        # nohup rc=0 says nothing — give the process a beat, then surface any immediate crash.
        dbg("rc=0 from nohup detaches the server; tailing log for immediate-crash evidence")
        time.sleep(1.5)
        tail_remote_log(host, rec, dry_run)


def wait_ready(host, host_ip, rec, dry_run, timeout=180):
    """Poll http://<ip>:<port>/v1/models until model_id appears.

    On timeout, tails the recipe's remote log (always-on, even without --debug) — the
    timeout is the one place something is known-wrong and the log is the only evidence.
    """
    if dry_run:
        print(f"[dry-run] poll http://{host_ip}:{rec['port']}/v1/models for '{rec['model_id']}'")
        return True
    url = f"http://{host_ip}:{rec['port']}/v1/models"
    start = time.time()
    deadline = start + timeout
    want = rec["model_id"]
    poll = 0
    while time.time() < deadline:
        poll += 1
        elapsed = time.time() - start
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                ids = [m.get("id") for m in json.loads(resp.read()).get("data", [])]
            if any(want == i or want in (i or "") or (i and i in want) for i in ids):
                dbg(f"wait_ready: poll#{poll} @{elapsed:.1f}s — target '{want}' present ✓")
                return True
            dbg(f"wait_ready: poll#{poll} @{elapsed:.1f}s — {len(ids)} ids; target absent")
        except Exception as e:
            dbg(f"wait_ready: poll#{poll} @{elapsed:.1f}s — {type(e).__name__}: {e}")
        time.sleep(3)
    # Timeout — surface the remote log regardless of --debug.
    tail_remote_log(host, rec, dry_run, label="readiness timeout — log-tail")
    return False


# ---------- config sync ----------

def sync_opencode(server_folder, model_id, dry_run):
    if dry_run:
        print(f"[dry-run] switch_opencode_config.switch_server('{server_folder}', "
              f"model_override='{model_id}')")
        return
    try:
        swc.switch_server(server_folder, model_override=model_id)
    except SystemExit as e:
        if e.code:  # model_override not in template → switch the server template anyway
            print(f"Note: '{model_id}' not in {server_folder} opencode template; "
                  f"switching server without model override.", file=sys.stderr)
            swc.switch_server(server_folder)


# ---------- smoke test ----------

def smoke_test(host_ip, rec, api_key, dry_run):
    url = f"http://{host_ip}:{rec['port']}/v1/chat/completions"
    if dry_run:
        print(f"[dry-run] POST {url}  (tool_choice=auto, prompt 'Read the file /tmp/notes.txt')")
        return True
    payload = {
        "model": rec["model_id"],
        "messages": [{"role": "user", "content": "Read the file /tmp/notes.txt"}],
        "tools": [SMOKE_TOOL],
        "tool_choice": "auto",
        "max_tokens": 512,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key and api_key not in ("not-needed", "<YOUR_API_KEY>"):
        headers["Authorization"] = f"Bearer {api_key}"
    dbg(f"smoke: POST {url}  (Authorization: Bearer {_redact(api_key)})")
    dbg(f"smoke: payload model={rec['model_id']} tools=[read_file] "
        f"tool_choice=auto max_tokens=512 stream=False")
    for attempt in (1, 2):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            if attempt == 1:
                print(f"Smoke test attempt 1 failed ({e}); retrying after cold-start...",
                      file=sys.stderr)
                time.sleep(5)
                continue
            print(f"Smoke test failed: {e}", file=sys.stderr)
            return False
        dt = time.time() - t0
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {})
        tcs = msg.get("tool_calls") or []
        dbg(f"smoke: attempt {attempt} HTTP 200  finish_reason={choice.get('finish_reason')}  "
            f"tool_calls={len(tcs)}  ({dt:.2f}s)")
        if tcs or choice.get("finish_reason") == "tool_calls":
            if tcs:
                fn = tcs[0].get("function", {})
                print(f"Smoke test PASS: tool '{fn.get('name')}' args={fn.get('arguments')} "
                      f"({dt:.2f}s)")
            else:
                print(f"Smoke test PASS: finish_reason=tool_calls ({dt:.2f}s)")
            return True
        if attempt == 1:
            print("Smoke test attempt 1: no tool call; retrying...", file=sys.stderr)
            time.sleep(2)
            continue
        print(f"Smoke test FAIL: no tool_calls in response (finish_reason="
              f"{choice.get('finish_reason')})", file=sys.stderr)
        dbg("smoke: raw response =\n" + _trunc(json.dumps(data, ensure_ascii=False), 1024))
    return False


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ssh-host", default="macstudio", help="SSH alias (default: macstudio)")
    ap.add_argument("--pick", help="Non-interactive selection TYPE:N (e.g. moe:1)")
    ap.add_argument("--list", action="store_true", help="Print the top-5 menus and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print every remote command instead of running it")
    ap.add_argument("--debug", action="store_true",
                    help="Per-step diagnostics on stderr (table parse, recipe match, every SSH "
                         "rc/stdout/stderr, readiness polls, smoke payload/response; key redacted)")
    ap.add_argument("--no-smoke", action="store_true", help="Skip the tool-call smoke test")
    args = ap.parse_args()

    global DEBUG
    DEBUG = args.debug

    groups = parse_benchmark_table()

    if args.list:
        print_menu(groups)
        return 0

    if args.pick:
        tkey, n = parse_pick(args.pick)
    else:
        tkey, n = interactive_select(groups)

    row, rec = resolve_selection(groups, tkey, n)
    print(f"\n→ {row['name']}  ({rec['server']} :{rec['port']}, id={rec['model_id']})")
    print(f"  benchmark: browse {fmt_secs(row['browse'])} / search {fmt_secs(row['search'])}\n")

    host = args.ssh_host

    # Resolve the live Mac Studio IP + key from the OpenCode config (for HTTP probes).
    live_cfg = chk.load_opencode_config()
    host_ip = chk.extract_real_ip(live_cfg) or host
    api_key = chk.extract_api_key(live_cfg)
    dbg(f"live config: ip={host_ip}  api_key={_redact(api_key)}")

    timings = {}

    # 1) Already up with the target model loaded? Skip straight to config sync.
    if not args.dry_run:
        probe_data = chk.probe(host)
        identified = chk.identify_servers(probe_data, [rec["port"]])
        entry = identified[0]
        dbg(f"probe: port {rec['port']} up={entry['up']} server={entry.get('server')}")
        if entry["up"] and entry.get("server") == rec["server"]:
            avail = chk.fetch_models(f"http://{host_ip}:{rec['port']}/v1", api_key=api_key) or []
            if any(rec["model_id"] == i or rec["model_id"] in (i or "") for i in avail):
                dbg(f"probe: target '{rec['model_id']}' already loaded → config sync only")
                print("Target server + model already running — syncing OpenCode config only.")
                sync_opencode(rec["server"], rec["model_id"], args.dry_run)
                if args.no_smoke:
                    return 0
                return 0 if smoke_test(host_ip, rec, api_key, args.dry_run) else 1
            dbg(f"probe: {len(avail)} ids listed; target absent → full switch")

    # 2) Availability guard — before stopping anything.
    if not check_on_disk(host, rec, args.dry_run):
        print("\nRunning server left untouched. Aborting.", file=sys.stderr)
        return 1

    # 3) Stop all LLM servers (free unified memory).
    print("Stopping all LLM servers...")
    t = time.time()
    ssh(host, STOP_ALL_CMD, args.dry_run, timeout=120)
    timings["stop"] = time.time() - t
    dbg(f"phase 'stop' took {timings['stop']:.1f}s")

    # 4) Start the target.
    print(f"Starting {rec['server']}...")
    t = time.time()
    if rec["kind"] == "lms":
        start_lms(host, rec, args.dry_run)
    else:
        start_remote_cmd(host, rec, args.dry_run)
    timings["load"] = time.time() - t
    dbg(f"phase 'load' took {timings['load']:.1f}s")

    # 5) Readiness.
    print("Waiting for readiness...")
    t = time.time()
    ready = wait_ready(host, host_ip, rec, args.dry_run)
    timings["readiness"] = time.time() - t
    dbg(f"phase 'readiness' took {timings['readiness']:.1f}s")
    if not ready:
        print(f"Error: {rec['model_id']} did not appear on "
              f"http://{host_ip}:{rec['port']}/v1/models within 180s", file=sys.stderr)
        return 1

    # 6) Sync OpenCode config.
    print("Syncing OpenCode config...")
    sync_opencode(rec["server"], rec["model_id"], args.dry_run)

    # 7) Smoke test.
    if args.no_smoke:
        print("Done (smoke test skipped).")
        dbg("total wall " + "  ".join(f"{k} {v:.1f}s" for k, v in timings.items()))
        return 0
    print("Running tool-call smoke test...")
    t = time.time()
    ok = smoke_test(host_ip, rec, api_key, args.dry_run)
    timings["smoke"] = time.time() - t
    print("\nDone." if ok else "\nSwitched, but smoke test did not confirm a tool call.")
    dbg("total wall " + "  ".join(f"{k} {v:.1f}s" for k, v in timings.items()))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
