"""The expression model behind the live display and the live answer preview.

This module owns the *structure* of the expression the user is building, as a
flat list of source tokens plus an optional in-progress number being typed.
Two things are derived from that structure, and nothing else:

``render()``
    the pretty expression text shown on the expression line ("12 × (3 + 4)").

``preview()``
    the live answer, produced by handing :func:`cinqic_calculator.evaluator`
    a compiled source string.

:meth:`ExpressionModel.preview` is a **pure function of this object's state**.
It allocates a string, calls the sandboxed evaluator (itself pure), and
returns a value. It does not touch the token list, calculator memory, history,
settings, or repeated-equals state. The calculator screens call it on every
keystroke, so that guarantee is load-bearing and is asserted directly by
``tests/test_expression.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .evaluator import ALLOWED_FUNCTION_NAMES, ErrorCode, EvaluationError, evaluate

__all__ = [
    "ExpressionModel",
    "tidy_literal",
    "Preview",
    "PreviewState",
    "format_number",
    "BINARY_OPERATORS",
    "FUNCTIONS",
    "POSTFIX_OPERATIONS",
]

#: Source form -> display form for the binary operators the keypad offers.
BINARY_OPERATORS = {
    "+": "+",
    "-": "−",
    "*": "×",
    "/": "÷",
    "**": "^",
}

#: Scientific functions offered as "name(" prefix tokens.
FUNCTIONS = {
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "asin": "sin⁻¹",
    "acos": "cos⁻¹",
    "atan": "tan⁻¹",
    "ln": "ln",
    "log": "log",
    "sqrt": "√",
    "cbrt": "∛",
    "abs": "abs",
    "reciprocal": "1/",
    "exp": "exp",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
}

#: Postfix operations that wrap the operand immediately to their left.
#: Each maps to a (source suffix, display suffix) pair.
POSTFIX_OPERATIONS = {
    "square": ("**2", "²"),
    "cube": ("**3", "³"),
    "factorial": ("!", "!"),
}

_CONSTANTS = {"pi": "π", "e": "e"}
_ANS = "ans"

# Tokens after which an operand may NOT directly follow -- i.e. seeing a digit
# here means the user wants an implicit multiplication ("2(3+4)", "2π").
_OPERAND_ENDINGS = {")", "pi", "e", _ANS, "!"}

_MAX_ENTRY_DIGITS = 15
_MAX_TOKENS = 200


class PreviewState:
    """Why :meth:`ExpressionModel.preview` returned what it did."""

    #: A finished, valid expression with a real answer.
    OK = "ok"
    #: Nothing typed yet, or only a bare number -- there is nothing to preview.
    EMPTY = "empty"
    #: Still being typed (trailing operator, unclosed function). Not an error:
    #: the UI must stay quiet rather than flashing "Error" mid-keystroke.
    INCOMPLETE = "incomplete"
    #: A genuine error the user should see (divide by zero, domain, overflow).
    ERROR = "error"


@dataclass(frozen=True)
class Preview:
    """The outcome of previewing an expression. Immutable by construction."""

    state: str
    value: float | None = None
    text: str = ""
    code: str | None = None

    @property
    def is_answer(self) -> bool:
        return self.state == PreviewState.OK


def format_number(value: float, max_significant: int = 12) -> str:
    """Render a float for display without ever silently changing its value.

    Very large and very small magnitudes fall back to scientific notation
    rather than being rounded into a lie -- the pre-1.1.0 formatter turned
    1e-15 into the string "0", which displayed a non-zero number as zero.
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError("cannot format a non-finite number")
    if value == 0:
        return "0"

    magnitude = abs(value)
    if magnitude >= 1e12 or magnitude < 1e-6:
        text = f"{value:.{max_significant - 1}e}"
        mantissa, exponent = text.split("e")
        if "." in mantissa:
            mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa}e{int(exponent)}"

    text = f"{value:.{max_significant}g}"
    if "e" in text:  # %g fell back to exponent form; normalise it
        mantissa, exponent = text.split("e")
        if "." in mantissa:
            mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa}e{int(exponent)}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass
class ExpressionModel:
    """A structured, editable arithmetic expression."""

    tokens: list[str] = field(default_factory=list)
    entry: str | None = None
    ans: float = 0.0

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def is_empty(self) -> bool:
        return not self.tokens and self.entry is None

    @property
    def open_parens(self) -> int:
        return sum(1 for token in self.tokens if token.endswith("(")) - self.tokens.count(")")

    def _last(self) -> str | None:
        if self.entry is not None:
            return self.entry
        return self.tokens[-1] if self.tokens else None

    def _ends_operand(self) -> bool:
        """True if the expression currently ends with a complete value."""
        if self.entry is not None:
            return True
        last = self._last()
        if last is None:
            return False
        return last in _OPERAND_ENDINGS or _is_number(last)

    def _at_capacity(self) -> bool:
        return len(self.tokens) >= _MAX_TOKENS

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.tokens = []
        self.entry = None

    def clear_entry(self) -> None:
        """Drop only the operand currently being typed, keeping the rest."""
        self.entry = None

    def input_digit(self, digit: str) -> None:
        if self.entry is None:
            if self._ends_operand():
                # "2(" style juxtaposition: the user typed a value straight
                # after another value, which universally means multiply.
                self._push_token("*")
            self.entry = digit
            return
        if self.entry == "0":
            self.entry = digit
            return
        if self.entry == "-0":
            self.entry = "-" + digit
            return
        if _digit_count(self.entry) >= _MAX_ENTRY_DIGITS:
            return
        self.entry += digit

    def input_decimal(self) -> None:
        if self.entry is None:
            if self._ends_operand():
                self._push_token("*")
            self.entry = "0."
            return
        if "." not in self.entry:
            self.entry += "."

    def toggle_sign(self) -> None:
        """Negate the operand being typed, or the value just produced."""
        if self.entry is not None:
            self.entry = self.entry[1:] if self.entry.startswith("-") else "-" + self.entry
            return
        if self.tokens and _is_number(self.tokens[-1]):
            last = self.tokens[-1]
            self.tokens[-1] = last[1:] if last.startswith("-") else "-" + last

    def push_operator(self, source: str) -> None:
        if source not in BINARY_OPERATORS:
            raise ValueError(f"Unknown operator: {source}")
        self._commit_entry()
        if not self.tokens:
            # A leading "-" is a valid sign; any other leading operator has
            # nothing to operate on, so start from the previous answer.
            if source == "-":
                self.entry = "-0"
                return
            self._push_token(_ANS)
        elif self.tokens[-1] in BINARY_OPERATORS:
            # Replace a mistyped operator instead of stacking two.
            self.tokens[-1] = source
            return
        elif self.tokens[-1].endswith("("):
            if source == "-":
                self.entry = "-0"
                return
            return
        self._push_token(source)

    def open_paren(self) -> None:
        self._begin_operand()
        self._push_token("(")

    def close_paren(self) -> None:
        if self.open_parens <= 0:
            return
        self._commit_entry()
        if not self.tokens or self.tokens[-1].endswith("(") or self.tokens[-1] in BINARY_OPERATORS:
            return  # nothing inside the group yet; closing would be invalid
        self._push_token(")")

    def push_function(self, name: str) -> None:
        if name not in FUNCTIONS:
            raise ValueError(f"Unknown function: {name}")
        if name not in ALLOWED_FUNCTION_NAMES:  # pragma: no cover - guard
            raise ValueError(f"Function {name} is not accepted by the evaluator")
        self._begin_operand()
        self._push_token(f"{name}(")

    def push_constant(self, name: str) -> None:
        if name not in _CONSTANTS:
            raise ValueError(f"Unknown constant: {name}")
        self._begin_operand()
        self._push_token(name)

    def push_ans(self) -> None:
        self._begin_operand()
        self._push_token(_ANS)

    def apply_postfix(self, operation: str) -> None:
        """Wrap the operand to the left in a postfix operation (x², x!)."""
        if operation not in POSTFIX_OPERATIONS:
            raise ValueError(f"Unknown postfix operation: {operation}")
        source_suffix, _ = POSTFIX_OPERATIONS[operation]
        self._commit_entry()
        if not self._ends_operand():
            return
        if source_suffix == "!":
            self._push_token("!")
            return
        start = self._operand_start()
        if self._needs_parens_for_postfix(start):
            self.tokens.insert(start, "(")
            self.tokens.append(")")
        self._push_token(source_suffix)

    def _needs_parens_for_postfix(self, start: int) -> bool:
        """Whether wrapping is required for correctness, not just for looks.

        A single non-negative literal or constant binds tighter than ``**``
        already. A negative literal does not: ``-5 ** 2`` is -25 in Python,
        so that one genuinely needs the parentheses.
        """
        operand = self.tokens[start:]
        if operand and operand[0] == "(" and operand[-1] == ")" and _is_balanced_group(operand):
            return False  # already "(2 + 3)"; wrapping again just adds noise
        if len(operand) != 1:
            return True
        token = operand[0]
        if token in _CONSTANTS or token == _ANS:
            return False
        return not (_is_number(token) and not token.startswith("-"))

    def apply_percent(self, degrees: bool = False) -> None:
        """Turn the operand being typed into a percentage.

        Context-sensitive, matching what desktop calculators have done for
        decades: after "+" or "-" a percentage means *percent of the running
        total* (200 + 10% = 220), while anywhere else it simply means
        "divide by one hundred" (10% = 0.1).
        """
        self._commit_entry()
        if not self.tokens or not _is_number(self.tokens[-1]):
            return
        value = float(self.tokens[-1])
        base = None
        if len(self.tokens) >= 2 and self.tokens[-2] in ("+", "-"):
            prefix = ExpressionModel(tokens=self.tokens[:-2], ans=self.ans)
            try:
                base = evaluate(prefix.compile_source(close_open_parens=True), degrees=degrees)
            except EvaluationError:
                base = None
        result = base * (value / 100.0) if base is not None else value / 100.0
        if not math.isfinite(result):
            # repr(inf) is "inf", which would compile to a bare identifier the
            # evaluator rejects. Leave the operand as the user typed it.
            return
        self.tokens[-1] = repr(result)

    def backspace(self) -> None:
        if self.entry is not None:
            if len(self.entry) > 1 and self.entry != "-0":
                self.entry = self.entry[:-1]
                if self.entry == "-":
                    self.entry = None
            else:
                self.entry = None
            return
        if self.tokens:
            self.tokens.pop()

    def set_ans(self, value: float) -> None:
        self.ans = value

    def replace_with_value(self, value: float) -> None:
        """Collapse the whole expression to a single committed value."""
        self.tokens = []
        self.entry = format_number(value)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _begin_operand(self) -> None:
        """Prepare to append a new operand.

        Commits whatever is being typed FIRST, then inserts the implicit
        multiplication if the expression already ended in a value. Doing it in
        the other order pushes the "*" in front of the operand it is meant to
        follow, turning "3" + sqrt into "* 3 sqrt(" instead of "3 * sqrt(".
        """
        self._commit_entry()
        if self._ends_operand():
            self._push_token("*")

    def _commit_entry(self) -> None:
        if self.entry is not None:
            self._push_token(_normalise_entry(self.entry))
            self.entry = None

    def _push_token(self, token: str) -> None:
        if self._at_capacity():
            return
        self.tokens.append(token)

    def _operand_start(self) -> int:
        """Index of the first token of the operand that ends the expression."""
        index = len(self.tokens) - 1
        if index < 0:
            return 0
        if self.tokens[index] == ")":
            depth = 0
            while index >= 0:
                token = self.tokens[index]
                if token == ")":
                    depth += 1
                elif token.endswith("("):
                    depth -= 1
                    if depth == 0:
                        # Include a function name prefix: sqrt(...) is one operand.
                        return index
                index -= 1
            return 0
        return index

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    def render(self) -> str:
        """The pretty expression text for the expression line."""
        pieces: list[str] = []
        for token in self.tokens:
            pieces.append(_render_token(token))
        if self.entry is not None:
            pieces.append(_render_number_text(self.entry))
        return _join_pieces(pieces).rstrip()

    def compile_source(self, close_open_parens: bool = False) -> str:
        """Compile to a source string the sandboxed evaluator accepts.

        Postfix "!" has no Python equivalent, so it is rewritten here into a
        ``factorial(...)`` call around the operand it applies to -- which is
        why this walks the tokens rather than simply joining them.
        """
        parts: list[str] = []
        for token in self.tokens:
            if token == "!":
                if not parts:
                    continue
                start = _factorial_operand_start(parts)
                operand = "".join(parts[start:])
                del parts[start:]
                parts.append(f"factorial({operand})")
                continue
            compiled = _compile_token(token, self.ans)
            if compiled:
                parts.append(compiled)
        if self.entry is not None:
            parts.append(_normalise_entry(self.entry))
        source = " ".join(parts)
        if close_open_parens:
            source += ")" * max(0, _source_open_parens(source))
        return source

    def is_complete(self) -> bool:
        """Whether the expression is finished enough to have a real answer."""
        if self.is_empty():
            return False
        last = self._last()
        if last is None:
            return False
        if self.entry is not None:
            if self.entry in ("-", "", "-0.") or self.entry.endswith("."):
                return False
        elif last in BINARY_OPERATORS or last.endswith("("):
            return False
        return self.open_parens == 0

    def _has_operation(self) -> bool:
        """Whether anything here actually computes something.

        "12", "(12)" and "((7))" are all just a number wearing brackets; a
        live "= 12" underneath them is noise, not information.
        """
        return any(
            token in BINARY_OPERATORS or token in _POSTFIX_DISPLAY or (token.endswith("(") and len(token) > 1) or token == "!"
            for token in self.tokens
        )

    def preview(self, degrees: bool = False, auto_close: bool = True) -> Preview:
        """Evaluate the current expression **without mutating anything**.

        Returns a :class:`Preview` describing either an answer, a reason the
        expression is not ready yet, or a real error worth showing.
        """
        if self.is_empty():
            return Preview(PreviewState.EMPTY)

        # A bare number is its own answer; previewing "= 12" under "12" is
        # noise, so report EMPTY and let the UI show nothing.
        if not self.tokens and self.entry is not None:
            return Preview(PreviewState.EMPTY)
        if not self._has_operation():
            return Preview(PreviewState.EMPTY)

        trailing_incomplete = not self.is_complete() and self.open_parens == 0
        if trailing_incomplete:
            return Preview(PreviewState.INCOMPLETE)

        source = self.compile_source(close_open_parens=auto_close)
        if not source.strip():
            return Preview(PreviewState.INCOMPLETE)

        try:
            value = evaluate(source, degrees=degrees)
        except EvaluationError as exc:
            if exc.code == ErrorCode.INVALID:
                # An invalid *shape* mid-typing is an unfinished expression,
                # not something to shout about. Real mistakes (divide by
                # zero, domain, overflow) are surfaced.
                return Preview(PreviewState.INCOMPLETE)
            return Preview(PreviewState.ERROR, text=str(exc), code=exc.code)

        try:
            text = tidy_literal(format_number(value))
        except ValueError:
            return Preview(PreviewState.ERROR, text="Number too large", code=ErrorCode.OVERFLOW)
        return Preview(PreviewState.OK, value=value, text=text)


# ----------------------------------------------------------------------
# Token helpers
# ----------------------------------------------------------------------
def _is_balanced_group(operand: list[str]) -> bool:
    """True if ``operand``'s leading "(" is closed by its trailing ")"."""
    depth = 0
    for index, token in enumerate(operand):
        if token.endswith("("):
            depth += 1
        elif token == ")":
            depth -= 1
            if depth == 0:
                return index == len(operand) - 1
    return False


def _is_number(token: str) -> bool:
    try:
        float(token)
    except (TypeError, ValueError):
        return False
    return True


def _digit_count(entry: str) -> int:
    return len(entry.replace("-", "").replace(".", ""))


def _normalise_entry(entry: str) -> str:
    """Turn an in-progress entry ("5.", "-", "") into a valid literal."""
    if entry in ("", "-", "."):
        return "0"
    if entry.endswith("."):
        entry += "0"
    if entry.startswith("."):
        entry = "0" + entry
    if entry.startswith("-."):
        entry = "-0" + entry[1:]
    return entry


def tidy_literal(text: str) -> str:
    """Present a stored numeric literal without changing its value.

    Trims a bare ".0" tail: percent and Ans store ``repr()`` so no precision
    is lost, but "200 + 20.0" reads worse than "200 + 20". Only the LEADING
    sign becomes a typographic minus -- blindly replacing every "-" would
    also mangle an exponent like "1e-15". Group the integer part in threes
    using commas, without converting through float (which could round an
    entry), touching fractional digits, or grouping scientific notation.
    """
    if text.endswith(".0"):
        text = text[:-2]
    if text.startswith("-"):
        text = "\u2212" + text[1:]
    if "e" in text.lower():
        return text
    sign = text[:1] if text.startswith(("\u2212", "+")) else ""
    integer, point, fraction = text[len(sign):].partition(".")
    if integer.isascii() and integer.isdigit():
        groups = [integer[max(0, end - 3):end] for end in range(len(integer), 0, -3)]
        integer = ",".join(reversed(groups))
    return sign + integer + point + fraction


_render_number_text = tidy_literal


_POSTFIX_DISPLAY = {source: display for source, display in POSTFIX_OPERATIONS.values()}


def _render_token(token: str) -> str:
    if token in _POSTFIX_DISPLAY:
        return _POSTFIX_DISPLAY[token]
    if token in BINARY_OPERATORS:
        return BINARY_OPERATORS[token]
    if token in _CONSTANTS:
        return _CONSTANTS[token]
    if token == _ANS:
        return "Ans"
    if token.endswith("(") and len(token) > 1:
        name = token[:-1]
        display = FUNCTIONS.get(name, name)
        return f"{display}("
    if _is_number(token):
        return _render_number_text(token)
    return token


def _compile_token(token: str, ans: float) -> str:
    if token == _ANS:
        return f"({ans!r})"
    if token == "!":
        return ""
    return token


def _source_open_parens(source: str) -> int:
    return source.count("(") - source.count(")")


def _factorial_operand_start(parts: list[str]) -> int:
    """Index in ``parts`` where the operand preceding a "!" begins."""
    index = len(parts) - 1
    if index < 0:
        return 0
    if parts[index].endswith(")"):
        depth = 0
        while index >= 0:
            depth += parts[index].count(")") - parts[index].count("(")
            if depth == 0:
                return index
            index -= 1
        return 0
    return index


def _join_pieces(pieces: list[str]) -> str:
    """Join rendered tokens with spaces only where they aid readability."""
    out = ""
    for piece in pieces:
        if not out:
            out = piece
            continue
        if piece in ("+", "−", "×", "÷", "^"):
            out += f" {piece} "
        elif out.endswith(("+ ", "− ", "× ", "÷ ", "^ ")) or out.endswith("(") or piece in (")", "²", "³", "!"):
            out += piece
        else:
            out += piece
    return out
