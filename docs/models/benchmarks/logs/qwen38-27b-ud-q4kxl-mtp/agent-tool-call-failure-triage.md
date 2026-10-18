# Agent tool-call triage: Qwen3.8-27B UD-Q4_K_XL + MTP (llama-cpp-mtp)

One OpenCode `search` run out of three hit the 300 s wall clock. This note records the signature and what was and was not checked. No upstream issue was filed.

## Overview

- Failure signature
- Contrast with the passing layers
- Search results
- Suspected layer and next steps

## Failure signature

| Item | Value |
|:--|:--|
| Scenario | `search` ("Browse Hackernews, get the only one latest topic") |
| Failed run | measured run 1 of 3 — `response_time_s 300.02`, `exit_code -1`, `llm_time_s 0` |
| Tool calls | `bash, webfetch, bash, bash, bash, bash, bash` (8 turns, 7 tool uses) |
| OpenCode errors | none (`error_count 0`, `errors: []`) |
| Passing runs | run 2: 79.61 s, 3 turns, `webfetch ×2`; run 3: 41.18 s, 2 turns, `webfetch ×1`; warmup: 53.64 s |
| Browse scenario | 3/3 clean, 24.8–29.1 s, `webfetch` only |
| Server | `llama-server` build 334 (`ac4cdde`), `-c 131072 --spec-type draft-mtp --spec-draft-n-max 2 --jinja --reasoning on` |
| Model | `unsloth/Qwen3.8-27B-GGUF` `UD-Q4_K_XL` |

Raw data: [`agent-bench-llama-cpp-mtp.json`](agent-bench-llama-cpp-mtp.json).

## Contrast with the passing layers

- API-level smoke passed 5/5 ([`api-tool-test-llama-cpp-mtp.json`](api-tool-test-llama-cpp-mtp.json)), so the template and tool-call parsing work for single and multi-turn calls.
- The same model on lm-studio (MLX 4-bit) used only `webfetch` in all 6 measured agent runs, so the bash fallback is not a property of the weights alone.
- `llama-server` log shows cold prompt processing at about 260 tok/s and repeated `erased invalidated context checkpoint` lines when the prefix changes between turns, so each long agent turn pays near-full prefill.

## Search results

One web search found no report of this exact behaviour (Qwen3.8-27B choosing `bash` over `webfetch` under OpenCode on llama.cpp). Related reports are about context-compaction loops in another agent and about tool-call formatting on the earlier 3.6 model. Nothing here is verified for this setup.

## Suspected layer and next steps

- **Likely layer:** agent-loop behaviour (model choosing `bash` fetches after a first tool result), not server transport. This matches the earlier `bash`-fallback pattern recorded for another llama.cpp model in [`model-benchmark-tool-call.md`](../../model-benchmark-tool-call.md).
- **Not checked:** whether the bash calls themselves hung (the run records `llm_time_s 0`, so per-turn timing was lost when the wall clock killed it); whether sampling at the model-card thinking settings changes the rate; whether a patched chat template removes it.
- **Next step if this matters:** repeat the search scenario with `--runs 10` and count `bash` fallbacks, then try the card's thinking-mode sampling (`temperature 1.0, top_p 0.95, top_k 20`) set on the server.
