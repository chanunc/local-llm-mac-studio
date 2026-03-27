"""Patch vllm-mlx server.py to honour VLLM_MLX_LOG_LEVEL env var at startup.

vllm-mlx has no --log-level flag. This patch injects a logging.basicConfig()
call at the top of server.py so the env var takes effect for any launch method.

Run once after install or upgrade:
    ~/vllm-mlx-env/bin/python scripts/patch_vllm_mlx_log_level.py

Idempotent — safe to re-run.

Non-interference with JANG patch:
    The JANG wrapper (run_vllm_jang.py) already calls logging.basicConfig()
    before importing vllm-mlx. Python's basicConfig() only applies on the
    first call, so the injected call in server.py is a silent no-op when the
    JANG wrapper is used. This patch only activates for direct vllm-mlx serve.
"""
import sys
import glob

MARKER = "# --- VLLM_MLX_LOG_LEVEL patch ---"

candidates = glob.glob(
    "/Users/chanunc/vllm-mlx-env/lib/python3.*/site-packages/vllm_mlx/server.py"
)
if not candidates:
    print("ERROR: vllm_mlx/server.py not found — is vllm-mlx installed?", file=sys.stderr)
    sys.exit(1)

TARGET = candidates[0]

with open(TARGET) as f:
    content = f.read()

if MARKER in content:
    print(f"Already patched: {TARGET}")
    sys.exit(0)

OLD = "import uvicorn"
NEW = (
    "import uvicorn\n"
    f"{MARKER}\n"
    "import os as _os, logging as _logging\n"
    '_logging.basicConfig(level=getattr(_logging, _os.environ.get("VLLM_MLX_LOG_LEVEL", "INFO").upper(), _logging.INFO))\n'
)

if OLD not in content:
    print(f"ERROR: anchor 'import uvicorn' not found in {TARGET}.", file=sys.stderr)
    print("The upstream code may have changed. Manual patching required.", file=sys.stderr)
    sys.exit(1)

content = content.replace(OLD, NEW, 1)

with open(TARGET, "w") as f:
    f.write(content)

print(f"Patched: {TARGET}")
