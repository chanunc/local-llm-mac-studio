# Model Summary: Qwen3-Coder Family

Alibaba's Qwen3-Coder lineage as catalogued in this stack. Two variants: the 80 B sparse-MoE flagship (Qwen3-Coder-Next 6-bit) used as the daily coding driver, and the compact 30 B/3 B-active 4-bit variant for tighter memory budgets.

## Index

- [Qwen3-Coder-Next (6-bit)](#qwen3-coder-next-6-bit) — Daily driver (coding)
- [Qwen3-Coder-30B-A3B Instruct (4-bit)](#qwen3-coder-30b-a3b-instruct-4-bit) — Compact coding model

---

## 🤖 Qwen3-Coder-Next (6-bit)

80B sparse MoE with only 3B active params. Optimized for coding agents and IDE integration. Performance comparable to Claude Sonnet 4.0 on SWE tasks. This is the **daily driver** model. The 6-bit quantization provides the best quality/size balance with 128-170K context on 96GB.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3-Coder-Next](https://huggingface.co/Qwen/Qwen3-Coder-Next) |
| MLX 6-bit | [mlx-community/Qwen3-Coder-Next-6bit](https://huggingface.co/mlx-community/Qwen3-Coder-Next-6bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 80B total, 3B active (512 experts, 10 routed + 1 shared) |
| Density | Sparse MoE |
| Specialties | Code generation, agentic reasoning, tool use, long-horizon recovery |
| Tokens/sec | ~40-60 tok/s on M3 Ultra (6-bit) |
| Context Size | 128K - 170K on 96GB (262K native limit) |
| On-disk size | ~60 GB |
| Cache | KV cache on 12/48 Gated Attention layers; supports q8/q4/FP8 cache quantization |
| Key Benchmarks | SWE-Bench Verified 42.8%, SWE-Bench Pro 44.3% |

**Caveats:**
- Non-thinking mode only (no `<think>` blocks)
- MLX KV cache issues during conversation branching

---

## 🤖 Qwen3-Coder-30B-A3B Instruct (4-bit)

Smaller Qwen coder MoE tuned for agentic coding and tool use. This is a compact coding option for local MLX servers when you want something smaller than Qwen3-Coder-Next.

| Spec | Value |
|:-----|:------|
| Base Model | [Qwen/Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) |
| MLX 4-bit | [mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit) |
| Vendor | Alibaba Qwen team; MLX by mlx-community |
| Parameters | 30.5B total, 3.3B active |
| Density | Sparse MoE |
| Architecture | `qwen3_moe` |
| Specialties | Agentic coding, browser use, function calling |
| Context Size | 262,144 tokens native (256K) |
| On-disk size | 17.2 GB |
| Current server use | Not in the default live server roster |
| Key Notes | Non-thinking mode only; does not emit `<think></think>` blocks |

**Caveats:**
- Compact coding tradeoff, not a drop-in quality replacement for Qwen3-Coder-Next 80B
- Long contexts still need memory discipline in practice when paired with another loaded model

---

## See also

- Catalog stub: [`docs/models/model-summary.md` § Qwen3-Coder Family](../model-summary.md#qwen3-coder-family-mlx-6-bit--4-bit)
- Sibling per-model files: [`model-summary-qwen-3-5.md`](model-summary-qwen-3-5.md) · [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md)
