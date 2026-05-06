# Tuning

Practical guide to the tuning surface across the Mac Studio LLM stack. Two orthogonal entry points:

| File | Use when |
|:--|:--|
| [`tuning-by-knob.md`](tuning-by-knob.md) | You know which knob you want to change (`--prefill-step-size`, thinking flag, drafter, quant, etc.) and need to know what it actually does and whether it is worth touching on our hardware. |
| [`tuning-by-workload.md`](tuning-by-workload.md) | You know what workload you are running (raw chat, single-turn tool call, agent loop) and need to know which knobs dominate that regime. |

The two files cross-reference; start at whichever side you are on.

## Scope

These docs cover **operational tuning** of running servers — flags, env vars, and chat-template choices that change throughput, latency, or correctness without re-quantising weights or swapping model architectures. Out of scope:

- Per-server runbooks (start/stop, log paths, ports) → [`../servers/`](../servers/)
- Per-model deployment recipes and spec tables → [`../models/per-model/`](../models/per-model/)
- Cross-cutting technique deep dives (DFlash, JANG, JANGTQ, prefill-speed, `bailing_hybrid`) → [`../models/techniques/`](../models/techniques/)
- Raw benchmark numbers → [`../models/benchmarks/`](../models/benchmarks/)

## Conventions

- Each knob entry leads with **what it does**, then *workload sensitivity*, then *our local measurement* if we have one.
- "Local measurement" means a number from `scripts/bench/` on the M3 Ultra, not a vendor-quoted figure.
- When a knob is documented as "not worth tuning on our hardware", the reason is captured inline so future investigations do not re-discover the same dead end.
