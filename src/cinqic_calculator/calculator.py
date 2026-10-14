"""Core calculator state machine: expression entry, live preview, scientific
functions, Ans, and memory. UI-independent and fully unit-testable.

Since 1.1.0 this is built on :class:`cinqic_calculator.expression.ExpressionModel`
rather than a two-register accumulator. The reason is the live expression
display: once the screen shows "2 + 3 x 4" in full, answering 20 (what
left-to-right immediate execution gives) would be visibly wrong. Showing the
whole expression and honouring operator precedence are the same decision, so
this evaluates with precedence and returns 14. See CHANGELOG.md.

Display responsibilities are split deliberately:

``display``
    the big number -- the operand being typed, or the committed result.
``expression_text``
    the full expression line being built.
``preview()``
    the provisional answer, before "=" is pressed. Never mutates state.
"""

from __future__ import annotations

from .evaluator import ErrorCode, EvaluationError, evaluate
from .expression import ExpressionModel, Preview, PreviewState, format_number, tidy_literal

_ERROR = "Error"

#: Short, human error text. Raw Python exception strings never reach the UI.
ERROR_MESSAGES = {
    ErrorCode.DIVIDE_BY_ZERO: "Cannot divide by zero",
    ErrorCode.DOMAIN: "Undefined for this input",
    ErrorCode.OVERFLOW: "Number too large",
    ErrorCode.INVALID: "Invalid expression",
}


class Calculator:
    """Turns button presses into an expression, a preview, and a result."""

    def __init__(self):
        self.model = ExpressionModel()
        self.degree_mode = True
        self.memory = None
        self.error_message: str | None = None
        self.error_code: str | None = None
        self.last_expression = ""
        self._result_text: str | None = None
        self._overwrite_entry = False
        # The trailing "op operand" of the last committed calculation, so a
        # second "=" can repeat it (2 + 3 = 5, = 8, = 11).
        self._repeat: tuple[str, str] | None = None

    # ------------------------------------------------------------------
    # Display surface
    # ------------------------------------------------------------------
    @property
    def display(self) -> str:
        if self.error_message is not None:
            return _ERROR
        if self._result_text is not None:
            return _display_number(self._result_text)
        if self.model.entry is not None:
            return _display_number(self.model.entry)
        # No operand is being typed (the user just pressed an operator, say).
        # Keep showing the most recent number rather than blanking to 0, so
        # "125 x" still reads 125 on the big display. "Ans" resolves to its
        # value here, otherwise an expression reading "Ans +" would sit above
        # a display reading 0 while Ans held something else entirely.
        for token in reversed(self.model.tokens):
            if token == "ans":
                return _display_number(format_number(self.model.ans))
            if _safe_float(token) is not None:
                return _display_number(token)
        preview = self.preview()
        if preview.is_answer:
            return preview.text
        return "0"

    @property
    def expression_text(self) -> str:
        if self.error_message is not None:
            return self.last_expression
        if self._result_text is not None:
            return self.last_expression
        return self.model.render()

    @property
    def plain_display(self) -> str:
        """The display as a machine-readable string (ASCII "-", no commas).

        :attr:`display` is for the screen; this is what gets copied to the
        clipboard or written to history, where display punctuation would
        produce a value that cannot be parsed back in.
        """
        text = self.display.replace(",", "")
        return "-" + text[1:] if text.startswith("\u2212") else text

    @property
    def ans(self) -> float:
        return self.model.ans

    @property
    def has_error(self) -> bool:
        return self.error_message is not None

    @property
    def has_memory(self) -> bool:
        return self.memory is not None

    def preview(self) -> Preview:
        """The live answer for the current expression. Pure: mutates nothing."""
        if self.error_message is not None or self._result_text is not None:
            return Preview(PreviewState.EMPTY)
        return self.model.preview(degrees=self.degree_mode)

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------
    def _prepare_input(self) -> None:
        """Clear a finished result / error before new input lands on it."""
        if self.error_message is not None:
            self.clear_all()
            return
        if self._overwrite_entry:
            self.model.clear()
            self._result_text = None
            self.last_expression = ""
            self._overwrite_entry = False

    def _continue_from_result(self) -> None:
        """Keep a committed result as the left operand of a new expression."""
        if self.error_message is not None:
            self.clear_all()
            return
        if self._result_text is not None:
            self.model.clear()
            self.model.entry = self._result_text
            self._result_text = None
            self.last_expression = ""
        self._overwrite_entry = False

    def input_digit(self, digit: str) -> None:
        self._prepare_input()
        self.model.input_digit(digit)

    def input_decimal(self) -> None:
        self._prepare_input()
        self.model.input_decimal()

    def toggle_sign(self) -> None:
        if self.error_message is not None:
            return
        if self._result_text is not None:
            self._continue_from_result()
        self.model.toggle_sign()

    def backspace(self) -> None:
        if self.error_message is not None:
            self.clear_all()
            return
        if self._result_text is not None:
            # Backspacing a finished result edits the result, not the
            # expression that produced it.
            self._continue_from_result()
        self.model.backspace()

    def push_operator(self, source: str) -> None:
        self._continue_from_result()
        self.model.push_operator(source)

    def open_paren(self) -> None:
        self._prepare_input()
        self.model.open_paren()

    def close_paren(self) -> None:
        if self.error_message is not None:
            return
        self._continue_from_result()
        self.model.close_paren()

    def push_function(self, name: str) -> None:
        self._prepare_input()
        self.model.push_function(name)

    def push_constant(self, name: str) -> None:
        self._prepare_input()
        self.model.push_constant(name)

    def push_ans(self) -> None:
        self._prepare_input()
        self.model.push_ans()

    def apply_postfix(self, operation: str) -> None:
        if self.error_message is not None:
            return
        self._continue_from_result()
        self.model.apply_postfix(operation)

    def percent(self) -> None:
        if self.error_message is not None:
            return
        self._continue_from_result()
        self.model.apply_percent(degrees=self.degree_mode)

    # ------------------------------------------------------------------
    # Clearing
    # ------------------------------------------------------------------
    def clear_all(self) -> None:
        self.model.clear()
        self.error_message = None
        self.error_code = None
        self.last_expression = ""
        self._result_text = None
        self._overwrite_entry = False
        self._repeat = None

    def clear_entry(self) -> None:
        """Clear only what is being typed, keeping the rest of the expression."""
        if self.error_message is not None or self._result_text is not None:
            self.clear_all()
            return
        self.model.clear_entry()

    @property
    def clear_label(self) -> str:
        """"CE" while an operand is mid-edit, "AC" when it would clear all.

        Lets a single key show what it is actually about to do instead of
        making the user guess which of two clear buttons they need.
        """
        if self.error_message is not None or self._result_text is not None:
            return "AC"
        return "CE" if self.model.entry is not None else "AC"

    def clear_smart(self) -> None:
        """Clear the entry if one is being typed, otherwise clear everything."""
        if self.clear_label == "CE":
            self.clear_entry()
        else:
            self.clear_all()

    # ------------------------------------------------------------------
    # Committing
    # ------------------------------------------------------------------
    def equals(self) -> None:
        if self.error_message is not None:
            return

        if self._result_text is not None:
            self._repeat_last_operation()
            return

        if self.model.is_empty():
            return

        expression_text = self.model.render()
        source = self.model.compile_source(close_open_parens=True)
        repeat = _trailing_operation(self.model)

        self._commit(source, expression_text, repeat)

    def _repeat_last_operation(self) -> None:
        """Apply the last "op operand" again -- the second and later "=".

        Deliberately rebuilt from the recorded operator and operand rather
        than by re-running the original expression, so "2 + 3 =" repeats as
        "+ 3" on each press instead of recomputing 2 + 3 forever.
        """
        if self._repeat is None or self._result_text is None:
            return
        operator, operand = self._repeat
        left = self._result_text
        source = f"({left}) {operator} ({operand})"
        expression_text = f"{_display_number(left)} {_operator_display(operator)} {_display_number(operand)}"
        self._commit(source, expression_text, self._repeat)

    def _commit(self, source: str, expression_text: str, repeat) -> None:
        try:
            value = evaluate(source, degrees=self.degree_mode)
            text = format_number(value)
        except EvaluationError as exc:
            self._fail(expression_text, exc.code)
            return
        except ValueError:
            self._fail(expression_text, ErrorCode.OVERFLOW)
            return

        self.model.clear()
        self.model.set_ans(value)
        self.last_expression = f"{expression_text} ="
        self._result_text = text
        self._overwrite_entry = True
        self._repeat = repeat

    def _fail(self, expression_text: str, code: str) -> None:
        self.model.clear()
        self.error_code = code
        self.error_message = ERROR_MESSAGES.get(code, ERROR_MESSAGES[ErrorCode.INVALID])
        self.last_expression = expression_text
        self._result_text = None
        self._overwrite_entry = False
        self._repeat = None

    # ------------------------------------------------------------------
    # Modes, memory, reuse
    # ------------------------------------------------------------------
    def set_degree_mode(self, degrees: bool) -> None:
        self.degree_mode = bool(degrees)

    def load_value(self, value: float) -> None:
        """Replace the whole expression with a value (history reuse, MR)."""
        self.clear_all()
        self.model.entry = format_number(value)

    def _current_value(self) -> float | None:
        """The number the display is showing, if it is a number at all."""
        if self.error_message is not None:
            return None
        if self._result_text is not None:
            return _safe_float(self._result_text)
        preview = self.preview()
        if preview.is_answer and preview.value is not None:
            return preview.value
        return _safe_float(self.plain_display)

    def memory_clear(self) -> None:
        self.memory = None

    def memory_recall(self) -> None:
        if self.memory is None:
            return
        self._prepare_input()
        self._continue_from_result()
        self.model.clear()
        self.model.entry = format_number(self.memory)

    def memory_store(self) -> None:
        value = self._current_value()
        if value is not None:
            self.memory = value

    def memory_add(self) -> None:
        value = self._current_value()
        if value is not None:
            self.memory = (self.memory or 0.0) + value

    def memory_subtract(self) -> None:
        value = self._current_value()
        if value is not None:
            self.memory = (self.memory or 0.0) - value


# ----------------------------------------------------------------------
def _safe_float(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _display_number(text: str) -> str:
    return tidy_literal(text)


def _operator_display(source: str) -> str:
    from .expression import BINARY_OPERATORS

    return BINARY_OPERATORS.get(source, source)


def _trailing_operation(model: ExpressionModel) -> tuple[str, str] | None:
    """Extract the final "op operand" pair, for repeated equals.

    Only a trailing *simple* operand qualifies: repeating "x (3 + 4)" would
    mean re-deriving a sub-expression, and guessing wrong there is worse than
    not repeating at all.
    """
    tokens = list(model.tokens)
    if model.entry is not None:
        tokens.append(model.entry)
    if len(tokens) < 3:
        return None
    operand, operator = tokens[-1], tokens[-2]
    from .expression import BINARY_OPERATORS

    if operator not in BINARY_OPERATORS:
        return None
    if _safe_float(operand) is None:
        return None
    return operator, operand
