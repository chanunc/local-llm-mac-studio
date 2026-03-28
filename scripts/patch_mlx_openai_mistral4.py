"""Patch mlx-openai-server and mlx_lm for Mistral 4 MLA text support.

This patch does four things:
1. Installs a vendored `mlx_lm.models.mistral4` module.
2. Updates `mlx_lm.models.mistral3` to dispatch `text_config.model_type == "mistral4"`.
3. Allows `reasoning_effort="none"` in chat template kwargs and chat requests.
4. Prevents mlx-openai-server from forcing Mistral Small 4 into an unsupported
   default `reasoning_effort="medium"` path.

The patch is version-gated and only auto-applies to known-good package pairs.
Use `--force-unknown-version` or `MLX_MISTRAL4_PATCH_FORCE=1` only after reviewing
the target files.

Run on the Mac Studio after mlx-openai-server installation or upgrade:
    ~/mlx-openai-server-env/bin/python scripts/patch_mlx_openai_mistral4.py
"""

from __future__ import annotations

import argparse
import os
import sys
import sysconfig
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


FORCE_ENV_VAR = "MLX_MISTRAL4_PATCH_FORCE"
MARKER = "# --- MISTRAL4 MLA patch ---"
SUPPORTED_VERSION_PAIRS = {
    ("0.31.1", "1.7.0"),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_site_packages(explicit_path: Path | None) -> Path:
    if explicit_path is not None:
        if not explicit_path.exists():
            print(f"ERROR: site-packages path does not exist: {explicit_path}", file=sys.stderr)
            sys.exit(1)
        return explicit_path

    purelib = Path(sysconfig.get_paths()["purelib"])
    if not purelib.exists():
        print(f"ERROR: could not resolve site-packages for {sys.executable}", file=sys.stderr)
        sys.exit(1)
    return purelib


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def replace_once(path: Path, old: str, new: str, *, name: str) -> None:
    content = read_text(path)
    if new in content:
        print(f"{name}: already patched")
        return
    if old not in content:
        print(f"ERROR: could not find expected block in {path}", file=sys.stderr)
        sys.exit(1)
    write_text(path, content.replace(old, new, 1))
    print(f"{name}: patched")


def package_version(dist_name: str) -> str:
    try:
        return version(dist_name)
    except PackageNotFoundError:
        print(f"ERROR: package is not installed: {dist_name}", file=sys.stderr)
        sys.exit(1)


def version_report() -> tuple[str, str]:
    return package_version("mlx-lm"), package_version("mlx-openai-server")


def force_requested(cli_force: bool) -> bool:
    return cli_force or (os.environ.get(FORCE_ENV_VAR) == "1")


def validate_versions(mlx_lm_version: str, server_version: str, *, force: bool) -> None:
    pair = (mlx_lm_version, server_version)
    if pair in SUPPORTED_VERSION_PAIRS:
        print(
            "Version gate: supported "
            f"(mlx-lm {mlx_lm_version}, mlx-openai-server {server_version})"
        )
        return

    supported = ", ".join(
        f"mlx-lm {mlx_lm} + mlx-openai-server {server}"
        for mlx_lm, server in sorted(SUPPORTED_VERSION_PAIRS)
    )
    message = (
        "Unsupported package pair for automatic patching: "
        f"mlx-lm {mlx_lm_version}, mlx-openai-server {server_version}. "
        f"Known-good pairs: {supported}. "
        f"Review the target files, then rerun with --force-unknown-version or "
        f"{FORCE_ENV_VAR}=1 if the code layout is still compatible."
    )
    if force:
        print(f"WARNING: {message}")
        return

    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def install_mistral4_module(site_packages: Path) -> None:
    src = repo_root() / "patches/mlx_lm/mistral4.py"
    if not src.exists():
        print(f"ERROR: missing vendored patch module: {src}", file=sys.stderr)
        sys.exit(1)

    dst = site_packages / "mlx_lm/models/mistral4.py"
    content = src.read_text(encoding="utf-8")
    if dst.exists() and dst.read_text(encoding="utf-8") == content:
        print("mistral4.py: already installed")
        return
    dst.write_text(content, encoding="utf-8")
    print(f"mistral4.py: installed to {dst}")


def patch_mistral3_dispatch(site_packages: Path) -> None:
    path = site_packages / "mlx_lm/models/mistral3.py"
    replace_once(
        path,
        "from . import llama, ministral3",
        "from . import llama, ministral3, mistral4\n" + MARKER,
        name="mistral3 import",
    )
    replace_once(
        path,
        """        if args.text_config.get("model_type") == "ministral3":
            self.language_model = ministral3.Model(
                ministral3.ModelArgs.from_dict(args.text_config)
            )
        else:
            self.language_model = llama.Model(
                llama.ModelArgs.from_dict(args.text_config)
            )""",
        """        text_model_type = args.text_config.get("model_type")
        if text_model_type == "mistral4":
            self.language_model = mistral4.Model(
                mistral4.ModelArgs.from_dict(args.text_config)
            )
        elif text_model_type == "ministral3":
            self.language_model = ministral3.Model(
                ministral3.ModelArgs.from_dict(args.text_config)
            )
        else:
            self.language_model = llama.Model(
                llama.ModelArgs.from_dict(args.text_config)
            )""",
        name="mistral3 dispatch",
    )


def patch_openai_schema(site_packages: Path) -> None:
    path = site_packages / "app/schemas/openai.py"
    replace_once(
        path,
        """class ChatTemplateKwargs(OpenAIBaseModel):
    \"\"\"Represents the arguments for a chat template.\"\"\"

    enable_thinking: bool = Field(default=True, description=\"Whether to enable thinking.\")
    reasoning_effort: Literal[\"low\", \"medium\", \"high\"] = Field(
        default=\"medium\", description=\"The reasoning effort level.\"
    )""",
        """class ChatTemplateKwargs(OpenAIBaseModel):
    \"\"\"Represents the arguments for a chat template.\"\"\"

    enable_thinking: bool = Field(default=True, description=\"Whether to enable thinking.\")
    reasoning_effort: Literal[\"none\", \"low\", \"medium\", \"high\"] = Field(
        default=\"medium\", description=\"The reasoning effort level.\"
    )""",
        name="openai ChatTemplateKwargs",
    )
    replace_once(
        path,
        """    user: str | None = Field(None, description=\"User identifier.\")
    repetition_penalty: float | None = Field(
        None, description=\"Repetition penalty for token generation.\"
    )""",
        """    user: str | None = Field(None, description=\"User identifier.\")
    reasoning_effort: Literal[\"none\", \"low\", \"medium\", \"high\"] | None = Field(
        None, description=\"Reasoning effort shortcut for chat template kwargs.\"
    )
    repetition_penalty: float | None = Field(
        None, description=\"Repetition penalty for token generation.\"
    )""",
        name="openai ChatCompletionRequest.reasoning_effort",
    )


def patch_mlx_lm_handler(site_packages: Path) -> None:
    path = site_packages / "app/handler/mlx_lm.py"
    replace_once(
        path,
        """            chat_template_kwargs = (
                request.chat_template_kwargs.model_dump() if request.chat_template_kwargs else {}
            )""",
        """            chat_template_kwargs = (
                request.chat_template_kwargs.model_dump() if request.chat_template_kwargs else {}
            )

            requested_reasoning_effort = getattr(request, "reasoning_effort", None)
            if requested_reasoning_effort and "reasoning_effort" not in chat_template_kwargs:
                chat_template_kwargs["reasoning_effort"] = requested_reasoning_effort

            model_id = (getattr(self, "served_model_name", None) or request.model or "").lower()
            if "mistral-small-4" in model_id:
                effort = str(chat_template_kwargs.get("reasoning_effort", "medium")).lower()
                if effort in {"", "low", "medium"}:
                    effort = "none"
                chat_template_kwargs["reasoning_effort"] = effort
                chat_template_kwargs["enable_thinking"] = effort != "none" """,
        name="mlx_lm handler reasoning_effort",
    )


def patch_responses_translation(site_packages: Path) -> None:
    path = site_packages / "app/api/endpoints.py"
    replace_once(
        path,
        """        if reasoning_effort in {"none", "minimal"}:
            chat_request_payload["chat_template_kwargs"] = {
                "enable_thinking": False,
            }""",
        """        if reasoning_effort in {"none", "minimal"}:
            chat_request_payload["chat_template_kwargs"] = {
                "enable_thinking": False,
                "reasoning_effort": "none",
            }""",
        name="responses reasoning translation",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply the local Mistral 4 MLA patch to mlx-openai-server."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only validate the environment and supported package versions.",
    )
    parser.add_argument(
        "--force-unknown-version",
        action="store_true",
        help="Allow patching an unvalidated mlx-lm / mlx-openai-server version pair.",
    )
    parser.add_argument(
        "--print-versions",
        action="store_true",
        help="Print detected package versions before exiting or patching.",
    )
    parser.add_argument(
        "--site-packages",
        type=Path,
        help="Override the target site-packages directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    site_packages = find_site_packages(args.site_packages)
    mlx_lm_version, server_version = version_report()

    if args.print_versions or args.check_only:
        print(f"site-packages: {site_packages}")
        print(f"mlx-lm: {mlx_lm_version}")
        print(f"mlx-openai-server: {server_version}")

    validate_versions(
        mlx_lm_version,
        server_version,
        force=force_requested(args.force_unknown_version),
    )

    if args.check_only:
        print("Patch compatibility check passed.")
        return

    install_mistral4_module(site_packages)
    patch_mistral3_dispatch(site_packages)
    patch_openai_schema(site_packages)
    patch_mlx_lm_handler(site_packages)
    patch_responses_translation(site_packages)
    print("Mistral 4 MLA patch complete.")


if __name__ == "__main__":
    main()
