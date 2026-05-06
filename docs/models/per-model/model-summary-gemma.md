# Model Summary: Gemma 4 Family

Google's Gemma 4 generation. Four variants currently catalogued in this stack: the **26B-A4B** mixture-of-experts multimodal release (vision + audio + video, 256K context, thinking mode), the dense **31B-it** instruction-tuned text-only release (64K context, thinking mode), the **DavidAU HERETIC uncensored 31B** GGUF fine-tune (128K context, Thinking variant, llmster), and the **TrevorJS EGA uncensored 26B A4B** GGUF (65K context loaded, non-thinking, active llmster main). They share the `Gemma4ForCausalLM` / `Gemma4ForConditionalGeneration` family but use different sub-architectures.

## Index

- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — MoE 26B/4B + vision + audio + video · 256K · `mlx-openai-server` · 15 GB · 50–62 tok/s
- [Gemma 4 31B-it (6-bit)](#gemma-4-31b-it-6-bit) — Dense 31B text-only · 64K loaded (256K native) · **mlx-lm server (current main 2026-05-06)** · 29 GB · 20.4 tok/s @ 512, browse 12.33 s (thinking ON) / browse 5.11 s (thinking OFF on llmster)
- [Codex GPT-5.5 finding: best next Gemma 4 MTP target for Mac Studio](#codex-gpt-55-finding-best-next-gemma-4-mtp-target-for-mac-studio-2026-05-06) — source-backed recommendation: try `gemma-4-e4b-it-bf16` + E4B assistant before retrying 31B or 26B-A4B MTP
- [Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm) — failed experiment](#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment) — drafter works at upstream-expected efficiency, pairs cleanly with 6-bit too (5/5 API harness, 16.54 s loop). **Real blocker: mlx-vlm's streaming SSE emits `delta.tool_calls` only as a final post-loop chunk** (mlx-lm streams them per-token), so opencode hits 300 s wall before the chunk fires. Independent of bf16 vs 6-bit, chat_template, or coalesce env var.
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
- **MTP drafter cannot be served via mlx-lm — only via mlx-vlm 0.5.0+ (from main):** `mlx-community/gemma-4-31B-it-assistant-bf16` (839 MB, `gemma4_assistant` arch) is supported in `mlx_vlm/speculative/drafters/gemma4_assistant/`, **not** in mlx-lm. mlx-lm 0.31.3 raises `Model type gemma4_assistant not supported`. PyPI `mlx-vlm 0.4.4` lacks the `mlx_vlm.speculative` submodule entirely; install from main (`pip install 'git+https://github.com/Blaizzy/mlx-vlm.git@main'` → 0.5.0). **The drafter is NOT bf16-locked** — the HF model card only documents bf16 pairings, but source-code review (no dtype assertion in `gemma4_assistant.py`/`config.py`/`parity_check.py`) plus community evidence ([NVIDIA forum's `serapis` ran `Intel/gemma-4-31B-it-int4-AutoRound` + drafter on vLLM for ~2× speedup](https://forums.developer.nvidia.com/t/gemma4-draft-models-are-now-available/369114)) plus our local verification (5/5 API tool-call harness on 6-bit + bf16 drafter, multi-turn loop 16.54 s) confirm any quantization works. **Documented failure mode for opencode-style streaming agent clients (regardless of quantization)** — see "[Gemma 4 31B-it bf16 + MTP drafter (mlx-vlm)](#gemma-4-31b-it-bf16--mtp-drafter-mlx-vlm-2026-05-06-failed-experiment)" below for the streaming tool-call emission bug.
- **`lms get` unreliable for >20 GB models** — use `huggingface_hub.snapshot_download` (see Loader gotcha above).
- **No vision input** — `Gemma4ForConditionalGeneration` in config.json, but loaded text-only; for multimodal see the 26B-A4B variant above.

---

## Codex GPT-5.5 finding: best next Gemma 4 MTP target for Mac Studio (2026-05-06)

Codex GPT-5.5 web review (2026-05-06) found that Google's MTP release materially changes the search space, but it does **not** overturn the local failure conclusion for the 31B bf16 + MTP pair. The best next experiment on this 96 GB Mac Studio is the **dense E4B bf16 target with its matching E4B assistant drafter**:

| Role | Model |
|:-----|:------|
| Target | [`mlx-community/gemma-4-e4b-it-bf16`](https://huggingface.co/mlx-community/gemma-4-e4b-it-bf16) |
| Drafter | [`mlx-community/gemma-4-E4B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-E4B-it-assistant-bf16) |
| Runtime | `mlx-vlm 0.5.0+` from main, `--draft-kind mtp`, `--draft-block-size 6` |

Rationale:

- **E4B is the cleanest Mac Studio MTP test.** It is dense, small enough to fit comfortably in bf16 (~16 GB target, ~159 MB drafter), and avoids both the 31B bf16 memory-bandwidth wall and the 26B-A4B MoE routing penalty at batch size 1.
- **Google explicitly calls out the 26B-A4B Apple Silicon caveat.** The official MTP blog says the 26B MoE has unique routing challenges at B=1 on Apple Silicon, while batch sizes 4-8 can unlock up to ~2.2x speedup locally. That makes 26B-A4B interesting for concurrent server throughput, not the first choice for sequential opencode-style agent loops.
- **E2B/E4B assistants have an extra drafter-side optimization.** Google's MTP docs and the vLLM Gemma 4 recipe note that E2B/E4B assistants use centroid / ordered-embedding masking to reduce the expensive vocabulary projection; 26B-A4B and 31B assistants do not.
- **31B bf16 + MTP remains a "do not retry yet" path for this workload.** Local benching already showed 12.3 tok/s @ 8K, 32K+ OOM, very slow prefill, and streaming agent hangs. Upstream and community reports confirm that the 31B MTP path can speed up bf16 vs bf16-no-drafter, but on Apple Silicon it still lands around 10-12 tok/s in early reports, which is below the current 6-bit production path for single sequential agent turns.

Suggested test launch shape:

```bash
ssh macstudio "nohup ~/mlx-vlm-env/bin/python -m mlx_vlm.server \
  --host 0.0.0.0 --port 8000 \
  --model mlx-community/gemma-4-e4b-it-bf16 \
  --draft-model mlx-community/gemma-4-E4B-it-assistant-bf16 \
  --draft-kind mtp \
  --draft-block-size 6 \
  --max-tokens 2048 \
  > /tmp/mlx-vlm-gemma4-e4b-mtp.log 2>&1 &"
```

Recommended priority order:

1. **Next MTP experiment:** `mlx-community/gemma-4-e4b-it-bf16` + `mlx-community/gemma-4-E4B-it-assistant-bf16`.
2. **Current best production Gemma:** keep `lmstudio-community/gemma-4-31B-it-MLX-6bit` on `mlx_lm.server` until E4B MTP is benchmarked end-to-end.
3. **Batch/concurrency experiment only:** `mlx-community/gemma-4-26b-a4b-it-bf16` + `mlx-community/gemma-4-26B-A4B-it-assistant-bf16`.
4. **Avoid for now:** `mlx-community/gemma-4-31b-it-bf16` + `mlx-community/gemma-4-31B-it-assistant-bf16` for opencode-style streaming agent loops.

Sources checked:

- Google Keyword: [Accelerating Gemma 4: faster inference with multi-token prediction drafters](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/) — MTP release, up-to-3x claim, KV/activation sharing, 26B-A4B Apple Silicon B=1 caveat.
- Google AI docs: [Speed-up Gemma 4 with Multi-Token Prediction](https://ai.google.dev/gemma/docs/mtp/overview) — architecture description, dense vs MoE verification behavior, E2B/E4B efficient embedder.
- Hugging Face / Google: [`google/gemma-4-31B-it-assistant`](https://huggingface.co/google/gemma-4-31B-it-assistant) — assistant-model card with Gemma 4 family specs, benchmark table, thinking controls, and usage examples.
- Hugging Face / mlx-community: [Gemma-4 Assistant (MTP) collection](https://huggingface.co/collections/mlx-community/gemma-4-assistant-mtp) — MLX assistant roster for E2B, E4B, 26B-A4B, and 31B.
- Hugging Face / mlx-community: [`gemma-4-e4b-it-bf16`](https://huggingface.co/mlx-community/gemma-4-e4b-it-bf16), [`gemma-4-E4B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-E4B-it-assistant-bf16), [`gemma-4-26b-a4b-it-bf16`](https://huggingface.co/mlx-community/gemma-4-26b-a4b-it-bf16), [`gemma-4-26B-A4B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-26B-A4B-it-assistant-bf16), [`gemma-4-31b-it-bf16`](https://huggingface.co/mlx-community/gemma-4-31b-it-bf16), [`gemma-4-31B-it-assistant-bf16`](https://huggingface.co/mlx-community/gemma-4-31B-it-assistant-bf16) — model sizes, pairings, MLX launch examples.
- vLLM recipes: [Gemma 4 Usage Guide](https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html) — available assistant models, recommended speculative-token settings, E2B/E4B centroid masking note, hardware caveat.
- Community signal: [LocalLLaMA Gemma 4 MTP release thread](https://www.reddit.com/r/LocalLLaMA/comments/1t4jq6h/gemma_4_mtp_released/) and [MacBook M5 128 GB 31B MTP report](https://www.reddit.com/r/LocalLLaMA/comments/1t4un0t/gemma431bcodingmtpbf16_slow_on_macbook_m5_128gb/) — early MLX/Mac reports support the conclusion that 31B bf16 MTP improves over bf16 baseline but is still not the best single-user Mac agent path.

---

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

### What would unblock this

- **Fix mlx-vlm's streaming tool-call emission** to mirror mlx-lm's per-token state machine. File upstream against [Blaizzy/mlx-vlm](https://github.com/Blaizzy/mlx-vlm). Tracked upstream limitations: [PR #773](https://github.com/Blaizzy/mlx-vlm/pull/773) (the original tool-calling PR) explicitly acknowledged "*mlx_lm parses the streaming output one token at a time during generation. This implementation parses it at the end of the stream*" — known compromise from day one. [PR #1037](https://github.com/Blaizzy/mlx-vlm/pull/1037) (merged) only strips raw markup from `delta.content`, "*preserving the existing single-emission pattern*". [PR #1012](https://github.com/Blaizzy/mlx-vlm/pull/1012) author noted "*End-of-stream chunk (... + tool_calls) … emitted once per request, not per token*". No open PR proposes per-token incremental `delta.tool_calls` emission. Related: [opencode #4255](https://github.com/anomalyco/opencode/issues/4255) (empty `tool_calls: []` array hang, open).
- **mlx-lm gaining `gemma4_assistant` arch support** (no PR open as of 2026-05-06; PR #1226 added MTP only for Qwen3.5/3.6). With mlx-lm hosting the drafter, the proven-working incremental tool-call streaming + prompt-cache reuse from the current 6-bit run would carry over, *and* mlx-lm could quantize the target so 6-bit + drafter avoids the bf16 bandwidth tax entirely. **This is the cleanest path forward.**
- **Until either of the above lands**, keep the 6-bit production main on `mlx_lm.server` and treat the mlx-vlm install as documentation-only.

### Runtime support landscape (verified 2026-05-06)

Where the `gemma4_assistant` MTP drafter actually runs today, across the runtimes this lab cares about plus references for completeness:

| Runtime | Status | Notes / citation |
|:--------|:-------|:-----------------|
| **mlx-lm** | ❌ Not supported | Raises `Model type gemma4_assistant not supported`. **0 PRs** open/closed in [`ml-explore/mlx-lm`](https://github.com/ml-explore/mlx-lm/pulls?q=is%3Apr+gemma4_assistant) for the drafter arch. Recent MTP work ([PR #1226](https://github.com/ml-explore/mlx-lm/pull/1226)) was Qwen 3.5/3.6 only. Active Gemma 4 PRs are sanitize/quantize/tool-parser — none touch MTP. |
| **mlx-vlm** | ⚠ Partial — non-streaming only | [PR #1112](https://github.com/Blaizzy/mlx-vlm/pull/1112) merged 2026-05-05; ships in 0.5.0 from main. Drafter pairs with quantized targets too (verified). **Streaming tool-call emission bug** ([per-token state machine missing](#root-cause-verified-by-source-code-review-2026-05-06)) makes opencode-style agent loops unusable. |
| **LM Studio (llama.cpp + GGUF)** | ❌ Not supported | LM Studio [speculative-decoding docs](https://lmstudio.ai/docs/app/advanced/speculative-decoding) only describe standard small-base-model drafters. No MTP / `gemma4_assistant` references in changelog through v0.4.11 (last Gemma 4 mention: "Improve Gemma 4 tool call reliability"). Underneath, [llama.cpp discussion #22735](https://github.com/ggml-org/llama.cpp/discussions/22735) (open, no maintainer engagement) reports `convert_hf_to_gguf.py` doesn't recognize `Gemma4AssistantForCausalLM` and new scaling tensors (`model.layers.0.layer_scalar`) are unmapped — **drafter weights can't even be converted to GGUF today**, let alone served. Plus the docs note "speculative decoding is problematic for MoE models like Gemma 4 26B-A4B" — even when MTP lands, 26B-A4B won't benefit. |
| **vLLM (Linux)** | ✅ Supported with quantized targets | NVIDIA Developer Forum: [`serapis`](https://forums.developer.nvidia.com/t/gemma4-draft-models-are-now-available/369114) ran `Intel/gemma-4-31B-it-int4-AutoRound` (4-bit) + `google/gemma-4-31B-it-assistant` (bf16 drafter) via `gemma4_mtp` method → **11.43 → 22.05 tok/s (~1.93×)**. Linux/server-grade; not the Mac Studio's path. |
| **transformers / SGLang** | ✅ Official Google path | Per Google's [MTP overview](https://ai.google.dev/gemma/docs/mtp/overview). Not a Mac Studio server stack. |
| **Ollama** | ❌ Tool parser broken as of 0.20.1 | [Paweł Huryn on X (2026-05)](https://x.com/PawelHuryn/status/2040498812318273583): "*Gemma 4 has function calling built in. Good luck actually using it … Ollama: tool parser still broken as of v0.20.1.*" Even basic Gemma 4 tool calls fail; MTP drafter not on their roadmap. |
| **Community: SeatownSin/gemma-4-E4B-mtp-drafter** | 🔬 Curio only | [HF model card](https://huggingface.co/SeatownSin/gemma-4-E4B-mtp-drafter) — first public extraction of the MTP heads Google trained but **stripped from the public HF release** (still present in proprietary LiteRT). Safetensors fp32, 78M params, **35% top-1 acceptance** (INT4 quant noise from mobile weights). Documented for transformers/vLLM/SGLang. **No GGUF or MLX port.** Interesting backstory; not a workaround for this lab. |

**What to watch:**
- `ml-explore/mlx-lm` — any new PR adding `gemma4_assistant` model architecture (currently 0 in queue; would unblock the cleanest path).
- `ggml-org/llama.cpp` — [discussion #22735](https://github.com/ggml-org/llama.cpp/discussions/22735) and [issue #22337](https://github.com/ggml-org/llama.cpp/issues/22337) ("draft issue Gemma E2B") for any conversion-script PR.
- `Blaizzy/mlx-vlm` — streaming SSE tool-call structural rewrite (per-token `delta.tool_calls` emission). [PR #773](https://github.com/Blaizzy/mlx-vlm/pull/773), [#1037](https://github.com/Blaizzy/mlx-vlm/pull/1037), [#1012](https://github.com/Blaizzy/mlx-vlm/pull/1012) all explicitly preserved the post-loop pattern; no open PR proposes the change.

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
