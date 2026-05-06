# Model Summary: Gemma 4 Family

Google's Gemma 4 generation. Four variants currently catalogued in this stack: the **26B-A4B** mixture-of-experts multimodal release (vision + audio + video, 256K context, thinking mode), the dense **31B-it** instruction-tuned text-only release (64K context, thinking mode), the **DavidAU HERETIC uncensored 31B** GGUF fine-tune (128K context, Thinking variant, llmster), and the **TrevorJS EGA uncensored 26B A4B** GGUF (65K context loaded, non-thinking, active llmster main). They share the `Gemma4ForCausalLM` / `Gemma4ForConditionalGeneration` family but use different sub-architectures.

## Index

- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — MoE 26B/4B + vision + audio + video · 256K · `mlx-openai-server` · 15 GB · 50–62 tok/s
- [Gemma 4 31B-it (6-bit)](#gemma-4-31b-it-6-bit) — Dense 31B text-only · 64K loaded (256K native) · **mlx-lm server (current main 2026-05-06)** · 29 GB · 20.4 tok/s @ 512, browse 12.33 s (thinking ON) / browse 5.11 s (thinking OFF on llmster)
- [DavidAU Gemma 4 31B Heretic Q6_k](#davidau-gemma-4-31b-heretic-q6k) — Uncensored (HERETIC + MysteryFT) · 128K · `llmster` · 23.47 GiB · 24.2 tok/s · 7/10 mlabonne · [bench writeup](../../uncen-model/gemma4-31b-davidau-heretic-benchmark.md)
- [TrevorJS Gemma 4 26B A4B Uncensored Q8_0](#trevorjs-gemma-4-26b-a4b-uncensored-q8) — MoE 26B/4B active · 65K loaded · `llmster` · 25.02 GiB · **87.6 tok/s** · 8/10 mlabonne · **browse 2.93 s 🥇** · [bench writeup](../../uncen-model/gemma4-26b-a4b-trevorjs-uncen-benchmark.md)

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

---

## Gemma 4 31B-it (6-bit)

Google's dense **31B instruction-tuned** text-only Gemma 4. No MoE, no vision/audio — single-modality model. Built-in thinking mode (ON by default on mlx-lm server; OFF on LM Studio). Deployed via the **lmstudio-community** MLX 6-bit conversion. **Current production main (2026-05-06)** on mlx-lm server (port 8000). Verified on Mac Studio M3 Ultra (96 GB) on May 1, 2026 (llmster) and May 6, 2026 (mlx-lm server).

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
| Tokens/sec (llmster) | 21.8 @ 512 → 21.1 @ 8K → 18.3 @ 32K ([bench](../benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json)) |
| On-disk size | 29 GB (model files); 31.32 GB total weights |
| Context Size | 65,536 loaded (both servers); native ≥ 256K |
| License | Gemma Terms of Use |
| MTP Drafter (pending) | `mlx-community/gemma-4-31B-it-assistant-bf16` (839 MB, `gemma4_assistant` arch) — downloaded, waiting for mlx-lm 0.31.3+ arch support |

**Current server: mlx-lm (direct), port 8000.** Model served by full filesystem path.

**Launch shape (mlx-lm server — current production):**

```bash
ssh macstudio "nohup python3 -m mlx_lm server \
  --model /Users/chanunc/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit \
  --host 0.0.0.0 --port 8000 \
  --max-tokens 8192 --prompt-cache-size 5 \
  > /tmp/mlx-lm-server.log 2>&1 &"
```

**Reload on llmster (thinking OFF — for lower-latency agent loops):**

```bash
ssh macstudio "~/.lmstudio/bin/lms load 'gemma-4-31b-it-mlx' \
  --gpu max --context-length 65536 -y"
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

> **Loader gotcha:** `lms get` failed to download cleanly twice (timed out at 88% with a hung "Finalizing download…" state and only shards 4–6 of 6 on disk). Recovery path: kill the hung `lms get`, then complete the download via `huggingface_hub.snapshot_download(repo_id=…, local_dir=~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit)` from any venv with `huggingface_hub` installed. LM Studio recognises the on-disk layout and `lms ls` then surfaces the model normally.
>
> **Context gotcha (llmster only):** despite passing `--context-length 65536`, the first `lms load` resolved to context 4096. Re-`lms unload` + re-`lms load --context-length 65536 -y` correctly seats 64K.

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

Prefill is 2.5–2.8× faster than llmster across 4K–32K. TTFT sub-0.65 s at 65K.

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

Thinking mode adds 3–4× more output tokens vs. llmster run (35–45 tokens per session). Browse overhead factor 2.4×, search overhead factor 5.6× compared to llmster (thinking OFF). Raw JSON: [`gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json`](../benchmarks/gemma-4-31b-it-mlx-6bit/agent-bench-mlx-lm.json).

### Benchmarks — llmster (M3 Ultra 96 GB, May 1 2026, thinking OFF)

#### API server

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **21.8** | 1,232 | 0.44 |
| 4K | 21.5 | 6,028 | 0.68 |
| 8K | 21.1 | 11,584 | 0.71 |
| 32K | 18.3 | 36,297 | 0.90 |

Raw JSON: [`gemma-4-31b-it-6bit/api-server-llmster.json`](../benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json).

#### Agent loop (llmster, thinking OFF)

| Scenario | Wall time (median) | LLM time (median) | Turns | Output tokens |
|:---------|-------------------:|------------------:|------:|:------|
| Browse www.example.com | **5.11 s** | 3.94 s | 2 | ~35 |
| Browse Hackernews latest topic | **6.37 s** | 5.18 s | 2 | ~45 |

Raw JSON: [`gemma-4-31b-it-6bit/agent-bench-llmster.json`](../benchmarks/gemma-4-31b-it-6bit/agent-bench-llmster.json).

### Caveats

- **Thinking mode is server-dependent:** llmster (LM Studio) serves with thinking OFF (model doesn't invoke `<think>` blocks on short tool-calling prompts). mlx-lm server enables thinking by default — output tokens per turn are 3–4× higher and latency is 2.4–5.6× higher as a result. Use llmster if you want lowest-latency thinking-off agent loops; use mlx-lm for future MTP drafter support.
- **MTP drafter pending mlx-lm arch support:** `mlx-community/gemma-4-31B-it-assistant-bf16` is downloaded (839 MB, `gemma4_assistant` arch) but mlx-lm 0.31.3 raises `ModuleNotFoundError: No module named 'mlx_lm.models.gemma4_assistant'`. Add `--draft-model <snap-path> --num-draft-tokens 3` to the launch shape once upstream merges the arch.
- **`lms get` unreliable for >20 GB models** — use `huggingface_hub.snapshot_download` (see Loader gotcha above).
- **No vision input** — `Gemma4ForConditionalGeneration` in config.json, but loaded text-only; for multimodal see the 26B-A4B variant above.

---

## DavidAU Gemma 4 31B Heretic Q6_k

DavidAU's HERETIC uncensoring method applied to the Gemma 4 31B-it dense base with a Mystery Fine Tune overlay. GGUF Q6_k format (25.20 GB on disk), Thinking variant. Served via llmster (LM Studio headless, port 1234). Benchmarked 2026-05-03.

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

**llmster identifier:** `gemma4-31b-davidau-heretic-q6k` (via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier 'gemma4-31b-davidau-heretic-q6k' -y`)

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

- **7/10 compliance is the lowest llmster score in this stack** — HERETIC appears less effective on Gemma 4 than on Qwen3.6. Refused: vulnerability exploitation script (P1), detailed bomb instructions (P4), identity theft step-by-step (P5).
- **Thinking channel not exposed as `reasoning_content`** — LM Studio's Gemma 4 runtime does not extract `<|channel>thought` blocks into `reasoning_content`; they count against the visible token budget.
- **Not the active production main** — superseded by TrevorJS Gemma 4 26B A4B Uncensored Q8_0 (2026-05-03). See below.
- **INSTRUCT variant not benchmarked** — `gemma-4-31B-Mystery-Fine-Tune-HERETIC-UNCENSORED-INSTRUCT-Q6_k.gguf` would likely be significantly faster on agent tasks (no thinking overhead). Worth benchmarking separately.

---

## TrevorJS Gemma 4 26B A4B Uncensored Q8_0

TrevorJS's norm-preserving biprojected abliteration + Expert-Granular Abliteration (EGA) applied to the official `google/gemma-4-26B-A4B-it` sparse MoE base. Non-thinking instruct variant — no `<|channel>thought` overhead. Active llmster main as of 2026-05-03.

| Spec | Value |
|:-----|:------|
| HuggingFace | [`TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF`](https://huggingface.co/TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF) |
| GGUF file | `gemma-4-26B-A4B-it-uncensored-Q8_0.gguf` |
| Format | GGUF Q8_0, llmster (LM Studio headless) |
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

### Performance (llmster, M3 Ultra 96 GB, 2026-05-03)

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

- **Fastest agent loop** in the uncensored + standard llmster roster — 2.93 s browse vs 5.11 s for standard Gemma 4 31B-it and 5.05 s for prior uncensored leader (prithivMLmods)
- **No thinking overhead** — non-thinking instruct; all generation is visible `content`
- **MoE architecture** at Q8_0 gives ~87.6 tok/s (vs 21.8 tok/s for dense 31B-it and 24.2 tok/s for DavidAU 31B Heretic)
- **8/10 compliance** — EGA abliteration more effective than DavidAU HERETIC on Gemma 4 (7/10), less effective than Qwen3.6 abliterations (10/10)

### Caveats

- **65K HTTP 400** — probe at full context boundary fails; queries < 32K work fine. Gemma 4's 1024-token sliding window on intermediate layers creates an effective limit below the nominal loaded context.
- **Text-only GGUF** — no mmproj companion; base model's multimodal capability not accessible in this deployment.
- **8/10 compliance** — P4 (detailed bomb instructions) and P7 (racism + violence website) refused. For 10/10 compliance, prefer Qwen3.6-A3B MoE variants.
