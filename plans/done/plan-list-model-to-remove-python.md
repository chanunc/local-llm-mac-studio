# Plan: `scripts/list_model_to_remove.py` — LLM-free port of `/list-model-to-remove`

Status: done
Created: 2026-05-08
Completed: 2026-05-09
Canonical: no
Implementation: [`scripts/list_model_to_remove.py`](../../scripts/list_model_to_remove.py); index entry in [`scripts/README.md`](../../scripts/README.md#disk-reclaim). Verified end-to-end via `--dry-run` against `macstudio` (46 entries, 623 GiB, hard-link dedupe correct).

## Context

The existing `/list-model-to-remove` skill (`~/.claude/skills/list-model-to-remove/`) walks the Mac Studio's four model storage roots, dedupes by inode, flags loaded models, and interactively removes selections. Its eight phases are orchestrated by an LLM (parsing args, rendering tables, prompting via `AskUserQuestion`, mapping `root_id` → cleanup command). That works, but it costs tokens every run and can't be invoked from a non-Claude shell session.

This change adds a self-contained Python script at `scripts/list_model_to_remove.py` that produces the same end behavior — same enumeration, same dedupe rules, same per-root cleanup commands, same loaded-model refusal — without an LLM in the loop. Run it from a plain terminal: `python3 scripts/list_model_to_remove.py [--filter ...] [--min-size ...] [--root ...] [--host macstudio|macstudio-ts]`.

**User decisions (already made):**
- Place in `scripts/list_model_to_remove.py` (top-level helper, alongside `switch_opencode_config.py`).
- Leave the existing skill untouched; it keeps working as today via the LLM path.
- Reuse `~/.claude/skills/list-model-to-remove/inventory.sh` as-is by streaming over SSH (`ssh <host> 'bash -s' < <path>`). No port of the bash logic.

## Behavioral contract (unchanged from SKILL.md)

| Property | Source of truth |
|:--|:--|
| Storage roots enumerated | `inventory.sh` lines 35-39 — `hf` / `lmstudio` / `omlx` / `hauhau` |
| TSV row format | `inventory.sh` line 7 — `<root>\t<name>\t<bytes>\t<inode>\t<paths>` |
| Liveness regex | SKILL.md Phase 2 — `vllm-mlx|mlx-openai-server|mlx_lm\.server|mlx_vlm\.server|vmlx_engine|dflash-serve|lms server|llama-server|omlx` |
| Inode-0 → never merge | SKILL.md Phase 3.4 |
| Loaded match = name OR any path appears in process list | SKILL.md Phase 4 |
| Sort by size desc | SKILL.md Phase 4 |
| Per-root cleanup command | SKILL.md Phase 7 table (hf → `huggingface-cli delete-cache` w/ `rm -rf` fallback; lmstudio → `rm -rf <container>` (`lms` has no `rm`); omlx → `rm -rf`; hauhau → `rm <file>`) |
| Refuse to remove loaded entries unless explicitly overridden | SKILL.md Phase 5 |
| Hard-link group: delete every path so disk actually frees | SKILL.md Phase 7 last paragraph |
| Skill **only** mutates Mac Studio FS — no doc/config edits | SKILL.md line 35 |

The Python script reproduces every row of that table. Anything that diverges is a bug.

## Script structure (single file, ~350-450 lines)

`scripts/list_model_to_remove.py`:

```
1. CLI                      argparse — same args as the skill plus --host {macstudio,macstudio-ts}
                            and --yes (skip both interactive prompts; for scripted reclaim).
2. ssh()                    Thin wrapper around subprocess.run(["ssh", host, ...], check=False)
                            returning (stdout, stderr, rc). Used everywhere we hit the Mac Studio.
3. liveness_probe(host)     Runs the SKILL.md Phase 2 ssh one-liner; returns the raw combined
                            output as a single string for substring matching.
4. run_inventory(host)      Streams ~/.claude/skills/list-model-to-remove/inventory.sh over SSH:
                                with INVENTORY.open() as f:
                                    subprocess.run(["ssh", host, "bash -s"], stdin=f, ...)
                            Parses TSV → list[Entry].
5. Entry dataclass          root, name, size_bytes, inode, paths: list[str]
6. apply_filters(entries,
                 root, filter, min_bytes)   Three-step filter from SKILL.md Phase 3.1-3.3.
7. dedupe_by_inode(entries) Group by non-zero inode; merge paths; keep first size.
                            Inode 0 stays separate. (SKILL.md Phase 3.4)
8. mark_loaded(entries,
               live_text)   Sets entry.loaded = True if name or any path is a substring
                            of live_text. (SKILL.md Phase 4)
9. render_table(entries)    Fixed-width table to stdout. Numbered from 1, sorted size desc.
                            Footer with totals. Same shape as SKILL.md Phase 4 example.
10. parse_selection(reply,
                    n_rows) Accepts "none" / "all" / comma-sep ints. Returns list[int]
                            or raises with a parseable error for re-prompt.
11. handle_loaded_picks(
        selected, entries,
        --yes)              For every loaded pick, prompt yes/no (default yes=skip).
                            With --yes, auto-skip loaded entries.
12. preview_block(picks)    Prints the SKILL.md Phase 6 preview — the actual command per
                            entry, derived from root_id (see "Cleanup command derivation"
                            below).
13. confirm()               input("Confirm / Edit / Abort [C/e/a]: "). With --yes,
                            auto-Confirm. AskUserQuestion is replaced by this single prompt.
14. execute_removals(host,
                     picks) Iterates picks. For HF, probes once: 
                                ssh host "command -v huggingface-cli"
                            and uses the CLI when available, falls back to rm -rf.
                            For lmstudio (GGUF vs MLX dir), strip the file basename when
                            the path ends in .gguf else use the path itself.
                            For omlx and hauhau, run the literal commands from the SKILL
                            table. Multiple paths → iterate and rm each, so hard-link
                            twins both free. Collect failures into errors list, never
                            halt the batch.
15. verify(host, picks)     Re-run du -sh on the four roots; print before/after-style
                            summary. Compute claimed_freed = sum of picks' size_bytes.
                            Print divergence note if du delta < claimed (hard-link still
                            held elsewhere — note from SKILL.md Notes section).
16. main()                  Wires it all together with the same phase numbers in comments
                            so behavior maps back to SKILL.md by section.
```

### Cleanup command derivation (Phase 7)

Per-root, computed in `execute_removals` from `Entry`:

| `root` | Command |
|:--|:--|
| `hf` | If `huggingface-cli` is on Mac Studio PATH: `ssh host "huggingface-cli delete-cache --disable-tui --repo <name>"`. Else: `ssh host "rm -rf <path>"` for each path. (Probe once, cache result.) |
| `lmstudio` | For each path: `target = path if not path.endswith('.gguf') else os.path.dirname(path)`; `ssh host "rm -rf <target>"`. (`lms` has no `rm` subcommand — confirmed in SKILL.md Phase 7 table.) |
| `omlx` | For each path: `ssh host "rm -rf <path>"`. |
| `hauhau` | For each path: `ssh host "rm <path>"` (single `.gguf` file). |

For multi-path (hard-link group) entries, iterate every path so each link is broken.

### Interactive prompts (no LLM, no AskUserQuestion)

| Phase | LLM-driven version | Python version |
|:--|:--|:--|
| 5 | Free-form chat reply | `input("rows to remove (e.g. 3,7,12 / all / none): ")` with re-prompt loop on bad input |
| 5 (loaded override) | LLM asks "Skip it? (yes/no)" | `input(f"#{n} ({name}) is loaded. Skip? [Y/n]: ")` (default yes) |
| 6 | `AskUserQuestion` with Confirm / Edit / Abort | `input("Confirm/Edit/Abort [C/e/a]: ")`; `e` jumps back to Phase 5 with same table |

`--yes` short-circuits both confirmation prompts: auto-skip loaded entries, auto-confirm the final preview. Useful for cron-style reclaim scripts.

## Files to add / edit

| File | Change |
|:--|:--|
| `scripts/list_model_to_remove.py` | **New.** ~350-450 line standalone script per the structure above. Executable shebang, `if __name__ == "__main__": main()`. Imports: `argparse`, `dataclasses`, `os.path`, `subprocess`, `sys`, plus stdlib only. |
| `scripts/README.md` | **Edit.** Add a new section `## Disk reclaim` (or extend the Layout table line for `scripts/`) with one row pointing at the new script. Mention that it mirrors `/list-model-to-remove` without the LLM, reuses `~/.claude/skills/list-model-to-remove/inventory.sh`, and supports `--yes` for non-interactive use. |
| `~/.claude/skills/list-model-to-remove/SKILL.md` | **No change.** (User chose "leave skill untouched.") |
| `~/.claude/skills/list-model-to-remove/inventory.sh` | **No change** — referenced by absolute path from the new script. |
| Top-level `README.md` / `CLAUDE.md` / `AGENTS.md` | **No change** — Sync Policy Event 5 only requires `scripts/README.md` updates for new scripts (no new benchmark type, no new patch). |

## Critical files to read before implementation

- `~/.claude/skills/list-model-to-remove/SKILL.md` — phase-by-phase contract.
- `~/.claude/skills/list-model-to-remove/inventory.sh` — TSV output format and root layout.
- `scripts/switch_opencode_config.py` — house style for top-level Python helpers (argparse, `Path(__file__).resolve().parent.parent`, `print(..., file=sys.stderr)`, exit codes).
- `scripts/chk_llm_macstu.py` — house style for SSH-into-macstudio scripts (host alias resolution, `ssh -o ConnectTimeout=…`, `--host` flag default).

## Reuse (do not re-implement)

- **Inventory enumeration**: `~/.claude/skills/list-model-to-remove/inventory.sh`. Stream verbatim — no Python rewrite.
- **TSV schema**: lines 7 + 61-64 of `inventory.sh`. Parse with `line.split("\t", 4)` (last field is paths joined by `|` — currently single-path, but split-friendly for future).
- **Liveness regex**: copy verbatim from `SKILL.md` Phase 2 into the Python script as a single string passed to the remote shell. Don't re-derive.

## Verification (end-to-end, on the real Mac Studio)

Run from this MacBook:

```bash
# 1. Dry inventory only — no removal prompts. Hidden behind a smoke-test flag.
#    (Add --dry-run to the script; prints table + footer then exits.)
python3 scripts/list_model_to_remove.py --dry-run

# 2. Filter + size cutoff.
python3 scripts/list_model_to_remove.py --filter qwen3.5 --min-size 5 --dry-run

# 3. Single root.
python3 scripts/list_model_to_remove.py --root lmstudio --dry-run

# 4. Loaded-flag check: with the current main loaded (whatever's on port 8000 or 1234),
#    confirm the corresponding row shows ● in the Loaded column.
python3 scripts/list_model_to_remove.py --dry-run | grep -E '●|Loaded'

# 5. End-to-end on a known-safe candidate (small, unloaded). Reply `none` at the
#    selection prompt — must exit cleanly with "no changes made" (Phase 5).
python3 scripts/list_model_to_remove.py

# 6. Skill parity: run /list-model-to-remove (LLM path) and
#    `python3 scripts/list_model_to_remove.py --dry-run` back-to-back; confirm:
#      - same number of entries
#      - same total GiB
#      - same set of names per root
#      - same set of ● flags
#    Any divergence is a port bug.

# 7. Tailscale fallback.
python3 scripts/list_model_to_remove.py --host macstudio-ts --dry-run

# 8. Non-interactive reclaim path (only run on a real disposable model).
python3 scripts/list_model_to_remove.py --filter <small-test-model> --yes
#    Must: refuse loaded entries, run rm/lms/hf-cli per root, print verify summary.
```

`--dry-run` is the safe checkpoint for steps 1-4, 6, 7 — it must short-circuit *before* any prompt or any removal.

## Acceptance criteria

1. `python3 scripts/list_model_to_remove.py --dry-run` produces a table with the same row count, names, sizes, and ● flags as `/list-model-to-remove` for the same Mac Studio state.
2. Hard-linked GGUFs appear as a single deduplicated row with multiple paths joined by `; ` in the Path(s) column.
3. Replying `none` exits with zero filesystem changes.
4. A `--yes` reclaim of a small unloaded model: succeeds, frees the expected bytes, and the loaded current main is **not** touched even if it would otherwise be selected.
5. Script depends only on Python stdlib + `ssh` + the existing `inventory.sh`. No new third-party deps.
