# Doom Loop — Repetition Failure in Edge / Small Reasoning Models

**Status:** known-issue notebook
**Created:** 2026-05-06
**Affects on this stack:** Qwen3.5 / Qwen3.6 family thinking variants on `mlx-openai-server`, `dflash-mlx`, and `oMLX`. Filed against our `oMLX` deployment as [`jundot/omlx#934`](https://github.com/jundot/omlx/issues/934). Relevant to any future Liquid LFM2.x deploy.

---

## TL;DR

A *doom loop* is what happens when a small reasoning model gets stuck in a repetitive text pattern instead of finishing — re-emitting the same n-gram, the same chain-of-thought fragment, or the same character (`!!!!!!!!!!`, ``````, …) until it hits the token cap. It is **disproportionately a small-model failure**: Maxime Labonne (Liquid AI, Head of Pre-training) reports the doom-loop ratio on **LFM 2.5 1.2B Thinking** at **15.74%** out of mid-training, dropping to **0.36%** only after a dedicated DPO + RLVR pipeline. He claims the equivalent reasoning-mode Qwen3.5 small model loops on **>50%** of hard tasks.

This document catalogs (1) the exact framing from his AI Engineer 2026-04-29 talk, (2) corroborating evidence from the bug trackers, (3) the testing methodology nobody fully publishes, and (4) what to add to our own benchmark rig under `docs/models/benchmarks/`.

---

## 1. Source — Maxime Labonne, Liquid AI

**Talk:** *Everything I Learned Training Frontier Small Models* — AI Engineer (2026-04-29, 20:13). [YouTube](https://youtu.be/fLUtUkqYHnQ) · [slides on X](https://x.com/maximelabonne/status/2042537534031343633).

### What he said (verbatim)

> "There's a new problem with small language models that you might have encountered even with bigger ones, and this is **doom looping**. … It's going to start repeating a sequence of words over and over and over again, and it just like never stops."
>
> "This is a problem all the time, but it's particularly a problem if you have **small models, reasoning models, and complex tasks**. If you have a tiny reasoning model on like super difficult math task, this is the **perfect recipe to have a lot of doom loops**."
>
> "If today you try to do the same thing with **Qwen 3.5 0.8B in reasoning mode, you will see a lot a lot a lot of doom loops, like over 50%** … which is something that **people complain about online** … that also shows that Qwen 3.5 small is **just a scaled-down version of bigger models**."

The talk closes on this as the punchline: edge models are not little big models — doom looping is the signature failure that proves it.

### His two-pronged fix

| # | Stage | Mechanism |
|---|---|---|
| **1** | **Preference alignment (DPO)** | Generate **5 temperature-sampled rollouts + 1 greedy (T=0)** rollout per prompt → LLM-as-jury scores them → best = chosen, worst (or any looping one) = rejected. |
| **2** | **RLVR (RL with verifiable rewards) + n-gram repetition penalty** | A doom-looped trace can't extract a final answer → no positive reward. Adds a soft n-gram penalty so loops are dispreferred even on the way to the answer. |

### The numbers from LFM 2.5 1.2B Thinking

| Stage | Doom-loop ratio |
|---|---|
| Mid-training | **15.74%** |
| SFT | 14.98% (barely moved) |
| DPO | 4.32% |
| **RLVR** | **0.36%** |

Source: [Liquid AI blog — LFM2.5-1.2B-Thinking](https://www.liquid.ai/blog/lfm2-5-1-2b-thinking-on-device-reasoning-under-1gb). The [LFM2 Technical Report (arXiv 2511.23404)](https://arxiv.org/abs/2511.23404) does **not** include this analysis.

---

## 2. Corroborating evidence

### GitHub — what Maxime meant by "people complain about online"

| Issue | Behavior |
|---|---|
| [QwenLM/Qwen3.6 #145](https://github.com/QwenLM/Qwen3.6/issues/145) | Qwen3.5 series enters infinite loop in reasoning with vendor-recommended sampling parameters. |
| [QwenLM/Qwen3.6 #88](https://github.com/QwenLM/Qwen3.6/issues/88) | On LiveCodeBench: **17.4%** of Qwen3.5-35B-A3B outputs had truncated thinking, **84% of those had >30% repetition** — same order of magnitude as Liquid's mid-training 15.74%. |
| [QwenLM/Qwen3-VL #1611](https://github.com/QwenLM/Qwen3-VL/issues/1611) | "Infinite repetition bug still exists." |
| [anomalyco/opencode #25129](https://github.com/anomalyco/opencode/issues/25129) | Qwen 3.6 thinking emits `!!!!!!!!!!` indefinitely. |
| [anomalyco/opencode #22142](https://github.com/anomalyco/opencode/issues/22142) | Repetitive tool-call loops with `qwen3.6-plus`. |
| [lmstudio-ai bug #1018](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1018) | "Reasoning never ends in qwen3 thinking models." Workaround: llama.cpp `--reasoning-budget 4096`. |
| [ollama/ollama #14421](https://github.com/ollama/ollama/issues/14421) | qwen3.5:35b looping issue. |
| [ollama/ollama #14493](https://github.com/ollama/ollama/issues/14493) | Qwen 3.5 27B repetition penalties silently ignored. |
| **[jundot/omlx #934](https://github.com/jundot/omlx/issues/934)** | **qwen3.6-35b-a3b infinite loop on our exact server stack.** |
| [HF Qwen3.6-35B-A3B disc #19](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/19) | "Endless reasoning loops." |
| [HF Qwen3.6-35B-A3B disc #20](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/20) | "Poor tools use and endless reasoning loop." |

### Vendor-recommended sampling (workaround, not a fix)

From [unsloth's Qwen3.5 docs](https://unsloth.ai/docs/models/qwen3.5) and the issue threads, Qwen recommends:

```
# Reasoning mode (Qwen3.5-122B-A10B, etc.)
temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
presence_penalty=1.5, repetition_penalty=1.0
```

Reporters consistently note `presence_penalty=1.5` is "silently ignored" by some inference stacks (e.g. ollama #14493). On our stack, set it explicitly in the OpenCode/Claude Code client and verify with `/v1/chat/completions` payload inspection — don't trust the default.

### Mechanism (academic)

- [LZ Penalty (arXiv 2504.20131)](https://arxiv.org/html/2504.20131v2) — n-gram-sliding-window repetition penalty designed so reasoning models can run **greedy** without degenerating. This is the published version of what Liquid calls their "n-gram-based repetition penalty."
- [Solving LLM Repetition Problem in Production (arXiv 2512.04419)](https://arxiv.org/html/2512.04419v1) — *"DPO fine-tuning offers a universal model-level solution"*, contrasting chosen non-repetitive vs. rejected repetitive responses. Exactly Liquid's solution #1.
- [OpenReview — Understanding Looping in Reasoning Models](https://openreview.net/forum?id=lPwsHTEPQ9) — formal periodicity score `Srep`, alarm when `Srep > S_th`.
- [Sebastian Raschka FAQ](https://sebastianraschka.com/faq/docs/repetition-loops-generation.html) — clean intuition: "Text generation is a local next-token process. Repetition occurs when local next-token choices start reinforcing the same pattern, especially under low-diversity decoding."

---

## 3. Testing methodology

There is **no canonical doom-loop benchmark**. Liquid's blog and tech report only say "*n-gram-based … on a dataset of representative prompts*" without specifying window size, threshold, prompt list, or judge. The 15.74% → 0.36% chart is a relative reduction, not a reproducible number.

The community has converged on **two distinct layers**, depending on what you're measuring.

### Layer 1 — Generation-side (text-level) loop detection

Matches Maxime's percentages. Pick one of:

**a. N-gram blocking / sliding-window count** (simplest, what Liquid implies)
- Pick `n` (typically **3–5 tokens**).
- Slide a window over the generated sequence.
- Flag the trace if any n-gram repeats **≥ K times** (typical K = 3–4), or compute `repetition_ratio = repeated_ngrams / total_ngrams`.
- Trace is "doom-looped" if `ratio > τ` (e.g. **>30%** — Qwen #88's threshold).

**b. LZ-penalty / compressibility** ([arXiv 2504.20131](https://arxiv.org/html/2504.20131v2))
- Compressibility under an LZ77 dictionary > τ ⇒ loop.
- Designed for greedy decoding without degeneration.

**c. Periodicity score Srep** ([OpenReview](https://openreview.net/forum?id=lPwsHTEPQ9))
- For perfect repetition with period P, `Srep ≈ 1`; for random sequences, `Srep ≈ 0`.
- Alarm when `Srep > S_th`, threshold `S_th ∈ (0, 1)`.

**d. Truncation-as-proxy** (operational, cheap)
- Run with a fixed `max_tokens` cap.
- If the model **hits the cap without emitting `</think>` or a final-answer tag**, count it as looped.
- Used in the Qwen #88 LiveCodeBench analysis. Same idea as llama.cpp's `--reasoning-budget`.

**Reproduction recipe matching Liquid's framing:**

```
prompts:    100–500 hard math + agentic prompts
            (AIME slice, BFCL hard subset, our existing agent bench)
decode:     temperature per model card, max_tokens=16384
detector:   any 4-gram repeats ≥ 4× consecutively in the last 1024 tokens
            OR generation hit max_tokens without final-answer tag
            OR repetition_ratio > 0.30
ratio:      flagged_traces / total_traces
```

This will reproduce the **15–16% → 0.4%** order of magnitude on Qwen3.5/3.6 thinking models.

### Layer 2 — Agent-side (tool-call-level) loop detection

Runtime guard, not a model-quality measurement. What OpenCode / PraisonAI / Cursor use to short-circuit a stuck model in production.

| Implementation | Window | Match | Trigger |
|---|---|---|---|
| [OpenCode PR #3445](https://github.com/anomalyco/opencode/pull/3445) | last **3** tool calls | `tool_name` + `JSON.stringify(args)` exact match | 3 consecutive identical → inject "try a different approach" |
| [OpenCode PR #12623](https://github.com/anomalyco/opencode/pull/12623) | per-turn output | reasoning/output text duplication | hard cap |
| [PraisonAI doom-loop docs](https://docs.praison.ai/docs/features/doom-loop-detection) | history of **30** calls | exact `(tool, args)`; plus *Poll-No-Progress* (`args + result` unchanged) and *Ping-Pong* (A→B→A→B) | warn at **10**, block at **20** |

These detectors don't measure model quality — they measure *agent behavior* — and are complementary to Layer 1, not competing.

---

## 4. What to add to our bench rig

If we want to add a `doom_loop_ratio` column to the existing benchmark write-ups under [`../benchmarks/`](../benchmarks/) (alongside browse/search timings):

1. **Prompt set:** ~50 hard prompts from the existing agent benchmark under `scripts/bench/`.
2. **Cap:** `max_tokens=16384`, temperature per the model's recommended sampling card.
3. **Detector** — run two checks per trace and OR them:
   - **No-progress:** trace ends without an answer extractable by the benchmark's grader.
   - **Repetition:** any 4-gram repeats ≥ 4× consecutively, or last 256 tokens have <30 unique tokens.
4. **Score:** `doom_loop_ratio = flagged / total`.

This is portable across `vllm-mlx`, `mlx-lm server`, `mlx-openai-server`, `dflash-mlx`, and `oMLX`. Costs no extra inference (runs over traces we'd be capturing anyway). Would let us reproduce the 15.74% → 0.36% chart for any model on the lab — and would catch the Qwen3.6 issue already filed as [`jundot/omlx#934`](https://github.com/jundot/omlx/issues/934) before it bites a benchmark.

### Why this matters for the lab

- The [DFlash sidecar](../../../docs/servers/) target is `mlx-community/Qwen3.6-35B-A3B-4bit` — exactly the family Maxime singled out as a doom-loop offender.
- Qwen3.5/3.6 thinking models are repeatedly evaluated on `mlx-openai-server` and `oMLX`. Without a doom-loop column, agentic benchmarks under-report: a "slow" model may actually be a *looped* model that the wall-clock cap eventually killed.
- Future Liquid LFM2.x deploy is the natural counter-example — should benchmark to ~0.4% if Liquid's claims hold.

---

## 5. Cross-references

- [`../per-model/model-summary-qwen-3-5.md`](../per-model/model-summary-qwen-3-5.md) — Qwen3.5 family deployment notes.
- [`../per-model/model-summary-qwen-3-6.md`](../per-model/model-summary-qwen-3-6.md) — Qwen3.6 family deployment notes.
- [`../benchmarks/model-benchmark-tool-call.md`](../benchmarks/model-benchmark-tool-call.md) — OpenCode agent loop benchmark (target for the new `doom_loop_ratio` column).
- [`../techniques/`](../techniques/) — inference-side techniques folder; an n-gram penalty / LZ-penalty note belongs here if we ever implement it as a runtime knob.

## Sources

**Primary**
- [Maxime Labonne talk — *Everything I Learned Training Frontier Small Models*](https://youtu.be/fLUtUkqYHnQ)
- [Maxime Labonne on X — slides + "solution to fix doom loops"](https://x.com/maximelabonne/status/2042537534031343633)
- [Liquid AI blog — LFM2.5-1.2B-Thinking](https://www.liquid.ai/blog/lfm2-5-1-2b-thinking-on-device-reasoning-under-1gb)
- [LFM2 Technical Report (arXiv 2511.23404)](https://arxiv.org/abs/2511.23404)
- [ZenML LLMOps Database — Liquid AI: Pre-training and Deploying SLMs for Edge](https://www.zenml.io/llmops-database/pre-training-and-deploying-small-language-models-for-edge-devices)

**GitHub bug tracker**
- [QwenLM/Qwen3.6 #145](https://github.com/QwenLM/Qwen3.6/issues/145)
- [QwenLM/Qwen3.6 #88](https://github.com/QwenLM/Qwen3.6/issues/88)
- [QwenLM/Qwen3-VL #1611](https://github.com/QwenLM/Qwen3-VL/issues/1611)
- [anomalyco/opencode #25129](https://github.com/anomalyco/opencode/issues/25129)
- [anomalyco/opencode #22142](https://github.com/anomalyco/opencode/issues/22142)
- [lmstudio-ai bug #1018](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1018)
- [ollama/ollama #14421](https://github.com/ollama/ollama/issues/14421)
- [ollama/ollama #14493](https://github.com/ollama/ollama/issues/14493)
- [jundot/omlx #934](https://github.com/jundot/omlx/issues/934)
- [HF Qwen3.6-35B-A3B disc #19](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/19) · [#20](https://huggingface.co/Qwen/Qwen3.6-35B-A3B/discussions/20)
- [Cursor forum — false-positive loop detection on qwen3-coder-plus](https://forum.cursor.com/t/false-positive-loop-detection-when-using-custom-model-qwen3-coder-plus-with-repetitive-reasoning-text-before-different-tool-calls/145252)

**Detection algorithms / mechanism**
- [arXiv 2504.20131 — LZ Penalty](https://arxiv.org/html/2504.20131v2)
- [arXiv 2512.04419 — Solving LLM Repetition Problem in Production](https://arxiv.org/html/2512.04419v1)
- [OpenReview — Understanding Looping in Reasoning Models](https://openreview.net/forum?id=lPwsHTEPQ9)
- [OpenReview — Monitor Degenerative Repetition in LLM Agents](https://openreview.net/pdf/c24d56b3bd8a29f19e0d1773c2548d1d41f29d86.pdf)
- [arXiv 2510.15061 — Antislop framework](https://arxiv.org/pdf/2510.15061)
- [Michael Brenndoerfer — Repetition Penalties (interactive)](https://mbrenndoerfer.com/writing/repetition-penalties-language-model-generation)
- [Sebastian Raschka FAQ — Why LLMs get stuck in loops](https://sebastianraschka.com/faq/docs/repetition-loops-generation.html)

**Agent-side detectors**
- [PraisonAI — Doom Loop Detection docs](https://docs.praison.ai/docs/features/doom-loop-detection)
- [OpenCode PR #3445](https://github.com/anomalyco/opencode/pull/3445)
- [OpenCode PR #12623](https://github.com/anomalyco/opencode/pull/12623)

**Runtime workarounds**
- [LM Studio bug #1018 — `--reasoning-budget 4096`](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1018)
- [unsloth — Qwen3.5 sampling-parameter card](https://unsloth.ai/docs/models/qwen3.5)
