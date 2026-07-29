"""The AuxiLab publishing guarantee, enforced as a test.

The published package must run with no cloud SDK, no credentials, and no network. These
checks fail the build if an Azure import, an SDK dependency, or a cloud environment
variable is reintroduced — which is easy to do by accident when `enterprise/` is sitting
in the same repository.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Directories that are deliberately excluded — kept for reference, deployed separately.
EXCLUDED = {"enterprise", ".venv", ".git", "node_modules", "__pycache__"}

#: Development tooling. Still scanned for cloud SDKs, but exempt from the no-networking
#: rule: the test suite and the screenshot capture script legitimately open sockets and
#: drive a local HTTP server. Neither ships in the wheel.
TOOLING_DIRS = {"tests", "docs"}

#: Import roots that must never appear in the published package.
BANNED_IMPORTS = {
    "azure",
    "msal",
    "openai",
    "boto3",
    "botocore",
    "google",
    "azureml",
    "applicationinsights",
    "opencensus",
}

#: Substrings that flag a cloud/auth dependency in requirements.
BANNED_REQUIREMENTS = (
    "azure",
    "msal",
    "openai",
    "boto3",
    "google-cloud",
    "applicationinsights",
    "opencensus",
    "authlib",
    "python-jose",
)


#: This file names the very strings it bans, so it is excluded from its own text scans.
SELF = Path(__file__).resolve()


def published_python_files() -> list[Path]:
    """Every .py file that ships as part of the standalone tool."""
    return [
        path
        for path in ROOT.rglob("*.py")
        if not any(part in EXCLUDED for part in path.relative_to(ROOT).parts)
    ]


def scannable_text_files() -> list[Path]:
    """Published files whose raw text can be searched for banned markers."""
    return [path for path in published_python_files() if path.resolve() != SELF]


def imported_roots(path: Path) -> set[str]:
    """Top-level module names imported by a file, including lazy in-function imports."""
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


# --------------------------------------------------------------------------- #
def test_the_scanner_actually_finds_files():
    """A guard that silently scans nothing would pass forever."""
    files = published_python_files()
    assert len(files) >= 10
    names = {p.name for p in files}
    assert {"mcp_server.py", "app.py", "cli.py"} <= names


@pytest.mark.parametrize("path", published_python_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_cloud_sdk_imports(path):
    offending = imported_roots(path) & BANNED_IMPORTS
    assert not offending, f"{path.relative_to(ROOT)} imports {sorted(offending)}"


def test_requirements_contain_no_cloud_sdks():
    for name in ("requirements.txt", "requirements-dev.txt"):
        text = (ROOT / name).read_text("utf-8").lower()
        for line in text.splitlines():
            entry = line.split("#", 1)[0].strip()
            if not entry:
                continue
            for banned in BANNED_REQUIREMENTS:
                assert banned not in entry, f"{name} pulls in {entry!r}"


def test_pyproject_declares_no_cloud_sdks():
    text = (ROOT / "pyproject.toml").read_text("utf-8").lower()
    dependency_block = text.split("[tool.")[0]  # project metadata only
    for banned in BANNED_REQUIREMENTS:
        assert banned not in dependency_block, f"pyproject declares {banned}"


def test_no_azure_environment_variables_are_read():
    for path in scannable_text_files():
        text = path.read_text("utf-8")
        for marker in ("AZURE_", "AAD_", "ENTRA_", "SERVICEBUS_", "KEYVAULT_"):
            assert marker not in text, f"{path.relative_to(ROOT)} references {marker}"


def test_no_authentication_layer_in_the_published_package():
    """No tokens, no bearer headers, no RBAC — the standalone tool has no auth model."""
    for path in scannable_text_files():
        text = path.read_text("utf-8").lower()
        for marker in ("bearer ", "jwt_secret", "client_secret", "tenant_id"):
            assert marker not in text, f"{path.relative_to(ROOT)} contains {marker!r}"


def test_the_five_tools_import_with_only_pydantic_available():
    """`tools` is the reusable core; it must not reach for the MCP or demo stack."""
    heavy = {"mcp", "gradio", "fastapi", "httpx", "starlette", "uvicorn", "sqlalchemy"}
    for path in (ROOT / "compliance_tools").rglob("*.py"):
        offending = imported_roots(path) & heavy
        assert not offending, f"compliance_tools/{path.name} imports {sorted(offending)}"


def test_tools_do_not_depend_on_the_database():
    """The tools stay pure; persistence is wired in by the callers."""
    for path in (ROOT / "compliance_tools").rglob("*.py"):
        assert "local_db" not in imported_roots(path), (
            f"compliance_tools/{path.name} imports database"
        )


def test_no_network_client_libraries_anywhere():
    """The shipped package must not be able to reach the network at all."""
    network = {"requests", "httpx", "aiohttp", "urllib3", "socket"}
    checked = 0
    for path in published_python_files():
        if set(path.relative_to(ROOT).parts) & TOOLING_DIRS:
            continue
        checked += 1
        offending = imported_roots(path) & network
        assert not offending, f"{path.relative_to(ROOT)} imports {sorted(offending)}"
    assert checked >= 8, "the scan covered suspiciously few shipped files"
