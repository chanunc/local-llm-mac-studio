# mlx-openai-server Maintenance

## Upgrading

```bash
~/mlx-openai-server-env/bin/pip install --upgrade mlx-openai-server

# Verify JANG patch still works (should print True)
JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python -c "
import mlx_lm; print('patch active:', mlx_lm.load.__name__ == '_jang_patched_load')"
```

The `.pth` patch survives upgrades. Only reinstall if the venv itself is deleted and recreated. See [JANG Patch](jang-patch.md) for installation instructions.

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
