Status: active
Created: 2026-05-04
Canonical: no

# Plan: `chk_llm_macstu.py` — Mac Studio LLM server + model status probe

> **Naming convention note:** Mirrors the user's `list-rm-model-macstu` skill shape (`<verb>_<noun>_macstu`), adapted to repo script convention (snake_case, `.py`). Establishes `<verb>_llm_macstu.py` as a future namespace for related ops scripts (e.g. potential siblings `bench_llm_macstu.py`, `clean_llm_macstu.py`).

## Context

The Mac Studio runs **one of four port-8000 servers** at a time (vllm-mlx, mlx-openai-server, oMLX, vmlx) plus optionally **llmster** (LM Studio :1234) and **dflash-mlx** (:8098). Today the only way to answer "what's running right now?" is the manual sequence I just ran by hand for the user:

```bash
ssh macstudio "ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep"
ssh macstudio "lsof -iTCP -sTCP:LISTEN -P | grep -E ':(8000|8098|1234) '"
ssh macstudio "curl -s http://localhost:1234/v1/models | python3 -m json.tool"
ssh macstudio "/Users/chanunc/.lmstudio/bin/lms ps"
```

Four SSH round-trips, three different output formats, and the LM Studio gotcha that `/v1/models` lists *available* models (not loaded — `lms ps` is the only way to see what's actually in RAM).

This is also the **Event 4 pre-benchmark hygiene** check (CLAUDE.md:185-203): before a "deploy and benchmark" run we have to confirm no other server is hogging port 8000 / unified memory. A scripted probe makes that check one command instead of four, and gives `/deploy-run-benchmark-uncen-model` and `/list-rm-model-macstu` a clean primitive to call.

The intended outcome: `python3 scripts/chk_llm_macstu.py` prints (or JSON-emits) the live state in under ~2 s, identifying the active server by process pattern, the loaded model via the right per-server API, and any LLM-related stragglers.

## Recommended approach

**One new file, one doc update.** No subdir. No new dependencies (stdlib only — matches `switch_opencode_config.py` and `bench_api_server.py`).

### File 1 (new): `scripts/chk_llm_macstu.py`

Top-level operational helper, peer of `scripts/switch_opencode_config.py`. Python 3, stdlib-only, `subprocess.run(['ssh', host, …])` over a configurable SSH alias.

**Probe order** (single SSH round-trip, batched via `ssh macstudio "cmd1; echo ---SEP---; cmd2; …"` to avoid four serial connects):

1. **Processes** — `ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms server|omlx_server' | grep -v grep`
2. **Listening ports** — `lsof -iTCP -sTCP:LISTEN -P -n | grep -E ':(8000|8098|1234) '`
3. **LM Studio loaded model** (only if 1234 listening) — `~/.lmstudio/bin/lms ps`
4. **Per-port `/v1/models`** (only for ports listening) — `curl -s -m 3 http://localhost:<port>/v1/models` (oMLX gets `-H "Authorization: Bearer <YOUR_API_KEY>"`; key fetched from local `~/.config/opencode/opencode.json` via the same `extract_api_key` pattern in `switch_opencode_config.py:44-49`)

**Server identity table** (process pattern → server name; baked in as a constant):

| Port | Process pattern (`pgrep -f`) | Server label |
|:--|:--|:--|
| 8000 | `vllm-mlx` | `vllm-mlx` |
| 8000 | `mlx-openai-server` | `mlx-openai-server` |
| 8000 | `vmlx_engine` | `vmlx` |
| 8000 | `omlx_server` (or owner=omlx via lsof) | `oMLX` |
| 1234 | `lms server` (or LM Studio app) | `llmster` |
| 8098 | `dflash-serve` | `dflash-mlx` |

**Default plain-text output** (mirrors what I just wrote out for the user manually, so the script's first run is a regression-free replacement for the by-hand answer):

```
Mac Studio LLM status (via macstudio)
=====================================

Port 8000 — DOWN
Port 1234 — llmster (LM Studio)
  Process  : PID 6006, RSS 1.18 GB  (LM Studio app)
  Loaded   : gemma4-26b-a4b-trevorjs-uncen-q8  (IDLE, 26.86 GB, 65536 ctx)
  Available: 10 models via /v1/models  (use --verbose to list)
Port 8098 — DOWN

Other LLM processes:
  PID 84238  113 MB  lms log stream --source server
```

**Flags** (argparse, mutually-exclusive group not needed — flags compose):

| Flag | Behavior |
|:--|:--|
| `--ssh-host HOST` | SSH alias, default `macstudio` (use `macstudio-ts` over Tailscale) |
| `--no-ssh` | Run probes locally — for invocation directly on the Mac Studio (the future `/deploy-run-benchmark-uncen-model` skill may want this) |
| `--json` | Emit a single JSON object instead of plain text (for skill consumption / piping into `jq`) |
| `--verbose` | Plain-text mode: list all available models per port (default suppresses the long list) |
| `--ports 8000,1234,8098` | Override probed port set (default: all three) |
| `--client {opencode,pi,openclaw,qwen-code,claude-code,all}` | After detecting the running server, **emit the matching client config** from `configs/clients/<detected-server>/<client>.<ext>` resolved with the live `<MAC_STUDIO_IP>` + `<YOUR_API_KEY>` (same placeholder replacement as `switch_opencode_config.py:60-67`). Suppresses the status report — emits raw JSON to stdout so it can be redirected: `... --client opencode > ~/.config/opencode/opencode.json`. With `all`, emits a JSON object keyed by client name. With `--json` *and* `--client`, the output is `{"server": …, "client": …, "config": {...}}` so callers can keep both pieces of info. |
| `--logs` | After detecting the running server, **emit the shell command** to follow that server's log (so the user can see prompt/tool-call activity in real time while testing the model). Prints to stdout; suppresses the status report. Examples: `ssh macstudio "tail -f /tmp/vllm-mlx.log"`, `ssh macstudio "~/.lmstudio/bin/lms log stream --source server"`. Pair with `eval $(...)` to attach immediately, or copy-paste into a second terminal. |
| `--all` | **Bundle everything into one report**: detected server, port, base URL, loaded model, full available-models list, every client config that exists for that server (resolved with placeholders), and the log-view command. **Default output is pretty text formatted for easy line-by-line copy** (one fact per line, dividers between sections, single-line shell commands the user can triple-click and paste). Pair with `--json` to get a machine-readable object/array instead. Mutually exclusive with `--client` and `--logs` (those are subset-emit modes; `--all` is the superset). If multiple servers are up, prints one block per server (text mode) or an array of per-port objects (`--json` mode); no `--port` disambiguation needed. |

**`--client` flag mapping** (built-in constant, mirrors the per-server file names already in `configs/clients/<server>/`):

| `--client` value | Source filename under `configs/clients/<server>/` |
|:--|:--|
| `opencode` | `opencode.json` |
| `pi` | `pi-models.json` |
| `openclaw` | `openclaw-provider.json` |
| `qwen-code` | `qwen-code-settings.json` |
| `claude-code` | `claude-code-settings.json` |
| `all` | every file present for that server |

**`--logs` per-server log location** (built-in constant; sourced from CLAUDE.md "View logs" Common Commands block):

| Detected server | Emitted command |
|:--|:--|
| `vllm-mlx` | `ssh <host> "tail -f /tmp/vllm-mlx.log"` |
| `mlx-openai-server` | `ssh <host> "tail -f /tmp/mlx-openai-server.log"` |
| `oMLX` | `ssh <host> "tail -f ~/.omlx/logs/server.log"` |
| `vmlx` | `ssh <host> "tail -f /tmp/vmlx.log"` |
| `dflash-mlx` | `ssh <host> "tail -f /tmp/dflash-mlx.log"` |
| `llmster` | `ssh <host> "~/.lmstudio/bin/lms log stream --source server"` (no flat log file — LM Studio streams via the `lms` CLI; this matches the persistent `lms log stream` process already alive on the box, PID 84238 in today's snapshot) |

When `--no-ssh` is set, the `ssh <host> "..."` wrapper is dropped — emit the inner command directly.

**`--all` text format** (default — designed for triple-click line copying):

```
Mac Studio LLM status (via macstudio)
=====================================

Server   : llmster (LM Studio)
Port     : 1234
Base URL : http://192.168.1.104:1234/v1
PID      : 6006
RSS      : 1.18 GB

Loaded model
------------
ID       : gemma4-26b-a4b-trevorjs-uncen-q8
Name     : gemma-4-26b-a4b-it-uncensored
Status   : IDLE
Size     : 26.86 GB
Context  : 65536

Logs (copy and run)
-------------------
ssh macstudio "~/.lmstudio/bin/lms log stream --source server"

Available models (10)
---------------------
  - gemma4-26b-a4b-trevorjs-uncen-q8
  - gemma-4-26b-a4b-it-uncensored
  - gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct
  - qwen3.6-40b-claude-4.6-opus-deckard-heretic-uncensored-thinking-neo-code-di-imatrix-max
  - …

Client configs
--------------
opencode  →  ~/.config/opencode/opencode.json
  Apply: python3 scripts/switch_opencode_config.py --server llmster
  Or paste below into the file:

  {
    "model": "...",
    "provider": { … resolved opencode.json … }
  }

(no pi-models.json template for llmster — opencode-only today)
```

Format rules:
- Every shell command sits on its own line with no leading indentation, so triple-click selects exactly the command.
- `key : value` rows align colons to the longest key per section.
- JSON config blocks are 2-space indented (matches the in-repo templates).
- Multi-server case prints the same block per server, separated by a single blank line and a `===` divider.
- All text goes to stdout; warnings (e.g. "API key fell back to not-needed") to stderr so they don't pollute copy-paste.

**`--all --json` schema** (single-server case; multi-server is an array of these):
```json
{
  "ssh_host": "macstudio",
  "port": 1234,
  "server": "llmster",
  "processes": [{"pid": 6006, "rss_bytes": 1268000000, "command": "..."}],
  "loaded_model": {
    "id": "gemma4-26b-a4b-trevorjs-uncen-q8",
    "model": "gemma-4-26b-a4b-it-uncensored",
    "status": "IDLE",
    "size_bytes": 28842000000,
    "context": 65536
  },
  "available_models": ["gemma4-26b-a4b-trevorjs-uncen-q8", "..."],
  "clients": {
    "opencode": { "...resolved opencode.json contents..." }
  },
  "logs_command": "ssh macstudio \"~/.lmstudio/bin/lms log stream --source server\""
}
```

Fields are `null` when not applicable (e.g. `loaded_model: null` for a port-8000 server with no `lms ps` analog; `clients: {}` if no templates exist for the detected server).

**Edge cases for `--client` and `--logs`** (shared — both modes do detection-then-emit):
- **No server up** — exit 1 with stderr `"no LLM server detected; cannot emit <client config|logs command>"`. Don't fall back to a "default" server.
- **Detected server has no template for the requested client** (`--client` only) — exit 3 with stderr listing what *is* available (matches the llmster reality today: opencode-only, per CLAUDE.md "currently OpenCode-only — full client config set is deferred unless llmster graduates to permanent server status"). Don't silently emit an empty config.
- **Multiple servers up** (port 8000 + llmster + dflash-mlx all running) — both `--client` and `--logs` require `--port N` to disambiguate; without it, exit 3 and tell the user which ports are up so they can pick. (In status mode the multi-server case just renders all rows — no ambiguity to resolve.)
- **API-key extraction failure** (`--client` only) — same fallback as `switch_opencode_config.py:62-66`: substitute `"not-needed"` for `<YOUR_API_KEY>` and emit a stderr warning.
- **`--client`, `--logs`, and `--all` mutual exclusion** — argparse `add_mutually_exclusive_group()`; pick one emit-mode at a time. (Status mode is the default when none of the three is set.)
- **`--all` with no servers up** — emits `[]` (empty array) and exits 1, so callers can `jq 'length > 0'` to gate next steps. Stderr message: `"no LLM servers detected"`.

**Exit codes**:
- `0` — status mode: at least one known LLM server is up; `--client` / `--logs` mode: emission succeeded
- `1` — no known LLM server up (useful as `if ! chk_llm_macstu.py; then ...` in pre-benchmark hygiene)
- `2` — SSH / connection error (couldn't even probe)
- `3` — `--client` mode: detected server has no template for the requested client; or `--client` / `--logs` mode with multiple servers up and no `--port` given

**Stylistic patterns to copy directly** (no novelty):
- Module docstring + usage block: `scripts/switch_opencode_config.py:1-13`
- `subprocess.run([..., capture_output=True, text=True])` + stderr error path: `scripts/switch_opencode_config.py:28-32`
- API-key extraction from live OpenCode config: `scripts/switch_opencode_config.py:44-49`
- Placeholder resolution (`<MAC_STUDIO_IP>`, `<YOUR_API_KEY>`) for `--client` output: `scripts/switch_opencode_config.py:60-67` — copy-paste, don't `from switch_opencode_config import` (sibling-script imports are brittle when run from different cwds)
- `urllib.request` + 3 s timeout for `/v1/models`: `scripts/bench/bench_api_server.py:42-45` (no httpx/requests dep)
- Argparse skeleton + `if __name__ == "__main__": main()`: `scripts/switch_opencode_config.py:185-203`

### File 2 (edit): `scripts/README.md`

Per CLAUDE.md Event 5 (line 227-234), a new top-level script needs a README entry — and that's it. No `docs/servers/<x>/maintenance.md` link (not a patch), no `docs/models/README.md` table row (not a benchmark).

Two edits, both small:

1. **Layout table** ([`scripts/README.md:7-11`](../../cc-prjs/cc-claude/setup-llm-macstu/scripts/README.md)) — add a row:
   ```
   | `chk_llm_macstu.py` | Probes the Mac Studio over SSH and reports which LLM server + model is currently running on ports 8000 / 1234 / 8098. |
   ```
2. **New "Status Checks" section** between Layout and Benchmarks — single-row table linking to the script with one-line purpose. Mirrors the Benchmarks/Patches sections' shape exactly so future status scripts have an obvious home. Skip the "Save raw output…" line (status checks aren't archived).

No other docs touched. No CLAUDE.md / AGENTS.md / README.md edits — Event 5 is explicit that script additions are confined to `scripts/README.md` unless the script is a patch (link from a server runbook) or benchmark (link from `docs/models/README.md`); this is neither.

### Files NOT modified (intentional)

- `README.md`, `CLAUDE.md`, `AGENTS.md` — Event 5 doesn't require it; the script is operator-facing tooling, not a workflow change. (If future skills come to depend on it as a primitive — e.g., `/deploy-run-benchmark-uncen-model` calling it for hygiene — *that* change would update CLAUDE.md's Event 4 snippet to reference it.)
- `configs/`, `docs/servers/`, `docs/current.md` — no live state changes.
- `~/.claude/skills/list-rm-model-macstu/` — the skill's `inventory.sh` covers a different question (what models are *on disk*, not what's *running*); they're complementary, not overlapping. No edit.

## Verification

End-to-end test sequence (the script should reproduce the manual answer I gave above):

1. **Smoke test (current state, llmster up)**:
   ```bash
   python3 scripts/chk_llm_macstu.py
   # Expect: Port 1234 row showing TrevorJS Gemma 4 26B A4B uncensored Q8 IDLE,
   #         Ports 8000 + 8098 DOWN, lms-log-stream as a stragler.
   # Exit code: 0
   ```
2. **JSON contract**:
   ```bash
   python3 scripts/chk_llm_macstu.py --json | python3 -m json.tool
   # Expect: dict with `ssh_host`, `ports` (keyed by port), `other_processes` keys.
   #         Each port entry: `up`, `server`, `processes`, `loaded_model`, `available_models`.
   ```
3. **Verbose listing**:
   ```bash
   python3 scripts/chk_llm_macstu.py --verbose
   # Expect: full list of llmster's ~10 available models below the Loaded line.
   ```
4. **`--client` resolution (happy path)**:
   ```bash
   python3 scripts/chk_llm_macstu.py --client opencode | python3 -m json.tool
   # Expect: configs/clients/llmster/opencode.json with <MAC_STUDIO_IP> + <YOUR_API_KEY>
   #         resolved from ~/.config/opencode/opencode.json. Exit 0.
   diff <(python3 scripts/chk_llm_macstu.py --client opencode) \
        <(python3 -c "import json,subprocess; \
          subprocess.run(['python3','scripts/switch_opencode_config.py','--server','llmster'])")
   # Expect: emitted config matches what switch_opencode_config.py would have written.
   ```
5. **`--client` missing-template path** (llmster has only opencode today):
   ```bash
   python3 scripts/chk_llm_macstu.py --client pi
   # Expect: stderr "llmster has no pi-models.json template; available: opencode",
   #         exit 3.
   ```
6. **`--client all`**:
   ```bash
   python3 scripts/chk_llm_macstu.py --client all | python3 -m json.tool
   # Expect: JSON object with one key per client config present for the detected
   #         server (today: just "opencode" for llmster).
   ```
7. **`--logs` emission**:
   ```bash
   python3 scripts/chk_llm_macstu.py --logs
   # Expect: ssh macstudio "~/.lmstudio/bin/lms log stream --source server"
   eval $(python3 scripts/chk_llm_macstu.py --logs)
   # Expect: live LM Studio log stream attaches; Ctrl-C exits cleanly.
   python3 scripts/chk_llm_macstu.py --no-ssh --logs
   # Expect: ~/.lmstudio/bin/lms log stream --source server  (no ssh wrapper).
   ```
8. **`--all` text bundle (copy-friendly default)**:
   ```bash
   python3 scripts/chk_llm_macstu.py --all
   # Expect: pretty-text block matching the format spec above —
   #         Server/Port/Base URL/PID/RSS rows, Loaded model section,
   #         Logs command on its own line, Available models bullet list,
   #         Client configs section with opencode entry + Apply hint + JSON body.
   # Exit 0.
   ```
9. **`--all --json` machine-readable**:
   ```bash
   python3 scripts/chk_llm_macstu.py --all --json | python3 -m json.tool
   # Expect: array with one object for llmster (today's only running server) containing
   #         server, port, base_url, loaded_model, available_models,
   #         clients.opencode (resolved), logs_command. Exit 0.
   python3 scripts/chk_llm_macstu.py --all --json | jq '.[0].logs_command'
   # Expect: "ssh macstudio \"~/.lmstudio/bin/lms log stream --source server\""
   python3 scripts/chk_llm_macstu.py --all --json | jq '.[0].clients | keys'
   # Expect: ["opencode"]   (only client config llmster ships today)
   ```
10. **Negative path — port-8000 server down (status quo)**: already covered by smoke test.
11. **Negative path — everything down**: requires temporarily stopping llmster, which kicks the user's main model out of RAM. **Skip in normal verification**; document the expected behavior in the docstring instead. If the user wants a true full-stop test, do it once before they start the next deploy-and-benchmark (the hygiene step kills everything anyway).
12. **SSH-failure path**:
    ```bash
    python3 scripts/chk_llm_macstu.py --ssh-host nonexistent-host
    # Expect: stderr "ssh: Could not resolve hostname …", exit 2.
    ```
13. **Local mode (skipped today)**: `--no-ssh` would only get exercised when invoked on the Mac Studio itself. Validate later if/when a skill calls it that way.
14. **Pre-commit drift check**:
   ```bash
   grep -rn "chk_llm_macstu" --include="*.md" --include="*.json" --include="*.py" .
   # Expect: only the new script and its scripts/README.md row.
   ```

## Critical files

| Path | Why critical |
|:--|:--|
| `scripts/chk_llm_macstu.py` (new) | The script itself |
| `scripts/README.md` | Event-5-mandated index update |
| `scripts/switch_opencode_config.py` | Stylistic template — argparse, SSH subprocess, API-key extraction |
| `scripts/bench/bench_api_server.py` | Stylistic template — `urllib.request` `/v1/models` probe with timeout |
| `~/.claude/skills/list-rm-model-macstu/inventory.sh` | Sibling probe (disk inventory) — confirms scope-non-overlap; no shared code |
| `CLAUDE.md:227-234` (Event 5) | Sync-policy rule that confines doc updates to `scripts/README.md` |
| `CLAUDE.md:185-203` (Event 4) | Future caller — pre-benchmark hygiene may grow a `chk_llm_macstu.py` reference once the script exists |
