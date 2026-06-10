# Active Plan Builder Prompt

Use this prompt when you want an agent to create or revise planning docs under:

```text
/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/plans/active/
```

## Prompt: Build Or Adjust Repo Plans

```text
You are working in my local LLM operations repo:

/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu

Task:
Build or adjust active plan documents for the requested work. Save the plan files under `plans/active/` and update `plans/README.md` Current Index.

Required repo rules:
- Plans are non-canonical design notes and work queues, not live runbooks.
- Do not assert live run-state.
- Do not say a model/server is current, primary, production, currently running, or currently stopped.
- Use `scripts/chk_llm_macstu.py` only as a live-state check command in execution steps, not as recorded state.
- New plans must start with:
  Status: active
  Created: YYYY-MM-DD
  Canonical: no
- Use `plan-<slug>.md` filenames.
- Keep plans actionable enough that another agent can execute them later.
- If the plan touches server docs, models, benchmarks, scripts, configs, or clients, include the relevant Sync Policy follow-up docs to update after implementation.
- If the plan includes benchmark work, include where raw JSON should be written under `docs/models/benchmarks/logs/<model-slug>/`.
- If user review is needed, make the HITL checkpoint explicit and place it before irreversible work or long benchmark runs.

Planning style:
- Prefer concrete commands, paths, output files, and pass/fail criteria.
- Separate implementation steps from documentation follow-ups.
- Include preflight checks, execution steps, verification, rollback/stop commands where relevant, and acceptance criteria.
- Keep runtime practical. If a script or benchmark could be slow, define smoke, standard, and extended modes.
- Keep scope narrow; do not turn a plan into unrelated refactors.

When adjusting existing plans:
- Read the existing plan first.
- Preserve useful structure and status metadata.
- Make targeted edits only.
- Update `plans/README.md` if filenames or topics change.
- Do not move plans to `done/` or `archive/` unless explicitly requested.

Deliverables:
- List every file created or edited.
- Summarize the plan intent in one or two sentences per plan.
- Mention any assumptions or unresolved decisions.
- Confirm that the live-state wording check was considered.

Suggested drift check before finishing:

grep -rn "current production\|production main\|production primary\|currently running\|currently stopped\|Last main\|Active model:" plans/active plans/README.md || true
```

## Optional Add-On: Multiphase Plan Split

Use this add-on when the work should be split into separate plans.

```text
Split the work into separate active plans when phases have different owners, prerequisites, risk levels, or execution timing.

For each plan, include:
- Goal
- Why this shape
- Preconditions
- Implementation steps
- HITL checkpoints, if any
- Runtime / cost controls
- Verification
- Acceptance criteria
- Documentation follow-ups

Name the files so their dependency order is obvious, but do not use numeric prefixes unless the user asks.
```
