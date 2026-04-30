# Plan: Rearrange repository document organization

**Branch:** `rearrange-claude-opus4-7`
**Date:** 2026-04-30

## Goal

Reduce "where does this go?" ambiguity as the repo grows past five servers and a dozen model benchmarks. The current top-level layout (set when the repo was three servers + one model) has accumulated four kinds of latent friction:

1. `docs/models/` is flat — 9 files mix a catalog, per-model deep-dives, benchmark write-ups, and how-tos.
2. Benchmark JSONs live in two homes (`docs/models/benchmarks/<model>/*.json` **and** `docs/servers/<server>/*-benchmark.json`).
3. `plans/` mixes active, completed, and stale plans with no lifecycle marker.
4. Plural/singular inconsistency: `docs/servers/` and `configs/clients/` are singular outliers; everything else is plural.

Plus two minor items: `scripts/` is a 10-file bag of patches + benches + tools, and `patches/mlx_lm/` is empty.

## Items (in execution order)

### 1. Trivial: delete empty `patches/mlx_lm/`

Empty dir — `git rm -r patches/mlx_lm`.

### 2. Split `scripts/` by purpose

Create:
- `scripts/patches/` — `patch_*.py` (6 files)
- `scripts/bench/` — `bench_*.py` (3 files)
- `scripts/` root — `switch_opencode_config.py` (and future tools)

Sweep references in: `README.md`, `CLAUDE.md`, `AGENTS.md`, `plans/*.md`, `docs/servers/**/*.md`, `docs/models/**/*.md`, and self-references inside the scripts.

### 3. Reorganize `docs/models/` by content type

| Destination | Files |
|:---|:---|
| `docs/models/` (root, catalog) | `model-summary.md` |
| `docs/models/per-model/` | `model-summary-ling.md`, `model-summary-mimo-v2.5.md` |
| `docs/models/benchmarks/` (already exists with JSON results) | `model-benchmark-agent-tool-call.md`, `model-benchmark-api-server.md`, `model-benchmark-standalone.md`, `model-benchmark-turboquant-jang.md` |
| `docs/models/how-to/` | `model-conversion-gguf-mlx.md`, `model-qwen-null-think-template-test.md` |
| (untouched — submodule) | `docs/models/uncen-model/` |

Sweep all relative-path references inside moved files (depth changes by 1) and all incoming references from `README.md`, `CLAUDE.md`, `AGENTS.md`, `configs/README.md`, and other docs.

### 4. Consolidate benchmark JSON locations

Move loose JSONs from `docs/servers/<server>/` into `docs/models/benchmarks/<model>/`, following the existing naming convention (`api-server-<server>.json`, `api-server-<server>-128k.json`):

| From | To |
|:---|:---|
| `docs/servers/vllm-mlx/ling-2.6-flash-6bit-benchmark.json` | `docs/models/benchmarks/ling-2.6-flash-6bit/api-server-vllm-mlx.json` |
| `docs/servers/vllm-mlx/qwen36-27b-jang4m-benchmark.json` | `docs/models/benchmarks/qwen36-27b-jang4m/api-server-vllm-mlx.json` |
| `docs/servers/vllm-mlx/qwen3-coder-next-6bit-128k-benchmark.json` | `docs/models/benchmarks/qwen3-coder-next-6bit/api-server-vllm-mlx-128k.json` (new dir) |
| `docs/servers/vllm-mlx/qwen35-122b-jang2s-128k-benchmark.json` | `docs/models/benchmarks/qwen35-122b-jang2s/api-server-vllm-mlx-128k.json` (new dir) |
| `docs/servers/mlx-openai-server/qwen36-35b-server-benchmark.json` | `docs/models/benchmarks/qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json` (new dir) |

Sweep `docs/models/benchmarks/model-benchmark-api-server.md` (after #3, this file lives in `benchmarks/`) and any other references.

### 5. Triage `plans/` — add `plans/archived/`

Archive plans that are clearly completed (deployed code visible in repo or referenced as "in production" elsewhere):

- `plan-mac-studio-lmstudio-ollama-benchmark.md` — llmster shipped 2026-04-30 (`docs/servers/llmster/summary.md`, `configs/clients/llmster/`, multiple commits).
- `plan-hot-cache-max-size-per-model.md` — `scripts/patches/patch_omlx_cache.py` (post #2) is in production, marked "Completed" inside the plan itself.

Leave the rest at `plans/` root (status uncertain, treat as active/backlog until the user confirms).

### 6. Plural/singular consistency

Rename:
- `docs/servers/` → `docs/servers/`
- `configs/clients/` → `configs/clients/`

Sweep:
- `README.md`, `CLAUDE.md`, `AGENTS.md`, `configs/README.md`
- `scripts/switch_opencode_config.py` (`CONFIGS_DIR = REPO_ROOT / "configs" / "client"` → `"clients"`)
- All `docs/**/*.md` cross-references
- Per-server `summary.md`/`maintenance.md` self-references

### 7. Skip: `docs/clients/` flat layout

Acknowledged in last review as low-priority. Skipping in this pass to keep disruption bounded.

## Link-sweep checklist

For each move, the following files almost always need updating:

- `README.md` (repository map + inline links)
- `CLAUDE.md` and `AGENTS.md` (kept synced — if you edit one, edit both)
- `configs/README.md` (cross-references to docs)
- The catalog file `docs/models/model-summary.md`
- Each moved file's own relative paths (depth changes break `../../scripts/` etc.)

Use `grep -rn "<old-path>"` after each move; iterate until clean.

## Out of scope

- Renaming `CLAUDE.md`/`AGENTS.md` into a symlink. The Sync Policy is acceptable.
- Adding `docs/README.md` as an index. Defer until structure stabilizes.
- Touching `docs/models/uncen-model/` (git submodule).
- Restructuring `docs/clients/` (low-priority skip per item #7).

## Commits

One commit per item, in execution order, on branch `rearrange-claude-opus4-7`:

1. Save this plan
2. Delete empty `patches/mlx_lm/`
3. Split `scripts/` by purpose
4. Reorganize `docs/models/` by content type
5. Consolidate benchmark JSON locations
6. Add `plans/archived/`
7. Rename `docs/server` → `docs/servers`, `configs/client` → `configs/clients`

Push branch at end.
