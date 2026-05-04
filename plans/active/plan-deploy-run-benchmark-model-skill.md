Status: active
Created: 2026-05-05
Canonical: no

# `/deploy-run-benchmark-model` skill — universal deploy + benchmark runner

## Context

The existing `/deploy-run-benchmark-uncen-model` skill (shipped 2026-05-02) compresses the 25–40 minute, 20+ file-edit recipe for uncensored models into one command. It explicitly aborts on censored / RLHF-aligned models with the message *"Censored model — wrong skill. Use the standard deploy flow under configs/clients/<server>/ instead."*

That abort path was hit when the user invoked the uncensored skill on `unsloth/granite-4.1-30b-GGUF` (IBM Granite 4.1 30B Instruct, Apache 2.0, RLHF-aligned) on 2026-05-04. The "standard deploy flow" the abort message refers to has no skill — it's still the manual recipe in CLAUDE.md Sync Policy Events 2 + 3 + 4 + 6, which is exactly what motivated building the uncensored skill in the first place.

This plan builds `/deploy-run-benchmark-model` — a strict superset of the uncensored skill that handles **both** censored and uncensored models with one branching pipeline. The uncensored skill stays in place as a thin alias for backward compatibility (or is deprecated in a follow-up — out of scope here).

The first real-world validation run is the same Granite 4.1 30B Q8_0 deploy that triggered the pivot — see `~/.claude/plans/build-script-to-check-snappy-gosling.md` for the per-model parameters (slug `granite-4.1-30b-q8`, context 131072, llmster server, flip-to-main per user choice).

## Why a new skill instead of patching the existing one

- Censored vs. uncensored branches differ on five concrete points (refusal bench, submodule edits, default-flip rules, configs/clients destination, commit count). Inlining all five conditionals into the existing skill would double its length and bury the canonical uncensored recipe.
- The user invocation `/deploy-run-benchmark-model <hf-repo-id>` reads correctly for both classes. Renaming the existing skill would break muscle memory.
- A separate skill lets us add the new Phase 0 (disk-space guard with `/list-rm-model-macstu` handoff) without re-validating the proven uncensored phases.

## New behaviour vs. the existing skill

| Concern | uncen-model (existing) | deploy-run-benchmark-model (new) |
|:--|:--|:--|
| Censored input | abort | take censored branch |
| Phase 0 disk guard | none | check `df -Pk ~`; abort + suggest `/list-rm-model-macstu` if free < (model size × 1.2) |
| Phase 4.2 refusal bench | always | only if branch=uncensored |
| Phase 5 submodule edits | always (`docs/models/uncen-model/`) | only if branch=uncensored |
| Phase 5 censored docs | never (split rule) | full Event 3 catalog edits + per-model file under `docs/models/per-model/model-summary-<family>.md` + `configs/clients/<server>/*.json` |
| Phase 6 commit count | 2 (submodule + parent) | 1 (parent only) on censored branch, 2 on uncensored branch |
| Default-flip behaviour | uncensored speed leader | flip per CLAUDE.md Event 4 strict reading (newly deployed model becomes the live main); user can override via `--no-flip` flag |

## Skill arguments

```
/deploy-run-benchmark-model <hf-repo-id> [quant] [context-len] [--server llmster|vmlx|vllm-mlx] [--no-commit] [--push] [--no-flip] [--censored auto|yes|no]
```

| Arg | Default | Notes |
|:--|:--|:--|
| `<hf-repo-id>` | required | e.g. `unsloth/granite-4.1-30b-GGUF` |
| `[quant]` | inferred | Heuristic per existing skill (K_P-family → Q6_K_P, plain GGUF → Q4_K_M). Q8_0 if user passes `8` or `q8`. |
| `[context-len]` | inferred | 131072 if HF card mentions "≥128 K to preserve thinking", else 65536 |
| `--server` | inferred | `llmster` for GGUF, `vmlx` for `*JANGTQ*` MLX, `vllm-mlx` for plain MLX |
| `--no-commit` | unset | Run benchmarks + write docs but skip staging |
| `--push` | unset | Auto-push at the end (default: print `git push` commands) |
| `--no-flip` | unset | Do not flip the new model to live main (Event 2 skipped, prior main stays in docs); use when running benchmarks for cross-model comparison without a production switch |
| `--censored` | `auto` | Override the Phase 1 vendor-marker classifier; `auto` runs the heuristic |

## Phase changes vs. uncen-model skill

### Phase 0 — Disk + RAM fit guard (NEW)

```bash
# Compute model size from HF API
SIZE_GB=$(curl -s "https://huggingface.co/api/models/$HF_REPO" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  print(round(sum(s.get('size',0) for s in d['siblings'] if '$QUANT' in s['rfilename'])/1e9,1))")
NEED_GB=$(awk "BEGIN{print int($SIZE_GB * 1.2 + 5)}")    # 20% headroom + 5 GB OS slack
FREE_GB=$(ssh macstudio 'df -Pk ~ | tail -1 | awk "{print int(\$4/1024/1024)}"')

if [ "$FREE_GB" -lt "$NEED_GB" ]; then
  cat <<EOF
Insufficient disk space on Mac Studio.
  Free:   ${FREE_GB} GiB
  Needed: ${NEED_GB} GiB (${SIZE_GB} GiB model + 20% headroom + 5 GB slack)

Run /list-rm-model-macstu to pick models to remove, then re-run this skill.
EOF
  exit 1
fi
```

`/list-rm-model-macstu` is interactive (free-form selection + AskUserQuestion confirmation) and cannot be invoked inline from another skill. Hand off to the user instead.

### Phase 1 — Validate + classify (MODIFIED)

Replace the abort-on-censored step with branching:

```python
# Pseudocode for the classifier
def classify(hf_repo_id, card_text):
    UNCEN_MARKERS = ["HauhauCS", "dealignai", "JANGTQ-CRACK", "NousResearch-Hermes",
                     "Hermes-4", "abliterated", "huihui-ai", "Dolphin-uncensored",
                     "Venice", "magnum", "Midnight-Miqu", "R1-1776",
                     "uncensored", "abliteration", "unfiltered", "low-refusal"]
    if any(m.lower() in (hf_repo_id + card_text).lower() for m in UNCEN_MARKERS):
        return "uncensored"
    return "censored"
```

`--censored yes|no` overrides the classifier output. `--censored auto` (default) runs it.

If branch=uncensored, continue exactly as the existing skill (Phase 1 step 6 slug rule, etc.).

If branch=censored, derive slug from the HF repo path:
- Strip vendor prefix and standard suffixes (`-GGUF`, `-MLX`, `-Instruct`)
- Lowercase ASCII, hyphens
- Append quant suffix lowercase (e.g. `granite-4.1-30b-q8`)

### Phase 2 — Pre-bench hygiene (UNCHANGED)

Same as existing skill.

### Phase 3 — Deploy (UNCHANGED structurally)

Same llmster / vmlx / vllm-mlx code paths. The deploy commands are identical regardless of branch.

### Phase 4 — Benchmarks (CONDITIONAL)

| Sub-phase | Censored branch | Uncensored branch |
|:--|:--|:--|
| 4.1 smoke (`bench_api_tool_call.py`) | run | run |
| 4.2 refusal (`refusal_harness.py`) | **skip** | run |
| 4.3 throughput (`bench_api_server.py`) | run | run |
| 4.4 agent (`bench_agent_tool_call.py`) | run | run |
| 4b triage on agent failure | run | run |

Output dir is `docs/models/benchmarks/<slug>/` either way. Refusal JSON simply isn't created on the censored branch.

### Phase 5 — Documentation (BRANCHED)

#### Censored branch — parent-only, no submodule

- `docs/current.md` — flip Production row (unless `--no-flip`); add prior main to Stopped/Documented Fallbacks
- `CLAUDE.md` + `AGENTS.md` (mirrored) — overview line for the new main
- `README.md` — Quick Start launch snippet, Models table row, Servers table sidecar/main note
- `configs/README.md` — Server Roles row + per-server section description
- `configs/clients/<server>/opencode.json` — flip top-level `model`/`small_model` (unless `--no-flip`); add new model entry to `models` map
  - `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json`, `claude-code-settings.json` — only if these files already exist for the server (per CLAUDE.md llmster-deferred policy)
- `docs/models/model-summary.md` — Index entry + per-family section
- `docs/models/per-model/model-summary-<base-family>.md` — new section after the prior sibling (specs · current-server · deployment recipe · smoke · perf · agent · caveats)
- `docs/models/README.md` — Per-model deep dives row if the per-model file is created
- `docs/models/benchmarks/model-benchmark-{api-server,api-tool-call,agent-tool-call}.md` — append rows + per-model sections

**Skip:** `docs/models/uncen-model/*` (submodule) — censored entries do not belong there per the 2026-05-02 censored/uncensored split.

#### Uncensored branch — unchanged from existing skill

`docs/models/uncen-model/` submodule edits as in the existing skill, plus the parent edits for `docs/current.md` / `README.md` / `CLAUDE.md` / `AGENTS.md` / `configs/README.md` / `docs/models/benchmarks/`.

### Phase 6 — Commits (BRANCHED)

| Branch | Commits | Notes |
|:--|:--|:--|
| Censored | 1 (parent only) | Subject: `Deploy and bench <slug> on <server>` |
| Uncensored | 2 (submodule + parent) | Same as existing skill |

`--push` semantics unchanged. `--no-commit` unchanged.

## Files to create / modify

### Create

- `~/.claude/skills/deploy-run-benchmark-model/SKILL.md` — full six-phase script (mirrors existing skill structure with the branched logic above)
- `~/.claude/skills/deploy-run-benchmark-model/refusal_harness.py` — verbatim copy of existing skill's harness (used only on uncensored branch)
- `~/.claude/skills/deploy-run-benchmark-model/README.md` — what the skill does, censored vs uncensored branches, files, extension points

### Modify

- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/plans/README.md` — add Active row for `plan-deploy-run-benchmark-model-skill.md`

### Cleanup

- `~/.claude/plans/build-script-to-check-snappy-gosling.md` — remove (per user feedback "save plans in repo `plans/active/`, not `~/.claude/plans/`"; the Granite-specific plan is captured by the validation-test section below)

## Validation

The first invocation of the new skill is the Granite 4.1 30B Q8_0 deploy that triggered this plan. Acceptance:

1. `/deploy-run-benchmark-model unsloth/granite-4.1-30b-GGUF 8 131072` runs end-to-end:
   - Phase 0: disk check passes (Mac Studio has ≥ 37 GiB free) or aborts cleanly with `/list-rm-model-macstu` instruction
   - Phase 1: classifier returns `censored` (no uncen markers in `unsloth/granite-4.1-30b-GGUF` or model card)
   - Phase 2: hygiene leaves the Mac Studio at `clean`
   - Phase 3: llmster loads `granite-4.1-30b-q8` with 131072 context, `lms ls` shows the identifier
   - Phase 4: 3 JSONs land in `docs/models/benchmarks/granite-4.1-30b-q8/` (api-server, api-tool-test, agent-bench), no refusal JSON
   - Phase 5: parent docs flip to Granite as new llmster main; submodule untouched
   - Phase 6: one parent commit staged, `git push` printed, no auto-push
2. `/deploy-run-benchmark-model HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` reproduces the existing uncensored skill's 2026-05-02 run end-to-end (regression check)
3. `/deploy-run-benchmark-model unsloth/granite-4.1-30b-GGUF --no-flip` runs benchmarks but does NOT change `docs/current.md` Production row or `opencode.json` defaults
4. Re-running on an already-deployed model is idempotent (model stays loaded; benchmarks re-run; doc edits are no-ops where unchanged)
5. Phase 0 disk guard correctly aborts on a synthetic low-space scenario (test by setting `NEED_GB` artificially high)

## Out of scope

- Deprecating or removing the existing `/deploy-run-benchmark-uncen-model` skill — keep it for backward compatibility; deprecation is a separate decision
- Auto-invoking `/list-rm-model-macstu` from inside this skill — that skill is interactive and cannot be driven programmatically
- MMLU-Pro / TruthfulQA-gen local eval (separate `plans/active/plan-bench-eval-local.md`)
- Vision-modality smoke tests (deferred from existing skill v1)
- Updating other client config files (claude-code, pi, openclaw, qwen-code) for llmster while it remains "provisional" per CLAUDE.md
