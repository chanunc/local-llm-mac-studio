# Plan: `bench_eval_local.py` — MMLU-Pro + TruthfulQA-gen Driver

Status: active
Created: 2026-05-03
Canonical: no

## Context

**Why now:** The `MMLU` and `TruthfulQA` columns in `docs/models/uncen-model/uncen-model-comparison.md` are empty for every GGUF uncen model on disk (prithivMLmods Aggressive Q6_K, HauhauCS Aggressive Q6_K_P, HauhauCS Balanced Q8_K_P). We have strong refusal-axis numbers for these models (`mlabonne 10/520` complied) but zero capability/factuality data — every row is **half-validated** (per `docs/models/uncen-model/uncen-model-bench-methods-compare.md`).

**The cheapest gap-closer:** MMLU-Pro `subset=0.05` (~30 min wall on llmster's 35B MoE) gives a regression check on knowledge; TruthfulQA-gen (~15-30 min, ROUGE/BLEU only — no judge) gives a factuality check. Both use scoring methods (regex / ROUGE) that **do not require `/v1/completions` logprobs**, so they work cleanly on llmster despite [lm-eval issue #2934](https://github.com/EleutherAI/lm-evaluation-harness/issues/2934) (LM Studio's logprobs gotcha).

**Outcome:** one Python driver in `scripts/bench/` that wraps both tools, emits one merged JSON in our standard envelope, fills the gap for three models in ~90 min total wall time.

## Recommended approach

**One Python script** — `scripts/bench/bench_eval_local.py` — that shells out to two pre-installed external tools and merges their JSON output. Python (not bash) for consistency with every other script in `scripts/bench/`, and because JSON merging + aggregate extraction is painful in shell.

### Pre-conditions (fail-fast at script start)

1. `~/eval-tools/Ollama-MMLU-Pro/run_openai.py` exists. (Currently does NOT — install: `git clone https://github.com/chigkim/Ollama-MMLU-Pro.git ~/eval-tools/Ollama-MMLU-Pro && (cd $_ && pip install -r requirements.txt)`.)
2. `lm_eval --help` exits 0. (Currently does NOT — install: `pip install "lm-eval[api]==0.4.11"`.)
3. `GET <base-url>/models` reachable in 10 s.
4. **Verification step before writing the script:** confirm `Ollama-MMLU-Pro/run_openai.py` actually accepts the CLI flags the design assumes (`--url`, `--model`, `--api_key`, `--category`, `--parallel`, `--subset`, `--max_tokens`, `--temperature`, `--style`, `--output_dir`). Run `python3 ~/eval-tools/Ollama-MMLU-Pro/run_openai.py --help` after install and adjust the subprocess command if any flag name differs. If the tool only accepts `config.toml`, fall back to generating a temp toml per run.

### CLI surface (mirrors `bench_api_server.py:99-109` + `refusal_harness.py:75-82`)

| Flag | Type | Default | Notes |
|:-----|:-----|:--------|:------|
| `--base-url` | required | — | `http://192.168.31.4:1234/v1` |
| `--model` | required | — | served name |
| `--api-key` | str | `None` | passed to both tools (defaults to `lm-studio` for MMLU-Pro if unset) |
| `--output` | required | — | merged JSON path |
| `--server-label` | str | `"unknown"` | echoed into `config.server_label` |
| `--mmlu-subset` | float | `0.05` | MMLU-Pro `--subset` |
| `--mmlu-max-tokens` | int | `8000` | clamp to `max(arg, 8000)` — thinking models truncate `</think>` below this |
| `--mmlu-categories` | str | `None` | comma list → repeated `--category` |
| `--mmlu-parallel` | int | `4` | MMLU-Pro `--parallel` |
| `--mmlu-timeout` | int | `3600` | subprocess timeout (s) |
| `--tqa-timeout` | int | `1800` | subprocess timeout (s) |
| `--skip-mmlu` / `--skip-truthfulqa` | flag | `False` | partial run |
| `--eval-tools-dir` | str | `~/eval-tools` | base for tool checkouts |
| `-v / --verbose` | flag | — | stream subprocess stdout |

### Subprocess invocations

**MMLU-Pro** — CLI overrides only (no temp config.toml, assuming pre-condition 4 passes):
```python
subprocess.run([
    sys.executable, "run_openai.py",
    "--url", args.base_url, "--model", args.model,
    "--api_key", args.api_key or "lm-studio",
    "--parallel", str(args.mmlu_parallel),
    "--subset", str(args.mmlu_subset),
    "--max_tokens", str(mmlu_max_tokens),
    "--temperature", "0.0", "--style", "multi_chat",
    "--output_dir", mmlu_out_dir,
] + repeated_category_flags,
cwd=eval_tools_dir / "Ollama-MMLU-Pro",
capture_output=True, text=True, timeout=args.mmlu_timeout)
```
Glob `<output_dir>/<model-slug>/report.json` → extract `overall.accuracy` + `categories[*].accuracy`.

**TruthfulQA-gen** — `local-chat-completions` (no tokenizer required, matches our chat-only LM Studio target):
```python
subprocess.run([
    "lm_eval",
    "--model", "local-chat-completions",
    "--model_args", f"model={args.model},base_url={args.base_url}/chat/completions,num_concurrent=4,max_retries=3"
                    + (f",api_key={args.api_key}" if args.api_key else ""),
    "--tasks", "truthfulqa_gen",
    "--apply_chat_template",
    "--output_path", tqa_out_dir,
    "--log_samples",
], capture_output=True, text=True, timeout=args.tqa_timeout)
```
Parse `<tqa_out_dir>/<sanitized-model>/results_<ts>.json` → `results.truthfulqa_gen.{rouge1,rouge2,rougeL,bleu_acc,bleu_diff}` + `n-samples`.

**Error capture** — mirror `bench_agent_tool_call.py:174-191`. Wrap each subprocess in try/except `TimeoutExpired`, set `exit_code = -1` on timeout, capture stderr tail (last 2 KB) into the merged JSON. Driver exits `0` if at least one bench succeeded, `1` only if both failed.

### Output JSON shape (merged envelope)

Saved to `args.output` (e.g., `docs/models/benchmarks/qwen36-35b-a3b-prithiv-aggressive/eval-local-llmster.json` — matches `agent-bench-llmster.json` per-server naming). Plus two siblings for forensic deep-dives: `<output>.mmlu-raw.json` and `<output>.tqa-raw.json` (verbatim copies of each tool's native JSON).

```json
{
  "benchmark": "eval-local",
  "version": "1.0",
  "timestamp": "2026-05-03T10:42:11+00:00",
  "config": {
    "base_url": "http://192.168.31.4:1234/v1",
    "model": "qwen3.6-35b-a3b-prithiv-aggressive-q6k",
    "server_label": "llmster (LM Studio headless)",
    "mmlu_subset": 0.05, "mmlu_max_tokens": 8000,
    "mmlu_categories": null, "mmlu_parallel": 4,
    "tools": {
      "ollama_mmlu_pro_path": "/Users/chanunc/eval-tools/Ollama-MMLU-Pro",
      "lm_eval_version": "0.4.11"
    }
  },
  "results": {
    "mmlu_pro": {
      "score": 0.612,
      "by_category": {"math": 0.58, "physics": 0.64, "...": "..."},
      "n_questions": 602, "wall_time_s": 1742.3,
      "raw_path": "...eval-local-llmster.json.mmlu-raw.json",
      "exit_code": 0
    },
    "truthfulqa_gen": {
      "rouge1": 0.41, "rouge2": 0.27, "rougeL": 0.38,
      "bleu_acc": 0.49, "bleu_diff": 0.06,
      "n_questions": 817, "wall_time_s": 1183.6,
      "raw_path": "...eval-local-llmster.json.tqa-raw.json",
      "exit_code": 0
    }
  }
}
```

Partial-failure shape (one tool errored): replace the failed tool's block with `{"error": "...", "exit_code": -1, "stderr_tail": "...", "wall_time_s": ...}`.

### Documentation updates (post-script)

1. `scripts/README.md` — add Bench table row pointing to the new script.
2. `docs/models/how-to/eval-benchmark-local-runners.md` — append a **"Driver script"** subsection after the MMLU-Pro and TruthfulQA sections, with one example invocation. Cross-link both ways (driver docstring → doc, doc → driver).
3. `plans/README.md` — add this plan to the Active index (Sync Policy Event 6).
4. **No skill change.** `~/.claude/skills/deploy-run-benchmark-uncen-model/SKILL.md` stays untouched. Track follow-up: add `--with-eval` opt-in flag in a separate plan once the driver is proven (avoids doubling the 25-40 min skill wall).

### Critical files

- **New:** `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_eval_local.py`
- **Reference (envelope shape, `--output` write):** `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_api_server.py:99-176`
- **Reference (subprocess + timeout + per-task error capture):** `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_agent_tool_call.py:155-210`
- **Reference (CLI flags + JSON shape sibling):** `/Users/chanunc/.claude/skills/deploy-run-benchmark-uncen-model/refusal_harness.py:75-136`
- **Doc updates:** `scripts/README.md`, `docs/models/how-to/eval-benchmark-local-runners.md`, `plans/README.md`
- **Cross-link target:** `docs/models/uncen-model/uncen-model-bench-methods-compare.md` (the new doc that motivates this script)

## Verification

End-to-end smoke test on llmster (~30-40 min wall):

```bash
# Pre-condition (one-time, NOT auto-installed):
git clone https://github.com/chigkim/Ollama-MMLU-Pro.git ~/eval-tools/Ollama-MMLU-Pro
(cd ~/eval-tools/Ollama-MMLU-Pro && pip install -r requirements.txt)
pip install "lm-eval[api]==0.4.11"

# Smoke against the current llmster main:
python3 /Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_eval_local.py \
  --base-url http://192.168.31.4:1234/v1 \
  --model qwen3.6-35b-a3b-prithiv-aggressive-q6k \
  --api-key lm-studio \
  --server-label "llmster (LM Studio headless)" \
  --output /Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/models/benchmarks/qwen36-35b-a3b-prithiv-aggressive/eval-local-llmster.json \
  -v
```

**Acceptance:**
1. Exit `0`; merged JSON validates against the example shape above.
2. `results.mmlu_pro.score` ∈ `[0.0, 1.0]`, `n_questions ≈ 600` (12 k × 0.05).
3. `results.truthfulqa_gen.rouge1` ∈ `[0.0, 1.0]`, `n_questions == 817`.
4. Both `*.mmlu-raw.json` + `*.tqa-raw.json` siblings exist and are non-empty.
5. Wall time < 40 min total (sanity cap; if > 50 min, bump `--mmlu-parallel` next run).
6. Partial-failure smoke: re-run with `--skip-truthfulqa` → JSON has only `mmlu_pro` under `results`, exit `0`.

**Then repeat for HauhauCS Aggressive + HauhauCS Balanced** (each ~30-40 min, both already on disk and reloadable per `docs/current.md` Stopped/Fallbacks). Three runs total (~90-120 min) populate the `MMLU` and `TruthfulQA` columns for half the comparison table.

**Out of scope** (explicit non-goals — defer):
- Auto-install of external tools (fail-fast with instructions only).
- Skill integration (separate `--with-eval` plan after driver is proven).
- HarmBench (separate driver — needs `cais/HarmBench-Llama-2-13b-cls` classifier sidecar).
- BLEURT scoring on TruthfulQA-gen (defer; ROUGE/BLEU sufficient).
- Logprobs pre-check (irrelevant for these two benches; document its absence so future maintainers don't add it).
