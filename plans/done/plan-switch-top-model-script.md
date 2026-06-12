# Plan: `scripts/switch_top_model.py` — switch Mac Studio to a top-5 fastest OpenCode-benchmark model

Status: done
Created: 2026-06-11
Completed: 2026-06-12
Canonical: no

Related: [`plan-switch-server.md`](plan-switch-server.md) is an older generic profile-registry
switcher design (vllm-mlx/vmlx era, not implemented). This plan is narrower and benchmark-driven:
selection comes from the live OpenCode benchmark table, not a static profile list, and it adds
OpenCode client sync + a tool-call smoke test.

## Context

The lab cycles through many server/model combos. The OpenCode end-to-end benchmark table
(`docs/models/benchmarks/model-benchmark-tool-call.md` §"OpenCode end-to-end")
already ranks every model by real agent-loop speed, but switching to one of the fast models is a
manual multi-step SSH dance (stop whatever holds the port, guardrail flip for lm-studio, exact
GGUF paths, parser flags). This script turns that into one interactive command: pick a model type,
pick one of the top-5 fastest in that group, and the script stops the running server, starts the
right one, syncs the OpenCode client config, and smoke-tests a tool call.

User decisions (AskUserQuestion, 2026-06-11):
- **Step 0 = pick model type** (🧱 Dense / 🧩 Hybrid MoE / 🔀 MoE), then top 5 *within* that group, ranked by **browse wall time ascending** (the table's own ordering).
- **Yes, sync OpenCode config** after the switch (reuse `switch_opencode_config.py`).

## Overview

- New script `scripts/switch_top_model.py` (top-level helper, Event 5)
- Dynamic parse of the three OpenCode end-to-end group tables → top-5 menu per group
- Hardcoded `LAUNCH_RECIPES` registry mapping known table rows → server stop/start commands
- Running-server detection + stop via reused `chk_llm_macstu.py` functions
- On-disk availability check (storage-cleanup guard) before stopping anything
- OpenCode config sync via reused `switch_opencode_config.py` functions
- Single tool-call smoke test against the new `/v1/chat/completions` endpoint
- `scripts/README.md` index row

## New file: `scripts/switch_top_model.py`

Stdlib-only (argparse, json, re, subprocess, urllib), same style as `chk_llm_macstu.py`.

### Step 1 — Parse the benchmark table (dynamic, no hardcoded ranking)

- Read `docs/models/benchmarks/model-benchmark-tool-call.md`, locate the
  `### OpenCode end-to-end` section, then the three `#### 🧱 Dense` / `#### 🧩 Hybrid MoE` / `#### 🔀 MoE` subsections.
- Per table row extract: model name (strip `🥇🥈🥉` medals and `**`), server cell, browse wall
  seconds, search wall seconds. Regex the first float before "s" in each metric cell
  (cells contain noise like `6.63 s _(initial 10.08)_ / 5.41 s`).
- Skip rows whose metric cells contain `⛔` (failures: magnum, ZAYA1, MiMo search-fail stays — skip only if *browse* is ⛔, since ranking is browse-based).

**Robustness to future table edits** (the table changes with every benchmark):
- Ranking is re-parsed on every run — new/reordered rows and updated timings need no script change.
- Columns are located **by header name** (`Model` / `Server` / `Browse` / `Search` substring match on the header row), not by position, so adding or reordering columns doesn't break parsing.
- If a section heading or required column can't be found, fail loudly (`table format changed — update parse_benchmark_table()`), never silently mis-rank.
- A new model entering a top 5 without a registry entry is still *listed* (with its timings) but marked `[no launch recipe — add to LAUNCH_RECIPES]`; selecting it prints what a recipe entry needs. Only the ~6-line recipe must be added by hand — paths/lms keys can't come from the table.

### Step 2 — Interactive selection

1. Prompt 1: model type — `1) Dense  2) Hybrid MoE  3) MoE`.
2. Prompt 2: top 5 of that group by browse wall ascending, e.g.
   `1) Huihui Gemma 4 26B A4B Abliterated i1-Q6_K   lm-studio   browse 2.55s / search 19.59s`.
   Rows without a `LAUNCH_RECIPES` match are listed but marked `[no launch recipe]` and not selectable.
3. `--pick TYPE:N` / non-TTY guard for scripted use; `--dry-run` prints every remote command instead of running it.

### Step 3 — Launch registry (`LAUNCH_RECIPES`)

Table rows can't carry GGUF paths / lms keys, so recipes are keyed by a distinctive
**substring of the table's model name** (parse stays dynamic; registry covers known models).
Recipe fields:

```python
{
  "match": "Huihui Gemma 4 26B A4B Abliterated",   # substring vs parsed model name
  "server": "lm-studio",                            # label + configs/clients/<folder>
  "port": 1234,
  "model_id": "gemma4-26b-a4b-huihui-abliterated-q6k",  # served id → API + opencode model_override
  "kind": "lms",                                    # "lms" | "remote-cmd"
  "lms_key": "huihui-gemma-4-26b-a4b-it-abliterated-i1",
  "context_length": 65536,
  # for kind="remote-cmd":
  # "gguf_path": "~/.cache/huggingface/.../model.gguf",  (availability check + start cmd)
  # "start_cmd": "nohup ~/llama-cpp-mainline/build/bin/llama-server ... &",
}
```

Entries to ship (the top-5 of each group as of 2026-06-11; exact lms keys / paths already documented):

**MoE:** Huihui Gemma 26B (`lms_key` + identifier above, from `docs/models/uncen-model/gemma4-26b-a4b-huihui-abliterated-benchmark.md:62`), TrevorJS Gemma 26B (`gemma-4-26b-a4b-it-uncensored` → `gemma4-26b-a4b-trevorjs-uncen-q8`, writeup :50), lmstudio-community Gemma Q8_0 on lm-studio (prefix `gemma-4-26b-a4b-it`; key-collision caveat at model-benchmark-tool-call.md:265), mlx-community Gemma 4-bit (`mlx-community/gemma-4-26b-a4b-it` → `gemma-4-26b-a4b-it-mlx-4bit`, :1621), lmstudio-community Gemma Q8_0 on `llama-cpp-mtp` stock (mainline binary, **no** `--spec-type`, GGUF path under `~/.lmstudio/models/lmstudio-community/...` — confirm via the comparison section).

**Hybrid MoE:** Huihui Qwen3.6-35B MTP Q6_K on llama-cpp-mainline :8100 (start command verbatim from CLAUDE.md "llama-cpp-mtp" block), unsloth Qwen3.6-35B UD-Q6_K (lm-studio), prithivMLmods Aggressive Q6_K (`qwen3.6-35b-a3b-uncensored-aggressive` + `--identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k` — key collision with HauhauCS, model-benchmark-tool-call.md:1051), HauhauCS Aggressive Q6_K_P (lm-studio, grep writeup for key), TurboQuant turbo3 V on TheTom fork :8099 (start command from `docs/servers/llama-cpp-turboquant/summary.md`).

**Dense:** Granite 4.1 30B (`granite-4.1-30b`, CLAUDE.md lm-studio example), Dolphin Venice 24B, TrevorJS Gemma 31B Q4_K_M, MiniCPM5-1B on sglang :30000 (start command from CLAUDE.md), Dolphin 3.0 R1 24B — lm-studio keys grepped from their `docs/models/uncen-model/` writeups / benchmark sections during implementation.

### Step 4 — Detect running, availability check, stop, start

- **Detect:** import from `scripts/chk_llm_macstu.py` — `probe(host)`, `identify_servers()`,
  `loaded_model_for()` (`sys.path` insert, same repo). If the target server is already up *and*
  `/v1/models` already lists `model_id`, skip to config sync.
- **Availability (before stopping anything):** `kind="lms"` → `ssh macstudio "~/.lmstudio/bin/lms ls"`,
  match `lms_key`; `kind="remote-cmd"` → `ssh macstudio "test -e <gguf_path>"`. If missing, print
  `Model not on disk (likely removed by storage cleanup). Re-download: <lms get …/huggingface-cli download …>` and exit 1 — running server untouched.
- **Stop:** per-server `STOP_COMMANDS` dict mirroring CLAUDE.md (pkill patterns, `brew services stop omlx`, `lms unload --all` + `lms server stop`, osaurus stop). Stop **all** detected LLM servers (Event-4-style hygiene), not just port-conflicting ones — frees unified memory for the incoming model.
- **Start:**
  - `lms` kind: guardrail dance (settings.json `mode: off` → `lms load <key> --gpu max --context-length 65536 --identifier <model_id> -y` → `mode: high`) → `lms server start --bind 0.0.0.0 --cors`. Exact pattern from the Huihui writeup / CLAUDE.md.
  - `remote-cmd` kind: run the recipe's `nohup … &` SSH command verbatim.
- **Readiness:** poll `http://<ip>:<port>/v1/models` every 3 s, timeout 180 s; confirm `model_id` appears.

### Step 5 — Sync OpenCode config

Import from `scripts/switch_opencode_config.py`: `switch_server(server_folder, model_override=model_id)`
(it already reads the live config for real IP/key, resolves the template at
`configs/clients/<server>/opencode.json`, backs up, writes `~/.config/opencode/opencode.json`).
The Mac Studio IP for readiness/smoke-test reuses its `extract_real_ip()` on the live config.

### Step 6 — Tool-call smoke test

Single POST to `http://<ip>:<port>/v1/chat/completions`:
- one tool def — reuse the `read_file` entry from `TOOLS` in `scripts/bench/bench_api_tool_call.py` (import or copy the single dict),
- prompt: `"Read the file /tmp/notes.txt"`, `tool_choice: "auto"`, `max_tokens: 512`, non-streaming,
- **pass** = response message contains `tool_calls` (or `finish_reason == "tool_calls"`); print tool name + args + latency; one retry on cold-start hiccup. Exit 0/1 accordingly.

## Other edits

- `scripts/README.md` — add row for `switch_top_model.py` in the top-level helpers table.

## Verification

1. `python3 scripts/switch_top_model.py --dry-run --pick moe:1` — table parse shows correct top-5 per group; printed SSH commands match CLAUDE.md patterns.
2. Real run: pick MoE → Huihui Gemma 26B. Confirm: prior server stopped, `lms ps` shows the model, smoke test returns a `read_file` tool call.
3. `python3 scripts/chk_llm_macstu.py` — reports lm-studio :1234 with the new model.
4. `~/.config/opencode/opencode.json` points at lm-studio template with `gemma4-26b-a4b-huihui-abliterated-q6k`.
5. Negative path: temporarily point a recipe at a bogus `lms_key` → script reports "not on disk" and leaves the running server untouched.

## Sync-policy notes

Script is an Event-5 helper: only `scripts/README.md` needs updating. The script *reports* live
state at runtime but writes no run-state into any doc (hard rule preserved). Speed figures quoted
above are benchmark-table citations, not live-state claims.
