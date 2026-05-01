# Plan: Deploy Osaurus Qwen3.6-35B-A3B JANGTQ4 as main vmlx server and run agent benchmark

Status: active
Created: 2026-05-01
Canonical: no

## Context

Target model: [`OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4`](https://huggingface.co/OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4).

The model is a JANGTQ4 / `weight_format: mxtq` bundle for `Qwen/Qwen3.6-35B-A3B`: 35B total / ~3B active MoE, `qwen3_5_moe`, 30 Gated DeltaNet linear-attention layers + 10 full-attention layers, routed experts quantized with 4-bit TurboQuant codebooks, attention/embed/shared expert/lm head at 8-bit or fp16, vision tower preserved, ~19.7 GB on disk, Apache-2.0.

The Hugging Face card states `jangtq_runtime.safetensors` is required and stock `mlx_lm.load()` cannot parse the `.tq_packed` tensors. In this repo, JANGTQ deployments use `vmlx` through the MLX Studio bundled Python because that is the only known local path with `load_jangtq` and the TurboQuant Metal kernels.

## Deployment posture

Deploy this model as the sole main server on port `8000` for a fair benchmark. Stop the current Ling `vllm-mlx` process and any other port-8000 server first, then start `vmlx` with `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` on `0.0.0.0:8000`.

This is a deliberate temporary production-state change for benchmarking. Capture the pre-change Ling command before stopping it so it can be restored exactly after the benchmark if desired.

## Goal

Deploy `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` through `vmlx` as the main port-8000 server, confirm it can serve OpenAI-compatible chat completions with tools and reasoning parsing, then run the existing OpenCode agent tool benchmark and save raw output under `docs/models/benchmarks/`.

## Non-goals

- No permanent production promotion unless follow-up docs explicitly make it persistent.
- No client-template default switch in `configs/clients/vmlx/opencode.json`.
- No refusal-rate or uncensored-content benchmark.

## Phase 1 - Preflight

1. Capture current port-8000 process before replacing it:

```bash
ssh macstudio "ps -axo pid,rss,command | grep -E '[v]llm-mlx|[L]ing-2.6-flash|[v]mlx_engine|[m]lx-openai-server|[o]mlx' | tee /tmp/pre-osaurus-port8000-processes.txt"
```

2. Stop existing port-8000 servers:

```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 3"
```

3. Check free memory after stopping the prior main server:

```bash
ssh macstudio "vm_stat && memory_pressure"
```

Decision rule: proceed only if there is enough headroom for ~22 GB model residency plus KV/cache overhead.

4. Confirm main port is free:

```bash
ssh macstudio "lsof -nP -iTCP:8000 -sTCP:LISTEN || true"
```

If anything is still listening on `8000`, identify and stop it before continuing.

5. Verify MLX Studio bundled Python and JANGTQ loader:

```bash
ssh macstudio 'BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  test -x "$BP/bin/python3" && \
  ls "$BP"/lib/python3.12/site-packages/jang_tools/load_jangtq*.py && \
  ls "$BP"/lib/python3.12/site-packages/jang_tools/turboquant/*kernel*.py'
```

6. Apply the existing vmlx MLLM tool patch:

```bash
ssh macstudio 'BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  "$BP/bin/python3" ~/setup-llm-macstu/scripts/patches/patch_vmlx_jangtq_mllm_tools.py'
```

## Phase 2 - Download and verify model files

Download into the normal Hugging Face cache:

```bash
ssh macstudio <<'REMOTE'
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
"$BP/bin/python3" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4"))
PY
REMOTE
```

Capture the snapshot path:

```bash
ssh macstudio <<'REMOTE'
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
"$BP/bin/python3" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4", local_files_only=True))
PY
REMOTE
```

Verify required JANGTQ sidecar and weight files:

```bash
ssh macstudio <<'REMOTE'
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=$("$BP/bin/python3" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4", local_files_only=True))
PY
)
test -f "$SNAP/jangtq_runtime.safetensors"
ls "$SNAP"/*.safetensors | wc -l
find "$SNAP" -maxdepth 1 \( -name "*.tq_packed" -o -name "*.safetensors" \) | head
REMOTE
```

If `jangtq_runtime.safetensors` is missing, fetch it explicitly:

```bash
ssh macstudio <<'REMOTE'
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=$("$BP/bin/python3" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4", local_files_only=True))
PY
)
hf download OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 jangtq_runtime.safetensors --local-dir "$SNAP"
REMOTE
```

## Phase 3 - Start vmlx as main server on port 8000

Start as the only main server:

```bash
ssh macstudio <<'REMOTE'
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=$("$BP/bin/python3" - <<'PY'
from huggingface_hub import snapshot_download
print(snapshot_download("OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4", local_files_only=True))
PY
)
nohup "$BP/bin/python3" -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &
echo $! > /tmp/vmlx-osaurus-qwen36-jangtq4.pid
REMOTE
```

Verify fast path:

```bash
ssh macstudio "tail -80 /tmp/vmlx-osaurus-qwen36-jangtq4.log"
```

Required log signals:

- `JANGTQ v2 loaded`
- `Replaced <N> modules with TurboQuantLinear` or equivalent native TQ replacement line
- No `JANGTQ fast path unavailable`
- No crash from `--smelt` / `--flash-moe` because neither flag is used

## Phase 4 - API and tool smoke tests

Set local endpoint:

```bash
BASE=http://<MAC_STUDIO_IP>:8000/v1
MODEL=OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4
```

Model list:

```bash
curl -s "$BASE/models" | python3 -m json.tool
```

Basic chat:

```bash
curl -s "$BASE/chat/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Say ok in one word.\"}],\"temperature\":0,\"max_tokens\":32}" \
  | python3 -m json.tool
```

Tool-call API benchmark:

```bash
mkdir -p docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus
python3 scripts/bench/bench_api_tool_call.py \
  --base-url "$BASE" \
  --model "$MODEL" \
  --output docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/api-tool-test-vmlx.json
```

API throughput benchmark:

```bash
python3 scripts/bench/bench_api_server.py \
  --base-url "$BASE" \
  --model "$MODEL" \
  --output docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/api-server-vmlx.json
```

## Phase 5 - OpenCode agent benchmark

`scripts/bench/bench_agent_tool_call.py --base-url` only overrides the health check. OpenCode itself reads `~/.config/opencode/opencode.json`, so temporarily point the global OpenCode config at this model, then restore it.

Backup:

```bash
cp ~/.config/opencode/opencode.json ~/.config/opencode/opencode.json.before-osaurus-qwen36-jangtq4
```

Patch the live OpenCode config manually or with `jq`:

```bash
jq '
  .provider.macstudio.options.baseURL = "http://<MAC_STUDIO_IP>:8000/v1" |
  .provider.macstudio.models["OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4"] = {
    "name": "Osaurus Qwen3.6-35B-A3B JANGTQ4 (vmlx main)",
    "tools": true,
    "reasoning": true,
    "limit": {"context": 262144, "output": 8192}
  } |
  .model = "macstudio/OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4" |
  .small_model = "macstudio/OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4"
' ~/.config/opencode/opencode.json > /tmp/opencode-osaurus.json &&
mv /tmp/opencode-osaurus.json ~/.config/opencode/opencode.json
```

Run a one-shot smoke before the full benchmark:

```bash
opencode run --format json --model macstudio/OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 "Browse www.example.com" | tee /tmp/opencode-osaurus-smoke.jsonl
```

If smoke emits raw `<tool_call>` text or visible `<think>` in `content`, stop and inspect vmlx parser flags and the OpenCode model capability flags.

Run measured benchmark:

```bash
python3 scripts/bench/bench_agent_tool_call.py \
  --model macstudio/OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4 \
  --base-url "$BASE" \
  --scenario both \
  --warmup 1 \
  --runs 3 \
  --output docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/agent-bench-vmlx.json \
  --verbose
```

Restore OpenCode config immediately:

```bash
mv ~/.config/opencode/opencode.json.before-osaurus-qwen36-jangtq4 ~/.config/opencode/opencode.json
```

## Phase 6 - Shutdown or restore

Stop the Osaurus process only if restoring the previous main server or ending the benchmark:

```bash
ssh macstudio 'if test -f /tmp/vmlx-osaurus-qwen36-jangtq4.pid; then kill "$(cat /tmp/vmlx-osaurus-qwen36-jangtq4.pid)" && rm /tmp/vmlx-osaurus-qwen36-jangtq4.pid; fi'
```

If restoring Ling, use the exact command captured in `/tmp/pre-osaurus-port8000-processes.txt`.

Verify current main process:

```bash
ssh macstudio "ps -axo pid,rss,command | grep -E '[v]llm-mlx|[L]ing-2.6-flash|[v]mlx_engine'"
```

## Phase 7 - Documentation updates after results

After successful runs:

- Validate JSON: `jq empty docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/*.json`.
- Add a section to `docs/models/benchmarks/model-benchmark-api-server.md` for API throughput.
- Add a row and per-model note to `docs/models/benchmarks/model-benchmark-agent-tool-call.md`.
- Add a Qwen3.6 family entry to `docs/models/per-model/model-summary-qwen-3-6.md`.
- Add a model row to `README.md` only if the result is worth keeping as a documented model in the roster.
- Update `docs/models/techniques/model-quantization-turboquant.md` if the run reveals new JANGTQ/vmlx behavior.
- Update `docs/current.md` if this main-server deployment persists beyond the benchmark session.

## Failure handling

- Missing `jangtq_runtime.safetensors`: fetch the required model sidecar explicitly and retry once.
- `JANGTQ fast path unavailable`: stop the Osaurus server, do not benchmark, document the loader failure.
- Raw tool XML in OpenCode: verify `--enable-auto-tool-choice --tool-call-parser qwen3` and `patch_vmlx_jangtq_mllm_tools.py`.
- Visible thinking text: verify `--reasoning-parser qwen3` and `"reasoning": true` in OpenCode config.
- Memory pressure after stopping the previous main server: abort and document the failure.

## Success criteria

- Previous main-server command is captured before replacement.
- `/v1/models` on port `8000` exposes `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4`.
- Basic chat succeeds.
- Tool-call API benchmark completes with structured `tool_calls[]`.
- OpenCode `browse` and `search` scenarios complete, or failures are captured with logs.
- Raw JSON and verbose logs are saved under `docs/models/benchmarks/qwen36-35b-a3b-jangtq4-osaurus/`.
