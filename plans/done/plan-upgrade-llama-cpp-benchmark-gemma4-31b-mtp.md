Status: done
Created: 2026-06-09
Completed: 2026-06-10
Canonical: no

# Plan: Upgrade llama.cpp and benchmark Gemma 4 31B dense MTP

## Naming

The requested "Gemma 4 32B" model is canonically published as **Gemma 4 31B**. This plan uses the upstream/Hugging Face `31B` identifiers so model paths, GGUF metadata, and benchmark records remain accurate.

## Goal

Upgrade the source-built mainline `ggml-org/llama.cpp` at `~/llama-cpp-mainline/` to a revision containing:

- [PR #23398](https://github.com/ggml-org/llama.cpp/pull/23398), merge `04eb4c446` — Gemma 4 MTP support.
- [PR #24277](https://github.com/ggml-org/llama.cpp/pull/24277), merge `379ac66` — post-merge KV-cell copy fix.

Then benchmark the standard **Gemma 4 31B-it dense GGUF** on the Mac Studio M3 Ultra with the same upgraded binary:

1. MTP disabled, establishing the new-binary baseline.
2. MTP enabled with the external `gemma4_assistant` GGUF.
3. Draft depths `1`, `2`, and `4`.
4. API throughput, tool-call correctness, and OpenCode agent-loop wall time.
5. Qwen3.6 MTP regression check before adopting the upgrade.

The experiment succeeds only if MTP improves useful workloads without breaking tool calls or materially regressing the existing Qwen3.6 MTP path.

## Why this experiment

PR #23398 reports large gains for Gemma 4 31B dense but no reliable batch-1 gain for Gemma 4 26B-A4B MoE. Dense verification can amortize a full target-model weight pass across multiple candidate tokens; MoE verification may activate different experts for each candidate and lose that advantage.

The Mac Studio checkout inspected on 2026-06-09 was `510b5c2`, dated 2026-05-20, so it predates Gemma 4 support. There is no primary-source Metal result for this PR yet. The benchmark must therefore establish both correctness and speed locally rather than extrapolating NVIDIA/DGX results.

## Scope

### Mandatory

- Upgrade and retain a rollback binary.
- Standard Gemma 4 31B-it target, preferably Q4_K_M.
- Published Gemma 4 31B Q8 MTP assistant.
- Same-binary baseline vs MTP A/B.
- Draft-depth sweep at `1`, `2`, and `4`.
- API throughput, API tool smoke, and agent benchmark.
- Existing Qwen3.6 MTP regression check.
- Raw JSON logs and canonical documentation updates.

### Optional extension

After the standard target passes, repeat the winning MTP configuration against the already-downloaded TrevorJS Gemma 4 31B-it Uncensored Q4_K_M. This tests whether the standard assistant retains enough acceptance after abliteration.

### Out of scope

- Gemma 4 26B-A4B MoE as the primary candidate.
- E2B/E4B, which PR #23398 did not support at merge.
- TurboQuant or other KV-cache experiments during the first pass.
- Multimodal testing.
- Promoting any model or server to a live/default role.
- Deleting the old binary or legacy `~/llama-cpp-mtp/` build.

## Expected artifacts

```text
docs/models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/
├── environment.json
├── api-server-baseline.json
├── api-server-mtp-n1.json
├── api-server-mtp-n2.json
├── api-server-mtp-n4.json
├── api-tool-baseline.json
├── api-tool-mtp-winning.json
├── agent-baseline.json
├── agent-mtp-winning.json
├── qwen36-mtp-regression.json
└── comparison.md
```

If the TrevorJS extension runs, add:

```text
├── trevorjs-api-server-baseline.json
├── trevorjs-api-server-mtp.json
├── trevorjs-api-tool-mtp.json
└── trevorjs-agent-mtp.json
```

## Phase 1: Preflight and artifact selection

1. Read:
   - [`docs/models/per-model/model-summary-gemma.md`](../../docs/models/per-model/model-summary-gemma.md)
   - [`docs/servers/llama-cpp-mtp/summary.md`](../../docs/servers/llama-cpp-mtp/summary.md)
   - [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](../../docs/models/techniques/model-technique-qwen-3-6-mtp.md)
2. Record the installed llama.cpp state:
   ```bash
   ssh macstudio "cd ~/llama-cpp-mainline && \
     git rev-parse HEAD && \
     git log -1 --format='%H %cI %s' && \
     git status --short && \
     ./build/bin/llama-server --version"
   ```
3. Abort the upgrade if the checkout has unexplained local modifications. Preserve local work rather than resetting it.
4. Inspect Hugging Face metadata and record exact filenames, sizes, and SHA/revision for:
   - Standard target: `unsloth/gemma-4-31B-it-GGUF`, Q4_K_M preferred.
   - Assistant: the matching `MTP/` Q8_0 GGUF from the same repository.
5. Confirm target and assistant use the same Gemma 4 31B vocabulary and assistant architecture.
6. Check disk space. Budget for target, assistant, temporary download state, build artifacts, and logs:
   ```bash
   ssh macstudio "df -h ~; du -sh ~/llama-cpp-mainline ~/.cache/huggingface/hub 2>/dev/null"
   ```
   Require at least target size + 10 GiB free. Do not delete models automatically.
7. Run [`scripts/chk_llm_macstu.py`](../../scripts/chk_llm_macstu.py) to capture pre-experiment state. Do not write that live state into documentation.

## Phase 2: Upgrade llama.cpp with rollback

1. Stop any process using the mainline binary before replacing it.
2. Preserve the old executable and source commit:
   ```bash
   ssh macstudio "cd ~/llama-cpp-mainline && \
     OLD=\$(git rev-parse --short HEAD) && \
     cp build/bin/llama-server build/bin/llama-server-\$OLD"
   ```
3. Fetch mainline without discarding local changes:
   ```bash
   ssh macstudio "cd ~/llama-cpp-mainline && git fetch origin master"
   ```
4. Inspect the candidate revision and recent commits. Select and record an exact SHA from `origin/master`; do not document only "latest".
5. Verify the candidate contains both required fixes:
   ```bash
   ssh macstudio "cd ~/llama-cpp-mainline && \
     git merge-base --is-ancestor 04eb4c446 <CANDIDATE_SHA> && \
     git merge-base --is-ancestor 379ac66 <CANDIDATE_SHA>"
   ```
6. Fast-forward or detach at the selected SHA, then rebuild with the existing Metal configuration:
   ```bash
   ssh macstudio "cd ~/llama-cpp-mainline && \
     git switch --detach <CANDIDATE_SHA> && \
     /opt/homebrew/bin/cmake -B build \
       -DGGML_METAL=ON \
       -DGGML_METAL_EMBED_LIBRARY=ON \
       -DBUILD_SHARED_LIBS=OFF \
       -DLLAMA_BUILD_TESTS=OFF \
       -DLLAMA_BUILD_EXAMPLES=ON \
       -DLLAMA_BUILD_SERVER=ON && \
     /opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server && \
     ./build/bin/llama-server --version"
   ```
7. Confirm the upgraded help exposes:
   - `--spec-type draft-mtp`
   - `--spec-draft-model` / `-md`
   - `--spec-draft-ngl`
   - `--spec-draft-n-max`
8. Write `environment.json` with:
   - old and new commit SHA
   - build flags
   - macOS version and chip/RAM
   - target and assistant repository revisions
   - exact GGUF filenames and sizes
   - benchmark script git commit

### Rollback

If build, load, or Qwen regression checks fail:

```bash
ssh macstudio "cd ~/llama-cpp-mainline && \
  cp build/bin/llama-server-510b5c2 build/bin/llama-server"
```

Use the actual recorded old SHA if it differs from `510b5c2`. Keep the failed candidate SHA and logs in the experiment notes.

## Phase 3: Download and validate the GGUFs

1. Download only the selected target and assistant files with `hf download`.
2. Store them under a revision-specific Hugging Face snapshot or a clearly named local directory; avoid ambiguous `snapshots/main` paths in recorded commands.
3. Verify file size and checksum.
4. Inspect GGUF metadata with the upgraded llama.cpp tooling:
   - Target architecture must be Gemma 4 dense 31B.
   - Assistant architecture must be `gemma4_assistant`.
   - Tokenizer/vocabulary metadata must match.
5. Do a load-only smoke before benchmark hygiene. Abort if:
   - either file fails to load;
   - the server does not initialize speculative decoding;
   - target/draft vocabulary mismatch is reported;
   - Metal allocation exceeds the 96 GB machine budget.

## Phase 4: Benchmark isolation

Run the mandatory Event 4 hygiene immediately before every measured configuration:

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; pkill -f 'sglang.launch_server'; pkill -f 'sglang serve'; \
  pkill -f 'llama-cpp-mainline/build/bin/llama-server'; \
  pkill -f 'llama-cpp-mtp/build/bin/llama-server'; \
  pkill -f 'llama-cpp-turboquant/build/bin/llama-server'; \
  pkill -f 'llama-cpp-thetom/build/bin/llama-server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx|sglang|llama-server' | grep -v grep || echo clean; \
  memory_pressure | head -5"
```

Before each run:

- Verify port 8100 is free.
- Record `memory_pressure`.
- Use `-ngl 99 -fa on -np 1`.
- Use the same target, context size, prompt set, cache types, and new binary.
- Run one warmup, then at least three measured repetitions.
- Stop the server and wait for memory pressure to settle before changing configuration.

Do not restore the prior model after benchmarking.

## Phase 5: Same-binary baseline

Launch the standard target without a drafter:

```bash
ssh macstudio "TARGET=<STANDARD_GEMMA4_31B_Q4_K_M_GGUF>; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server \
    -m \"\$TARGET\" \
    -ngl 99 -fa on -np 1 -c 65536 \
    --host 0.0.0.0 --port 8100 \
    --alias gemma4-31b-q4km-baseline \
    --jinja --reasoning on \
    > /tmp/llama-cpp-gemma4-baseline.log 2>&1 &"
```

Run:

1. Health and one-shot generation.
2. `bench_api_tool_call.py`.
3. `bench_api_server.py` at `512,4096,8192,32768`.
4. `bench_agent_tool_call.py --scenario both --warmup 1 --runs 3`.

The stock `bench_api_server.py` filler can trigger deterministic early EOS on some models. If Gemma emits fewer than 40 output tokens, switch both baseline and MTP runs to the existing real-content methodology used by `qwen36-27b-mtp/perf-llama-cpp-mtp.json`. Never compare filler results against real-content results.

## Phase 6: MTP draft-depth sweep

For each `N` in `1 2 4`, launch:

```bash
ssh macstudio "TARGET=<STANDARD_GEMMA4_31B_Q4_K_M_GGUF>; \
  DRAFT=<GEMMA4_31B_MTP_Q8_0_GGUF>; \
  nohup ~/llama-cpp-mainline/build/bin/llama-server \
    -m \"\$TARGET\" -md \"\$DRAFT\" \
    -ngl 99 --spec-draft-ngl 99 -fa on -np 1 -c 65536 \
    --spec-type draft-mtp --spec-draft-n-max <N> \
    --host 0.0.0.0 --port 8100 \
    --alias gemma4-31b-q4km-mtp-n<N> \
    --jinja --reasoning on \
    > /tmp/llama-cpp-gemma4-mtp-n<N>.log 2>&1 &"
```

For each depth:

1. Confirm logs show the assistant model and speculative implementation initialized.
2. Run the same throughput prompts and contexts as baseline.
3. Capture `draft_n`, `draft_n_accepted`, acceptance rate, TTFT, decode tok/s, and peak memory.
4. Run three measured repetitions.
5. Stop and clean before the next depth.

Select the winning depth by:

1. Correct output and stable server behavior.
2. Highest median decode tok/s across 512, 8K, and 32K.
3. No material TTFT or memory regression.
4. Acceptance preferably at least 40%.

Do not select solely by acceptance rate; the best throughput can occur at a lower acceptance rate with a deeper draft.

## Phase 7: Correctness and agent benchmark

Run the full correctness/agent suite only for baseline and the winning MTP depth:

1. API tool smoke: 5 single-call scenarios and 3-turn loop.
2. Agent browse: one warmup + three measured.
3. Agent search: one warmup + three measured.
4. Inspect response payloads for:
   - valid `tool_calls[]`;
   - no raw tool markup in `content`;
   - sane `finish_reason`;
   - reasoning separated as expected;
   - no duplicated or skipped text caused by speculative decoding.

Agent benchmarks should use a temporary OpenCode model entry pointing to port 8100. Preserve and restore the user's local OpenCode config after the run.

## Phase 8: Qwen3.6 regression guard

Using the upgraded mainline binary, rerun a focused existing Qwen3.6 MTP model:

- Preferred: huihui-ai Qwen3.6-35B-A3B MTP Q6_K, because it is already a mainline-binary reference.
- Minimum fallback: unsloth Qwen3.6-27B-MTP UD-Q6_K_XL.

Run:

- one tool smoke;
- throughput at 512 and 8K;
- draft acceptance;
- one browse agent run.

Compare against the recorded baseline in [`docs/servers/llama-cpp-mtp/summary.md`](../../docs/servers/llama-cpp-mtp/summary.md). Regression threshold: no more than 5% median decode loss and no correctness/tool-call failure.

If Qwen regresses, retain the new binary under a SHA-suffixed filename for Gemma experiments and restore the old binary as the default executable.

## Phase 9: Optional TrevorJS extension

Only run this phase if the standard target:

- passes tool smoke;
- gains at least 15% decode throughput;
- has at least 40% draft acceptance;
- does not regress Qwen.

Use the existing target:

```text
~/.lmstudio/models/TrevorJS/gemma-4-31B-it-uncensored-GGUF/gemma-4-31B-it-uncensored-Q4_K_M.gguf
```

Repeat:

1. Same-new-binary baseline.
2. Winning standard-model draft depth.
3. API tool smoke.
4. Agent browse/search.

If acceptance falls below 40% or throughput fails to improve by 10%, record the standard assistant as incompatible or uneconomic for this fine-tune. Do not tune around the failure with unrelated cache quantization in this plan.

## Acceptance criteria

### Adopt upgraded binary for the MTP sidecar

- Build contains both required merge commits.
- Standard Gemma 4 31B loads with the assistant on Metal.
- API tool smoke is 5/5 and multi-turn is 3/3.
- Winning MTP configuration improves median decode by at least 15% at 512, 8K, and 32K.
- Acceptance remains at least 40% on representative prose/code prompts.
- Output-heavy agent search improves by at least 10%, or the throughput gain is strong enough to justify retaining the path as a non-agent generation option.
- Existing Qwen3.6 MTP stays within 5% of recorded decode performance and retains tool correctness.

### Reject or keep experimental only

- Any correctness or tool-call regression.
- No positive throughput at two or more contexts.
- Acceptance below 40% with all tested depths.
- Large memory/TTFT penalty that offsets decode gains.
- Qwen3.6 regression above 5%.

## Documentation updates after measured results

This is an upgrade plus new benchmark, not a new server type.

Update:

- [`docs/servers/llama-cpp-mtp/summary.md`](../../docs/servers/llama-cpp-mtp/summary.md)
  - exact upgraded SHA and build date;
  - standard Gemma launch command;
  - winning draft depth;
  - rollback procedure;
  - measured performance and limitations.
- [`docs/models/per-model/model-summary-gemma.md`](../../docs/models/per-model/model-summary-gemma.md)
  - replace projections with measured Metal results;
  - explain standard vs TrevorJS acceptance;
  - record where MTP helps and where fixed agent overhead dominates.
- [`docs/models/benchmarks/model-benchmark-api-server.md`](../../docs/models/benchmarks/model-benchmark-api-server.md)
  - baseline and winning-MTP rows.
- [`docs/models/benchmarks/model-benchmark-tool-call.md`](../../docs/models/benchmarks/model-benchmark-tool-call.md)
  - correctness and agent-loop rows.
- `README.md`
  - only if the result establishes a meaningful new benchmark headline or operating option.
- `AGENTS.md` and `CLAUDE.md`
  - mirror exact SHA/flags only if the runbook's normal launch recommendation changes.

Raw logs go under `docs/models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/`.

No doc may claim the tested model is current, primary, production, running, or stopped.

## Verification and drift checks

```bash
python3 -m json.tool docs/models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/environment.json >/dev/null
for f in docs/models/benchmarks/logs/gemma4-31b-mtp-llama-cpp/*.json; do
  python3 -m json.tool "$f" >/dev/null
done

grep -rn "Gemma 4 32B\|gemma-4-32" README.md AGENTS.md CLAUDE.md docs/ plans/ || true
grep -rn "current production\|production main\|production primary\|currently running\|currently stopped\|Last main\|Active model:" \
  README.md AGENTS.md CLAUDE.md configs/README.md docs/ || true

cmp -s <(tail -n +4 AGENTS.md) <(tail -n +4 CLAUDE.md)
git diff --check
```

## Plan lifecycle

After the upgrade, benchmarks, logs, and documentation are complete:

1. Move this file to `plans/done/`.
2. Change `Status: active` to `Status: done`.
3. Add `Completed: YYYY-MM-DD`.
4. Move its row in [`plans/README.md`](../README.md) from Active to Done.

