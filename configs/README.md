# Configs — Active Model Reference

**Last updated: 2026-03-16**

This directory contains ready-to-use client config files for connecting to the Mac Studio M3 Ultra oMLX server. Copy each file to its destination path and replace `<MAC_STUDIO_IP>` and `<YOUR_API_KEY>` with real values.

## Currently Active Models

Two models are loaded in RAM on the Mac Studio (96GB unified memory). Both run fully in-memory with no SSD KV cache spill.

| Model | ID | Context | Memory | Role |
|-------|----|---------|--------|------|
| Qwen3.5 35B-A3B 8-bit | `mlx-community/Qwen3.5-35B-A3B-8bit` | **262,144** tokens | 36.9 GB | Default / SWE agent |
| Nemotron 3 Nano 30B-A3B 8-bit | `NVIDIA-Nemotron-3-Nano-30B-A3B-MLX-8Bit` | **650,000** tokens | 32.8 GB | Long-context tasks |

### Qwen3.5 35B-A3B 8-bit
- **Vendor:** Alibaba Qwen team; MLX by mlx-community
- **Architecture:** 35B sparse MoE, 3B active params (256 experts, 8 routed + 1 shared)
- **Context:** 262,144 tokens native (256K)
- **Strengths:** SWE-bench 69.2%, efficient high-throughput, thinking mode
- **Default model** — pinned in oMLX, loads on startup

### Nemotron 3 Nano 30B-A3B 8-bit
- **Vendor:** NVIDIA; MLX by mlx-community
- **Architecture:** 32B hybrid MoE — 23 Mamba2 layers + 23 attention layers, 3B active params, 2 KV heads
- **Context:** 650,000 tokens *(RAM-optimised: calculated from 16.3 GB available KV headroom at bfloat16; avoids SSD spill)*
- **Strengths:** Efficient long-context inference, multilingual (6 languages), KV-efficient hybrid architecture
- **Note:** Use model ID without `mlx-community/` prefix in client configs

## Context Size Notes

Nemotron's 650K context limit is derived from the available RAM after both models are loaded:

```
Process limit:   88.0 GB
Both models:    −69.7 GB
Overhead:        −2.0 GB
─────────────────────────
KV headroom:    ~16.3 GB

KV per token = 2 × 23 attn layers × 2 KV heads × 128 head_dim × 2 bytes = 23 KB
16.3 GB ÷ 23 KB × 90% safety = ~650,000 tokens
```

Qwen3.5 35B-A3B context is capped at its native 262,144 — the remainder is used by Nemotron's KV pool.

## Config Files

| File | Copy to | Used by |
|------|---------|---------|
| `claude-code-macstudio-settings.json` | `~/.claude/macstudio-settings.json` | Claude Code |
| `opencode.json` | `~/.config/opencode/opencode.json` | OpenCode |
| `pi-models.json` | `~/.pi/agent/models.json` | Pi Coding Agent |
| `openclaw-macstudio-provider.json` | Merge into `~/.openclaw/openclaw.json` | OpenClaw |
