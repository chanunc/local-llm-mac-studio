# Plan: vllm-mlx Homebrew Formula & Tap

## Context

vllm-mlx is the fastest API server for MLX inference on Mac Studio (3-4% overhead vs standalone). It's currently pip-installed in `~/vllm-mlx-env/` and managed via a custom launchd plist + shell script. Creating a Homebrew formula would enable `brew install vllm-mlx` and `brew services start/stop vllm-mlx` — the same workflow as oMLX.

**Current state:** Manually started via CLI (`~/vllm-mlx-env/bin/vllm-mlx serve` or `~/run_vllm_jang.py serve`). No persistent service.

**Goal:** `brew tap chanunc/vllm-mlx && brew install vllm-mlx && brew services start vllm-mlx`

---

## Phase 1: Create the Tap Repository

### 1a. Initialize repo

```bash
mkdir -p ~/cc-prjs/homebrew-vllm-mlx/Formula
cd ~/cc-prjs/homebrew-vllm-mlx
git init
```

### 1b. Directory structure

```
homebrew-vllm-mlx/
├── Formula/
│   └── vllm-mlx.rb       ← Homebrew formula
├── scripts/
│   └── vllm-mlx-jang     ← JANG wrapper (installed to bin/)
├── README.md
└── LICENSE
```

---

## Phase 2: Write the Formula

### 2a. Skeleton formula (`Formula/vllm-mlx.rb`)

```ruby
class VllmMlx < Formula
  include Language::Python::Virtualenv

  desc "vLLM-like inference server for Apple Silicon (MLX backend)"
  homepage "https://github.com/waybarrios/vllm-mlx"
  url "https://github.com/waybarrios/vllm-mlx/archive/refs/tags/v0.2.6.tar.gz"
  sha256 "<TARBALL_SHA256>"
  license "Apache-2.0"

  depends_on "python@3.12"
  depends_on :macos  # MLX is macOS-only

  # --- 60+ resource blocks go here (Phase 3) ---

  def install
    virtualenv_install_with_resources

    # Install JANG wrapper script
    (bin/"vllm-mlx-jang").write <<~EOS
      #!/bin/bash
      # Launch vllm-mlx with JANG model support
      exec "#{libexec}/bin/python" "#{libexec}/bin/vllm-mlx-jang-wrapper" "$@"
    EOS

    # Install the Python JANG wrapper
    (libexec/"bin/vllm-mlx-jang-wrapper").write <<~PYTHON
      #!/usr/bin/env python3
      import sys, logging
      logging.basicConfig(level=logging.INFO)
      logger = logging.getLogger("jang_patch")

      import mlx_lm
      _orig_load = mlx_lm.load

      def patched_load(path_or_hf_repo, tokenizer_config=None, **kwargs):
          from pathlib import Path
          try:
              from jang_tools.loader import is_jang_model, load_jang_model
          except ImportError:
              return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)
          model_path = Path(path_or_hf_repo)
          if not model_path.is_dir():
              omlx_path = Path.home() / ".omlx" / "models" / path_or_hf_repo.replace("/", "--")
              if omlx_path.is_dir():
                  model_path = omlx_path
          if model_path.is_dir() and is_jang_model(str(model_path)):
              logger.info(f"JANG model detected: {model_path}")
              model, tokenizer = load_jang_model(str(model_path))
              logger.info(f"JANG model loaded: {type(model).__name__}")
              return model, tokenizer
          return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)

      mlx_lm.load = patched_load
      logger.info("JANG monkey-patch applied")
      from vllm_mlx.cli import main
      sys.exit(main())
      PYTHON
    chmod 0755, libexec/"bin/vllm-mlx-jang-wrapper"
  end

  # brew services start/stop/restart vllm-mlx
  service do
    run [opt_bin/"vllm-mlx-jang", "serve",
         "--host=0.0.0.0", "--port=8000",
         "#{Dir.home}/.omlx/models/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K"]
    keep_alive true
    log_path var/"log/vllm-mlx.log"
    error_log_path var/"log/vllm-mlx.log"
    working_dir var
  end

  def caveats
    <<~EOS
      vllm-mlx and oMLX both use port 8000.
      Stop one before starting the other:

        brew services stop omlx
        brew services start vllm-mlx

      To change the model, edit the service plist:
        #{opt_prefix}/homebrew.mxcl.vllm-mlx.plist

      For JANG model support, install jang_tools:
        #{opt_libexec}/bin/pip install 'jang[mlx]>=0.1.0'
    EOS
  end

  test do
    system bin/"vllm-mlx", "--help"
  end
end
```

### 2b. Get the tarball SHA256

```bash
curl -sL https://github.com/waybarrios/vllm-mlx/archive/refs/tags/v0.2.6.tar.gz | shasum -a 256
```

If no v0.2.6 tag exists, use a commit archive:
```bash
url "https://github.com/waybarrios/vllm-mlx/archive/<COMMIT_SHA>.tar.gz"
```

---

## Phase 3: Generate Resource Stanzas (Hardest Part)

Each pip dependency must be declared as a `resource` block with exact URL + sha256. vllm-mlx has 60+ transitive dependencies.

### 3a. Option A: `brew update-python-resources` (preferred)

```bash
# Install the formula skeleton first (without resources — it will fail)
brew install --verbose ./Formula/vllm-mlx.rb 2>&1 || true

# Auto-generate resource blocks
brew update-python-resources Formula/vllm-mlx.rb
```

This reads `pyproject.toml` / `setup.py` and resolves all dependencies into resource stanzas.

### 3b. Option B: `poet` (fallback)

```bash
pip install homebrew-pypi-poet
# Generate resources for vllm-mlx and all deps
poet vllm-mlx > resources.txt
```

Paste the output into the formula between `depends_on` and `def install`.

### 3c. Option C: Manual (last resort)

For each dependency in `pip freeze` output:
1. Find the sdist/wheel URL on PyPI: `https://pypi.org/project/<pkg>/#files`
2. Get sha256: `curl -sL <url> | shasum -a 256`
3. Add resource block:
```ruby
resource "package-name" do
  url "https://files.pythonhosted.org/packages/.../package-1.0.tar.gz"
  sha256 "abc123..."
end
```

### 3d. Known heavy dependencies

These will need resources (non-exhaustive):
- `mlx`, `mlx-lm`, `mlx-metal` (Apple MLX framework)
- `torch`, `torchvision` (PyTorch — large downloads)
- `transformers`, `tokenizers`, `huggingface-hub`
- `fastapi`, `uvicorn`, `starlette`, `pydantic`
- `gradio`, `gradio-client` (optional, for Gradio UI)
- `numpy`, `safetensors`, `sentencepiece`, `regex`

**Risk:** `torch` and `torchvision` are very large (~2GB combined). Consider adding `--no-deps` for torch or marking it as an optional dependency to reduce install size.

---

## Phase 4: Test Locally

### 4a. Install from local formula

```bash
cd ~/cc-prjs/homebrew-vllm-mlx
brew install --verbose ./Formula/vllm-mlx.rb
```

### 4b. Verify binary

```bash
vllm-mlx --help
vllm-mlx-jang serve --help
```

### 4c. Test service

```bash
brew services stop omlx
brew services start vllm-mlx
brew services list
curl -s http://localhost:8000/v1/models | python3 -m json.tool
brew services stop vllm-mlx
brew services start omlx
```

### 4d. Audit formula

```bash
brew audit --new-formula ./Formula/vllm-mlx.rb
```

---

## Phase 5: Install JANG Support

JANG is not a pip dependency of vllm-mlx, so it must be installed separately into the formula's venv:

```bash
$(brew --prefix vllm-mlx)/libexec/bin/pip install 'jang[mlx]>=0.1.0'
```

This is similar to how we install the JANG fork into oMLX's venv today.

---

## Phase 6: Publish

### 6a. Push to GitHub

```bash
cd ~/cc-prjs/homebrew-vllm-mlx
git add -A
git commit -m "Add vllm-mlx formula with JANG support and brew services"
git remote add origin https://github.com/chanunc/homebrew-vllm-mlx.git
git push -u origin main
```

### 6b. User install command

```bash
brew tap chanunc/vllm-mlx
brew install vllm-mlx
$(brew --prefix vllm-mlx)/libexec/bin/pip install 'jang[mlx]>=0.1.0'
brew services start vllm-mlx
```

---

## Phase 7: Maintenance

### Upgrading vllm-mlx

When a new version is released:
1. Update `url` and `sha256` in the formula
2. Re-run `brew update-python-resources Formula/vllm-mlx.rb`
3. Test: `brew reinstall vllm-mlx`
4. Commit and push

### After `brew upgrade vllm-mlx`

JANG support must be re-installed (same as oMLX pattern):
```bash
$(brew --prefix vllm-mlx)/libexec/bin/pip install 'jang[mlx]>=0.1.0'
```

---

## Risks & Alternatives

| Risk | Impact | Mitigation |
|------|--------|------------|
| 60+ resource stanzas to maintain | High — every vllm-mlx update may change deps | Use `brew update-python-resources` to auto-generate |
| `torch` + `torchvision` are 2GB+ | Long install time, large formula | Consider excluding or making optional |
| vllm-mlx has no stable release tags | Can't pin to version | Use commit SHA in url |
| v0.2.6 return bug needs patching | Formula installs broken code | Add a `patch` block in the formula or wait for upstream fix |
| JANG is a separate install step | Not fully integrated | Document in caveats, add post-install script |

### Alternative: Keep Current Setup

The existing manual CLI approach provides the same functionality with:
- Zero resource stanza maintenance
- Easier to update (`pip install --upgrade`)
- JANG wrapper already integrated
- Flexible model switching (no hardcoded model in a plist)

**Recommendation:** Only create the Homebrew formula if you want to share this with others or standardize across multiple machines. For personal use, manual CLI start/stop is simpler.

---

## Key Files

| File | Purpose |
|------|---------|
| `Formula/vllm-mlx.rb` | Homebrew formula with service block |
| `scripts/vllm-mlx-jang` | JANG wrapper shell script |
| `docs/server/vllm-mlx/summary.md` | vllm-mlx server summary (reference) |
| `docs/server/vllm-mlx/jang-patch.md` | JANG monkey-patch guide (reference) |
