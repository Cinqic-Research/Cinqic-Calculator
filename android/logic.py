"""Pure-Python glue between the platform-independent ``cinqic_calculator``
core and the Kivy Android frontend.

Everything in this module is plain Python with no Kivy import at module
load time, on purpose: it is unit-tested directly (see
``tests/test_android_glue.py``) on a plain desktop interpreter that has no
Kivy or Android tooling installed at all. Any real *decision logic* the
Android screens need (memory-button enabled state, the persist-memory
toggle's clear-on-disable semantics, which screen currently owns hardware
key input, recording a calculation to history) belongs here, not inline in
a screen's ``.py``/``.kv`` file, precisely so it can be tested this way.
"""

from __future__ import annotations

import datetime as _datetime
import math

from cinqic_calculator import constants
from cinqic_calculator.calculator import Calculator
from cinqic_calculator.history import History
from cinqic_calculator.settings import Settings

__all__ = [
    "resolve_data_dir",
    "animations_enabled",
    "haptics_enabled",
    "press_animation",
    "entry_animation",
    "parenthesis_label",
    "preview_line",
    "accessibility_label",
    "memory_controls_enabled",
    "restore_persisted_memory",
    "persist_memory_value",
    "set_persist_memory",
    "record_history_entry",
    "load_history_result",
    "ScreenInputRouter",
]


def resolve_data_dir(user_data_dir: str) -> str:
    """Resolve the app's private data directory from Kivy's ``user_data_dir``.

    Thin wrapper around ``constants.data_dir(override_base=...)`` so the app
    and its tests don't need to poke at the shared ``constants`` module
    directly, and so a bad/empty ``user_data_dir`` fails loudly instead of
    silently falling back to the desktop's Windows ``LOCALAPPDATA`` path.
    """
    if not user_data_dir:
        raise ValueError("user_data_dir is required to resolve the Android data directory")
    return constants.data_dir(override_base=user_data_dir)


def memory_controls_enabled(calculator: Calculator) -> bool:
    """Whether the MC/MR controls should be interactive.

    Mirrors the desktop v1.0.1 regression fix: MC/MR must be genuinely
    disabled (not just styled to look inert) whenever memory is empty, and
    must become enabled again as soon as memory holds a value.
    """
    return calculator.has_memory


def restore_persisted_memory(calculator: Calculator, settings: Settings) -> None:
    """Restore ``calculator.memory`` from settings at startup.

    Only restores when ``persist_memory`` is enabled AND the stored value is
    a genuine number. ``bool`` is deliberately excluded even though it is an
    ``int`` subclass in Python, since a stray ``True``/``False`` in
    settings.json should never be treated as a memory value.
    """
    if not settings.get("persist_memory", False):
        return
    stored = settings.get("memory_value")
    if isinstance(stored, (int, float)) and not isinstance(stored, bool):
        # JSON allows Infinity/NaN and huge integers; none is a usable memory.
        try:
            value = float(stored)
        except OverflowError:
            return
        if math.isfinite(value):
            calculator.memory = value


def persist_memory_value(calculator: Calculator, settings: Settings) -> None:
    """Persist the current memory value to settings, if enabled.

    Call this after every memory-mutating operation (MS, MC, M+, M-) so the
    on-disk value never goes stale while persistence is turned on.
    """
    if settings.get("persist_memory", False):
        settings.set("memory_value", calculator.memory)
        settings.save()


def set_persist_memory(settings: Settings, enabled: bool) -> None:
    """Apply the "remember calculator memory between sessions" toggle.

    Regression guard for the pre-1.0.1 desktop bug where this checkbox had
    no real effect: turning persistence OFF must clear the stored memory
    value immediately (not just stop future writes), so a later re-enable
    never resurrects a stale value.
    """
    settings.set("persist_memory", bool(enabled))
    if not enabled:
        settings.set("memory_value", None)
    settings.save()


def record_history_entry(history: History, expression: str, result: str, timestamp: str | None = None) -> None:
    """Add a finished calculation to history with an ISO-8601 timestamp.

    A thin wrapper so screens don't need to import ``datetime`` or know
    ``History.add()``'s exact signature. Respects ``History.enabled``
    (driven by the ``save_history`` setting) automatically, since that
    check already lives inside ``History.add()``.
    """
    if timestamp is None:
        timestamp = _datetime.datetime.now().isoformat(timespec="seconds")
    history.add(expression, result, timestamp)


def load_history_result(calculator, result_text: str) -> bool:
    """Load a stored history result back into the calculator.

    Returns False (leaving the calculator untouched) when the stored result
    is not a number -- a recorded "Error" row, or a file edited by hand.
    History rows are read back off disk, so this must not assume they are
    well-formed.
    """
    try:
        value = float(str(result_text).replace("\u2212", "-"))
    except (TypeError, ValueError):
        return False
    # load_value refuses inf/NaN ("1e999" in an edited file), which would
    # otherwise raise out of the history screen's button handler.
    return calculator.load_value(value)


class ScreenInputRouter:
    """Tracks which screen currently "owns" hardware key / back-button input.

    Why this exists: the desktop v1.0.1 fix discovered that Tkinter
    keyboard shortcuts bound at the *toplevel* (so they work without needing
    focus) fired no matter which view was actually showing, letting
    keystrokes typed into a Financial/Convert entry field silently drive the
    hidden Calculator view's state. The fix was to guard every
    toplevel-bound handler on ``winfo_ismapped()``.

    Kivy's normal text input already avoids this class of bug: each
    screen's ``TextInput``/numeric-entry widgets are separate objects and
    only the focused one receives typed text, so there is no single shared
    "current expression" that other screens can accidentally mutate merely
    by being visible. The one place an equivalent leak *could* still creep
    in is a global ``Window``-level binding (hardware back button, a global
    keyboard-shortcut handler) that unconditionally forwards to the
    Calculator screen's ``Calculator`` instance regardless of which screen
    is actually active. Any such global binding must consult
    :meth:`is_active` before touching Calculator state - this class is that
    guard, kept as plain-Python decision logic so it's directly testable.
    """

    def __init__(self) -> None:
        self._active_screen_name: str | None = None

    def set_active(self, screen_name: str) -> None:
        self._active_screen_name = screen_name

    @property
    def active_screen_name(self) -> str | None:
        return self._active_screen_name

    def is_active(self, screen_name: str) -> bool:
        return self._active_screen_name == screen_name


# ---------------------------------------------------------------------------
# Interaction decisions
#
# The keypad's feel is described here, in plain Python, rather than inline in
# a .kv rule -- same reasoning as the memory/router logic above: it is real
# decision logic, so it belongs where it can be unit-tested without Kivy or
# an Android device present.
# ---------------------------------------------------------------------------

#: Press/release timings for the keypad's spring response, in seconds. The
#: total is kept well under the ~200ms at which a control starts to feel
#: sluggish rather than tactile.
PRESS_SCALE = 0.96
RELEASE_OVERSHOOT = 1.03
PRESS_DURATION = 0.045
RELEASE_DURATION = 0.11

#: The entry animation for a changed display: a short rise and fade-in.
ENTRY_OFFSET_DP = 10
ENTRY_DURATION = 0.13


def animations_enabled(settings) -> bool:
    """Whether motion should be used, honouring the reduced-motion setting.

    Animations are on by default; the setting is an explicit opt-out.
    """
    return not bool(settings.get("reduced_motion", False))


def haptics_enabled(settings) -> bool:
    return bool(settings.get("haptics", True))


def press_animation(reduced_motion: bool):
    """Return (press_scale, overshoot, press_time, release_time), or None.

    With reduced motion the keypad must still acknowledge a press instantly,
    so the caller falls back to a colour-only state change rather than to no
    feedback at all.
    """
    if reduced_motion:
        return None
    return (PRESS_SCALE, RELEASE_OVERSHOOT, PRESS_DURATION, RELEASE_DURATION)


def entry_animation(reduced_motion: bool):
    """Return (offset_dp, duration) for a freshly-changed display, or None."""
    if reduced_motion:
        return None
    return (ENTRY_OFFSET_DP, ENTRY_DURATION)


def parenthesis_label(open_parens: int, ends_operand: bool) -> str:
    """Which bracket a single combined "( )" key should insert next.

    One key instead of two keeps the keypad at four columns. It closes a
    group when one is open and there is something inside it to close, and
    opens a new group otherwise.
    """
    if open_parens > 0 and ends_operand:
        return ")"
    return "("


def preview_line(preview) -> str:
    """The text for the live answer line, or "" when it should stay silent."""
    state = getattr(preview, "state", None)
    if state == "ok":
        return f"= {preview.text}"
    if state == "error":
        return preview.text
    return ""


#: Spoken/described labels for keys whose face is a symbol. Screen readers
#: otherwise announce these as punctuation or skip them entirely.
_ACCESSIBILITY_LABELS = {
    "\u00f7": "divide",
    "\u00d7": "multiply",
    "\u2212": "minus",
    "+": "plus",
    "=": "equals",
    "%": "percent",
    "\u232b": "backspace",
    "\u00b1": "plus or minus",
    ".": "decimal point",
    "(": "open bracket",
    ")": "close bracket",
    "AC": "clear all",
    "CE": "clear entry",
    "Ans": "previous answer",
}


def accessibility_label(value: str) -> str:
    return _ACCESSIBILITY_LABELS.get(value, value)
