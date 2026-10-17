"""Guards on version and licence metadata.

Cinqic Calculator declares its version in seven places across two platforms
and three packaging systems. Nothing but a test keeps them in step, and a
release that ships an installer stamped with last version's number is the
kind of defect nobody notices until a user reports it.
"""

import configparser
import re
import tomllib
from pathlib import Path

import pytest

import cinqic_calculator
from cinqic_calculator import constants

REPO_ROOT = Path(__file__).resolve().parents[1]


def read(*parts):
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pyproject():
    return tomllib.loads(read("pyproject.toml"))


@pytest.fixture(scope="module")
def buildozer():
    parser = configparser.ConfigParser()
    parser.read_string(read("android", "buildozer.spec"))
    return parser


# ---------------------------------------------------------------------------
# Version coherence
# ---------------------------------------------------------------------------
def test_package_version_matches_constants():
    assert cinqic_calculator.__version__ == constants.APP_VERSION


def test_pyproject_version_matches_constants(pyproject):
    assert pyproject["project"]["version"] == constants.APP_VERSION


def test_windows_installer_version_matches_constants():
    match = re.search(r'#define MyAppVersion "([^"]+)"', read("installer", "cinqic-calculator.iss"))
    assert match, "installer script has no MyAppVersion"
    assert match.group(1) == constants.APP_VERSION


def test_android_version_matches_the_desktop_product_version():
    """One product version across platforms, as of 1.1.0."""
    import android.android_constants as android_constants

    assert android_constants.ANDROID_APP_VERSION == constants.APP_VERSION


def test_buildozer_version_matches_android_constants(buildozer):
    import android.android_constants as android_constants

    assert buildozer["app"]["version"] == android_constants.ANDROID_APP_VERSION
    assert int(buildozer["app"]["android.numeric_version"]) == android_constants.ANDROID_VERSION_CODE


def test_android_version_code_only_ever_increases():
    """versionCode 1 shipped as Android 1.0.0 and 2 as 1.1.0; an upgrade needs a higher one."""
    import android.android_constants as android_constants

    assert android_constants.ANDROID_VERSION_CODE >= 3


def test_changelog_leads_with_the_current_version():
    """No "Unreleased" heading may sit above the version being shipped."""
    first = re.search(r"^## (.+)$", read("CHANGELOG.md"), re.MULTILINE).group(1)
    assert first.split()[0] == constants.APP_VERSION


# ---------------------------------------------------------------------------
# Identity that must not change
# ---------------------------------------------------------------------------
def test_android_package_id_is_unchanged(buildozer):
    """Changing this would orphan every existing install."""
    assert buildozer["app"]["package.name"] == "calculator"
    assert buildozer["app"]["package.domain"] == "com.cinqic"
    assert constants.APP_ID == "com.cinqic.calculator"


def test_android_requests_no_permissions(buildozer):
    assert buildozer["app"].get("android.permissions", "").strip() == ""


# ---------------------------------------------------------------------------
# Licensing
# ---------------------------------------------------------------------------
def test_license_file_is_apache_2():
    license_text = read("LICENSE")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "MIT License" not in license_text


def test_notice_file_exists_and_names_the_project():
    notice = read("NOTICE")
    assert "Cinqic Calculator" in notice
    assert "Apache License, Version 2.0" in notice


def test_pyproject_declares_apache_2(pyproject):
    assert pyproject["project"]["license"] == "Apache-2.0"


def test_no_stale_mit_references_remain():
    """The migration must be complete, not cosmetic."""
    skip_dirs = {".git", "dist", "build", "__pycache__", ".build-venv", ".build-venv-linux", ".venv"}
    offenders = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        if path.name.endswith(".egg-info") or ".egg-info" in str(path):
            continue  # generated packaging metadata, not source
        if path.name == "test_packaging.py":
            continue  # this file necessarily mentions the string it looks for
        if path.suffix in (".png", ".ico", ".gz", ".zip", ".exe"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Two files legitimately mention MIT: the third-party inventory
        # (Kivy, pytest and Ruff really are MIT) and the changelog entry
        # recording the migration away from it. Everywhere else, naming MIT
        # means something still claims the wrong licence.
        if path.name in ("THIRD_PARTY_NOTICES.md", "CHANGELOG.md"):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bMIT\b", line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
    assert not offenders, "stale MIT references:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# Release notes
# ---------------------------------------------------------------------------
def _release_notes():
    import importlib.util

    spec = importlib.util.spec_from_file_location("release_notes", REPO_ROOT / "scripts" / "release_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_tree(tmp_path, version="2.0.0", android_version="2.0.0", changelog="## 2.0.0 - 2026-01-02\n\n### Fixed\n\n- A fix.\n\n## 1.0.0\n\n- Old.\n"):
    (tmp_path / "src" / "cinqic_calculator").mkdir(parents=True)
    (tmp_path / "src" / "cinqic_calculator" / "constants.py").write_text(f'APP_VERSION = "{version}"\n', encoding="utf-8")
    (tmp_path / "android").mkdir()
    (tmp_path / "android" / "android_constants.py").write_text(f'ANDROID_APP_VERSION = "{android_version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(("platform", "tag"), [("desktop", "v2.0.0"), ("android", "android-v2.0.0")])
def test_release_notes_come_from_the_tagged_changelog_section(tmp_path, platform, tag):
    notes = _release_notes().build_notes(platform, tag, "Owner/Repo", _fake_tree(tmp_path))
    assert f"Cinqic Calculator{' for Android' if platform == 'android' else ''} {tag}" in notes
    assert "#### Fixed\n\n- A fix." in notes
    assert "Old." not in notes, "only the tagged version's section"
    assert "https://github.com/Owner/Repo/blob/main/PRIVACY.md" in notes


@pytest.mark.parametrize(
    ("platform", "tag", "tree", "message"),
    [
        ("desktop", "v2.0.1", {}, "source tree is version 2.0.0"),
        ("desktop", "android-v2.0.0", {}, "not a desktop release tag"),
        ("android", "v2.0.0", {}, "not a android release tag"),
        ("android", "android-v2.0.0", {"android_version": "1.9.0"}, "source tree is version 1.9.0"),
        ("desktop", "v2.0.0", {"changelog": "## Unreleased\n\n- Pending.\n"}, "no '## 2.0.0' section"),
        ("desktop", "v2.0.0", {"changelog": "## 2.0.0\n\n## 1.0.0\n- Old.\n"}, "is empty"),
    ],
)
def test_release_notes_refuse_a_mismatched_tag_or_missing_section(tmp_path, platform, tag, tree, message):
    module = _release_notes()
    with pytest.raises(module.ReleaseNotesError, match=re.escape(message)):
        module.build_notes(platform, tag, "Owner/Repo", _fake_tree(tmp_path, **tree))


@pytest.mark.parametrize(("platform", "prefix"), [("desktop", "v"), ("android", "android-v")])
def test_release_notes_build_for_the_current_version(platform, prefix):
    notes = _release_notes().build_notes(platform, prefix + constants.APP_VERSION, "Cinqic-Research/Cinqic-Calculator")
    assert "thousands separators" in notes
