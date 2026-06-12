# Plans

Plans are design notes and work queues. They are **not** live runbooks and should not be treated as canonical operational truth. Run [`scripts/chk_llm_macstu.py`](../scripts/chk_llm_macstu.py) for live run-state (it is intentionally not recorded in any doc) and see [`docs/servers/`](../docs/servers/) for runbooks.

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
| [`active/plan-bench-eval-local.md`](active/plan-bench-eval-local.md) | MMLU-Pro + TruthfulQA-gen local benchmark driver (`bench_eval_local.py`) |
| [`active/plan-holo31-macstudio-computer-use-eval.md`](active/plan-holo31-macstudio-computer-use-eval.md) | Select Holo 3.1 MLX/GGUF variants for Mac Studio and build a staged computer-use benchmark |
| [`active/plan-ideogram4-macstudio-eval.md`](active/plan-ideogram4-macstudio-eval.md) | Ideogram 4 FP8 on ComfyUI/MPS plus an agent-style design-redesign benchmark |
| [`active/plan-lm-studio-uncen-benchmark.md`](active/plan-lm-studio-uncen-benchmark.md) | lm-studio uncensored-model benchmark slate |
| [`active/plan-lobehub-macstudio-setup.md`](active/plan-lobehub-macstudio-setup.md) | LobeHub config against Mac Studio servers |
| [`active/plan-lora-ops-copilot.md`](active/plan-lora-ops-copilot.md) | LoRA "Mac Studio ops copilot" — PEFT/TRL adapter on `Qwen3.5-2B` for repo-specific ops Q&A, MacBook M1 Pro 16GB inference |
| [`active/plan-mlx-vlm-qwen-vl-deploy-benchmark.md`](active/plan-mlx-vlm-qwen-vl-deploy-benchmark.md) | Update `mlx-vlm`, deploy Qwen VL 4-bit sidecar, then run agent tooling and visual-agent benchmarks |
| [`active/plan-reorganise-repo-structure.md`](active/plan-reorganise-repo-structure.md) | Re-organise scripts, docs, and folders — fix post-April-2026 drift ([visual HTML](active/plan-reorganise-repo-structure.html)) |
| [`active/plan-rotorquant-apple-silicon-implementation.md`](active/plan-rotorquant-apple-silicon-implementation.md) | RotorQuant feasibility on Apple Silicon |
| [`active/plan-switch-server.md`](active/plan-switch-server.md) | Server/model switcher script design |
| [`active/plan-turboquant-mlx-implementation.md`](active/plan-turboquant-mlx-implementation.md) | TurboQuant feasibility and implementation plan |
| [`active/plan-vlm-visual-agent-benchmark-harness.md`](active/plan-vlm-visual-agent-benchmark-harness.md) | Visual-agent benchmark harness for OCR, chart, screenshot, and video tasks with HITL fixture review |
| [`active/plan-vllm-mlx-homebrew-formula.md`](active/plan-vllm-mlx-homebrew-formula.md) | vllm-mlx Homebrew formula/tap |

### Done

| Plan | Topic |
|:--|:--|
| [`done/plan-dflash-mlx-deploy.md`](done/plan-dflash-mlx-deploy.md) | dflash-mlx sidecar (Qwen3.6-35B-A3B + DFlash drafter) — shipped 2026-04-30, runbook at `docs/servers/dflash-mlx/summary.md` |
| [`done/plan-hot-cache-max-size-per-model.md`](done/plan-hot-cache-max-size-per-model.md) | oMLX per-model hot cache patch (shipped, lives in `scripts/patches/patch_omlx_cache.py`) |
| [`done/plan-mac-studio-lmstudio-ollama-benchmark.md`](done/plan-mac-studio-lmstudio-ollama-benchmark.md) | LM Studio / Ollama benchmark — drove lm-studio adoption 2026-04-30 |
| [`done/plan-ollama-top-benchmark-models.md`](done/plan-ollama-top-benchmark-models.md) | Ollama deployment comparison for top non-Qwen3.6-A3B benchmark models (`gemma4:26b`, Granite 4.1 30B, Gemma 4 31B) |
| [`done/plan-rearrange-docs-organization.md`](done/plan-rearrange-docs-organization.md) | Repo structure reorganization (this layout) |
| [`done/plan-gemma-4-31b-lm-studio.md`](done/plan-gemma-4-31b-lm-studio.md) | Deploy Gemma 4 31B-it on lm-studio + 3 benchmarks (shipped 2026-05-01) — agent-loop champion at 5–6 s wall |
| [`done/plan-deploy-run-benchmark-uncen-model-skill.md`](done/plan-deploy-run-benchmark-uncen-model-skill.md) | `/deploy-run-benchmark-uncen-model` skill — six-phase deploy + bench + docs runner, shipped 2026-05-02 to `~/.claude/skills/deploy-run-benchmark-uncen-model/` |
| [`done/plan-list-model-to-remove-python.md`](done/plan-list-model-to-remove-python.md) | `scripts/list_model_to_remove.py` — LLM-free Python port of `/list-model-to-remove`, verified by dry run against Mac Studio |
| [`done/plan-deploy-huihui-qwen36-35b-mtp-abliterated.md`](done/plan-deploy-huihui-qwen36-35b-mtp-abliterated.md) | huihui-ai Qwen3.6-35B-A3B Claude-4.7-Opus-abliterated MTP Q6_K — first MoE+MTP on llama-cpp-mtp, shipped 2026-05-20 with benchmarks |
| [`done/plan-chk-llm-macstu.md`](done/plan-chk-llm-macstu.md) | `scripts/chk_llm_macstu.py` — Mac Studio LLM server + model status probe (shipped 2026-05-04) |
| [`done/plan-comfyui-zanime-sidecar.md`](done/plan-comfyui-zanime-sidecar.md) | ComfyUI sidecar (port 8188) for Z-Image / Z-Anime — shipped 2026-05-08, runbook at `docs/servers/comfyui/summary.md` |
| [`done/plan-deploy-llama-cpp-mtp-sidecar-qwen36-27b.md`](done/plan-deploy-llama-cpp-mtp-sidecar-qwen36-27b.md) | `llama-cpp-mtp` sidecar (port 8100) with Qwen3.6-27B-MTP UD-Q6_K_XL — shipped 2026-05-14 |
| [`done/plan-list-model-to-remove.md`](done/plan-list-model-to-remove.md) | `/list-model-to-remove` skill design — shipped 2026-06-02 (`scripts/list_model_to_remove.py`) |
| [`done/plan-deploy-run-benchmark-model-skill.md`](done/plan-deploy-run-benchmark-model-skill.md) | `/deploy-run-benchmark-model` skill — shipped 2026-05-05, handles censored + uncensored models |
| [`done/plan-dflash-regression-investigation.md`](done/plan-dflash-regression-investigation.md) | DFlash regression on M3 Ultra — concluded 2026-04-30: regresses vs baseline, upstream-tracking only |
| [`done/plan-osaurus-qwen36-jangtq4-vmlx-agent-bench.md`](done/plan-osaurus-qwen36-jangtq4-vmlx-agent-bench.md) | Osaurus Qwen3.6-35B-A3B JANGTQ4 via vmlx — shipped 2026-05-14 with agent benchmarks |
| [`done/plan-upgrade-llama-cpp-benchmark-gemma4-31b-mtp.md`](done/plan-upgrade-llama-cpp-benchmark-gemma4-31b-mtp.md) | llama.cpp upgrade + Gemma 4 31B dense MTP benchmark — completed 2026-06-10 |
| [`done/plan-huggingface-skills-analysis.md`](done/plan-huggingface-skills-analysis.md) | Hugging Face skills (hf-cli, HF datasets) fitness assessment for this repo — concluded 2026-05-15 |
| [`done/plan-switch-top-model-script.md`](done/plan-switch-top-model-script.md) | `scripts/switch_top_model.py` — benchmark-driven top-5 model switcher with OpenCode sync + tool-call smoke test, shipped 2026-06-12 ([visual HTML](done/plan-switch-top-model-script.html)) |

### Archive

| Plan | Topic |
|:--|:--|
| [`archive/plan-itermai-omlx-setup.md`](archive/plan-itermai-omlx-setup.md) | iTermAI to oMLX setup notes |

### Prompts

Reusable prompts for driving planning sessions. Not plans themselves — pass to an agent or use as a starting point.

| File | Purpose |
|:--|:--|
| [`prompts/build-adjust-active-plans.md`](prompts/build-adjust-active-plans.md) | Prompt for creating or revising active plans under `plans/active/` |
| [`prompts/fine-tuning-PEFT-LoRA-experiments.md`](prompts/fine-tuning-PEFT-LoRA-experiments.md) | Prompts for planning focused PEFT/LoRA experiments (behavior specialization, not compression) |

## Plan Metadata

New plans should start with a small status block:

```md
Status: active
Created: YYYY-MM-DD
Canonical: no
```

When a plan is implemented or abandoned, move the file to `done/` or `archive/`, then update this README's index. Updating this file is part of the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) for any plan that touches live state.
