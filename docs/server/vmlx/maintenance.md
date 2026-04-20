# vmlx Maintenance

Operational notes for the `vmlx` JANGTQ server on Mac Studio. See [`summary.md`](summary.md) for the architectural overview.

## Lifecycle

### Start

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 > /tmp/vmlx.log 2>&1 &
```

First-boot weight load is ~10 s on a warm FS cache (`JANGTQ v2 loaded in 10.1s` in the log), up to ~60 s on cold first access after reboot.

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

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"JANGTQ fast path unavailable"` in log | Dequant-and-requant fallback triggered; the bundled loader was not imported | Check the loader files exist under `$BP/lib/python3.12/site-packages/jang_tools/`; if missing, reinstall the DMG |
| Gibberish repeat loops on generation | Same as above (fallback produces this on the MiniMax family) | Same |
| Server start fails with `ValueError: weight_format=mxtq` | `--smelt` or `--flash-moe` was passed | Remove those flags ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)) |
| `exec: /Users/eric/mlx/...: no such file` | You ran `$BP/bin/vmlx` directly; the shebang is broken | Use `$BP/bin/python3 -m vmlx_engine.cli serve …` |
| `OSError: port already in use` | Another server still holds `:8000` | Run the pre-start cleanup block above |
| Empty response / hang on first request | First-request JIT compilation of Metal kernels | Wait ~30 s on the first generation; subsequent requests are fast |

For anything loader-related, the canonical public tracker is [`jjang-ai/jangq#5`](https://github.com/jjang-ai/jangq/issues/5).
