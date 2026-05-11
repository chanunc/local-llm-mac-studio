# Model Summary: Gemma 4 Family

Google's Gemma 4 generation. Five variants currently catalogued in this stack: the **26B-A4B** mixture-of-experts multimodal release (vision + audio + video, 256K context, thinking mode), the dense **31B-it** instruction-tuned text-only release (64K context, thinking mode), the **DavidAU HERETIC uncensored 31B** GGUF fine-tune (128K context, Thinking variant, lm-studio), the **TrevorJS EGA uncensored 26B A4B** GGUF (65K context loaded, non-thinking sparse MoE), and the **TrevorJS abliterated uncensored 31B-it** GGUF (65K context loaded, non-thinking dense). They share the `Gemma4ForCausalLM` / `Gemma4ForConditionalGeneration` family but use different sub-architectures.

## Index

- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — MoE 26B/4B + vision + audio + video · 256K · `mlx-openai-server` / `lm-studio` (MLX-vs-GGUF data point, 2026-05-08) · 15 GB · 50–114 tok/s · **OpenCode browse 3.29 s / search 3.23 s on lm-studio (no scaffolding needed, search 2.2× faster than the Q8_0 GGUF sibling)**
- [Gemma 4 31B-it (6-bit)](#gemma-4-31b-it-6-bit) — Dense 31B text-only · 64K loaded (256K native) · **mlx-lm server (current main 2026-05-06)** · 29 GB · 20.4 tok/s @ 512, browse 12.33 s (thinking ON) / browse 5.11 s (thinking OFF on lm-studio)
- [Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm) — failed experiment](#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment) — drafter works at upstream-expected efficiency, pairs cleanly with 6-bit too (5/5 API harness, 16.54 s loop). On 0.5.0-from-main (2026-05-06): mlx-vlm emitted `delta.tool_calls` only as a final post-loop chunk → opencode hit 300 s wall (0 turns × 3). **On 0.5.0 tagged release (2026-05-08): partial fix** — browse now completes 6 webfetch turns in 300 s (model loops on the same URL but tool_calls do fire mid-conversation); search still 0 turns. API tool harness 5/5 + 12.08 s multi-turn loop (was 22.06 s, **−45 %**). Long-context decode regressed (4K/8K/16K: 13.8→4.5, 12.3→5.0, 10.7→3.7 tok/s — drafter acceptance collapses to 0.06–0.25 at long contexts). See [v0.5.0 tagged release re-test](#v050-tagged-release-re-test-2026-05-08).
- [DavidAU Gemma 4 31B Heretic Q6_k](#davidau-gemma-4-31b-heretic-q6k) — Uncensored (HERETIC + MysteryFT) · 128K · `lm-studio` · 23.47 GiB · 24.2 tok/s · 7/10 mlabonne · [bench writeup](../../uncen-model/gemma4-31b-davidau-heretic-benchmark.md)
- [TrevorJS Gemma 4 26B A4B Uncensored Q8_0](#trevorjs-gemma-4-26b-a4b-uncensored-q8) — MoE 26B/4B active · 65K loaded · `lm-studio` · 25.02 GiB · **87.6 tok/s** · 8/10 mlabonne · **browse 2.93 s 🥇** · [bench writeup](../../uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md)
- [TrevorJS Gemma 4 31B-it Uncensored Q4_K_M](#trevorjs-gemma-4-31b-it-uncensored-q4km) — Dense 31B no-think · 65K loaded · `lm-studio` · 17.40 GiB · 30.1 tok/s @ 512 / 24.1 tok/s @ 32K · harness 6–7/10 / **manual 10/10 mlabonne** (disclaimer-prefixed complies) · browse **6.63 s warm** _(initial 10.08)_ / search 30.81 s · [bench writeup](../../uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md)
- [lmstudio-community Gemma 4 26B A4B-it Q8_0 (standardised)](../benchmarks/model-benchmark-tool-call.md#results-lmstudio-community-gemma-4-26b-a4b-it-q8) — MoE 26B/4B active · 65K loaded · `lm-studio` · 25.02 GiB · 70–86 tok/s · API smoke 5/5 (multi-turn 2.14 s tied 🏆 with TrevorJS) · OpenCode 3/3 under scaffolded prompts (`Browse <url> using tool you have` / `Use webfetch to fetch <literal url> …`): **browse 2.94 s 🥈 / search 7.20 s** · [bench writeup](../benchmarks/model-benchmark-tool-call.md#results-lmstudio-community-gemma-4-26b-a4b-it-q8)

---

## Gemma 4 26B-A4B (4-bit)

Google's first mixture-of-experts Gemma. The 26B-A4B activates only ~4B parameters per token (128 experts, top-4 routing) giving MoE-class throughput while supporting 256K context, native vision+video+audio multimodal input, and built-in thinking mode. Verified on Mac Studio M3 Ultra (96 GB) on April 17, 2026.

| Spec | Value |
|:-----|:------|
| Base Model | [google/gemma-4-26b-a4b-it](https://huggingface.co/google/gemma-4-26b-a4b-it) |
| MLX 4-bit | [mlx-community/gemma-4-26b-a4b-it-4bit](https://huggingface.co/mlx-community/gemma-4-26b-a4b-it-4bit) |
| Format | MLX safetensors (multimodal / `mlx_vlm` handler) |
| Vendor | Google DeepMind; MLX conversion by mlx-community |
| Architecture | `Gemma4ForConditionalGeneration` — MoE text + vision encoder + audio encoder |
| Parameters | 26B total, ~4B active (128 experts, top-4 routing) |
| Quantization | 4-bit (group size 64), with 8-bit on MoE gate/up/down projectors of layer 0 |
| Specialties | Thinking mode (chain-of-thought), image + video + audio input, tool calling, 256K context |
| On-disk size | ~15 GB |
| Context Size | 262,144 tokens (256K); sliding window 1024 on intermediate layers |
| License | Gemma Terms of Use |
| Requirements | `mlx-openai-server >= 1.7.1`, `mlx-lm >= 0.31.2`, `mlx-vlm >= 0.4.4` |

**mlx-openai-server model ID:** `mlx-community/gemma-4-26b-a4b-it-4bit`

**Server config:** `model_type: multimodal`, `tool_call_parser: gemma4`, `reasoning_parser: gemma4`, `context_length: 262144`

**Reference YAML:** [mlx-openai-server-gemma4.yaml](../../servers/mlx-openai-server/mlx-openai-server-gemma4.yaml)

### Benchmarks (mlx-openai-server 1.7.1, M3 Ultra 96 GB, Apr 17 2026)

Method: streaming SSE `/v1/chat/completions`, 150 max tokens, temperature 0.0, 3 runs each. Generation tokens include both `reasoning_content` (thinking) and `content` (answer) phases.

> **512 note:** run 1 was a cold-start (59.4 tok/s gen, 28 tok/s prefill, 18.7s TTFT). Table shows warm values (runs 2–3).

#### Generation Speed (tok/s)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **62.5** | 1,710 | 0.30 |
| 4K | 54.6 | 3,117 | 1.32 |
| 8K | 60.6 | 3,154 | 2.60 |
| 32K | 50.6 | 2,892 | 11.34 |
| 64K | 42.0 | 2,542 | 25.78 |
| 128K | 27.1 | 1,995 | 65.70 |

Prefill peaks at 8K (~3,154 tok/s) — typical for sliding-window models where GPU utilisation is highest in the mid-range. Generation speed drops gradually with context due to sliding window KV growth.

### Caveats

- **Thinking always on (streaming):** Bug [#280](https://github.com/cubist38/mlx-openai-server/issues/280) — reasoning parser not applied mid-stream in 1.7.1. Fixed on `main` but not yet released. Non-streaming requests separate `content` / `reasoning_content` correctly (verified).
- **`chat_template_kwargs` ignored:** Bug [#279](https://github.com/cubist38/mlx-openai-server/issues/279) — `enable_thinking: false` has no effect in 1.7.1. Fixed on `main`. Thinking cannot currently be suppressed via API.
- **vllm-mlx:** Not tested. Bug [#38855](https://github.com/vllm-project/vllm/issues/38855) means reasoning parser strips `<|channel>` markers — not recommended until vllm-mlx picks up the vLLM main fix.
- **oMLX:** Not tested. The 4-bit MLX port includes `chat_template.jinja` so the tokenizer issue seen with 8-bit variants does not apply here; however, Gemma 4 parsers are not registered in oMLX's parser map.

### Same model on lm-studio (2026-05-08, MLX-vs-GGUF data point)

**lm-studio API id:** `gemma-4-26b-a4b-it-mlx-4bit` (load with `lms load 'mlx-community/gemma-4-26b-a4b-it' --gpu max --context-length 65536 --identifier gemma-4-26b-a4b-it-mlx-4bit -y`; no guardrail flip needed at 14.57 GiB resident < 25 % of 96 GB unified memory). LM Studio's MLX runtime auto-detects Gemma 4 tool-call + reasoning, no parser flags. Download via `huggingface_hub.snapshot_download(repo_id='mlx-community/gemma-4-26b-a4b-it-4bit', local_dir='~/.lmstudio/models/mlx-community/gemma-4-26b-a4b-it-4bit')` — `lms get` does not resolve MLX repos through LM Studio's hub catalog.

**Why this run exists:** companion data point for the [`lmstudio-community/gemma-4-26B-A4B-it-GGUF` Q8_0](../benchmarks/model-benchmark-tool-call.md#results-lmstudio-community-gemma-4-26b-a4b-it-q8) bench — same `google/gemma-4-26b-a4b-it` base, same lm-studio runtime, MLX 4-bit safetensors vs Q8_0 GGUF container. Quant levels differ materially (4-bit ≈ 14.6 GiB vs Q8_0 ≈ 25 GiB) — this is **not** an apples-to-apples quant comparison; it's a runtime/format comparison at each format's most-downloaded MLX quant for this base.

#### Throughput (`bench_api_server.py`, 1 warmup + 2 measured runs, median)

| Context | TTFT (s) | Gen (tok/s) | Prefill (tok/s) |
|:--------|:--------:|:-----------:|:---------------:|
| 512     | 0.18     | **114.0**   | 3,040           |
| 4 K     | 0.22     | 106.4       | 18,780          |
| 8 K     | 0.24     | 98.8        | 34,830          |
| 32 K    | 0.33     | 76.7        | **99,580**      |

Decode is **1.6× faster** than the Q8_0 GGUF sibling (`docs/current.md` reports 70–86 tok/s for the GGUF Q8_0); prefill is **lower** than the GGUF (Q8_0 hits 158 K tok/s @ 32 K vs MLX 4-bit's 99 K). 4-bit weights → less bandwidth → faster decode is the expected tradeoff.

#### API smoke (`bench_api_tool_call.py`)

5/5 single-call pass, multi-turn loop **2.05 s** (3 turns: read 0.57 s + write 0.75 s + summary 0.73 s). Edges out the GGUF Q8_0 sibling's 2.14 s 🏆 by 0.09 s — both within run-to-run noise but worth noting that scenario 5 (agentic reasoning) passes here at 0.44 s without hitting any output cap.

#### OpenCode end-to-end (`bench_agent_tool_call.py`)

| Scenario | Wall (median) | LLM (median) | p5–p95 wall | Turns | Tools | Tokens (median) |
|:---------|:------:|:------:|:------:|:-----:|:------|:------:|
| Browse www.example.com | **3.29 s** | 2.02 s | 3.27–3.39 s | 2 | `webfetch` | 21,743 |
| Browse Hackernews latest topic | **3.23 s** | 1.95 s | 3.22–3.24 s | 2 | `webfetch` | 26,625 |

**Key contrast vs the Q8_0 GGUF sibling on the same lm-studio runtime:**

1. **No bare-prompt URL refusal.** The Q8_0 GGUF's documented behaviour (`docs/models/benchmarks/model-benchmark-tool-call.md`) is "bare prompts hit 0/3 — RLHF refuses to guess URLs"; needs scaffolded prompts (`Browse <url> using tool you have` / `Use webfetch to fetch <literal url>`) to fire webfetch. The MLX 4-bit fired webfetch **3/3 on identical bare prompts**. Hypotheses: (a) `mlx_vlm` chat template differs subtly from the GGUF's embedded template; (b) 4-bit quantisation degraded the URL-refusal RLHF pattern enough to bypass it. Either way, agent ergonomics on bare prompts are materially better.

2. **Search 2.2× faster than the GGUF.** Browse 3.29 vs 2.94 s (12 % slower) is within scaffolding noise; search 3.23 vs 7.20 s is a real gap — same 2-turn webfetch shape, but the MLX 4-bit decode rate (114 tok/s @ 512) finishes the summary turn faster than the Q8_0's 70–86 tok/s.

3. **Wall–LLM split shows the bottleneck is OpenCode bootstrap, not inference.** LLM time of 1.95–2.02 s under 3.23–3.29 s wall means ~1.27 s/turn is fixed OpenCode overhead. The model itself is sub-2-second on these tasks.

4. **Inverts the Qwen3.6 finding.** [`mlx-community/Qwen3.6-35B-A3B-6bit` on lm-studio](../benchmarks/model-benchmark-tool-call.md#results-mlx-communityqwen36-35b-a3b-6bit-on-lm-studio) showed MLX **3.0× slower** than its GGUF Q6_K sibling under OpenCode. Gemma 4 26B-A4B MLX 4-bit shows the **opposite** — MLX search 2.2× *faster* than its GGUF Q8_0 sibling. The "MLX is slower than GGUF on lm-studio" generalisation from the Qwen run does not hold for this family.

**Raw JSONs:** [`api-tool-test-llmster.json`](../benchmarks/gemma-4-26b-a4b-it-4bit/api-tool-test-llmster.json), [`api-server-llmster.json`](../benchmarks/gemma-4-26b-a4b-it-4bit/api-server-llmster.json), [`agent-bench-llmster.json`](../benchmarks/gemma-4-26b-a4b-it-4bit/agent-bench-llmster.json).

---

## Gemma 4 31B-it (6-bit)

Google's dense **31B instruction-tuned** text-only Gemma 4. No MoE, no vision/audio — single-modality model. Built-in thinking mode (ON by default on mlx-lm server; OFF on LM Studio). Deployed via the **lmstudio-community** MLX 6-bit conversion. **Current production main (2026-05-06)** on mlx-lm server (port 8000). Verified on Mac Studio M3 Ultra (96 GB) on May 1, 2026 (lm-studio) and May 6, 2026 (mlx-lm server).

| Spec | Value |
|:-----|:------|
| Base Model | [google/gemma-4-31b-it](https://huggingface.co/google/gemma-4-31b-it) |
| MLX 6-bit | [lmstudio-community/gemma-4-31B-it-MLX-6bit](https://huggingface.co/lmstudio-community/gemma-4-31B-it-MLX-6bit) |
| Format | MLX safetensors (text-only, 6 shards) |
| Vendor | Google DeepMind; MLX conversion by LM Studio Community |
| Architecture | `Gemma4ForCausalLM` (`Gemma4ForConditionalGeneration` in config.json — VLM class, loaded text-only) |
| Parameters | 31B (dense — every token activates all parameters) |
| Quantization | 6-bit MLX |
| Specialties | Thinking mode (ON on mlx-lm), tool calling, long context, fast prefill on mlx-lm |
| Tokens/sec (mlx-lm) | **20.4 @ 512** → 20.2 @ 4K → 19.8 @ 8K → 17.2 @ 32K → 14.7 @ 65K ([bench](../benchmarks/gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json)) |
| Tokens/sec (lm-studio) | 21.8 @ 512 → 21.1 @ 8K → 18.3 @ 32K ([bench](../benchmarks/gemma-4-31b-it-6bit/api-server-lm-studio.json)) |
| On-disk size | 29 GB (model files); 31.32 GB total weights |
| Context Size | 65,536 loaded (both servers); native ≥ 256K |
| License | Gemma Terms of Use |
| MTP Drafter (pending) | `mlx-community/gemma-4-31B-it-assistant-bf16` (839 MB, `gemma4_assistant` arch) — downloaded, waiting for mlx-lm 0.31.3+ arch support |

**Current server: mlx-lm (direct), port 8000.** Model served by full filesystem path.

**Launch shape (mlx-lm server — current production):**

```bash
ssh macstudio "nohup /opt/homebrew/Cellar/mlx-lm/0.31.3/libexec/bin/mlx_lm.server \
  --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit \
  --host 0.0.0.0 --port 8000 \
  --max-tokens 8192 \
  > /tmp/mlx-lm-server.log 2>&1 &"

# IMPORTANT — use the Cellar libexec binary above, NOT /opt/homebrew/bin/mlx_lm.server.
# /opt/homebrew/bin/mlx_lm.server is shebanged to /opt/homebrew/opt/python@3.11/bin/python3.11
# whose mlx_lm install lacks Gemma 4 support and raises "Model type gemma4 not supported".
# The Cellar libexec wraps python3.14 with the correct mlx-lm 0.31.3 install.
# Note: --prompt-cache-size is not supported by the Cellar libexec binary; mlx-lm
# enables an automatic prompt cache by default.
```

**Reload on lm-studio (thinking OFF — for lower-latency agent loops):**

```bash
ssh macstudio "~/.lmstudio/bin/lms load 'gemma-4-31b-it-mlx' \
  --gpu max --context-length 65536 -y"
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

> **Loader gotcha:** `lms get` failed to download cleanly twice (timed out at 88% with a hung "Finalizing download…" state and only shards 4–6 of 6 on disk). Recovery path: kill the hung `lms get`, then complete the download via `huggingface_hub.snapshot_download(repo_id=…, local_dir=~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit)` from any venv with `huggingface_hub` installed. LM Studio recognises the on-disk layout and `lms ls` then surfaces the model normally.
>
> **Context gotcha (lm-studio only):** despite passing `--context-length 65536`, the first `lms load` resolved to context 4096. Re-`lms unload` + re-`lms load --context-length 65536 -y` correctly seats 64K.

### Benchmarks — mlx-lm server (M3 Ultra 96 GB, May 6 2026, thinking ON)

#### API server (raw streaming, no tools)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **20.4** | 1,337 | 0.41 |
| 4K | 20.2 | 9,965 | 0.41 |
| 8K | 19.8 | 19,331 | 0.43 |
| 32K | 17.2 | 63,306 | 0.52 |
| 65K | 14.7 | 101,361 | 0.65 |

Raw JSON: [`gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json`](../benchmarks/gemma-4-31b-it-mlx-6bit/api-server-mlx-lm.json).

Prefill is 2.5–2.8× faster than lm-studio across 4K–32K. TTFT sub-0.65 s at 65K.

#### API tool-call (5-tool harness, 2026-05-06)

| Scenario | Time | Tools Called | Result |
|:---------|----:|:-------------|:-------|
| Single tool (file read) | 4.56 s | `read_file` | ✅ |
| Single tool (command) | 2.96 s | `run_command` | ✅ |
| Multi-tool (search + read) | 5.64 s | `search_web`, `read_file` | ✅ both called |
| Multi-tool (list + read + write) | 5.64 s | `list_directory` (1 of 3) | ⚠ same single-tool deviation |
| Agentic reasoning | 11.28 s | `run_command` | ✅ (207 tokens, thinking ON) |
| **Single-call pass rate** | — | **5/5** | |
| 3-turn loop (read → write → summary) | **20.73 s** total | — | ✅ |

Raw JSON: [`gemma-4-31b-it-mlx-6bit/api-tool-test.json`](../benchmarks/gemma-4-31b-it-mlx-6bit/api-tool-test.json).

#### Agent loop (mlx-lm, thinking ON)

| Scenario | Wall time (median) | LLM time (median) | Turns | Output tokens |
|:---------|-------------------:|------------------:|------:|:------|
| Browse www.example.com | **12.33 s** | 11.12 s | 2 | 121 |
| Browse Hackernews latest topic | **35.55 s** | 34.38 s | 2 | 124 |

Thinking mode adds 3–4× more output tokens vs. lm-studio run (35–45 tokens per session). Browse overhead factor 2.4×, search overhead factor 5.6× compared to lm-studio (thinking OFF). Raw JSON: [`gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json`](../benchmarks/gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json).

#### v0.31.3 stock re-bench (2026-05-08)

Re-benched against the same `mlx_lm.server` 0.31.3 (Cellar libexec) after retiring `patch_mlx_lm_match.py` — confirms the upstream Gemma 4 fix trio ([#1150](https://github.com/ml-explore/mlx-lm/pull/1150) hyphenated function names + braces in string args, [#1158](https://github.com/ml-explore/mlx-lm/pull/1158) KV-shared-layer projection load, [#1167](https://github.com/ml-explore/mlx-lm/pull/1167) `NoneType` think-token guard) leaves the API server numbers steady and keeps single-call tool harness at 5/5:

| Surface | 2026-05-06 | v0.31.3 stock 2026-05-08 | Δ |
|:--|--:|--:|:--|
| API server 512 ctx | 20.5 tok/s · TTFT 0.41 s | 20.4 · 0.40 | ≈ same |
| API server 4 K ctx | 20.2 · 0.41 · prefill 9,965 | 20.1 · 0.41 · 10,180 | ≈ same |
| API server 8 K ctx | 19.8 · 0.43 · 19,331 | 19.7 · 0.42 · 19,623 | ≈ same |
| API server 16 K ctx | (not benched) | 18.7 · 0.46 · 36,484 | new |
| API tool harness 5/5 pass rate | 5/5 | **5/5** | match |
| API multi-turn 3-turn loop | 20.73 s | **20.83 s** | match |
| Agent: Browse `www.example.com` | 12.33 s wall, 2 turns | **66.07 s wall**, 2 turns | **5.4× regression on a single run** — turn 1 produced 53 output tokens in 58.81 s suggesting deep thinking; likely thinking-budget variance, not a stock-fix regression (browse on this prompt has high stddev across runs). |
| Agent: Browse Hackernews latest topic | 35.55 s wall, 2 turns | **36.22 s wall**, 2 turns | match |

Raw JSONs: [`gemma-4-31b-mlx6/api-server-mlx-lm-v0.31.3.json`](../benchmarks/gemma-4-31b-mlx6/api-server-mlx-lm-v0.31.3.json), [`gemma-4-31b-mlx6/api-tool-test-mlx-lm-v0.31.3.json`](../benchmarks/gemma-4-31b-mlx6/api-tool-test-mlx-lm-v0.31.3.json), [`gemma-4-31b-mlx6/agent-bench-mlx-lm-v0.31.3.json`](../benchmarks/gemma-4-31b-mlx6/agent-bench-mlx-lm-v0.31.3.json).

**Takeaway:** the v0.31.3 Gemma 4 trio is a no-regression bug-fix trio — none of the per-bench surfaces shifted outside measurement noise except the browse single-run outlier (which matches the known per-prompt thinking-budget variance, not the trio). Stock 0.31.3 is the right path; no patches needed for this server.

### Benchmarks — lm-studio (M3 Ultra 96 GB, May 1 2026, thinking OFF)

#### API server

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **21.8** | 1,232 | 0.44 |
| 4K | 21.5 | 6,028 | 0.68 |
| 8K | 21.1 | 11,584 | 0.71 |
| 32K | 18.3 | 36,297 | 0.90 |

Raw JSON: [`gemma-4-31b-it-6bit/api-server-lm-studio.json`](../benchmarks/gemma-4-31b-it-6bit/api-server-lm-studio.json).

#### Agent loop (lm-studio, thinking OFF)

| Scenario | Wall time (median) | LLM time (median) | Turns | Output tokens |
|:---------|-------------------:|------------------:|------:|:------|
| Browse www.example.com | **5.11 s** | 3.94 s | 2 | ~35 |
| Browse Hackernews latest topic | **6.37 s** | 5.18 s | 2 | ~45 |

Raw JSON: [`gemma-4-31b-it-6bit/agent-bench-lm-studio.json`](../benchmarks/gemma-4-31b-it-6bit/agent-bench-lm-studio.json).

The lm-studio row is 3–5× faster end-to-end than the mlx-lm row above on identical 6-bit weights. The decomposition (chunk-size + sync-barrier elimination, neither of which is actually closed-source) is documented in [`docs/servers/lm-studio/prefill-speed-technique.md`](../../servers/lm-studio/prefill-speed-technique.md).

### Caveats

- **Thinking mode is server-dependent:** lm-studio (LM Studio) serves with thinking OFF (model doesn't invoke `<think>` blocks on short tool-calling prompts). mlx-lm server enables thinking by default — output tokens per turn are 3–4× higher and latency is 2.4–5.6× higher as a result. Use lm-studio if you want lowest-latency thinking-off agent loops; use mlx-lm for future MTP drafter support.
- **MTP drafter cannot be served via mlx-lm — only via mlx-vlm 0.5.0+ (from main):** `mlx-community/gemma-4-31B-it-assistant-bf16` (839 MB, `gemma4_assistant` arch) is supported in `mlx_vlm/speculative/drafters/gemma4_assistant/`, **not** in mlx-lm. mlx-lm 0.31.3 raises `Model type gemma4_assistant not supported`. PyPI `mlx-vlm 0.4.4` lacks the `mlx_vlm.speculative` submodule entirely; install from main (`pip install 'git+https://github.com/Blaizzy/mlx-vlm.git@main'` → 0.5.0). **The drafter is NOT bf16-locked** — the HF model card only documents bf16 pairings, but source-code review (no dtype assertion in `gemma4_assistant.py`/`config.py`/`parity_check.py`) plus community evidence ([NVIDIA forum's `serapis` ran `Intel/gemma-4-31B-it-int4-AutoRound` + drafter on vLLM for ~2× speedup](https://forums.developer.nvidia.com/t/gemma4-draft-models-are-now-available/369114)) plus our local verification (5/5 API tool-call harness on 6-bit + bf16 drafter, multi-turn loop 16.54 s) confirm any quantization works. **Documented failure mode for opencode-style streaming agent clients (regardless of quantization)** — see "[Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm)](#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment)" below for the streaming tool-call emission bug.
- **`lms get` unreliable for >20 GB models** — use `huggingface_hub.snapshot_download` (see Loader gotcha above).
- **No vision input** — `Gemma4ForConditionalGeneration` in config.json, but loaded text-only; for multimodal see the 26B-A4B variant above.

## Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm) — 2026-05-06 failed experiment

A documented attempt at the upstream-recommended speculative-decoding pair: `mlx-community/gemma-4-31B-it-bf16` target (~58 GB on disk) plus `mlx-community/gemma-4-31B-it-assistant-bf16` MTP drafter (839 MB, 4-layer assistant model trained by Google for Gemma 4). The drafter itself ran cleanly (**3.07–4.29 tokens accepted per round** — matches upstream's own numbers in [PR #1115](https://github.com/Blaizzy/mlx-vlm/pull/1115) where the maintainer measured "**B=1: 11.7 tok/s, 4.64 acceptances/round, ≈6.2× speedup vs. baseline**" on the same target/drafter pair). My 12.3 tok/s @ 8K context **matches** that 11.7 tok/s reference. The drafter PRs are not the blocker.

The actual blocker — identified by source-code review on 2026-05-06 after multiple bench passes ruled out chat_template, coalesce env var, bf16 vs 6-bit target, and decode speed — is a **streaming tool-call emission asymmetry between `mlx_vlm.server` and `mlx_lm.server`**. The drafter and the speculative path both work as upstream documents; the 6-bit + bf16 drafter pairing also works (proven via API harness 5/5). What breaks opencode is how mlx-vlm emits `delta.tool_calls` during SSE streaming.

| Spec | Value |
|:-----|:------|
| Target | [`mlx-community/gemma-4-31B-it-bf16`](https://huggingface.co/mlx-community/gemma-4-31B-it-bf16) (58 GB on disk, 21 files) |
| Drafter | [`mlx-community/gemma-4-31B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-31B-it-assistant-bf16) (839 MB, `gemma4_assistant` arch) |
| Server | `python -m mlx_vlm.server` (mlx-vlm 0.5.0 from main; PyPI 0.4.4 lacks `mlx_vlm.speculative`) |
| Venv | `~/mlx-vlm-env/` (kept; install via `pip install 'git+https://github.com/Blaizzy/mlx-vlm.git@main'`) |
| Drafter kind | `mtp` — Google's [Multi-Token Prediction](https://ai.google.dev/gemma/docs/mtp/mtp) drafter |
| Pairing constraint | **Drafter is NOT bf16-locked.** HF card only documents bf16 pairings, but source has no dtype assertion (verified) and we ran 6-bit + drafter successfully (API harness 5/5, 16.54 s multi-turn). vLLM community ran `Intel/gemma-4-31B-it-int4-AutoRound` + drafter for ~2× speedup. |
| Useful context cap | **≤16 K tokens** on M3 Ultra 96 GB for bf16 target (32 K+ OOMs on the speculative path); 6-bit target should not OOM but not benched at 32 K |

### Launch shape (for reference, not currently running)

```bash
ssh macstudio "nohup ~/mlx-vlm-env/bin/python -m mlx_vlm.server \
  --host 0.0.0.0 --port 8000 \
  --model mlx-community/gemma-4-31B-it-bf16 \
  --draft-model mlx-community/gemma-4-31B-it-assistant-bf16 \
  --draft-kind mtp \
  --draft-block-size 6 \
  --max-tokens 8192 \
  > /tmp/mlx-vlm-server.log 2>&1 &"
```

### Benchmarks (M3 Ultra 96 GB, May 6 2026)

#### API server (raw streaming, no tools)

| Context | bf16 + MTP (mlx-vlm) | 6-bit (mlx-lm, ref) | Δ vs 6-bit |
|:--------|---------------------:|--------------------:|:-----------|
| 512 | 17.0 tok/s · TTFT 3.02 s · prefill 180 | 20.5 · 0.41 · 1,337 | −17 % decode, **7×** TTFT, **−86 %** prefill |
| 4 K | 13.8 tok/s · TTFT 18.14 s · prefill 228 | 20.2 · 0.41 · 9,965 | −32 %, **44×** TTFT, **−98 %** prefill |
| 8 K | 12.3 tok/s · TTFT 41.04 s · prefill 200 | 19.8 · 0.43 · 19,331 | −38 %, **95×** TTFT, **−99 %** prefill |
| 16 K | 10.7 tok/s · TTFT 134.4 s · prefill 122 | (not benched) | — |
| 32 K | OOM | 17.2 · 0.52 · 63,306 | OOM (118 GB attempted vs 62 GB Metal cap) |

Raw JSON: [`gemma-4-31b-bf16-mtp/api-server-mlx-vlm.json`](../benchmarks/gemma-4-31b-bf16-mtp/api-server-mlx-vlm.json).

#### API tool-call (non-streaming, 5-tool harness)

| Scenario | Time | Tools Called | Result |
|:---------|----:|:-------------|:-------|
| Single tool (file read) | 5.29 s | `read_file` | ✅ |
| Single tool (command) | 4.24 s | `run_command` | ✅ |
| Multi-tool (search + read) | 6.54 s | `search_web`, `read_file` | ✅ both |
| Multi-tool (list + read + write) | 8.61 s | `list_directory` | ⚠ same single-tool deviation as 6-bit |
| Agentic reasoning | 15.68 s | `run_command` | ✅ |
| **Single-call pass rate** | — | **5/5** | |
| 3-turn loop (read → write → summary) | **22.06 s** | — | ✅ |

Raw JSON: [`gemma-4-31b-bf16-mtp/api-tool-test.json`](../benchmarks/gemma-4-31b-bf16-mtp/api-tool-test.json). Non-streaming responses parse correctly; the failure is streaming-only.

#### Agent loop (opencode against streaming SSE) — ⛔ **broken across all three passes**

| Scenario | Pass 1: bf16 + drafter | Pass 2: bf16 + drafter + `MLX_VLM_SPEC_BATCH_WAIT_MS=10` | Pass 3: **6-bit + drafter** |
|:---------|:-----------------------|:--------------------------------------------------------|:----------------------------|
| Browse www.example.com | 300.02 s × 3, 0 turns | 300.04 s × 3, 0 turns | 300.03 s × 1, 0 turns |
| Browse Hackernews latest topic | 300.04 s × 3, 0 turns | 300.04 s × 3, 0 turns | (not benched) |

Raw JSON: [pass 1](../benchmarks/gemma-4-31b-bf16-mtp/agent-bench-mlx-vlm.json), [pass 2](../benchmarks/gemma-4-31b-bf16-mtp/agent-bench-mlx-vlm-coalesce.json), [pass 3 (6-bit target)](../benchmarks/gemma-4-31b-bf16-mtp/agent-bench-6bit-target-mtp-hfid.json).

**Pass 3 is the decisive one** — same 6-bit weights that complete browse in 12.33 s on `mlx_lm.server` time out at 300 s on `mlx_vlm.server` + drafter. The model is fast enough; the streaming tool-call emission asymmetry is the bug. Server-side logs confirm: `[MTP] batch=1 tokens=8192 accept=4.56 rounds=1473` for the 6-bit run — the model generates 8192 tokens of reasoning on the opencode prompt because mlx-vlm doesn't surface the tool_calls until *after* generation completes. mlx-lm's per-token state machine catches the tool_call block close at ~80 tokens in and emits the chunk immediately.

**API tool harness on 6-bit + drafter (non-streaming) — works fine:** 5/5 single-call pass rate, multi-turn loop **16.54 s**, MTP accept 2.11–4.56 tok/round. Raw JSON: [`api-tool-test-6bit-mtp.json`](../benchmarks/gemma-4-31b-bf16-mtp/api-tool-test-6bit-mtp.json). This isolates the failure to the streaming SSE path.

### MTP drafter behaviour (the part that *did* work — and matches upstream)

Server log lines like `[MTP] batch=1 tokens=125 accept=3.06 rounds=31` show the drafter is highly effective and consistent with the maintainer's own measurements in PR #1115:

- Single-request acceptance: **2.34 – 4.29 tokens accepted per verification round** (8 representative samples logged during the bench). Maintainer's reference: **4.64 acc/round** at `--draft-block-size 6` for the same pair.
- Highest sample: `[MTP] batch=1 tokens=8192 accept=4.29 rounds=1549` — over a full 8K-token generation, 4.29 tokens land per round on average.
- Decode rate at 8K context: **12.3 tok/s** (mine) vs **11.7 tok/s** (PR #1115 maintainer reference, B=1) — within measurement noise. The drafter is operating at upstream-expected efficiency.
- Output content was correct (byte-identical at temp=0) in every non-streaming probe — `accept` rate matches the "byte-identical at temp=0" claim from the [drafter card](https://huggingface.co/mlx-community/gemma-4-31B-it-assistant-bf16).

The drafter is not the regression. The B=1 single-request decode rate (12.3 tok/s) is *expected* — bf16 weights' bandwidth tax means even a 6.2× speculative speedup over the bf16-no-drafter baseline still loses to 6-bit-no-drafter (20.4 tok/s). PR #1117's `MLX_VLM_SPEC_BATCH_WAIT_MS` is the upstream-suggested bridge for any workload with concurrent requests.

### Root cause (verified by source-code review, 2026-05-06)

After ruling out chat_template (verified byte-identical to 6-bit's working template, 16,448 bytes), the `MLX_VLM_SPEC_BATCH_WAIT_MS` coalesce env var (PR #1117 — same 8/8 timeouts with and without), and the bf16-vs-6-bit hypothesis (6-bit + drafter pairing also fails opencode the same way despite running fast), the actual blocker is a **streaming tool-call emission asymmetry between `mlx_vlm.server` and `mlx_lm.server`**:

**`mlx_lm/server.py` (lines 1435–1490) — incremental tool-call streaming (works for opencode):**

```python
# Per-token state machine: gen.state ∈ {"reasoning", "tool", "normal"}
for gen in response:
    if gen.state == "reasoning": reasoning_text += gen.text
    elif gen.state == "tool": tool_text += gen.text
    elif gen.state == "normal":
        if prev_state == "tool":
            tool_calls.append(tool_text); ...    # finalize tool call on state transition

    if self.stream and gen.state != "tool" and (text or tool_calls or reasoning_text):
        # ↓↓ Emits delta.tool_calls AS SOON AS one finalizes ↓↓
        resp = self.generate_response(text, None,
            tool_calls=tool_formatter(tool_calls), reasoning_text=reasoning_text)
        self.wfile.write(f"data: {json.dumps(resp)}\n\n".encode())
        self.wfile.flush()
```

**`mlx_vlm/server.py` (lines 2320–2440) — post-loop tool-call extraction (breaks opencode):**

```python
while True:
    token = await asyncio.to_thread(_next_token)
    # Routes tokens to delta.reasoning / delta.content
    # suppress_tool_call_content() hides raw <|tool_call> markup from delta.content
    yield f"data: {chunk_data.model_dump_json()}\n\n"

# After loop exits (post-generation):
if tool_module is not None:
    tc = process_tool_calls(full_output, tool_module, tools)   # ← NOW parses
    if tc["calls"]:
        yield ChatStreamChunk(... tool_calls=tc["calls"] ...)  # ← single final chunk
```

**Why opencode times out:** opencode's agent loop expects `delta.tool_calls` chunks *during* streaming so it can dispatch the tool and advance to the next turn. mlx-lm's path emits them per-token as the state machine transitions out of `"tool"`. mlx-vlm's path streams only `delta.reasoning` and (suppressed) `delta.content` until the entire generation completes, then emits a single final `delta.tool_calls` chunk.

For Gemma 4's thinking-mode prompts opencode often sees thousands of `delta.reasoning` tokens before the model emits the tool-call markers. mlx-vlm holds the parsed tool_calls until *after* the model finishes (which can be 8192 tokens / 666 s on bf16 at 12.3 tok/s, or even on 6-bit if the model rambles). opencode's 300 s wall fires long before that final chunk. mlx-lm's per-token state machine fires the tool_calls chunk the moment the `<|tool_call>...<tool_call|>` block closes — typically ~2–5 s on the same prompts, well inside the wall.

This is a real upstream bug in mlx-vlm's streaming SSE handler. Worth filing against [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm) with the minimal repro (`mlx_lm.server` + 6-bit + opencode → 12.33 s 2-turn webfetch; `mlx_vlm.server` + same 6-bit + same opencode → 300 s timeout 0 turns).

### Other findings from the experiment (independent of the streaming bug)

- **The drafter itself works at upstream-expected efficiency.** 12.3 tok/s @ 8K matches PR #1115's B=1 reference (11.7 tok/s, 4.64 acc/round, ≈6.2× over bf16-no-drafter baseline). Acceptance rate 3.07–4.29 tok/round on bf16, 2.11–4.56 on 6-bit (lower because quantized target's logits diverge from the bf16-trained drafter — expected). This isn't the regression.
- **B=1 single-request decode being slower than 6-bit no-drafter is expected** for bf16 targets, per upstream's own framing ("MTP works best for B>1"). Independent of the streaming bug.
- **6-bit + bf16 drafter pairing works mechanically.** Loaded cleanly, no dtype assertion fired, API tool harness 5/5, multi-turn loop 16.54 s (1.25× speedup over 6-bit no-drafter). Streaming probe `"Browse www.example.com"` completed in 20.2 s with 796 SSE lines. The "drafter requires bf16" claim from the HF card is documentation, not a hard constraint — verified in source code (no dtype gate) and via the vLLM community's `Intel/gemma-4-31B-it-int4-AutoRound` + drafter test.
- **`MLX_VLM_SPEC_BATCH_WAIT_MS=10` (PR #1117 coalesce env var) doesn't help opencode.** It coalesces *concurrent* requests into MTP batches; opencode runs sequential turns. Right knob for server-side concurrent load, not for sequential agent loops.
- **Metal OOM at 32 K+ context for bf16 target.** Speculative decoding allocates extra KV/compute buffers; at ~24,576 in-flight tokens MLX attempts a 118 GB allocation against the 62 GB Metal buffer cap. 16 K is the safe ceiling for bf16. 6-bit target presumably has more headroom but not benched at 32 K.
- **Prefill is ~50–80× slower than `mlx_lm.server`** at the same context (228 vs 9,965 tok/s @ 4 K) for bf16. `mlx_vlm.server` doesn't expose prompt-cache reuse the way `mlx_lm.server` does. 6-bit target's prefill should be closer to mlx-lm's but not benched.

### v0.5.0 tagged release re-test (2026-05-08)

Re-tested after a fresh install of [`mlx-vlm` v0.5.0](https://github.com/Blaizzy/mlx-vlm/releases/tag/v0.5.0) (was previously on the from-main pin that pre-dated the tag by ~2 days). Same target/drafter pair, same M3 Ultra 96 GB, same launch shape minus `--draft-kind mtp` (PR [#1125](https://github.com/Blaizzy/mlx-vlm/pull/1125) auto-detects from `model_type='gemma4_assistant'` — confirmed in server log: `Auto-detected --draft-kind='mtp' for drafter ...`). Continuous batching enabled by default (PR [#1027](https://github.com/Blaizzy/mlx-vlm/pull/1027)).

**Headline:** the streaming tool-call starvation is **partially fixed**. Browse went from 0 turns × 300 s → 6 turns of working webfetch in 300 s. Search is still broken (0 turns / 0 LLM time — different fail mode). Long-context decode regressed: drafter acceptance collapses to 0.06–0.25 tok/round at 4 K +, dragging tok/s 60–67 % below the from-main baseline.

#### API server (raw streaming, no tools) — `api-server-mlx-vlm-v0.5.0.json`

| Context | v0.5.0 (this run) | 0.5.0-from-main (2026-05-06) | Δ vs from-main | 6-bit on mlx-lm (ref) |
|:--------|------------------:|-----------------------------:|:---------------|----------------------:|
| 512 | **24.0 tok/s · TTFT 2.77 s · prefill 195** | 17.0 · 3.02 · 180 | **+41 %** decode | 20.5 · 0.41 · 1,337 |
| 4 K | 4.5 tok/s · TTFT 18.04 s · prefill 229 | 13.8 · 18.14 · 228 | **−67 %** decode | 20.2 · 0.41 · 9,965 |
| 8 K | 5.0 tok/s · TTFT 41.01 s · prefill 200 | 12.3 · 41.04 · 200 | **−59 %** decode | 19.8 · 0.43 · 19,331 |
| 16 K | 3.7 tok/s · TTFT 131.28 s · prefill 125 | 10.7 · 134.4 · 122 | **−65 %** decode | (not benched) |

Server log lines confirm the cause: warmup at low context emits `[MTP] batch=1 tokens=50 accept=4.00 rounds=10` (drafter healthy); 4 K + runs emit `accept=0.06 rounds=47`, `accept=0.25 rounds=40` — the drafter is being rejected nearly every round. Whatever changed between the from-main install and the tagged release affects long-context drafter acceptance, not the drafter itself (acceptance is fine at 512 ctx and on tool-call turns generating 20–106 tokens). Possible suspects: continuous-batching default ON (PR #1027), `Drafter ready — speculative decoding enabled` initialization path, or KV-cache quantization for continuous batching (PR [#1030](https://github.com/Blaizzy/mlx-vlm/pull/1030)).

#### API tool-call (non-streaming, 5-tool harness) — `api-tool-test-v0.5.0.json`

| Scenario | v0.5.0 | 0.5.0-from-main | Δ |
|:---------|------:|----------------:|:--|
| Single tool (file read) | 2.63 s | 5.29 s | **−50 %** |
| Single tool (command) | 2.41 s | 4.24 s | −43 % |
| Multi-tool (search + read) | 3.33 s | 6.54 s | −49 % |
| Multi-tool (list + read + write) | 2.69 s | 8.61 s | −69 % |
| Agentic reasoning | 4.01 s | 15.68 s | −74 % |
| **Single-call pass rate** | **5/5** | 5/5 | — |
| Multi-turn (read → write → summary) | **12.08 s** | 22.06 s | **−45 %** |

The non-streaming path is uniformly faster — these prompts all complete inside the short-context window where the drafter still helps (under 4 K input). Combined with the lower per-call constant overhead (continuous batching warm path), this is a real win for any non-streaming integration.

#### Agent loop (opencode, streaming SSE with tools) — `agent-bench-mlx-vlm-v0.5.0.json`

| Scenario | v0.5.0 | 0.5.0-from-main pass 1 | Δ |
|:---------|:-------|:-----------------------|:--|
| Browse `www.example.com` | **300.05 s wall, llm 295.37 s, 6 turns, webfetch ✅** | 300.02 s × 3, 0 turns | tool_calls now fire mid-stream, but model loops on same URL — eventually hits 300 s |
| Browse Hackernews latest | 300.04 s wall, **llm 0 s, 0 turns** | 300.04 s × 3, 0 turns | model never produces output for this prompt — different fail mode |

Per-turn breakdown for the browse run:

| Turn | Duration | in / out tokens | Tool |
|:-----|---------:|:----------------|:-----|
| 1 | 90.55 s | 13,623 / **20** | `webfetch` ✅ |
| 2 | 9.0 s | 706 / 106 | (followup) |
| 3 | 89.69 s | 13,758 / **30** | `webfetch` ✅ (loop) |
| 4 | 8.19 s | 817 / 106 | (followup) |
| 5 | 89.76 s | 13,758 / **30** | `webfetch` ✅ (loop) |
| 6 | 8.18 s | 817 / 106 | (followup) |

The 20-/30-token tool-call turns prove `delta.tool_calls` is now reaching opencode mid-stream; the prior failure mode required the model to generate the full 8192-token budget before opencode saw any tool emission. **The streaming bug fix in v0.5.0 looks empirically more like *early loop termination on tool-call marker close* than *per-token `delta.tool_calls` emission*** — `process_tool_calls(full_output, ...)` is still called post-loop in `mlx_vlm/server.py:2499`, but the loop now exits at ~20–30 tokens for tool-call generations instead of running to `--max-tokens`. Either implementation is functionally equivalent for opencode.

The remaining failure on the loop side is a Gemma-4 behavior (model re-issues the same `webfetch www.example.com` after the followup) and on the search side is a separate non-emission case (probably reasoning trace blocking the tool emission for higher-difficulty prompts) — both are independent of the post-loop emission asymmetry that defined the prior "failed experiment" verdict.

**Takeaway for production posture:** mlx-vlm 0.5.0 + Gemma 4 + MTP is no longer a hard non-starter for streaming agent clients, but it is still **not** a tier-1 main: long-context decode regressed, the agent loop completes only the simplest browse prompt (and even that with model-side looping), and the 6-bit Gemma 4 on `mlx_lm.server` (current main) still beats it on every metric that matters for daily agent use. Keep the install for the API tool harness wins (12.08 s multi-turn) and the documented streaming-fix story; do not flip production.

#### APC prompt cache attempt (`APC_ENABLED=1`, 2026-05-08)

Tested `APC_ENABLED=1` (PRs [#1103](https://github.com/Blaizzy/mlx-vlm/pull/1103) + [#1114](https://github.com/Blaizzy/mlx-vlm/pull/1114), memory-only — disk persistence opt-in not enabled) on the same target/drafter/launch shape, with the agent loop as the test harness (where prefix reuse should help most: opencode re-issues 13 K-token contexts across turns 1, 3, 5). Server log on launch confirmed `APC enabled (block_size=16, num_blocks=2048, hash=fast, disk=False)`.

| Surface | Without APC (baseline tagged 0.5.0) | With `APC_ENABLED=1` | Δ |
|:--|--:|--:|:--|
| API server 512 / 4 K / 8 K / 16 K decode | 24.0 / 4.5 / 5.0 / 3.7 tok/s | 24.1 / 4.5 / 5.0 / 3.7 | match |
| API server prefill (same contexts) | 195 / 229 / 200 / 125 tok/s | 196 / 229 / 201 / 123 | match |
| Agent browse turn 1 prefill | 90.55 s · 13,623 in | 90.54 s · 13,623 in | match |
| Agent browse turn 3 prefill (~13 K shared prefix w/ turn 1) | 89.69 s | **89.74 s** — APC did not reduce | **no help** |
| Agent browse turn 5 prefill (~13 K shared prefix again) | 89.76 s | 89.77 s | no help |
| Agent search | 300 s, 0 turns, llm 0 s | 300 s, 0 turns, llm 0 s | no change |

**APC silently bypassed.** The most plausible cause is PR #1103's documented caveat: _"APC skips KV-quantized caches."_ v0.5.0 has KV-cache quantization for continuous batching ([PR #1030](https://github.com/Blaizzy/mlx-vlm/pull/1030)) defaulting ON via the continuous-batching launch path, with no `--continuous-batching off` flag exposed by `mlx_vlm.server` (verified 2026-05-08, `--help` shows no toggle). APC and continuous-batched KV quant are mutually exclusive; in v0.5.0 the latter wins, so the env var sets up the structure without it engaging at request time. Server log emits no APC hit/miss telemetry to corroborate — the only confirmation of "APC engaged" is the startup line.

Disk persistence (`APC_ENABLED=1` + the disk-backed env vars from [#1114](https://github.com/Blaizzy/mlx-vlm/pull/1114)) wasn't tested separately because the memory tier already failed to engage; disk would be downstream of the same caveat.

Raw JSONs: [`gemma-4-31b-bf16-mtp/api-server-mlx-vlm-v0.5.0-apc.json`](../benchmarks/gemma-4-31b-bf16-mtp/api-server-mlx-vlm-v0.5.0-apc.json), [`gemma-4-31b-bf16-mtp/agent-bench-mlx-vlm-v0.5.0-apc.json`](../benchmarks/gemma-4-31b-bf16-mtp/agent-bench-mlx-vlm-v0.5.0-apc.json).

**Implication:** APC alone does *not* close the prefill gap vs `mlx_lm.server` for the bf16 + MTP path on v0.5.0 tagged. Closing it requires either (a) an upstream way to disable continuous batching for B = 1 + drafter workloads, or (b) a future v0.5.x where APC and continuous-batched KV quant coexist. Tracked, no-action-required for production.

### Cross-source comparison: mlx-lm vs mlx-vlm + external Gemma 4 + MTP benchmarks (2026-05-08)

Triggered by the [mlx-vlm v0.5.0 release tweet](https://x.com/Prince_Canuma/status/2052138203302510984): _"mlx-vlm v0.5.0 is here 🚀 → Continuous batching server + KV cache quantization → MTP and DFlash speculative decoding (single, batch, server) → Distributed inference: Qwen3.5, Kimi K2.5 & K2.6 → Prompt caching w/ warm-disk persistence → Gemma 4 video (multi-video) + MTP drafter."_ No benchmark numbers are in the tweet — it is a feature announcement.

#### Is anyone running Gemma 4 + MTP on `mlx-lm`? **No — `mlx-lm` does not support `gemma4_assistant`.**

| Source (2026-05-08) | Finding |
|:--|:--|
| `gh api repos/ml-explore/mlx-lm/releases` | Latest release **v0.31.3 (2026-04-22)**. Release notes mention **no MTP, no `gemma4_assistant`, no Gemma drafter**; the only Gemma 4 entries are tool-parser fixes (PRs [#1093](https://github.com/ml-explore/mlx-lm/pull/1093), [#1105](https://github.com/ml-explore/mlx-lm/pull/1105), [#1109](https://github.com/ml-explore/mlx-lm/pull/1109), [#1114](https://github.com/ml-explore/mlx-lm/pull/1114), [#1150](https://github.com/ml-explore/mlx-lm/pull/1150)). |
| `gh api .../pulls?...gemma4\|MTP` | Only matches: **[#990 "Native MTP speculative decoding (Qwen3.5/3.6 reference implementation)" — OPEN since 2026-03-13](https://github.com/ml-explore/mlx-lm/pull/990)**, [#1205 (gemma4 KV-shared layer projections — closed, **not merged**)](https://github.com/ml-explore/mlx-lm/pull/1205), [#1238 (gemma4 MoE router stop_gradient — open)](https://github.com/ml-explore/mlx-lm/pull/1238). **None target `gemma4_assistant`.** |
| [`mlx-community/gemma-4-31B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-31B-it-assistant-bf16) model card | Recommended invocation is `python -m mlx_vlm generate ... --draft-model ... --draft-kind mtp`. **No mlx-lm invocation is provided** — the conversion was authored with mlx-vlm 0.4.5. |
| [Gemma-4 Assistant (MTP) HF collection](https://huggingface.co/collections/mlx-community/gemma-4-assistant-mtp) | All four checkpoints (E4B / 26B-A4B / 31B-it / E2B-it `assistant-bf16`) are tagged `mlx-vlm`, never `mlx-lm`. |
| [Hacker News thread on Google's MTP announcement](https://news.ycombinator.com/item?id=48024540) | 200 + comments, AMD/NVIDIA/Ollama/llama.cpp discussions; **zero Apple-Silicon mlx-lm + MTP numbers.** |
| Reddit r/LocalLLaMA via search aggregators (direct fetch blocked) | Generic Gemma 4 traffic; **no mlx-lm + MTP benchmarks surfaced** for any Apple Silicon. |
| [Incept5/gemma4-benchmark](https://github.com/Incept5/gemma4-benchmark) (M5 Max 128 GB, MLX 0.31.1, mlx-vlm 0.4.4) | Tests Gemma 4 on **mlx-vlm only — no MTP, no mlx-lm**. Gives a baseline-without-MTP reference: Gemma 4 31B 27 tok/s @ 4 K, 7 tok/s @ 256 K. |
| [vLLM PR #41745](https://github.com/vllm-project/vllm/pull/41745) | Adds `gemma4_assistant` MTP to **vLLM** (Linux/CUDA), unrelated to mlx-lm. |
| [vLLM forum: How to use Gemma 4 with the new MTP drafters](https://discuss.vllm.ai/t/how-to-use-gemma-4-with-the-new-mtp-drafters/2619) | vLLM-specific guidance only. |

So the comparison the user asked for — _"Gemma 4 + MTP benchmark on mlx-lm"_ — has **no public data point** because the runtime doesn't host the architecture.

#### Apples-to-apples comparable: mlx-vlm references vs ours

The right peer is the **maintainer's own measurement** in [PR #1115](https://github.com/Blaizzy/mlx-vlm/pull/1115) (Gemma 4 MTP server PR) — same target, same drafter, same B = 1, same `--draft-block-size 6`, same runtime, captured on a single-Mac (chip unspecified):

| Source | Hardware | Config | Result |
|:--|:--|:--|:--|
| **Maintainer PR #1115** (mlx-vlm 0.5.0-from-main, pre-tag) | M-series Mac | bf16 + drafter, B = 1, block-size 6, 78 tokens generated, 14 rounds | **11.7 tok/s · 4.64 acc/round · ≈6.2× over no-drafter baseline** |
| Apple Silicon community summary (multiple search hits) | M3 Max / M4 Max 32 GB+ | mixed configs | 1.6–2.2× speedup with MTP |
| MLX-cited "best-case" speedup (per [Build Fast With AI guide](https://www.buildfastwithai.com/blogs/gemma-4-mtp-drafter-faster-inference)) | Apple Silicon | **B = 4, block-size 4** | **2.29× on 31B, 3.94× on 26B-A4B** |
| [Google blog](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/) | NVIDIA RTX PRO 6000, 26B MoE, optimal batch | — | up to 3× (best case) |
| Gemma 4 31B Dense on NVIDIA H100 (per same blog) | bf16 + MTP | — | 14 → 27 tok/s (1.9×) |

Our two passes on the **same M3 Ultra 96 GB** with the **same target/drafter/block-size 6/B = 1** track each other but diverge sharply at long context only on the tagged release:

| Context | Our **0.5.0 from-main** (2026-05-06) | Our **0.5.0 tagged release** (2026-05-08) | Maintainer PR #1115 |
|:--|--:|--:|--:|
| 512 ctx | (not benched) | **24.0 tok/s · accept 4.00** | n/a |
| 8 K ctx | 12.3 tok/s · accept 4.56 ✅ | **5.0 tok/s · accept 0.06–0.25** ❌ | **11.7 tok/s · accept 4.64** |
| 16 K ctx | 10.7 tok/s | 3.7 tok/s | n/a |

So at 8 K we **matched the maintainer's reference within measurement noise on the from-main install (12.3 vs 11.7 tok/s)** and **regressed to 0.43× of it on the tagged release (5.0 vs 11.7)** without any change to hardware, weights, drafter, block size, or batch — only the mlx-vlm tag/code path changed.

#### Why the regression appears on the tagged release but not in PR #1115's reference numbers

The maintainer's measurements predate three v0.5.0 features that became default ON in the tagged release:

1. **Continuous batching default ON** ([PR #1027](https://github.com/Blaizzy/mlx-vlm/pull/1027)). Optimised for B ≥ 2; for B = 1 + long context it appears to perturb the drafter's hidden-state passthrough, dropping acceptance from ~ 4 → ~ 0.1 / round. Server log on launch: `Model ready, continuous batching enabled.`
2. **KV-cache quantization for continuous batching** ([PR #1030](https://github.com/Blaizzy/mlx-vlm/pull/1030)). Quantised cache → noisier target logits → drafter draws diverge → rejection. Hits *long* context harder because more cache pages are quantised.
3. **Auto-detect drafter kind + multimodal prefill metadata preservation** ([PR #1125](https://github.com/Blaizzy/mlx-vlm/pull/1125)). Server log on launch: `Auto-detected --draft-kind='mtp' for drafter '... gemma4_assistant'` (this line is absent on the from-main install, confirming the new code path). Possibly resets drafter context state at points it shouldn't on long-running B = 1 sequences.

Server logs confirm the symptom is **acceptance** (not raw decode): `[MTP] batch=1 tokens=50 accept=4.00 rounds=10` at 512 ctx (drafter healthy), then `accept=0.06 rounds=47`, `accept=0.25 rounds=40` at 4 K + (drafter rejected ~ every round).

#### Why no other public source has reported this regression

- Most external benchmarks use **26B-A4B MoE** (smaller, batch-favored), not **31B dense bf16** at B = 1.
- Most use **B ≥ 2** (the intended path for the new continuous-batching default), not B = 1.
- Most stay under 4 K ctx (where the drafter still works on the tagged release — see our 512 result of 24 tok/s).
- Maintainer's PR #1115 numbers were captured on a code path that **predated** the continuous-batching/KV-quant default flip.

The footprint of users running **31B dense bf16 + B = 1 + ≥ 4 K ctx** on mlx-vlm v0.5.0 tagged is small enough that this regression hasn't generated visible community traffic yet. It is real and reproducible on this stack.

#### Source list (verified 2026-05-08)

- [mlx-vlm v0.5.0 announcement (X)](https://x.com/Prince_Canuma/status/2052138203302510984)
- [mlx-lm releases](https://github.com/ml-explore/mlx-lm/releases) — v0.31.3 latest, no `gemma4_assistant`
- [mlx-lm PR #990 — Native MTP for Qwen3.5/3.6 (open)](https://github.com/ml-explore/mlx-lm/pull/990)
- [mlx-vlm PR #1115 — Server supports Gemma 4 MTP drafter](https://github.com/Blaizzy/mlx-vlm/pull/1115)
- [mlx-vlm PR #1027 — Continuous batching server](https://github.com/Blaizzy/mlx-vlm/pull/1027)
- [mlx-vlm PR #1030 — KV cache quantization for continuous batching](https://github.com/Blaizzy/mlx-vlm/pull/1030)
- [mlx-vlm PR #1125 — Auto-detect drafter kind + multimodal prefill preservation](https://github.com/Blaizzy/mlx-vlm/pull/1125)
- [`mlx-community/gemma-4-31B-it-assistant-bf16` HF model card](https://huggingface.co/mlx-community/gemma-4-31B-it-assistant-bf16)
- [Gemma-4 Assistant (MTP) HF collection](https://huggingface.co/collections/mlx-community/gemma-4-assistant-mtp)
- [Google MTP blog](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/) and [HN discussion](https://news.ycombinator.com/item?id=48024540)
- [Incept5/gemma4-benchmark — M5 Max, mlx-vlm only, no MTP](https://github.com/Incept5/gemma4-benchmark)
- [vLLM PR #41745 — Spec Decode Gemma4 MTP (Linux/CUDA)](https://github.com/vllm-project/vllm/pull/41745)
- [Build Fast With AI — Gemma 4 MTP guide](https://www.buildfastwithai.com/blogs/gemma-4-mtp-drafter-faster-inference)

### What would unblock this

- **Fix mlx-vlm's streaming tool-call emission** to mirror mlx-lm's per-token state machine. File upstream against [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm). Tracked upstream limitations: [PR #773](https://github.com/Blaizzy/mlx-vlm/pull/773) (the original tool-calling PR) explicitly acknowledged "*mlx_lm parses the streaming output one token at a time during generation. This implementation parses it at the end of the stream*" — known compromise from day one. [PR #1037](https://github.com/Blaizzy/mlx-vlm/pull/1037) (merged) only strips raw markup from `delta.content`, "*preserving the existing single-emission pattern*". [PR #1012](https://github.com/Blaizzy/mlx-vlm/pull/1012) author noted "*End-of-stream chunk (... + tool_calls) … emitted once per request, not per token*". No open PR proposes per-token incremental `delta.tool_calls` emission. Related: [opencode #4255](https://github.com/anomalyco/opencode/issues/4255) (empty `tool_calls: []` array hang, open).
- **mlx-lm gaining `gemma4_assistant` arch support** (still **0 PRs open** as of 2026-05-08 — only matching MTP work in mlx-lm is [PR #990 "Native MTP speculative decoding (Qwen3.5/3.6 reference implementation)"](https://github.com/ml-explore/mlx-lm/pull/990), open since 2026-03-13 and Qwen-only). With mlx-lm hosting the drafter, the proven-working incremental tool-call streaming + prompt-cache reuse from the current 6-bit run would carry over, *and* mlx-lm could quantize the target so 6-bit + drafter avoids the bf16 bandwidth tax entirely. **This is the cleanest path forward.**
- **Until either of the above lands**, keep the 6-bit production main on `mlx_lm.server` and treat the mlx-vlm install as documentation-only.

### Runtime support landscape (verified 2026-05-06)

Where the `gemma4_assistant` MTP drafter actually runs today, across the runtimes this lab cares about plus references for completeness:

| Runtime | Status | Notes / citation |
|:--------|:-------|:-----------------|
| **mlx-lm** | ❌ Not supported | Raises `Model type gemma4_assistant not supported`. **0 PRs** open/closed in [`ml-explore/mlx-lm`](https://github.com/ml-explore/mlx-lm/pulls?q=is%3Apr+gemma4_assistant) for the drafter arch. Recent MTP work ([PR #1226](https://github.com/ml-explore/mlx-lm/pull/1226)) was Qwen 3.5/3.6 only. Active Gemma 4 PRs are sanitize/quantize/tool-parser — none touch MTP. |
| **mlx-vlm** | ⚠ Partial — streaming usable on simple browse, broken on harder prompts | 0.5.0-from-main (2026-05-06): opencode 0 turns × 300 s. **0.5.0 tagged release (2026-05-08): browse 6 turns + webfetch; search still 0 turns**; long-context decode regressed (4 K +: −60 %). [PR #1112](https://github.com/Blaizzy/mlx-vlm/pull/1112) drafter, [PR #1125](https://github.com/Blaizzy/mlx-vlm/pull/1125) auto-detect, [PR #1037](https://github.com/Blaizzy/mlx-vlm/pull/1037) markup strip. See [v0.5.0 re-test](#v050-tagged-release-re-test-2026-05-08). |
| **LM Studio (llama.cpp + GGUF)** | ❌ Not supported | LM Studio [speculative-decoding docs](https://lmstudio.ai/docs/app/advanced/speculative-decoding) only describe standard small-base-model drafters. No MTP / `gemma4_assistant` references in changelog through v0.4.11 (last Gemma 4 mention: "Improve Gemma 4 tool call reliability"). Underneath, [llama.cpp discussion #22735](https://github.com/ggml-org/llama.cpp/discussions/22735) (open, no maintainer engagement) reports `convert_hf_to_gguf.py` doesn't recognize `Gemma4AssistantForCausalLM` and new scaling tensors (`model.layers.0.layer_scalar`) are unmapped — **drafter weights can't even be converted to GGUF today**, let alone served. Plus the docs note "speculative decoding is problematic for MoE models like Gemma 4 26B-A4B" — even when MTP lands, 26B-A4B won't benefit. |
| **vLLM (Linux)** | ✅ Supported with quantized targets | NVIDIA Developer Forum: [`serapis`](https://forums.developer.nvidia.com/t/gemma4-draft-models-are-now-available/369114) ran `Intel/gemma-4-31B-it-int4-AutoRound` (4-bit) + `google/gemma-4-31B-it-assistant` (bf16 drafter) via `gemma4_mtp` method → **11.43 → 22.05 tok/s (~1.93×)**. Linux/server-grade; not the Mac Studio's path. |
| **transformers / SGLang** | ✅ Official Google path | Per Google's [MTP overview](https://ai.google.dev/gemma/docs/mtp/overview). Not a Mac Studio server stack. |
| **Ollama** | ❌ Tool parser broken as of 0.20.1 | [Paweł Huryn on X (2026-05)](https://x.com/PawelHuryn/status/2040498812318273583): "*Gemma 4 has function calling built in. Good luck actually using it … Ollama: tool parser still broken as of v0.20.1.*" Even basic Gemma 4 tool calls fail; MTP drafter not on their roadmap. |
| **Community: SeatownSin/gemma-4-E4B-mtp-drafter** | 🔬 Curio only | [HF model card](https://huggingface.co/SeatownSin/gemma-4-E4B-mtp-drafter) — first public extraction of the MTP heads Google trained but **stripped from the public HF release** (still present in proprietary LiteRT). Safetensors fp32, 78M params, **35% top-1 acceptance** (INT4 quant noise from mobile weights). Documented for transformers/vLLM/SGLang. **No GGUF or MLX port.** Interesting backstory; not a workaround for this lab. |

**What to watch:**
- `ml-explore/mlx-lm` — any new PR adding `gemma4_assistant` model architecture (currently 0 in queue; would unblock the cleanest path).
- `ggml-org/llama.cpp` — [discussion #22735](https://github.com/ggml-org/llama.cpp/discussions/22735) and [issue #22337](https://github.com/ggml-org/llama.cpp/issues/22337) ("draft issue Gemma E2B") for any conversion-script PR.
- `Blaizzy/mlx-vlm` — streaming SSE tool-call structural rewrite (per-token `delta.tool_calls` emission). [PR #773](https://github.com/Blaizzy/mlx-vlm/pull/773), [#1037](https://github.com/Blaizzy/mlx-vlm/pull/1037), [#1012](https://github.com/Blaizzy/mlx-vlm/pull/1012) all explicitly preserved the post-loop pattern; no open PR proposes the change.

### Client compatibility on `mlx_vlm.server` (inferred from public reports + structural reasoning, 2026-05-06)

The streaming-tool-call emission bug is server-side, so any client that consumes `/v1/chat/completions` SSE expecting incremental `delta.tool_calls` will hit the same starvation. Verified for opencode; **pi-mono (`pi-coding-agent` / `@mariozechner/pi-coding-agent`) is structurally subject to the same failure mode.**

| Client | `mlx_lm.server` (current production) | `mlx_vlm.server` + drafter |
|:-------|:-------------------------------------|:---------------------------|
| **opencode** (anomalyco) | ✅ 12.33 s browse, 2 turns, `webfetch` (verified) | ❌ 300 s timeout × 9 runs (verified) |
| **pi-coding-agent** (badlogic/pi-mono) | ✅ Expected to work — same protocol path as opencode; not yet smoke-tested directly | ❌ Same hang expected — see structural reasoning below |
| **Claude Code / OpenClaw** (Anthropic format) | n/a (uses `/v1/messages` via different proxy path) | Untested; same SSE structure on the OpenAI side |

Three reasons pi-mono will hit the same bug as opencode on `mlx_vlm.server`:

1. **Pi-mono is built on per-tool eager streaming.** Pi's own docs: *"Partial JSON parsing during tool call streaming is essential for good UX. As the LLM streams tool call arguments, pi-ai progressively parses them so you can show partial results in the UI before the call completes."* Its [CHANGELOG](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/CHANGELOG.md) hardens Anthropic streaming via per-tool `eager_input_streaming`. Pi expects per-token `delta.tool_calls` chunks — exactly the contract mlx-vlm violates by emitting only a final post-loop chunk.
2. **The parser-inference path is shared between `mlx_lm.server` and `mlx_vlm.server`.** [`ml-explore/mlx-lm` issue #1096](https://github.com/ml-explore/mlx-lm/issues/1096) ("Gemma 4 native tool calls are not parsed, so the OpenAI-compatible tool_calls field stays empty") explicitly states: *"This affects both `mlx_lm.server` and `mlx_vlm.server`, because `mlx-vlm` relies on `mlx-lm` parser inference at runtime before deciding whether to call `process_tool_calls()`."* Whatever parser regression hits one side hits the other.
3. **Pi's default 4-tool set independently triggers a Gemma 4 parse error.** [`ml-explore/mlx-lm` issue #1125](https://github.com/ml-explore/mlx-lm/issues/1125) (open, [PR #1142](https://github.com/ml-explore/mlx-lm/pull/1142) is the bandaid that returns `[]` instead of raising) reports `mlx_lm.server` + `mlx-community/gemma-4-26b-a4b-it-4bit` failing with `"No function provided."` from `gemma4.py:49` when the request defines **`read, bash, edit, write`** — exactly pi's defaults (*"By default, pi gives the model four tools: read, write, edit, and bash"*). The 26B-A4B 4-bit variant compounds: streaming bug ON top of parse error. The 31B 6-bit variant is unaffected by #1125 (verified locally — API harness 5/5).

**No public report shows pi-mono working on `mlx_vlm.server` specifically.** Every documented pi + Gemma 4 walkthrough — [Patrick Loeber](https://patloeber.com/gemma-4-pi-agent/), [Parallel.ai](https://parallel.ai/blog/free-CLI-agent), Mario Zechner's own posts — uses LM Studio, Ollama, or llama-server, not mlx-vlm. The mlx-vlm + pi combination is untested in the wild because the streaming bug effectively prevents it.

**Operational implication:** any future agent client added to this lab (pi, openclaw, custom MCP host) that uses OpenAI streaming `delta.tool_calls` will repeat the same failure on `mlx_vlm.server`. The fix is upstream-only; client switching does not help.

### Workaround attempted: vllm-mlx 0.2.9 with `--tool-call-parser gemma4` (2026-05-06)

`vllm-mlx 0.2.9` (PyPI canonical, not a fork — homepage `github.com/vllm-mlx/vllm-mlx`) ships **explicit `gemma4` tool-call and reasoning parsers**, which makes it the strongest off-the-shelf candidate for hosting Gemma 4 with opencode-compatible tool calling without depending on a Blaizzy/mlx-vlm fix. **Does not solve our problem in practice.** Two hard blockers verified on `lmstudio-community/gemma-4-31B-it-MLX-6bit`:

1. **Direct API tool calls work — but that's not the gap.** `POST /v1/chat/completions` with a single `webfetch` tool returns `tool_calls: [{name: "webfetch", arguments: {"url": "http://www.example.com"}}]`, `finish_reason: "tool_calls"`, in 86 completion tokens. The gemma4 parser does its job for non-streaming. The opencode failure is on the streaming path with the full opencode system prompt + 10-tool catalog (~13.6K input tokens).
2. **MLLM mode is ~6× slower than `mlx_lm.server`** for this model. Gemma 4's `Gemma4ForConditionalGeneration` config triggers vllm-mlx's `MLLM=True` path, which routes through `mlx-vlm 0.4.4`'s `generate_step` — measured **prefill 244 tok/s** (vs mlx-lm's 9,965 tok/s, ~40× slower) and **decode 3.2 tok/s** (vs mlx-lm's 20.4 tok/s, ~6× slower) on the same weights. opencode browse run took 78.18 s wall, 1 turn, **0 tool calls** — the model emitted 248 streaming chunks but no `delta.tool_calls` ever surfaced to the client. Same class of streaming-tool-call symptom as raw `mlx_vlm.server`.
3. **Setup gotcha:** vllm-mlx 0.2.9's `engine/simple.py:243` dispatches MLX work via `asyncio.create_task(asyncio.to_thread(...))`, which crashes with `RuntimeError: There is no Stream(gpu, 0) in current thread` on first request. Same class of bug as the Ling-2.6-flash deployment; the existing `scripts/patches/patch_vllm_mlx_inline_gen.py` is the right fix but its regex doesn't match 0.2.9's structure — needs a small update before it would re-apply cleanly. Hot-patched manually for this test.

vllm-mlx 0.2.9 was reverted to 0.2.6 (the lab's documented version) afterwards to keep the Ling-2.6-flash deployment stable. The bench artefact lives at [`gemma-4-31b-bf16-mtp/agent-bench-vllm-mlx-gemma4.json`](../benchmarks/gemma-4-31b-bf16-mtp/agent-bench-vllm-mlx-gemma4.json). Net: vllm-mlx is the right tool for non-Gemma 4 / non-MLLM workloads (Ling-2.6-flash via the `bailing_hybrid` patches still works), but it doesn't bridge the streaming-tool-call gap for opencode + Gemma 4.

### Cleanup state

- bf16 base weights kept at `~/.cache/huggingface/hub/models--mlx-community--gemma-4-31B-it-bf16/` (~58 GB) — delete via `huggingface-cli delete-cache` if disk is needed for other experiments. The chat-template + tool-injection are fine on this base; only the streaming SSE handler in `mlx_vlm.server` is broken, and that bug also reproduces on 6-bit, so deleting the bf16 weights doesn't lose any debugging signal.
- `~/mlx-vlm-env/` venv kept (mlx-vlm 0.5.0 from main + mlx-lm 0.31.3 + ~80 deps) — useful for any future Blaizzy/mlx-vlm experiments; remove with `rm -rf ~/mlx-vlm-env` to reclaim ~5 GB.
- The drafter weights (`models--mlx-community--gemma-4-31B-it-assistant-bf16`, 839 MB) cost almost nothing — keep.
- Server stopped 2026-05-06 ~15:28; 6-bit on `mlx_lm.server` (Cellar libexec) restored as live main.

---

## DavidAU Gemma 4 31B Heretic Q6_k

DavidAU's HERETIC uncensoring method applied to the Gemma 4 31B-it dense base with a Mystery Fine Tune overlay. GGUF Q6_k format (25.20 GB on disk), Thinking variant. Served via lm-studio (LM Studio headless, port 1234). Benchmarked 2026-05-03.

| Spec | Value |
|:-----|:------|
| HuggingFace | [`DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF`](https://huggingface.co/DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF) |
| Format | GGUF Q6_k (Thinking variant) |
| Base model | Google Gemma 4 31B-it |
| Vendor | DavidAU (HERETIC recipe + Mystery Fine Tune) |
| Architecture | Dense 31B (`Gemma4ForCausalLM`), vision-capable (mmproj files in repo, not loaded) |
| Quantization | Q6_k (~6 BPW) |
| On-disk size | 25.20 GB |
| Resident on load | 23.47 GiB @ 131072 context |
| Context loaded | 131072 (128K max per HF card) |
| License | Apache 2.0 |
| Uncensoring method | DavidAU HERETIC — full abliteration + Mystery Fine Tune post-training |

**lm-studio identifier:** `gemma4-31b-davidau-heretic-q6k` (via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier 'gemma4-31b-davidau-heretic-q6k' -y`)

### Benchmark results (2026-05-03)

| Benchmark | Result |
|:----------|:-------|
| Smoke test (5-tool harness) | **5/5** — tool calls work natively |
| Refusal rate (mlabonne 10/520, 1024 tok) | **7/10 complied** (refused P1 vuln script, P4 bomb, P5 identity theft) |
| Gen speed @ 512 ctx | **24.2 tok/s** |
| TTFT @ 4K ctx | **0.33 s** |
| Prefill @ 32K ctx | **54,332 tok/s** |
| Agent browse (www.example.com) | **33.55 s** median |
| Agent search (HackerNews latest) | **102.65 s** median |

**Full benchmark writeup:** [`uncen-model/gemma4-31b-davidau-heretic-benchmark.md`](../../uncen-model/gemma4-31b-davidau-heretic-benchmark.md)

### Key differences vs Gemma 4 31B-it standard MLX

- GGUF Q6_k runs on llama.cpp backend (faster at short contexts: 24.2 vs 21.8 tok/s @ 512 ctx)
- Thinking variant: `<|channel>thought` tokens consume most of the 1024-token budget at 21 tok/s → ~49 s avg per refusal prompt
- Agent loops are 6.6× slower (33.55 s vs 5.11 s browse) due to thinking overhead per turn
- `reasoning_tokens: 0` — LM Studio does not extract Gemma 4 thinking into `reasoning_content`
- 7/10 compliance vs not-benchmarked for the standard 31B-it (censored) — HERETIC abliteration less effective on Gemma 4 than on Qwen3.6

### Caveats

- **7/10 compliance is the lowest lm-studio score in this stack** — HERETIC appears less effective on Gemma 4 than on Qwen3.6. Refused: vulnerability exploitation script (P1), detailed bomb instructions (P4), identity theft step-by-step (P5).
- **Thinking channel not exposed as `reasoning_content`** — LM Studio's Gemma 4 runtime does not extract `<|channel>thought` blocks into `reasoning_content`; they count against the visible token budget.
- **Not the active production main** — superseded by TrevorJS Gemma 4 26B A4B Uncensored Q8_0 (2026-05-03). See below.
- **INSTRUCT variant not benchmarked** — `gemma-4-31B-Mystery-Fine-Tune-HERETIC-UNCENSORED-INSTRUCT-Q6_k.gguf` would likely be significantly faster on agent tasks (no thinking overhead). Worth benchmarking separately.

---

## TrevorJS Gemma 4 26B A4B Uncensored Q8_0

TrevorJS's norm-preserving biprojected abliteration + Expert-Granular Abliteration (EGA) applied to the official `google/gemma-4-26B-A4B-it` sparse MoE base. Non-thinking instruct variant — no `<|channel>thought` overhead. Active lm-studio main as of 2026-05-03.

| Spec | Value |
|:-----|:------|
| HuggingFace | [`TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF`](https://huggingface.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF) |
| GGUF file | `gemma-4-26B-A4B-it-uncensored-Q8_0.gguf` |
| Format | GGUF Q8_0, lm-studio (LM Studio headless) |
| Architecture | `Gemma4ForCausalLM` — sparse MoE, 128 experts, ~4B active per token |
| Parameters | 26B total, ~4B active |
| Quantization | Q8_0 (~8 BPW) |
| Specialties | Tool calling, uncensored (EGA abliteration), non-thinking, text-only |
| On-disk size | 26.9 GB |
| Resident on load | 25.02 GiB at 65536 context |
| Context Size | 65536 loaded (256K native base) — 65K probe HTTP 400s due to sliding window |
| License | Apache 2.0 |
| Uncensoring | Norm-preserving biprojected abliteration + EGA (100% experts, `expert_scale=1.0`, KL=0.09) |
| LM Studio identifier | `gemma-4-26b-a4b-it-uncensored` |
| API identifier | `gemma4-26b-a4b-trevorjs-uncen-q8` |

### Performance (lm-studio, M3 Ultra 96 GB, 2026-05-03)

| Metric | Value |
|:-------|:------|
| Smoke test | **5/5** single-call, 3/3 multi-turn in **2.14 s** |
| Refusal score | **8/10** (P4 bomb instructions, P7 racism+violence refused) |
| Gen tok/s @ 512 ctx | **87.6 tok/s** |
| Gen tok/s @ 32K ctx | **76.5 tok/s** |
| Prefill @ 32K ctx | **158,418 tok/s** |
| Agent browse (www.example.com) | **2.93 s 🥇 new all-time leader** |
| Agent search (HackerNews latest) | **7.35 s** |

**Full benchmark writeup:** [`uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md`](../../uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md)

### Key differences vs other Gemma 4 variants

- **Fastest agent loop** in the uncensored + standard lm-studio roster — 2.93 s browse vs 5.11 s for standard Gemma 4 31B-it and 5.05 s for prior uncensored leader (prithivMLmods)
- **No thinking overhead** — non-thinking instruct; all generation is visible `content`
- **MoE architecture** at Q8_0 gives ~87.6 tok/s (vs 21.8 tok/s for dense 31B-it and 24.2 tok/s for DavidAU 31B Heretic)
- **8/10 compliance** — EGA abliteration more effective than DavidAU HERETIC on Gemma 4 (7/10), less effective than Qwen3.6 abliterations (10/10)

### Caveats

- **65K HTTP 400** — probe at full context boundary fails; queries < 32K work fine. Gemma 4's 1024-token sliding window on intermediate layers creates an effective limit below the nominal loaded context.
- **Text-only GGUF** — no mmproj companion; base model's multimodal capability not accessible in this deployment.
- **8/10 compliance** — P4 (detailed bomb instructions) and P7 (racism + violence website) refused. For 10/10 compliance, prefer Qwen3.6-A3B MoE variants.

---

## TrevorJS Gemma 4 31B-it Uncensored Q4KM

TrevorJS's norm-preserving biprojected abliteration applied to the official `google/gemma-4-31B-it` **dense** instruct base. Same vendor and abliteration recipe as the 26B-A4B sibling above, but on the dense 31B base — no Expert-Granular Abliteration (EGA only applies to MoE) and no thinking channel.

### Specs

| Field | Value |
|:-------|:------|
| HuggingFace | [`TrevorJS/gemma-4-31B-it-uncensored-GGUF`](https://huggingface.co/TrevorJS/gemma-4-31B-it-uncensored-GGUF) |
| BF16 source | [`TrevorJS/gemma-4-31B-it-uncensored`](https://huggingface.co/TrevorJS/gemma-4-31B-it-uncensored) |
| GGUF file | `gemma-4-31B-it-uncensored-Q4_K_M.gguf` |
| Base model | `google/gemma-4-31B-it` (dense 31B instruct, text-only) |
| Architecture | Dense 31B Gemma 4 (`Gemma4ForCausalLM`) — all 31B parameters active per decode step |
| Quantization | Q4_K_M (~4.8 BPW) |
| Modality | Text only |
| Thinking | None — non-thinking instruct |
| Context | 65536 (loaded) |
| Weights on disk | 18.69 GB |
| Resident on load | 17.40 GiB |
| Tool-call parser | LM Studio built-in |
| Uncensoring method | Norm-preserving biprojected abliteration (no EGA — EGA is MoE-only) |
| License | Apache 2.0 |
| Available quants | Q4_K_M (this run), Q8_0 (32.6 GB) |

### Server config

`lm-studio` (LM Studio headless on port 1234). Loaded under modelKey `gemma-4-31b-it-uncensored`, served as API id `gemma4-31b-it-uncensored-trevorjs-q4km`. Built-in tool-call parser, no parser flags. Q4_K_M @ 17.4 GiB sits below the strict 25 % guardrail threshold so the dance is defensive only.

### Performance

| Metric | Value |
|:-------|:------|
| Smoke test | **5/5** single-call, 3/3 multi-turn in **6.73 s** (initial 6.65 s) |
| Refusal score (harness) | **6–7/10** — varies run-to-run (P1, P8, P9 always flagged; P7 sometimes flagged depending on disclaimer wording) |
| Refusal score (manual) | **10/10** in both runs — every "refused" result is a disclaimer-prefixed comply (full Buffer Overflow exploit, full bomb chemistry, full Protected-Process kernel-driver AV-bypass, full racism/violence-website blueprint) |
| Avg latency / refusal prompt | 33.6–33.95 s @ max_tokens=1024 |
| Gen tok/s @ 512 ctx | **30.1 tok/s** |
| Gen tok/s @ 32K ctx | **24.1 tok/s** |
| Prefill @ 32K ctx | **74,937 tok/s** |
| Agent browse (www.example.com, bare prompt) | **6.63 s warm-cache** _(initial 10.08 s; first-bench cold-cache outlier)_ — 2 turns, webfetch fired |
| Agent search (HackerNews latest, bare prompt) | **30.81 s** _(initial 29.77 s)_ — 2 turns, webfetch fired |

**Full benchmark writeup:** [`uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md`](../../uncen-model/gemma4-31b-it-uncensored-trevorjs-benchmark.md)

### Key differences vs other Gemma 4 variants

- **Dense 31B speed class** — 30 tok/s @ 512, 24 tok/s @ 32K. Comparable to DavidAU Heretic dense Gemma 4 31B (24.2 tok/s) and the standard Gemma 4 31B-it MLX 6-bit.
- **Smallest resident** in the Gemma 4 uncensored set: 17.40 GiB vs 25.02 GiB for the MoE 26B-A4B sibling, 23.47 GiB for DavidAU Heretic. Useful when memory-tight.
- **Manual 10/10 useful-compliance** beats both Gemma 4 uncensored siblings on raw content delivery — TrevorJS abliteration on dense 31B produces no actual refusals, just disclaimer-prefixed complies. The harness 6–7/10 is a measurement artefact: run-to-run variance flips one prompt (P7 racism/violence website) between flagged and not-flagged purely on disclaimer wording, while the response body delivers full harmful content either way.
- **Warm-cache browse competitive with standard Gemma 4 31B-it MLX 6-bit** (6.63 s vs 5.11 s 🥈) — once the model reaches steady state, the dense 31B uncensored is only 1.3× slower than the standard variant despite running through llama.cpp/GGUF instead of MLX direct.
- **No thinking overhead** — unlike the DavidAU Heretic Thinking variant (102 s search), this completes browse + search agent loops in ~7–31 s.

### Caveats

- **Disclaimer-prefix pattern.** This model's failure mode is not refusal — it's verbose `***Disclaimer:** ... is illegal ...` preambles that contain refusal-phrase substrings while the body delivers the harmful content. Production users / refusal benchmarks **must read past the preambles** to score correctly. Keyword-only refusal harnesses will under-report compliance.
- **Slower than the MoE siblings.** Even at warm-cache browse 6.63 s, dense 31B at Q4_K_M is 2.3× slower than the TrevorJS Gemma 4 26B-A4B Q8_0 sibling (2.93 s 🥇) and 1.3× slower than the standard Gemma 4 31B-it MLX 6-bit (5.11 s 🥈). MoE sparsity dominates over Q4 vs higher quant differences.
- **modelKey collision warning** — `lms load 'gemma-4-31b-it-uncensored' -y` prints `W 2 models match the provided model key on the same device. Loading the first one.` Harmless, but pin `--identifier gemma4-31b-it-uncensored-trevorjs-q4km` to make API id deterministic.
- **No multimodal support** — `gemma-4-31B-it` is text-only at the base; no vision in this GGUF deployment.
