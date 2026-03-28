# mlx-openai-server Maintenance

## Upgrading

```bash
~/mlx-openai-server-env/bin/pip install --upgrade mlx-openai-server

# Verify JANG patch still works (should print True)
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

The `.pth` patch survives upgrades. Only reinstall if the venv itself is deleted and recreated. See [JANG Patch](jang-patch.md) for installation instructions.

**After upgrading**, also re-apply the tool_call arguments patch (see below).

If you use Mistral Small 4 on `mlx-openai-server`, also re-apply the Mistral 4 MLA patch in this repo (see below).

---

## Tool Call Arguments Patch

The Qwen3.5 chat template expects `tool_call.arguments` as a dict, but OpenAI API clients (OpenClaw, etc.) send it as a JSON string. This causes `"Can only get item pairs from a mapping"` errors.

**Patch:** `_parse_tool_call_arguments()` method added to `MLXLMHandler.refine_messages()` in `app/handler/mlx_lm.py`. It JSON-parses any stringified `arguments` before the chat template processes them.

**Apply/re-apply:**

```bash
scp scripts/patch_mlx_openai_tool_args.py macstudio:/tmp/
ssh macstudio "python3 /tmp/patch_mlx_openai_tool_args.py"
# Then restart the server
```

The patch script is idempotent (detects if already applied). Must be re-applied after every `pip install --upgrade mlx-openai-server`.

---

## Mistral 4 MLA Patch

`JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L` needs a local `mlx_lm` patch because upstream `mlx-lm` still lacks native `mistral4` text support. This repo includes:

- `scripts/deploy_mistral4_mlx_openai_server.sh` — preferred one-command flow from a client machine
- `patches/mlx_lm/mistral4.py` — vendored MLX text backend
- `scripts/patch_mlx_openai_mistral4.py` — version-gated installer for the backend plus the `reasoning_effort` fixes
- `scripts/smoke_test_mlx_openai_mistral4.py` — direct + HTTP verification after patching

**Known-good versions:**
- `mlx-lm 0.31.1`
- `mlx-openai-server 1.7.0`

The patch script fails closed on unknown version pairs. Review the target files first, then use `--force-unknown-version` or `MLX_MISTRAL4_PATCH_FORCE=1` only if the upstream layout is still compatible.

**Preferred one-command flow:**

Run from this repo on a client machine. The script stages the patch files, checks versions, reapplies the patch, restarts `mlx-openai-server`, waits for `/v1/models`, and runs the smoke test.

```bash
./scripts/deploy_mistral4_mlx_openai_server.sh --host macstudio-ts
# or on LAN:
./scripts/deploy_mistral4_mlx_openai_server.sh --host macstudio
```

**Apply/re-apply:**

```bash
ssh macstudio "rm -rf /tmp/mistral4-patch && mkdir -p /tmp/mistral4-patch/scripts /tmp/mistral4-patch/patches/mlx_lm"
scp scripts/patch_mlx_openai_mistral4.py macstudio:/tmp/mistral4-patch/scripts/
scp scripts/smoke_test_mlx_openai_mistral4.py macstudio:/tmp/mistral4-patch/scripts/
scp patches/mlx_lm/mistral4.py macstudio:/tmp/mistral4-patch/patches/mlx_lm/
ssh macstudio "cd /tmp/mistral4-patch && ~/mlx-openai-server-env/bin/python scripts/patch_mlx_openai_mistral4.py"
# Then restart the server
```

**Version check only:**

```bash
ssh macstudio "cd /tmp/mistral4-patch && ~/mlx-openai-server-env/bin/python \
  scripts/patch_mlx_openai_mistral4.py --check-only --print-versions"
```

**Post-upgrade smoke test:**

```bash
ssh macstudio "JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python \
  /tmp/mistral4-patch/scripts/smoke_test_mlx_openai_mistral4.py"
```

The patch script is idempotent and should be re-run after every `pip install --upgrade mlx-openai-server` or `pip install --upgrade mlx-lm` until upstream `mlx-lm` ships native `mistral4` support.

Smoke-tested on March 28, 2026:
- `/v1/chat/completions` returned `"hello from mistral"` for a fixed prompt
- `/v1/chat/completions` with `reasoning_effort="high"` returned `"Four"` for `2+2`
- `/v1/responses` with `reasoning.effort="none"` returned `"hello from mistral"`

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-env/.../jang_patch.pth` | Triggers JANG patch at Python startup |
| `~/mlx-openai-server-env/.../jang_mlx_patch.py` | JANG detection and loading logic |
| `~/mlx-openai-server-env/.../mlx_lm/models/mistral4.py` | Local Mistral 4 MLA backend installed by patch script |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config (JANG + nvfp4) |
| `~/run_mlx_openai_jang.py` | Legacy single-model JANG wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
