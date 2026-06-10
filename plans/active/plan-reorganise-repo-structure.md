# Plan: Re-organise scripts, docs, and folders

Status: active
Created: 2026-06-10
Canonical: no

Visual version: [`plan-reorganise-repo-structure.html`](plan-reorganise-repo-structure.html)

## Progress

- Commits 1–5 executed 2026-06-10 (`f261ab8`…`dc2bb41`): pending Gemma-MTP work landed, `RTK.md` gitignored, benchmark log dirs moved under `logs/`, HyperNova indexed + run-state claims removed, llmster plan files renamed.
- Commits 6 (plans audit sweep) and 7 (root strays) pending user go-ahead.

## Context

The repo had a structured reorganisation in April 2026 (`plans/done/plan-rearrange-docs-organization.md`) that established the current layout: `scripts/{bench,patches}`, `docs/models/{per-model,techniques,benchmarks,how-to}`, `plans/{active,done,archive}`. Since then, ~6 weeks of experiment work has drifted from those conventions:

- Two benchmark-log folders (`deepseek-v4-flash/`, `lfm2.5-8b-a1b-q8/`) sit directly under `docs/models/benchmarks/` instead of `benchmarks/logs/<model-slug>/`.
- `docs/models/per-model/model-summary-hypernova.md` exists but is not indexed in `docs/models/README.md`.
- `plans/README.md` index references `plan-lm-studio-uncen-benchmark.md` and `plan-gemma-4-31b-lm-studio.md`, but the actual files still carry the pre-rebrand `llmster` names.
- `plans/active/` holds 20 plans, several demonstrably shipped (script/server/skill exists in repo) but never swept to `done/`.
- Root-level strays: `huggingface-skills-analysis.md` (tracked analysis note), `html/` (one PEFT/LoRA explainer HTML), `prompts/` (2 untracked planning prompts), `RTK.md` (untracked Codex-CLI tool instructions).
- Pre-existing uncommitted Gemma-4-MTP doc work (modified CLAUDE/AGENTS/docs + untracked logs/fixtures + 3 new plans) is entangled with the working tree.

**Finding: `scripts/` needs no changes** — all 19 scripts are correctly placed per convention and fully indexed in `scripts/README.md`. Same for `configs/clients/`, `docs/servers/`, `docs/clients/`, `docs/tuning/`, `docs/server-apis/` — indexes all match.

User decisions (confirmed): audit + sweep active plans; distribute root strays into the existing tree; gitignore `RTK.md`; commit the pending Gemma-MTP work first as its own commit.

## Commit sequence

One commit per step, on `main` (matches April precedent of small atomic commits). **No pushes** — repo is already ahead of origin; pushing is a separate user decision per saved preference.

### Commit 1 — land pending Gemma-4-MTP work (pre-existing, not reorg)

Stage and commit together (they are one coherent session's output):
- Modified: `AGENTS.md`, `CLAUDE.md`, `docs/models/benchmarks/model-benchmark-tool-call.md`, `docs/models/per-model/model-summary-gemma.md`, `docs/servers/README.md`, `docs/servers/llama-cpp-mtp/summary.md`, `plans/README.md`
- Untracked: `docs/models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/`, `docs/models/benchmarks/fixtures/`, `plans/active/plan-holo31-macstudio-computer-use-eval.md`, `plans/active/plan-ideogram4-macstudio-eval.md`, `plans/active/plan-upgrade-llama-cpp-benchmark-gemma4-31b-mtp.md`
- Verify CLAUDE.md/AGENTS.md stay content-identical except lines 1–3 (`diff <(tail -n +4 CLAUDE.md) <(tail -n +4 AGENTS.md)`).
- Do NOT stage `RTK.md` or `prompts/` (handled later).

### Commit 2 — gitignore RTK.md

- Append `RTK.md` to `.gitignore` under the existing macOS/tool-local section, with a one-line comment (Codex-CLI machine-local instructions).

### Commit 3 — fix benchmark logs layout

- `git mv docs/models/benchmarks/deepseek-v4-flash docs/models/benchmarks/logs/deepseek-v4-flash`
- `git mv docs/models/benchmarks/lfm2.5-8b-a1b-q8 docs/models/benchmarks/logs/lfm2.5-8b-a1b-q8`
- Reference sweep: `grep -rn "benchmarks/deepseek-v4-flash\|benchmarks/lfm2.5-8b-a1b-q8" --include="*.md" --include="*.json" --include="*.py" .` — fix links (likely in `model-benchmark-*.md`, `docs/servers/ds4/summary.md`, per-model docs). Keep JSON filenames as-is (historical, e.g. `api-server-llmster.json`).

### Commit 4 — index the orphaned HyperNova doc

- Add `model-summary-hypernova.md` row to the per-model table in `docs/models/README.md` (note: "analysis only", per CLAUDE.md family table).
- Check `docs/models/model-summary.md` master index — add an entry/stub row if missing, marked analysis-only. No "current/primary" language (Sync Policy hard rule).

### Commit 5 — rename llmster plan files to match index

- `git mv plans/active/plan-llmster-uncen-benchmark.md plans/active/plan-lm-studio-uncen-benchmark.md`
- `git mv plans/done/plan-gemma-4-31b-llmster.md plans/done/plan-gemma-4-31b-lm-studio.md`
- `plans/README.md` index already uses the new names — verify, don't edit unless stale.
- Sweep for links to the **old filenames** only: `grep -rn "plan-llmster-uncen-benchmark\|plan-gemma-4-31b-llmster" --include="*.md" .` Leave historical `llmster` mentions in prose/JSON untouched.

### Commit 6 — plans audit: sweep shipped plans to done/

Candidates with shipped artifacts (verify each before moving — artifact named below must exist and the plan's mandatory scope be covered):

| Plan | Completion evidence |
|:--|:--|
| `plan-chk-llm-macstu.md` | `scripts/chk_llm_macstu.py` shipped, canonical health-check in CLAUDE.md |
| `plan-comfyui-zanime-sidecar.md` | comfyui server runbook + `scripts/bench/bench_zanime_walltime.py` shipped |
| `plan-deploy-llama-cpp-mtp-sidecar-qwen36-27b.md` | llama-cpp-mtp sidecar + `logs/qwen36-27b-mtp/` benchmarks shipped |
| `plan-list-model-to-remove.md` | `scripts/list_model_to_remove.py` + `/list-model-to-remove` skill shipped |
| `plan-deploy-run-benchmark-model-skill.md` | `/deploy-run-benchmark-model` skill shipped (listed in CLAUDE.md) |
| `plan-dflash-regression-investigation.md` | Verdict recorded: "Regresses vs baseline on M3 Ultra — upstream-tracking only" (CLAUDE.md + technique doc) |
| `plan-osaurus-qwen36-jangtq4-vmlx-agent-bench.md` | vmlx-swift-lm/Osaurus runbook shipped; verify agent-bench logs exist before moving |
| `plan-upgrade-llama-cpp-benchmark-gemma4-31b-mtp.md` | Commit 1 lands its outputs (gemma4-31b-mtp logs + doc updates); verify mandatory scope met |
| `plan-mlx-vlm-qwen-vl-deploy-benchmark.md` | Uncertain — mlx-vlm streaming bug blocked it (memory). Move only if plan's goal is concluded; else leave active |

For each plan that moves: `git mv plans/active/<f> plans/done/<f>`, move its row from Active to Done table in `plans/README.md`. Do not edit plan contents (plans never claim live state; "Status: active" line inside may be flipped to `done` — match how existing `plans/done/` files handle it, check one first).

Leave in `active/` (no shipped artifact / clearly backlog): bench-eval-local, holo31, ideogram4, lm-studio-uncen-benchmark, lobehub, lora-ops-copilot, rotorquant, switch-server, turboquant-mlx, vllm-mlx-homebrew-formula, vlm-visual-agent-benchmark-harness.

Report the final classification with evidence in the session summary before this commit.

### Commit 7 — relocate root strays

- `git mv huggingface-skills-analysis.md plans/done/plan-huggingface-skills-analysis.md` — concluded research analysis (2026-05-15); add row to Done table in `plans/README.md`. Sweep: `grep -rn "huggingface-skills-analysis" --include="*.md" .`
- `git mv html/peft-lora-quick-understanding.html docs/models/techniques/model-technique-peft-lora.html`; delete now-empty `html/`; add row to `docs/models/techniques/README.md` index (note HTML format). Sweep: `grep -rn "peft-lora-quick-understanding\|html/" --include="*.md" .`
- Move `prompts/` → `plans/prompts/` (both files are planning prompts: `build-adjust-active-plans.md` literally maintains `plans/active/`; `fine-tuning-PEFT-LoRA-experiments.md` generates LoRA experiment plans). Plain `mv` + `git add` (untracked). Add a short "Prompts" section to `plans/README.md` listing both files. Fix the absolute path inside `build-adjust-active-plans.md` if it references the old location.

### Final verification (after commit 7)

1. Pre-commit drift check from CLAUDE.md:
   `grep -rn "current production\|production main\|production primary\|currently running\|currently stopped\|Last main\|Active model:" README.md AGENTS.md CLAUDE.md configs/README.md docs/ || true`
2. Broken-link sweep for every moved path:
   `grep -rn "benchmarks/deepseek-v4-flash\|benchmarks/lfm2.5-8b-a1b-q8\|plan-llmster\|plan-gemma-4-31b-llmster\|huggingface-skills-analysis.md\|html/peft-lora\|prompts/build-adjust\|prompts/fine-tuning" --include="*.md" --include="*.json" --include="*.py" . | grep -v plans/done` — expect only intentional historical mentions.
3. Index↔disk parity: for `plans/`, `docs/models/`, `docs/models/techniques/` — every file on disk appears in its README, every README link resolves (`ls` vs index rows).
4. CLAUDE.md ↔ AGENTS.md parity check (tail -n +4 diff).
5. `git status` clean except intentionally-ignored `RTK.md` absence from status.

## Out of scope

- `scripts/` — already conformant, no changes.
- Backfilling client-config templates for provisional servers (intentional deferral per configs/clients/README).
- Renaming historical `llmster` mentions inside doc prose / JSON filenames.
- `docs/models/uncen-model/` submodule — untouched.
- Pushing to origin — left to the user (repo already ahead of origin/main).
