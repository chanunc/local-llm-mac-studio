# Benchmark: Tool-Call Latency

Tested on **Mac Studio M3 Ultra (96 GB)**.

## 🧪 Method

Two complementary harnesses, both reported per model:

1. **API-level tool-call harness** — direct `/v1/chat/completions` with a 5-tool fixture (`read_file`, `write_file`, `run_command`, `search_web`, `list_directory`). Five single-call scenarios + a 3-turn agentic loop (`read_file → write_file → final answer`, with simulated tool results between turns). Non-streaming, `temperature=0.0`, `max_tokens=1024`. Pass criterion per scenario: `finish_reason: "tool_calls"` with at least one well-formed entry in `message.tool_calls[]`.
   - Script: [`scripts/bench/bench_api_tool_call.py`](../../../scripts/bench/bench_api_tool_call.py)
2. **OpenCode end-to-end harness** — real agent CLI invocation via `opencode run --format json`, measuring wall time (subprocess elapsed) and LLM time (sum of per-turn assistant durations from the session export). Captures agent system prompts, tool definitions, multi-turn loop, and reasoning overhead — the actual latency a user experiences, not raw inference tok/s.
   - Script: [`scripts/bench/bench_agent_tool_call.py`](../../../scripts/bench/bench_agent_tool_call.py)
   - Config switcher: [`scripts/switch_opencode_config.py`](../../../scripts/switch_opencode_config.py)

**Why this matters:** Raw benchmarks show 45-85 tok/s for these models. But agent workloads include 2,000-4,000 token system prompts, multiple API round-trips, and reasoning amplification. Measured end-to-end, `opencode run "Hi"` takes 80s vs 2.7s raw curl for the same model — a 30x gap ([analysis](../../../docs/clients/opencode-analysis.md)).

---

## Index

**Cross-model tables** (medians, all models side-by-side):
- [API-level tool calling](#api-level-tool-calling-direct-v1chatcompletions-5-tool-harness) — direct `/v1/chat/completions` 5-tool harness
- [OpenCode end-to-end](#opencode-end-to-end-opencode-run---format-json-real-agent-loop) — `opencode run` real agent loop (wall + LLM time)
- [Server / parser flag matrix](#server--parser-flag-matrix) — required server CLI flags + patches per model
- [Scenario 1: Browse www.example.com](#scenario-1-browse-wwwexamplecom-single-tool-call) — single-tool ranking
- [Scenario 2: Browse Hackernews latest topic](#scenario-2-browse-hackernews-latest-topic-multi-step) — multi-step ranking

**Per-model results** (typical inference + agent bench + key findings):
- [JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K](#results-jangq-aiqwen35-35b-a3b-jang_4k) — 35 B sparse MoE, 3 B active, JANG 4-bit mixed (vllm-mlx + patch) — *2026-04-21, re-bench 2026-04-27*
- [dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK](#results-dealignaiqwen36-35b-a3b-jangtq4-crack) — 35 B sparse MoE, TurboQuant 4-bit, abliterated (vmlx + MLLM patch) — *2026-04-21, re-bench 2026-04-27 (search hang fixed)*
- [OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4](#results-osaurusaiqwen36-35b-a3b-jangtq4) — 35 B sparse MoE + VL, TurboQuant 4-bit (vmlx + MLLM patch) — *2026-05-01*
- [JANGQ-AI/Qwen3.6-27B-JANG_4M](#results-jangq-aiqwen36-27b-jang_4m) — 27 B dense + ViT, hybrid attn, JANG 4.45-bit mixed (vllm-mlx + JANG wrapper + patch) — *2026-04-23, re-bench 2026-04-27*
- [mlx-community/Qwen3.6-27B-6bit](#results-mlx-communityqwen36-27b-6bit) — 27 B dense + ViT, uniform 6-bit MLX (vllm-mlx, no patches) — *2026-04-24, re-bench 2026-04-27*
- [jedisct1/Qwen3.6-35B-rust.mlx](#results-jedisct1qwen36-35b-rustmlx) — 35 B sparse MoE, 3 B active, uniform 8-bit MLX, Rust LoRA merged (vllm-mlx, no patches) — *2026-04-24, re-bench 2026-04-27*
- [mlx-community/Ling-2.6-flash-mlx-6bit](#results-mlx-communityling-26-flash-mlx-6bit) — 104 B sparse MoE, 7.4 B active, hybrid MLA + linear-attention SSM, uniform 6-bit MLX (vllm-mlx, requires PR-1227 vendor + 2 thread-local patches) — *2026-04-29*
- [lmstudio-community/gemma-4-31B-it-MLX-6bit](#results-lmstudio-communitygemma-4-31b-it-mlx-6bit) — 31 B dense, text-only, uniform 6-bit MLX (lm-studio, no patches; LM Studio runtime auto-detects Gemma 4 tool-call + reasoning) — **fastest search in doc** (6.37 s wall 🏆); 🥉 browse (5.11 s wall) — *2026-05-01*
- [HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive](#results-hauhaucsqwen35-35b-a3b-uncensored-hauhaucs-aggressive) — 35 B sparse MoE, 3 B active, Q6_K GGUF, abliterated (lm-studio, no patches) — **5/5 API pass, browse 5.21 s** — *2026-05-05*
- [AITRADER/Huihui-Qwen3.5-35B-A3B-abliterated-4bit-MLX](#results-aitraderhuihui-qwen35-35b-a3b-abliterated-4bit-mlx) — 35 B sparse MoE, 3 B active, 4-bit MLX safetensors, abliterated (lm-studio, no patches) — **5/5 API pass, browse 15.72 s** — *2026-05-05*
- [mlx-community/Dolphin-Mistral-24B-Venice-Edition-mlx-8Bit](#results-mlx-communitydolphin-mistral-24b-venice-edition-mlx-8bit) — 24 B dense Mistral, 8-bit MLX, uncensored (lm-studio, no patches) — **5/5 API pass, browse 6.62 s** — *2026-05-05*
- [moot20/Dolphin3.0-R1-Mistral-24B-MLX-8bits](#results-moot20dolphin30-r1-mistral-24b-mlx-8bits) — 24 B dense Mistral R1, 8-bit MLX, uncensored (lm-studio, no patches) — **5/5 API pass, browse 7.5 s, search 34.52 s (high variance)** — *2026-05-05*
- [HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced](#results-hauhaucsqwen36-27b-uncensored-hauhaucs-balanced) — 27 B dense Qwen3.6, Q8_K_P GGUF, balanced uncensored (lm-studio, no patches) — **5/5 API pass, browse 11.16 s** — *2026-05-05*
- [lmstudio-community/Hermes-4-70B-MLX-6bit](#results-lmstudio-communityhermes-4-70b-mlx-6bit) — 70 B dense Llama, 6-bit MLX, NousResearch Hermes 4 (lm-studio, no patches) — **5/5 API pass, browse 15.63 s, search 79.98 s (bash-loop)** — *2026-05-05*
- [heni86/magnum-v4-72b_mlx-4bit](#results-heni86magnum-v4-72b_mlx-4bit) — 72 B dense Qwen2, 4-bit MLX, magnum roleplay fine-tune (lm-studio, no patches) — **⛔ 0/5 API pass — does not call tools** — *2026-05-05*
- [mradermacher/Midnight-Miqu-70B-v1.5-GGUF](#results-mradermachermidnight-miqu-70b-v15-gguf) — 70 B Mixtral-derived, Q4_K_M GGUF (lm-studio) — **⛔ SKIP — HTTP 400, no system role support** — *2026-05-05*

**Topic index** (jump to specific concerns):
- *Wall vs LLM time methodology* — see [OpenCode end-to-end](#opencode-end-to-end-opencode-run---format-json-real-agent-loop) intro
- *API-level harness script* — `scripts/bench/bench_api_tool_call.py` (5 single-call scenarios + 3-turn agentic loop, non-streaming, temperature 0)
- *vllm-mlx streaming + tool-call bug + patch* — see Qwen3.5-35B-A3B JANG 4K § Key Findings #3
- *vmlx MLLM tools-dropped bug + patch* — see JANGTQ4-CRACK § Key Findings #1 and `CLAUDE.md` Known Issues
- *300 s OpenCode client timeout (search hits)* — see Qwen3.6-27B-JANG_4M / Qwen3.6-27B-6bit § Key Findings
- *A3B sparsity (3 B active out of 35 B) speed advantage* — see Qwen3.6-35B-rust.mlx and Qwen3.5-35B-A3B § Key Findings
- *Quality vs latency trade-offs by quantization* — see Qwen3.6-27B-6bit § Key Findings #4

---

## Cross-Model Summary

All numbers below are medians; per-model detail sections follow further down.

### API-level tool calling (direct `/v1/chat/completions`, 5-tool harness)

Rows ordered by agentic loop time (ascending); 5/5 pass rate before 4/5.

| Model | Server | Pass rate | Single-tool latency | Multi-tool latency | Agentic loop (3-turn `read→write→summary`) |
|:------|:-------|:---------:|:-------------------:|:------------------:|:------------------------------------------:|
| TrevorJS Gemma 4 26B A4B Uncensored Q8_0 | **lm-studio** | ✅ **5/5** | **0.29 - 0.83 s** 🏆 | **0.34 - 0.35 s** 🏆 | **2.14 s** 🏆 |
| Ling-2.6-flash mlx-6bit (104B/7.4B-active, bailing_hybrid) | vllm-mlx (patched) | ✅ **5/5** | 1.21 - 2.13 s | 1.61 - 1.81 s | **4.74 s** 🥈 |
| Huihui Qwen3.5-35B-A3B abliterated 4bit MLX | **lm-studio** | ✅ **5/5** | 1.11 - 1.61 s | 1.29 - 1.72 s | **4.94 s** |
| Dolphin 3.0 R1 Mistral 24B MLX-8bit | **lm-studio** | ✅ **5/5** | 1.27 - 3.37 s | 1.29 - 1.39 s | 5.12 s |
| HauhauCS Qwen3.5-35B-A3B Aggressive Q6_K GGUF | **lm-studio** | ✅ **5/5** | 1.43 - 1.60 s | 1.59 - 1.90 s | 5.37 s |
| HauhauCS Qwen3.6-35B-A3B Aggressive Q6_K_P GGUF | **lm-studio** | ✅ **5/5** | 1.54 - 2.53 s | 1.54 - 2.51 s | 5.48 s |
| majentik Qwen3.6-35B-A3B-RotorQuant-MLX-6bit | mlx-openai-server | ⚠ 4/5 | 1.16 - 12.27 s | 1.37 - 4.28 s | **5.13 s** (text-only despite VL tag; no RotorQuant runtime; OpenCode browse 101.45 s 🐢) |
| Qwen3.6-35B-A3B Q6_K + TurboQuant `turbo3` V | `llama-cpp-turboquant` :8099 (TheTom) | ⚠ 4/5 | 1.35 - 15.73 s | 1.62 - 4.67 s | **5.57 s** (auto-asymm K=q8_0; agent-loop speed leader 6.47s/15.64s) |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | ✅ **5/5** | **1.18 - 1.21 s** 🥉 | **1.51 - 1.53 s** 🥉 | 5.64 s |
| prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K GGUF | **lm-studio** | ✅ **5/5** | 1.60 - 1.98 s | 1.60 - 4.27 s | 5.87 s |
| Qwen3.6-35B-A3B 4-bit + DFlash drafter | **dflash-mlx** | ✅ **5/5** | 1.84 - 1.88 s | 1.68 - 2.23 s | 5.9 s |
| Dolphin Venice 24B MLX-8bit | **lm-studio** | ✅ **5/5** | 1.35 - 4.51 s | 3.66 - 5.20 s | 6.55 s |
| Qwen3.6-35B-A3B Q6_K + RotorQuant `iso3` KV | `llama-cpp-turboquant` :8099 (johndpope) | ✅ **5/5** | 2.00 - 16.91 s | 2.48 - 4.93 s | 8.48 s (decode strong but cold prefill timeout @ 32K) |
| Gemma 4 31B-it (dense, lmstudio-community 6-bit) | **lm-studio** | ✅ **5/5** | 1.28 - 3.77 s | 1.41 - 2.41 s | 9.8 s |
| IBM Granite 4.1 30B Q8_0 | **lm-studio** | ✅ **5/5** | 1.13 - 2.99 s | 1.13 - 1.29 s | 10.37 s |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | ✅ **5/5** | 2.47 - 5.37 s | 2.77 - 3.71 s | 11.54 s |
| Hermes 4 70B MLX-6bit | **lm-studio** | ✅ **5/5** | 2.26 - 7.86 s | 2.26 - 4.54 s | 13.34 s |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | ✅ **5/5** | 3.44 - 3.76 s | 4.23 - 8.13 s | 14.84 s |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx 1.5.20 | ✅ **5/5** | 1.31 - 6.63 s | 2.50 - 9.80 s | 15.48 s |
| Qwen3.6-27B 6bit (dense, mlx-community) | vllm-mlx | ✅ **5/5** | 4.73 - 5.75 s | 7.52 - 8.83 s | 19.31 s |
| Qwen3.6-27B 6bit (dense, mlx-community) | **lm-studio** | ✅ **5/5** | 4.22 - 6.58 s | 5.28 - 8.86 s | 20.28 s |
| DavidAU Gemma 4 31B Heretic Q6_k GGUF (Thinking) | **lm-studio** | ✅ **5/5** | 2.75 - 8.48 s | 4.89 - 5.68 s | 23.68 s |
| HauhauCS Qwen3.6-27B Balanced Q8_K_P GGUF | **lm-studio** | ✅ **5/5** | 5.86 - 24.52 s | 6.31 - 11.50 s | 25.70 s |
| DavidAU Qwen3.6-40B Heretic Q6_K IMatrix GGUF | **lm-studio** | ✅ **5/5** | 6.39 - 15.90 s | 7.47 - 17.63 s | 30.31 s |
| Qwen3.6-35B-A3B Rust LoRA (jedisct1, 8-bit) | vllm-mlx | ⚠ 4/5 | 1.42 - 1.80 s | 1.42 - 2.70 s | 6.99 s ⚠ |
| magnum-v4-72b MLX-4bit | **lm-studio** | ⛔ **0/5** | N/A (no tool calls emitted) | N/A | N/A (multi-turn loop only passed) |
| Midnight-Miqu-70B-v1.5 Q4_K_M GGUF | **lm-studio** | ⛔ **SKIP** | N/A — HTTP 400 (no system role support) | N/A | N/A |

⚠ Rust LoRA Agentic-reasoning prompt (`Find the largest file in /tmp`) hits the 1024-token cap because the model emits long Gemini-style chain-of-thought as `content` (no `<think>` wrapper, so the `qwen3` reasoning parser doesn't strip it). All other scenarios pass cleanly. JANGTQ4-CRACK passes 5/5 at API level — its Search-scenario hang was specific to the OpenCode end-to-end harness, not a model-level tool-call failure.

⛔ magnum-v4-72b: The Qwen2-72B base model was fine-tuned for creative/roleplay (Magnum project) and does not call tools despite receiving tool definitions — all scenarios return `finish_reason: stop` with prose answers, not `tool_calls`. The multi-turn loop works because it uses explicit `<tool_call>` format in the conversation history from the harness.

⛔ Midnight-Miqu-70B-v1.5: The Mixtral-derived model's jinja chat template only supports `user` and `assistant` roles — LM Studio returns HTTP 400 when the tool-definition `system` message is sent. Tool calling is architecturally unsupported on this model.

### OpenCode end-to-end (`opencode run --format json`, real agent loop)

Two medians reported per scenario:

- **Wall time** — full `opencode run` subprocess elapsed (bootstrap + LLM turns + tool execution + teardown). What a user waits for.
- **LLM time** — sum of per-turn assistant `time.completed - time.created` from the session export. Matches the duration that opencode's TUI status bar displays (e.g. `▣ Build · ... · 50.8s`). Isolates model-side latency from client-side overhead.

Rows ordered by browse wall time (ascending).

| Model | Server | Browse (wall / llm) | Search (wall / llm) | Notes |
|:------|:-------|:-------------------:|:-------------------:|:------|
| **TrevorJS Gemma 4 26B A4B Uncensored Q8_0** | **lm-studio** | **2.93 s 🥇** / 1.74 s | **7.35 s 🏆** / 6.15 s | 2 / 2 turns; `webfetch`. Sparse MoE 4B active, non-thinking, 87.6 tok/s gen.<br>**All-time browse leader. Current search leader** (prior 🏆 was Gemma 4 31B-it 6.37s on lm-studio, thinking OFF — now historical). 8/10 mlabonne refusal. See [bench writeup](../uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md). |
| **prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K GGUF** | **lm-studio** | **5.05 s 🥈** / 3.82 s | 13.56 s / 12.35 s | 2 / 3 turns; `webfetch`. MoE 35B/3B active + VL, thinking-on.<br>See [bench writeup](../uncen-model/qwen36-35b-a3b-prithiv-aggressive-benchmark.md). |
| HauhauCS Qwen3.6-35B-A3B Aggressive Q6_K_P GGUF | **lm-studio** | 5.14 s 🥉 / 3.94 s | 12.01 s / 10.81 s | 2 / 3 turns; `webfetch`. MoE 35B/3B active + VL, thinking-on.<br>See [bench writeup](../uncen-model/qwen36-35b-a3b-hauhaucs-aggressive-benchmark.md). |
| **HauhauCS Qwen3.5-35B-A3B Aggressive Q6_K GGUF** | **lm-studio** | **5.21 s** / 4.0 s | 10.54 s / 9.34 s | 2 / 2 turns; `webfetch`. MoE 35B/3B active, thinking-off in practice.<br>See [results section](#results-hauhaucsqwen35-35b-a3b-uncensored-hauhaucs-aggressive). |
| IBM Granite 4.1 30B Q8_0 | **lm-studio** | 6.24 s / 5.02 s | 10.51 s / 9.31 s | 2 / 2 turns; `webfetch`. Dense 30B, non-thinking, 24.8 tok/s gen.<br>Apache 2.0. See [per-model](../per-model/model-summary-granite-4.1.md). |
| **Qwen3.6-35B-A3B Q6_K + TurboQuant `turbo3` V** | `llama-cpp-turboquant` :8099 (TheTom fork) | **6.47 s** / 5.27 s | **15.64 s** / 14.38 s | 2 / 3 turns; `webfetch`. MoE 35B/3B, auto-asymm K=q8_0 + turbo3 V, sparse V dequant + 4-mag LUT.<br>**2.07× / 2.27× faster than Gemma 4 mlx-lm baseline (12.33 s / 35.55 s).** See [per-model](../per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-q6_k--turboquant-turbo3-v-on-thetoms-fork). |
| **Dolphin Venice 24B MLX-8bit** | **lm-studio** | **6.62 s** / 5.38 s | 21.04 s / 19.8 s | 2 / 2 turns; `webfetch`. Dense Mistral 24B, no thinking.<br>See [results section](#results-mlx-communitydolphin-mistral-24b-venice-edition-mlx-8bit). |
| **Dolphin 3.0 R1 Mistral 24B MLX-8bit** | **lm-studio** | **7.5 s** / 6.28 s | 34.52 s / 4.42 s | 2.5 / 7 turns; `webfetch`+`bash`. High search variance (10–59 s). Loops bash excessively on search.<br>See [results section](#results-moot20dolphin30-r1-mistral-24b-mlx-8bits). |
| HauhauCS Qwen3.6-27B Balanced Q8_K_P GGUF | **lm-studio** | 11.16 s / 9.94 s | 28.91 s / 27.68 s | 2 / 2.5 turns; `webfetch`. Dense Qwen3.6 27B, Q8_K_P, thinking-on.<br>See [results section](#results-hauhaucsqwen36-27b-uncensored-hauhaucs-balanced). |
| Gemma 4 31B-it (dense, lmstudio-community 6-bit) | **mlx-lm** | 12.33 s / 11.12 s | 35.55 s / 34.38 s | 2 / 2 turns; `webfetch`. **Thinking ON** (mlx-lm server, 121/124 output tokens). Prior lm-studio run (thinking OFF): *5.11 s browse / 6.37 s search*. See [results section](#results-lmstudio-communitygemma-4-31b-it-mlx-6bit). |
| Gemma 4 31B-it bf16 + MTP drafter | mlx-vlm 0.5.0 (incl. PRs #1112/#1115/#1117) | ⛔ **300 s timeout × 6** (2 passes) | ⛔ **300 s timeout × 6** (2 passes) | 0 / 0 turns; (none). MTP drafter matches upstream B=1 reference (3.07–4.29 acc/round, 12.3 tok/s @ 8K vs PR #1115's 11.7 tok/s). chat_template.jinja verified byte-identical to 6-bit's working template — issue [#941](https://github.com/Blaizzy/mlx-vlm/issues/941) ruled out. Two distinct blockers: (1) mlx-vlm streaming hangs on long-reasoning prompts (trivial prompts stream OK; "Browse www.example.com" hangs 360 s; reproducible) and (2) at 12.3 tok/s decode the 8192-token reasoning budget consumes ~666 s/turn — exceeds opencode's 300 s wall regardless. `MLX_VLM_SPEC_BATCH_WAIT_MS=10` did not help (PR #1117 env var only helps concurrent requests, not sequential agent loops). Non-streaming tool harness still passes 5/5. Full analysis: [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment). |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 12.86 s / 11.47 s | 16.28 s / 14.98 s | 2 / 2 turns; `webfetch`. Sparse 3B-active MoE. |
| Qwen3.6-35B-A3B Rust LoRA (jedisct1, 8-bit) | vllm-mlx | 13.94 s / 12.72 s | 26.31 s / 25.09 s | 2 / 3 turns; `webfetch`. A3B sparsity.<br>Search splits into top-stories + item fetches. |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx 1.5.20 | 14.11 s / 12.9 s | 252.67 s / 251.46 s | 2 / 2 turns; `webfetch`. JANGTQ4 / `mxtq` MoE 35B/3B + VL.<br>Search dominated by 8K-token turn-2 reply on long-context decode. |
| Hermes 4 70B MLX-6bit | **lm-studio** | 15.63 s / 14.39 s | 79.98 s / 78.74 s | 3 / 6 turns; `webfetch`+`bash`. Search dominated by bash-loop loops (8 bash calls on run 1). Dense 70B Llama.<br>See [results section](#results-lmstudio-communityhermes-4-70b-mlx-6bit). |
| Huihui Qwen3.5-35B-A3B abliterated 4bit MLX | **lm-studio** | 15.72 s / 14.49 s | 21.38 s / 20.16 s | 2 / 2 turns; `webfetch`. MoE 35B/3B active, no thinking prelude.<br>See [results section](#results-aitraderhuihui-qwen35-35b-a3b-abliterated-4bit-mlx). |
| DavidAU Qwen3.6-40B Heretic Q6_K IMatrix GGUF | **lm-studio** | 18.73 s / 17.47 s | 71.02 s / 69.86 s | 2 / 3 turns; `webfetch`. Dense 40B all-active, thinking-on (Deckard/PDK).<br>See [bench writeup](../uncen-model/qwen36-40b-davidau-heretic-benchmark.md). |
| Ling-2.6-flash mlx-6bit (sparse 104B/7.4B-active, hybrid MLA + linear-attn) | vllm-mlx (patched) | 25.75 s / 24.50 s | 29.64 s / 28.40 s | 2 / 2 turns; `webfetch` (one search took `skill`).<br>7.4B active dominated by MLA cost. |
| Qwen3.6-35B-A3B 4-bit + DFlash drafter | dflash-mlx | 27.59 s / 26.38 s | 54.78 s / 53.58 s | 2 / 3 turns; `webfetch`. 87% draft accept.<br>**Search 2.1× slower than lm-studio** — growing context favors prefill. |
| Qwen3.6-27B 6bit (dense, mlx-community) | **lm-studio** | 31.96 s / 30.74 s | 25.71 s / 24.51 s | 2 / 2 turns; `webfetch`. Prefill 47K tok/s @ 32K.<br>See [api-server bench](model-benchmark-api-server.md#qwen36-27b-6-bit-standard-mlx-on-lm-studio-vs-vllm-mlx). |
| DavidAU Gemma 4 31B Heretic Q6_k GGUF (Thinking) | **lm-studio** | 33.55 s / 32.21 s | 102.65 s / 101.44 s | 2–3 turns; `webfetch`. Dense 31B, **Thinking model** — `<\|channel>thought` budget consumes most of 21 tok/s decode per turn.<br>See [bench writeup](../uncen-model/gemma4-31b-davidau-heretic-benchmark.md). |
| magnum-v4-72b MLX-4bit | **lm-studio** | ⛔ N/A (no tools) | ⛔ N/A (no tools) | No tools called — model answers from training memory.<br>See [results section](#results-heni86magnum-v4-72b_mlx-4bit). |
| MiMo V2.5 4-bit, 130-expert pruned (jedisct1) | vllm-mlx (patched) | 55.51 s ⚠ / 54.29 s | ⛔ **fail** | Browse: 1/3 invalid tool call, 2/3 hit 8K cap. Search: 0/3 zero tool calls.<br>API-level w/ single tool *works* — issue is OpenCode's 10-tool catalog + thinking-on. |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 69.14 s / 67.93 s | 108.51 s / 107.29 s | 2 / 3 turns; `webfetch`.<br>Dense 27 B + thinking-on adds 30+ s/turn. |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 71.10 s / 69.88 s | 154.18 s / 152.94 s | 2 / 3 turns; `webfetch`, `bash`.<br>A3B but TurboQuant kernels stay slow under deep thinking. |
| Qwen3.6-27B 6bit (dense, mlx-community) | vllm-mlx | 97.93 s / 96.75 s | 127.28 s / 126.05 s | 2 / 2 turns; `webfetch`. Standard 6-bit MLX, no JANG speedup.<br>Thinking-on dense path is the slowest browse. |
| majentik Qwen3.6-35B-A3B-RotorQuant-MLX-6bit | **mlx-openai-server** | **101.45 s 🐢** / 100.26 s | 21.25 s / 20.05 s | 2 / 3 turns; `webfetch`. **Text-only despite VL HF tag** (vision_tower weights absent). Turn 1 spends 98.87 s emitting only 68 tokens — likely qwen3 reasoning parser not stripping `<think>` blocks.<br>See [per-model](../per-model/model-summary-qwen-3-6.md#majentik-qwen36-35b-a3b-rotorquant-mlx-6bit). |

**2026-04-30 re-run note:** all six models re-benchmarked under a new prompt set (`Browse www.example.com` for browse, `Browse Hackernews, get the only one latest topic` for search). The old prompts (`Browse github.com` and `Search 3 latest ai agentic tools on github.com`) often elicited a clarification round instead of an immediate webfetch — adding model-side variance unrelated to inference latency. New prompts are concrete URLs / a deterministic public API, so every model fires webfetch on turn 1. **Numbers in this table are not directly comparable to the 2026-04-27 entries in `agent-bench.prev.json`** — work-per-scenario differs. JANG_4K leapfrogs Rust LoRA on search now that both run the same 2-turn webfetch path with no `task` / `bash` outliers. Per-model deep-dive sections below retain the 2026-04-27 prompt-set analysis; the new raw runs are in each model's `agent-bench.json`.

### Server / parser flag matrix

Rows ordered alphabetically by model name.

| Model | Server | `--tool-call-parser` | `--reasoning-parser` | Required patch |
|:------|:-------|:---------------------|:---------------------|:--------------|
| DavidAU Gemma 4 31B Heretic Q6_k GGUF (Thinking) | lm-studio | (built-in) | (built-in — `<\|channel>thought` → `reasoning_content`) | none — LM Studio Gemma 4 runtime. Guardrail override **required** before initial load (see [bench writeup](../uncen-model/gemma4-31b-davidau-heretic-benchmark.md)) |
| IBM Granite 4.1 30B Q8_0 | lm-studio | (built-in) | N/A (non-thinking model) | none — LM Studio Granite runtime handles tool-call format natively. Guardrail override **required** before initial load (65K context). |
| DavidAU Qwen3.6-40B Heretic Q6_K IMatrix | lm-studio | (built-in) | (built-in) | none — LM Studio Qwen3 chat template + `<think>` handled natively. Guardrail override **required** before initial load (dense 40B + 131K; see [bench writeup](../uncen-model/qwen36-40b-davidau-heretic-benchmark.md)) |
| Qwen3.6-35B-A3B 4-bit + DFlash | dflash-mlx | (built-in via `mlx_lm.server`) | (built-in — `delta.reasoning`) | `scripts/patches/patch_dflash_mlx_serve.py` + `scripts/patches/patch_mlx_lm_match.py` |
| Gemma 4 31B-it (lmstudio-community 6-bit) | lm-studio | (built-in) | (built-in) | none — `lms server start --bind 0.0.0.0 --cors`; LM Studio runtime auto-detects Gemma 4 tool-call format and routes `<think>` to `reasoning_content` |
| Gemma 4 31B-it (lmstudio-community 6-bit) | mlx-lm server (direct) | N/A (native Gemma 4 format) | N/A (thinking emitted as part of content in streaming) | none — launch via Cellar libexec binary (`/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server`); the `/opt/homebrew/bin/mlx_lm.server` symlink resolves to a python3.11 mlx_lm install that lacks Gemma 4 support. Thinking mode ON by default |
| Gemma 4 31B-it bf16 + MTP drafter (gemma4_assistant) | mlx-vlm 0.5.0 (from main; incl. PRs #1112/#1115/#1117) | N/A | N/A | install mlx-vlm from `git+https://github.com/Blaizzy/mlx-vlm.git@main` (PyPI 0.4.4 lacks `mlx_vlm.speculative`). Launch with `--draft-model mlx-community/gemma-4-31B-it-assistant-bf16 --draft-kind mtp --draft-block-size 6` and **set `MLX_VLM_SPEC_BATCH_WAIT_MS=10`** (PR #1117) for concurrent agent workloads. Streaming SSE silence on first attempt likely traces to missing `chat_template.jinja` per [#941](https://github.com/Blaizzy/mlx-vlm/issues/941). Re-test pending. Cap context ≤ 16 K (32 K+ Metal-OOMs at 118 GB vs 62 GB cap) |
| HauhauCS Qwen3.6-35B-A3B Aggressive Q6_K_P | lm-studio | (built-in) | (built-in) | none — LM Studio runtime. Custom `K_P` quant labels: use `hf_hub_download` + `lms import -L` |
| Ling-2.6-flash mlx-6bit | vllm-mlx | `hermes` | (none — model has no `<think>`) | vendored `mlx_lm/models/bailing_hybrid.py` from PR [#1227](https://github.com/ml-explore/mlx-lm/pull/1227) + `scripts/patches/patch_mlx_lm_threadlocal_stream.py` + `scripts/patches/patch_vllm_mlx_inline_gen.py` |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx | `qwen3` | `qwen3` | `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` |
| prithivMLmods Qwen3.6-35B-A3B Aggressive Q6_K | lm-studio | (built-in) | (built-in) | none — LM Studio auto-detects qwen35moe chat template. Guardrail workaround required if loading after other models (see [bench writeup](../uncen-model/qwen36-35b-a3b-prithiv-aggressive-benchmark.md)) |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx | `qwen3_coder` | `qwen3` | `scripts/patches/patch_vllm_mlx_streaming_tools.py` |
| Qwen3.6-27B JANG 4M | vllm-mlx | `qwen3_coder` | `qwen3` | same as JANG 4K |
| Qwen3.6-27B 6bit (mlx-community) | lm-studio | (built-in) | (built-in) | none — `lms server start --bind 0.0.0.0`; tool-call + reasoning parsing handled by LM Studio's MLX runtime out of the box |
| Qwen3.6-27B 6bit (mlx-community) | vllm-mlx | `qwen3_coder` | `qwen3` | none (standard MLX safetensors — no wrapper) |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | `qwen3` | `qwen3` | `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` |
| Qwen3.6-35B-A3B Rust LoRA (jedisct1) | vllm-mlx | `qwen3_coder` | `qwen3` | none (standard 8-bit MLX safetensors — `qwen3_5_moe` arch in mlx-lm 0.31.1) |
| TrevorJS Gemma 4 26B A4B Uncensored Q8_0 | lm-studio | (built-in) | N/A (non-thinking model) | none — `lms server start --bind 0.0.0.0 --cors`; LM Studio auto-detects Gemma 4 tool-call format. Guardrail override **required** before initial load (`lms guardrails set --guardrails-level off`; restore after load) |
| HauhauCS Qwen3.5-35B-A3B Aggressive Q6_K | lm-studio | (built-in) | (built-in) | none — LM Studio GGUF runtime. Load with `--context-length 32768`; default 4K too small for OpenCode system prompt. Download via `hf_hub_download` (Q6_K file) — `lms get` cannot resolve repo. |
| Huihui Qwen3.5-35B-A3B abliterated 4bit MLX | lm-studio | (built-in) | N/A (non-thinking model) | none — LM Studio MLX runtime. Load with `--context-length 32768`. Download via `snapshot_download` — `lms get` cannot resolve repo. |
| Dolphin Venice 24B MLX-8bit | lm-studio | (built-in) | N/A (non-thinking model) | none — LM Studio MLX runtime. Load with `--context-length 32768`. |
| Dolphin 3.0 R1 Mistral 24B MLX-8bits | lm-studio | (built-in) | N/A (non-thinking model) | none — LM Studio MLX runtime. Load with `--context-length 32768`. |
| HauhauCS Qwen3.6-27B Balanced Q8_K_P | lm-studio | (built-in) | (built-in) | none — LM Studio GGUF runtime. Load with `--context-length 32768`. Download via `hf_hub_download` (Q8_K_P file) — `lms get` cannot resolve custom quant label. |
| Hermes 4 70B MLX-6bit | lm-studio | (built-in) | N/A (non-thinking model) | none — LM Studio MLX runtime. Load with `--context-length 32768`. Large (53 GiB loaded) — may OOM alongside other models. |
| magnum-v4-72b MLX-4bit | lm-studio | N/A (does not call tools) | N/A | none — tool calling not functional regardless of flags. Do not use for agentic tasks. |
| Midnight-Miqu-70B-v1.5 Q4_K_M | lm-studio | N/A (HTTP 400 on tool requests) | N/A | none — chat-template only supports user/assistant roles; system-role tool definitions rejected. |

---

## 🤖 Results: JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K

**Date:** 2026-04-21
**Server:** vllm-mlx with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.5 MoE — 35B total, 3B active (256 experts, 8/tok), 262K context

### Typical Inference (3 runs each, median)

| Scenario | Time | Output Tokens | Speed |
|:---------|:-----|:-------------|:------|
| Short Q&A | 2.23s | 216 | 96.6 tok/s |
| Code generation | 4.43s | 442 | 99.5 tok/s |
| Reasoning | 9.53s | 968 | 101.5 tok/s |
| Long output (2K tok) | 20.12s | 2,048 | 101.8 tok/s |

Thinking tokens (`<think>` block) included in output count. Model always generates reasoning preamble.

### API-Level Tool Calling (non-streaming, 5 tools available)

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:------------|:-------|
| Single tool (file read) | 1.21s | 54 | 44.6 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 1.18s | 81 | 68.6 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 1.51s | 115 | 76.1 tok/s | `search_web`, `read_file` | ✅ PASS |
| Multi-tool (list + read + write) | 1.53s | 117 | 76.2 tok/s | `list_directory`, `read_file` | ✅ PASS |
| Agentic reasoning | 1.29s | 92 | 71.3 tok/s | `list_directory` | ✅ PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, proper `finish_reason: tool_calls`.
Parallel tool calling works (multi-tool scenarios call 2+ tools in single response).

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read config, fix port to 8080, write back"

| Turn | Action | Time |
|:-----|:-------|:-----|
| 1 | `read_file("/tmp/app/config.json")` | 1.34s |
| 2 | `write_file(…, {"host":"0.0.0.0","port":8080,"debug":true})` | 2.04s |
| 3 | Natural language summary (stop) | 2.26s |
| **Total** | **3 turns, complete task** | **5.64s** |

### OpenCode Agent Benchmark (streaming via `opencode run`)

**Before patch** (unpatched vllm-mlx):

| Scenario | Response Time (median) | Turns | Tools Called |
|:---------|:----------------------|:------|:------------|
| Browse github.com | 24.69s | 1 | (none) |
| Search 3 latest AI tools | 49.32s | 1 | (none) |

Unpatched result: BLOCKED — vllm-mlx streaming path with `--reasoning-parser` bypasses tool-call parsing entirely. The `<tool_call>` XML leaks into `content` as plain text.

**After patch** (`scripts/patches/patch_vllm_mlx_streaming_tools.py`):

| Scenario | Response Time (median) | Turns | Tools Called |
|:---------|:----------------------|:------|:------------|
| Browse github.com | 36.54s (2026-04-21) / 42.58s (2026-04-24) | 2 | `webfetch` |
| Search 3 latest AI tools | 59.50s (2026-04-21) / 70.61s (2026-04-24) | 2 | `bash`, `webfetch`, `task` |

Full agentic tool use works end-to-end through OpenCode. The 2026-04-24 re-run used `--print-logs --log-level=INFO` captured per-run to [`qwen35-35b-a3b-jang4k/agent-bench.logs/`](qwen35-35b-a3b-jang4k/agent-bench.logs/); raw JSON in [`qwen35-35b-a3b-jang4k/agent-bench.json`](qwen35-35b-a3b-jang4k/agent-bench.json). The ~15 % increase vs 2026-04-21 mostly reflects higher-token OpenCode system prompts in the newer 1.14.21 client (10.8k-token first-turn prefill vs ~9k earlier).

### Key Findings

1. **Raw inference: ~97-102 tok/s** — fast and consistent for a 3B-active MoE on M3 Ultra.

2. **Tool calling works at API level** — 5/5 pass rate with correct tool selection, valid JSON args, and parallel multi-tool calling. Multi-turn agentic loop completes a 3-step task in 5.6s.

3. **vllm-mlx streaming bug (fixed by patch)** — the streaming path has two mutually exclusive branches: the reasoning parser path (`--reasoning-parser`) and the standard path with tool parsing. When both flags are set, reasoning wins and tool calls are never parsed. The patch (`scripts/patches/patch_vllm_mlx_streaming_tools.py`) integrates tool-call detection into the reasoning path using the generic `parse_tool_calls()` function which handles the Nemotron/XML format (`<function=name><parameter=p>v</parameter>`) that Qwen3.5 MoE uses. Re-apply after `pip install -U vllm-mlx`.

4. **Agentic performance:** Browse task completes in ~37s (2 turns), search task in ~60s (2-4 turns). The model correctly selects appropriate tools and completes multi-step reasoning.

---

## Scenario 1: Browse www.example.com (Single Tool Call)

Prompt: `"Browse www.example.com"`

Rows ordered by response time (ascending). Date varies by model: 2026-04-30 for all except TrevorJS (2026-05-03).

| Model | Server | Response Time (median) | Turns | Tools | Tokens |
|:------|:-------|:---------------------------------:|:------|:------|:-------|
| TrevorJS Gemma 4 26B A4B Uncensored Q8_0 | lm-studio | **2.93 s 🏆** | 2 | `webfetch` | ~10.8K in / ~20–37 out |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 12.86 s 🥈 | 2 | `webfetch` | ~10.8K in / ~136 out |
| Qwen3.6-35B-A3B Rust LoRA (jedisct1, 8-bit) | vllm-mlx | 13.94 s 🥉 | 2 | `webfetch` | ~10.8K in / ~136 out |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx 1.5.20 / 1.3.65 | 14.11 s _(was 72.75 s on 1.3.65)_ | 2 | `webfetch` | 2 in / 106 out |
| Ling-2.6-flash mlx-6bit (sparse 104B/7.4B-active) | vllm-mlx (patched) | 25.75 s | 2 | `webfetch` | ~10.8K in / ~135 out |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 69.14 s | 2 | `webfetch` | ~10.7K in / ~150 out |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 71.10 s | 2 | `webfetch` | ~10.8K in / ~119 out |
| Qwen3.6-27B 6bit (dense, mlx-community) | vllm-mlx | 97.93 s | 2 | `webfetch` | ~10.7K in / ~137 out |

The new prompt removes the clarification round the old `Browse github.com` triggered on every model — every model now fires `webfetch https://www.example.com` on turn 1 and emits the page summary on turn 2. Wall-time spread reflects pure inference latency (sparsity + thinking-on density), not model decision-making.

---

## Scenario 2: Browse Hackernews Latest Topic (Multi-Step)

Prompt: `"Browse Hackernews, get the only one latest topic"`

Rows ordered by response time (ascending). Date varies by model: 2026-04-30 for all except TrevorJS (2026-05-03).

| Model | Server | Response Time (median) | Turns | Tools | Tokens | Context Growth |
|:------|:-------|:---------------------------------:|:------|:------|:-------|:---------------|
| TrevorJS Gemma 4 26B A4B Uncensored Q8_0 | lm-studio | **7.35 s 🏆** | 2 | `webfetch` | ~26K | ~13K/turn |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 16.28 s 🥈 | 2 | `webfetch` | ~26K | ~13K/turn |
| Qwen3.6-35B-A3B Rust LoRA (jedisct1, 8-bit) | vllm-mlx | 26.31 s 🥉 | 3 | `webfetch` | ~43K | ~13K/turn |
| Ling-2.6-flash mlx-6bit (sparse 104B/7.4B-active) | vllm-mlx (patched) | 29.64 s | 2 | `webfetch`, `skill` | ~23K | ~12K/turn |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx (patched) | 108.51 s | 3 | `webfetch` | ~34K | ~12K/turn |
| Qwen3.6-27B 6bit (dense, mlx-community) | vllm-mlx | 127.28 s | 2 | `webfetch` | ~23K | ~12K/turn |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | 154.18 s | 3 | `webfetch`, `bash` | ~43K | ~14K/turn |
| Osaurus Qwen3.6-35B-A3B JANGTQ4 | vmlx 1.5.20 / 1.3.65 | 252.67 s _(was 135.06 s on 1.3.65)_ | 2 | `webfetch` | ~13K | turn 2 = 8,192 out tokens at regressed long-context decode |

The Firebase top-stories API + per-item-metadata pattern resolves cleanly in 2-3 webfetch turns for every model — JANG_4K's 2-turn convergence (it inlines top-id-fetch + top-item-fetch into a single reasoned call) is what gives it the win over Rust LoRA's 3-turn approach. JANGTQ4-CRACK's outlier search wall (one run hit 297 s) is the abliterated TurboQuant kernels stalling under deep thinking, not a tool-loop problem.

---

## 🤖 Results: OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4

**Date:** original 2026-05-01 (vMLX 1.3.65); refreshed **2026-05-05** under vMLX 1.5.20 + `--continuous-batching`
**Server:** vmlx (MLX Studio bundled Python) on port 8000 with `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 --continuous-batching` (last flag mandatory on 1.5.20+ per [`docs/servers/vmlx/maintenance.md`](../../servers/vmlx/maintenance.md))
**Architecture:** Qwen3.6 MoE+VL — 35B total, ~3B active, JANGTQ4 / `mxtq`, 262K context
**Raw JSON:** [`qwen36-35b-a3b-jangtq4-osaurus/`](qwen36-35b-a3b-jangtq4-osaurus/) (current files reflect 2026-05-05 refresh; prior numbers preserved in git history)

### API-Level Tool Calling (2026-05-05 refresh)

| Scenario | Time | Tools Called | Result | vs. 2026-05-01 |
|:--|--:|:--|:--|:--|
| Single tool (file read) | 1.73 s | `read_file` | PASS | was 3.28 s |
| Single tool (command) | 1.31 s | `run_command` | PASS | was 13.14 s — large variance run-to-run |
| Multi-tool (search + read) | 1.84 s | `search_web`, `read_file` | PASS | was 3.84 s |
| Multi-tool (list + read + write) | 1.68 s | `list_directory` | PASS | was 2.87 s |
| Agentic reasoning | 6.63 s | `run_command` | PASS | was 12.08 s |

Pass rate: **5/5**. Multi-turn loop completed in **3 turns / 15.48 s** (was 11.65 s — within run-to-run variance, slightly slower because turn 3 generates more tokens).

### OpenCode Agent Benchmark (2026-05-05 refresh)

| Scenario | Wall median | LLM median | Turns | Tools | vs. 2026-05-01 |
|:--|--:|--:|--:|:--|:--|
| Browse www.example.com | **14.11 s** | 12.9 s | 2 | `webfetch` | **5.2× faster** (was 72.75 s — prefill speedup dominates) |
| Browse Hackernews latest topic | **252.67 s** | 251.46 s | 2 | `webfetch` | **1.9× slower** (was 135.06 s — turn 2 produces 8,192 output tokens at the regressed long-context decode rate, ~18 tok/s @ 64K vs prior 52 tok/s) |

Key finding (2026-05-05): vMLX 1.5.20 changes the latency profile dramatically. Prefill jumps from ~360 tok/s to ~900 tok/s across all contexts (2.5×), but long-context decode regresses 36–65 % at 32–64K. Net effect on agent loops depends on output length — short replies win big, long replies lose.

---

## 🤖 Results: dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK

**Date:** 2026-04-21
**Server:** vmlx (MLX Studio v1.3.65 bundled Python) with `--enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3`
**Architecture:** Qwen3.6 MoE+VL — 35B total, 3B active, 4-bit TurboQuant (JANGTQ4), CRACK abliterated, 262K context
**Model path:** `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` via HuggingFace cache

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via `scripts/bench/bench_api_tool_call.py` (2026-04-26). Raw JSON: [`qwen36-35b-a3b-jangtq4-crack/api-tool-test.json`](qwen36-35b-a3b-jangtq4-crack/api-tool-test.json).

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:-------------|:-------|
| Single tool (file read) | 5.37 s | 80 | 14.9 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 2.47 s | 65 | 26.3 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 3.71 s | 145 | 39.1 tok/s | `search_web`, `read_file` | ✅ PASS (parallel) |
| Multi-tool (list + read + write) | 2.77 s | 83 | 29.9 tok/s | `list_directory` | ✅ PASS (chose serial) |
| Agentic reasoning | 10.49 s | 588 | 56.1 tok/s | `run_command` | ✅ PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, `finish_reason: tool_calls`. The MLLM tools patch (`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`) is required for vmlx to forward tool definitions on this model's MLLM code path.

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 2.94 s | 89 |
| 2 | `write_file({...port:8080...})` | 4.02 s | 146 |
| 3 | Natural language summary (stop) | 4.58 s | 166 |
| **Total** | **3 turns, complete task** | **11.54 s** | 401 |

The OpenCode-level Search hang seen in the end-to-end bench (`⛔ hung, 0 tool calls`) does not reproduce at the API level — the model emits valid `tool_calls` deltas on the same `search_web` scenario in 3.7 s. The hang is a harness/prompt-level interaction, not a model tool-call failure.

### OpenCode Agent Benchmark (streaming via `opencode run`)

| Scenario | Response Time (median) | Range (p5-p95) | Turns | Tools Called | Tokens | Errors |
|:---------|:----------------------|:----------------|:------|:------------|:-------|:-------|
| Browse github.com | 93.63s | 93.09 - 96.54s | 2 | `webfetch` | 26,750 | 0 |
| Search 3 latest AI tools | 91.22s | 89.04 - 124.71s | 2-3 | `bash`, `webfetch` | 26,411 | 0 |

### Per-Turn Breakdown (browse, sample run)

| Turn | Duration | Input Tokens | Output Tokens |
|:-----|:---------|:-------------|:-------------|
| 1 | 42.23s | 10,352 | 65 |
| 2 | 49.68s | 16,039 | 335 |

### Per-Turn Breakdown (search, 3-turn run)

| Turn | Duration | Input Tokens | Output Tokens |
|:-----|:---------|:-------------|:-------------|
| 1 | 51.62s | 10,641 | 254 |
| 2 | 34.94s | 11,138 | 244 |
| 3 | 36.95s | 11,633 | 303 |

### Key Findings

1. **Tool calling works reliably** — 0 errors across 6 measured runs. The MLLM tools patch (`scripts/patches/patch_vmlx_jangtq_mllm_tools.py`) is required for vmlx to forward tool definitions to the model.

2. **Reasoning tokens: 0** — despite `--reasoning-parser qwen3`, the model did not emit `<think>` blocks in these short agentic tasks. This may be task-dependent.

3. **2.5x slower than JANG 4K on vllm-mlx** — browse 93.63s vs 36.54s, search 91.22s vs 59.50s. The gap is likely a combination of the vmlx MLLM code path overhead and TurboQuant inference vs standard JANG format.

4. **Consistent browse, variable search** — browse stddev 1.86s (tight), search stddev 19.99s (one run took 3 turns / 124.71s instead of the usual 2).

---

## 🤖 Results: JANGQ-AI/Qwen3.6-27B-JANG_4M

**Date:** 2026-04-23
**Server:** vllm-mlx v0.2.6 (`run_vllm_jang.py` wrapper) with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.6 dense — 27.3B params, hybrid (48 Gated DeltaNet + 16 full-attention) layers, ViT vision encoder, 4.45 bits/param JANG mixed 4/8-bit, 262K native context (1M YaRN). Loaded as `MLLM=False` (text-only — vllm-mlx does not expose the vision tower).
**Model path:** `~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M` (downloaded via `huggingface_hub.snapshot_download`)

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via [`qwen36-27b-jang4m/api-tool-test.json`](qwen36-27b-jang4m/api-tool-test.json). Direct `/v1/chat/completions` invocation, mirroring the API-level table above.

| Scenario | Time | Output Tokens | Speed | Tools Called | Result |
|:---------|:-----|:--------------|:------|:------------|:-------|
| Single tool (file read) | 3.76s | 65 | 17.3 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 3.44s | 64 | 18.6 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 8.13s | 228 | 28.0 tok/s | `search_web`, `read_file` | ✅ PASS (parallel) |
| Multi-tool (list + read + write) | 4.23s | 89 | 21.1 tok/s | `list_directory` | ✅ PASS (chose serial — 1 tool/turn) |
| Agentic reasoning | 13.47s | 421 | 31.3 tok/s | `run_command` | ✅ PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, `finish_reason: tool_calls`. Parallel calling demonstrated in scenario 3.

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 4.42s | 97 |
| 2 | `write_file({...port:8080...})` | 5.89s | 144 |
| 3 | Natural language summary (stop) | 4.53s | 85 |
| **Total** | **3 turns, complete task** | **14.84s** | 326 |

For comparison: the same task on `Qwen3.5-35B-A3B JANG 4K` (sparse 3B-active MoE) finished in 5.64s — dense 27B is ~2.6x slower per turn but completes the loop with the same correctness.

### Streaming Tool Calls (direct curl validation)

Verified independently of OpenCode: a streaming `/v1/chat/completions` request with `stream=true` and a `webfetch` tool returns reasoning chunks (sent as `reasoning` + `reasoning_content` deltas) followed by a `tool_calls` delta and `finish_reason: tool_calls`. End-to-end ~5s for the "Browse github.com" prompt with 283 prompt tokens / 83 completion tokens.

### OpenCode End-to-End Agent Benchmark

**Date:** 2026-04-24 (re-run with `--print-logs --log-level=INFO` captured per-run under [`qwen36-27b-jang4m/agent-bench.logs/`](qwen36-27b-jang4m/agent-bench.logs/)).

Captured via `scripts/bench/bench_agent_tool_call.py` (1 warmup + 3 measured per scenario, `-v` enables opencode INFO logs per run). Raw JSON: [`qwen36-27b-jang4m/agent-bench.json`](qwen36-27b-jang4m/agent-bench.json).

| Scenario | Median | p5 – p95 | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:--------:|:-----:|:-----------|:----------------------:|
| Browse github.com | **114.25 s** | 89.4 – 250.7 s | 2 | `webfetch` | 27,503 |
| Search 3 latest AI agentic tools on github.com | **163.59 s** | 162.31 – 265.76 s | 3 | `bash`, `webfetch` | 35,063 |

Per-turn breakdown (browse, representative run): turn 1 prefill=10,791 tokens → 193.1 s (one `webfetch` tool call, routed through the dense 27B with ~80-200 token `<think>` preamble); turn 2 prefill=16,478 → 56.4 s (final text, 233 output tokens). Search variance is high because some runs chose `bash` shell pipelines (gh-style search via curl/grep) and some chose a single `webfetch` — on runs that chain 4+ web fetches or shell steps, wall time pushes toward the 300 s timeout ceiling.

Cross-model comparison on the same scenarios (all captured 2026-04-24 with the same bench script):

| Model | Server | Browse | Search | vs. this model |
|:------|:-------|:------:|:------:|:--------------|
| Qwen3.5-35B-A3B JANG 4K (sparse MoE, 3B active) | vllm-mlx | 42.58 s | 70.61 s | **~2.7× faster** browse, **~2.3× faster** search |
| Qwen3.6-35B-A3B JANGTQ4-CRACK (sparse MoE, 3B active, TurboQuant 4-bit) | vmlx | 88.94 s ⚠ (2 good + 1 timeout) | ⛔ hung (0 tool calls) | search scenario failed on vmlx — separate issue, not a model-quality signal |
| **Qwen3.6-27B JANG 4M (this model, dense 27B)** | vllm-mlx | **114.25 s** | **163.59 s** | baseline |

### Key Findings

1. **API-level tool calling works perfectly** — 5/5 single-call pass + 3-turn loop completes correctly. Streaming `tool_calls` delta is emitted (verified via curl). Same `qwen3_coder` tool parser + `qwen3` reasoning parser as the Qwen3.5 setup.

2. **Dense 27B latency is ~2.7× sparse 3B-active MoE on end-to-end OpenCode** — browse 114.25 s vs 42.58 s for Qwen3.5-35B-A3B JANG 4K; search 163.59 s vs 70.61 s. The inner 3-turn agentic loop (no OpenCode harness) measured 14.84 s vs 5.64 s. Per-turn time is dominated by full-attention prefill of growing context (turns 1-2 prefill 10-17k tokens × 16 full-attention layers).

3. **High single-run variance (89 – 265 s browse, 162 – 266 s search)** — caused by non-deterministic branching in the agent loop. When the model chooses a single `webfetch` the run finishes in ~90 s; when it chooses a `bash` loop of 5-9 shell calls (observed once in browse warmup and one measured run), wall time pushes toward the 300 s timeout. Median is a more robust metric than mean for this model.

4. **Verbose reasoning preamble** — the model emits ~80-200 tokens of `<think>`-equivalent reasoning (routed to `reasoning_content` by the `qwen3` parser) before the tool call, even on simple prompts. This adds ~1-3s of fixed overhead per turn versus a non-thinking equivalent.

5. **Client-config hygiene** — previously the local `~/.config/opencode/opencode.json` and `~/.pi/agent/models.json` defaulted to `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`, which is not served by the single-model vllm-mlx. Calls without an explicit `--model` returned 404 from the server ("The model … does not exist"). Both local configs were realigned with the repo canonical (`configs/clients/vllm-mlx/`) to default to the live 27B model; this must be repeated whenever the vllm-mlx primary model changes.

---

## 🤖 Results: mlx-community/Qwen3.6-27B-6bit

**Date:** 2026-04-24
**Server:** vllm-mlx v0.2.6 native CLI (no JANG wrapper — standard MLX safetensors) with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.6 dense — 27.3B params, hybrid (48 Gated DeltaNet + 16 full-attention) layers, ViT vision encoder, standard MLX 6-bit quantization (uniform), 262K native context. Loaded as `MLLM=False` (text-only — vllm-mlx does not expose the vision tower).
**Model path:** `~/.cache/huggingface/hub/models--mlx-community--Qwen3.6-27B-6bit` (21 GB on disk, downloaded via `hf download`)

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via `scripts/bench/bench_api_tool_call.py` (2026-04-26). Raw JSON: [`qwen36-27b-6bit/api-tool-test.json`](qwen36-27b-6bit/api-tool-test.json).

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:-------------|:-------|
| Single tool (file read) | 5.75 s | 101 | 17.6 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 4.73 s | 79 | 16.7 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 7.52 s | 157 | 20.9 tok/s | `search_web`, `read_file` | ✅ PASS (parallel) |
| Multi-tool (list + read + write) | 8.83 s | 193 | 21.9 tok/s | `list_directory` | ✅ PASS (chose serial) |
| Agentic reasoning | 13.69 s | 328 | 24.0 tok/s | `run_command` | ✅ PASS |

**Pass rate: 5/5** — correct tool selection, valid JSON arguments, `finish_reason: tool_calls`. Single-call latency (~5–9 s) is roughly 1.5–2× the JANG_4M dense baseline at the same param count, despite no JANG wrapper overhead — extra latency tracks the 6-bit weight bandwidth (21 GB vs 17.5 GB).

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 7.53 s | 154 |
| 2 | `write_file({...port:8080...})` | 5.91 s | 103 |
| 3 | Natural language summary (stop) | 5.87 s | 94 |
| **Total** | **3 turns, complete task** | **19.31 s** | 351 |

### OpenCode End-to-End Agent Benchmark

Captured via `scripts/bench/bench_agent_tool_call.py` (1 warmup + 3 measured per scenario). Raw JSON: [`qwen36-27b-6bit/agent-bench.json`](qwen36-27b-6bit/agent-bench.json).

| Scenario | Wall (median) | LLM (median) | p5 – p95 | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:------:|:--------:|:-----:|:-----------|:----------------------:|
| Browse github.com | **119.93 s** | 118.76 s | 106.21 – 124.42 s | 2 | `webfetch` | 27,536 |
| Search 3 latest AI agentic tools on github.com | **300.04 s** ⚠ | 161.04 s | 162.25 – 300.05 s | 2 | `webfetch`, `bash`, `glob` | 32,764 |

⚠ 2 of 3 search runs hit OpenCode's 300 s wall-clock cap: one chained 4 tools (`webfetch`×2 + `bash` + `glob`, 237 s LLM time, client killed at 300 s); one returned zero output/turns at the cap. Only run 3 (162.25 s / 161.04 s LLM, 2 × `webfetch`) completed cleanly. Same pattern as the JANG_4M baseline — dense 27B + multi-tool chain regularly hits the timeout ceiling.

Per-turn breakdown (browse, representative run): turn 1 prefill ≈ 10.8k tokens → 56 s, turn 2 prefill ≈ 16.5k → 62 s. 0 reasoning tokens emitted in any run — the `qwen3` reasoning parser is armed but the model did not produce `<think>` blocks on these prompts.

Cross-model comparison on the same scenarios (all captured 2026-04-24 with the same bench script):

| Model | Server | Bits | Disk | Browse | Search | vs. this model |
|:------|:-------|:----:|:----:|:------:|:------:|:--------------|
| Qwen3.5-35B-A3B JANG 4K (sparse MoE, 3B active) | vllm-mlx | 4.00 mixed | — | 42.58 s | 70.61 s | **~2.8× faster** browse, **~2.3× faster** search |
| Qwen3.6-27B JANG 4M (dense, same architecture) | vllm-mlx | 4.45 mixed | 17.5 GB | 114.25 s | 163.59 s | 5 % faster browse (smaller weights), ~1 % diff on clean search |
| **Qwen3.6-27B 6bit (this model, dense 27B)** | vllm-mlx | 6.00 uniform | 21 GB | **119.93 s** | **162.25 s** (clean) | baseline |

### Key Findings

1. **Right server chosen** — vllm-mlx native CLI (no JANG wrapper needed; the 6-bit model is standard MLX safetensors). Documented as lowest-overhead server at long contexts in CLAUDE.md. Tool-call + reasoning parsers attached cleanly on startup (`qwen3_coder` / `qwen3`).

2. **Browse ~5 % slower than JANG_4M** (119.93 s vs 114.25 s) — consistent with the 21 GB vs 17.5 GB weight-bandwidth ratio on M3 Ultra. Memory bandwidth dominates per-token cost at these prompt sizes; no algorithmic regression vs JANG mixed-precision.

3. **Search median inflated by client timeout** — on runs that converge in 2 turns the 6-bit model performs within 1 % of JANG_4M (162.25 s vs 163.59 s). Dense 27B models chain 4+ tool calls roughly 1 in 3 runs, which pushes wall time past OpenCode's 300 s ceiling. Use median-of-clean-runs or raise the client cap for a cleaner number.

4. **Quality upside not measured here** — this bench is latency-only. External reference (LLM infrastructure research memo, 1350): 6-bit uniform retains ~1 ppt more quality vs 4.45-bit JANG mixed on standard benchmarks while adding ~3.5 GB disk / ~5 % wall latency.

### Server comparison: lm-studio vs vllm-mlx (same model file, 2026-04-30)

Same model, same hardware, same OpenCode bench harness. The only variable is the server.

**Setup for lm-studio:** LM Studio installed via `brew install --cask lm-studio` (v0.4.12). MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`. Bootstrapped `~/.lmstudio/bin/lms`, ran `lms get https://huggingface.co/mlx-community/Qwen3.6-27B-6bit`, loaded via `lms load qwen3.6-27b --gpu max --context-length 65536`, served via `lms server start --bind 0.0.0.0`. Served identifier: `qwen3.6-27b` (lowercase, org prefix stripped — used as-is in the bench `--model` arg). Raw JSON: [`qwen36-27b-6bit/api-server-lm-studio.json`](qwen36-27b-6bit/api-server-lm-studio.json), [`api-tool-test-lm-studio.json`](qwen36-27b-6bit/api-tool-test-lm-studio.json), [`agent-bench-lm-studio.json`](qwen36-27b-6bit/agent-bench-lm-studio.json).

**API-level tool calling (5-tool harness, 2026-04-30 prompts):**

| Scenario | vllm-mlx | lm-studio | Δ |
|:---------|:--------:|:-------:|:---:|
| Single tool (file read) | 5.75 s | 6.58 s | +14 % |
| Single tool (command) | 4.73 s | 4.22 s | −11 % |
| Multi-tool (search + read) | 7.52 s | 8.86 s | +18 % |
| Multi-tool (list + read + write) | 8.83 s | 5.28 s | **−40 %** |
| Agentic reasoning | 13.69 s | 18.07 s | +32 % |
| **3-turn agentic loop total** | **19.31 s** | **20.28 s** | +5 % |

API-level latency is roughly a wash (within ±20 % per scenario, +5 % on the 3-turn loop). Both servers pass 5/5; the underlying decode rate is set by the same MLX kernels and the same 6-bit weight bandwidth.

**OpenCode end-to-end (`opencode run`, browse + search, 1 warmup + 3 measured):**

| Scenario | vllm-mlx wall / llm | lm-studio wall / llm | lm-studio speedup |
|:---------|:-------------------:|:------------------:|:----------------:|
| Browse www.example.com | 97.93 s / 96.75 s | **31.96 s / 30.74 s** | **3.1× faster** |
| Browse Hackernews latest topic | 127.28 s / 126.05 s | **25.71 s / 24.51 s** | **4.9× faster** |

This is the headline finding. Same MLX file, same hardware, same client harness, same prompts. **lm-studio is 3–5× faster end-to-end on the OpenCode agent loop**.

**Why lm-studio wins on agent workloads:**

1. **Prefill kernel is dramatically faster.** lm-studio's `mlx-llm` runtime sustains 47K tok/s prefill at 32K context (TTFT 0.70 s). The closest comparison from vllm-mlx + this model family is the JANG_4M variant at ~314 tok/s prefill (TTFT 104 s @ 32K). The 10-K-token OpenCode system prompt and tool catalog is mostly prefill cost — every turn shaves tens of seconds.
2. **Reasoning content is exposed correctly.** lm-studio captured 70–79 reasoning tokens per scenario (visible in agent-bench JSON `reasoning_tokens`). vllm-mlx with this exact model + `--reasoning-parser qwen3` reported 0 reasoning tokens — the parser detected no `<think>` blocks. Either lm-studio's chat-template handling preserves Qwen3.6 thinking output where vllm-mlx swallows it, or the LM Studio MLX runtime emits thinking content even when the chat template suppresses it. Net effect: lm-studio is letting the model think briefly (~75 tok), reach the tool call faster, and the user sees a concise final answer.
3. **OpenCode-side overhead is identical.** LLM time tracks wall time within ~1.2 s on both servers — the gap is purely model-side, not client/streaming overhead.

**Decode (gen tok/s) is slightly slower on lm-studio** (29.9 vs vllm-mlx + JANG_4M at 36.5 @ 512). The 5-tool API harness shows this trade — single-call latency is similar, agentic reasoning (which decodes more tokens) is +32 %. But for agent loops where prefill dominates, the prefill win compensates ~10× over.

**Caveats:**
- Comparison is against vllm-mlx + JANG 4M for prefill numbers (the standard 6-bit model on vllm-mlx never had an api-server benchmark run). For agent-bench, the comparison is direct (same model file).
- lm-studio ships closed-source MLX runtime — exact prefill kernel implementation isn't auditable. If LM Studio rewrites the runtime in a future update, results may shift.
- lm-studio's `lms get` doesn't reuse the HF cache — re-downloaded the same 22 GB into `~/.lmstudio/models/`. Disk-cost duplication for any HF-cached model.

**Recommendation:** For standard MLX models that don't need JANG/JANGTQ patches, **lm-studio is the better server for agent workloads** on this hardware. The vllm-mlx stack remains the right choice for JANG-quantized weights, custom parsers (`hermes` for Ling, `nemotron`), and the patches required for `bailing_hybrid` / Mistral Small 4. For Qwen3.6-27B-6bit specifically, this changes the production calculus — if quality at the 6-bit weight class is acceptable, lm-studio makes this a viable agent default at ~30 s end-to-end browse latency.

---

## 🤖 Results: jedisct1/Qwen3.6-35B-rust.mlx

**Date:** 2026-04-24
**Server:** vllm-mlx v0.2.6 native CLI with `--enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3`
**Architecture:** Qwen3.6-35B-A3B (`Qwen3_5MoeForConditionalGeneration`, `model_type=qwen3_5_moe`) — 256 experts, 8 active per token, 40 layers (3 linear / 1 full attention pattern, Mamba-like SSM hybrid), `max_position_embeddings=262144`, vision tokens defined in tokenizer (text-only here). 8-bit MLX uniform quant (group_size=64). Base: `Brooooooklyn/Qwen3.6-35B-A3B-UD-Q8_K_XL-mlx`. LoRA (rank 8, alpha 16) trained on 356K Rust commits (634K samples) for diff generation, then merged into the quantized weights.
**Model path:** `~/.omlx/models/jedisct1--Qwen3.6-35B-rust.mlx` (35 GB on disk, downloaded via `hf download`)

### Typical Inference (`scripts/bench/bench_api_server.py`, 1 warmup + 2 runs, median)

Raw JSON: [`qwen36-35b-rust/api-typical.json`](qwen36-35b-rust/api-typical.json).

| Context (tokens) | TTFT (median) | Gen tok/s (median) |
|:----------------:|:------:|:------:|
|  ~256 |  0.31 s | **83.2** |
| ~2,048 |  1.00 s | 82.2 |
| ~8,192 |  3.70 s | 79.7 |

Generation throughput stays in the 80 tok/s band even at 8K prefill — matches the ~A3B-class behaviour seen on JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K (only 3 B params active per token despite 35 B total). `prompt_tokens` reports 0 in the streaming SSE / non-streaming probe — known vllm-mlx field-fill bug, not a real prefill of zero. `prefill_tps` therefore unmeasurable here; TTFT scales linearly with context (~0.45 ms / token), consistent with M3 Ultra bandwidth on 8-bit MoE weights.

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via `scripts/bench/bench_api_tool_call.py` (2026-04-26). Raw JSON: [`qwen36-35b-rust/api-tool-test.json`](qwen36-35b-rust/api-tool-test.json).

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:-------------|:-------|
| Single tool (file read) | 1.80 s | 84 | 46.7 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 1.42 s | 82 | 57.7 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 2.70 s | 188 | 69.5 tok/s | `search_web`, `read_file` | ✅ PASS (parallel) |
| Multi-tool (list + read + write) | 1.42 s | 82 | 57.7 tok/s | `list_directory` | ✅ PASS (chose serial) |
| Agentic reasoning | 12.82 s | 1024 | 79.9 tok/s | (none) | ❌ FAIL — `finish_reason: length` |

**Pass rate: 4/5** — fastest single-call latency of any model in this doc (A3B sparsity + cache-warm SSM hybrid). The `Agentic reasoning` failure is a model behaviour, not a server bug: this Rust-LoRA-tuned variant emits long Gemini-style chain-of-thought as plain `content` (no `<think>` wrapper) and runs out of token budget before emitting the tool call. Other models on this prompt produce 328-588 tokens and call the tool cleanly. Bumping `max_tokens` past 1024 is unlikely to help — sample inspection shows the model loops on candidate-command deliberation.

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 1.57 s | 93 |
| 2 | `write_file({...port:8080...})` | 2.86 s | 197 |
| 3 | Natural language summary (stop) | 2.56 s | 168 |
| **Total** | **3 turns, complete task** | **6.99 s** | 458 |

At API level the 4-bit Qwen3.5-35B-A3B JANG 4K baseline (5.64 s, 1.18-1.21 s single-call) still edges out this 8-bit variant — A3B sparsity gives both models 3 B active params, but lower-bit weights win on memory bandwidth. The Rust LoRA's huge OpenCode-end-to-end advantage (4.5× over the dense 27B models) comes from prefill + agent-loop convergence, not from per-call generation speed.

### OpenCode End-to-End Agent Benchmark

Captured via `scripts/bench/bench_agent_tool_call.py --warmup 1 --runs 3 --skip-permissions --verbose`. Raw JSON: [`qwen36-35b-rust/agent-bench.json`](qwen36-35b-rust/agent-bench.json).

| Scenario | Wall (median) | LLM (median) | p5 – p95 | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:------:|:--------:|:-----:|:-----------|:----------------------:|
| Browse github.com | **25.35 s** | 24.17 s | 21.67 – 28.28 s | 2 | `webfetch` | 27,619 |
| Search 3 latest AI agentic tools on github.com | **36.73 s** | 35.58 s | 27.38 – 51.15 s | 3 | `webfetch`, `bash` | 34,165 |

Per-turn breakdown (browse, sample): turn 1 prefill ≈ 10.8k → 11.0 s, turn 2 prefill ≈ 16.5k → 13.2 s. 0 reasoning tokens emitted — the qwen3 reasoning parser is armed but the model produced its thinking in the body of the assistant response (Gemini-style "Here's a thinking process:" preamble, captured by the parser only when `</think>` is hit; on agent turns it skips thinking entirely).

Cross-model comparison on the same scenarios (all captured 2026-04-24 with the same bench script):

| Model | Server | Bits | Active params | Disk | Browse | Search | vs. this model |
|:------|:-------|:----:|:----:|:----:|:------:|:------:|:--------------|
| **Qwen3.6-35B-A3B Rust LoRA (this model)** | vllm-mlx | 8 uniform | 3 B | 35 GB | **25.35 s** | **36.73 s** | baseline |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx | 4 mixed | 3 B | — | 42.58 s | 70.61 s | this is **~1.7×** / **~1.9×** faster |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx | 4.45 mixed | 27 B | 17.5 GB | 114.25 s | 163.59 s | this is **~4.5×** / **~4.5×** faster |
| Qwen3.6-27B 6bit (dense) | vllm-mlx | 6 uniform | 27 B | 21 GB | 119.93 s | 162.25 s | this is **~4.7×** / **~4.4×** faster |

### Key Findings

1. **Right server chosen** — vllm-mlx native CLI. The `qwen3_5_moe` architecture is supported by mlx-lm 0.31.1 (`mlx_lm/models/qwen3_5_moe.py`); the chat template is the standard Qwen3 XML tool format that the existing `qwen3_coder` parser handles natively. Tool call probe (`get_weather`) returned a clean OpenAI `tool_calls` block on first try.

2. **Faster than other A3B 35 B variants on these scenarios despite 8-bit (vs 4-bit) weights** — most of the speedup is the smaller / cleaner agent loops the Rust-tuned model takes (browse converges in 2 turns, search in 3 vs 5+ for some other models). A3B sparsity (3 B active) keeps generation throughput high; 8-bit weight-bandwidth penalty is real (~5–10 % vs 4-bit) but doesn't dominate at these token counts.

3. **Search variance is wide (27 – 51 s, p5 – p95)** — one of three measured runs went 5 turns / 6 bash calls. The Rust-specialist LoRA does not appear to break general agentic tool use on natural-language prompts, but it does drift toward `bash` more than `webfetch` (vs. dense Qwen3.6 which prefers `webfetch`). Worth flagging if you intend to use this for non-Rust agent work.

4. **Agentic value is limited by training scope** — the LoRA was trained on Rust commit diffs (jedisct1/rust dataset, 356K commits). Strong code-generation specialist, but not a general agent. For Rust-heavy refactor / patch workflows it may outperform the base model; for general agentic browse/search/etc. you're getting the base Qwen3.6-35B-A3B behaviour (this benchmark) without the Rust upside.

5. **No JANG / TurboQuant bug surfaced** — this is plain 8-bit MLX safetensors (no JANG mixed precision, no TurboQuant), so vllm-mlx can run it without the JANG wrapper script. No special config knobs needed beyond the standard Qwen3 parser flags.

---

## 🤖 Results: mlx-community/Ling-2.6-flash-mlx-6bit

**Date:** 2026-04-29
**Server:** vllm-mlx v0.2.6 native CLI (no JANG wrapper) with `--enable-auto-tool-choice --tool-call-parser hermes`
**Architecture:** `BailingMoeV2_5ForCausalLM` / `model_type=bailing_hybrid` — 104 B total, 7.4 B active, 32 layers (4 MLA layers at indices 4/15/23/31, 28 Lightning-style linear-attention recurrence layers), 256 experts (8 active per token + 1 shared), sigmoid noaux_tc routing with group-limited top-8, 6-bit MLX uniform quant (~80 GB on disk), `max_position_embeddings=131,072`. No `<think>` reasoning emitted. Text-only.
**Model path:** `mlx-community/Ling-2.6-flash-mlx-6bit` (HF cache)
**Deployment patches (all required, all idempotent):**
1. Vendored `mlx_lm/models/bailing_hybrid.py` from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227) into `~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/models/`
2. [`scripts/patches/patch_mlx_lm_threadlocal_stream.py`](../../../scripts/patches/patch_mlx_lm_threadlocal_stream.py) — converts module-level thread-local `generation_stream` into a per-thread lazy accessor
3. [`scripts/patches/patch_vllm_mlx_inline_gen.py`](../../../scripts/patches/patch_vllm_mlx_inline_gen.py) — replaces `await asyncio.to_thread(...)` with direct synchronous calls so MLX kernels stay on the asyncio loop thread (required for thread-bound `mx.fast.metal_kernel` objects used by the linear-attention recurrence and GLA SSM kernel)

### API-Level Tool Calling (non-streaming, 5 tools available)

Captured via `scripts/bench/bench_api_tool_call.py` (2026-04-29). Raw JSON: [`ling-2.6-flash-6bit/api-tool-test.json`](ling-2.6-flash-6bit/api-tool-test.json).

| Scenario | Time | Tokens | Speed | Tools Called | Result |
|:---------|:-----|:-------|:------|:-------------|:-------|
| Single tool (file read) | 2.13 s | 22 | 10.3 tok/s | `read_file` | ✅ PASS |
| Single tool (command) | 1.21 s | 24 | 19.8 tok/s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 1.81 s | 47 | 26.0 tok/s | `search_web`, `read_file` | ✅ PASS (parallel) |
| Multi-tool (list + read + write) | 1.61 s | 33 | 20.5 tok/s | `list_directory` | ✅ PASS (chose serial) |
| Agentic reasoning | 1.51 s | 32 | 21.2 tok/s | `run_command` | ✅ PASS |

**Pass rate: 5/5** — fastest sub-2s single-call median in this doc behind only the JANG_4K MoE. Tool calls emerge as Hermes-format `<tool_call>{json}</tool_call>` blocks; vllm-mlx's `hermes` parser converts them cleanly to OpenAI `tool_calls`. No `qwen3` parser variant works here (vllm-mlx 0.2.6 only ships `qwen3_coder` for tool-call parsing, which expects XML body — Ling emits JSON body).

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time | Output Tokens |
|:-----|:-------|:-----|:--------------|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 1.41 s | 32 |
| 2 | `write_file({...port:8080...})` | 1.61 s | 56 |
| 3 | Natural language summary (stop) | 1.71 s | 43 |
| **Total** | **3 turns, complete task** | **4.74 s** | 131 |

Fastest completion of the 3-turn config-fix loop in this doc — beats the prior champion (Qwen3.5-35B-A3B JANG 4K at 5.64 s). Architecture pays: only 7.4 B active params, no `<think>` preamble. Note: the first measurement of this same loop in the un-tooled-server smoke pass took 16.22 s on the read_file call due to first-time JIT compilation of the GLA Metal kernel; subsequent calls dropped to 1.21 - 2.13 s. Quoted numbers above are warm.

### OpenCode End-to-End Agent Benchmark

Captured via `scripts/bench/bench_agent_tool_call.py --warmup 1 --runs 3 --skip-permissions`. Raw JSON: [`ling-2.6-flash-6bit/agent-bench.json`](ling-2.6-flash-6bit/agent-bench.json).

| Scenario | Wall (median) | LLM (median) | p5 – p95 | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:------:|:--------:|:-----:|:-----------|:----------------------:|
| Browse github.com | **36.61 s** | 35.41 s | 34.85 – 48.50 s | 2 | `webfetch` (1× `bash` outlier in run 3) | 27,928 |
| Search 3 latest AI agentic tools on github.com | **76.98 s** | 75.68 s | 51.33 – 91.65 s | 4 | `webfetch` (one run used `bash`) | 63,435 |

Per-turn breakdown (browse, sample): turn 1 prefill ≈ 10.8k → 13.3 s, turn 2 prefill ≈ 16.8k → 22.1 s. 0 reasoning tokens. Search took **3 - 4 measured turns** (vs 2 - 3 for the Qwen models on the same prompt) — the model chains `webfetch` calls iteratively rather than synthesising 3 results from a single fetch.

Cross-model comparison on the same scenarios (best-of-doc runs):

| Model | Server | Bits | Active params | Disk | Browse | Search | vs. this model |
|:------|:-------|:----:|:----:|:----:|:------:|:------:|:--------------|
| Qwen3.6-35B-A3B Rust LoRA | vllm-mlx | 8 uniform | 3 B | 35 GB | 20.77 s | **23.29 s** | this is **~1.8×** slower browse, **~3.3×** slower search |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx | 4 mixed | 3 B | — | **16.74 s** | 81.92 s | this is **~2.2×** slower browse, **~1.1× faster** search |
| **Ling-2.6-flash mlx-6bit (this model)** | vllm-mlx (patched) | 6 uniform | 7.4 B | 80 GB | **36.61 s** | **76.98 s** | baseline |
| Qwen3.6-35B-A3B JANGTQ4-CRACK | vmlx | TQ4 | 3 B | — | 97.21 s | 91.45 s | this is **~2.7× faster** browse, **~1.2× faster** search |
| Qwen3.6-27B JANG 4M (dense) | vllm-mlx | 4.45 mixed | 27 B | 17.5 GB | 89.81 s | 117.73 s | this is **~2.5× faster** browse, **~1.5× faster** search |
| Qwen3.6-27B 6bit (dense) | vllm-mlx | 6 uniform | 27 B | 21 GB | 124.30 s | 283.37 s | this is **~3.4× faster** browse, **~3.7× faster** search |

### Key Findings

1. **Best-in-doc API-level tool-call latency** — 5/5 pass with all calls under 2.2 s; the 4.74 s 3-turn loop is the new champion. This is what 7.4 B active params bought us on M3 Ultra. Practical agent latency for coding-style read/write/edit workflows is excellent.

2. **OpenCode end-to-end is mid-pack on browse, weaker on search** — wall-time ranking sits between the two A3B 35 B winners and the dense 27B losers. Browse converges in 2 turns like the Qwen models; search expands to 3 - 4 turns with multiple `webfetch` calls. The model is more "agentic-iterative" than the Qwen models on multi-step research, which costs wall time even though per-call generation is fast.

3. **Three patches required to run at all**: bailing_hybrid is brand-new in mlx-lm (unmerged PR #1227). The thread-local stream + asyncio-to-thread interaction with thread-bound Metal kernels surfaced the deepest mlx-lm/vllm-mlx integration bug in this doc. See server section in [model-benchmark-api-server.md](#ling-26-flash-mlx-6bit-104b7b-active-bailing_hybrid) for technical details.

4. **64K context ceiling** on M3 Ultra (96 GB) — KV cache for 4 MLA layers + the 80 GB model weights pushes 128K out of memory. OpenCode never approaches that limit (max ~63K observed in search), so this is not a practical agent issue, only a doc-truth note.

5. **No `<think>` reasoning** — adds no thinking-token overhead. For agent loops where you want minimal preamble before tool calls, this is a structural advantage versus Qwen3 / Qwen3.6 thinking models.

---

## 🤖 Results: lmstudio-community/gemma-4-31B-it-MLX-6bit

**Date:** 2026-05-01
**Server:** lm-studio (LM Studio headless), `lms server start --bind 0.0.0.0 --cors --port 1234`. Model loaded via `lms load gemma-4-31b-it-mlx --gpu max --context-length 65536 -y`. **No parser flags** — LM Studio's MLX runtime auto-detects Gemma 4 tool-call and routes `<think>` to `reasoning_content`.
**Architecture:** Google Gemma 4 dense **31 B** instruction-tuned, text-only (no vision, no MoE), uniform 6-bit MLX, 29 GB on disk. Per-model deep dive: [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit).

### API-Level Tool Calling (5-tool harness, 2026-05-01)

| Scenario | Time | Tools Called | Result |
|:---------|:-----|:-------------|:-------|
| Single tool (file read) | 3.77 s | `read_file` | ✅ PASS |
| Single tool (command) | 1.28 s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 2.41 s | `search_web`, `read_file` | ✅ PASS |
| Multi-tool (list + read + write) | 1.41 s | `list_directory` (1 of 3 expected) | ⚠ partial — only one tool emitted, but well-formed and `finish_reason: tool_calls` |
| Agentic reasoning | 2.40 s | `run_command` | ✅ PASS |

**Pass rate: 5/5** — all single-call scenarios produce valid OpenAI `tool_calls[]`. The "multi-tool list+read+write" scenario emits a single `list_directory` call rather than the three expected; client would re-prompt after the tool result. Counted as PASS because the call is well-formed; logging it here as the only deviation. Raw JSON: [`gemma-4-31b-it-6bit/api-tool-test-lm-studio.json`](gemma-4-31b-it-6bit/api-tool-test-lm-studio.json).

### Multi-Turn Agentic Loop (simulated tool results)

Task: "Read /tmp/app/config.json, change port to 8080, write back"

| Turn | Action | Time |
|:-----|:-------|:-----|
| 1 | `read_file({"path":"/tmp/app/config.json"})` | 2.86 s |
| 2 | `write_file({...port:8080...})` | 4.02 s |
| 3 | Natural language summary (stop) | 2.92 s |
| **Total** | **3 turns, complete task** | **9.8 s** |

About 2× faster than the same loop on Qwen3.6-27B 6-bit on lm-studio (20.28 s) — Gemma 4 31B-it skips the thinking preamble entirely.

### OpenCode End-to-End Agent Benchmark (2026-05-01)

Captured via `scripts/bench/bench_agent_tool_call.py --scenario both --warmup 1 --runs 3` against `macstudio/gemma-4-31b-it-mlx`. Raw JSON: [`gemma-4-31b-it-6bit/agent-bench-lm-studio.json`](gemma-4-31b-it-6bit/agent-bench-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5 – p95 wall | Turns | Tools used | Tokens (total, median) |
|:---------|:------:|:------:|:------:|:-----:|:-----------|:----------------------:|
| Browse www.example.com | **5.11 s** | 3.94 s | 4.97 – 5.12 s | 2 | `webfetch` | 20,225 |
| Browse Hackernews latest topic | **6.37 s** | 5.18 s | 6.24 – 6.37 s | 2 | `webfetch` | 25,397 |

Per-turn breakdown (browse, sample): turn 1 prefill 10,062 tokens → 2.48 s, turn 2 prefill 10,128 tokens → 1.31 s, output 20 + 15 tokens. Search: turn 1 prefill 10,067 → 3.28 s, turn 2 prefill 15,285 → 1.77 s, output 23 + 22 tokens. **Output is tiny** — the model goes straight to the tool call with zero or near-zero textual prelude.

Cross-model comparison (current best-of-doc on the new 2026-04-30 prompt set):

| Model | Server | Browse | Search | vs. Gemma 4 31B-it on lm-studio |
|:------|:-------|:------:|:------:|:------------------------------|
| **Gemma 4 31B-it (this model)** | **lm-studio** | **5.11 s** 🏆 | **6.37 s** 🏆 | baseline |
| Qwen3.5-35B-A3B JANG 4K | vllm-mlx (patched) | 12.86 s 🥈 | 16.28 s 🥈 | this is **2.5× faster** browse, **2.6× faster** search |
| Qwen3.6-35B Rust LoRA | vllm-mlx | 13.94 s | 26.31 s | this is **2.7× faster** browse, **4.1× faster** search |
| Qwen3.6-35B-A3B 4-bit + DFlash | dflash-mlx | 27.59 s | 54.78 s | this is **5.4× faster** browse, **8.6× faster** search |
| Ling-2.6-flash mlx-6bit | vllm-mlx (patched) | 25.75 s | 29.64 s | this is **5.0× faster** browse, **4.7× faster** search |
| Qwen3.6-27B 6bit | lm-studio | 31.96 s | 25.71 s | this is **6.3× faster** browse, **4.0× faster** search |
| Qwen3.6-27B JANG 4M | vllm-mlx (patched) | 69.14 s | 108.51 s | this is **13.5× faster** browse, **17.0× faster** search |

### Key Findings

1. **New end-to-end agent-loop champion in this doc.** 5.11 s browse / 6.37 s search are the fastest wall times across every model + server tested here (prior champion: Qwen3.5-35B-A3B JANG 4K on vllm-mlx at 12.86 s / 16.28 s). The win is structural — Gemma 4 31B-it on this prompt set emits **15–23 output tokens per turn** with no thinking preamble, whereas Qwen3 / Qwen3.6 thinking models emit hundreds of `<think>` tokens before the tool call.

2. **Decode is actually slower than Qwen3.6-27B on the same lm-studio** (18 vs 26 tok/s @ 32K, see [api-server bench](model-benchmark-api-server.md#gemma-4-31b-it-6-bit-dense-on-lm-studio)). The agent-loop win is entirely about **tokens generated per agent turn**, not raw decode speed. Larger models that talk less beat smaller models that think out loud.

3. **Tool-call surface works on lm-studio without parser flags.** `bench_api_tool_call.py` passes 5/5 single-call scenarios, and the OpenCode end-to-end loop completes in 2 turns on both scenarios with zero `error_count`. LM Studio's MLX runtime auto-detects Gemma 4's tool-call format — no `--tool-call-parser gemma4` flag exists or is needed.

4. **`reasoning_content` field is present but empty on every bench prompt.** Gemma 4 has built-in thinking mode but did not invoke it on any of the 5 tool-harness scenarios or the 6 OpenCode runs (3 browse + 3 search). The runtime's reasoning routing is wired correctly (verified in smoke); the model simply chose not to think for these short-output tool-calling prompts. Set `chat_template_kwargs.enable_thinking: true` if you need explicit thinking.

5. **`lms get` is unreliable for >20 GB models.** First two `lms get` attempts hung at 88 % with no resume capability (only shards 4–6 of 6 reached disk). Working path: kill the hung process, complete the download with `huggingface_hub.snapshot_download(repo_id=…, local_dir=~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit)`. LM Studio recognises the on-disk layout afterward. See [`per-model/model-summary-gemma.md`](../per-model/model-summary-gemma.md#gemma-4-31b-it-6-bit) "Loader gotcha" callout.

6. **First load ignored `--context-length`** — model came up at 4K despite `--context-length 65536`, hit `HTTP 400: tokens exceed context length` on the 4K bench. Re-`lms unload` + re-`lms load --context-length 65536 -y` correctly seats 64K. Verify with `lms ps` after every load.

### Re-bench: mlx-lm server (2026-05-06, thinking ON)

**Date:** 2026-05-06
**Server:** `mlx_lm.server` from the homebrew Cellar libexec (`/opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server`), port 8000. **Do not use** `/opt/homebrew/bin/mlx_lm.server` — that symlink resolves to a python3.11 mlx_lm that lacks Gemma 4 (raises `Model type gemma4 not supported`). No parser flags — mlx-lm 0.31.3 has native Gemma 4 support. **Thinking mode ON by default** (model emits thinking context before tool calls).

#### API-Level Tool Calling (5-tool harness, 2026-05-06)

Raw JSON: [`gemma-4-31b-it-mlx-6bit/api-tool-test.json`](gemma-4-31b-it-mlx-6bit/api-tool-test.json).

| Scenario | Time | Tools Called | Result |
|:---------|:-----|:-------------|:-------|
| Single tool (file read) | 4.56 s | `read_file` | ✅ PASS |
| Single tool (command) | 2.96 s | `run_command` | ✅ PASS |
| Multi-tool (search + read) | 5.64 s | `search_web`, `read_file` | ✅ PASS — both tools in one call |
| Multi-tool (list + read + write) | 5.64 s | `list_directory` (1 of 3 expected) | ⚠ partial — same single-tool deviation as lm-studio run |
| Agentic reasoning | 11.28 s | `run_command` | ✅ PASS — 207 output tokens (thinking) |

**Multi-turn loop total:** 20.73 s (3 turns: read 8.51 s + write 9.26 s + summary 2.96 s). Notably slower than lm-studio's 9.8 s — model generates 134+156 output tokens vs 20+15 on lm-studio. Multi-tool (search + read) now calls BOTH tools in a single response (vs lm-studio which only called `search_web`).

#### OpenCode End-to-End Agent Benchmark (2026-05-06, thinking ON)

Raw JSON: [`gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json`](gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json).

| Scenario | Wall (median) | LLM (median) | p5 – p95 wall | Turns | Tools used | Output tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:-----------|:----------------------:|
| Browse www.example.com | **12.33 s** | 11.12 s | 12.33 – 12.35 s | 2 | `webfetch` | 121 |
| Browse Hackernews latest topic | **35.55 s** | 34.38 s | 35.28 – 35.85 s | 2 | `webfetch` | 124 |

Per-turn breakdown (browse): turn 1 → 4.83 s / 53 tokens; turn 2 → 6.30 s / 68 tokens. Search: turn 1 → 7.59 s / 83 tokens; turn 2 → 26.79 s / 41 tokens (long HN page prefill at 5K tokens dominates). Total output tokens per run: ~121 browse / ~124 search — **3–4× higher than the lm-studio thinking-OFF run (35 / 45 tokens)**.

**Thinking-ON vs Thinking-OFF impact:**

| Run | Server | Browse | Search | Output tokens/turn (browse) |
|:----|:-------|:------:|:------:|:---------------------------:|
| 2026-05-01 (thinking OFF) | lm-studio | **5.11 s** | **6.37 s** | ~17 |
| 2026-05-06 (thinking ON) | mlx-lm | 12.33 s | 35.55 s | ~60 |
| Overhead factor | | **2.4×** | **5.6×** | **3.5×** |

**Why thinking mode hurts agent latency more for search than browse:** The HN page response is ~5K tokens of prefill on turn 2. With thinking ON, the model also generates a long reasoning trace before the final summary answer — at ~15 tok/s effective decode, each extra 60 reasoning tokens costs ~4 s. Browse has a smaller turn-2 prefill (~10K) and the summary is shorter, so the overhead is less pronounced.

---

## 🤖 Results: IBM Granite 4.1 30B Q8_0 on lm-studio

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, GGUF Q8_0 runtime. Loaded with `--identifier granite-4.1-30b-q8 --context-length 65536`. No parser flags required.
**Architecture:** IBM Granite — dense 30B decoder-only, no MoE, no thinking channel.

### Typical Inference

| Scenario | Gen tok/s | Context | TTFT (s) |
|:---------|----------:|--------:|---------:|
| 512 tok | 24.8 | 512 | 0.22 |
| 4K tok | 26.0 | 4K | 0.23 |
| 32K tok | 18.7 | 32K | 0.36 |

### API-Level Tool Calling (5-tool harness)

Raw JSON: [`granite-4.1-30b-q8/api-tool-test.json`](granite-4.1-30b-q8/api-tool-test.json).

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 2.99 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.13 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 1.29 | `tool_calls` | `search_web` |
| 4 | Multi-tool (list + read + write) | 1.13 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 1.14 | `tool_calls` | `list_directory` |

**Pass rate: 5/5.** LM Studio handles Granite 4.1's tool-call format natively — no `--tool-call-parser` flag at load time.

#### Multi-turn agentic loop (3 turns, total 10.37 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 2.74 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 3.14 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 4.50 | `stop` | — final answer |

### OpenCode Agent Loop (browse + search)

Raw JSON: [`granite-4.1-30b-q8/agent-bench-lm-studio.json`](granite-4.1-30b-q8/agent-bench-lm-studio.json).

| Scenario | Wall time (median) | LLM time | Turns | Tools |
|:---------|:------------------:|:--------:|:-----:|:------|
| Browse www.example.com | **6.24 s** | 5.02 s | 2 | webfetch |
| Browse Hackernews latest | **10.51 s** | 9.31 s | 2 | webfetch |

### Key Findings

1. **Dense 30B decode is 3–3.5× slower than Gemma 4 26B A4B MoE** (24.8 vs 87.6 tok/s @ 512). The MoE architecture (4B active per step) is the structural advantage — all 30B Granite params are loaded per token.

2. **Browse latency is mid-table** (6.24 s) — competitive with Gemma 4 31B-it (5.11 s) and well below the Qwen3.6 GGUF family (12–33 s range). Short output-token count per turn (15–30 tokens) keeps the loop tight despite the lower tok/s.

3. **No thinking overhead** — Granite 4.1 is a standard instruct model with no `<think>` channel. All tokens land in visible `content`.

4. **Apache 2.0 license** — fully permissive, no Gemma Terms / community license restriction.

5. **Tool-call correctness: 5/5.** LM Studio handles Granite 4.1's tool-call format natively.

---

## 🤖 Results: prithivMLmods/Qwen3.6-35B-A3B Aggressive Q6_K

**Date:** 2026-05-02
**Server:** lm-studio / LM Studio headless on port 1234, GGUF runtime. Loaded with `--identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --context-length 65536`. No parser flags required.
**Architecture:** Qwen3.6 MoE — 35B total, ~3B active, Q6_K GGUF.
**Raw JSON:** [`qwen36-35b-a3b-prithiv-aggressive/api-tool-test.json`](qwen36-35b-a3b-prithiv-aggressive/api-tool-test.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.79 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.98 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 4.27 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.60 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 5.79 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool arguments are well-formed JSON; model emits `run_command` with a `find | sort | head` pipeline for the agentic scenario. LM Studio handles the Qwen3 chat-template tool-call format natively.

#### Multi-turn agentic loop (3 turns, total 5.87 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.67 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 2.44 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.77 | `stop` | — final answer |

### Caveats

- LM Studio's GGUF runtime handles `<think>` and tool calls natively for this Qwen3 GGUF — no parser flags at load time.
- **Model key collision:** `lms load qwen3.6-35b-a3b-uncensored-aggressive` matches both prithivMLmods and HauhauCS models; use `--identifier` to pin the stable API id, and `-y` to select non-interactively (picks first alphabetically, which is the prithivMLmods model).

---

## 🤖 Results: Qwen3.6-35B-A3B 4-bit + z-lab/Qwen3.6-35B-A3B-DFlash drafter

**Date:** 2026-04-30
**Server:** dflash-mlx 0.1.4.1 (`pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'`) + three local patches: [`patch_dflash_mlx_serve.py`](../../../scripts/patches/patch_dflash_mlx_serve.py), [`patch_mlx_lm_match.py`](../../../scripts/patches/patch_mlx_lm_match.py), and (only for 0.1.0) [`patch_dflash_mlx_host.py`](../../../scripts/patches/patch_dflash_mlx_host.py). Started with `--host 0.0.0.0 --port 8098 --temp 0.0 --chat-template-args '{"enable_thinking":false}'`.
**Architecture:** mlx-community/Qwen3.6-35B-A3B-4bit target + z-lab/Qwen3.6-35B-A3B-DFlash drafter (block-diffusion verifier).
**Raw JSON:** [`qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json`](qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.84 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.88 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 2.23 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.68 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 6.08 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool calls are well-formed — JSON-encoded `arguments`, correct `function.name`, `type: "function"`, UUID `id`. Reasoning routed to `message.reasoning` (separate from `content`).

#### Multi-turn agentic loop (3 turns, total 5.9 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 2.39 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 1.43 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 2.09 | `stop` | — final answer |

The state-machine reset patch (`patch_mlx_lm_match.py`) is what unblocks turn 2 onward — without it, the second invocation of `match()` after a tool-call match terminal hits `KeyError: None`. The fix is `mlx_lm.generate.match()`'s state machine, not dflash-mlx-specific.

### Caveats

- **Greedy only.** `--temp 0.0` is the bench setting. Higher temperature reduces draft acceptance below 86%, eroding DFlash's win.
- **Disable thinking for tool-call benches.** `--chat-template-args '{"enable_thinking":false}'` keeps the model from emitting long `<think>` blocks before each tool call. Tool-call correctness unaffected, but bench is 2-4× faster per turn.
- **Server log telemetry** confirms DFlash is active: per-request lines like `122.3 tok/s | 81.2% accepted | 695 tokens` appear in `/tmp/dflash-mlx.log`.

---

## 🤖 Results: DavidAU/Qwen3.6-40B-Heretic Q6_K IMatrix on lm-studio

**Date:** 2026-05-03
**Server:** lm-studio / LM Studio headless on port 1234, GGUF runtime. Loaded with `--identifier qwen36-40b-davidau-heretic-q6k --context-length 131072`. No parser flags required.
**Architecture:** DavidAU dense **40B** Qwen3.6 derivative, Heretic abliteration, Q6_K IMatrix GGUF.
**Raw JSON:** [`qwen36-40b-davidau-heretic/api-tool-test.json`](qwen36-40b-davidau-heretic/api-tool-test.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 7.47 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 6.39 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 17.63 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 7.74 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 15.90 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Tool calls are well-formed across all scenarios. Dense 40B at 8.8–9.7 tok/s: single-call latencies are 5–8× slower than MoE siblings (prithivMLmods 1.60–5.79 s vs 6.39–17.63 s). LM Studio handles Qwen3 tool-call format natively.

#### Multi-turn agentic loop (3 turns, total 30.31 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 10.35 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 11.88 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 8.08 | `stop` | — final answer |

### Caveats

- Dense 40B at 8.8–9.7 tok/s is expected. Reload prithivMLmods Aggressive Q6_K (`lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --context-length 65536 -y`) when throughput matters.
- LM Studio memory guardrail must be set to `"off"` before loading this model (dense 40B + 131K context) — see `docs/current.md` launch shape for the full toggle recipe.
- Thinking mode is on by default; the model produces `<think>` reasoning before each tool call, contributing to latency but not blocking tool-call correctness.

---

## 🤖 Results: HauhauCS/Qwen3.5-35B-A3B-Uncensored-HauhauCS-Aggressive

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, GGUF runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Qwen3.5 MoE — 35B total, ~3B active (A3B), Q6_K GGUF, HauhauCS abliteration. 28.51 GB on disk.
**Raw JSON:** [`hauhaucs-qwen35-35b-a3b-aggressive/api-tool-test-lm-studio.json`](hauhaucs-qwen35-35b-a3b-aggressive/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.60 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.43 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 1.90 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.59 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 2.99 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Fast, correct tool selection. Parallel tool calling demonstrated in scenario 3.

#### Multi-turn agentic loop (3 turns, total 5.37 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.71 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 2.20 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.46 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`hauhaucs-qwen35-35b-a3b-aggressive/agent-tool-test-lm-studio.json`](hauhaucs-qwen35-35b-a3b-aggressive/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | **5.21 s** | 4.0 s | 5.19–5.24 s | 2 | `webfetch` | 22,806 |
| Browse Hackernews latest topic | **10.54 s** | 9.34 s | 10.24–10.85 s | 2 | `webfetch` | 27,594 |

Per-turn breakdown (browse, sample): turn 1 prefill 11,294 tokens → 1.92 s (42 output tokens), turn 2 prefill 11,415 → 2.11 s (61 output tokens). Reasoning tokens: ~51 per run (minimal thinking prelude).

### Key Findings

1. **Competitive browse at 5.21 s** — faster than the Hermes 4 70B (15.63 s) and Huihui 4bit (15.72 s), slightly slower than Dolphin Venice (6.62 s). The MoE A3B architecture keeps latency low despite the GGUF format.

2. **5/5 API pass rate** — correct tool selection, valid JSON arguments, `finish_reason: tool_calls`. Parallel multi-tool calling works in scenario 3.

3. **No patches needed.** LM Studio's GGUF runtime handles Qwen3.5 MoE tool-call format natively. Downloaded via `hf_hub_download` (Q6_K file only); `lms get` resolves the repo but fails at download.

4. **Context requirement:** default LM Studio context (4096) is too small for OpenCode's system prompt (~11,294 tokens). Must reload with `--context-length 32768`.

---

## 🤖 Results: AITRADER/Huihui-Qwen3.5-35B-A3B-abliterated-4bit-MLX

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, MLX runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Qwen3.5 MoE — 35B total, ~3B active (A3B), 4-bit MLX safetensors, Huihui abliteration. 19 GB on disk / 19.02 GiB loaded.
**Raw JSON:** [`huihui-qwen35-35b-a3b-4bit/api-tool-test-lm-studio.json`](huihui-qwen35-35b-a3b-4bit/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 1.61 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.11 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 1.72 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 1.29 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 1.33 | `tool_calls` | `list_directory` |

**Pass rate: 5/5.** Fast and correct. Smallest model on disk (19 GB).

#### Multi-turn agentic loop (3 turns, total 4.94 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.40 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 1.63 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.91 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`huihui-qwen35-35b-a3b-4bit/agent-tool-test-lm-studio.json`](huihui-qwen35-35b-a3b-4bit/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | 15.72 s | 14.49 s | 15.32–16.12 s | 2 | `webfetch` | 22,836 |
| Browse Hackernews latest topic | 21.38 s | 20.16 s | 20.10–22.65 s | 2 | `webfetch` | 27,648 |

Per-turn breakdown (browse, sample): turn 1 prefill 11,292 tokens → 12.55 s (43 output tokens), turn 2 prefill 11,415 → 1.53 s (86 output tokens). Turn 1 dominates — the first prefill is slow despite MoE sparsity.

### Key Findings

1. **Best API-level agentic loop at 4.94 s** among all models benchmarked on lm-studio here (narrowly beating HauhauCS Qwen3.5 Q6_K at 5.37 s). The 4-bit MLX format is faster at single-token decode than the GGUF.

2. **Agent loop slower than API loop** by 3×. Turn 1 in OpenCode takes 12.55 s for 43 output tokens — roughly 3.4 tok/s for the first turn. The 11K-token system-prompt prefill likely dominates cold-start time on the 4-bit MLX path.

3. **Smallest footprint** — 19 GiB loaded vs 27+ GiB for other models, leaving headroom on the 96 GB Mac Studio for future parallel serving.

---

## 🤖 Results: mlx-community/Dolphin-Mistral-24B-Venice-Edition-mlx-8Bit

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, MLX runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Mistral 24B dense decoder, 8-bit MLX, Dolphin Venice uncensored fine-tune. 23 GB on disk / 23.34 GiB loaded.
**Raw JSON:** [`dolphin-mistral-24b-venice-mlx/api-tool-test-lm-studio.json`](dolphin-mistral-24b-venice-mlx/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 4.51 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.35 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 5.20 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 3.66 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 3.86 | `tool_calls` | `list_directory` |

**Pass rate: 5/5.** High variance on single-tool scenarios (1.35–5.20 s) — Mistral dense 24B decode speed varies by output token count.

#### Multi-turn agentic loop (3 turns, total 6.55 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.57 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 2.98 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.99 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`dolphin-mistral-24b-venice-mlx/agent-tool-test-lm-studio.json`](dolphin-mistral-24b-venice-mlx/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | 6.62 s | 5.38 s | 6.02–7.21 s | 2 | `webfetch` | 24,116 |
| Browse Hackernews latest topic | 21.04 s | 19.8 s | 19.63–22.45 s | 2 | `webfetch` | 28,784 |

Per-turn breakdown (browse, sample): turn 1 prefill 11,966 tokens → 2.47 s (41 output tokens), turn 2 prefill 12,052 → 2.29 s (43 output tokens). No thinking tokens — Dolphin Venice is a non-thinking model.

### Key Findings

1. **Second-fastest browse (6.62 s)** among newly benchmarked models, after HauhauCS Qwen3.5 Q6_K (5.21 s). Dense Mistral 24B is competitive with MoE models for short-output agent tasks.

2. **Warmup penalty is large** — first (warmup) run was 38.77 s, measured runs settled at 6–7 s. Initial model-weight cold-start on MLX path.

3. **No thinking overhead** — Dolphin Venice is not a thinking model; every token is visible content. This simplifies tool-call parsing but limits multi-step reasoning quality.

---

## 🤖 Results: moot20/Dolphin3.0-R1-Mistral-24B-MLX-8bits

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, MLX runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Mistral 24B dense decoder with DeepSeek R1 distillation, 8-bit MLX, Dolphin 3.0 uncensored fine-tune. 23 GB on disk / 23.34 GiB loaded.
**Raw JSON:** [`dolphin3-r1-mistral-24b-mlx/api-tool-test-lm-studio.json`](dolphin3-r1-mistral-24b-mlx/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 3.37 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.31 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 1.39 | `tool_calls` | `search_web` (partial — only 1 of 2 tools) |
| 4 | Multi-tool (list + read + write) | 1.29 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 1.27 | `tool_calls` | `list_directory` |

**Pass rate: 5/5.** Note: scenario 3 emits only `search_web` (not the requested `search_web + read_file` pair). Tool call is valid but parallel calling is incomplete.

#### Multi-turn agentic loop (3 turns, total 5.12 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 1.47 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 2.53 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 1.12 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`dolphin3-r1-mistral-24b-mlx/agent-tool-test-lm-studio.json`](dolphin3-r1-mistral-24b-mlx/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | 7.5 s | 6.28 s | 6.18–8.83 s | 2–3 | `webfetch` | 30,159 |
| Browse Hackernews latest topic | 34.52 s | 4.42 s | 10.10–58.93 s | 7 | `webfetch`, `bash` | 12,735 |

### Key Findings

1. **High search variance** — p5 10.1 s vs p95 58.93 s. One measured run took 58.93 s (12 agent turns, 7 webfetch + bash loops). The other took 10.1 s (2 turns). The R1 distillation causes the model to pick agentic strategies inconsistently.

2. **Bash-looping behavior** — on the 58.93 s search run, the model called `bash` (curl/grep shell pipelines) 4+ times and `webfetch` multiple times instead of a clean webfetch + summary. This wastes tokens and produces shallow results.

3. **LLM time vs wall time gap** — on the bad search run, wall=58.93 s but llm=0 s. This indicates the session expired or was cut short on the opencode side (tool execution time exceeded session). A clean 2-turn run showed wall=10.1 s / llm=8.83 s which is reasonable.

4. **Not recommended for search-heavy agent tasks.** Browse is acceptable (7.5 s median). Dolphin Venice is more consistent.

---

## 🤖 Results: HauhauCS/Qwen3.6-27B-Uncensored-HauhauCS-Balanced

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, GGUF runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Qwen3.6 dense 27B, Q8_K_P GGUF, HauhauCS Balanced uncensored. 31.96 GB on disk / 29.77 GiB loaded.
**Raw JSON:** [`hauhaucs-qwen36-27b-balanced/api-tool-test-lm-studio.json`](hauhaucs-qwen36-27b-balanced/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 5.86 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 6.99 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 11.50 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 6.31 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 24.52 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Correct tool selection, but latency is high (5.86–24.52 s single-call). The agentic reasoning scenario at 24.52 s generates a longer thinking block. Dense 27B all-params-active path, Q8 precision.

#### Multi-turn agentic loop (3 turns, total 25.70 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 11.25 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 9.36 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 5.09 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`hauhaucs-qwen36-27b-balanced/agent-tool-test-lm-studio.json`](hauhaucs-qwen36-27b-balanced/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | 11.16 s | 9.94 s | 9.87–12.46 s | 2 | `webfetch` | 22,773 |
| Browse Hackernews latest topic | 28.91 s | 27.68 s | 17.95–39.88 s | 2–3 | `webfetch` | 33,908 |

Per-turn breakdown (browse, sample): turn 1 prefill 11,288 tokens → 4.57 s (32 output tokens), turn 2 prefill 11,397 → 6.66 s (62 output tokens). Reasoning tokens: ~38 per run.

### Key Findings

1. **Dense Q8 is slow.** At 11.16 s browse and 28.91 s search, this is the second-slowest of the new models (after Hermes 4 70B search). All 27B params are active per token (no MoE), and Q8 is the largest quant of the models tested.

2. **Tool correctness is high** — 5/5 API pass with parallel multi-tool calling (scenario 3). Thinking tokens (~38) are generated but short — the balanced tuning suppresses excessive reasoning.

3. **Download note:** Q8_K_P is a custom quant label — `lms get` cannot resolve it. Use `hf_hub_download` directly for the specific `Qwen3.6-27B-Uncensored-HauhauCS-Balanced-Q8_K_P.gguf` filename.

---

## 🤖 Results: lmstudio-community/Hermes-4-70B-MLX-6bit

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, MLX runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Llama 70B dense decoder, 6-bit MLX, NousResearch Hermes 4 instruction/tool-use fine-tune. 53 GB on disk / 53.41 GiB loaded.
**Raw JSON:** [`hermes-4-70b-mlx-6bit/api-tool-test-lm-studio.json`](hermes-4-70b-mlx-6bit/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 7.86 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 2.44 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 4.54 | `tool_calls` | `search_web`, `read_file` |
| 4 | Multi-tool (list + read + write) | 2.26 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 4.68 | `tool_calls` | `run_command` |

**Pass rate: 5/5.** Correct tool selection and well-formed arguments. Latency range (2.26–7.86 s) reflects token-count variation — dense 70B decode.

#### Multi-turn agentic loop (3 turns, total 13.34 s)

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 5.97 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 5.28 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 2.10 | `stop` | — final answer |

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`hermes-4-70b-mlx-6bit/agent-tool-test-lm-studio.json`](hermes-4-70b-mlx-6bit/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | 15.63 s | 14.39 s | 13.07–18.20 s | 3 | `webfetch` (×2) | 33,302 |
| Browse Hackernews latest topic | 79.98 s | 78.74 s | 74.44–85.53 s | 6 | `bash` (×8), `webfetch` | 73,208 |

Per-turn breakdown (browse, sample): 3 turns at 3.87 s / 3.24 s / 9.84 s — the model webfetches twice before summarizing (visiting the site twice). Search: 6 turns using bash shell pipelines (`curl`, `grep`) plus one webfetch — a slower, less reliable approach than direct webfetch.

### Key Findings

1. **Browse is mid-table (15.63 s)** — comparable to Huihui 4bit (15.72 s) but 3 turns instead of 2 (model double-fetches example.com). Dense 70B Llama is slower per token than MoE models.

2. **Search is worst in class (79.98 s)** — the model defaults to bash shell pipelines (`curl | grep`) to search Hackernews instead of using webfetch directly. This generates 8+ bash calls, high token counts (73K total), and slow convergence. Hermes 4 was likely trained to use tool-use-as-coding, not webfetch-first strategies.

3. **Large disk footprint** — 53 GiB loaded; only fits on the 96 GB Mac Studio alongside 1–2 small models. Significantly larger than the 35B A3B alternatives (19–30 GiB).

4. **Warmup penalty** — first browse run (warmup) was 117 s; measured runs settled at 13–18 s. Same MLX cold-start pattern as Huihui.

---

## 🤖 Results: heni86/magnum-v4-72b_mlx-4bit

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, MLX runtime. Loaded with `--context-length 32768 -y`. No parser flags required.
**Architecture:** Qwen2 72B dense decoder, 4-bit MLX, Magnum roleplay fine-tune (Anthracite/MoralityIsAMyth). 38 GB on disk / 38.11 GiB loaded.
**Raw JSON:** [`magnum-v4-72b-mlx-4bit/api-tool-test-lm-studio.json`](magnum-v4-72b-mlx-4bit/api-tool-test-lm-studio.json)

### API-Level Tool Calling (5-tool harness)

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 5.59 | `stop` | (none) |
| 2 | Single tool (command) | 1.84 | `stop` | (none) |
| 3 | Multi-tool (search + read) | 3.65 | `stop` | (none) |
| 4 | Multi-tool (list + read + write) | 1.88 | `stop` | (none) |
| 5 | Agentic reasoning ("Find the largest file in /tmp") | 1.87 | `stop` | (none) |

**Pass rate: 0/5.** The model answers all scenarios from training memory without calling any tools. `finish_reason: stop` on every single-call scenario.

#### Multi-turn agentic loop (harness-provided tool context — 3 turns, 12.44 s)

The 3-turn agentic loop harness provides explicit tool call results in the conversation history, which the model then continues; this produces valid `tool_calls` on turn 1 and turn 2. This is not a genuine tool-calling capability — it is the model continuing a pre-seeded conversation format.

### OpenCode End-to-End Agent Benchmark (2026-05-05)

Raw JSON: [`magnum-v4-72b-mlx-4bit/agent-tool-test-lm-studio.json`](magnum-v4-72b-mlx-4bit/agent-tool-test-lm-studio.json).

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | ⛔ 12.03 s | 10.81 s | 8.24–15.81 s | 2 | (none) | 22,367 |
| Browse Hackernews latest topic | ⛔ 16.13 s | 14.8 s | 15.78–16.48 s | 2–4 | (none) | 27,863 |

The model responds in 2–4 turns but never calls `webfetch`. It answers "Browse www.example.com" by describing example.com from training memory (correct content, not live data). Search: describes Hackernews topics from training knowledge.

### Key Findings

1. **⛔ Does not call tools.** magnum-v4-72b is fine-tuned exclusively for creative roleplay (Magnum project) — the tool-use RLHF signal was not included. The model ignores tool definitions and answers from training memory.

2. **Qualitative output is fluent.** The prose responses to browse/search prompts are coherent and topically relevant — just not live data. Magnum is a quality roleplay model, not a tool-use model.

3. **Not suitable for agentic workflows.** Skip for any task requiring real-time web access, file operations, or multi-step tool-call loops.

---

## 🤖 Results: mradermacher/Midnight-Miqu-70B-v1.5-GGUF

**Date:** 2026-05-05
**Server:** lm-studio / LM Studio headless on port 1234, GGUF runtime. Model was loaded but immediately failed tool-call requests.
**Architecture:** Mixtral 8x7B derivative with Mistral tokenizer, Q4_K_M GGUF, Midnight-Miqu roleplay fine-tune.
**Raw JSON:** [`midnight-miqu-70b-q4km/api-tool-test-lm-studio.json`](midnight-miqu-70b-q4km/api-tool-test-lm-studio.json)

### Result

**⛔ SKIP — tool calling architecturally unsupported.**

All `/v1/chat/completions` requests with `tools[]` return HTTP 400:

```
Error rendering prompt with jinja template: "Only user and assistant roles are supported!"
```

The model's jinja chat template only supports `user` and `assistant` message roles. The tool-call harness injects tool definitions via a `system` role message (the OpenAI tools API standard), which this template rejects outright. Normal chat (no tools) works fine.

### Key Findings

1. **Chat-template limitation is architectural.** Midnight-Miqu is based on Mixtral 8x7B (December 2023), predating the OpenAI tool-call API conventions. The model was fine-tuned for creative/roleplay use, not agentic tool use.

2. **No workaround available.** Overriding the chat template would require a custom jinja template that maps tool definitions into the user/assistant conversation — non-trivial and unreliable.

3. **Disk cost.** 41 GB Q4_K_M GGUF downloaded at 95% disk utilization. Remove if disk is needed: `lms rm midnight-miqu-70b-v1.5` or `rm ~/.lmstudio/models/mradermacher/Midnight-Miqu-70B-v1.5-GGUF/`.

4. **CRACK 122B (model 9) skipped** — disk dropped to 23 GB free after downloading Midnight-Miqu (41 GB). The CRACK 122B model (69.6 GB) could not fit; skip threshold in task instructions was 80 GB.
