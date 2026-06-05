Status: active
Created: 2026-06-03
Canonical: no

# mlx-vlm 0.6.x Qwen VL Deploy And Benchmark

Update `mlx-vlm` on the Mac Studio to the latest available release, deploy a Qwen VL 4-bit model as a provisional sidecar, then benchmark both normal agent tooling and the new visual-agent harness.

This plan intentionally does not record live run-state. Check live state with `scripts/chk_llm_macstu.py` before and after execution.

## Target

Selected model:

```text
mlx-community/Qwen3.6-35B-A3B-4bit
```

Rationale:

- Qwen3.6 native multimodal model.
- 35B total / ~3B active MoE gives a better speed-memory tradeoff than dense VL models.
- 4-bit footprint leaves headroom on a 96 GB Mac Studio for vision features, KV cache, continuous batching, APC/vision cache, and repeated image turns.
- Already familiar in this repo as a Qwen3.6 family target.

Comparison model if time permits:

```text
mlx-community/Qwen3-VL-32B-Instruct-4bit
```

Use it as a dedicated VLM baseline if Qwen3.6-A3B underperforms on OCR/chart/screenshot tasks.

## Version Policy

At execution time, verify the latest `mlx-vlm` version from PyPI/GitHub before installing. As of 2026-06-03, the researched target is `mlx-vlm` 0.6.0, but the command should not assume that remains latest.

Record the installed version and git/ref if installing from source.

## Port / Server Posture

Use a non-conflicting sidecar port:

```text
8081
```

Reason:

- `8080` is already used by ChindaMT `mlx-lm`.
- Port 8000 servers are mutually exclusive and should not be displaced for a provisional VLM sidecar.
- `mlx-vlm` is being evaluated for multimodal tasks, not as a text-agent replacement.

## Preflight

1. Check live state:

```bash
python3 scripts/chk_llm_macstu.py
```

2. Check Mac Studio disk and memory headroom.
3. Check whether `~/mlx-vlm-env/` exists and which version it contains.
4. Confirm no process is already bound to `8081`.
5. Do not stop unrelated sidecars unless memory pressure requires it.

## Upgrade / Install

Proposed execution shape:

```bash
ssh macstudio "python3 -m venv ~/mlx-vlm-env || true"
ssh macstudio "~/mlx-vlm-env/bin/pip install -U pip wheel"
ssh macstudio "~/mlx-vlm-env/bin/pip install -U mlx-vlm"
ssh macstudio "~/mlx-vlm-env/bin/python -c 'import mlx_vlm; print(mlx_vlm.__version__)'"
```

If PyPI lacks the needed server features, install from upstream main and record the commit:

```bash
ssh macstudio "~/mlx-vlm-env/bin/pip install -U 'git+https://github.com/Blaizzy/mlx-vlm.git'"
```

Use escalation only where required by network/sandbox policy.

## Model Download

Download the selected model through the Mac Studio venv:

```bash
ssh macstudio "~/mlx-vlm-env/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('mlx-community/Qwen3.6-35B-A3B-4bit')
PY"
```

If comparing Qwen3-VL:

```bash
ssh macstudio "~/mlx-vlm-env/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('mlx-community/Qwen3-VL-32B-Instruct-4bit')
PY"
```

## Launch

Primary launch shape:

```bash
ssh macstudio "nohup ~/mlx-vlm-env/bin/python -m mlx_vlm.server \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --host 0.0.0.0 --port 8081 \
  > /tmp/mlx-vlm-qwen36-vl.log 2>&1 &"
```

If the installed `mlx-vlm` CLI exposes additional flags for continuous batching, APC, vision cache, or metrics, prefer explicit flags and record the exact command in the benchmark writeup.

Stop command:

```bash
ssh macstudio "pkill -f 'mlx_vlm.server.*8081'"
```

Logs:

```bash
ssh macstudio "tail -50 /tmp/mlx-vlm-qwen36-vl.log"
```

## Smoke Tests

1. Health:

```bash
curl -s http://<MAC_STUDIO_IP>:8081/v1/models | python3 -m json.tool
```

2. Text sanity:

```bash
curl -s http://<MAC_STUDIO_IP>:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen3.6-35B-A3B-4bit","messages":[{"role":"user","content":"Reply ok"}],"max_tokens":16}'
```

3. Image sanity:

- Send a small base64 image block.
- Confirm the model identifies obvious content.
- Record whether `image_url` data URLs are accepted.

4. Tool-call smoke:

Run the existing API tool harness if `tools[]` is supported:

```bash
python3 scripts/bench/bench_api_tool_call.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --output docs/models/benchmarks/logs/qwen36-35b-a3b-4bit/api-tool-test-mlx-vlm.json
```

## Benchmarks

### Existing Agent Tool Benchmark

Create an OpenCode client template only if the server passes tool-call smoke.

Then run:

```bash
python3 scripts/bench/bench_agent_tool_call.py \
  --model macstudio-mlx-vlm/mlx-community/Qwen3.6-35B-A3B-4bit \
  --scenario both \
  --warmup 1 --runs 3 \
  --skip-permissions \
  --output docs/models/benchmarks/logs/qwen36-35b-a3b-4bit/agent-bench-mlx-vlm.json
```

This benchmark is expected to be a secondary signal. `mlx-vlm` should not be judged primarily as a text-agent replacement.

### New Visual-Agent Benchmark

After `plan-vlm-visual-agent-benchmark-harness.md` is implemented:

1. Run HITL fixture review:

```bash
python3 scripts/bench/bench_vlm_agent_task.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --hitl-review \
  --tasks ocr,chart,screenshot,video
```

2. Run smoke:

```bash
python3 scripts/bench/bench_vlm_agent_task.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --suite smoke \
  --tasks all \
  --output docs/models/benchmarks/logs/qwen36-35b-a3b-4bit/vlm-agent-task-smoke-mlx-vlm.json
```

3. Run standard after smoke passes:

```bash
python3 scripts/bench/bench_vlm_agent_task.py \
  --base-url http://<MAC_STUDIO_IP>:8081/v1 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --suite standard \
  --tasks all \
  --output docs/models/benchmarks/logs/qwen36-35b-a3b-4bit/vlm-agent-task-mlx-vlm.json
```

4. Repeat with `mlx-community/Qwen3-VL-32B-Instruct-4bit` only if Qwen3.6-A3B is weak on OCR/chart/screenshot or if a dedicated-VL baseline is needed.

## Decision Criteria

Keep `mlx-vlm` + Qwen VL as a documented sidecar if the standard visual benchmark shows:

- OCR: at least 80% local field-level pass.
- Chart: at least 70% local QA pass.
- Screenshot: at least 70% click/bbox hit rate.
- Video: at least 60% short-video or sampled-frame pass.
- Tool formatting: passes strict JSON/tool-call output for the majority of tasks.
- Same-image follow-up: measurable second-turn speedup from vision cache/APC.
- Operational fit: stable on `8081`, no repeated OOM, no server crash, clear logs.

Reject or keep as research-only if:

- image inputs are flaky through API,
- tool calls are not parseable,
- memory pressure blocks routine use,
- repeated visual turns do not improve latency,
- Qwen3-VL baseline substantially outperforms Qwen3.6-A3B on core visual tasks.

## Documentation Updates After Successful Deploy

If the sidecar is worth keeping, update in one commit:

- `README.md` sidecar list, server table, and limitations.
- `CLAUDE.md` and `AGENTS.md` mirrored server bullet, data flow, common commands.
- `configs/README.md`.
- `configs/clients/mlx-vlm/opencode.json` if agent tooling works.
- `configs/clients/README.md`.
- `scripts/switch_opencode_config.py` if adding an OpenCode template.
- `docs/servers/mlx-vlm/summary.md`.
- `docs/servers/README.md`.
- `docs/models/model-summary.md` and relevant Qwen family doc if benchmark findings are meaningful.
- `docs/models/benchmarks/model-benchmark-tool-call.md` and a new visual benchmark summary if the new harness is implemented.

Do not record live run-state in canonical docs.
