# Model Techniques

Cross-cutting reference notes on **model-level techniques, quantisation formats, and architectures** that affect how models run on the Mac Studio stack. Distinct from:

- [`../per-model/`](../per-model/) — per-model deployment recipes and spec
- [`../benchmarks/`](../benchmarks/) — raw performance numbers
- [`../../servers/`](../../servers/) — server runbooks (start/stop, logs, ports)

These docs are evidence-based and synthesise local data + external research + hypothesis ranking + recommendation. Each file is the canonical *what-it-is* reference; server runbooks cover operational steps and link back here for the technique explanation.

## Naming convention

Filenames carry the category prefix so the type of doc is obvious:

| Prefix | Meaning | Example |
|:--|:--|:--|
| `model-technique-` | Generation-time technique (speculative decoding, prompt caching, prefix caching) | [`model-technique-dflash.md`](model-technique-dflash.md) |
| `model-quantization-` | Weight or activation quantisation format / KV cache compression | [`model-quantization-jang.md`](model-quantization-jang.md), [`model-quantization-turboquant.md`](model-quantization-turboquant.md) |
| `model-architecture-` | Model architecture pattern that requires cross-cutting deployment treatment | [`model-architecture-bailing-hybrid.md`](model-architecture-bailing-hybrid.md) |

## Index

| File | Category | Topic |
|:--|:--|:--|
| [`model-technique-dflash.md`](model-technique-dflash.md) | Technique | DFlash block-diffusion speculative decoding — what it is, cross-fork landscape (bstnxbt vs Aryagm), M3 Ultra workload-gated regression analysis. |
| [`model-quantization-jang.md`](model-quantization-jang.md) | Quantisation | JANG adaptive mixed-precision weight format — format properties, three per-server integration approaches, cross-server perf, Nemotron-H caveat. |
| [`model-quantization-turboquant.md`](model-quantization-turboquant.md) | Quantisation | TurboQuant KV cache compression (Google ICLR 2026) + JANGTQ weight format — algorithm, MLX implementations (PR #858 + flovflo), JANGTQ-only vmlx requirement. |
| [`model-architecture-bailing-hybrid.md`](model-architecture-bailing-hybrid.md) | Architecture | InclusionAI's `bailing_hybrid` MoE — 4 MLA + 28 Lightning recurrence layers, the canonical 3-patch deploy recipe, server compatibility matrix. |

## Conventions

- One file per technique. Filename leads with `model-<category>-` so listing the folder shows the category at a glance.
- Lead with **what it is** in one paragraph for readers who do not know the technique yet, then *how it integrates with this stack*, then performance / known limitations / cross-references.
- Cross-link to `../benchmarks/` for raw JSON, `../../servers/<name>/summary.md` for runbooks, `../per-model/` for model-specific deployment, and `../../../plans/active/` if there is an active investigation plan.
- If a technique becomes operationally adopted, surface the conclusion in [`../../current.md`](../../current.md) and the relevant server runbook — keep the deeper notes here.

Future fits: `model-technique-prefix-caching.md`, `model-technique-prompt-caching.md`, `model-architecture-mimo-v2.md`, `model-quantization-mlx-mxfp4.md`, etc.
