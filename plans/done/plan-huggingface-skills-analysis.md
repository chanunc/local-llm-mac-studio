# Hugging Face Skills Analysis

Status: done
Created: 2026-05-15
Completed: 2026-05-15
Canonical: no

## Summary

Hugging Face Agent Skills can help this repository, but only as supporting Hub workflow helpers. They should not replace this repo's existing Mac Studio deployment, benchmark, and documentation workflows.

The highest-value addition is the Hugging Face CLI skill (`hf-cli`). It can make model discovery, metadata inspection, quant-file selection, download, and Hub cache operations more reliable. The `huggingface-datasets` skill may also help when local evaluation work moves from documentation into implementation.

## What Hugging Face Provides

Hugging Face publishes a marketplace of agent skills for coding agents, including OpenAI Codex. The documented install shape is:

```text
/plugin marketplace add huggingface/skills
/plugin install <skill-name>@huggingface/skills
```

Relevant available skills include:

| Skill | Relevance |
|:--|:--|
| `hf-cli` | Hub operations through the `hf` CLI: model metadata, downloads, uploads, repo management, jobs. |
| `huggingface-datasets` | Dataset discovery, row pagination, filtering, and search. |
| `huggingface-community-evals` | Evaluation workflows against Hub models. |
| `huggingface-papers` | Search and read HF paper pages in markdown. |
| `huggingface-llm-trainer` | Fine-tune LLMs on Hugging Face Jobs. |
| `gradio` | Build Gradio web UIs and demos. |
| `transformers-js` | Run models in JavaScript/TypeScript with WebGPU/WASM. |

HF also documents `hf skills add`, which generates an agent skill from the locally installed `hf` CLI. That is useful because the generated skill can track the installed CLI version.

References:

- <https://huggingface.co/docs/hub/en/agents-skills>
- <https://huggingface.co/docs/hub/agents-cli>
- <https://huggingface.co/docs/hub/en/agents-overview>

## Current Repo Coverage

This repository already has stronger domain-specific automation than the generic HF skills for the critical path:

- `AGENTS.md` documents `/deploy-run-benchmark-uncen-model`, which already handles Mac Studio hygiene, deployment, smoke/refusal/perf/agent benchmarks, and documentation sync for uncensored model deployments.
- `plans/active/plan-deploy-run-benchmark-model-skill.md` already defines a universal deploy-and-benchmark skill for both censored and uncensored models.
- `AGENTS.md` has precise Sync Policy rules for new model files, live-state changes, production model switches, benchmarks, scripts, plans, and technique docs.
- `AGENTS.md` includes mandatory pre-benchmark hygiene that stops competing Mac Studio LLM servers before a model benchmark.
- `scripts/list_model_to_remove.py` already ports a local model cleanup skill and knows the repo's Hugging Face cache, LM Studio, oMLX, and staging paths.
- `docs/models/how-to/eval-benchmark-local-runners.md` already captures local MMLU, MMLU-Pro, TruthfulQA, HarmBench, and refusal-rate runner guidance.

HF skills do not know this stack's server matrix, parser flags, port conflicts, Mac Studio memory constraints, model-family gotchas, benchmark JSON conventions, or doc sync rules. They should not own deployment orchestration.

## Where HF Skills Help

### `hf-cli`

Recommended. This is the clearest win.

Use it to improve the discovery and metadata phases of deploy work:

- Query model metadata.
- List repository siblings and quant files.
- Inspect file sizes before download.
- Download snapshots or specific GGUF / MLX files.
- Inspect model cards and discussions.
- Manage Hub cache behavior.

This overlaps with the planned universal deploy skill's Phase 0/1 logic and the existing uncensored skill's use of `hf_hub_download` and `hf download`.

### `huggingface-datasets`

Useful for eval work.

This can help with reproducible subsets and local evaluation datasets, especially for MMLU-style, TruthfulQA-style, HarmBench-style, and refusal-rate workflows. It should complement, not replace, the local eval runner notes and scripts.

### `huggingface-community-evals`

Possibly useful, but secondary.

This repo's benchmarks focus on local OpenAI-compatible endpoints, tool calls, agent loops, TTFT, prefill, generation throughput, and Mac Studio server behavior. HF community evals may help for model-card style reporting, but they should not replace the local benchmark scripts.

### `huggingface-papers`

Useful as research support.

This can help collect paper context for technique docs such as DFlash, JANG, TurboQuant, MTP, and model architecture notes. Operational conclusions should still land in `docs/models/techniques/` and server runbooks.

## Low-Value Skills For This Repo

These are not priorities right now:

| Skill | Reason |
|:--|:--|
| `huggingface-llm-trainer` | The repo is currently an inference and benchmarking lab, not a training pipeline. |
| `huggingface-vision-trainer` | Same; no current vision training workflow. |
| `huggingface-trackio` | No active training experiment tracking need. |
| `huggingface-paper-publisher` | No current paper publishing workflow. |
| `gradio` | ComfyUI already covers the current image-generation sidecar; the repo is not building hosted demos. |
| `transformers-js` | Browser/WebGPU inference is outside the Mac Studio server focus. |

## Recommendation

Install only the HF CLI skill first:

```text
/plugin marketplace add huggingface/skills
/plugin install hf-cli@huggingface/skills
```

Then consider `huggingface-datasets` when the local eval plan moves into implementation.

Do not let Hugging Face skills replace the repo's deployment and benchmark skills. The correct integration model is:

1. Use HF skills for Hub-facing primitives: metadata, downloads, datasets, papers.
2. Keep Mac Studio deployment, benchmark orchestration, live-state changes, and documentation sync under this repo's existing AGENTS/CLAUDE rules and local skills.
3. If the universal `/deploy-run-benchmark-model` skill is implemented, allow it to call HF CLI operations during discovery/download phases, while preserving the repo-specific hygiene, benchmark, and sync phases.

## Practical Next Step

Add `hf-cli` as a project-level helper skill and update the planned universal deploy skill to explicitly use it during Phase 0 and Phase 1. That gives the repo the useful part of HF's agent integration without weakening the Mac Studio-specific operating discipline.
