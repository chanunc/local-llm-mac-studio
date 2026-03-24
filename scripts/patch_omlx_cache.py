import os
import sys
import glob
import re
from pathlib import Path


def get_omlx_path():
    # Try to find omlx package path
    try:
        import omlx
        return Path(omlx.__file__).parent
    except ImportError:
        # Fallback: find the latest installed version in Homebrew
        candidates = sorted(
            glob.glob("/opt/homebrew/Cellar/omlx/*/libexec/lib/python3.*/site-packages/omlx"),
            reverse=True
        )
        if candidates:
            return Path(candidates[0])
        print("Error: Could not find omlx package. Please run this on the Mac Studio.")
        sys.exit(1)


def patch_file(path, pattern, replacement, name):
    if not path.exists():
        print(f"Skipping {name}: {path} not found.")
        return False

    content = path.read_text()
    if "# --- INJECTED HOOK for per-model hot cache ---" in content or "hot_cache_max_size: Optional[str]" in content:
        print(f"{name} is already patched.")
        return True

    if pattern not in content:
        print(f"Error: Could not find pattern in {name}. Version mismatch or file already changed.")
        return False

    new_content = content.replace(pattern, replacement)
    path.write_text(new_content)
    print(f"Successfully patched {name}.")
    return True


def main():
    omlx_path = get_omlx_path()
    print(f"Found omlx at: {omlx_path}")

    # --- 1. Patch model_settings.py ---
    # Add hot_cache_max_size field to ModelSettings dataclass.
    # Try both the 0.2.14 style (plain dataclass) and older Field() style.
    ms_path = omlx_path / "model_settings.py"
    ms_patched = False

    # 0.2.14+ style (plain dataclass fields)
    ms_pattern_new = "    max_tokens: Optional[int] = None"
    ms_replacement_new = (
        "    hot_cache_max_size: Optional[str] = None  # Per-model hot cache override (e.g. '10GB')\n"
        "    max_tokens: Optional[int] = None"
    )
    if not patch_file(ms_path, ms_pattern_new, ms_replacement_new, "model_settings.py"):
        # 0.2.13 style (Pydantic Field)
        ms_pattern_old = "max_tokens: Optional[int] = Field(default=None"
        ms_replacement_old = (
            "hot_cache_max_size: Optional[str] = Field(default=None, "
            "description=\"Per-model hot cache override (e.g. '10GB')\")\n"
            "    max_tokens: Optional[int] = Field(default=None"
        )
        patch_file(ms_path, ms_pattern_old, ms_replacement_old, "model_settings.py")

    # --- 2. Patch engine_pool.py ---
    # Inject hook right before "# Create engine based on engine type".
    # In 0.2.14, model_settings is already retrieved above this line.
    ep_path = omlx_path / "engine_pool.py"

    hook_0214 = """\
            # --- INJECTED HOOK for per-model hot cache ---
            try:
                if model_settings and getattr(model_settings, 'hot_cache_max_size', None):
                    from .config import parse_size
                    cache_str = model_settings.hot_cache_max_size
                    logger.info(f"Using per-model hot_cache_max_size: {cache_str} for {model_id}")
                    self._scheduler_config.hot_cache_max_size = parse_size(cache_str)
            except Exception as e:
                logger.warning(f"Failed to apply per-model cache settings: {e}")
            # --- END INJECTED HOOK ---

            # Create engine based on engine type"""

    ep_pattern_0214 = "            # Create engine based on engine type"
    if not patch_file(ep_path, ep_pattern_0214, hook_0214, "engine_pool.py"):
        # 0.2.13 style
        ep_pattern_old = 'logger.info(f"Loading model: {model_id}")\n\n            # Create engine based on engine type'
        hook_old = '''logger.info(f"Loading model: {model_id}")

            # --- INJECTED HOOK for per-model hot cache ---
            try:
                from .settings import GlobalSettings
                from .utils import parse_size
                m_settings = self._server_state.settings_manager.get_settings(model_id) if hasattr(self, '_server_state') else None

                if m_settings and getattr(m_settings, 'hot_cache_max_size', None):
                    cache_str = getattr(m_settings, 'hot_cache_max_size')
                    logger.info(f"Using per-model hot_cache_max_size: {cache_str} for {model_id}")
                    self._scheduler_config.hot_cache_max_size = parse_size(cache_str)
                else:
                    global_hot = GlobalSettings().cache.hot_cache_max_size
                    logger.info(f"Using global hot_cache_max_size: {global_hot} for {model_id}")
                    self._scheduler_config.hot_cache_max_size = parse_size(global_hot) if global_hot != "0" else 0
            except Exception as e:
                logger.warning(f"Failed to apply per-model cache settings: {e}")
            # --- END INJECTED HOOK ---

            # Create engine based on engine type'''
        patch_file(ep_path, ep_pattern_old, hook_old, "engine_pool.py")


if __name__ == "__main__":
    main()
