# Running LLM Eval Benchmarks Locally

How to run **MMLU**, **MMLU-Pro**, **TruthfulQA**, **HarmBench**, and **mlabonne/harmful_behaviors** against this stack's OpenAI-compatible endpoints (`llmster :1234`, `vmlx :8000`, etc.) without depending on hosted-only services or an OpenAI API key.

For benchmark *definitions* (what each one measures), see [`docs/models/uncen-model/uncen-model-comparison.md` § Benchmark Glossary](../uncen-model/uncen-model-comparison.md#benchmark-glossary). For the smoke-tests we already run on every deploy (`bench_api_tool_call.py`, `bench_api_server.py`, `bench_agent_tool_call.py`, `refusal_harness.py`), see [`scripts/bench/`](../../../scripts/bench/) and [`docs/models/benchmarks/`](../benchmarks/).

Last updated: 2026-05-03.

## TL;DR — Recommended Tool Set

| Need | Tool | Local-friendly? | Notes |
|:-----|:-----|:----------------|:------|
| MMLU (full + subset) | `EleutherAI/lm-evaluation-harness` | Yes (via `local-completions`) | Needs logprobs from `/v1/completions`; LM Studio is unreliable here ([issue #2934](https://github.com/EleutherAI/lm-evaluation-harness/issues/2934)). vmlx + vllm-mlx do expose them. |
| MMLU-Pro | `chigkim/Ollama-MMLU-Pro` | **Yes — purpose-built for OpenAI-compat local servers** | Regex extraction of letter answer; no judge model. |
| TruthfulQA | `lm-evaluation-harness` `truthfulqa_mc1`/`mc2`/`gen` | Yes | mc1/mc2 = loglikelihood (no judge); `gen` = ROUGE/BLEU/BLEURT (sidesteps OpenAI GPT-judge requirement). |
| HarmBench | `centerforaisafety/HarmBench` `step_2_and_3` | Yes (with monkey-patch) | Last release Feb 2024. Needs OpenAI base_url forwarding patch. Local classifier `cais/HarmBench-Llama-2-13b-cls`. |
| mlabonne/harmful_behaviors | Existing `refusal_harness.py` + Llama-Guard-3-8B sidecar | Yes | Replace keyword-match `refused()` with second-LM-Studio-slot Llama-Guard call. |

There is **no single harness** that covers all five today. `groq/openbench` is the most promising "one tool" candidate but its catalog still lacks HarmBench/MMLU-Pro/TruthfulQA — re-evaluate when 1.0 ships.

---

## MMLU

**Recommendation:** [`EleutherAI/lm-evaluation-harness`](https://github.com/EleutherAI/lm-evaluation-harness) v0.4.11 (Feb 2026, 12.4k stars) — only viable harness for the classic loglikelihood-scoring MMLU.

**Install + run:**
```bash
pip install "lm-eval[api]==0.4.11"

# Full MMLU against llmster (note: requires working /v1/completions logprobs)
lm_eval --model local-completions \
    --model_args model=qwen3.6-35b-a3b-prithiv-aggressive-q6k,base_url=http://<MAC_STUDIO_IP>:1234/v1/completions,num_concurrent=4,tokenized_requests=False,tokenizer_backend=huggingface,tokenizer=Qwen/Qwen3.6-35B-A3B,max_length=4096 \
    --apply_chat_template \
    --tasks mmlu \
    --batch_size 1

# MMLU-200 subset (matches numbers in uncen-model-comparison.md)
lm_eval ... --tasks mmlu --limit 200
```

**Verify logprobs first** — otherwise lm-eval silently falls back to generative scoring:
```bash
curl -s http://<MAC_STUDIO_IP>:1234/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"<served-name>","prompt":"x","logprobs":5,"max_tokens":1}' \
  | python3 -m json.tool
# Expect logprobs.top_logprobs to be a populated array.
```

| Field | Value |
|:------|:------|
| Judge | None (loglikelihood scoring against the 4 letter tokens) |
| Time on llmster (35B MoE @ ~50 tok/s) | Full ~6–10 hr · `--limit 200` ~5–10 min |
| Output | JSON via `--output_path`; per-subject breakdown |
| Caveats | LM Studio's `/v1/completions` logprobs are unreliable. vmlx + vllm-mlx work. `--apply_chat_template` only for instruct models. |
| Refs | [API guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/API_guide.md) · [Doil Kim walkthrough](https://medium.com/@kimdoil1211/evaluating-llm-accuracy-with-lm-evaluation-harness-for-local-server-a-comprehensive-guide-933df1361d1d) · [issue #2934](https://github.com/EleutherAI/lm-evaluation-harness/issues/2934) |

---

## MMLU-Pro

**Recommendation:** [`chigkim/Ollama-MMLU-Pro`](https://github.com/chigkim/Ollama-MMLU-Pro) (111 stars, 55 commits, active) — purpose-built for OpenAI-compatible local servers. Falls back to [`TIGER-AI-Lab/MMLU-Pro/evaluate_from_api.py`](https://github.com/TIGER-AI-Lab/MMLU-Pro/blob/main/evaluate_from_api.py) if you want the official upstream.

**Install + run:**
```bash
git clone https://github.com/chigkim/Ollama-MMLU-Pro.git
cd Ollama-MMLU-Pro
pip install -r requirements.txt

# Edit config.toml:
#   [server]    url = "http://<MAC_STUDIO_IP>:1234/v1"
#               api_key = "lm-studio"
#               model = "qwen3.6-35b-a3b-prithiv-aggressive-q6k"
#   [inference] temperature = 0.0
#               max_tokens = 8000   # IMPORTANT for thinking models
#               style = "multi_chat"
#   [test]      categories = ["math"]   # or omit for all 14
#               subset = 0.05            # smoke; 1.0 for full

python run_openai.py

# Or override on the fly:
python run_openai.py --url http://<MAC_STUDIO_IP>:1234/v1 --model <name> --category math --parallel 4
```

| Field | Value |
|:------|:------|
| Judge | None (regex `r"answer is \(?([A-J])\)?"` + secondary `r"\.*[aA]nswer:\s*\(([A-J])\)"` + random-fallback) |
| Time on llmster | Full 12k q ~6–12 hr · single category ~1 hr · `subset=0.05` ~30 min |
| Output | Per-category JSON + Markdown report; "correct/random-guess/adjusted" scoring |
| Caveats | **Thinking models (Qwen3.6-A3B family) need `max_tokens >= 8000`** — otherwise `</think>` truncates the answer. CoT length variance produces ±2 % score swings between runs at `temperature=0`. |
| Refs | [chigkim repo](https://github.com/chigkim/Ollama-MMLU-Pro) · [TIGER upstream](https://github.com/TIGER-AI-Lab/MMLU-Pro) · [MMLU-Pro-NoMath analysis](https://huggingface.co/blog/sam-paech/mmlu-pro-nomath) · [lm-eval issue #3391](https://github.com/EleutherAI/lm-evaluation-harness/issues/3391) (thinking-model truncation) |

---

## TruthfulQA

**Recommendation:** `lm-evaluation-harness` `truthfulqa_mc1` + `truthfulqa_mc2` (multiple-choice, no judge needed). The original [`sylinrl/TruthfulQA`](https://github.com/sylinrl/TruthfulQA) requires an OpenAI fine-tuned `GPT-judge` for the generative task — downrank.

**Install + run:**
```bash
# MC tasks (fast, no judge needed)
lm_eval --model local-completions \
    --model_args model=<served-name>,base_url=http://<MAC_STUDIO_IP>:1234/v1/completions,tokenizer=<hf-id>,tokenized_requests=False \
    --tasks truthfulqa_mc1,truthfulqa_mc2 \
    --num_fewshot 0 --batch_size 1

# Generative task — sidesteps GPT-judge with ROUGE/BLEU/BLEURT
lm_eval --model local-chat-completions \
    --model_args model=<served-name>,base_url=http://<MAC_STUDIO_IP>:1234/v1/chat/completions \
    --tasks truthfulqa_gen \
    --apply_chat_template
```

For BLEURT scoring on `truthfulqa_gen`: `pip install bleurt` + downloaded checkpoint (~500 MB).

| Field | Value |
|:------|:------|
| Judge | mc1/mc2 = none. `truthfulqa_gen` = BLEURT/ROUGE/BLEU (no judge), or wire Hermes 4 70B as a [JailbreakBench-style](https://github.com/JailbreakBench/jailbreakbench) `Llama3RefusalJudge` if you want LLM-as-judge. |
| Time on llmster | 817 q × 2 tasks ≈ 15–30 min |
| Caveats | mc2 needs logprobs (same `/v1/completions` gotcha as MMLU). `truthfulqa_gen` ROUGE is noisier than GPT-judge but acceptable for relative ranking. |
| Refs | [lm-eval truthfulqa README](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/truthfulqa/README.md) · [sylinrl upstream](https://github.com/sylinrl/TruthfulQA) |

---

## HarmBench

**Recommendation:** [`centerforaisafety/HarmBench`](https://github.com/centerforaisafety/HarmBench) (938 stars). **Maintenance flag:** last release Feb 2024, 30 open issues — community has somewhat moved on, but the classifier model is still the gold standard local judge for refusal-robustness work. Use `step_2_and_3` (skip attacks; just generate completions + classify).

**Install + run:**
```bash
git clone https://github.com/centerforaisafety/HarmBench && cd HarmBench
pip install -r requirements.txt && python -m spacy download en_core_web_sm

# Add to configs/model_configs/models.yaml:
#   llmster_main:
#     model:
#       model_name_or_path: qwen3.6-35b-a3b-prithiv-aggressive-q6k
#       token: lm-studio
#       base_url: http://<MAC_STUDIO_IP>:1234/v1
#     model_type: open_ai_chat

# Patch baselines/openai_models.py to forward base_url=os.getenv("OPENAI_BASE_URL")
# (the shipped open_ai_chat adapter ignores base_url today — see Caveats)

python ./scripts/run_pipeline.py \
    --methods DirectRequest \
    --models llmster_main \
    --step 2_and_3 \
    --mode local

# Or just run the classifier on existing completions:
./scripts/evaluate_completions.sh \
    cais/HarmBench-Llama-2-13b-cls \
    data/behaviors/harmbench_behaviors_text_val.csv \
    <completions.json> \
    <save.json>
```

| Field | Value |
|:------|:------|
| Judge | [`cais/HarmBench-Llama-2-13b-cls`](https://huggingface.co/cais/HarmBench-Llama-2-13b-cls) — 13 B fp16 ≈ 26 GB or 4-bit ≈ 8 GB, fits on M3 Ultra. Lighter alt: `cais/HarmBench-Mistral-7b-val-cls` (~14 GB fp16). |
| Time on llmster | 400 behaviors × ~30 s gen + ~5 s classify ≈ 3–4 hr · validation subset (~80) ≈ 40 min |
| Output | Per-behavior CSV + classifier JSON |
| Caveats | The shipped `open_ai_chat` adapter does NOT forward `base_url` — must edit `baselines/openai_models.py` to read `OPENAI_BASE_URL` env var. Not pip-installable as-is. Working alternative: [Promptfoo HarmBench guide](https://www.promptfoo.dev/docs/guides/evaling-with-harmbench/) wraps the eval differently. Use `harmbench_behaviors_text_val.csv` (40 behaviors) as the cheapest meaningful smoke before the full 400. |
| Refs | [evaluation_pipeline.md](https://github.com/centerforaisafety/HarmBench/blob/main/docs/evaluation_pipeline.md) · [run_classifier.ipynb](https://github.com/centerforaisafety/HarmBench/blob/main/notebooks/run_classifier.ipynb) · [classifier model card](https://huggingface.co/cais/HarmBench-Llama-2-13b-cls) · [Promptfoo guide](https://www.promptfoo.dev/docs/guides/evaling-with-harmbench/) |

---

## mlabonne/harmful_behaviors (Refusal Rate)

We already run a 10-prompt subsample with keyword-match scoring via [`refusal_harness.py`](file:///Users/chanunc/.claude/skills/deploy-run-benchmark-uncen-model/refusal_harness.py). The community-standard upgrades, in order of pragmatism:

1. **Llama Guard 3 8B as drop-in judge** — easiest evolution path. Load [`meta-llama/Llama-Guard-3-8B`](https://huggingface.co/meta-llama/Llama-Guard-3-8B) (Q4_K_M ≈ 5 GB) as a second model in LM Studio on the same `:1234` endpoint. Replace `refused()` in the harness with an HTTP call sending `(prompt, response)` as the Llama-Guard chat template; parse first token (`safe` / `unsafe`). Outputs the violated S1–S13 MLCommons category for free. Eliminates false-positives on responses like "Here's a safer alternative…" that the keyword list misses.
2. **JailbreakBench published prompts** — [`JailbreakBench/jailbreakbench`](https://github.com/JailbreakBench/jailbreakbench) (584 stars) ships `Llama3JailbreakJudge` (70B) + `Llama3RefusalJudge` (8B) prompts as plain text. The 8B variant is what underlies option 1 above.
3. **StrongREJECT rubric judge** — [`dsbowen/strong_reject`](https://github.com/dsbowen/strong_reject) (136 stars, active). Rubric scores refusal + specificity + convincingness 0–1. The fine-tuned-Gemma-2B judge variant runs locally; the rubric judge is GPT-4-by-default but the prompt is open-source — point it at Hermes 4 70B on llmster by setting `OPENAI_API_BASE=http://<MAC_STUDIO_IP>:1234/v1`. Captures partial-compliance that keyword-match misses ([HarmMetric Eval paper](https://arxiv.org/pdf/2509.24384)).
4. **HarmBench classifier as gold standard** — `cais/HarmBench-Llama-2-13b-cls` (option from the HarmBench section above) gives binary yes/no per (behavior, completion); ~93 % human-label agreement.

**Recommended drop-in upgrade for `refusal_harness.py`:** replace the `REFUSAL_PHRASES` list + `refused()` function with an HTTP call to a second LM Studio model serving Llama-Guard-3-8B. Treat `unsafe` token as "complied with harmful request", `safe` as refusal/redirection. Persist the upgraded scores to `docs/models/benchmarks/<slug>/refusal-rate-llamaguard-llmster.json` alongside the existing keyword-match JSON for cross-validation during the transition.

---

## Cross-Cutting Notes

### Judge-model strategy on this stack

The current llmster main (`prithivMLmods Aggressive Q6_K`) is **not** suitable as a judge — it has been refusal-tuned out of, so it scores everything as "complied". The right pattern:

- **Llama-Guard-3-8B** (~5 GB Q4_K_M) on a second LM Studio slot — for refusal/safety scoring.
- **Hermes 4 70B** (already on disk, ~40 GB Q4) on a third LM Studio slot — for StrongREJECT rubric grading and TruthfulQA-gen LLM-as-judge if you want to substitute for GPT-4.
- **`cais/HarmBench-Llama-2-13b-cls`** (~8 GB Q4) — for HarmBench step 3 + cross-validation of the Llama-Guard scores.

LM Studio routes `chat.completions` by the `model` field, so all three judges can co-exist on `:1234` as separate model names. Memory: 5 + 40 + 8 = 53 GB — leaves ~30 GB on the M3 Ultra 96 GB box for the model under test, which is fine for any 35B-class target.

### First-week MVP plan for llmster prithivMLmods

1. **Day 1 (1 hr):** Verify `/v1/completions` logprobs work on LM Studio (curl test in MMLU section). If yes → run `lm_eval --tasks mmlu --limit 200 --num_fewshot 5` for an MMLU-200 number that matches the existing `uncen-model-comparison.md` table.
2. **Day 1–2 (4 hrs):** Run `chigkim/Ollama-MMLU-Pro` with `subset = 0.1` (1200 q smoke) → calibrate `max_tokens`/`parallel` → kick off full 12 k overnight.
3. **Day 2 (30 min):** Run `lm_eval --tasks truthfulqa_mc1,truthfulqa_mc2,truthfulqa_gen --metric rouge,bleu` (no judge needed for mc1/mc2; ROUGE for gen).
4. **Day 3 (1 hr setup + overnight):** Drop `refusal_harness.py` from 10 → 520 prompts, add Llama-Guard-3-8B sidecar judge. Persist to `docs/models/benchmarks/<slug>/refusal-rate-llamaguard-llmster.json`. Replaces ~80 % of HarmBench's signal at ~5 % the operational cost.
5. **Day 4–5 (4 hrs):** Run HarmBench `step_2_and_3` on the 40-behavior `_val` CSV with the local classifier as the gold standard. Only escalate to the 400-prompt full set if val results are surprising.

### Logprobs reality check

The single biggest gotcha across MMLU + TruthfulQA-mc is whether your server returns usable token logprobs on `/v1/completions`:

| Server | Logprobs on `/v1/completions` | Notes |
|:-------|:-------------------------------|:------|
| llmster (LM Studio) | ⚠ Unreliable — [issue #2934](https://github.com/EleutherAI/lm-evaluation-harness/issues/2934) | Falls back to generative scoring silently. Verify before every benchmark run. |
| vmlx | ✅ Yes | OpenAI-compatible end-to-end. |
| vllm-mlx | ✅ Yes | Standard. |
| dflash-mlx | Unknown — verify | Wraps `mlx_lm.server`; should inherit. |
| mlx-openai-server | ✅ Yes | Standard. |

For MMLU on llmster specifically, you may need to either (a) accept the generative-scoring fallback (and re-baseline your numbers against community generative-MMLU scores, not loglikelihood-MMLU scores), or (b) load the same model on vmlx for the MMLU pass only.

---

## See Also

- [`docs/models/uncen-model/uncen-model-comparison.md` § Benchmark Glossary](../uncen-model/uncen-model-comparison.md#benchmark-glossary) — what each benchmark measures, scale, interpretation
- [`scripts/bench/`](../../../scripts/bench/) — the inference-harness benchmarks we run on every deploy (tool-call smoke, throughput, agent loop)
- [`~/.claude/skills/deploy-run-benchmark-uncen-model/refusal_harness.py`](file:///Users/chanunc/.claude/skills/deploy-run-benchmark-uncen-model/refusal_harness.py) — current keyword-match refusal harness; recommended evolution: Llama-Guard-3-8B HTTP judge as a second LM Studio model slot
- [`docs/models/benchmarks/`](../benchmarks/) — raw bench JSONs + per-benchmark cross-model summaries
