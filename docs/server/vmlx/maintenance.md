# vmlx Maintenance

Operational notes for the `vmlx` JANGTQ server on Mac Studio. See [`summary.md`](summary.md) for the architectural overview.

## Index
- [Lifecycle](#lifecycle)
  - [Start](#start)
  - [Stop](#stop)
  - [Status](#status)
- [Switching to/from other servers](#switching-tofrom-other-servers)
- [Upgrading](#upgrading)
- [Changing the served model](#changing-the-served-model)
- [Model download cancellation](#model-download-cancellation)
- [Memory / performance tuning](#memory--performance-tuning)
- [Tool use and reasoning (MLLM models)](#tool-use-and-reasoning-mllm-models)
  - [Required server flags](#required-server-flags)
  - [Required source patch](#required-source-patch-scriptspatch_vmlx_jangtq_mllm_toolspy)
- [Troubleshooting](#troubleshooting)

---

## Lifecycle

### Start

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  > /tmp/vmlx.log 2>&1 &
```

First-boot weight load is ~10 s on a warm FS cache (`JANGTQ v2 loaded in 10.1s` in the log), up to ~60 s on cold first access after reboot.

The three parser flags are required for OpenCode / Claude Code tool use and Qwen3 thinking. See [§ Tool use and reasoning (MLLM models)](#tool-use-and-reasoning-mllm-models) for what each flag does and why a one-time source patch is also needed.

### Stop

```bash
pkill -f vmlx_engine
```

No `brew services` entry; no launchd integration. The process does not auto-restart on crash — re-run the start command if it dies.

### Status

```bash
pgrep -f vmlx_engine && echo "vmlx up" || echo "vmlx down"
ps -o pid,rss,comm -p "$(pgrep -f vmlx_engine)"
tail -20 /tmp/vmlx.log
```

Healthy log tail contains `JANGTQ v2 loaded … native TQ, no dequant` and `Replaced N modules with TurboQuantLinear`. The HTTP layer logs each request as `INFO: <ip>:<port> - "POST /v1/chat/completions HTTP/1.1" 200 OK`.

## Switching to/from other servers

Only one server owns port 8000 at a time. Full switch recipes (with `pkill` of sibling servers) live in the top-level [`CLAUDE.md` § Common Commands](../../../CLAUDE.md) and [`configs/README.md` § Switching Servers](../../../configs/README.md#switching-servers).

Minimum pre-start cleanup when coming from any other server:

```bash
pkill -f vllm-mlx
pkill -f mlx-openai-server
/opt/homebrew/bin/brew services stop omlx
sleep 2
```

## Upgrading

Upgrade path = re-install the MLX Studio DMG. There is no `pip install -U` route, because the loader + Metal kernels live inside the app bundle, not in pypi. After upgrade:

1. Close the Electron UI if it happens to be open (`osascript -e 'quit app "vMLX"'`).
2. Replace the app bundle (`cp -R "/Volumes/vMLX-<ver>-arm64/vMLX.app" /Applications/`, overwriting).
3. **Re-verify the loader is still bundled** — occasionally a release ships with a different site-packages layout:

   ```bash
   BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
   ls $BP/lib/python3.12/site-packages/jang_tools/load_jangtq*.py
   ls $BP/lib/python3.12/site-packages/jang_tools/turboquant/*.py
   ```

4. Restart the server using the Start recipe above.

The bundled `bin/vmlx` shebang may still hardcode the maintainer's build path after upgrade; always invoke via `python3 -m vmlx_engine.cli serve` regardless.

## Changing the served model

Bundled-Python `vmlx serve` takes a single model directory as its positional argument. To swap:

1. Download the new JANGTQ model into `~/.cache/huggingface/hub/` (HuggingFace Hub standard layout works):

   ```bash
   BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
   $BP/bin/python3 -c "from huggingface_hub import snapshot_download; \
     print(snapshot_download('<org>/<model>'))"
   ```

2. Find the snapshot path it prints (`…/snapshots/<hash>/`).
3. Restart the server with the new `SNAP=` value in the Start recipe.
4. Update the model ID across all four `configs/client/vmlx/*.json` files and the `README.md` Models & Benchmarks row so clients see the new ID.

## Model download cancellation

`snapshot_download` is a blocking call — `Ctrl-C` in the foreground terminates it and leaves `.incomplete` files in the snapshot directory. Clean up with:

```bash
find ~/.cache/huggingface/hub/ -name '*.incomplete' -delete
```

For background downloads, `pkill -f snapshot_download` (or `pkill -f huggingface_hub`) is the nuclear option.

## Memory / performance tuning

No server-side knobs — vmlx uses the same `iogpu.wired_limit_mb` sysctl that `oMLX` and `vllm-mlx` depend on. If you have not set it already:

```bash
sudo sysctl iogpu.wired_limit_mb=92160
echo 'iogpu.wired_limit_mb=92160' | sudo tee /etc/sysctl.conf
```

Monitor peak usage during generation via `vm_stat` — model weights show up as **wired pages** (Metal unified memory), not RSS:

```bash
vm_stat | grep -E 'free|active|wired'
```

Expected at idle (model loaded): ~58 GB active, ~177 K wired pages. During generation: ~4 M wired pages (~66 GB).

## Tool use and reasoning (MLLM models)

OpenAI-style tool calling and the `reasoning_content` split against any `is_mllm=True` model (Qwen3.6-VL JANGTQ4-CRACK, Qwen3.5-VL-122B CRACK, etc.) require **both** runtime flags **and** a one-time source patch. Without either half, clients like OpenCode or Claude Code render the model's `<think>` block as the visible reply ("thinking nonsense") and/or watch it emit `curl` / `fetch` as plain prose instead of tool calls.

### Required server flags

| Flag | What it does | Failure mode without it |
|------|--------------|-------------------------|
| `--enable-auto-tool-choice` | Turns on OpenAI `tool_choice: auto` semantics and wires the qwen3 tool-call response parser | Raw `<tool_call>…</tool_call>` XML leaks into `content`; clients render it as text, never execute |
| `--tool-call-parser qwen3` | Extracts `<tool_call>` blocks into the structured `tool_calls[]` response field | Same as above |
| `--reasoning-parser qwen3` | Extracts `<think>…</think>` blocks into the separate `reasoning_content` response field | Whole thinking monologue leaks into `content`; OpenCode shows it as the assistant's visible reply |

All three are already in the Start recipe above.

### Required source patch (`scripts/patch_vmlx_jangtq_mllm_tools.py`)

vmlx 1.0.3 (MLX Studio v1.3.65 bundled Python) has three defects on the MLLM path that flags alone cannot fix. The patch script rewrites three sites across two files inside `$BP/lib/python3.12/site-packages/vmlx_engine/`:

1. **`engine/simple.py` — `SimpleEngine.chat()` / `.stream_chat()` drop `tools` before dispatching to MLLM.** Both methods extract `tools` as an explicit positional parameter, then forward `mllm_kwargs = dict(kwargs)` to `self._model.chat()` / `.stream_chat()`. Because `tools` was already pulled out of `kwargs`, `mllm_kwargs` never contains it. The patch injects `if template_tools: mllm_kwargs["tools"] = template_tools` after the existing `enable_thinking` / `reasoning_effort` conditionals in both MLLM branches.
2. **`models/mllm.py` — `MLLM._apply_chat_template()` ignores `tools` entirely.** Even if upstream forwarded it, the signature does not accept `tools` and the body never pushes it into `template_kwargs`. The patch adds `tools: list | None = None` to the signature, `if tools: template_kwargs["tools"] = tools` in the body, and updates both call sites to pop `tools` from kwargs and pass it through.
3. **`models/mllm.py` — `_apply_chat_template()` never parses stringified `tool_calls[].function.arguments`.** On multi-turn tool use, clients replay the prior assistant turn with `arguments` as a JSON *string* (OpenAI wire format). Qwen3's Jinja template calls `.items()` on it and raises `Can only get item pairs from a mapping`, and vmlx falls back to *"last user message only"* — losing the full tool/thinking context so the model thinks random nonsense. The patch parses stringified arguments into dicts before handing messages to the template (mirrors the non-MLLM branch in `simple.py` which already does this).

Run once on Mac Studio:

```bash
ssh macstudio "/Applications/vMLX.app/Contents/Resources/bundled-python/python/bin/python3 \
  ~/setup-llm-macstu/scripts/patch_vmlx_jangtq_mllm_tools.py"
```

Idempotent. Backups land at `mllm.py.bak.tools` / `simple.py.bak.tools` alongside each file. **Re-apply after every MLX Studio DMG upgrade** — the bundled-python tree is overwritten on install.

Upstream fix belongs at [`jjang-ai/vmlx`](https://github.com/jjang-ai/vmlx) (not yet filed); the patch script can retire once it lands.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"JANGTQ fast path unavailable"` in log | Dequant-and-requant fallback triggered; the bundled loader was not imported | Check the loader files exist under `$BP/lib/python3.12/site-packages/jang_tools/`; if missing, reinstall the DMG |
| Gibberish repeat loops on generation | Same as above (fallback produces this on the MiniMax family) | Same |
| Server start fails with `ValueError: weight_format=mxtq` | `--smelt` or `--flash-moe` was passed | Remove those flags ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)) |
| `exec: /Users/eric/mlx/...: no such file` | You ran `$BP/bin/vmlx` directly; the shebang is broken | Use `$BP/bin/python3 -m vmlx_engine.cli serve …` |
| `OSError: port already in use` | Another server still holds `:8000` | Run the pre-start cleanup block above |
| Empty response / hang on first request | First-request JIT compilation of Metal kernels | Wait ~30 s on the first generation; subsequent requests are fast |
| OpenCode shows the model's `<think>` block as the visible reply ("thinking nonsense") | `--reasoning-parser qwen3` missing OR the OpenCode model entry lacks `"reasoning": true` | Add the flag (see Start recipe) and `"reasoning": true` in `configs/client/vmlx/opencode.json` |
| Model emits `curl` / `fetch` as prose instead of calling a tool, with `prompt_tokens` ~24 | MLLM path dropped the `tools[]` array before the chat template (bugs 1 + 2 above) | Run `scripts/patch_vmlx_jangtq_mllm_tools.py` on Mac Studio and restart vmlx |
| Log warns `Failed to apply chat template: Can only get item pairs from a mapping, using last user message` after the first tool call | MLLM path never parses stringified `tool_calls[].function.arguments` (bug 3 above) | Same — the patch script fixes all three bugs together |

For anything loader-related, the canonical public tracker is [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5).
