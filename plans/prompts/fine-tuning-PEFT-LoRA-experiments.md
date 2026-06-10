# PEFT LoRA Experiment Planning Prompts

Use these prompts to plan focused PEFT/LoRA experiments. Each prompt assumes LoRA is used for behavior specialization, not compression. Model size, speed, and target-device fit come from the base model, quantization, and runtime.

## Prompt 1: Mac Studio Workflow LoRA

```text
You are planning a PEFT/LoRA fine-tuning experiment for my local LLM operations repo:

/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu

Purpose:
Build a small local model or adapter that serves my local-llm-macstu workflow best and fastest on a MacBook Pro M1 Pro with 16GB RAM. The model should act as a Mac Studio operations copilot, not a general coding model.

The adapter should teach the model to:
- answer repo-specific Mac Studio LLM operations questions concisely,
- know the server map, ports, launch shapes, and benchmark workflow from this repo,
- avoid claiming live run-state unless checked with scripts/chk_llm_macstu.py,
- recommend the right benchmark layer: bench_api_server.py, bench_api_tool_call.py, or bench_agent_tool_call.py,
- produce shell-oriented answers and operational next steps,
- avoid verbose reasoning and long explanations unless explicitly requested.

Constraints:
- Use PEFT/LoRA only for behavior specialization.
- Target a small instruct base model suitable for MacBook Pro M1 Pro 16GB.
- Prefer transformers + PEFT + TRL on MPS for the learning/training path.
- Do not assume the adapter makes the model smaller or faster.
- Plan for eventual quantized inference after merging the adapter.

Repo context to inspect:
- README.md
- AGENTS.md
- docs/tuning/tuning-by-workload.md
- docs/tuning/tuning-by-knob.md
- docs/models/how-to/eval-benchmark-local-runners.md
- docs/servers/*/summary.md
- scripts/chk_llm_macstu.py
- scripts/bench/bench_api_server.py
- scripts/bench/bench_api_tool_call.py
- scripts/bench/bench_agent_tool_call.py

Deliver an experiment plan with:
- recommended base model candidates and why,
- dataset design with example input/output records,
- how to generate 100, 300, and 1000-example dataset versions from the repo,
- LoRA configuration starting point,
- training command or training script outline,
- evaluation prompts for held-out repo workflow questions,
- latency and quality metrics,
- pass/fail decision criteria,
- deployment path for MacBook inference,
- risks and mitigations.

The final plan should be practical enough to run as a first quick experiment.
```

## Prompt 2: Android Automation LoRA

```text
You are planning a PEFT/LoRA fine-tuning experiment for a tiny Android-local automation model.

Purpose:
Build a small enough model or adapter to fit and run automation workflows only on my Android device. The target is not a general assistant. It should be a narrow local automation planner that maps user requests into constrained JSON actions.

The adapter should teach the model to:
- classify user intent,
- choose from a fixed set of allowed automation actions,
- fill action arguments safely,
- emit strict JSON only,
- ask for confirmation for risky actions,
- summarize local state briefly,
- avoid open-ended coding or long autonomous reasoning.

Constraints:
- Use PEFT/LoRA only for behavior specialization.
- Choose a very small base model first; LoRA does not make the base model fit Android.
- The final deployment should merge the LoRA into the base model and quantize for Android runtime.
- Assume live PEFT adapter switching on Android is less important than a single merged model.
- Keep the action space small and schema-driven.

Design the automation schema around actions like:
- read_status
- summarize_notification
- create_reminder
- draft_message
- classify_task
- run_known_template
- ask_confirmation
- no_action

Deliver an experiment plan with:
- recommended base model size class and candidates,
- Android runtime options to evaluate,
- strict JSON schema for actions,
- dataset design with positive, ambiguous, and refusal/confirmation examples,
- example training records,
- LoRA configuration starting point,
- merge and quantization path,
- offline Android evaluation checklist,
- JSON validity metrics,
- task success metrics,
- latency and memory targets,
- pass/fail decision criteria,
- risks and mitigations.

Keep the plan narrow enough that a tiny model can succeed.
```

## Prompt 3: Thai Translation Style LoRA

```text
You are planning a PEFT/LoRA fine-tuning experiment for my personal Thai translation style.

Purpose:
Build a LoRA adapter that makes a translation-capable model produce Thai translations in my preferred technical style. This is for personal use and comparison against the repo's existing ChindaMT Thai-English sidecar.

The adapter should teach the model to:
- translate English to Thai in my preferred tone,
- preserve model names, commands, ports, file paths, and technical terms when appropriate,
- avoid over-translating CLI and software terms,
- keep translations concise,
- handle Mac Studio / local LLM operations text naturally,
- optionally translate Thai back to English while preserving technical meaning.

Repo context to inspect:
- README.md sections mentioning ChindaMT and Thai translation
- docs/servers/mlx-lm/summary.md
- docs/clients/fabric-setup.md
- docs/models/model-summary.md entries for ChindaMT

Constraints:
- Use PEFT/LoRA only for style and terminology adaptation.
- Do not train for broad world knowledge.
- Prefer a translation-capable base model or small instruct model with acceptable Thai ability.
- Use a fixed evaluation set for side-by-side comparison:
  base model vs base + Thai-style LoRA vs ChindaMT output.

Dataset design:
- English technical sentence -> preferred Thai translation
- English operational paragraph -> preferred Thai translation
- Thai technical sentence -> preferred English translation
- glossary-preservation examples
- negative examples where commands, model IDs, URLs, ports, and file paths must not be translated

Deliver an experiment plan with:
- recommended base model candidates and why,
- dataset format and example records,
- glossary rules,
- 50-example, 200-example, and 1000-example dataset milestones,
- LoRA configuration starting point,
- training script outline,
- evaluation prompt set,
- human preference scoring rubric,
- automatic checks for preserving commands, paths, ports, and model IDs,
- deployment path for local use,
- pass/fail decision criteria,
- risks and mitigations.

Make the first experiment quick, measurable, and focused on style rather than general translation benchmarks.
```

## Shared Evaluation Prompt

```text
Given the PEFT/LoRA experiment plan above, turn it into a runnable first-pass checklist.

Include:
- exact files or docs to read,
- dataset rows to create first,
- minimum viable training command,
- minimum viable evaluation command,
- expected output artifacts,
- how to compare base vs adapter,
- what result would justify continuing,
- what result would mean the idea is not worth pursuing.

Keep the first pass small enough to complete in one sitting.
```
