# Plan: `lm` — Mac Studio LLM server/model switcher

## Context

Switching servers and models on the Mac Studio is currently a five-line shell
incantation per switch — `pkill -f vllm-mlx; pkill -f vmlx_engine; pkill -f mlx-openai-server; brew services stop omlx; sleep 2; ssh macstudio "..."` — copied from `CLAUDE.md` and edited per model. Past sessions show the user has done this enough times that the gotchas are now cataloged: port-8000 collision after a partial kill (memory #1437), processes auto-respawning during a stuck state (#1413), and the JANG-vs-direct loader split for vllm-mlx (memory #1435 vs #1467). `scripts/switch_opencode_config.py` already handles the *client* side of the switch; there is no equivalent for the *server* side.

The user asked for "a simple script or command to easy switching LLM model and servers" — based on past tasks, the right shape is a single Python file mirroring `switch_opencode_config.py`, driven off a curated profile registry, that encapsulates the stop → wait-for-port → start → health-check loop.

Originally this plan covered a `CLAUDE.md` documentation refresh; that task has been deferred at user request. The original drafted edits are recoverable from this file's git history if we want to come back to them.

## Goals

1. One command to switch backends (`vllm-mlx` ↔ `mlx-openai-server` ↔ `omlx` ↔ `vmlx`).
2. Within `vllm-mlx`, one flag to switch model variants (the high-frequency operation per memory — JANG_4M, 27B-6bit, 35B-rust, 122B-2S, 35B-JANG_4K).
3. Within `vmlx`, one flag to switch JANGTQ snapshots (MiniMax-M2.7, Qwen3.6-35B-JANGTQ4-CRACK).
4. Encode the parser-flag rules from `CLAUDE.md` once so future-Claude doesn't paste the wrong one.
5. Handle the port-conflict + respawn gotchas from memory #1437 / #1413.
6. Read-only on first run (no edits to client configs); pair cleanly with the existing `switch_opencode_config.py`.

## Non-goals

- Not auto-discovering models in `~/.omlx/models/` — the registry is curated so unsupported variants don't surface.
- Not updating client configs — that's `switch_opencode_config.py`'s job. Print a follow-up hint instead.
- Not running benchmarks — separate `scripts/bench/bench_*.py` already do that.
- Not tracking the live model in any persistent state file — `/v1/models` is the source of truth.

## Design

### Single file: `scripts/switch_server.py`

Stdlib only (`argparse`, `json`, `subprocess`, `time`, `sys`). Runs on the laptop; all Mac Studio operations go through `ssh <host> "<cmd>"`. Default host `macstudio`, override with `--host macstudio-ts` for Tailscale (matches `CLAUDE.md` SSH alias convention).

### Profile registry (top-of-file dict)

Each profile slug maps to a kind + the kind-specific args. Drawn from memories #1435, #1437, #1443, #1467 and `CLAUDE.md` command blocks:

| slug | kind | what |
|---|---|---|
| `qwen36-27b-jang4m` | vllm-mlx | `~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M` → `JANGQ-AI/Qwen3.6-27B-JANG_4M` (current documented default) |
| `qwen36-27b-6bit` | vllm-mlx | `mlx-community/Qwen3.6-27B-6bit` (HF ref, no local path) |
| `qwen36-35b-rust` | vllm-mlx | `~/.omlx/models/jedisct1--Qwen3.6-35B-rust.mlx` → `jedisct1/Qwen3.6-35B-rust.mlx` |
| `qwen35-122b-jang2s` | vllm-mlx | `~/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S` (previous primary) |
| `qwen35-35b-jang4k` | vllm-mlx | `~/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K` |
| `mlx-openai-server` | mlx-openai-server | YAML roster (`~/mlx-openai-server-multimodel.yaml`); no model arg |
| `omlx` | omlx | `brew services start omlx`; multi-model |
| `minimax-m2.7-crack` | vmlx | `~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537…` (current `CLAUDE.md` default) |
| `qwen36-35b-jangtq4-crack` | vmlx | `…--dealignai--Qwen3.6-35B-A3B-JANGTQ4-CRACK/snapshots/4ef2fc7…` |

Adding a new model = one dict entry. Slugs match the names already used under `docs/models/benchmarks/<slug>/agent-bench.json` so cross-referencing is natural.

### Subcommands

```
lm list                # print registry; show current /v1/models
lm status              # ssh + show pgrep summary, port owner, /v1/models
lm stop                # full teardown, verify port 8000 free
lm start <profile>     # stop -> wait -> start -> health check -> hint
lm restart <profile>   # alias for stop+start
lm logs <profile>      # ssh tail -f /tmp/<server>.log (or oMLX path)
```

### Stop logic — encode the gotchas

```
pkill -f vllm-mlx; pkill -f vmlx_engine; pkill -f mlx-openai-server;
/opt/homebrew/bin/brew services stop omlx 2>/dev/null; true
```
Then poll `lsof -nP -iTCP:8000 -sTCP:LISTEN -t` for up to 15s. If still occupied, escalate to `pkill -9 -f …` and poll another 15s. If still occupied at 30s total, abort and print the memory-#1413 hint about the supervisor that auto-respawns vllm-mlx — that's a known stuck state that needs human eyes, not more retries.

### Start logic — one branch per kind, parser flags encoded

- **vllm-mlx (all variants):** always go through `~/run_vllm_jang.py` — memory #1467 confirms the wrapper handles both JANG-format and the Rust LoRA MLX-safetensor case, so we don't need a `wrapper: jang|direct` split. Flags: `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3` (CLAUDE.md §"Common Commands"; mandatory for Qwen3.5/3.6 — `qwen` parser does NOT work).
- **mlx-openai-server:** `JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch --config ~/mlx-openai-server-multimodel.yaml --no-log-file > /tmp/mlx-openai-server.log 2>&1 &`.
- **oMLX:** `/opt/homebrew/bin/brew services start omlx`.
- **vmlx:** `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; nohup $BP/bin/python3 -m vmlx_engine.cli serve <snapshot> --host 0.0.0.0 --port 8000 --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 > /tmp/vmlx.log 2>&1 &`. **Note the parser is `qwen3`, not `qwen3_coder`** — different from vllm-mlx. CLAUDE.md spells out why; the script bakes it in so the user can't get it wrong.

### Health check

Poll `curl -s http://localhost:8000/v1/models` every 2s for up to 60s. Parse JSON, confirm `data[*].id` includes the expected `served_name` (or, for vmlx, the snapshot's HF model-id which the engine reports). For multi-model backends (mlx-openai-server, oMLX), accept *any* non-empty `data` array.

Optional `--smoke` flag runs one-shot `/v1/chat/completions` with "Say hi" — guards against the disconnect-guard stuck-state from memory #1414 where `/v1/models` responds but inference hangs. Default off (adds ~2s and clutters output for the common case).

### Output shape

```
$ lm start qwen36-35b-rust
→ host=macstudio profile=qwen36-35b-rust kind=vllm-mlx
→ stopping all backends ……………… ok (1.4s)
→ port 8000 free ……………………… ok
→ launching vllm-mlx (jedisct1/Qwen3.6-35B-rust.mlx) … ok (3.2s)
→ /v1/models reports jedisct1/Qwen3.6-35B-rust.mlx … ok
   Next: python3 scripts/switch_opencode_config.py --server vllm-mlx
```

On failure, dump `tail -30 /tmp/<server>.log` automatically so the user doesn't need to ssh in to diagnose — same logs the user already polls per `CLAUDE.md` "View logs".

## Files modified

- **New:** `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/switch_server.py` (~200 lines, stdlib only).
- No changes to client configs, no changes to `CLAUDE.md` or `AGENTS.md` in this round (deferred — see Follow-ups).

## Reused vs new

- **Reused (read-only refs):** `scripts/switch_opencode_config.py` for module shape, argparse pattern, and shebang/style. The new script doesn't import it; pairing is by convention (success message points at it).
- **New:** the profile registry and the SSH stop/start/health-check loop. Nothing else in the repo encapsulates this — current state is shell snippets in `CLAUDE.md`.

## Verification

1. **Smoke (no SSH):** `python3 scripts/switch_server.py list` should print the 9 profiles with no SSH calls. Pure local read.
2. **Status (SSH read-only):** `python3 scripts/switch_server.py status` should report whatever is currently running. No state change.
3. **End-to-end on a non-default profile:** `python3 scripts/switch_server.py start qwen36-27b-6bit`, confirm `/v1/models` flips, then run the API-level diagnostic harness `python3 scripts/bench/bench_api_tool_call.py` (per the JANGTQ4-search-hang triage memory) to confirm tool calls round-trip.
4. **Switch back:** `python3 scripts/switch_server.py start qwen36-27b-jang4m` (the documented default) so the box ends up where `CLAUDE.md` says it should be.
5. **Failure path:** while a server is mid-startup, run `start` again and confirm the port-busy escalation path triggers cleanly (pkill → pkill -9 → abort with #1413 hint).

## Follow-ups (not in this round, recorded for later)

1. Refresh `CLAUDE.md` so the Architecture > Scripts bullet enumerates `switch_server.py` alongside the bench harnesses and patch scripts; mention the parallel `AGENTS.md` sync requirement; replace the stale mlx-openai-server roster line. (This was the original /init plan; deferred when the user pivoted.)
2. Optional shell wrapper `scripts/lm` (one-line `exec python3 "$(dirname "$0")/switch_server.py" "$@"`) plus a README pointer so the typed command matches the doc shorthand. Skip unless the user asks — the Python invocation is fine.
