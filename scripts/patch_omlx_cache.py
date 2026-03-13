import os
import sys
import re
from pathlib import Path

def get_omlx_path():
    # Try to find omlx package path
    try:
        import omlx
        return Path(omlx.__file__).parent
    except ImportError:
        # Fallback to default Homebrew path on Mac Studio
        p = Path("/opt/homebrew/Cellar/omlx/0.2.9/libexec/lib/python3.11/site-packages/omlx")
        if p.exists():
            return p
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
    
    # 1. Patch model_settings.py
    # We add hot_cache_max_size to the ModelSettings class fields
    ms_path = omlx_path / "model_settings.py"
    ms_pattern = "max_tokens: Optional[int] = Field(default=None"
    ms_replacement = "hot_cache_max_size: Optional[str] = Field(default=None, description=\"Per-model hot cache override (e.g. '10GB')\")\n    max_tokens: Optional[int] = Field(default=None"
    patch_file(ms_path, ms_pattern, ms_replacement, "model_settings.py")
    
    # 2. Patch engine_pool.py
    # We inject the hook into _load_engine right before engine creation
    ep_path = omlx_path / "engine_pool.py"
    ep_pattern = 'logger.info(f"Loading model: {model_id}")\n\n            # Create engine based on engine type'
    
    hook = """
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
                    # Fallback to global setting from settings.json
                    global_hot = GlobalSettings().cache.hot_cache_max_size
                    logger.info(f"Using global hot_cache_max_size: {global_hot} for {model_id}")
                    self._scheduler_config.hot_cache_max_size = parse_size(global_hot) if global_hot != "0" else 0
            except Exception as e:
                logger.warning(f"Failed to apply per-model cache settings: {e}")
            # --- END INJECTED HOOK ---
"""
    ep_replacement = f'logger.info(f"Loading model: {{model_id}}"){hook}\n            # Create engine based on engine type'
    patch_file(ep_path, ep_pattern, ep_replacement, "engine_pool.py")

if __name__ == "__main__":
    main()
