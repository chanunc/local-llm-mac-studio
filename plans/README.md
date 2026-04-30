# Plans

Plans are design notes and work queues. They are not live runbooks and should not be treated as canonical operational truth. Use `docs/current.md` for current state and `docs/server/` for runbooks.

## Folders

| Folder | Meaning |
|:--|:--|
| `active/` | Work that is still planned or in progress |
| `done/` | Implemented plans kept for historical context |
| `archive/` | Superseded or abandoned ideas |

## Current Index

### Active

| Plan | Topic |
|:--|:--|
| [`active/plan-llmster-uncen-benchmark.md`](active/plan-llmster-uncen-benchmark.md) | llmster uncensored-model benchmark slate |
| [`active/plan-lobehub-macstudio-setup.md`](active/plan-lobehub-macstudio-setup.md) | LobeHub config against Mac Studio servers |
| [`active/plan-mac-studio-lmstudio-ollama-benchmark.md`](active/plan-mac-studio-lmstudio-ollama-benchmark.md) | LM Studio / Ollama benchmark comparison |
| [`active/plan-rotorquant-apple-silicon-implementation.md`](active/plan-rotorquant-apple-silicon-implementation.md) | RotorQuant feasibility on Apple Silicon |
| [`active/plan-switch-server.md`](active/plan-switch-server.md) | Server/model switcher script design |
| [`active/plan-turboquant-mlx-implementation.md`](active/plan-turboquant-mlx-implementation.md) | TurboQuant feasibility and implementation plan |
| [`active/plan-vllm-mlx-homebrew-formula.md`](active/plan-vllm-mlx-homebrew-formula.md) | vllm-mlx Homebrew formula/tap |

### Done

| Plan | Topic |
|:--|:--|
| [`done/plan-hot-cache-max-size-per-model.md`](done/plan-hot-cache-max-size-per-model.md) | oMLX per-model hot cache patch |

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

When a plan is implemented, move it to `done/` or `archive/` and update any live documentation separately.
