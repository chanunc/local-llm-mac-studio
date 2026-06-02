# Plan: LoRA "Mac Studio Ops Copilot" — first PEFT experiment

Status: active
Created: 2026-06-02
Canonical: no

## Context

`setup-llm-macstu` is an operations notebook for a personal LLM lab on a Mac Studio M3 Ultra. The operational knowledge — server map, ports, launch command shapes, tuning knobs, benchmark workflow, and the hard rule *"never assert live run-state; check `scripts/chk_llm_macstu.py`"* — lives in docs but has to be re-read every session. The goal is a **small local adapter** that turns a tiny instruct model into a fast, repo-specific ops copilot that runs on a **MacBook Pro M1 Pro 16GB**, answers concisely and shell-first, and recommends the right benchmark layer — *without* claiming what is currently running.

This is a behavior-specialization task, so **PEFT/LoRA only**. Training path is **transformers + PEFT + TRL on MPS** (per request); MLX-LM LoRA is the noted faster-on-Apple-Silicon fallback. The adapter does **not** make the model smaller or faster — speed comes from the small base + post-merge quantization.

### Decisions (confirmed with user)
- **Base model:** `Qwen/Qwen3.5-2B` (Qwen3.5 small series, Mar 2026, Apache 2.0, 262K ctx, thinking off by default — matches "be concise"). Mirror: `unsloth/Qwen3.5-2B`. Aligns with the repo's Qwen3.5/3.6 ecosystem; merges + quantizes cleanly to MLX/GGUF.
- **Dataset:** Hybrid — deterministic templated extraction (anchor facts) + teacher-distilled paraphrase/expansion grounded strictly in repo doc chunks.
- **Train framework:** transformers + PEFT + TRL (`SFTTrainer`) on MPS, bf16, no bitsandbytes 4-bit (CUDA-only).
- **Deploy:** merge adapter → fp16 → quantize to MLX 4-bit and/or GGUF Q4_K_M for MacBook inference.

## Overview

This plan covers:
- **Base model** choice + rationale and the architecture caveat (Gated DeltaNet hybrid → LoRA `all-linear`).
- **Dataset design** with the chat-JSONL record schema and 4 concrete example records (incl. a guardrail/refuse-live-state record).
- **Dataset generation pipeline** (`build_lora_dataset.py`) and how it yields the **100 / 300 / 1000**-example versions from the repo.
- **LoRA config** starting point and the **training script** outline + command.
- **Evaluation**: held-out gold prompts, quality + latency + guardrail metrics, and **pass/fail** criteria.
- **MacBook deployment** path (merge → quantize → serve).
- **Risks & mitigations**, the **first quick experiment**, and **verification**.

---

## 1. Base model

| Candidate | Why | 16GB-train note |
|:--|:--|:--|
| **`Qwen/Qwen3.5-2B`** ✅ | Newest Qwen small model; repo is Qwen-native; thinking-off default = concise; Apache 2.0 | ~4 GB bf16; LoRA fits with headroom for activations |
| `Qwen/Qwen3.5-0.8B` | Fastest iteration / most headroom | trivially fits; lower ceiling — fallback if 2B is slow on M1 Pro |
| `unsloth/Qwen3.5-2B` (mirror) | Same weights, sometimes faster to pull | identical |

**Architecture caveat:** the small series uses a **Gated DeltaNet hybrid** (linear + softmax attention). Public module names aren't pinned, so we **don't hardcode** `target_modules`. Use PEFT `target_modules="all-linear"` and verify with a one-shot module dump (snippet in §4).

---

## 2. Dataset design

### 2.1 Record schema — chat JSONL (one example per line)
TRL `SFTTrainer` consumes `messages`. Loss is masked to the **assistant turn only** (assistant-only / completion-only loss) so the model learns *answers*, not to parrot questions.

```json
{"messages": [
  {"role": "system", "content": "You are the Mac Studio LLM-ops copilot for the setup-llm-macstu repo. Answer concisely and shell-first. Give the exact command or fact, then a one-line operational next step if useful. Never claim which model/server is currently running — direct the user to `python3 scripts/chk_llm_macstu.py`. Do not show long reasoning unless explicitly asked."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

The persona system prompt is **fixed across all records** (it encodes conciseness + the run-state guardrail) and is reused verbatim at inference.

### 2.2 Example records (grounded in real repo facts)

**(a) Port / launch fact**
- user: `How do I start lm-studio's server on port 1234 for LAN?`
- assistant: ```` ```bash\n~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors\n``` \nLoad the model first with `lms load '<id>' --gpu max --context-length 65536 -y`. For large models do the guardrail dance: flip `modelLoadingGuardrails` to `off` in `~/.lmstudio/settings.json`, load, restore to `high`. ````

**(b) Benchmark-layer routing**
- user: `Which bench script do I run to test that tool calls actually parse correctly?`
- assistant: `scripts/bench/bench_api_tool_call.py` — single-turn 5-tool harness for parser correctness. Use `bench_api_server.py` for raw prefill/decode throughput, and `bench_agent_tool_call.py` for the multi-turn OpenCode browse/search agent-loop gate.

**(c) Tuning knob**
- user: `Agent loop feels slow on a Qwen3.6 model. What do I change first?`
- assistant: The thinking flag — it dominates (3–4× output tokens × N turns). Set `enable_thinking:false` (e.g. `--chat-template-args '{"enable_thinking":false}'`). Next: prompt-cache size, then verify the right `--tool-call-parser`.

**(d) Guardrail / refuse live-state (critical class)**
- user: `Which model is running on the Mac Studio right now?`
- assistant: I can't assert live run-state — it's not tracked in any doc. Check it: ```bash\npython3 scripts/chk_llm_macstu.py\n``` Add `--models` for full per-port model lists or `--client opencode` to emit the matching config.

### 2.3 Content sources (grounding corpus)
- `docs/servers/*/summary.md` (16 runbooks) → port, launch shape, gotchas, parser flags
- `README.md` / `AGENTS.md` / `CLAUDE.md` → server table, Common Commands (verbatim launch cmds), data-flow
- `docs/models/model-summary.md` (+ `per-model/`) → catalog facts, "best for"
- `docs/tuning/tuning-by-workload.md`, `tuning-by-knob.md` → knob priority per workload
- `docs/models/how-to/eval-benchmark-local-runners.md` → MMLU/MMLU-Pro/TruthfulQA/HarmBench how-to
- `scripts/bench/{bench_api_server,bench_api_tool_call,bench_agent_tool_call}.py` docstrings + argparse → which-script-for-what + flags
- `scripts/chk_llm_macstu.py` docstring/usage → run-state guardrail answers
- `configs/clients/*/opencode.json` → ports + compatible model ids

---

## 3. Generating the 100 / 300 / 1000 versions

New script: **`scripts/tuning/build_lora_dataset.py`** (two-stage, deterministic ordering, pinned to a git commit hash recorded in the dataset header).

**Stage A — templated extraction (anchor facts, no LLM):** parse the sources above into seed Q→A pairs with fixed templates:
- per server: "What port…", "How do I start…", "What's the gotcha with…", "Which parser flag for…", "When do I use X vs Y…"
- per bench script: purpose-routing pairs (see 2.2b)
- per tuning knob: effect + how-to pairs
- run-state guardrail pairs (a fixed seed set of live-state questions → defer-to-`chk_llm_macstu.py`)
Every pair carries a `source` citation. → **~120–150 grounded seeds.**

**Stage B — teacher distillation (paraphrase + expand):** call a Mac Studio model over its OpenAI-compatible endpoint (whatever is up — discover via `chk_llm_macstu.py --json`; e.g. a Qwen3.6 on `:8100`/`:1234`). For each doc chunk:
- inject the **chunk text + its Stage-A seeds** into the prompt; instruct: *"Generate operator questions answerable ONLY from this context; answers concise + shell-first; if a question needs live state, the answer must defer to `scripts/chk_llm_macstu.py`; never invent ports/flags."*
- produce paraphrase variants of seeds (same answer, varied phrasing → robustness) and a few compositional multi-fact questions.
- **automated fact-check:** discard any generated answer whose ports/script-names/flags aren't substrings of the source chunk.

**Versions (deterministic subsets, ~10% held out for eval, never trained):**
- **v100** — Stage A core only, deduped (~100). Smoke that pipeline + training loop work end-to-end.
- **v300** — v100 + 1–2 teacher paraphrases each + full guardrail set (~300).
- **v1000** — v300 + broad teacher expansion across all servers/models/tuning + compositional Q&A (~1000).
- **eval-gold.jsonl** — 20–30 **hand-written** held-out workflow questions (authored by us, not generated), the real quality gate (see §5).

Output dir: `datasets/lora-ops-copilot/{v100,v300,v1000,eval-gold}.jsonl`.

---

## 4. LoRA configuration (starting point)

```python
from peft import LoraConfig
lora = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules="all-linear",   # robust for Gated DeltaNet hybrid; verify below
    bias="none", task_type="CAUSAL_LM",
)
```
**Verify target modules once** before the first run:
```python
import torch
from transformers import AutoModelForCausalLM
m = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-2B", torch_dtype=torch.bfloat16)
print(sorted({n.split('.')[-1] for n,mod in m.named_modules() if isinstance(mod, torch.nn.Linear)}))
```
If `all-linear` over-targets (e.g. router/gate layers hurt), fall back to the printed attention + MLP proj names.

Training hyperparameters (TRL `SFTConfig`): `bf16=True`, `max_seq_length=1024` (answers are short), `per_device_train_batch_size=1`, `gradient_accumulation_steps=8`, `learning_rate=2e-4`, `lr_scheduler_type="cosine"`, `warmup_ratio=0.03`, `num_train_epochs=3` (v100/v300) / `2` (v1000), `packing=False`, assistant-only loss via TRL's completion-only collator / `assistant_only_loss`.

---

## 5. Training & evaluation

### 5.1 Training script — `scripts/tuning/train_lora_ops_copilot.py`
TRL `SFTTrainer` skeleton; `device_map={"":"mps"}`, bf16, gradient checkpointing on. Invocation:
```bash
python3 scripts/tuning/train_lora_ops_copilot.py \
  --base Qwen/Qwen3.5-2B \
  --data datasets/lora-ops-copilot/v100.jsonl \
  --out adapters/ops-copilot-v100 \
  --epochs 3 --max-seq-len 1024 --grad-accum 8 --lr 2e-4
```
Env: a dedicated venv `~/lora-ops-env/` with `transformers peft trl datasets accelerate` (pip in venv; PyTorch MPS build).

### 5.2 Eval script — `scripts/tuning/eval_lora_ops_copilot.py`
Runs the merged/adapter model over `eval-gold.jsonl` and scores:

| Metric | How | Target |
|:--|:--|:--|
| **Fact accuracy** | regex/substring match of the gold key fact (port, script name, flag) in the answer | ≥ 0.80 |
| **Guardrail compliance** | % of live-state questions that defer to `chk_llm_macstu.py` and make no live-state claim | ≥ 0.95 (hard gate) |
| **Conciseness** | median answer length vs base model on same prompts | ≤ base; ideally shorter |
| **Rubric quality** | LLM-as-judge (Mac Studio model): correctness / conciseness / shell-orientation, 0–2 each | mean ≥ 4.5 / 6 |
| **Off-domain sanity** | 3 general prompts to detect catastrophic forgetting | coherent, no degradation |
| **Latency (MacBook)** | tok/s + first-token latency on merged 4-bit model | report; ≥ usable interactive speed |

Held-out gold examples (subset of the 20–30): *"What port is ds4 on and what must I never do with it?"*, *"Give me the pre-benchmark hygiene command."*, *"Which server is the only path for ZAYA1?"*, *"How do I check what's running over Tailscale?"*, *"OpenCode tool calls render as prose on vllm-mlx — what's wrong?"*

### 5.3 Pass/fail decision
- **PASS** (proceed to v300/v1000 + deploy): guardrail ≥ 0.95 **and** fact accuracy ≥ 0.80 **and** rubric ≥ 4.5/6 **and** no off-domain regression.
- **PARTIAL** (iterate data/hparams): guardrail ≥ 0.95 but fact accuracy 0.6–0.8 → add data (v300), raise epochs/r.
- **FAIL** (rethink): guardrail < 0.95 (unsafe live-state claims) → over-sample guardrail class, raise its weight; or training unstable on MPS → switch to MLX-LM LoRA fallback (§7).

---

## 6. Deployment path (MacBook inference)

1. **Merge:** `PeftModel.from_pretrained(base, adapter).merge_and_unload()` → save fp16 safetensors.
2. **Quantize (pick one or both):**
   - MLX: `mlx_lm.convert --hf-path <merged> -q --q-bits 4 --mlx-path ops-copilot-mlx-4bit`
   - GGUF: llama.cpp `convert_hf_to_gguf.py` → `llama-quantize … Q4_K_M`
3. **Serve on MacBook:** `mlx_lm.server --model ops-copilot-mlx-4bit` (or Ollama/LM Studio import). Pair with the fixed persona system prompt from §2.1.
4. Adapter ≠ smaller/faster: the ~2B base at 4-bit is what makes it MacBook-fast.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|:--|:--|
| Gated DeltaNet module names unknown → wrong `target_modules` | `all-linear` + verification dump (§4); fall back to printed names |
| MPS OOM / instability / slow on M1 Pro 16GB | seq 1024, batch 1, grad-accum, gradient checkpointing; **fallback: MLX-LM LoRA** (`mlx_lm.lora`, faster on Apple Silicon) or train on the Mac Studio |
| Teacher hallucinates ports/flags | strict grounding (chunk-in-prompt), Stage-A anchors, automated substring fact-check, drop on mismatch |
| Tiny dataset → memorization not generalization | held-out gold eval, paraphrase augmentation, low `r`, few epochs |
| Catastrophic forgetting of general ability | low `r`/few epochs, off-domain sanity prompts in eval |
| **Live-state leakage** (model invents "currently running X") | dedicated guardrail class over-sampled, hard ≥0.95 gate, eval blocks deploy if failed |
| Stale facts as repo evolves | pin dataset to git commit (recorded in header); regenerate on doc changes |

---

## 8. First quick experiment (run this first)
1. Set up `~/lora-ops-env/` (transformers/peft/trl/datasets/accelerate).
2. Build **v100** + **eval-gold** with `build_lora_dataset.py` (Stage A + hand-write 20 gold).
3. Verify `target_modules` dump; train **v100** on `Qwen/Qwen3.5-2B`, 3 epochs (expect a modest wait on M1 Pro; if intolerably slow, drop to `Qwen3.5-0.8B` or MLX-LM fallback).
4. Run `eval_lora_ops_copilot.py` on the adapter → check the §5.3 gates.
5. If PASS/PARTIAL → build v300/v1000 and merge+quantize for MacBook. If FAIL → §5.3 remedies.

---

## 9. Files to create / update (on approval)
- `scripts/tuning/build_lora_dataset.py` — Stage A extraction + Stage B teacher distillation + fact-check
- `scripts/tuning/train_lora_ops_copilot.py` — TRL SFT (MPS, bf16, assistant-only loss)
- `scripts/tuning/eval_lora_ops_copilot.py` — gold eval + fact-match + guardrail + LLM-judge + latency
- `datasets/lora-ops-copilot/{v100,v300,v1000,eval-gold}.jsonl`
- `docs/tuning/lora-ops-copilot.md` — writeup (with `## Overview`), linked from `docs/tuning/README.md`
- `scripts/README.md` — add a `tuning/` section (repo Sync Policy, Event 5)

## 10. Verification (end-to-end)
- `build_lora_dataset.py --version v100` produces ≥100 lines; every line is valid chat JSON with the fixed system prompt; fact-check log shows 0 ungrounded facts kept.
- Training completes without OOM; loss decreases; adapter saved.
- `eval_lora_ops_copilot.py` prints the §5 metric table; guardrail ≥ 0.95 on the live-state subset.
- Manual smoke: ask 5 gold questions to the merged 4-bit model on MacBook via `mlx_lm.server`; answers are concise, shell-first, and defer on live-state.
