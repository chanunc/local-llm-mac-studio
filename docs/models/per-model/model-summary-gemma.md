# Model Summary: Gemma 4 Family

Google's Gemma 4 generation. Two variants currently catalogued in this stack: the **26B-A4B** mixture-of-experts multimodal release (vision + audio + video, 256K context, thinking mode) and the dense **31B-it** instruction-tuned text-only release (64K context, thinking mode). They share the `Gemma4ForConditionalGeneration` family but use different sub-architectures.

## Index

- [Gemma 4 26B-A4B (4-bit)](#gemma-4-26b-a4b-4-bit) — MoE 26B/4B + vision + audio + video · 256K · `mlx-openai-server` · 15 GB · 50–62 tok/s
- [Gemma 4 31B-it (6-bit)](#gemma-4-31b-it-6-bit) — Dense 31B text-only · 64K loaded (256K native) · `llmster` · 29 GB · 18–22 tok/s, **6.3× faster agent loop than Qwen3.6-27B on llmster**

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

Google's dense **31B instruction-tuned** text-only Gemma 4. No MoE, no vision/audio — single-modality model. Built-in thinking mode (default-off in this deployment). Deployed via the **lmstudio-community** MLX 6-bit conversion, which is what LM Studio's `lms get` resolves to and what the LM Studio runtime (`mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`) loads natively. Verified on Mac Studio M3 Ultra (96 GB) on May 1, 2026.

| Spec | Value |
|:-----|:------|
| Base Model | [google/gemma-4-31b-it](https://huggingface.co/google/gemma-4-31b-it) |
| MLX 6-bit | [lmstudio-community/gemma-4-31B-it-MLX-6bit](https://huggingface.co/lmstudio-community/gemma-4-31B-it-MLX-6bit) |
| Format | MLX safetensors (text-only, 6 shards) |
| Vendor | Google DeepMind; MLX conversion by LM Studio Community |
| Architecture | `Gemma4ForCausalLM` — dense decoder, no MoE, no vision encoder |
| Parameters | 31B (dense — every token activates all parameters) |
| Quantization | 6-bit MLX |
| Specialties | Thinking mode, tool calling, long context, fast agent-loop on small outputs |
| Tokens/sec | 21.8 @ 512 → 21.5 @ 4K → 21.1 @ 8K → 18.3 @ 32K (llmster, [bench](../benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json)) |
| On-disk size | 29 GB (model files); 31.32 GB total weights as reported by `lms get` |
| Context Size | 65,536 loaded; native ≥ 256K (per HF model card; not retested at higher) |
| License | Gemma Terms of Use |
| Requirements | LM Studio runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.6.0`+ (ships native Gemma 4 support) |

**llmster (LM Studio headless) model ID:** `gemma-4-31b-it-mlx` (LM Studio mangles `lmstudio-community/gemma-4-31B-it-MLX-6bit` → lowercased, org-prefix-stripped, `-6bit` suffix dropped).

**Server config:** llmster on port 1234. **No parser flags required** — the LM Studio runtime auto-detects Gemma 4's tool-call format (verified empirical 5/5 pass on `bench_api_tool_call.py`) and routes `<think>` blocks to `reasoning_content` (verified — empty `reasoning_content` field present in the response schema even when no thinking is emitted).

**Launch shape:**

```bash
ssh macstudio "~/.lmstudio/bin/lms get \
  'https://huggingface.co/lmstudio-community/gemma-4-31B-it-MLX-6bit' -y"
ssh macstudio "~/.lmstudio/bin/lms load 'gemma-4-31b-it-mlx' \
  --gpu max --context-length 65536 -y"
```

> **Loader gotcha:** `lms get` failed to download cleanly twice (timed out at 88% with a hung "Finalizing download…" state and only shards 4–6 of 6 on disk). Recovery path: kill the hung `lms get`, then complete the download via `huggingface_hub.snapshot_download(repo_id=…, local_dir=~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit)` from any venv with `huggingface_hub` installed (`~/dflash-mlx-env/bin/python` works). LM Studio recognises the on-disk layout and `lms ls` then surfaces the model normally.
>
> **Context gotcha:** despite passing `--context-length 65536`, the first `lms load` resolved to context **4096** (the default for the model's chat template) — the 4K → 32K context bench hit `HTTP 400: tokens exceed context length`. Re-`lms unload` + re-`lms load --context-length 65536 -y` correctly seats 64K.

### Benchmarks (llmster, M3 Ultra 96 GB, May 1 2026)

Three runs against the loaded model at temperature 0.0; warmup excluded from medians.

#### API server (raw streaming, no tools)

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **21.8** | 1,232 | 0.44 |
| 4K | 21.5 | 6,028 | 0.68 |
| 8K | 21.1 | 11,584 | 0.71 |
| 32K | 18.3 | 36,297 | 0.90 |

Decode is roughly flat 21 tok/s at low–mid contexts and falls to 18 tok/s at 32K. Prefill scales well (1.2K → 36K tok/s as context grows), and TTFT stays under 1 s through 32K. For comparison: Qwen3.6-27B (dense, 6-bit) on the same llmster instance is ~30 tok/s decode at 32K and ~47K tok/s prefill — so the larger 31B dense Gemma pays a ~40% decode tax at this quant level.

Raw JSON: [`gemma-4-31b-it-6bit/api-server-llmster.json`](../benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json).

#### API tool-call (5-tool harness, single + 3-turn agentic)

| Scenario | Time | Result |
|:---------|----:|:-------|
| Single tool (file read) | 3.77 s | ✅ `read_file` |
| Single tool (command) | 1.28 s | ✅ `run_command` |
| Multi-tool (search + read) | 2.41 s | ✅ `search_web`, `read_file` |
| Multi-tool (list + read + write) | 1.41 s | ⚠ only `list_directory` (1 of 3 expected) |
| Agentic reasoning | 2.40 s | ✅ `run_command` |
| **Single-call pass rate** | — | **5/5** |
| 3-turn loop (read → write → summary) | **9.8 s** total | ✅ all turns complete |

Median single-tool latency 2.4 s, 3-turn loop 9.8 s — both **about 2× faster than Qwen3.6-27B on llmster** (5.4 s / 20.3 s respectively per the [llmster benchmarks](../benchmarks/model-benchmark-agent-tool-call.md#opencode-end-to-end-opencode-run---format-json-real-agent-loop)).

Raw JSON: [`gemma-4-31b-it-6bit/api-tool-test-llmster.json`](../benchmarks/gemma-4-31b-it-6bit/api-tool-test-llmster.json).

#### Agent loop (`opencode run --format json`)

| Scenario | Wall time (median) | LLM time (median) | Turns | Tools |
|:---------|-------------------:|------------------:|------:|:------|
| Browse www.example.com | **5.11 s** | 3.94 s | 2 | `webfetch` |
| Browse Hackernews latest topic | **6.37 s** | 5.18 s | 2 | `webfetch` |

**6.3× faster on Browse and 4.0× faster on Search** vs. Qwen3.6-27B on llmster (31.96 s / 25.71 s wall). Output is tiny (15–23 tokens per turn) — Gemma 4 31B-it goes straight to the tool call without a thinking-prelude, which is the dominant cost for Qwen3.6 on the same harness.

Raw JSON: [`gemma-4-31b-it-6bit/agent-bench-llmster.json`](../benchmarks/gemma-4-31b-it-6bit/agent-bench-llmster.json).

### Caveats

- **`reasoning_content` field present but empty in this prompt set** — Gemma 4 31B has built-in thinking mode but did not emit `<think>` blocks on any of the bench prompts (short reasoning prompts; one-shot tool calls; 2-turn agent loops). This is consistent with Gemma 4's training (thinking only on prompts that warrant it), not a parser bug. Set `chat_template_kwargs.enable_thinking: true` if explicit thinking is needed.
- **`lms get` is unreliable for >20 GB models on this system** — the closed-source LM Studio downloader hung at 88% with no resume capability twice in this deployment. The `huggingface_hub.snapshot_download` workaround above is the recommended path; LM Studio still recognises the model afterward.
- **First `lms load` ignores `--context-length` flag in some cases** — verify with `lms ps` after load and reload if context isn't what you asked for.
- **vllm-mlx, oMLX, mlx-openai-server:** Not tested for this model. Same Gemma 4 parser issues as the 26B-A4B section above apply (parser-registration gaps in oMLX, vllm-mlx reasoning-parser bug). llmster is the lowest-friction path.
- **No vision input** — this is the dense text-only release; for image / video / audio see the 26B-A4B variant above.

### Provisional posture

Per the llmster precedent in CLAUDE.md, only `configs/clients/llmster/opencode.json` lists this model; the other client templates (`claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json`) are deferred until/unless this model graduates to a permanent role. Top-level `model` / `small_model` keys in `opencode.json` remain on `qwen3.6-27b` — Gemma 4 31B is opt-in per request.
