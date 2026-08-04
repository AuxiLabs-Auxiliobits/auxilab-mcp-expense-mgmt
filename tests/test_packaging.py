"""Packaging invariants.

These catch the class of mistake that only shows up after someone runs `pip install`:
metadata that claims something the wheel does not deliver, or a data file that loads fine
from the source tree because pytest happens to be running there.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["compliance_tools", "local_db"]


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))


@pytest.mark.parametrize("package", PACKAGES)
def test_type_hints_are_advertised_to_downstream_checkers(package):
    """Without py.typed, a downstream mypy ignores our hints — and the `Typing :: Typed`
    classifier would be a claim the wheel does not honour."""
    assert (ROOT / package / "py.typed").is_file()


def test_typed_classifier_matches_reality(pyproject):
    classifiers = pyproject["project"]["classifiers"]
    if "Typing :: Typed" in classifiers:
        for package in PACKAGES:
            assert (ROOT / package / "py.typed").is_file()


def test_version_is_single_sourced(pyproject):
    """Hatch reads the version from the package, so pyproject must not also pin one."""
    assert "version" in pyproject["project"].get("dynamic", [])
    assert "version" not in pyproject["project"]
    assert pyproject["tool"]["hatch"]["version"]["path"] == "compliance_tools/__init__.py"


def test_version_is_a_valid_semver():
    import re

    from compliance_tools import __version__

    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+].+)?", __version__), __version__


def test_changelog_documents_the_current_version():
    from compliance_tools import __version__

    changelog = (ROOT / "CHANGELOG.md").read_text("utf-8")
    assert f"## [{__version__}]" in changelog, (
        f"CHANGELOG.md has no section for the current version {__version__}"
    )


def test_declared_packages_exist(pyproject):
    for package in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]:
        assert (ROOT / package / "__init__.py").is_file()


def test_data_files_live_inside_a_shipped_package():
    """Anything loaded via importlib.resources must sit in a distributed package."""
    for data_file in ("compliance_tools/baseline_policy.json", "local_db/schema.sql"):
        assert (ROOT / data_file).is_file()
        assert data_file.split("/")[0] in PACKAGES


def test_runtime_dependencies_stay_small(pyproject):
    """Four is the number the README advertises. Adding a fifth is a decision, not a drift."""
    deps = pyproject["project"]["dependencies"]
    assert len(deps) <= 4, deps


def test_project_urls_are_declared(pyproject):
    urls = pyproject["project"]["urls"]
    for key in ("Homepage", "Repository", "Issues", "Changelog", "Documentation"):
        assert key in urls, f"pyproject is missing the {key} URL"
        assert urls[key].startswith("https://")


# --------------------------------------------------------------------------- #
# Documented claims must match reality
#
# An independent audit found the README asserting its dependencies were "all pure Python"
# when pydantic-core is Rust and gradio pulls numpy and pandas. The claim had survived
# three review passes because nothing checked it. These tests check.
# --------------------------------------------------------------------------- #
def _requirements() -> list[str]:
    import re

    lines = (ROOT / "requirements.txt").read_text("utf-8").splitlines()
    entries = [ln.split("#", 1)[0].strip() for ln in lines]
    return [re.split(r"[><=!~\[]", e)[0].strip() for e in entries if e]


def test_readme_dependency_list_matches_requirements():
    readme = (ROOT / "README.md").read_text("utf-8")
    declared = _requirements()
    assert len(declared) == 4, declared
    for package in declared:
        assert f"`{package}`" in readme, f"{package} is installed but never named in the README"


def test_readme_does_not_claim_the_dependencies_are_pure_python():
    """They are not: pydantic-core is Rust, and gradio brings numpy and pandas."""
    for name in ("README.md", "requirements.txt", "SECURITY.md", "CHANGELOG.md"):
        text = (ROOT / name).read_text("utf-8").lower()
        assert "all pure python" not in text, f"{name} makes an inaccurate purity claim"


def test_supported_python_versions_agree_everywhere(pyproject):
    """`requires-python`, the classifiers, the README and the CI matrix must not drift."""
    import re

    requires = pyproject["project"]["requires-python"]
    minimum = re.search(r"(\d+\.\d+)", requires).group(1)
    assert minimum == "3.11", requires

    classifier_versions = {
        c.rsplit(" :: ", 1)[-1]
        for c in pyproject["project"]["classifiers"]
        if c.startswith("Programming Language :: Python :: 3.")
    }
    assert classifier_versions == {"3.11", "3.12", "3.13"}, classifier_versions

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    for version in classifier_versions:
        assert f'"{version}"' in ci, f"CI does not test Python {version}"

    readme = (ROOT / "README.md").read_text("utf-8")
    for version in classifier_versions:
        assert version in readme, f"README does not mention Python {version}"


def test_readme_coverage_badge_matches_the_enforced_floor(pyproject):
    """A badge quoting a number nothing enforces is a number that will rot."""
    import re

    readme = (ROOT / "README.md").read_text("utf-8")
    claimed = re.search(r"coverage-(\d+)%25", readme)
    assert claimed, "no coverage badge found in the README"
    floor = pyproject["tool"]["coverage"]["report"]["fail_under"]
    assert int(claimed.group(1)) >= floor, (
        f"badge claims {claimed.group(1)}% but CI only enforces {floor}%"
    )


def test_required_community_files_exist():
    for name in (
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "ARCHITECTURE.md",
    ):
        assert (ROOT / name).is_file(), f"{name} is missing"


def _readme_image_sources() -> list[str]:
    import re

    return re.findall(r'<img src="([^"]+)"', (ROOT / "README.md").read_text("utf-8"))


def test_readme_images_are_repository_relative():
    """Relative paths render on GitHub whatever branch you are viewing, and survive forks
    and renames. An absolute URL would have to pin a branch name — and pinning the wrong
    one produces a visibly broken hero image, which is a worse failure than the PyPI
    limitation noted in CONTRIBUTING.md's release checklist.
    """
    sources = _readme_image_sources()
    assert sources, "the README embeds no images"
    for src in sources:
        assert src.startswith("docs/images/"), f"unexpected image path: {src}"


def test_readme_images_exist_in_the_repository():
    """Catches a screenshot renamed or deleted without updating the README.

    Skipped when running from an unpacked sdist, which deliberately omits ``docs/``.
    """
    if not (ROOT / "docs" / "images").is_dir():
        pytest.skip("docs/ is not shipped in the sdist")

    for src in _readme_image_sources():
        assert (ROOT / src).is_file(), f"README references a missing image: {src}"
