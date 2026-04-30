# vmlx Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Starting the server](#starting-the-server)
- [Tool use and reasoning](#tool-use-and-reasoning)
- [Verifying the fast path](#verifying-the-fast-path)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [See also](#see-also)

---

## Overview

`vmlx` is the **JANGTQ-only** server in this repo. It exists because TurboQuant-weight (JANGTQ) models need `jang_tools.load_jangtq` + the `turboquant/*kernel*` Metal kernels at load time — and **none of that ships via the public pypi `jang` or `vmlx` wheels** ([`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5)). The loader + kernels are bundled only inside the MLX Studio Electron DMG's relocatable Python (`panel/scripts/bundle-python.sh` per the vmlx 1.3.62 CHANGELOG). `vmlx` runs headlessly out of that bundled Python — no GUI session is needed despite the Electron packaging.

Speaks **OpenAI + Anthropic + Ollama** APIs on port 8000. Served model on this Mac Studio: `dealignai/MiniMax-M2.7-JANGTQ-CRACK` (230B / ~10B active MoE, JANGTQ 2-bit codebook + 8-bit attn/embed, CRACK-abliterated, ~57 GB on disk).

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌────────────────────────────────────────┐
│ Claude Code    │            │ vmlx_engine (port 8000)                │
│ OpenCode       │─── LAN ───>│   dealignai/MiniMax-M2.7-JANGTQ-CRACK  │
│ OpenClaw       │            │   Native TQ fast path (Metal kernels)  │
│ Pi             │            │   OpenAI + Anthropic + Ollama APIs     │
└────────────────┘            └────────────────────────────────────────┘
```

The server process is `/Applications/vMLX.app/Contents/Resources/bundled-python/python/bin/python3 -m vmlx_engine.cli serve …`. Weights are resolved from `~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/<hash>/` (downloaded via `huggingface_hub`).

## Installation

**One-time:** install the MLX Studio DMG on Mac Studio.

```bash
# On Mac Studio (GUI session once, then never again)
curl -L -o /tmp/vmlx.dmg \
  https://github.com/jjang-ai/mlxstudio/releases/download/v1.3.65/vMLX-1.3.65-arm64.dmg
hdiutil attach /tmp/vmlx.dmg
cp -R "/Volumes/vMLX 1.3.65-arm64/vMLX.app" /Applications/
hdiutil detach "/Volumes/vMLX 1.3.65-arm64"
```

The app bundle is **self-contained** — no Homebrew coupling, no `brew services` entry. You don't need to launch the Electron UI; the bundled Python under `/Applications/vMLX.app/Contents/Resources/bundled-python/python/` is fully functional over SSH.

**Verify the bundled loader is there** (should list non-zero results):

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
ls $BP/lib/python3.12/site-packages/jang_tools/load_jangtq*.py
ls $BP/lib/python3.12/site-packages/jang_tools/turboquant/*.py
```

Expected: `load_jangtq.py`, `load_jangtq_vlm.py`, `turboquant/{tq_kernel,hadamard_kernel,gather_tq_kernel,fused_gate_up_kernel}.py`.

## Starting the server

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx.log 2>&1 &
```

> **Do not** use the shipped `$BP/bin/vmlx` script — its shebang hardcodes the maintainer's build path (`/Users/eric/mlx/vllm-mlx/panel/bundled-python/python/bin/python3`). The `vmlx_engine.cli` module route is the maintainer-documented workaround (CHANGELOG: "Bundled spawn uses `python3 -m vmlx_engine.cli serve` (avoids shebang issues)").

---

## Tool use and reasoning

OpenAI-style tool calling and Qwen3 thinking-token separation both work on vmlx but require **three runtime flags and a one-time source patch** applied to the bundled Python.

**Runtime flags** (already in the Start snippet above):

| Flag | Required for |
|------|-------------|
| `--enable-auto-tool-choice` | `tool_choice: auto` semantics + qwen3 tool-call parser wiring |
| `--tool-call-parser qwen3` | Extracts `<tool_call>…</tool_call>` into structured `tool_calls[]` |
| `--reasoning-parser qwen3` | Extracts `<think>…</think>` into `reasoning_content` (keeps `content` clean) |

Without `--reasoning-parser qwen3`, the model's entire thinking monologue appears in `content` and clients like OpenCode show it as the visible reply ("thinking nonsense").

**One-time source patch** — vmlx 1.0.3 has three MLLM-path defects the flags alone cannot fix (tools silently dropped before the chat template, template ignores them anyway, multi-turn tool replay crashes the Jinja template). Fix:

```bash
ssh macstudio "$BP/bin/python3 ~/setup-llm-macstu/scripts/patches/patch_vmlx_jangtq_mllm_tools.py"
```

Idempotent. **Re-apply after every DMG upgrade.** Full bug-by-bug breakdown: [`maintenance.md` § Tool use and reasoning](maintenance.md#tool-use-and-reasoning-mllm-models).

## Verifying the fast path

On startup, `tail /tmp/vmlx.log` should contain:

```
JANGTQ v2 loaded in ~10s: <model-name> (0.0-bit avg, native TQ, no dequant)
Replaced <N> modules with TurboQuantLinear / TurboQuantSwitchLinear
```

**Absence** of `JANGTQ fast path unavailable` is the real verification — that warning means the dequant-and-requant fallback path in `vmlx_engine/utils/jang_loader.py` triggered, which produces gibberish output on the MiniMax family ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)).

## Health check

No API key required.

```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool
curl -s http://<MAC_STUDIO_IP>:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"dealignai/MiniMax-M2.7-JANGTQ-CRACK","messages":[{"role":"user","content":"2+2?"}],"temperature":1.0,"max_tokens":100}' \
  | python3 -m json.tool
```

Response has a `reasoning_content` field (separate from `content`) — vmlx applies the MiniMax reasoning parser automatically.

## Performance (Mac Studio M3 Ultra, 96 GB)

| Prompt tokens | Completion tokens | Elapsed | tok/s (incl. prefill) |
|--------------:|------------------:|--------:|----------------------:|
| 52            | 523               | 12.0 s  | **43.72** |
| 510           | 534               | 13.6 s  | 39.42 |
| 2,138         | 308               | 17.2 s  | 17.91 |
| 8,407         | 311               | 50.2 s  | 6.20 |

At short context, meets the vmlx maintainer's 42 tok/s M3 Ultra baseline ([vmlx#72](https://github.com/jjang-ai/vmlx/issues/72)). The aggregate tok/s collapses at long context because the single-shot metric bundles prefill into elapsed time. Peak wired RAM during generation ≈ **66.6 GB / 96 GB**.

Full deploy + perf report: [`docs/models/uncen-model/minimax-m27-crack-benchmark.md`](../../models/uncen-model/minimax-m27-crack-benchmark.md) (in the private `uncen-model` submodule).

## Known limitations

- **MLLM tool-use bugs (patch required)**: vmlx 1.0.3 drops `tools[]` before the chat template, ignores it in `_apply_chat_template`, and crashes on multi-turn tool replay with "Can only get item pairs from a mapping". All three are fixed by `scripts/patches/patch_vmlx_jangtq_mllm_tools.py`. Must re-apply after every DMG upgrade. See [§ Tool use and reasoning](#tool-use-and-reasoning) and [`maintenance.md`](maintenance.md#tool-use-and-reasoning-mllm-models).
- **Incompatible flags**: `--smelt` and `--flash-moe` raise `ValueError` on `weight_format=mxtq` ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)). Do not pass either.
- **JANGTQ-weight models only**: non-JANGTQ models work too, but there is no reason to use vmlx for them — `vllm-mlx` / `mlx-openai-server` / `oMLX` have better operational stories and matching or faster perf.
- **Single-vendor dependency risk**: the loader + Metal kernels are not in any public package. A new DMG install is the only supported path after reinstall; there is no `pip install` fallback today. Upstream tracking issue: [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5).
- **No Homebrew service entry**: vmlx is launched via `nohup … &` and killed via `pkill -f vmlx_engine`. See [`maintenance.md`](maintenance.md) for the lifecycle script.
- **Refusal-rate benchmarking is a separate step**: the CRACK prompt suite ([`uncen-model-prompts.md`](../../models/uncen-model/uncen-model-prompts.md)) produces content that requires explicit per-session authorization to generate/log. The deploy doc leaves the 2026-04-20 refusal-rate row unchecked for that reason.

## See also

- [`maintenance.md`](maintenance.md) — lifecycle + upgrade recipe
- [`maintenance.md` § Tool use and reasoning](maintenance.md#tool-use-and-reasoning-mllm-models) — three MLLM-path bugs, patch script, troubleshooting table
- [`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`](../../../scripts/patches/patch_vmlx_jangtq_mllm_tools.py) — idempotent source patch for all three bugs
- [`docs/models/model-summary.md` § unblocking path](../../models/model-summary.md#unblocking-path--corrected--deployed-2026-04-20) — why pypi `vmlx` alone doesn't work
- [`docs/models/uncen-model/minimax-m27-crack-benchmark.md`](../../models/uncen-model/minimax-m27-crack-benchmark.md) — per-context perf + RAM detail
