"""Shared constants: app identity, paths, and color palette."""

import os
import subprocess
import sys

APP_NAME = "Cinqic Calculator"
APP_VERSION = "1.1.1"
APP_ID = "com.cinqic.calculator"

MAX_HISTORY_ENTRIES = 200


def data_dir(override_base: str | None = None) -> str:
    """Return the per-user application data directory, creating it if needed.

    ``override_base`` lets a platform frontend supply its own private storage
    root (e.g. Android's ``App.user_data_dir``) instead of the per-OS location
    used by the desktop app.

    Windows keeps ``%LOCALAPPDATA%\\Cinqic\\Calculator`` exactly as before, so
    existing installs keep their settings and history. Linux follows the XDG
    Base Directory spec (``$XDG_DATA_HOME``, defaulting to
    ``~/.local/share``) rather than dropping a bare ``Cinqic`` folder into the
    user's home directory.
    """
    if override_base is not None:
        os.makedirs(override_base, exist_ok=True)
        return override_base
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "Cinqic", "Calculator")
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Dark "Juniper-inspired" color palette
# ---------------------------------------------------------------------------
COLOR_BACKGROUND = "#0A0A0A"
COLOR_PANEL = "#161616"
COLOR_PANEL_ALT = "#1E1E1E"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#A0A0A0"
COLOR_ACCENT = "#32CD32"
COLOR_ACCENT_ACTIVE = "#28A428"
COLOR_BORDER = "#2A2A2A"
COLOR_ERROR = "#FF6B6B"

# The light accent is darker than the dark theme's so that accent-coloured
# TEXT (the live answer preview, operator glyphs, the memory indicator) clears
# WCAG AA against the light panels. The previous #219A21 managed only 3.1:1 on
# the keypad. See tests/test_accessibility.py, which enforces this.
LIGHT_COLOR_BACKGROUND = "#F5F5F5"
LIGHT_COLOR_PANEL = "#FFFFFF"
LIGHT_COLOR_PANEL_ALT = "#ECECEC"
LIGHT_COLOR_TEXT_PRIMARY = "#111111"
LIGHT_COLOR_TEXT_SECONDARY = "#5A5A5A"
LIGHT_COLOR_ACCENT = "#177317"
LIGHT_COLOR_ACCENT_ACTIVE = "#0F5410"
LIGHT_COLOR_BORDER = "#D6D6D6"
LIGHT_COLOR_ERROR = "#C62828"


def detect_system_theme() -> str:
    """Best-effort light/dark detection for the host desktop.

    Falls back to 'dark' whenever the platform cannot be asked, which keeps
    startup fast and predictable rather than blocking on a slow lookup.
    """
    if sys.platform == "win32":
        return _detect_windows_theme()
    return _detect_freedesktop_theme()


def _detect_windows_theme() -> str:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value == 1 else "dark"
    except (OSError, ImportError):
        return "dark"


def _detect_freedesktop_theme() -> str:
    """Ask GTK/GNOME settings, tolerating desktops that have no such setting.

    ``gsettings`` is queried with a short timeout: a desktop session that is
    slow or missing must not delay application startup.
    """
    for key in ("color-scheme", "gtk-theme"):
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", key],
                capture_output=True,
                text=True,
                timeout=0.6,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            break
        value = (result.stdout or "").strip().strip("'\"").lower()
        if not value:
            continue
        if "dark" in value:
            return "dark"
        if key == "color-scheme" and value in ("default", "prefer-light"):
            return "light"
        if key == "gtk-theme" and value:
            return "light"
    return "dark"


def resolve_theme(theme_name: str) -> str:
    if theme_name == "system":
        return detect_system_theme()
    if theme_name not in ("dark", "light"):
        return "dark"
    return theme_name


def get_colors(theme_name: str) -> dict:
    """Return a color dict for 'dark' or 'light' (call resolve_theme first)."""
    if theme_name == "light":
        return {
            "background": LIGHT_COLOR_BACKGROUND,
            "panel": LIGHT_COLOR_PANEL,
            "panel_alt": LIGHT_COLOR_PANEL_ALT,
            "text_primary": LIGHT_COLOR_TEXT_PRIMARY,
            "text_secondary": LIGHT_COLOR_TEXT_SECONDARY,
            "accent": LIGHT_COLOR_ACCENT,
            "accent_active": LIGHT_COLOR_ACCENT_ACTIVE,
            "border": LIGHT_COLOR_BORDER,
            "error": LIGHT_COLOR_ERROR,
        }
    return {
        "background": COLOR_BACKGROUND,
        "panel": COLOR_PANEL,
        "panel_alt": COLOR_PANEL_ALT,
        "text_primary": COLOR_TEXT_PRIMARY,
        "text_secondary": COLOR_TEXT_SECONDARY,
        "accent": COLOR_ACCENT,
        "accent_active": COLOR_ACCENT_ACTIVE,
        "border": COLOR_BORDER,
        "error": COLOR_ERROR,
    }


def relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance of an ``#rrggbb`` colour."""
    hex_color = hex_color.lstrip("#")
    channels = []
    for index in (0, 2, 4):
        value = int(hex_color[index : index + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours (1.0 to 21.0)."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_on(background: str) -> str:
    """Pick black or white text for ``background``, whichever reads better.

    Used instead of hardcoding black on the accent: the light and dark
    themes' accents differ enough that one fixed choice fails on one of them,
    and this keeps working if the palette is ever retuned.
    """
    return "#000000" if contrast_ratio("#000000", background) >= contrast_ratio("#FFFFFF", background) else "#FFFFFF"
