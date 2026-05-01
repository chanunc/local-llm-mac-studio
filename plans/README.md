# Plans

Plans are design notes and work queues. They are **not** live runbooks and should not be treated as canonical operational truth. Use [`docs/current.md`](../docs/current.md) for current state and [`docs/servers/`](../docs/servers/) for runbooks.

## Folders

| Folder | Meaning |
|:--|:--|
| [`active/`](active/) | Work that is still planned or in progress |
| [`done/`](done/) | Implemented plans kept for historical context |
| [`archive/`](archive/) | Superseded or abandoned ideas |

## Current Index

### Active

| Plan | Topic |
|:--|:--|
| [`active/plan-dflash-regression-investigation.md`](active/plan-dflash-regression-investigation.md) | Diagnose and fix DFlash regression on Mac Studio M3 Ultra |
| [`active/plan-llmster-uncen-benchmark.md`](active/plan-llmster-uncen-benchmark.md) | llmster uncensored-model benchmark slate |
| [`active/plan-lobehub-macstudio-setup.md`](active/plan-lobehub-macstudio-setup.md) | LobeHub config against Mac Studio servers |
| [`active/plan-osaurus-qwen36-jangtq4-vmlx-agent-bench.md`](active/plan-osaurus-qwen36-jangtq4-vmlx-agent-bench.md) | Deploy Osaurus Qwen3.6-35B-A3B JANGTQ4 as main vmlx server and run OpenCode agent benchmark |
| [`active/plan-rotorquant-apple-silicon-implementation.md`](active/plan-rotorquant-apple-silicon-implementation.md) | RotorQuant feasibility on Apple Silicon |
| [`active/plan-switch-server.md`](active/plan-switch-server.md) | Server/model switcher script design |
| [`active/plan-turboquant-mlx-implementation.md`](active/plan-turboquant-mlx-implementation.md) | TurboQuant feasibility and implementation plan |
| [`active/plan-vllm-mlx-homebrew-formula.md`](active/plan-vllm-mlx-homebrew-formula.md) | vllm-mlx Homebrew formula/tap |

### Done

| Plan | Topic |
|:--|:--|
| [`done/plan-dflash-mlx-deploy.md`](done/plan-dflash-mlx-deploy.md) | dflash-mlx sidecar (Qwen3.6-35B-A3B + DFlash drafter) — shipped 2026-04-30, runbook at `docs/servers/dflash-mlx/summary.md` |
| [`done/plan-hot-cache-max-size-per-model.md`](done/plan-hot-cache-max-size-per-model.md) | oMLX per-model hot cache patch (shipped, lives in `scripts/patches/patch_omlx_cache.py`) |
| [`done/plan-mac-studio-lmstudio-ollama-benchmark.md`](done/plan-mac-studio-lmstudio-ollama-benchmark.md) | LM Studio / Ollama benchmark — drove llmster adoption 2026-04-30 |
| [`done/plan-rearrange-docs-organization.md`](done/plan-rearrange-docs-organization.md) | Repo structure reorganization (this layout) |
| [`done/plan-gemma-4-31b-llmster.md`](done/plan-gemma-4-31b-llmster.md) | Deploy Gemma 4 31B-it on llmster + 3 benchmarks (shipped 2026-05-01) — agent-loop champion at 5–6 s wall |

### Archive

| Plan | Topic |
|:--|:--|
| [`archive/plan-itermai-omlx-setup.md`](archive/plan-itermai-omlx-setup.md) | iTermAI to oMLX setup notes |

## Plan Metadata

New plans should start with a small status block:

```md
Status: active
Created: YYYY-MM-DD
Canonical: no
```

When a plan is implemented or abandoned, move the file to `done/` or `archive/`, then update this README's index. Updating this file is part of the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) for any plan that touches live state.
