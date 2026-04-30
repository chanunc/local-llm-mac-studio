# Model Docs

Model catalog, compatibility notes, and benchmark summaries for the Mac Studio stack.

| Doc | Purpose |
|:--|:--|
| [`model-summary.md`](model-summary.md) | Canonical parent-repo model catalog |
| [`model-summary-ling.md`](model-summary-ling.md) | Ling-2.6-flash deployment and caveats |
| [`model-summary-mimo-v2.5.md`](model-summary-mimo-v2.5.md) | MiMo V2.5 failure analysis and benchmark notes |
| [`model-benchmark-api-server.md`](model-benchmark-api-server.md) | API server throughput, TTFT, and prefill results |
| [`model-benchmark-agent-tool-call.md`](model-benchmark-agent-tool-call.md) | OpenCode and tool-call latency results |
| [`model-benchmark-standalone.md`](model-benchmark-standalone.md) | Standalone generation benchmarks |
| [`model-benchmark-turboquant-jang.md`](model-benchmark-turboquant-jang.md) | TurboQuant / JANG benchmark notes |
| [`model-conversion-gguf-mlx.md`](model-conversion-gguf-mlx.md) | GGUF to MLX conversion notes |
| [`model-qwen-null-think-template-test.md`](model-qwen-null-think-template-test.md) | Qwen thinking-template test notes |
| [`benchmarks/`](benchmarks/) | Raw JSON and log outputs |
| [`uncen-model/`](uncen-model/) | Private submodule for uncensored-model research |

Keep production-track model specs in `model-summary.md`. Keep detailed one-off deployment or failure reports in dedicated `model-summary-*.md` files and link back from the catalog.
