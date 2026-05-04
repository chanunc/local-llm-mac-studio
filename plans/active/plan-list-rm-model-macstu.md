Status: active
Created: 2026-05-04
Canonical: no

# Plan: `/list-rm-model-macstu` skill

## Context

The Mac Studio M3 Ultra (96 GB) keeps experimental LLMs in **four** model-keeping folders that together total ~720 GiB. Models accumulate across `deploy-run-benchmark-uncen-model` runs — there is no cleanup automation. Without a triage tool the user has to SSH in and manually `du -sh` each directory before deciding what to delete, and hard-linked GGUFs (e.g. `~/.cache/hauhau-gguf` ↔ `~/.lmstudio/models`) make double-counting easy.

This skill gives a single command — `/list-rm-model-macstu` — that enumerates every model on disk with **name, size, path(s), server-side state**, then walks the user through a safe interactive removal.

The skill must:
1. Cover all four storage roots, dedupe hard links by inode.
2. Flag any model currently mmap'd by a running server (refuse to remove without explicit override).
3. Ask the user which entries to remove using a numbered table, then confirm before any destructive action via `AskUserQuestion`.
4. Prefer the per-directory clean-removal CLI (`lms rm`, `huggingface-cli delete-cache`) over raw `rm -rf` so internal indexes stay consistent.

## Files to create

| Path | Purpose |
|:--|:--|
| `~/.claude/skills/list-rm-model-macstu/SKILL.md` | Skill body — YAML frontmatter + phased markdown. Mirrors the structure of `~/.claude/skills/deploy-run-benchmark-uncen-model/SKILL.md`. |
| `~/.claude/skills/list-rm-model-macstu/inventory.sh` | Single SSH'd-bash payload that emits a TSV manifest (`inode\tsize_bytes\tpath\troot\tloaded_flag`) for all four roots. Stored as a separate file because it's ~80 lines of bash and embedding it inline in SKILL.md hurts readability. |

No parent-repo edits; no submodule edits. The skill lives entirely in `~/.claude/skills/` (user-scope, not committed to setup-llm-macstu).

## Frontmatter

```yaml
---
name: list-rm-model-macstu
description: List every model on the Mac Studio across HF cache / LM Studio / oMLX / hauhau-gguf and interactively remove selections. Dedupes hard links, flags loaded models, prefers per-server cleanup CLIs over rm -rf.
argument-hint: [--filter <pattern>] [--min-size <GiB>] [--root hf|lmstudio|omlx|hauhau|all]
allowed-tools: Bash Read Write AskUserQuestion
---
```

Tools restricted to read + interactive prompt + Bash (for SSH). No Edit/WebFetch/WebSearch.

## Phase outline (what SKILL.md tells the assistant to do)

### Phase 1 — Argument parsing
- `$ARGUMENTS` parsed inline (same convention as `deploy-run-benchmark-uncen-model`).
- Default: `--root all`, no filter, no min-size.
- Validate `--root` against `{hf, lmstudio, omlx, hauhau, all}`; abort with clear error otherwise.

### Phase 2 — Liveness probe (read-only)
Single SSH call that captures **what processes are currently using model files**:
```bash
ssh macstudio "ps -axo pid,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms server|omlx' | grep -v grep; \
  ~/.lmstudio/bin/lms ps --json 2>/dev/null"
```
Capture the output verbatim into `LIVE_PROCESSES`. Used in Phase 4 to mark loaded models.

### Phase 3 — Inventory enumeration
Run `inventory.sh` over SSH (heredoc'd, no file copy needed):
```bash
ssh macstudio 'bash -s' < ~/.claude/skills/list-rm-model-macstu/inventory.sh
```

`inventory.sh` emits one TSV line per **logical model** (top-level directory under each root, or a single GGUF for hauhau-gguf):

```
<root_id>\t<model_name>\t<size_bytes>\t<inode_of_largest_file>\t<paths_pipe_separated>
```

Per-root rules:
- `hf`: each `~/.cache/huggingface/hub/models--ORG--MODEL/` → name = `ORG/MODEL`, size = `du -sb` on the directory, inode = `stat -f %i` on the largest blob.
- `lmstudio`: parse `~/.lmstudio/bin/lms ls --json`; name = `path` field; inode = stat on the actual `.gguf`. Resolves the LM Studio internal name shown in `lms ls`.
- `omlx`: each top-level directory under `~/.omlx/models/`.
- `hauhau`: each top-level `*.gguf` under `~/.cache/hauhau-gguf/`.

After all rows are emitted, the assistant **deduplicates by inode** in-process: if two rows share the same inode-of-largest-file, merge into a single entry whose `paths` field contains both, keep the size once. (This catches the `lms import -L` hard-link case.)

### Phase 4 — Build the table
Format and print:

```
#   Server     Model                                          Size      Loaded   Path(s)
1   llmster    gemma-4-26b-a4b-it-uncensored                  25.0 GiB  ●        ~/.lmstudio/models/...; ~/.cache/hauhau-gguf/...
2   hf         mlx-community/Qwen3.6-35B-A3B-4bit             19.5 GiB  -        ~/.cache/huggingface/hub/models--mlx-community--...
...
Total: 47 models, 718 GiB on disk
Loaded (●): 1 model — refuse-to-remove unless --force passed
```

Apply `--filter` (substring match on model name, case-insensitive) and `--min-size` (skip rows below threshold) at this stage.

The `Loaded` flag is `●` if any path in the entry appears in `LIVE_PROCESSES` (`lms ps --json` paths or the `--model` arg of any matched ps line).

### Phase 5 — Selection
Print the table inline, then prompt the user in plain text:

> Reply with the row numbers to remove (comma-separated, e.g. `3,7,12`), `all` to remove every unloaded entry, or `none` to abort.

Wait for the user's free-form reply. Validate: numbers must be in range, `all` and `none` are valid sentinels. If any selected number is currently loaded (`●`), surface that explicitly and ask whether to skip it — do not auto-include loaded models even on `all`.

### Phase 6 — Pre-delete confirmation (AskUserQuestion)
Show the final preview:
- Selected entries with size + paths
- Total bytes to be freed
- Per-entry removal command that **will** be run

Ask via `AskUserQuestion` with three options:
- **Confirm — remove all listed entries**
- **Edit selection — go back to Phase 5**
- **Abort — exit without changes**

### Phase 7 — Execute removals
Per entry, in this order of preference:
- `hf`: `ssh macstudio "huggingface-cli delete-cache --disable-tui --repo <ORG/MODEL>"` if the CLI exists, else `rm -rf` the `models--ORG--MODEL/` dir.
- `lmstudio`: `ssh macstudio "~/.lmstudio/bin/lms rm <model-key>"`. If `lms rm` errors, fall back to `rm -rf` on the path AND `lms ls` re-scan.
- `omlx`: `rm -rf` the top-level directory.
- `hauhau`: `rm` the file (single `.gguf`).

For hard-linked entries (paths field contains multiple), iterate every path so the disk space actually frees.

After each removal, log success/failure. Do **not** halt the batch on a single failure — collect errors and surface them at the end.

### Phase 8 — Verify
Re-run `du -sh` on the four roots and report **before / after / freed** to the user. End-of-skill summary message.

## Reuse of existing patterns

- **Frontmatter shape, phase numbering, SSH invocation** — copy from `~/.claude/skills/deploy-run-benchmark-uncen-model/SKILL.md`.
- **Pre-bench hygiene SSH probe** — `CLAUDE.md` Event 4 has the canonical "list all running model processes" command; reuse the same regex.
- **`lms` CLI flags** — `lms ls --json`, `lms ps --json`, `lms rm <key>` all confirmed to exist (Explore agent verified `lms ls --json` and `lms` commit `0b2a176`).
- **macOS BSD vs GNU find** — use `stat -f` (BSD) on the Mac Studio side, not `-printf` (GNU). Captured in `inventory.sh` comments.

## Verification (manual, after the skill is written)

1. `ls ~/.claude/skills/list-rm-model-macstu/` → should show `SKILL.md` + `inventory.sh`.
2. Dry-run by typing `/list-rm-model-macstu --root hf` and answering `none` at the selection prompt → should print the HF table only and exit cleanly with zero deletions.
3. With nothing currently loaded on Mac Studio, run `/list-rm-model-macstu --filter nonexistent-string-xyz` → should print "0 models match" and exit.
4. Test the loaded-model refusal: load a small model on llmster, run the skill, try to select that model → should be blocked with the explicit "loaded — skip?" prompt.
5. Real removal: pick a known-stale entry (e.g. an old benchmark snapshot in HF cache), confirm through Phase 6, watch Phase 7 succeed and Phase 8 report freed bytes matching the entry's size.
6. Hard-link case: confirm a GGUF that exists as both `~/.cache/hauhau-gguf/X.gguf` and `~/.lmstudio/models/.../X.gguf` shows as **one** row with two paths in the table, and removing it deletes both paths so `du` reflects the full reclaim.

## Sync Policy follow-ups (when implementation begins)

Per CLAUDE.md Event 6, the implementation commit must also:
- Add this plan to `plans/README.md` Active index.
- On completion, move this file to `plans/done/` and update the README index again.

## Out of scope

- Deletion of model entries from `configs/clients/<server>/*.json` or any of the parent-repo docs — this skill only touches the macstudio filesystem. Doc cleanup remains a manual / future-skill concern.
- Removing partial / interrupted HF downloads (`*.incomplete` files inside `blobs/`). Could add later under `--include-incomplete`.
- Cross-host (Tailscale) variant. Skill assumes the LAN `macstudio` SSH alias resolves; user can swap to `macstudio-ts` by editing the skill if needed.
