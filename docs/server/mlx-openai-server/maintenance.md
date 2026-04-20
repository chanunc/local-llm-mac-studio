# mlx-openai-server Maintenance

## Index
- [Upgrading](#-upgrading)
- [Tool Call Arguments Patch](#-tool-call-arguments-patch)
- [Qwen Empty `<think>` Template Patch](#qwen-empty-think-template-patch)
- [Mistral Small 4 Status](#️-mistral-small-4-status)
- [Files on Mac Studio](#-files-on-mac-studio)

---

## 🔁 Upgrading

```bash
~/mlx-openai-server-env/bin/pip install --upgrade mlx-openai-server

# Verify JANG patch still works (should print True)
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

The `.pth` patch survives upgrades. Only reinstall if the venv itself is deleted and recreated. See [JANG Patch](jang-patch.md) for installation instructions.

**After upgrading**, also re-apply the tool_call arguments patch (see below).

## 🧩 Tool Call Arguments Patch

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

## Qwen Empty `<think>` Template Patch

Qwen 3.5 and 3.6 ship a Jinja chat template that re-emits `<think>\n\n</think>\n\n` for every prior assistant turn even when `reasoning_content` is empty. The serialized prompt prefix drifts (especially after tool use) → KV-cache miss → full reprocess. Affects every engine that loads the shipped template (vllm-mlx, mlx-openai-server, oMLX); fix is template-level. Source: [r/LocalLLaMA 1sg076h](https://www.reddit.com/r/LocalLLaMA/comments/1sg076h/).

**Patch (Qwen 3.5 — 5 models, both inline JSON and external `.jinja` forms):**

Old: `{%- if loop.index0 > ns.last_query_index %}`
New: `{%- if loop.index0 > ns.last_query_index and reasoning_content %}`

**Patch (Qwen 3.6 — preserves the `preserve_thinking` semantics):**

Old: `{%- if (preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index) %}`
New: `{%- if reasoning_content and ((preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index)) %}`

**Apply/re-apply (idempotent):**

```bash
ssh macstudio 'python3 << "PYEOF"
QWEN35_FILES = [
    "/Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S/tokenizer_config.json",
    "/Users/chanunc/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K/tokenizer_config.json",
    "/Users/chanunc/.omlx/models/dealignai--Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK/tokenizer_config.json",
    "/Users/chanunc/.omlx/models/mlx-community--Qwen3.5-27B-4bit/chat_template.jinja",
    "/Users/chanunc/.omlx/models/nightmedia--Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx/chat_template.jinja",
]
QWEN36_FILE = "/Users/chanunc/.omlx/models/mlx-community/Qwen3.6-35B-A3B-6bit/chat_template.jinja"
OLD_35 = "{%- if loop.index0 > ns.last_query_index %}"
NEW_35 = "{%- if loop.index0 > ns.last_query_index and reasoning_content %}"
OLD_36 = "{%- if (preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index) %}"
NEW_36 = "{%- if reasoning_content and ((preserve_thinking is defined and preserve_thinking is true) or (loop.index0 > ns.last_query_index)) %}"
def patch(p, old, new):
    s = open(p).read()
    if new in s: print(f"ALREADY {p}"); return
    if old not in s: print(f"SKIP {p}"); return
    open(p, "w").write(s.replace(old, new)); print(f"PATCHED {p}")
for p in QWEN35_FILES: patch(p, OLD_35, NEW_35)
patch(QWEN36_FILE, OLD_36, NEW_36)
PYEOF'
# Then restart whichever server hosts the patched model
```

Templates are loaded at model-load time, so a server restart is required to pick up the change. **Must be re-applied any time a model is re-downloaded** (e.g. `huggingface-cli download` overwrites `chat_template.jinja` / `tokenizer_config.json`). Originals are kept as `.bak.<timestamp>` siblings from the first patch run.

**Validation test (community-recommended):** in a fresh chat, ask the model to "generate two random 20-digit numbers and only show me the first." In a follow-up turn, ask for the second number. Pre-patch: model forgets. Post-patch: model recalls.

---

## ⚠️ Mistral Small 4 Status

No repo-managed local Mistral Small 4 patch is maintained here anymore.

`JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L` still depends on upstream `mlx-lm` gaining native `mistral4` / MLA support before it can be considered supported on `mlx-openai-server`.

For Apple Silicon local use, prefer `GGUF` on `llama.cpp` / `LM Studio` / `Ollama`. For full-feature self-deployment, Mistral's official guidance still points to `vLLM`.

---

## 📁 Files on Mac Studio

| File | Purpose |
|------|---------|
| `~/mlx-openai-server-env/` | Python 3.12 venv |
| `~/mlx-openai-server-env/.../jang_patch.pth` | Triggers JANG patch at Python startup |
| `~/mlx-openai-server-env/.../jang_mlx_patch.py` | JANG detection and loading logic |
| `~/mlx-openai-server-multimodel.yaml` | Multi-model YAML config (JANG + Qwen coder 30B 4-bit) |
| `~/run_mlx_openai_jang.py` | Legacy single-model JANG wrapper |
| `/tmp/mlx-openai-server.log` | Server log (when started with redirect) |
