"""Interface smoke tests: import every UI module, build the main window once,
and check button/keyboard callbacks don't raise across every view.

Tkinter only reliably supports one Tk() root per process, so all GUI tests
here share a single MainWindow instance (module-scoped fixture) instead of
each creating and destroying its own - repeatedly creating Tk() roots in one
process is a known source of Tcl-level flakiness. The fixture itself skips
the whole module if no display is available (e.g. a headless CI runner
without Xvfb), so it never hangs CI.
"""

import pytest

tk = pytest.importorskip("tkinter")


def test_import_all_ui_modules():
    import cinqic_calculator.ui.about_view  # noqa: F401
    import cinqic_calculator.ui.calculator_view  # noqa: F401
    import cinqic_calculator.ui.components  # noqa: F401
    import cinqic_calculator.ui.converter_view  # noqa: F401
    import cinqic_calculator.ui.financial_view  # noqa: F401
    import cinqic_calculator.ui.history_view  # noqa: F401
    import cinqic_calculator.ui.main_window  # noqa: F401
    import cinqic_calculator.ui.settings_view  # noqa: F401


@pytest.fixture(scope="module")
def app_window(tmp_path_factory):
    from cinqic_calculator.history import History
    from cinqic_calculator.settings import Settings
    from cinqic_calculator.ui.main_window import MainWindow

    base = tmp_path_factory.mktemp("smoke")
    settings = Settings(str(base / "settings.json"))
    history = History(str(base / "history.json"))
    try:
        window = MainWindow(settings, history)
    except tk.TclError:
        pytest.skip("No display available for GUI smoke test")
        return
    window.update()
    yield window
    window.destroy()


def test_main_window_creates_and_switches_every_view(app_window):
    for name in app_window.views:
        app_window.show_view(name)
        app_window.update()
    assert app_window.winfo_exists()


def test_calculator_view_button_and_keyboard_callbacks(app_window):
    app_window.show_view("Calculator")
    calc_view = app_window.views["Calculator"]
    calc_view.calc.clear_all()
    for key in ("5", "+", "3", "="):
        calc_view._on_key(key)
    app_window.update()
    assert calc_view.calc.display == "8"

    calc_view.copy_result()
    calc_view._on_key("\u232b")
    calc_view.toggle_scientific()
    calc_view._dispatch("px:square")
    calc_view._dispatch("fn:sin")
    calc_view._dispatch("const:pi")
    calc_view._dispatch("pow10")
    calc_view.toggle_degree_mode()
    app_window.update()
    assert calc_view.winfo_exists()


def test_expression_and_preview_labels_are_wired_to_real_state(app_window):
    """Regression: the expression label existed but was never populated."""
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("1", "2", "5", "\u00d7", "2", "4"):
        view._on_key(key)
    app_window.update()
    assert view.expr_var.get() == "125 \u00d7 24"
    assert view.display_var.get() == "24"
    assert view.preview_var.get() == "= 3,000"


def test_preview_clears_once_the_result_is_committed(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("8", "\u00d7", "8", "="):
        view._on_key(key)
    app_window.update()
    assert view.display_var.get() == "64"
    assert view.expr_var.get() == "8 \u00d7 8 ="
    assert view.preview_var.get() == ""


def test_unfinished_expression_does_not_show_an_error(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("7", "+"):
        view._on_key(key)
    app_window.update()
    assert view.preview_var.get() == ""
    assert view.display_var.get() == "7"


def test_divide_by_zero_shows_a_readable_message(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("5", "\u00f7", "0", "="):
        view._on_key(key)
    app_window.update()
    assert view.display_var.get() == "Error"
    assert "divide by zero" in view.expr_var.get().lower()
    assert "Traceback" not in view.expr_var.get()


def test_active_operator_is_indicated(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("6", "\u00d7"):
        view._on_key(key)
    app_window.update()
    assert view._operator_buttons["*"]._cinqic_active is True
    assert view._operator_buttons["+"]._cinqic_active is False
    assert str(view._operator_buttons["*"].cget("relief")) == "sunken"


def test_clear_key_relabels_itself(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    app_window.update()
    assert view._keypad_buttons["AC"].cget("text") == "AC"
    for key in ("4", "+", "2"):
        view._on_key(key)
    app_window.update()
    assert view._keypad_buttons["AC"].cget("text") == "CE"


def test_long_results_shrink_the_display_font(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in "123456789":
        view._on_key(key)
    view._on_key("\u00d7")
    for key in "987654321":
        view._on_key(key)
    view._on_key("=")
    app_window.update()
    size = int(str(view.display_label.cget("font")).split()[-1])
    assert size < 40, "a long result must shrink to stay readable"


def test_scientific_panel_does_not_squeeze_the_keypad(app_window):
    """Regression: opening the panel flattened the number keys into slivers."""
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    if not view.scientific_visible:
        view.toggle_scientific()
    app_window.update()
    app_window.update_idletasks()
    assert view.grid_frame.winfo_height() >= 5 * 44
    view.toggle_scientific()
    app_window.update()


def test_history_view_reuse_and_delete(app_window):
    history = app_window.history
    history.clear()
    history.add("2 + 2", "4", "2026-01-01T00:00:00")

    app_window.show_view("History")
    history_view = app_window.views["History"]
    history_view.refresh()
    app_window.update()
    history_view.tree.selection_set("0")
    history_view._copy_selected()
    history_view._reuse_selected()
    app_window.update()
    assert app_window.views["Calculator"].calc.display == "4"


def test_settings_view_toggles(app_window):
    app_window.show_view("Settings")
    settings_view = app_window.views["Settings"]
    settings_view.save_history_var.set(False)
    settings_view._on_save_history_toggle()
    app_window.update()
    assert app_window.history.enabled is False
    settings_view.save_history_var.set(True)
    settings_view._on_save_history_toggle()


def test_keyboard_shortcuts_mapped(app_window):
    bindings = app_window.bind()
    assert "<Control-Key-comma>" in bindings
    assert "<Key-F1>" in bindings
    assert "<Control-Key-l>" in bindings


# ---------------------------------------------------------------------------
# Regression tests: v1.0.1 memory-state and keyboard-leak fixes
# ---------------------------------------------------------------------------
def _find_entries(widget):
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Entry":
            found.append(child)
        found.extend(_find_entries(child))
    return found


def test_memory_indicator_and_buttons_disabled_when_empty(app_window):
    app_window.show_view("Calculator")
    calc_view = app_window.views["Calculator"]
    calc_view.calc.memory_clear()
    calc_view._refresh()
    app_window.update()

    assert calc_view.memory_indicator.cget("text") == ""
    assert str(calc_view._memory_buttons["MC"].cget("state")) == "disabled"
    assert str(calc_view._memory_buttons["MR"].cget("state")) == "disabled"


def test_memory_buttons_enable_after_store_and_disable_after_clear(app_window):
    app_window.show_view("Calculator")
    calc_view = app_window.views["Calculator"]
    calc_view.calc.clear_all()
    calc_view._refresh()

    calc_view._on_key("5")
    calc_view._on_memory("MS")
    app_window.update()
    assert calc_view.memory_indicator.cget("text") == "M"
    assert str(calc_view._memory_buttons["MC"].cget("state")) == "normal"
    assert str(calc_view._memory_buttons["MR"].cget("state")) == "normal"

    calc_view._on_memory("MC")
    app_window.update()
    assert calc_view.memory_indicator.cget("text") == ""
    assert str(calc_view._memory_buttons["MC"].cget("state")) == "disabled"
    assert str(calc_view._memory_buttons["MR"].cget("state")) == "disabled"


def test_keyboard_input_does_not_leak_from_other_views_to_calculator(app_window):
    """Regression: typing into a Financial/Convert entry field must not
    silently drive the (invisible) Calculator view's state, since keyboard
    shortcuts are bound at the toplevel and previously fired regardless of
    which view was actually showing."""
    app_window.show_view("Calculator")
    calc_view = app_window.views["Calculator"]
    calc_view.calc.clear_all()
    calc_view._refresh()

    app_window.show_view("Financial")
    app_window.update()
    entries = _find_entries(app_window.views["Financial"])
    assert entries, "Financial view should have entry fields"
    entry = entries[0]
    entry.focus_set()
    app_window.update()

    app_window.event_generate("<Key-5>")
    app_window.event_generate("<Key-7>")
    app_window.update()

    assert entry.get() == "57"
    assert calc_view.calc.display == "0"

    app_window.show_view("Calculator")


def test_memory_restores_on_init_when_persist_memory_enabled(app_window, tmp_path):
    """Regression: the 'Remember calculator memory between sessions' setting
    previously did nothing - memory was never actually restored on startup.
    Builds a second CalculatorView under the already-open window (instead of
    a second Tk() root, which is flaky to create/destroy repeatedly in one
    process) to exercise the same settings-driven init path a real restart
    would take."""
    from cinqic_calculator.history import History
    from cinqic_calculator.settings import Settings
    from cinqic_calculator.ui.calculator_view import CalculatorView

    settings = Settings(str(tmp_path / "settings.json"))
    settings.set("persist_memory", True)
    settings.set("memory_value", 42.0)
    settings.save()
    history = History(str(tmp_path / "history.json"))

    view = CalculatorView(app_window, app_window.colors, history, settings)
    app_window.update()
    try:
        assert view.calc.memory == 42.0
        assert view.memory_indicator.cget("text") == "M"
        assert str(view._memory_buttons["MC"].cget("state")) == "normal"
    finally:
        view.destroy()


def test_persist_memory_toggle_off_clears_stored_value(app_window):
    """Regression: settings.json didn't have a memory_value key in
    DEFAULT_SETTINGS, so Settings.load() silently dropped it on reload
    regardless of the persist_memory checkbox's state."""
    settings_view = app_window.views["Settings"]
    settings_view.settings.set("memory_value", 99.0)
    settings_view.persist_memory_var.set(False)
    settings_view._on_persist_memory_toggle()
    assert settings_view.settings.get("memory_value") is None


def test_a_long_expression_is_trimmed_and_marked_as_trimmed(app_window):
    """Clipping silently would leave no sign there is more than is shown."""
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for _ in range(40):
        for key in ("1", "2", "3", "+"):
            view._on_key(key)
    view._on_key("9")
    app_window.update()
    app_window.update_idletasks()
    view._refresh()
    app_window.update()

    shown = view.expr_var.get()
    assert shown.startswith("…"), "a trimmed expression must say so"
    assert shown.rstrip().endswith("9"), "the tail being typed must stay visible"
    assert len(shown) < len(view.calc.expression_text)


def test_a_short_expression_is_not_trimmed(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in ("2", "+", "2"):
        view._on_key(key)
    app_window.update()
    view._refresh()
    assert view.expr_var.get() == "2 + 2"


def test_the_window_does_not_grow_to_fit_a_long_expression(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    app_window.update_idletasks()
    width_before = app_window.winfo_width()
    for _ in range(40):
        for key in ("1", "2", "3", "+"):
            view._on_key(key)
    app_window.update()
    app_window.update_idletasks()
    assert app_window.winfo_width() == width_before


def test_typing_a_long_expression_stays_responsive(app_window):
    """Guards the expression-trimming cost.

    Trimming used to measure the text one character at a time, rebuilding
    the font object on every refresh, which made typing visibly slow. The
    threshold is deliberately generous - this is here to catch an
    order-of-magnitude regression, not to benchmark the CI runner.
    """
    import time

    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    app_window.update_idletasks()

    started = time.perf_counter()
    for _ in range(40):
        for key in ("1", "2", "3", "+"):
            view._on_key(key)
    elapsed = time.perf_counter() - started

    assert elapsed < 3.0, f"160 key presses took {elapsed:.2f}s"


def test_grouped_result_copy_history_and_reuse(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    app_window.history.clear()
    for key in ("1", "2", "3", "4", ".", "5", "+", "2", "0", "0", "0", "="):
        view._on_key(key)
    app_window.update()
    assert view.display_var.get() == "3,234.5"
    view.copy_result()
    assert view.clipboard_get() == "3234.5"
    assert app_window.history.entries[0]["result"] == "3234.5"

    # Older, ungrouped history results receive the same display formatting.
    app_window.history.add("5000 - 1", "4999", "2026-01-01T00:00:00")
    history_view = app_window.views["History"]
    history_view.refresh()
    assert history_view.tree.item("1", "values")[1] == "4,999"
    assert history_view.tree.item("0", "values")[1] == "3,234.5"
    history_view.tree.selection_set("0")
    history_view._copy_selected()
    assert history_view.clipboard_get() == "3234.5"
    history_view._reuse_selected()
    assert view.display_var.get() == "3,234.5"


@pytest.mark.parametrize(
    ("clipboard", "display"),
    [("−1,234.56", "−1,234.56"), ("1.23456789012e14", "1.23456789012e14"), ("Total: $981.07", "981.07")],
)
def test_paste_keeps_sign_and_exponent(app_window, clipboard, display):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    view.clipboard_clear()
    view.clipboard_append(clipboard)
    app_window._paste_shortcut()
    app_window.update()
    assert view.display_var.get() == display


def test_ambiguous_paste_leaves_the_calculator_unchanged(app_window):
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    view._on_key("7")
    view.clipboard_clear()
    view.clipboard_append("2026-10-16")
    app_window._paste_shortcut()
    app_window.update()
    assert view.display_var.get() == "7"


def test_long_grouped_history_results_are_not_clipped(app_window):
    from tkinter import font as tkfont

    app_window.history.clear()
    app_window.history.add("big", "-123456789012", "2026-10-16T09:00:00")
    app_window.history.add("tiny", "-1.23456789012e-100", "2026-10-16T09:00:01")
    app_window.show_view("History")
    history_view = app_window.views["History"]
    app_window.update()
    font = tkfont.nametofont("TkDefaultFont")
    for text in ("−123,456,789,012", "−1.23456789012e-100"):
        assert history_view.tree.column("result", "width") >= font.measure(text)
    app_window.history.clear()
    history_view.refresh()


def test_widest_grouped_entry_fits_the_display(app_window):
    """15 digits, a decimal point, separators and a sign at the minimum window size."""
    from tkinter import font as tkfont

    app_window.geometry("640x700")
    app_window.show_view("Calculator")
    view = app_window.views["Calculator"]
    view.calc.clear_all()
    for key in "1234567890123.45":
        view._on_key(key)
    view._on_key("±")
    app_window.update()
    text = view.display_var.get()
    assert text == "−1,234,567,890,123.45"
    font = tkfont.Font(font=view.display_label.cget("font"))
    assert font.measure(text) <= view.display_label.winfo_width()
    view.calc.clear_all()
    app_window.geometry("900x800")
    app_window.update()
