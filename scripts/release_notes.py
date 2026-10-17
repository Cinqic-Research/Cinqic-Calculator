"""Write a GitHub release body from CHANGELOG.md, refusing a mismatched tag.

Usage: release_notes.py <desktop|android> <tag> <owner/repo> <output.md>

The release workflows used to carry a hard-coded "What's new" list, so every
release after 1.1.0 would have been published with 1.1.0's notes. This takes
the notes from the CHANGELOG section for the tagged version instead, and
fails -- before anything is published -- when the tag does not match the
version in the source tree or the changelog has no section for it.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

TAG_PATTERNS = {
    "desktop": re.compile(r"v(\d+\.\d+\.\d+)"),
    "android": re.compile(r"android-v(\d+\.\d+\.\d+)"),
}

DESKTOP_TEMPLATE = """\
## Cinqic Calculator {tag}

A private, offline calculator for Windows and Linux.

### What's new
{notes}

### Install on Windows
Download `Cinqic-Calculator-Windows-x64-Setup.exe` and run it (no
administrator privileges required). A portable ZIP is also
available if you'd rather not install anything.

### Install on Linux
Download `Cinqic-Calculator-Linux-x86_64.tar.gz`, extract it, and
run `./CinqicCalculator/cinqic-calculator`. The bundle is
self-contained -- no Python or Tk installation required.

### Privacy
Works fully offline. No account, telemetry, or ads. See
[PRIVACY.md](https://github.com/{repo}/blob/main/PRIVACY.md).

### Known limitations
These builds are not code-signed. Windows SmartScreen may show an
unfamiliar-app warning on first run - this is expected for an
unsigned open-source build.

Juniper is not integrated into this release; the calculator works
fully without AI.

### Verify your download
Checksums for every asset are in `SHA256SUMS.txt`.

Source: https://github.com/{repo}
"""

ANDROID_TEMPLATE = """\
## Cinqic Calculator for Android {tag}

A private, offline calculator for Android. Standard and
scientific math, unit conversion, financial tools, and local
history and settings -- no account, no ads, and no internet
permission.

**Package:** `com.cinqic.calculator`

### What's new
{notes}

### Privacy
Works fully offline. No account, telemetry, analytics, or ads.
See [PRIVACY.md](https://github.com/{repo}/blob/main/PRIVACY.md).

### Juniper
Juniper is not integrated into Cinqic Calculator. The calculator
works fully without AI.

### Install
This is a direct APK download, not a Play Store listing.
Download `Cinqic-Calculator-Android.apk`, then allow "install
unknown apps" for your browser or file manager when prompted.

### Verify your download
Checksum: `SHA256SUMS-Android.txt` in this release.
Signing certificate fingerprint: printed in this workflow's
"Verify the release signature" step log.

Source: https://github.com/{repo}
"""


class ReleaseNotesError(ValueError):
    pass


def source_version(platform: str, root: Path = REPO_ROOT) -> str:
    if platform == "android":
        path, name = root / "android" / "android_constants.py", "ANDROID_APP_VERSION"
    else:
        path, name = root / "src" / "cinqic_calculator" / "constants.py", "APP_VERSION"
    match = re.search(rf'^{name} = "([^"]+)"', path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ReleaseNotesError(f"{name} not found in {path}")
    return match.group(1)


def changelog_section(changelog: str, version: str) -> str:
    """The body of the "## <version>" section (a trailing date is allowed)."""
    heading = re.compile(rf"^## {re.escape(version)}(?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$", re.MULTILINE)
    match = heading.search(changelog)
    if not match:
        raise ReleaseNotesError(f"CHANGELOG.md has no '## {version}' section")
    following = re.search(r"^## ", changelog[match.end():], re.MULTILINE)
    body = changelog[match.end(): match.end() + following.start()] if following else changelog[match.end():]
    body = body.strip()
    if not body:
        raise ReleaseNotesError(f"CHANGELOG.md section '## {version}' is empty")
    # The section sits under "### What's new" in the release body, so its own
    # subheadings move down one level.
    return re.sub(r"^###", "####", body, flags=re.MULTILINE)


def build_notes(platform: str, tag: str, repo: str, root: Path = REPO_ROOT) -> str:
    if platform not in TAG_PATTERNS:
        raise ReleaseNotesError(f"unknown platform {platform!r}; expected one of {sorted(TAG_PATTERNS)}")
    match = TAG_PATTERNS[platform].fullmatch(tag)
    if not match:
        raise ReleaseNotesError(f"tag {tag!r} is not a {platform} release tag")
    version = match.group(1)
    expected = source_version(platform, root)
    if version != expected:
        raise ReleaseNotesError(f"tag {tag!r} is version {version}, but the source tree is version {expected}")
    notes = changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    template = ANDROID_TEMPLATE if platform == "android" else DESKTOP_TEMPLATE
    return template.format(tag=tag, repo=repo, notes=notes)


def main(argv) -> int:
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    platform, tag, repo, output = argv
    try:
        notes = build_notes(platform, tag, repo)
    except ReleaseNotesError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    Path(output).write_text(notes, encoding="utf-8")
    print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
