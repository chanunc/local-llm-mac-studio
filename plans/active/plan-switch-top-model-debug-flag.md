# Plan: `--debug` flag for `scripts/switch_top_model.py` — per-step diagnostics + log-tail-on-timeout

Status: active
Created: 2026-06-12
Canonical: no

Related: extends [`done/plan-switch-top-model-script.md`](../done/plan-switch-top-model-script.md)
(shipped 2026-06-12). This plan adds observability only — no behavior change to the switch flow.

## Context

Every consequential action in `switch_top_model.py` happens on the Mac Studio over SSH, and the
current code discards the evidence:

- `ssh()` runs with `capture_output=True` and every call site uses the default `check=False` —
  return code, stdout, and stderr are captured then thrown away.
- `start_remote_cmd` launches via `nohup … &`, so `rc=0` is guaranteed even when the server
  aborts one second later. The only evidence lands in `/tmp/*.log` on the remote machine.
- `wait_ready` swallows every exception for up to 180 s — connection-refused (server dead) and
  404 (server up, wrong model id) are indistinguishable.

Net effect: ~5 distinct failure causes collapse into one symptom — "did not appear on /v1/models
within 180s". The 2026-06-11 llama-server triage session (silent crash, Gatekeeper rejection,
exit 137, no `--help` output) is a catalog of exactly the failure class this masks; each incident
would present identically under this script today.

User decisions (2026-06-12):
- Add `--debug` per the Scenario A/B mock (success trace + remote-crash trace).
- Open question settled at implementation time: log-tail-on-`wait_ready`-timeout **always-on**
  (recommended) vs debug-only.

## Overview

- Module-level `DEBUG` flag + `dbg()` helper printing `[debug]`-prefixed lines to **stderr**
- `ssh()` result dump: echo command, then rc / stdout / stderr after execution
- Table-parser tracing: section/group line numbers, column indices, per-row keep/skip + reason
- Recipe-match tracing (incl. `server_match` disambiguation)
- `check_on_disk` raw `lms ls` / `test -e` evidence
- Post-launch remote log tail for `remote-cmd` kinds (catches nohup-detached crashes)
- `wait_ready` per-poll tracing: elapsed, ids listed, exception class
- `smoke_test` payload + raw response dump on failure; API key always `***redacted***`
- Per-phase + total wall-time summary
- Log-tail-on-timeout in `wait_ready` (proposed always-on, not debug-gated)
- Verification via `--dry-run --debug`, a forced-failure run, and a clean live run

## Design

### Plumbing

- `DEBUG = False` at module level; set from `args.debug` in `main()`.
- `def dbg(*parts)`: no-op unless `DEBUG`; prints `[debug] …` to `sys.stderr` (stdout stays
  clean for piping; consistent with existing `file=sys.stderr` error style).
- ~30–40 lines total, all behind the flag; zero behavior change when off — same commands, same
  exit codes, same stdout.

### Instrumentation points

| Site | Debug output |
|:--|:--|
| `parse_benchmark_table()` | Section found at line N (+ end), groups discovered with line numbers, column indices per group, each row kept (`name browse=X search=Y`) or skipped (+ reason: `⛔`, too-few-cells, empty name) |
| `match_recipe()` | Which recipe matched a row; note when `server_match` disambiguated same-named rows |
| `ssh()` | Pre: `ssh <host>: <cmd>` (truncate `STOP_ALL_CMD`-class long commands to one line). Post: `rc=N stdout=… stderr=…` (`(empty)` markers; cap each at ~500 chars) |
| `check_on_disk()` | lms kind: rc + which key matched among how many listed models (raw `lms ls` lines on miss). remote-cmd kind: rc + OK/MISSING |
| `start_remote_cmd()` | Note that `rc=0` from nohup says nothing; then **log tail** (below) |
| `wait_ready()` | Per poll: `poll#N @Xs — connection refused` / `M ids; target absent` / `target present ✓` (exception → class name, not traceback) |
| `smoke_test()` | POST URL with `Authorization: Bearer ***redacted***`, payload summary (model / tools / tool_choice / max_tokens), HTTP status + `finish_reason`; on FAIL dump raw response JSON (cap ~1 KB) |
| `main()` | Live-config resolution (`ip=…  api_key=***redacted (N chars)***`), probe result for the target port, per-phase wall times + total at exit |

### Remote log tail

New helper `tail_remote_log(host, rec, lines=12)`:

- Map recipe → log file. Derive from the `> /tmp/….log` redirect already present in each
  `start_cmd` (regex `>\s*(/tmp/\S+\.log)`) — no second registry to maintain. lms kind has no
  `/tmp` file; use `~/.lmstudio/bin/lms log stream --source server` last-resort or skip
  (lm-studio load errors already surface in the `lms load` rc/stdout dump).
- Called (a) ~1.5 s after `start_remote_cmd` launch when `DEBUG`, and (b) from `wait_ready`
  on timeout for `remote-cmd` recipes — **always-on** (recommended): the timeout is the one
  place where something is known-wrong, and the last 12 log lines are the only evidence
  (`unknown pre-tokenizer type`, Gatekeeper kill, abort, OOM). Withholding it behind a flag
  the user forgot to pass serves nobody. Falls back silently if the log file is absent.
- Optional knob deferred: `--log-tail-lines N` — not needed until 12 proves wrong.

### Redaction rule (hard requirement)

Never print request headers or the api_key value anywhere in debug output. Render as
`***redacted***` (optionally with char count). This repo is mirrored publicly; a pasted debug
transcript must be safe by construction.

## Verification

1. `python3 scripts/switch_top_model.py --pick moe:1 --dry-run --debug` — parser/match/redaction
   lines appear on stderr; stdout identical to a non-debug dry run (`diff` the two stdouts).
2. Without `--debug`: byte-identical output to current behavior (regression guard).
3. Forced failure: point a remote-cmd recipe at a bogus binary path → launch, observe the
   log tail firing on `wait_ready` timeout (with and without `--debug`).
4. Clean live run with `--debug` → confirm phase timings + redacted key + PASS trace.
5. `grep` the debug output of a real run for the live API key — must be absent.

## Sync-policy notes

Event-5 script change: update the `switch_top_model.py` row in `scripts/README.md` to mention
`--debug` (and log-tail-on-timeout if always-on). No run-state assertions anywhere. Debug output
reports live state at runtime only; nothing is written to docs.
