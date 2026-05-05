# Model Docs

Model catalog, deployment notes, and benchmark results for the Mac Studio stack. Layout reflects content type — keep new files in the matching subdirectory.

## Layout

| Path | Purpose |
|:--|:--|
| [`model-summary.md`](model-summary.md) | Canonical catalog. Index + per-model spec tables. Start here. |
| [`per-model/`](per-model/) | Long-form deployment write-ups for individual models (Ling, MiMo). Catalog entry should stub-link here when a per-model file exists. |
| [`techniques/`](techniques/) | Inference-side technique notes (speculative decoding, caching, quantisation profiles) — what they are, when they help, hardware sensitivity. |
| [`benchmarks/`](benchmarks/) | Cross-model benchmark write-ups + raw JSON/log outputs grouped by model slug. |
| [`how-to/`](how-to/) | One-off conversion / template / debugging guides. |
| [`uncen-model/`](uncen-model/) | Private submodule for uncensored-model research. |

## Per-model deep dives

| File | Topic |
|:--|:--|
| [`per-model/model-summary-ling.md`](per-model/model-summary-ling.md) | Ling-2.6-flash deployment recipe (`bailing_hybrid` patches, server flags, caveats). |
| [`per-model/model-summary-mimo-v2.5.md`](per-model/model-summary-mimo-v2.5.md) | MiMo V2.5 three-config investigation and failure analysis. |
| [`per-model/model-summary-qwen-3-coder.md`](per-model/model-summary-qwen-3-coder.md) | Qwen3-Coder family (Coder-Next 6-bit, Coder-30B-A3B 4-bit). |
| [`per-model/model-summary-qwen-3-5.md`](per-model/model-summary-qwen-3-5.md) | Qwen3.5 family (4 variants: 27B Opus Distilled, 122B-A10B 4-bit, 122B-A10B JANG 2S, 35B-A3B JANG 4K). |
| [`per-model/model-summary-qwen-3-6.md`](per-model/model-summary-qwen-3-6.md) | Qwen3.6 family (7 variants: 35B-A3B 6-bit/4-bit, Osaurus JANGTQ4, 27B JANG 4M, 27B 6-bit, HauhauCS Q8_K_P GGUF, 35B Rust LoRA). |
| [`per-model/model-summary-nemotron.md`](per-model/model-summary-nemotron.md) | Nemotron family (Nano 30B, Super 120B, Cascade-2 30B) + cross-cutting server compatibility note. |
| [`per-model/model-summary-gemma.md`](per-model/model-summary-gemma.md) | Gemma 4 family (26B-A4B 4-bit MoE multimodal, 31B-it 6-bit dense text-only). |
| [`per-model/model-summary-granite-4.1.md`](per-model/model-summary-granite-4.1.md) | IBM Granite 4.1 30B Q8_0 GGUF — active llmster main (2026-05-05), Apache 2.0, 24.8 tok/s. |

## Benchmarks

| File | Coverage |
|:--|:--|
| [`benchmarks/model-benchmark-api-server.md`](benchmarks/model-benchmark-api-server.md) | API throughput / TTFT / prefill across servers. |
| [`benchmarks/model-benchmark-tool-call.md`](benchmarks/model-benchmark-tool-call.md) | OpenCode agent loop end-to-end latency. |
| [`benchmarks/model-benchmark-agent-local.md`](benchmarks/model-benchmark-agent-local.md) | llama-agent in-process agent loop (no API server in the path). |
| [`benchmarks/model-benchmark-standalone.md`](benchmarks/model-benchmark-standalone.md) | Standalone generation benchmarks. |
| [`benchmarks/model-benchmark-turboquant-jang.md`](benchmarks/model-benchmark-turboquant-jang.md) | TurboQuant / JANG benchmark notes. |
| [`benchmarks/<model-slug>/`](benchmarks/) | Raw `agent-bench.json`, `api-server-<server>.json`, and per-run logs. |

## How-to

| File | Topic |
|:--|:--|
| [`how-to/model-conversion-gguf-mlx.md`](how-to/model-conversion-gguf-mlx.md) | GGUF → MLX safetensors conversion. |
| [`how-to/model-qwen-null-think-template-test.md`](how-to/model-qwen-null-think-template-test.md) | Qwen null-think chat template test. |
| [`how-to/eval-benchmark-local-runners.md`](how-to/eval-benchmark-local-runners.md) | Run MMLU / MMLU-Pro / TruthfulQA / HarmBench / refusal-rate locally against llmster / vmlx / vllm-mlx OpenAI endpoints. |

## Conventions

- Production-track specs go in [`model-summary.md`](model-summary.md) — keep one row in the Index plus one per-model section.
- If a model needs more than ~150 lines of detail, put it in [`per-model/`](per-model/) and stub-link from the catalog.
- Benchmark JSON belongs under [`benchmarks/<model-slug>/`](benchmarks/) named `<benchmark-type>.json` or `<benchmark-type>-<server>.json` for cross-server comparisons.
- Add new content following the [Sync Policy](../../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) — README.md, model-summary.md, and the relevant client config file all need to land together.
