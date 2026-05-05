# Model Summary: IBM Granite 4.1 Family

IBM's Granite 4.1 generation. One variant currently catalogued in this stack: the **30B** dense instruction-tuned model, quantized to Q8_0 GGUF by the Unsloth team (Apache 2.0).

## Index

- [Granite 4.1 30B Q8_0 (unsloth GGUF)](#granite-41-30b-q8_0-unsloth-gguf) — Dense 30B instruct · 65K loaded · `llmster` · 28.57 GiB · 24.8 tok/s · **active llmster main 2026-05-05**

---

## Granite 4.1 30B Q8_0 (unsloth GGUF)

IBM's Granite 4.1 30B instruction-tuned model. Dense decoder-only architecture (no MoE, no vision). Standard RLHF-aligned safety training; Apache 2.0 license (no usage restrictions). Quantized to Q8_0 by Unsloth. Verified on Mac Studio M3 Ultra (96 GB) on 2026-05-05.

| Spec | Value |
|:-----|:------|
| Base Model | IBM Granite 4.1 30B Instruct |
| GGUF repo | [unsloth/granite-4.1-30b-GGUF](https://huggingface.co/unsloth/granite-4.1-30b-GGUF) |
| GGUF file | `granite-4.1-30b-Q8_0.gguf` (30.7 GB download) |
| Format | GGUF Q8_0 |
| Vendor | IBM Research; GGUF by Unsloth |
| Architecture | `granite` (dense decoder-only transformer) |
| Parameters | 30B (dense — every token activates all parameters) |
| Quantization | Q8_0 |
| Specialties | Tool calling, instruction following, Apache 2.0, no thinking overhead |
| On-disk size | 30.7 GB (download); 28.57 GiB resident after load |
| Context Size | 131,072 tokens native; loaded at 65,536 (65K probe HTTP 400 — sliding window boundary) |
| License | Apache 2.0 |

**LM Studio internal name:** `granite-4.1-30b`

**API identifier:** `granite-4.1-30b-q8`

**Server:** `llmster` / LM Studio headless on port 1234

### Deployment Recipe

```bash
# 1. Download
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='unsloth/granite-4.1-30b-GGUF', \
  filename='granite-4.1-30b-Q8_0.gguf', \
  local_dir='/Users/chanunc/.cache/hauhau-gguf')\""

# 2. Hard-link import
ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo unsloth/granite-4.1-30b-GGUF -y \
  ~/.cache/hauhau-gguf/granite-4.1-30b-Q8_0.gguf"

# 3. Disable guardrail, load, restore
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='off'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""
ssh macstudio "~/.lmstudio/bin/lms load 'granite-4.1-30b' \
  --gpu max --context-length 65536 \
  --identifier 'granite-4.1-30b-q8' -y"
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); \
  s=json.load(open(f'{h}/.lmstudio/settings.json')); \
  s['modelLoadingGuardrails']['mode']='high'; \
  json.dump(s, open(f'{h}/.lmstudio/settings.json','w'), indent=2)\""
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"
```

### Smoke Test (API Tool Harness)

Tested on **Mac Studio M3 Ultra (96 GB)** — 2026-05-05.

**Server:** llmster / LM Studio headless on port 1234. Raw JSON: [`../benchmarks/granite-4.1-30b-q8/api-tool-test.json`](../benchmarks/granite-4.1-30b-q8/api-tool-test.json).

| # | Scenario | Latency (s) | finish_reason | tools called |
|:--|:---------|------------:|:--------------|:-------------|
| 1 | Single tool (file read) | 2.99 | `tool_calls` | `read_file` |
| 2 | Single tool (command) | 1.13 | `tool_calls` | `run_command` |
| 3 | Multi-tool (search + read) | 1.29 | `tool_calls` | `search_web` |
| 4 | Multi-tool (list + read + write) | 1.13 | `tool_calls` | `list_directory` |
| 5 | Agentic reasoning | 1.14 | `tool_calls` | `list_directory` |

**Pass rate: 5/5.** Tool calls are well-formed. LM Studio handles Granite tool-call format natively — no parser flags required.

**Multi-turn loop (3 turns, total 10.37 s):**

| Turn | Prompt shape | Latency (s) | finish_reason | Tool called |
|:-----|:-------------|------------:|:--------------|:------------|
| 1 | `Read /tmp/app/config.json, change port to 8080, write back` | 2.74 | `tool_calls` | `read_file` |
| 2 | (with prior tool result) | 3.14 | `tool_calls` | `write_file` |
| 3 | (with prior tool result) | 4.50 | `stop` | — final answer |

### Throughput (llmster, 2026-05-05)

Method: streaming SSE `/v1/chat/completions`, 50 max tokens, temperature 0.0, 2 runs + 1 warmup. Raw JSON: [`../benchmarks/granite-4.1-30b-q8/api-server-llmster.json`](../benchmarks/granite-4.1-30b-q8/api-server-llmster.json).

| Context | Gen (tok/s) | Prefill (tok/s) | TTFT (s) |
|:--------|------------:|----------------:|---------:|
| 512 | **24.8** | 2,520 | 0.22 |
| 4K | 26.0 | 17,890 | 0.23 |
| 8K | 23.6 | 34,200 | 0.24 |
| 32K | 18.7 | 92,600 | 0.36 |

Gen speed is 3–3.5× slower than TrevorJS Gemma 4 26B A4B (sparse MoE ~4B active) due to all 30B params being active per decode step. Prefill scales linearly from ~2.5K tok/s @ 512 to ~92K tok/s @ 32K (well-behaved dense attention).

### Agent Benchmark (OpenCode, 2026-05-05)

Method: `bench_agent_tool_call.py`, `opencode run --format json`, 3 measured runs + 1 warmup. Raw JSON: [`../benchmarks/granite-4.1-30b-q8/agent-bench-llmster.json`](../benchmarks/granite-4.1-30b-q8/agent-bench-llmster.json).

| Scenario | Wall time (median) | LLM time | Turns | Tools |
|:---------|:------------------:|:--------:|:-----:|:------|
| Browse www.example.com | 6.24 s | 5.02 s | 2 | webfetch |
| Browse Hackernews latest | 10.51 s | 9.31 s | 2 | webfetch |

Browse is ~2× slower than TrevorJS Gemma 4 26B A4B (2.93 s) but competitive with Gemma 4 31B-it (5.11 s) for a dense 30B GGUF.

### Agent Benchmark (llama-agent in-process, 2026-05-05)

Method: [`bench_agent_local.py`](../../../scripts/bench/bench_agent_local.py) — drives [`gary149/llama-agent`](https://github.com/gary149/llama-agent) (build b9121 pre-built binary) over a PTY, with the model resident across all scenarios. **No OpenAI-compatible server in the path** — inference and the agent loop run in one process. Tools execute for real against a sandbox at `/private/tmp/bench-llama-agent`. Raw JSON: [`../benchmarks/granite-4.1-30b-q8/agent-local.json`](../benchmarks/granite-4.1-30b-q8/agent-local.json). See [`model-benchmark-agent-local.md`](../benchmarks/model-benchmark-agent-local.md) for methodology + harness caveats.

Model load: **3.84 s** (one-time). Steady gen rate per scenario: **21.0–21.4 tok/s** (vs 24.8 tok/s raw streaming via LM Studio — small gap is per-turn agent-loop reset, not server overhead).

| # | Scenario | Wall (s) | Iter | Output tok | tok/s | Tools called |
|:--|:---------|---------:|-----:|-----------:|------:|:-------------|
| 1 | Single tool (file read) | 10.11 | 2 | 61 | 21.4 | `read` |
| 2 | Single tool (command) | 6.60 | 2 | 63 | 21.4 | `bash` |
| 3 | Multi-tool (grep + read) | 8.69 | 3 | 147 | 21.1 | `glob` → `read` |
| 4 | Multi-tool (list + read + write) | 11.74 | 4 | 203 | 21.0 | `glob` → `read` → `write` |
| 5 | Agentic reasoning (largest file) | 12.85 | 4 | 138 | 21.2 | `glob` → `bash` |
| — | **Multi-turn (port=8080)** | **15.35** | 5 | 265 | 21.0 | `read` → `edit` → `read` → `edit` ✅ port rewritten |

**Pass rate: 6/6.** The multi-turn `read → edit → read → edit` sequence shows the model double-checks the file after editing — real agent behaviour, not a regression. Total scenarios wall: 65.34 s after a single 3.84 s model load.

### Caveats

- **65K context probe HTTP 400** — Granite 4.1 sliding window boundary; real queries < 32K work fine. Same pattern as Gemma 4 on llmster.
- **Dense 30B decode speed** — all 30B params active per token; 24.8 tok/s is expected (vs 87.6 tok/s for Gemma 4 26B-A4B MoE at ~4B active). For higher throughput use the Gemma 4 26B A4B or a sparse MoE model.
- **Censored/aligned** — standard IBM RLHF safety training. For uncensored content workflows, reload TrevorJS Gemma 4 26B A4B Uncensored Q8_0 from `docs/current.md` fallbacks.
- **Guardrail required** — LM Studio guardrail `mode: "high"` blocks this load; must toggle `"off"` before `lms load`, then restore.
