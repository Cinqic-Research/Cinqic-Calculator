"""Standard + scientific calculator view.

Layout, top to bottom: the expression being built, the big display, and the
live answer preview. The preview is what makes this view feel alive -- it is
recomputed on every keypress from :meth:`Calculator.preview`, which is a pure
function and cannot disturb the calculation in progress.
"""

import datetime
import math
import tkinter as tk
from tkinter import font as tkfont

from ..calculator import Calculator, parse_number_text
from ..expression import PreviewState
from .components import ToolTip, make_button, section_label, set_button_active

# 5x5 keypad. "=" sits in the grid with the other keys rather than in a
# detached row of its own, and memory has moved into the scientific panel so
# the everyday keypad stays uncluttered.
KEYPAD_ROWS = [
    ["AC", "(", ")", "%", "⌫"],
    ["7", "8", "9", "÷", "xʸ"],
    ["4", "5", "6", "×", "√"],
    ["1", "2", "3", "−", "Ans"],
    ["±", "0", ".", "+", "="],
]

# Scientific functions, grouped so related operations sit together instead of
# being dumped into one undifferentiated grid.
SCIENTIFIC_GROUPS = [
    ("Trigonometry", [("sin", "fn:sin"), ("cos", "fn:cos"), ("tan", "fn:tan"), ("sin⁻¹", "fn:asin"), ("cos⁻¹", "fn:acos"), ("tan⁻¹", "fn:atan")]),
    ("Powers & roots", [("x²", "px:square"), ("x³", "px:cube"), ("xʸ", "op:**"), ("√x", "fn:sqrt"), ("∛x", "fn:cbrt"), ("x!", "px:factorial")]),
    ("Logs & constants", [("ln", "fn:ln"), ("log", "fn:log"), ("eˣ", "fn:exp"), ("10ˣ", "pow10"), ("π", "const:pi"), ("e", "const:e")]),
    ("Other", [("1/x", "fn:reciprocal"), ("|x|", "fn:abs"), ("sinh", "fn:sinh"), ("cosh", "fn:cosh"), ("tanh", "fn:tanh"), ("Ans", "ans")]),
]

MEMORY_BUTTONS = [("MC", "Memory clear"), ("MR", "Memory recall"), ("M+", "Memory add"), ("M-", "Memory subtract"), ("MS", "Memory store")]

_OPERATOR_KEYS = {"÷": "/", "×": "*", "−": "-", "+": "+", "xʸ": "**"}

# Display font shrinks as the number grows, so a long result stays on screen
# instead of being clipped. (length_threshold, font_size)
_DISPLAY_FONT_STEPS = [(10, 40), (14, 32), (18, 26), (24, 20), (999, 16)]


class CalculatorView(tk.Frame):
    def __init__(self, parent, colors, history, settings, on_status=None):
        super().__init__(parent, bg=colors["background"])
        self.colors = colors
        self.history = history
        self.settings = settings
        self.on_status = on_status or (lambda text: None)
        self.calc = Calculator()
        self.calc.set_degree_mode(bool(settings.get("degree_mode", True)))
        self.scientific_visible = False
        self._operator_buttons = {}
        self._memory_buttons = {}
        self._keypad_buttons = {}

        if self.settings.get("persist_memory", False):
            stored_memory = self.settings.get("memory_value")
            if isinstance(stored_memory, (int, float)) and not isinstance(stored_memory, bool):
                try:
                    value = float(stored_memory)
                except OverflowError:  # a huge integer in a hand-edited settings.json
                    value = math.inf
                if math.isfinite(value):
                    self.calc.memory = value

        self._build()
        self.bind_all_keys()
        self._refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        c = self.colors

        display_frame = tk.Frame(self, bg=c["panel"], highlightthickness=1, highlightbackground=c["border"])
        display_frame.pack(fill="x", padx=16, pady=(12, 8))

        self.expr_var = tk.StringVar(value="")
        self.expr_label = tk.Label(
            display_frame, textvariable=self.expr_var, font=("Segoe UI", 13),
            bg=c["panel"], fg=c["text_secondary"], anchor="e",
        )
        self.expr_label.pack(fill="x", padx=14, pady=(8, 0))

        self.display_var = tk.StringVar(value="0")
        self.display_label = tk.Label(
            display_frame, textvariable=self.display_var, font=("Segoe UI", 40),
            bg=c["panel"], fg=c["text_primary"], anchor="e",
        )
        self.display_label.pack(fill="x", padx=14)

        self.preview_var = tk.StringVar(value="")
        self.preview_label = tk.Label(
            display_frame, textvariable=self.preview_var, font=("Segoe UI", 15),
            bg=c["panel"], fg=c["accent"], anchor="e",
        )
        self.preview_label.pack(fill="x", padx=14, pady=(0, 2))

        meta = tk.Frame(display_frame, bg=c["panel"])
        meta.pack(fill="x", padx=14, pady=(0, 8))
        self.memory_indicator = tk.Label(meta, text="", font=("Segoe UI", 9, "bold"), bg=c["panel"], fg=c["accent"])
        self.memory_indicator.pack(side="left")
        self.angle_indicator = tk.Label(meta, text="DEG", font=("Segoe UI", 9, "bold"), bg=c["panel"], fg=c["text_secondary"])
        self.angle_indicator.pack(side="right")

        actions = tk.Frame(self, bg=c["background"])
        actions.pack(fill="x", padx=16, pady=(0, 6))
        copy_btn = make_button(actions, "Copy", self.copy_result, c, kind="function", width=8, height=1, font_size=10)
        copy_btn.pack(side="left", padx=(0, 6))
        ToolTip(copy_btn, "Copy result (Ctrl+C)", c)
        self.sci_toggle_btn = make_button(actions, "Scientific", self.toggle_scientific, c, kind="function", width=12, height=1, font_size=10)
        self.sci_toggle_btn.pack(side="left", padx=(0, 6))
        ToolTip(self.sci_toggle_btn, "Show scientific functions and memory (Ctrl+E)", c)
        self.angle_btn = make_button(actions, "DEG", self.toggle_degree_mode, c, kind="function", width=6, height=1, font_size=10)
        self.angle_btn.pack(side="left")
        ToolTip(self.angle_btn, "Switch between degrees and radians", c)

        self.scientific_frame = tk.Frame(self, bg=c["background"])
        self._build_scientific_panel()

        self.grid_frame = tk.Frame(self, bg=c["background"])
        self.grid_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._build_keypad()

    def _build_scientific_panel(self):
        """Lay the scientific groups out two-across.

        One group per row would make this panel ~300px tall, which on a
        720-800px window leaves the keypad squeezed into slivers. Pairing the
        groups uses the width that is already there and halves the height, so
        the keypad keeps its full size with the panel open.
        """
        c = self.colors
        for index, (title, entries) in enumerate(SCIENTIFIC_GROUPS):
            block = tk.Frame(self.scientific_frame, bg=c["background"])
            block.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 8) if index % 2 == 0 else (0, 0))
            section_label(block, title, c, size=8).pack(anchor="w", pady=(4, 1))
            row = tk.Frame(block, bg=c["background"])
            row.pack(fill="x")
            for column, (label, action) in enumerate(entries):
                button = make_button(row, label, lambda a=action: self._dispatch(a), c, kind="function", width=3, height=1, font_size=10)
                button.grid(row=0, column=column, padx=1, pady=1, sticky="nsew")
                row.grid_columnconfigure(column, weight=1)

        memory_block = tk.Frame(self.scientific_frame, bg=c["background"])
        memory_block.grid(row=2, column=0, columnspan=2, sticky="nsew")
        section_label(memory_block, "Memory", c, size=8).pack(anchor="w", pady=(4, 1))
        memory_row = tk.Frame(memory_block, bg=c["background"])
        memory_row.pack(fill="x", pady=(0, 4))
        for index, (label, tip) in enumerate(MEMORY_BUTTONS):
            button = make_button(memory_row, label, lambda v=label: self._on_memory(v), c, kind="function", width=5, height=1, font_size=10)
            button.grid(row=0, column=index, padx=1, pady=1, sticky="nsew")
            memory_row.grid_columnconfigure(index, weight=1)
            ToolTip(button, tip, c)
            self._memory_buttons[label] = button

        for column in range(2):
            self.scientific_frame.grid_columnconfigure(column, weight=1)

    def _build_keypad(self):
        c = self.colors
        for row_index, row in enumerate(KEYPAD_ROWS):
            for col_index, value in enumerate(row):
                if value in _OPERATOR_KEYS:
                    kind = "operator"
                elif value == "=":
                    kind = "equals"
                elif value.isdigit() or value in (".", "±"):
                    kind = "number"
                else:
                    kind = "function"
                button = make_button(self.grid_frame, value, lambda v=value: self._on_key(v), c, kind=kind, width=5, height=2, font_size=15)
                button.grid(row=row_index, column=col_index, padx=3, pady=3, sticky="nsew")
                self._keypad_buttons[value] = button
                if value in _OPERATOR_KEYS:
                    self._operator_buttons[_OPERATOR_KEYS[value]] = button
            self.grid_frame.grid_rowconfigure(row_index, weight=1, minsize=44)
        for col in range(5):
            self.grid_frame.grid_columnconfigure(col, weight=1)

        ToolTip(self._keypad_buttons["Ans"], "Insert the previous result", c)
        ToolTip(self._keypad_buttons["⌫"], "Backspace", c)
        ToolTip(self._keypad_buttons["xʸ"], "Raise to a power", c)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_key(self, value: str):
        calc = self.calc
        if value == "AC":
            calc.clear_smart()
        elif value == "⌫":
            calc.backspace()
        elif value == "±":
            calc.toggle_sign()
        elif value == "%":
            calc.percent()
        elif value == ".":
            calc.input_decimal()
        elif value == "(":
            calc.open_paren()
        elif value == ")":
            calc.close_paren()
        elif value == "Ans":
            calc.push_ans()
        elif value == "√":
            calc.push_function("sqrt")
        elif value in _OPERATOR_KEYS:
            calc.push_operator(_OPERATOR_KEYS[value])
        elif value == "=":
            self._commit()
        elif value.isdigit():
            calc.input_digit(value)
        self._refresh()

    def _dispatch(self, action: str):
        """Run one scientific-panel action described by its short code."""
        calc = self.calc
        if action.startswith("fn:"):
            calc.push_function(action[3:])
        elif action.startswith("px:"):
            calc.apply_postfix(action[3:])
        elif action.startswith("op:"):
            calc.push_operator(action[3:])
        elif action.startswith("const:"):
            calc.push_constant(action[6:])
        elif action == "ans":
            calc.push_ans()
        elif action == "pow10":
            calc.input_digit("1")
            calc.input_digit("0")
            calc.push_operator("**")
        self._refresh()

    def _commit(self):
        """Press "=", recording the calculation to history exactly once.

        History is written from what the calculator actually committed, not
        from what was on screen beforehand, so a no-op "=" records nothing
        and a repeated "=" records the operation it really performed.
        """
        before = (self.calc.last_expression, self.calc.display)
        self.calc.equals()
        if self.calc.has_error:
            return
        if (self.calc.last_expression, self.calc.display) == before:
            return
        expression = self.calc.last_expression.rstrip().removesuffix("=").rstrip()
        if expression:
            self._record_history(expression)

    def _on_memory(self, value: str):
        calc = self.calc
        if value == "MC":
            calc.memory_clear()
        elif value == "MR":
            calc.memory_recall()
        elif value == "M+":
            calc.memory_add()
        elif value == "M-":
            calc.memory_subtract()
        elif value == "MS":
            calc.memory_store()
        if value != "MR":
            self._persist_memory_if_enabled()
        self._refresh()

    def toggle_scientific(self):
        self.scientific_visible = not self.scientific_visible
        if self.scientific_visible:
            self.scientific_frame.pack(fill="x", padx=16, before=self.grid_frame)
            self._ensure_room_for_scientific()
        else:
            self.scientific_frame.pack_forget()
        set_button_active(self.sci_toggle_btn, self.scientific_visible, self.colors)
        self.sci_toggle_btn.config(text="Scientific ▴" if self.scientific_visible else "Scientific ▾")
        self.on_status(f"Scientific mode {'on' if self.scientific_visible else 'off'}")

    def _ensure_room_for_scientific(self):
        """Grow the window if the scientific panel would squeeze the keypad.

        Tkinter's packer shrinks the expanding child (the keypad) when the
        total requested height exceeds the window, which is how the panel
        used to flatten the number keys into unusable slivers.
        """
        top = self.winfo_toplevel()
        try:
            top.update_idletasks()
            needed = self.scientific_frame.winfo_reqheight() + self.grid_frame.winfo_reqheight() + self.display_label.master.winfo_reqheight() + 160
            if top.winfo_height() < needed:
                screen_limit = max(600, top.winfo_screenheight() - 80)
                top.geometry(f"{top.winfo_width()}x{min(needed, screen_limit)}")
        except tk.TclError:  # pragma: no cover - window already going away
            pass

    def toggle_degree_mode(self):
        degrees = not self.calc.degree_mode
        self.calc.set_degree_mode(degrees)
        self.settings.set("degree_mode", degrees)
        self.settings.save()
        self.on_status(f"Angle mode: {'degrees' if degrees else 'radians'}")
        self._refresh()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _refresh(self):
        calc = self.calc
        display_text = calc.display
        self.display_var.set(display_text)
        self.display_label.config(font=("Segoe UI", _display_font_size(display_text)))
        self.expr_var.set(self._fit_expression(calc.expression_text))

        preview = calc.preview()
        if preview.state == PreviewState.OK:
            self.preview_var.set(f"= {preview.text}")
            self.preview_label.config(fg=self.colors["accent"])
        elif preview.state == PreviewState.ERROR:
            self.preview_var.set(preview.text)
            self.preview_label.config(fg=self.colors["error"])
        else:
            self.preview_var.set("")

        if calc.has_error:
            self.expr_var.set(calc.error_message or "")
            self.expr_label.config(fg=self.colors["error"])
        else:
            self.expr_label.config(fg=self.colors["text_secondary"])

        self.memory_indicator.config(text="M" if calc.has_memory else "")
        angle = "DEG" if calc.degree_mode else "RAD"
        self.angle_indicator.config(text=angle)
        self.angle_btn.config(text=angle)

        self._keypad_buttons["AC"].config(text=calc.clear_label)
        memory_state = "normal" if calc.has_memory else "disabled"
        for label in ("MC", "MR"):
            if label in self._memory_buttons:
                self._memory_buttons[label].config(state=memory_state)

        pending = _pending_operator(calc)
        for source, button in self._operator_buttons.items():
            set_button_active(button, source == pending, self.colors, kind="operator")

    def _fit_expression(self, text: str) -> str:
        """Trim a long expression from the left, marking that it was trimmed.

        The tail is what matters while typing, so the start is what gets
        dropped -- but silently clipping it would leave no sign that there is
        more expression than is shown, so an ellipsis is prefixed.
        """
        if not text:
            return text
        width = self.expr_label.winfo_width()
        if width <= 1:  # not laid out yet; nothing sensible to measure against
            return text
        measure = self._expr_font_measure()
        if measure is None:
            return text
        available = width - 8
        if measure(text) <= available:
            return text

        # Binary search for the longest tail that fits. Dropping one
        # character at a time would cost a text-measurement per character on
        # every keystroke, which is slow enough to be felt while typing.
        low, high = 0, len(text)
        while low < high:
            middle = (low + high) // 2
            if measure("\u2026" + text[middle:]) <= available:
                high = middle
            else:
                low = middle + 1
        return "\u2026" + text[low:]

    def _expr_font_measure(self):
        """A cached text-measuring function for the expression line's font.

        Building a tkfont.Font is expensive; doing it on every refresh made
        typing visibly slower.
        """
        font_spec = self.expr_label.cget("font")
        cached = getattr(self, "_expr_font_cache", None)
        if cached is None or cached[0] != font_spec:
            try:
                cached = (font_spec, tkfont.Font(font=font_spec))
            except tk.TclError:  # pragma: no cover - font unavailable
                return None
            self._expr_font_cache = cached
        return cached[1].measure

    def _record_history(self, expression: str):
        timestamp = datetime.datetime.now().isoformat(timespec="seconds")
        self.history.add(expression, self.calc.plain_display, timestamp)

    def _persist_memory_if_enabled(self):
        if self.settings.get("persist_memory", False):
            self.settings.set("memory_value", self.calc.memory)
            self.settings.save()

    # ------------------------------------------------------------------
    # Clipboard and history reuse
    # ------------------------------------------------------------------
    def copy_result(self):
        self.clipboard_clear()
        self.clipboard_append(self.calc.plain_display)
        self.on_status("Result copied")

    def paste_expression(self):
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        value = parse_number_text(text)
        if value is None or not self.calc.load_value(value):
            self.on_status("Clipboard does not hold a single number")
            return
        self._refresh()
        self.on_status("Value pasted")

    def use_result_in_history(self, result_text: str):
        try:
            value = float(str(result_text).replace("−", "-"))
        except (TypeError, ValueError):
            return
        if self.calc.load_value(value):
            self._refresh()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------
    def bind_all_keys(self):
        # Bound on the toplevel so shortcuts work without the keypad holding
        # focus -- which means every handler must check that this view is the
        # one actually on screen, or typing into another view's entry field
        # would silently drive the hidden calculator (the v1.0.1 bug).
        top = self.winfo_toplevel()
        simple = {
            "period": ".", "plus": "+", "minus": "−", "asterisk": "×", "slash": "÷",
            "parenleft": "(", "parenright": ")", "percent": "%", "asciicircum": "xʸ",
        }
        for digit in "0123456789":
            top.bind(f"<Key-{digit}>", lambda e, d=digit: self._guarded(d))
        for keysym, value in simple.items():
            top.bind(f"<Key-{keysym}>", lambda e, v=value: self._guarded(v))
        top.bind("<Return>", lambda e: self._guarded("="))
        top.bind("<KP_Enter>", lambda e: self._guarded("="))
        top.bind("<Key-equal>", lambda e: self._guarded("="))
        top.bind("<Escape>", lambda e: self._guarded("AC"))
        top.bind("<BackSpace>", lambda e: self._guarded("⌫"))
        top.bind("<Control-e>", lambda e: self.toggle_scientific() if self._is_active() else None)
        top.bind("<Control-r>", lambda e: self._guarded("Ans"))

    def _guarded(self, value: str):
        if self._is_active():
            self._on_key(value)

    def _is_active(self) -> bool:
        return bool(self.winfo_exists()) and bool(self.winfo_ismapped())


# ----------------------------------------------------------------------
def _display_font_size(text: str) -> int:
    for threshold, size in _DISPLAY_FONT_STEPS:
        if len(text) <= threshold:
            return size
    return _DISPLAY_FONT_STEPS[-1][1]


def _pending_operator(calc) -> str | None:
    """The operator the expression currently ends on, for the active state."""
    from ..expression import BINARY_OPERATORS

    if calc.has_error or calc.model.entry is not None:
        return None
    tokens = calc.model.tokens
    if tokens and tokens[-1] in BINARY_OPERATORS:
        return tokens[-1]
    return None
