# LFM2 / LFM2.5 Family (LiquidAI `lfm2moe` hybrid MoE)

LiquidAI's on-device hybrid models. The lab variant is **LFM2.5-8B-A1B** — an 8.3 B-total / ~1.5 B-active sparse MoE (`lfm2moe`, 32 experts × 959 M) built for edge inference. Reasoning-only (always emits a `<think>` chain), text-only, proprietary `lfm1.0` license.

## Overview

This document covers:

- **Variant spec** — LFM2.5-8B-A1B Q8_0 specs and source
- **The tool-calling trap** — why it fails on LM Studio and how to make it work on llama.cpp (the headline gotcha)
- **Deployment recipe** — patch the GGUF chat template + serve via `llama-cpp-mainline --jinja`
- **Benchmarks** — smoke, throughput, OpenCode agent loop
- **Caveats** — reasoning-only, recurrent `invalid` tool calls in OpenCode, runtime support status

## Variant: LFM2.5-8B-A1B Q8_0

| Field | Value |
|:--|:--|
| HF repo | [`LiquidAI/LFM2.5-8B-A1B-GGUF`](https://huggingface.co/LiquidAI/LFM2.5-8B-A1B-GGUF) |
| Architecture | `lfm2moe` — hybrid MoE, 8.3 B total / ~1.5 B active (32 × 959 M experts) |
| Quant | Q8_0, 9.01 GB on disk (8.39 GiB resident) |
| Context | 65536 used here (8 B-class; card unspecified) |
| License | `lfm1.0` (LiquidAI proprietary) |
| Modality | Text-only (no `mmproj`) |
| Reasoning | **Always on** — reasoning-only model, no documented disable toggle |
| Tool format | **Pythonic** — `<|tool_call_start|>[func(arg="...")]<|tool_call_end|>` (Llama-3.2-style list) |
| Working server | `llama-cpp-mainline` `:8100` via plain `--jinja` (**not** lm-studio) |

## The tool-calling trap (headline gotcha)

LFM2.5's native tool-call format is a **Pythonic call list** between `<|tool_call_start|>` / `<|tool_call_end|>` special tokens. As of late May 2026 (the model is days old), runtime support is uneven:

### lm-studio (llmster `:1234`) — tool calls do NOT work

LM Studio does not detect `lfm2moe` as tool-capable ([lmstudio-js #458](https://github.com/lmstudio-ai/lmstudio-js/issues/458)), so it **ignores the model's native template** and injects its generic `[TOOL_REQUEST]` instruction format. Because the model is reasoning-only, it writes the injected block *inside* its `<think>` chain and stops without closing it, so LM Studio classifies the whole output — tool call included — as `reasoning_content`:

```
reasoning_content: "...[TOOL_REQUEST]\n{\"name\":\"read_file\",...}\n[END_TOOL_REQUEST]"
content: ""   tool_calls: []   finish_reason: "stop"
```

Result: **smoke 0/5**. Neither `chat_template_kwargs:{enable_thinking:false}` nor a `/no_think` prefix helps — the model has no reasoning-off switch. There is no known LM Studio workaround today.

### llama.cpp `--jinja` — works, *after a one-line template patch*

The `llama-cpp-mainline` binary uses the GGUF's embedded template and a PEG tool-call parser that knows `<|tool_call_start|>`. But with the **canonical-repo** GGUF it returns:

```
HTTP 500: Failed to parse input at pos N:
<|tool_call_start|>[read_file(path="/tmp/config.json")]<|tool_call_end|>
```

— the tokens are recognized but llama.cpp doesn't route to the LFM2 pythonic parser ([ggml-org/llama.cpp #20245](https://github.com/ggml-org/llama.cpp/issues/20245)).

**Root cause / fix:** llama.cpp's chat-format auto-detection keys off marker text in the template. The community fix [`nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2`](https://huggingface.co/nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2) differs from the canonical template by exactly **one leading Jinja comment** — `{# List of tools: [ #}` — which is the marker llama.cpp needs to select the LFM2 pythonic parser. With it: tool calls parse, `finish_reason: "tool_calls"`, *and* the `<think>` block separates into `reasoning_content` (load log shows `thinking = 1` vs `0`). The byte diff is trivial; the behavioral difference is total.

## Deployment recipe (Q8_0 + patched template on llama.cpp)

The fixed-v2 repo only ships Q4_K_M, so to keep 8-bit, transplant its template into the canonical Q8_0:

```bash
# 1. Download canonical Q8_0 + fixed-v2 Q4 (template source)
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download as d; \
  d(repo_id='LiquidAI/LFM2.5-8B-A1B-GGUF', filename='LFM2.5-8B-A1B-Q8_0.gguf', local_dir='/Users/chanunc/.cache/hauhau-gguf'); \
  d(repo_id='nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2', filename='LFM2.5-8B-A1B-Q4_K_M.gguf', local_dir='/Users/chanunc/.cache/hauhau-gguf')\""

# 2. Extract the fixed template, then re-embed into the Q8_0 (gguf-py needs numpy — use vllm-mlx-env)
ssh macstudio "cd ~/llama-cpp-mainline && ~/vllm-mlx-env/bin/python -c \"
import sys; sys.path.insert(0,'gguf-py'); from gguf import GGUFReader; import pathlib
t=GGUFReader('/Users/chanunc/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q4_K_M.gguf').get_field('tokenizer.chat_template').contents()
pathlib.Path('/tmp/FIXED.jinja').write_text(t)\""
ssh macstudio "cd ~/llama-cpp-mainline && PYTHONPATH=gguf-py ~/vllm-mlx-env/bin/python gguf-py/gguf/scripts/gguf_new_metadata.py \
  /Users/chanunc/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q8_0.gguf \
  /Users/chanunc/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q8_0-fixed.gguf \
  --chat-template-file /tmp/FIXED.jinja"

# 3. Serve via mainline llama.cpp (no MTP flags) — --jinja is mandatory for tool calls
ssh macstudio "GGUF=/Users/chanunc/.cache/hauhau-gguf/LFM2.5-8B-A1B-Q8_0-fixed.gguf; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 65536 \
    --host 0.0.0.0 --port 8100 --alias lfm2.5-8b-a1b-q8 --jinja --reasoning-format auto \
    > /tmp/lfm-q8fixed.log 2>&1 &"
ssh macstudio "pkill -f 'port 8100'"  # stop
```

(Shortcut: deploy `nathanrchn/LFM2.5-8B-A1B-GGUF-fixed-v2` directly if Q4_K_M is acceptable — same behavior, no patch step.)

## Benchmarks

All on the patched Q8_0 via `llama-cpp-mainline --jinja` `:8100`. Logs: [`benchmarks/lfm2.5-8b-a1b-q8/`](../benchmarks/lfm2.5-8b-a1b-q8/).

**Smoke (API tool-call):** ✅ **5/5** single-call (0.51–0.90 s) · multi-turn 3-turn loop 2.64 s. (Same harness on lm-studio: **0/5** — see trap above.)

**Throughput (decode tok/s @ input tokens):**

| Context | 512 | 4 096 | 8 192 | 32 768 |
|:--|:--|:--|:--|:--|
| gen tok/s | 190.6 | 188.5 | 185.2 | 169.9 |
| TTFT | 0.03 s | 0.03 s | 0.03 s | 0.04 s |
| prefill tok/s | 20 K | 148 K | 277 K | 827 K |

Very fast for an 8 B-footprint model — the ~1.5 B active path keeps decode near 170–190 tok/s across context. (lm-studio runtime is comparable: 197–209 tok/s ≤4 K, 166–188 @ 8–32 K — generation works there; only tool-calling is broken.)

**Agent loop (OpenCode end-to-end, 3 runs):**

| Scenario | Wall (median) | LLM | Turns | Tools |
|:--|:--|:--|:--|:--|
| Browse www.example.com | **11.1 s** [6.93–13.81] | 7.12 s | 3 | invalid → webfetch |
| Browse Hackernews latest | **19.72 s** [15.92–35.5] | 15.71 s | 3 | invalid → webfetch |

Mid-pack — comparable to dense 27 B GGUF agents.

## Caveats

- **lm-studio is a dead end for agents** — generation works, tool calls do not. Use `llama-cpp-mainline --jinja` only.
- **Canonical GGUF needs the template patch** — without the `{# List of tools: [ #}` marker, llama.cpp returns HTTP 500 on every tool call ([#20245](https://github.com/ggml-org/llama.cpp/issues/20245)).
- **Recurrent `invalid` tool call in OpenCode** — the model almost always emits one `invalid` tool call (name/arg shape OpenCode's adapter rejects) before recovering with `webfetch`. One search run looped to 9 turns with 6 consecutive invalids before recovering. Tasks still complete, but turn counts and latency are noisier than mature Qwen3.6 GGUFs.
- **Occasionally skips the tool** — one browse run answered in a single turn without calling `webfetch` (model decided it "knew" the answer).
- **Reasoning-only** — every turn includes a `<think>` chain; no off switch. Use `--reasoning-format auto` so it lands in `reasoning_content`.
- Full failure-investigation log: [`benchmarks/lfm2.5-8b-a1b-q8/agent-tool-call-failure-triage.md`](../benchmarks/lfm2.5-8b-a1b-q8/agent-tool-call-failure-triage.md).
