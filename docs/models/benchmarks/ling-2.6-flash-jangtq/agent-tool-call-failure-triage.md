# Ling-2.6-flash-JANGTQ — Phase 4 smoke failure triage

Date: 2026-05-05
Model: `JANGQ-AI/Ling-2.6-flash-JANGTQ` (BailingMoeV2.5, ~103B / ~8B-active hybrid MoE)
Server: vmlx 1.5.20 (DMG upgrade from 1.3.65 today), jang_tools 2.5.22
Quant: JANGTQ2 (2-bit MXTQ on 256 routed experts × 31 MoE layers; 8-bit affine on attention/shared/dense; 30 GB on disk vs. 200 GB bf16)
Launch: `--enable-auto-tool-choice --tool-call-parser deepseek --reasoning-parser deepseek_r1 --continuous-batching`
Patches re-applied: `patch_vmlx_jangtq_mllm_tools.py`, `patch_mlx_lm_threadlocal_stream.py`

## Failure signature

`bench_api_tool_call.py` smoke: **2/5 single-call passed**, multi-turn aborted.

| Scenario | finish | tools | tok/s | Notes |
|:--|:--|:--|:--|:--|
| Single tool (file read) | length | none | 48.3 | Truncated at 1024 tokens |
| Single tool (command) | stop | none | 9.1 | Direct prose answer, no tool |
| Multi-tool (search + read) | tool_calls | `search_web` | 12.2 | ✅ |
| Multi-tool (list + read + write) | length | none | 49.0 | Truncated at 1024 tokens |
| Agentic reasoning | tool_calls | `list_directory` | 12.0 | ✅ |
| Multi-turn turn 1 | stop | none | — | Aborted: no tool call |

Reproducer (5-tool array, "Read the file /tmp/notes.txt") yielded the canonical degenerate output:

```
"the name of the function is "the name of the function is "the name of the function is "...
```
repeated until 1024-token cap (1024 completion tokens generated, 0 useful content).

## Mitigation experiments

Same prompt, same 5-tool array, varied temperature + system prompt:

| temperature | system | finish | tool_calls | content sample |
|:--|:--|:--|:--|:--|
| 0.3 | none | tool_calls | `read_file` | `'I read_file("https://www.google.com/search?q=100+year+old+person+with+heart+condition", ...'` |
| 0.7 | none | stop | none | `'I read the file /tmp/notes.txt and tell you its contents.'` (no actual call) |
| 0 | `detailed thinking on` | stop | none | `"I'll never forget this day."` (unrelated) |
| 0.7 | `detailed thinking on` | length | none | `'I need to find the information about the actual number of participants...'` (hallucination) |

Single-tool, narrow array (`read_file` only), temp=0:
```json
{"finish_reason":"tool_calls","tool_calls":[{"function":{"name":"read_file","arguments":"{\"path\":\"/tmp/notes.txt\"}"}}]}
```
i.e. **single-tool array works**; multi-tool array degrades.

## Probable layer

**Quantization quality (model layer), not server / parser / harness.**

Evidence:
- Trivial QA works ("What is 84 * 3 / 2?" → "126") — model loads, decodes, and emits coherent answers for non-tool prompts.
- The single-tool array reproducer succeeds (model calls `read_file` with the right path).
- 5-tool array degenerates into infinite repetition / hallucinated unrelated content.
- **Parser swap does not help.** Re-tested with `--tool-call-parser qwen3 --reasoning-parser qwen3` (the proven flag set from prior `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` success — see `docs/models/per-model/model-summary-qwen-3-6.md`). Identical degeneration: `'I have a question about the "cost" of the "cost" of the "cost" of the "cost"...'` at temp=0.7; `"I'll never forget this day."` at temp=0 with `detailed thinking on`.
- Throughput is healthy (48 tok/s decode), so it's not a kernel correctness issue.
- Author hasn't published a coding benchmark for JANGTQ2; the `pass@1=1.0` numbers in the README are for the GGUF Q4_K_M / Q8_0 flavors only.

## Compare to prior JANGTQ success

| Aspect | OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 (worked, 2026-05-01) | JANGQ-AI/Ling-2.6-flash-JANGTQ (today, failed) |
|:--|:--|:--|
| Quant tier | JANGTQ**4** (4-bit experts) | JANGTQ**2** (2-bit experts) — 2× more aggressive |
| Architecture | Qwen3.6 hybrid (Gated DeltaNet + full attn) | Bailing-V2.5 hybrid (MLA + Lightning-Linear-Attn + MTP) |
| vmlx version | 1.3.65 | 1.5.20 (upgraded today) |
| Parser flags | `--tool-call-parser qwen3 --reasoning-parser qwen3` | tried both `deepseek` AND `qwen3`; both degenerate |
| `--continuous-batching` | not used | required (without it: `Stream(gpu, 1)` error) |
| 5-tool API harness | 5/5 | 2/5 |
| Caveat | "Simple chat can emit natural-language thinking in `content`; OpenCode tool calls still parse correctly" | Multi-tool prompts degenerate into infinite repetition or unrelated hallucination |

The 4-bit Qwen variant kept tool-routing intact. The 2-bit Ling variant has lost it. Quant aggressiveness is the most parsimonious explanation; new arch (`bailing_hybrid`) and new vmlx version are confounders but the degeneration pattern (token-level repetition) is a textbook over-quantization signature.

## Control test (2026-05-05, after Ling failure)

Re-loaded `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` on vmlx 1.5.20 with both patches applied + `--continuous-batching` (proven flag set + the new continuous-batching requirement). Same `bench_api_tool_call.py` harness:

```
[1/2] Single-call scenarios
  • Single tool (file read) ... 1.82s, finish=tool_calls, tools=['read_file']
  • Single tool (command) ... 1.31s, finish=tool_calls, tools=['run_command']
  • Multi-tool (search + read) ... 1.84s, finish=tool_calls, tools=['search_web', 'read_file']
  • Multi-tool (list + read + write) ... 1.68s, finish=tool_calls, tools=['list_directory']
  • Agentic reasoning ... 6.63s, finish=tool_calls, tools=['run_command']

[2/2] Multi-turn agentic loop
    turn 1: 2.50s, finish=tool_calls, tools=['read_file']
    turn 2: 3.18s, finish=tool_calls, tools=['write_file']
    turn 3: 9.82s, finish=tool_calls, tools=['write_file']
Single-call pass rate: 5/5
Multi-turn total: 3 turns, 15.51s
```

Matches the 2026-05-01 baseline (5/5, 11.65 s multi-turn) within run-to-run variance. **Toolchain is healthy.** Ling-JANGTQ2 failure is therefore the model, not the infrastructure.

## vmlx 1.5.20 regressions discovered (independent of Ling)

1. **MLLM tokenizer crash without `--continuous-batching`**: First load of `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` on vmlx 1.5.20 with the historically-correct flag set (no `--continuous-batching`) raises `AttributeError: Qwen2Tokenizer has no attribute stopping_criteria` from `mlx_vlm/generate.py:854 → tokenizer.stopping_criteria.reset(...)`. The JANG loader sets `stopping_criteria` on the inner tokenizer but the wrapper class doesn't surface it. Workaround: add `--continuous-batching` (uses a different generation path that bypasses the bug). **Implication**: vmlx 1.5.20's launch shape now requires `--continuous-batching` for VLM/MLLM JANGTQ models — update `docs/servers/vmlx/summary.md` and `docs/models/per-model/model-summary-qwen-3-6.md` launch snippets.
2. **`bailing_hybrid` requires `--continuous-batching`**: see top of report.

So the new universal vmlx 1.5.20 launch snippet for any JANGTQ model is:

```bash
$BP/bin/python3 -m vmlx_engine.cli serve $SNAP --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser <qwen3|deepseek|...> \
  --reasoning-parser <qwen3|deepseek_r1|...> \
  --continuous-batching
```

## Sidebar findings during deploy

1. **vMLX needed upgrade**: 1.3.65 → 1.5.20 to resolve `bailing_hybrid` not being in `mlx_lm.models`. v1.5.17 release notes ("Ling-2.6-flash / Bailing-V2.5 ... loads in") landed today.
2. **`pip install jang-tools` is broken**: `jang-tools` is not on PyPI; it ships only inside vMLX.app. The HF README's instructions cannot be followed literally.
3. **Repo upload was incomplete at our first pull**: shard 00018-of-00029 was missing; author re-uploaded ~1 h later (commit `867ec1e8`).
4. **`model.safetensors.index.json` is stale**: still references 31-shard layout (`*-of-00031`), while files are 29-shard prestack (`*-of-00029`). Local regeneration of `weight_map` from actual shard contents (1,149 prestacked tensors per JANGTQ-PRESTACK STANDARD, vMLX v1.5.19 feature) fixed loading. Backup at `model.safetensors.index.json.bak.broken-31shard`.
5. **`--continuous-batching` is required** on vmlx for `bailing_hybrid`. Without it, `mx.eval([c.state for c in prompt_cache])` raises `RuntimeError: There is no Stream(gpu, 1) in current thread.` Patch to `mlx_lm/generate.py` (thread-local generation_stream) was applied but turned out unnecessary once `--continuous-batching` was added.

## Next steps

- **Author-facing**: file an HF discussion noting the broken `model.safetensors.index.json` (shard-layout mismatch) and report multi-tool degeneration on JANGTQ2 (with reproducer above). Author is publishing today; quick turnaround likely.
- **Lab-facing**: revisit when JANGTQ4 (4-bit) flavor of Ling-2.6 ships, or use the existing `mlx-community/Ling-2.6-flash-mlx-6bit` 6-bit MLX path on vllm-mlx (already documented in CLAUDE.md / `docs/models/techniques/model-architecture-bailing-hybrid.md`).
- **Skill-facing**: consider a bench preflight that hits `/v1/chat/completions` with the smoke prompt + single-tool array before running the full 5-tool harness, to detect quantization degeneration before doc edits.
