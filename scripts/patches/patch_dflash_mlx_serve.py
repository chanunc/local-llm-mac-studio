"""Patch dflash-mlx 0.1.4.1+ serve.py for two upstream bugs.

Why:
  1. `DFlashModelProvider.load()` references `self.default_model_map`, but
     mlx_lm.server.ModelProvider only exposes `self._model_map`. Calling
     `dflash-serve` against any request crashes with AttributeError.
  2. `_print_startup_banner()` requires `model_provider.model_key` to be
     resolved before printing, but the model is lazy-loaded on first
     request. Result: server fails to start with
     "DFlash server requires a resolved draft model before startup."
     when the model has not loaded yet.

Both are present in `pip install dflash-mlx` 0.1.4.1 from main branch.
The 0.1.0 PyPI release uses a custom HTTPServer and does not have these
bugs, but also lacks tool-calling / sampling support. Use 0.1.4.1+ for
full OpenAI semantics.

Run on the Mac Studio:
    ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_dflash_mlx_serve.py
"""

import sys
from pathlib import Path


# Bug 1: AttributeError on DFlashModelProvider.load
OLD_1 = "self.default_model_map.get(model_path, model_path)"
NEW_1 = "self._model_map.get(model_path, model_path)"

# Bug 2: startup banner gates on model_key, which is None until first request.
# Insert a fallback to cli_args.draft_model just before the RuntimeError check.
OLD_2 = (
    '    target_ref = target_ref or model_provider.cli_args.model or "unknown"\n'
    "    if not draft_ref:"
)
NEW_2 = (
    '    target_ref = target_ref or model_provider.cli_args.model or "unknown"\n'
    '    draft_ref = draft_ref or getattr(model_provider.cli_args, "draft_model", None)\n'
    "    if not draft_ref:"
)


def find_serve_py() -> Path:
    try:
        import dflash_mlx
    except ImportError:
        print("Error: dflash_mlx not importable. Activate ~/dflash-mlx-env first.", file=sys.stderr)
        sys.exit(1)
    pkg_dir = Path(dflash_mlx.__file__).parent
    serve_py = pkg_dir / "serve.py"
    if not serve_py.exists():
        print(f"Error: {serve_py} not found.", file=sys.stderr)
        sys.exit(1)
    return serve_py


def main() -> int:
    serve_py = find_serve_py()
    text = serve_py.read_text()
    changed = False

    if NEW_1 in text and OLD_1 not in text:
        print(f"Bug 1 (default_model_map): already patched.")
    elif OLD_1 in text:
        text = text.replace(OLD_1, NEW_1)
        print(f"Bug 1 (default_model_map): patched.")
        changed = True
    else:
        # Neither old nor new — version drift.
        print(f"Warning: bug 1 pattern not found. dflash-mlx version may have moved past this fix.", file=sys.stderr)

    if NEW_2 in text and OLD_2 not in text:
        print(f"Bug 2 (banner draft_ref fallback): already patched.")
    elif OLD_2 in text:
        text = text.replace(OLD_2, NEW_2)
        print(f"Bug 2 (banner draft_ref fallback): patched.")
        changed = True
    else:
        print(f"Warning: bug 2 pattern not found. dflash-mlx version may have moved past this fix.", file=sys.stderr)

    if changed:
        serve_py.write_text(text)
        print(f"Wrote {serve_py}")
    else:
        print("No changes needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
