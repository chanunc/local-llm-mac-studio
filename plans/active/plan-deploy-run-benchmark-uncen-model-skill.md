# Plan: Build `/deploy-run-benchmark-uncen-model` Skill

Status: active
Created: 2026-05-02
Canonical: no

## Context

On 2026-05-02 we deployed `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` Q6_K_P from a cold start: pre-bench hygiene → Hub download → `lms import -L` → `lms load` → `lms server start` → 4 benchmarks (smoke, refusal, perf, agent) → 14 doc files (submodule + parent). The whole sequence takes ~25–40 minutes wall and touches >20 distinct edits across two repos. **It's the same shape every time** — the Balanced Q8_K_P run on 2026-05-01 followed the identical recipe with one model-id substitution.

The goal of the new skill is to compress that sequence into a single user-invokable command (`/deploy-run-benchmark-uncen-model <hf-repo-id> [quant] [context-len]`) so future uncensored-model deployments don't re-discover the same Sync Policy / submodule-push / `K_P`-resolver gotchas.

The plan to follow is documented in `/Users/chanunc/.claude/plans/justify-this-model-https-huggingface-co-glittery-orbit.md` (the just-executed deploy-and-bench run) — the skill should encode that plan as a parameterised script.

**Sync Policy applies:** this skill is build-time tooling, not a live-state change. Adding the skill itself triggers **Event 6** (new plan in `plans/active/`); shipping the skill triggers no events. Each *invocation* of the skill triggers Event 3 + Event 4 + Event 6 on the host repo (the skill executes those event-checklists).

## Goal

A skill at `~/.claude/skills/deploy-run-benchmark-uncen-model/SKILL.md` that takes a HuggingFace uncensored-model repo ID and (optionally) quant + context length, then executes the full deploy-and-benchmark sequence end-to-end against the Mac Studio LLM lab (`/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/`).

Outcome: one command to go from "this HF repo looks interesting" to "model is benchmarked, documented, and the submodule + parent commits are staged for push."

## Non-goals

- **Not** a generic deploy-any-model skill. Scope is limited to **uncensored** GGUF / abliteration / CRACK variants targeting llmster (or vmlx for JANGTQ-CRACK). Censored / standard models follow a different doc tree and are out of scope.
- **Not** a server-bringup skill. Assumes LM Studio (or vmlx) is already installed; only handles model deployment.
- **Not** an auto-pusher. The skill ends with staged commits ready for the user to inspect; final `git push` is gated on explicit confirmation per the user's saved memory preference.
- **No** vision-modality smoke tests in v1 — `mmproj-*-f16.gguf` is documented but not exercised.

## Skill input shape

```bash
/deploy-run-benchmark-uncen-model <hf-repo-id> [quant] [context-len] [--server llmster|vmlx] [--no-commit]
```

| Arg | Type | Default | Notes |
|:--|:--|:--|:--|
| `$1` (hf-repo-id) | required | — | e.g. `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` |
| `$2` (quant) | optional | `Q6_K_P` if K_P-family detected on HF; else inferred from repo's primary quant | Suffix on the GGUF filename: `Q4_K_P`, `Q6_K_P`, `Q8_K_P`, `Q4_K_M`, etc. |
| `$3` (context-len) | optional | 131072 if HF card mentions "≥128K to preserve thinking", else `65536` | Passed to `lms load --context-length`. |
| `--server` | optional | `llmster` | Currently only `llmster` (GGUF) and `vmlx` (JANGTQ) supported. Inferred from repo: `*JANGTQ-CRACK*` → vmlx, `*K_P*` GGUF → llmster. |
| `--no-commit` | flag | unset | Skip the staging step at the end; benchmarks still run. |

## Phases the skill executes

### Phase 1: Validate + sniff HF metadata

1. WebFetch the HF page; extract: base architecture, available quant filenames + sizes, license, `mmproj` presence, recommended loader, "preserve thinking" language.
2. Validate: must be an uncensored model (HauhauCS, dealignai-CRACK, NousResearch-Hermes, Dolphin-uncensored, magnum, abliterated, etc. — fall back to "ask user to confirm" on ambiguous cases). If repo looks censored, abort with a redirect to the censored sister flow.
3. Pick server based on file format:
   - GGUF → llmster (via `lms`)
   - JANGTQ / `*-CRACK*` MLX safetensors → vmlx bundled-Python
   - Plain MLX safetensors uncensored → vllm-mlx (fall-through, lower priority)
4. Pick quant based on RAM budget: Q6_K_P preferred for K_P-family; Q4_K_M for plain GGUF; Q8 only if model ≤ 30 B and ≤ 50 GB at Q8.
5. Pick API identifier: lowercased, org-prefix-stripped, `--identifier <slug>-<quant_lower>` (matches yesterday's pattern).

### Phase 2: Pre-bench hygiene

Verbatim from CLAUDE.md Event 4:

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

Abort if the post-cleanup process list isn't empty.

### Phase 3: Deploy

For llmster (GGUF):
1. `huggingface_hub.hf_hub_download` to `~/.cache/hauhau-gguf/` (avoids the `lms get` K_P-mis-resolver bug).
2. `lms import -L --user-repo <hf-repo> -y <gguf-path>` (hard link).
3. `lms load <internal-name> --gpu max --context-length <ctx> --identifier <api-id> -y`.
4. `lms server start --bind 0.0.0.0 --cors`.
5. Sanity: `curl http://192.168.31.4:1234/v1/models | jq` — verify identifier appears.

For vmlx (JANGTQ):
1. `~/vmlx-env/bin/hf download <hf-repo>` (or huggingface_hub equivalent).
2. Resolve snapshot path (`~/.cache/huggingface/hub/models--<org>--<repo>/snapshots/<sha>`).
3. Launch via `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; $BP/bin/python3 -m vmlx_engine.cli serve <SNAP> --host 0.0.0.0 --port 8000 --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 > /tmp/vmlx.log 2>&1 &`.
4. Re-apply `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` (idempotent).
5. Sanity: `curl http://192.168.31.4:8000/v1/models | jq`.

### Phase 4: Benchmarks

In order, write outputs to `docs/models/benchmarks/<slug>/`:

1. **Smoke (`bench_api_tool_call.py`)** → `api-tool-test.json`. Pass criterion: `single-call pass rate ≥ 4/5`.
2. **Refusal (inline mlabonne 10/520 harness)** → `refusal-rate-<server>.json`. `temp=1.0`, `max_tokens=1024` (uncensored default), keyword-match against both `content` + `reasoning_content`. Score = `complied / total`.
3. **Throughput (`bench_api_server.py`)** → `api-server-<server>.json`. Contexts `512,4096,8192,32768,65536` (skip 65536 if `context-len < 65536`). Temp 0.0, 50 generated tokens, 1 cold + 2 warm.
4. **Agent (`bench_agent_tool_call.py`)** → `agent-bench-<server>.json`. Switch OpenCode config first via `scripts/switch_opencode_config.py --server <server>`. 1 warmup + 3 measured browse + search.

Abort the doc-update phase if smoke fails (pass rate < 4/5) or refusal harness throws — leave the model running so the user can debug.

**Agent tool-call failure → triage flow.** If the agent benchmark (#4) fails — defined as **any** of: `errors[]` non-empty, exit code ≠ 0, `agent_turns: 0`, `tool_calls: []` when a tool was expected, p95 wall time > 250 s (within timeout cap of 300 s), or browse/search median > 5× the cross-model median for the same server/scenario — the skill enters a triage subroutine **before** asking whether to update docs. Past examples that should fire this branch: MiMo V2.5 ("Browse: 1/3 invalid tool call, 2/3 hit 8K cap. Search: 0/3 zero tool calls"), JANGTQ4-CRACK Search hang (was OpenCode-layer, eventually fixed at the API level), and the NordVPN-Shield-blocking-OpenCode socket regression.

### Phase 4b: Agent-tool-call failure triage

Trigger: any failure signature from Phase 4 #4 above. The skill executes:

1. **Capture failure signature** — extract from `agent-bench-<server>.json`:
   - Failed scenario(s): browse, search, or both
   - Per-turn error messages (first 200 chars each, deduped)
   - Tool-call counts vs expected (e.g. `expected webfetch, got: []`)
   - Any timeout / exit-code != 0 / hang signature
   - The exact model id, server, parser flags, context length, and the OpenCode version used
   - The smoke-test result from `api-tool-test.json` for contrast (did API-level tool calls work? this isolates server-vs-OpenCode-layer issues per the JANGTQ4-CRACK precedent)

2. **Search known sources** — issue three parallel WebSearch / WebFetch queries:
   - **Reddit:** `site:reddit.com <model-base-family> tool calling not working` and `site:reddit.com <model-base-family> opencode lm studio` — focus subs `r/LocalLLaMA`, `r/LocalLLM`, `r/Oobabooga`, `r/MachineLearning`. Catch posts about chat-template / abliteration / quant-format breaking tool use.
   - **HuggingFace:** the model card's *Community* tab (`https://huggingface.co/<repo-id>/discussions`) plus the base-model card (`https://huggingface.co/<base-model>/discussions`). Look for closed-but-related issues + chat-template caveats.
   - **GitHub:** issues across the toolchain — `lmstudio-ai/lmstudio.js`, `lmstudio-ai/llms`, `ml-explore/mlx-lm`, `bstnxbt/dflash-mlx`, `jjang-ai/vmlx`, `jjang-ai/jangq`, `anomalyco/opencode`, `vercel/ai`. Query patterns: `tool_calls empty <quant-family>`, `agent loop hang <model-family>`, `<base-family> chat template tools`, plus the exact error string from the failure capture (truncated).
   - For each source, return at most 5 hits ranked by relevance; capture the URL, title, status (open/closed/merged), and a 2-line summary.

3. **Generate structured issue report** at `docs/models/benchmarks/<slug>/agent-tool-call-failure-triage.md`:
   ```md
   # Agent Tool-Call Failure — <model-id> on <server>
   Date: YYYY-MM-DD
   Slug: <slug>
   ## Failure signature
   <captured fields from step 1>
   ## Smoke-test contrast
   <api-tool-test.json results — did API-level tools pass? if yes, layer = OpenCode/agent; if no, layer = server/model>
   ## Probable layer
   server | model | parser | OpenCode | network — picked by smoke-vs-agent comparison and search hits
   ## Related findings
   ### Reddit
   - [title](url) — <2-line summary>
   ### HuggingFace
   - [discussion title](url) — <2-line summary>
   ### GitHub
   - [issue / PR title](url) — open|closed — <2-line summary>
   ## Recommended next steps
   <ranked: parser-flag fix, patch re-apply, OpenCode upgrade, abandon the model, file an upstream issue, etc.>
   ## Reproducer (for upstream filing)
   <minimal curl + opencode-run snippet that reproduces the failure deterministically>
   ```
   The reproducer block is the **draft of an upstream-filable issue** — pre-formatted so the user can paste it into a HuggingFace discussion or a GitHub issue with one click if they choose to. Includes the exact server flags, model id, OpenCode version, and the failing prompt.

4. **`AskUserQuestion` prompt** — surface the triage report inline in chat with three options:
   - **Continue with docs (caveats noted)** — proceed to Phase 5 but mark the model in `docs/models/uncen-model/uncen-model-readme.md` Top Recommended caveat column with the failure mode (precedent: MiMo V2.5's "OpenCode tool-call broken" entry). Useful when the bench has cross-server value even if this server is broken.
   - **Skip docs, leave model running for manual debug** — model stays loaded; benchmark JSONs + triage report stay on disk; no submodule / parent edits. Default for serious bugs you want the user to investigate before recording.
   - **Abort + unload** — `lms unload --all` (or `pkill vmlx_engine`), delete the partial bench dir, exit non-zero. Default for trivially-broken models we don't want to clutter the catalog with.

   Skill defaults: if smoke also failed → "Abort + unload"; if smoke passed but agent failed → "Skip docs". User can always override.

5. **Whichever branch the user picks**, append the triage report to the bench writeup at Phase 5 if "Continue" is chosen, or leave it standalone if "Skip docs" / "Abort". Either way the report is the durable artefact — it's the thing future agents grep for when a similar failure recurs.

Triage subroutine never auto-files an upstream issue. The reproducer block is a *draft*; the user decides whether to publish.

### Phase 5: Documentation updates

Submodule first, then parent (per yesterday's submodule-push gotcha — pushes from the wrong directory silently no-op).

**Submodule (`docs/models/uncen-model/`):**
- New: `<slug>-benchmark.md` — mirror the structure of `qwen36-35b-a3b-hauhaucs-aggressive-benchmark.md` (model card · deployment · smoke · refusal · perf · agent · cross-server comparison · operational notes · see-also).
- Update: `README.md` (file index + headline bullets), `uncen-model-readme.md` (Top Recommended + Full Roster + Quick Take), `uncen-model-comparison.md` (Full Comparison row + Server Compatibility row), `uncen-model-test-results.md` (summary row + per-prompt detail block + methodology server list).
- Update: `client-configs/<server>/opencode.json` + `openclaw-provider.json` + `pi-models.json` — add new model entry, set as default if uncensored speed leader.
- Update: `client-configs/README.md` — Layout note + roster table.

**Parent (`/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/`):**
- `docs/current.md` — flip "Production" row if this model becomes the active main; add prior model to "Stopped / Documented Fallbacks" with restart launch shape.
- `docs/models/per-model/model-summary-<base-family>.md` — new section after the prior sibling (specs · current-server · deployment recipe · smoke · refusal · perf · agent · caveats).
- `docs/models/model-summary.md` — Index entry + Per-Model row in family table.
- `README.md` — Models table row, Servers table sidecar/main note, Quick Start launch snippet swap.
- `CLAUDE.md` + `AGENTS.md` (mirrored, header-only diff) — overview line + per-server bullet.
- `configs/README.md` — Server Roles row "Model(s)" column + per-section description.
- Cross-model bench summary tables: `docs/models/benchmarks/model-benchmark-{api-server,api-tool-call,agent-tool-call,standalone}.md` — add rows.
- `configs/clients/<server>/*.json` — **only if this model becomes the default** for the censored side (rare for uncensored). Per the censored/uncensored split (added 2026-05-02), uncensored entries do not land in `configs/clients/`; they only land in the submodule's `client-configs/`.

### Phase 6: Drift check + stage commits

```bash
grep -n "<previous-uncen-default-id>" \
  README.md AGENTS.md CLAUDE.md configs/README.md \
  docs/current.md docs/models/model-summary.md
```

Verify only catalog/fallback hits remain. Then:

```bash
# Submodule first
git -C docs/models/uncen-model add -A
git -C docs/models/uncen-model commit -m "<slug> benchmark + roster updates"
# parent
git add -A
git commit -m "Bump uncen-model submodule: <slug> deploy and bench"
```

**Do not push** unless `--push` is passed. Default behaviour: print the two `git push` commands the user should run from the right working directories. This avoids the "Everything up-to-date" submodule-push trap from 2026-05-01.

## Skill file structure

```
~/.claude/skills/deploy-run-benchmark-uncen-model/
├── SKILL.md                  # the runnable skill (Markdown + bash blocks)
├── refusal_harness.py        # inline refusal-rate driver (port from /tmp/refusal_bench_aggressive.py)
└── README.md                 # how the skill works, contributor docs
```

`SKILL.md` frontmatter:

```yaml
---
name: deploy-run-benchmark-uncen-model
description: Deploy + benchmark a HuggingFace uncensored model end-to-end on the Mac Studio LLM lab — pre-bench hygiene, deploy, smoke + refusal + perf + agent benchmarks, full doc + submodule updates following CLAUDE.md Sync Policy. Use when the user wants to add or evaluate a HauhauCS / dealignai-CRACK / NousResearch-Hermes / Dolphin / magnum / abliterated / Huihui-style uncensored model on llmster or vmlx.
argument-hint: <hf-repo-id> [quant] [context-len] [--server llmster|vmlx] [--no-commit]
allowed-tools: Bash Read Write Edit WebFetch WebSearch AskUserQuestion
---
```

The body of `SKILL.md` is the six-phase script with bash blocks the agent runs in sequence. Each phase has explicit pre/post conditions so the agent knows when to abort.

## Critical files (existing utilities to reuse)

- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_api_tool_call.py`
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_api_server.py`
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/bench/bench_agent_tool_call.py`
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/scripts/switch_opencode_config.py`
- `/tmp/refusal_bench_aggressive.py` — port to skill repo as `refusal_harness.py`
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/models/uncen-model/qwen36-35b-a3b-hauhaucs-aggressive-benchmark.md` — template shape for the new bench writeup
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/docs/models/per-model/model-summary-qwen-3-6.md` — template for per-model section
- `/Users/chanunc/cc-prjs/cc-claude/setup-llm-macstu/CLAUDE.md` Sync Policy (Events 3 + 4 + 6)

## Open questions

1. **Slug derivation rule** — yesterday's slug was `qwen36-35b-a3b-hauhaucs-aggressive`; the day before's was `qwen36-27b-hauhaucs-q8kp`. Inconsistent (`hauhaucs-aggressive` vs `hauhaucs-q8kp`). Decide one rule (proposed: `<base-family>-<vendor>-<tier>` for HauhauCS, `<base-family>-<crack-tier>-crack` for dealignai). Plan to revisit when we add a third HauhauCS variant.
2. **Skill UX when smoke fails** — abort cleanly and leave model running, or auto-unload and refund the bench dir? Default should be "leave running, surface a triage block in chat" so the user can inspect.
3. **vmlx vs llmster routing edge cases** — what if a HauhauCS variant ever ships in MLX safetensors? Today none do, but the skill's format-sniff should detect this and route to `vllm-mlx` rather than llmster.
4. **Censored model accidentally passed in** — should the skill refuse, or warn-and-route to a sibling skill? v1 should refuse with a redirect message, since the doc-update tree is wrong for censored models.

## Acceptance criteria

1. `/deploy-run-benchmark-uncen-model HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` reproduces the 2026-05-02 run end-to-end (no diff vs the actual files committed today, modulo timestamps).
2. `/deploy-run-benchmark-uncen-model dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` correctly routes to vmlx, applies the MLLM tools patch, and writes a benchmark file matching the existing `qwen36-35b-jangtq4-crack-benchmark.md` shape.
3. Re-running the same command on a model that's already deployed is idempotent — model stays loaded, benchmarks re-run, doc edits are no-ops where unchanged.
4. Skill aborts before the deploy phase if pre-bench hygiene leaves residual processes; on smoke or refusal-bench failure aborts before doc-edit; on agent-tool-call failure runs Phase 4b triage subroutine (Reddit + HF + GitHub search → structured triage report under `docs/models/benchmarks/<slug>/agent-tool-call-failure-triage.md` → `AskUserQuestion` with continue/skip/abort options).
5. Censored/uncensored split honoured — no skill-generated edits land in `configs/clients/<server>/` (only in `docs/models/uncen-model/client-configs/<server>/`).
6. Final state: two staged commits (submodule + parent), no automatic push, final chat output prints the two `git push` commands with the right `cd` prefixes.

## Verification plan

Phase-by-phase smoke test on a third HauhauCS variant when one ships:

1. Phase 1 sniff — confirm WebFetch parses the file table and the recommended-quant heuristic picks Q6_K_P or equivalent.
2. Phase 2 hygiene — run on a Mac Studio that has vmlx live, confirm process is killed and `memory_pressure` returns expected output.
3. Phase 3 deploy — confirm `lms server start` returns the new identifier in `/v1/models`.
4. Phase 4 — confirm all four JSONs land in the new bench dir with the expected shape.
4b. Phase 4b (negative test) — deliberately point the skill at a model known to break OpenCode tool-calling (e.g. revisit MiMo V2.5 4-bit or use a deliberately-broken parser flag). Confirm the triage report file lands at `docs/models/benchmarks/<slug>/agent-tool-call-failure-triage.md`, contains at least 1 result from each of Reddit / HF / GitHub (or a "no relevant results" stanza if a search returns empty), the smoke-vs-agent layer attribution is correct, and the `AskUserQuestion` block surfaces in chat.
5. Phase 5 — diff the resulting docs against the 2026-05-02 PR; the only diff should be the model id and the numbers.
6. Phase 6 — confirm the staged commit graph: submodule head matches its remote-pending state; parent head bumps the submodule pointer.

After acceptance, move this plan to `plans/done/`, add the skill to `~/.claude/skills/`, and add a one-line note in `CLAUDE.md` Project section pointing future agents at it.
