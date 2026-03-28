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

## Mistral Small 4 Status

No repo-managed local Mistral Small 4 patch is maintained here anymore.

`JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L` still depends on upstream `mlx-lm` gaining native `mistral4` / MLA support before it can be considered supported on `mlx-openai-server`.

For Apple Silicon local use, prefer `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`. For full-feature self-deployment, Mistral's official guidance still points to `vLLM`.

---

## Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-env/.../jang_patch.pth` | Triggers JANG patch at Python startup |
| `~/mlx-openai-server-env/.../jang_mlx_patch.py` | JANG detection and loading logic |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config (JANG + nvfp4) |
| `~/run_mlx_openai_jang.py` | Legacy single-model JANG wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
