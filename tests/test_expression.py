"""Tests for the expression model and the live answer preview.

The most important tests here are the purity ones: the preview runs on every
keystroke, so if it could mutate anything, every calculation the user makes
would be silently corrupted by the act of looking at it.
"""

import copy

import pytest

from cinqic_calculator.evaluator import ErrorCode
from cinqic_calculator.expression import (
    ExpressionModel,
    PreviewState,
    format_number,
    group_digits,
    tidy_literal,
)


def build(*presses, ans=0.0):
    """Drive a model with a compact script of button presses."""
    model = ExpressionModel(ans=ans)
    for press in presses:
        if press.isdigit():
            model.input_digit(press)
        elif press == ".":
            model.input_decimal()
        elif press == "+/-":
            model.toggle_sign()
        elif press in ("+", "-", "*", "/", "**"):
            model.push_operator(press)
        elif press == "(":
            model.open_paren()
        elif press == ")":
            model.close_paren()
        elif press == "ans":
            model.push_ans()
        elif press in ("pi", "e"):
            model.push_constant(press)
        elif press.startswith("fn:"):
            model.push_function(press[3:])
        elif press.startswith("px:"):
            model.apply_postfix(press[3:])
        elif press == "back":
            model.backspace()
        else:  # pragma: no cover - guards test typos
            raise AssertionError(f"unknown press: {press}")
    return model


def digits(text):
    return list(text)


# ---------------------------------------------------------------------------
# Preview purity - the load-bearing guarantee
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "presses",
    [
        ("1", "2", "+", "3"),
        ("5", "/", "0"),
        ("fn:sin", "3", "0", ")"),
        ("(", "2", "+", "3"),
        ("9", "px:factorial"),
        ("2", "**", "1", "0"),
    ],
)
def test_preview_never_mutates_the_model(presses):
    model = build(*presses)
    before = copy.deepcopy(model)
    for _ in range(10):
        model.preview(degrees=True)
        model.preview(degrees=False)
    assert model.tokens == before.tokens
    assert model.entry == before.entry
    assert model.ans == before.ans


def test_preview_does_not_advance_ans():
    model = build("2", "+", "3", ans=99.0)
    model.preview()
    assert model.ans == 99.0


def test_preview_is_repeatable():
    model = build("1", "2", "*", "1", "2")
    first = model.preview()
    assert [model.preview().text for _ in range(5)] == [first.text] * 5


# ---------------------------------------------------------------------------
# Live preview behaviour
# ---------------------------------------------------------------------------
def test_preview_shows_answer_before_equals():
    model = build(*digits("125"), "*", *digits("24"))
    preview = model.preview()
    assert preview.state == PreviewState.OK
    assert preview.text == "3,000"


def test_preview_respects_operator_precedence():
    assert build("2", "+", "3", "*", "4").preview().text == "14"


def test_preview_respects_parentheses():
    assert build("(", "2", "+", "3", ")", "*", "4").preview().text == "20"


@pytest.mark.parametrize(
    "presses",
    [
        ("1", "2", "+"),
        ("fn:sin",),
        ("2", "*", "("),
        ("1", "."),
    ],
)
def test_unfinished_expression_is_not_an_error(presses):
    """A half-typed expression must stay quiet, not flash "Error"."""
    assert build(*presses).preview().state in (PreviewState.INCOMPLETE, PreviewState.EMPTY)


def test_bare_number_has_nothing_to_preview():
    assert build(*digits("42")).preview().state == PreviewState.EMPTY


def test_preview_auto_closes_open_parentheses():
    assert build("fn:sin", *digits("30")).preview(degrees=True).text == "0.5"


def test_real_errors_do_surface():
    preview = build("5", "/", "0").preview()
    assert preview.state == PreviewState.ERROR
    assert preview.code == ErrorCode.DIVIDE_BY_ZERO
    assert "divide by zero" in preview.text.lower()


def test_domain_error_surfaces():
    preview = build("fn:sqrt", "9", "+/-", ")").preview()
    assert preview.state == PreviewState.ERROR
    assert preview.code == ErrorCode.DOMAIN


# ---------------------------------------------------------------------------
# Building expressions
# ---------------------------------------------------------------------------
def test_render_uses_display_symbols():
    assert build(*digits("12"), "*", *digits("3")).render() == "12 × 3"


def test_implicit_multiplication_keeps_operand_order():
    """Regression: the implicit "x" was inserted before the pending operand."""
    model = build("3", "fn:sqrt", *digits("16"), ")")
    assert model.render() == "3 × √(16)"
    assert model.preview().text == "12"


def test_implicit_multiplication_before_constant():
    model = build("2", "pi")
    assert model.render() == "2 × π"


def test_operator_replaces_a_mistyped_operator():
    model = build("5", "+", "*")
    assert model.render() == "5 ×"


def test_leading_operator_uses_previous_answer():
    model = build("*", "2", ans=21.0)
    assert model.render() == "Ans × 2"
    assert model.preview().text == "42"


def test_postfix_square_renders_without_redundant_parentheses():
    assert build("5", "px:square").render() == "5²"


def test_postfix_square_parenthesises_a_negative_operand():
    """-5 ** 2 is -25 in Python; the parentheses are load-bearing here."""
    model = build("5", "+/-", "px:square")
    assert model.preview().text == "25"


def test_postfix_square_does_not_double_wrap_a_group():
    assert build("(", "2", "+", "3", ")", "px:square").render() == "(2 + 3)²"


def test_factorial_compiles_to_an_allowlisted_call():
    model = build("5", "px:factorial")
    assert "factorial(5)" in model.compile_source()
    assert model.preview().text == "120"


def test_close_paren_is_ignored_when_nothing_is_open():
    assert build("5", ")").render() == "5"


def test_token_count_is_bounded():
    model = ExpressionModel()
    for _ in range(500):
        model.input_digit("1")
        model.push_operator("+")
    assert len(model.tokens) <= 201


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------
def test_backspace_trims_the_entry_then_the_tokens():
    model = build(*digits("12"), "+", *digits("34"))
    model.backspace()
    assert model.render() == "12 + 3"
    model.backspace()
    assert model.render() == "12 +"
    model.backspace()
    assert model.render() == "12"


def test_entry_digit_limit():
    model = build(*digits("1234567890123456789"))
    assert len(model.entry.replace(".", "")) == 15


def test_toggle_sign_on_entry():
    model = build("5")
    model.toggle_sign()
    assert model.entry == "-5"
    model.toggle_sign()
    assert model.entry == "5"


def test_repeated_decimal_is_ignored():
    model = build("1", ".", ".", "5")
    assert model.entry == "1.5"


def test_degree_mode_changes_trig_without_changing_the_expression():
    model = build("fn:sin", *digits("30"), ")")
    assert model.render() == "sin(30)"
    assert model.preview(degrees=True).text == "0.5"
    assert model.preview(degrees=False).text != "0.5"
    assert model.render() == "sin(30)"


# ---------------------------------------------------------------------------
# Percent
# ---------------------------------------------------------------------------
def test_percent_after_plus_is_percent_of_the_running_total():
    model = build(*digits("200"), "+", *digits("10"))
    model.apply_percent()
    assert model.preview().text == "220"


def test_percent_standalone_divides_by_one_hundred():
    model = build(*digits("50"))
    model.apply_percent()
    assert float(model.tokens[-1]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Number formatting - must never silently change a value
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"),
        (5.0, "5"),
        (-5.0, "-5"),
        (0.1 + 0.2, "0.3"),
        (1e20, "1e20"),
        (1.5e-9, "1.5e-9"),
    ],
)
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_tiny_values_are_never_rendered_as_zero():
    """Regression: the old formatter printed 1e-15 as the string "0"."""
    text = format_number(1e-15)
    assert text != "0"
    assert float(text) == pytest.approx(1e-15)


def test_huge_values_are_never_truncated_into_a_different_number():
    text = format_number(1.2345e30)
    assert float(text) == pytest.approx(1.2345e30)


def test_format_number_rejects_non_finite():
    with pytest.raises(ValueError):
        format_number(float("inf"))


def test_tidy_literal_preserves_exponent_sign():
    assert tidy_literal("1e-15") == "1e-15"
    assert tidy_literal("20.0") == "20"
    assert tidy_literal("-3") == "−3"


def test_percent_leaves_the_operand_alone_when_the_result_overflows():
    """repr(inf) is "inf", which would compile to an identifier the evaluator
    rejects. The operand stays as typed instead."""
    model = ExpressionModel(tokens=["1e308", "+", "99999"])
    model.apply_percent()
    assert model.tokens == ["1e308", "+", "99999"]
    assert model.preview().state == PreviewState.OK


def test_grouped_expressions_compile_to_ungrouped_arithmetic():
    model = build("fn:sqrt", *digits("1000000"), ")", "+", *digits("2000"))
    assert model.render() == "√(1,000,000) + 2,000"
    assert "," not in model.compile_source()
    assert model.preview().value == 3000
    assert model.preview().text == "3,000"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("999", "999"),
        ("1000", "1,000"),
        ("1234567.8900", "1,234,567.8900"),
        ("-1234567.89", "−1,234,567.89"),
        ("1234.", "1,234."),
        ("0.1234567", "0.1234567"),
        ("1000.0", "1,000"),
        ("1.234e-15", "1.234e-15"),
        ("-1.234e20", "−1.234e20"),
        ("1E+1000", "1E+1000"),
        ("Error", "Error"),
    ],
)
def test_grouping_preserves_fractional_digits_and_exponents(text, expected):
    assert tidy_literal(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10.0", "10.0"),
        ("1000.0", "1,000.0"),
        ("-0.0", "−0.0"),
        ("-123", "−123"),
        ("-1234", "−1,234"),
        ("123456", "123,456"),
        ("-", "−"),
        ("0.", "0."),
        ("1.5e-7", "1.5e-7"),
    ],
)
def test_group_digits_never_trims_what_was_typed(text, expected):
    assert group_digits(text) == expected
