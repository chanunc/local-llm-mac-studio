# Plan: Ollama top benchmark model deployment comparison

Status: done
Created: 2026-05-31
Completed: 2026-05-31
Canonical: no

## Objective

Deploy and benchmark non-Qwen3.6-A3B models on the Mac Studio Ollama sidecar to test whether Ollama can beat LM Studio on the same family / similar quant in agent workloads.

This plan follows the completed `qwen3.6:35b-mlx` Ollama deployment pattern:

- Keep Ollama on sidecar port `11434`.
- Run pre-benchmark hygiene before each measured run.
- Smoke direct OpenAI-compatible tool calls before OpenCode agent benchmarks.
- Record raw JSON under `docs/models/benchmarks/logs/<model-slug>/`.
- Update benchmark summary rows only after results are validated.
- Do not record live run-state in docs.

## Current baseline to beat

Use `docs/models/benchmarks/model-benchmark-tool-call.md` as the canonical comparison table.

### Primary target family: Gemma 4 26B-A4B

This is the strongest candidate because Gemma 4 26B-A4B dominates the top non-Qwen3.6-A3B benchmark rows:

| Existing row | Server | API loop | Browse | Search | Notes |
|:--|:--|--:|--:|--:|:--|
| Huihui Gemma 4 26B-A4B Abliterated i1-Q6_K | lm-studio | 1.93 s | 2.55 s | 19.59 s | API leader and browse leader; search uses `task` subagent |
| TrevorJS Gemma 4 26B-A4B Uncensored Q8_0 | lm-studio | 2.14 s | 2.93 s | 7.35 s | Search leader; uses `webfetch` |
| lmstudio-community Gemma 4 26B-A4B-it Q8_0 | lm-studio | 2.14 s | 2.94 s | 7.20 s | Needs scaffolded prompts |
| mlx-community Gemma 4 26B-A4B-it 4-bit MLX | lm-studio | not run | 3.29 s | 3.23 s | Best standard/censored Gemma 4 search row |

Ollama has official `gemma4:26b`, advertised as Gemma 4 26B-A4B MoE, ~4B active, 18GB, 256K context, text/image, tool-capable. This is the first model to test.

### Secondary target: Granite 4.1 30B

Granite is the strongest clean dense comparison:

| Existing row | Server | API loop | Browse | Search | Notes |
|:--|:--|--:|--:|--:|:--|
| IBM Granite 4.1 30B Q8_0 | lm-studio | 10.37 s | 6.24 s | 10.51 s | Dense #1 OpenCode row; Apache 2.0 |

Ollama has `granite4.1:30b-q5_1`. This is not the same quant as the LM Studio Q8_0 row, but it is a good family-level server comparison.

### Tertiary target: Gemma 4 31B-it

Use this only after Gemma 4 26B and Granite:

| Existing row | Server | API loop | Browse | Search | Notes |
|:--|:--|--:|--:|--:|:--|
| TrevorJS Gemma 4 31B-it Uncensored Q4_K_M | lm-studio | 6.73 s | 6.63 s warm | 30.81 s | Dense uncensored variant |
| Gemma 4 31B-it 6-bit MLX | lm-studio / mlx-lm | 9.8 s | 5.11-12.33 s | 6.37-35.55 s | Results differ by runtime and think mode |

Ollama has official `gemma4:31b`, 20GB, 256K context. It is useful for server-family comparison, but less clean because the best LM Studio row is an uncensored GGUF variant.

## Candidate order

1. `gemma4:26b`
2. `granite4.1:30b-q5_1`
3. `gemma4:31b`

Optional exact-GGUF import tests after the official tags:

1. Import `mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF` into Ollama via `Modelfile`.
2. Import `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` into Ollama via `Modelfile`.
3. Import the existing Granite 4.1 30B Q8_0 GGUF into Ollama via `Modelfile`.

Exact-GGUF imports are the cleanest LM Studio vs Ollama server comparison. Official Ollama tags are the best test of Ollama's curated/optimized path.

## Pre-benchmark hygiene

Before each benchmark, stop other LLM servers on the Mac Studio. Use the repo standard Event 4 hygiene with Ollama added explicitly, because this plan restarts Ollama between candidate models:

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'; \
  pkill -f '/opt/homebrew.*/ollama serve'; pkill -f 'ollama runner'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx|sglang.launch_server|sglang serve|ollama' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

Do not restore the prior model afterward.

## Ollama server launch

```bash
ssh macstudio "nohup env OLLAMA_HOST=0.0.0.0:11434 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 \
  /opt/homebrew/opt/ollama/bin/ollama serve > /tmp/ollama.log 2>&1 &"
```

Pull candidate:

```bash
ssh macstudio "/opt/homebrew/opt/ollama/bin/ollama pull gemma4:26b"
ssh macstudio "/opt/homebrew/opt/ollama/bin/ollama list | head"
curl -s http://<MAC_STUDIO_IP>:11434/v1/models | python3 -m json.tool
```

Stop:

```bash
ssh macstudio "pkill -f '/opt/homebrew.*/ollama serve'; pkill -f 'ollama runner'"
```

## Client config approach

Create or temporarily modify `configs/clients/ollama/opencode.json` for each model.

For `gemma4:26b`, add model entry:

```json
"gemma4:26b": {
  "name": "Gemma 4 26B-A4B via Ollama",
  "tools": true,
  "reasoning": true,
  "limit": {
    "context": 65536,
    "output": 8192
  }
}
```

Set:

```json
"model": "macstudio-ollama/gemma4:26b",
"small_model": "macstudio-ollama/gemma4:26b"
```

For one-off benchmark work, it is acceptable to switch this template during the deploy and update the compatible roster after the result is accepted.

## Benchmark commands

Use the same three benchmark classes as the Qwen3.6 Ollama deployment.

Create the output directory first. The benchmark scripts write JSON files but do not create missing parent directories:

```bash
mkdir -p docs/models/benchmarks/logs/gemma4-26b-ollama
```

### API tool smoke

```bash
python3 scripts/bench/bench_api_tool_call.py \
  --base-url http://<MAC_STUDIO_IP>:11434/v1 \
  --model gemma4:26b \
  --output docs/models/benchmarks/logs/gemma4-26b-ollama/api-tool-test-ollama.json
```

Required gate: 5/5 single-call tool pass and multi-turn loop completes. If this fails, stop and debug the Ollama tag / template / parser before running OpenCode.

### API server throughput

```bash
python3 scripts/bench/bench_api_server.py \
  --base-url http://<MAC_STUDIO_IP>:11434/v1 \
  --model gemma4:26b \
  --contexts 512,4096,8192,32768,65536 \
  --output docs/models/benchmarks/logs/gemma4-26b-ollama/api-server-ollama.json
```

Match the output shape used by `docs/models/benchmarks/logs/qwen36-35b-mlx-ollama/api-server-ollama.json`.

### OpenCode agent benchmark

```bash
python3 scripts/switch_opencode_config.py --server ollama

python3 scripts/bench/bench_agent_tool_call.py \
  --tool opencode \
  --scenario both \
  --warmup 1 \
  --runs 3 \
  --skip-permissions \
  --output docs/models/benchmarks/logs/gemma4-26b-ollama/agent-bench-ollama.json
```

Check `tool_calls_per_run`. For apples-to-apples comparisons with LM Studio Gemma 4 rows, note whether the agent chooses `webfetch` or `task`.

## Success criteria

For `gemma4:26b`, a result is interesting if any of these hold:

- Browse beats LM Studio `gemma4-26b-a4b-huihui-abliterated-q6k` 2.55 s.
- Search beats LM Studio TrevorJS Q8_0 7.35 s or lmstudio-community Q8_0 7.20 s.
- API loop beats 1.93-2.14 s.
- Same-family Ollama tag is close enough while using less memory / simpler deployment.

For `granite4.1:30b-q5_1`, a result is interesting if:

- Browse beats 6.24 s.
- Search beats 10.51 s.
- Tool smoke remains 5/5.

## Documentation update checklist

If a candidate is deployed and benchmarked:

- Raw logs:
  - `docs/models/benchmarks/logs/<slug>/api-tool-test-ollama.json`
  - `docs/models/benchmarks/logs/<slug>/api-server-ollama.json`
  - `docs/models/benchmarks/logs/<slug>/agent-bench-ollama.json`
  - `docs/models/benchmarks/logs/<slug>/summary.md`
- Summary rows:
  - `docs/models/benchmarks/model-benchmark-tool-call.md`
  - `docs/models/benchmarks/model-benchmark-api-server.md`
  - README benchmark headline only if top-tier / notable.
- Catalog:
  - `docs/models/model-summary.md`
  - relevant per-model file if a new variant/gotcha is meaningful:
    - Gemma 4: `docs/models/per-model/model-summary-gemma.md`
    - Granite: `docs/models/per-model/model-summary-granite-4.1.md`
- Server/client docs:
  - `docs/servers/ollama/summary.md`
  - `configs/clients/ollama/opencode.json`
  - `configs/clients/README.md` if compatible roster changes materially.
- Indexes:
  - `docs/models/README.md` only if per-model docs get a new meaningful variant count/description.
  - `plans/README.md` when moving this plan to done/archive.

## Notes for next session

- The completed baseline commit is `4e8e0de Document Ollama Qwen3.6 MLX deployment`.
- Current unrelated working-tree files may exist from earlier work: `docs/servers/sglang/summary.md`, `docs/server-apis/`, `RTK.md`, `huggingface-skills-analysis.md`, `scripts/list_model_to_remove.py`, and `plans/done/plan-list-model-to-remove-python.md`. Do not accidentally include them in an Ollama benchmark commit unless explicitly requested.
- Prefer official Ollama tags first. Exact-GGUF imports are a separate second phase.
