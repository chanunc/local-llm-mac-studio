# Tuning client configs (`contextWindow`, `maxTokens`)

How to size the two per-model knobs that show up in every client config in `configs/clients/<server>/` (and on the live OpenClaw / OpenCode / Pi / qwen-code installs that derive from them).

## What each knob controls

| Knob | What it does | Where it ends up on the wire |
|:--|:--|:--|
| `contextWindow` (OpenClaw) / `limit.context` (OpenCode) | **Total input + output budget** the model can "see". The runtime pre-checks `prompt_tokens` against this; long sessions trip `context-overflow-precheck` / `assistantError` here. | Drives prompt-trimming and overflow checks **client-side**. The server enforces its own ceiling via the load-time flag (`lms load --context-length …`, `vllm-mlx --max-model-len …`, etc.) — the client value must not exceed the server-loaded value or the API rejects with a 400. |
| `maxTokens` (OpenClaw) / `limit.output` (OpenCode) | **Per-response output cap** — the maximum tokens the model is allowed to generate on a single turn. | Sent upstream as `max_tokens` (OpenAI-compat) or `max_output_tokens` (Anthropic-compat). The runtime also reserves this much when computing whether the next turn fits inside `contextWindow`, so raising it slightly *reduces* effective conversation history. |

These two are independent, but they live in the same conversation budget: at any turn, `prompt_tokens + maxTokens ≤ contextWindow` must hold, otherwise the server truncates or rejects.

`contextWindow` is the knob that fixes "long-running Telegram threads tripping `context-overflow-precheck`". `maxTokens` is the knob that fixes "the model's reply got cut off mid-sentence". Don't confuse them.

## Hard ceilings — Gemma 4 26B-A4B family

Both the **lmstudio-community Gemma 4 26B-A4B-it Q8_0** and the **TrevorJS uncensored EGA-abliterated** variant share the same base (`google/gemma-4-26B-A4B-it`), so all numbers below apply identically to both. Verified by reading the GGUF header on each file:

```
context_length = 0x40000 = 262144 tokens (256K)
```

- TrevorJS finetune is weight-edit only (EGA abliteration on attention/FFN); RoPE, position embeddings, and trained context length are unchanged from the base.
- LM Studio silently clamps `--context-length` to the GGUF-declared max — you cannot push past 262144.
- Pushing past would hit RoPE positions never seen during training; output collapses (looping, off-topic) even if forced.

There is **no separate architectural cap on output tokens** for either variant — the model just keeps decoding until EOS or `max_tokens`. Google's published Gemma family service limit is **8192** output tokens, which is the safe number to use as a per-turn cap.

## Memory ladder on the M3 Ultra (96 GB unified)

With Gemma 4 26B-A4B Q8_0 resident (≈ 27 GB wired), KV-cache cost dominates the remaining budget. Gemma 4 uses mostly sliding-window attention with sparse global-attention layers, so KV grows sub-linearly with context — the rough numbers:

| `--context-length` (server) ↔ `contextWindow` (client) | KV cache @ Q8 (rough) | Free RAM after | Status |
|---:|:--|:--|:--|
| 65 536 | ~4 GB | ~58 GB | original deploy |
| **131 072** | ~8 GB | ~54 GB | **current sweet spot** — doubles capacity, comfortable for long Telegram threads |
| 262 144 (max trained) | ~16 GB | ~46 GB | safe alone, but no other 25 GB+ model can coexist |
| > 262 144 | — | — | not loadable; would degrade quality if forced |

For `maxTokens`:

| `maxTokens` | % of 128K context per reply | Notes |
|---:|--:|:--|
| 4 096 | 3 % | original — fine for short chat replies, truncates long-form |
| **8 192** | 6 % | **recommended** — matches Google's documented family limit |
| 16 384 | 12 % | works locally; comfortable for long-form code / writeups |
| 32 768 | 25 % | each reply eats a quarter of the window — starves history |
| up to ~127 K | up to 100 % | mechanically allowed, never useful |

## Applied values (2026-05-07)

Both Gemma 4 26B-A4B variants now ship with `contextWindow = 131072`, `maxTokens = 8192` across every shipped lm-studio client template:

| File | Entry | Field path |
|:--|:--|:--|
| [`configs/clients/lm-studio/opencode.json`](../../configs/clients/lm-studio/opencode.json) | `gemma-4-26b-a4b-q8` | `provider.macstudio.models.<id>.limit.{context, output}` |
| [`configs/clients/lm-studio/opencode.json`](../../configs/clients/lm-studio/opencode.json) | `gemma4-26b-a4b-trevorjs-uncen-q8` | same |
| [`configs/clients/lm-studio/openclaw-provider.json`](../../configs/clients/lm-studio/openclaw-provider.json) | `gemma-4-26b-a4b-q8` | `macstudio.models[].{contextWindow, maxTokens}` |
| [`configs/clients/lm-studio/openclaw-provider.json`](../../configs/clients/lm-studio/openclaw-provider.json) | `gemma-4-26b-a4b-it-uncensored` | same |

Server-side, the [`README.md`](../../README.md) Quick Start launch shape carries the matching `--context-length 131072` for the lmstudio-community variant. A TrevorJS reload command was previously documented at 65 536 — it is a documented restart shape, not a live-state assertion, and should be raised to 131 072 whenever it is reloaded as a main.

The full lm-studio template set (`opencode.json`, `openclaw-provider.json`, `claude-code-settings.json`, `pi-models.json`, `qwen-code-settings.json`) ships under `configs/clients/lm-studio/`. The Claude Code, Pi, and qwen-code templates carry the same `contextWindow=131072` / `maxTokens=8192` numbers for both Gemma 4 26B-A4B variants (Pi config) and the matching defaults (Claude Code uses the OpenAI-compat path: `CLAUDE_CODE_USE_OPENAI=1` + `OPENAI_BASE_URL` + `CLAUDE_CODE_OPENAI_MODEL`, since LM Studio does not speak the Anthropic API).

## How to apply the change

Three places must all agree:

1. **Server-side** — load the model with the larger context. For LM Studio:
   ```bash
   ssh macstudio "~/.lmstudio/bin/lms unload <identifier> && \
     ~/.lmstudio/bin/lms load '<modelKey>' --gpu max \
       --context-length 131072 --identifier <identifier> -y"
   ssh macstudio "~/.lmstudio/bin/lms ps"   # verify CONTEXT actually applied
   ```
   LM Studio's first load **sometimes silently caps to a previous value** — always verify with `lms ps`.
2. **Client templates** — update the matching `contextWindow` / `maxTokens` (or `limit.context` / `limit.output`) in `configs/clients/<server>/*.json`.
3. **Live client configs** — the deployed copies on each client machine. For OpenClaw on `narutaki`, sync both `models.providers.<p>.models[]` **and** the `agents.defaults.models` alias map (the alias map is keyed by `<provider>/<id>` and resolves to the model entry — out of sync = client uses the old limits).

## When *not* to raise these

- **`contextWindow`** above the server-loaded `--context-length` → API 400.
- **`contextWindow`** above the GGUF / model-card trained max → quality collapse beyond the trained range, even if the runtime accepts it.
- **`maxTokens`** much larger than typical reply length → wastes prompt budget per turn (the runtime reserves this much before computing what fits).
- Any of these on a model in active long-context use without re-running the perf benchmark — KV cost is sub-linear for sliding-window models like Gemma 4 but still meaningful, and prefill speed at the new ceiling is not the same as at 32 K.

## See also

- [`tuning-by-knob.md`](tuning-by-knob.md) — server-side flags (`--prefill-step-size`, drafter, parser, etc.).
- [`tuning-by-workload.md`](tuning-by-workload.md) — which knobs dominate per workload regime.
- [`../../scripts/chk_llm_macstu.py`](../../scripts/chk_llm_macstu.py) — probe the Mac Studio for live server / model run-state.
- Memory: "Update narutaki openclaw.json in two places" — sync rule for live OpenClaw configs.
