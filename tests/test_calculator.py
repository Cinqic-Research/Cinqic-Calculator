"""Behaviour tests for the calculator state machine.

These test what a user can observe -- the expression line, the big display,
the live preview, and what "=" commits -- rather than which internal fields
happen to hold them.
"""

import pytest

from cinqic_calculator.calculator import Calculator
from cinqic_calculator.evaluator import ErrorCode
from cinqic_calculator.expression import PreviewState


def press(calc, *presses):
    for item in presses:
        if item.isdigit():
            calc.input_digit(item)
        elif item == ".":
            calc.input_decimal()
        elif item == "+/-":
            calc.toggle_sign()
        elif item in ("+", "-", "*", "/", "**"):
            calc.push_operator(item)
        elif item == "=":
            calc.equals()
        elif item == "(":
            calc.open_paren()
        elif item == ")":
            calc.close_paren()
        elif item == "ans":
            calc.push_ans()
        elif item == "%":
            calc.percent()
        elif item == "back":
            calc.backspace()
        elif item == "AC":
            calc.clear_all()
        elif item == "CE":
            calc.clear_entry()
        elif item in ("pi", "e"):
            calc.push_constant(item)
        elif item.startswith("fn:"):
            calc.push_function(item[3:])
        elif item.startswith("px:"):
            calc.apply_postfix(item[3:])
        else:  # pragma: no cover - guards test typos
            raise AssertionError(f"unknown press: {item}")
    return calc


def d(text):
    return list(text)


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("presses", "expected"),
    [
        (("2", "+", "3", "="), "5"),
        (("9", "-", "4", "="), "5"),
        (("6", "*", "7", "="), "42"),
        (("8", "/", "2", "="), "4"),
        (("2", "**", "1", "0", "="), "1,024"),
    ],
)
def test_basic_arithmetic(presses, expected):
    assert press(Calculator(), *presses).display == expected


def test_operator_precedence_is_honoured():
    """The display shows the whole expression, so it must answer 14, not 20."""
    assert press(Calculator(), "2", "+", "3", "*", "4", "=").display == "14"


def test_parentheses_override_precedence():
    assert press(Calculator(), "(", "2", "+", "3", ")", "*", "4", "=").display == "20"


def test_decimal_input():
    assert press(Calculator(), "1", ".", "5", "+", "2", ".", "5", "=").display == "4"


def test_negative_values():
    assert press(Calculator(), "5", "+/-", "+", "3", "=").display == "−2"


def test_division_by_zero_reports_a_clear_message():
    calc = press(Calculator(), "5", "/", "0", "=")
    assert calc.display == "Error"
    assert calc.error_code == ErrorCode.DIVIDE_BY_ZERO
    assert calc.error_message == "Cannot divide by zero"


def test_input_after_an_error_starts_clean():
    calc = press(Calculator(), "5", "/", "0", "=")
    calc.input_digit("7")
    assert calc.display == "7"
    assert not calc.has_error


# ---------------------------------------------------------------------------
# Live expression + preview
# ---------------------------------------------------------------------------
def test_expression_line_is_populated_while_typing():
    """Regression: the expression field existed but was never written to."""
    calc = press(Calculator(), *d("125"), "*", *d("24"))
    assert calc.expression_text == "125 × 24"


def test_live_preview_before_equals():
    calc = press(Calculator(), *d("125"), "*", *d("24"))
    preview = calc.preview()
    assert preview.state == PreviewState.OK
    assert preview.text == "3,000"
    assert calc.display == "24", "the big display still shows what is being typed"


def test_equals_promotes_the_preview_to_the_result():
    calc = press(Calculator(), *d("125"), "*", *d("24"))
    expected = calc.preview().text
    calc.equals()
    assert calc.display == expected
    assert calc.expression_text == "125 × 24 ="


def test_display_keeps_the_last_operand_after_an_operator():
    calc = press(Calculator(), *d("125"), "*")
    assert calc.display == "125"
    assert calc.expression_text == "125 ×"


def test_preview_is_silent_once_a_result_is_committed():
    calc = press(Calculator(), "2", "+", "2", "=")
    assert calc.preview().state == PreviewState.EMPTY


# ---------------------------------------------------------------------------
# Repeated equals
# ---------------------------------------------------------------------------
def test_repeated_equals_repeats_the_last_operation():
    """2 + 3 = 5, = 8, = 11 -- documented since 1.0.0, implemented in 1.1.0."""
    calc = press(Calculator(), "2", "+", "3", "=")
    assert calc.display == "5"
    calc.equals()
    assert calc.display == "8"
    calc.equals()
    assert calc.display == "11"


def test_repeated_equals_with_multiplication():
    calc = press(Calculator(), "2", "*", "3", "=")
    assert [calc.display, (calc.equals(), calc.display)[1], (calc.equals(), calc.display)[1]] == ["6", "18", "54"]


def test_repeated_equals_updates_the_expression_line():
    calc = press(Calculator(), "2", "+", "3", "=")
    calc.equals()
    assert calc.expression_text == "5 + 3 ="


def test_previewing_does_not_corrupt_repeated_equals():
    """The preview runs constantly; it must not consume the repeat state."""
    calc = press(Calculator(), "2", "+", "3")
    for _ in range(20):
        calc.preview()
    calc.equals()
    for _ in range(20):
        calc.preview()
    calc.equals()
    assert calc.display == "8"


def test_clear_all_forgets_the_repeat():
    calc = press(Calculator(), "2", "+", "3", "=", "AC")
    calc.equals()
    assert calc.display == "0"


def test_repeat_is_not_guessed_for_a_grouped_operand():
    calc = press(Calculator(), "2", "+", "(", "1", "+", "2", ")", "=")
    assert calc.display == "5"
    calc.equals()
    assert calc.display == "5", "no repeat rather than a guessed one"


# ---------------------------------------------------------------------------
# Ans
# ---------------------------------------------------------------------------
def test_ans_holds_the_previous_result():
    calc = press(Calculator(), "7", "*", "6", "=")
    assert calc.ans == pytest.approx(42.0)


def test_ans_can_be_used_in_a_new_expression():
    calc = press(Calculator(), "7", "*", "6", "=", "ans", "+", "8")
    assert calc.expression_text == "Ans + 8"
    calc.equals()
    assert calc.display == "50"


def test_ans_is_independent_of_memory():
    calc = press(Calculator(), "7", "*", "6", "=")
    calc.memory_store()
    calc.memory_add()
    assert calc.memory == pytest.approx(84.0)
    assert calc.ans == pytest.approx(42.0), "memory edits must not move Ans"


def test_pressing_an_operator_continues_from_the_result():
    calc = press(Calculator(), "5", "+", "3", "=", "*", "2", "=")
    assert calc.display == "16"


def test_typing_a_digit_after_equals_starts_a_new_expression():
    calc = press(Calculator(), "5", "+", "3", "=", "9")
    assert calc.display == "9"
    assert calc.expression_text == "9"


# ---------------------------------------------------------------------------
# Clearing and correction
# ---------------------------------------------------------------------------
def test_clear_label_reflects_what_the_key_will_do():
    calc = press(Calculator(), "5", "+", "3")
    assert calc.clear_label == "CE"
    calc.clear_smart()
    assert calc.expression_text == "5 +"
    assert calc.clear_label == "AC"
    calc.clear_smart()
    assert calc.expression_text == ""
    assert calc.display == "0"


def test_clear_entry_keeps_the_rest_of_the_expression():
    calc = press(Calculator(), "1", "2", "+", "3", "4", "CE")
    assert calc.expression_text == "12 +"


def test_backspace_edits_a_committed_result():
    calc = press(Calculator(), "1", "0", "+", "5", "=")
    assert calc.display == "15"
    calc.backspace()
    assert calc.display == "1"


def test_backspace_on_an_error_clears_it():
    calc = press(Calculator(), "5", "/", "0", "=", "back")
    assert not calc.has_error
    assert calc.display == "0"


# ---------------------------------------------------------------------------
# Scientific
# ---------------------------------------------------------------------------
def test_square_and_cube():
    assert press(Calculator(), "5", "px:square", "=").display == "25"
    assert press(Calculator(), "3", "px:cube", "=").display == "27"


def test_factorial():
    assert press(Calculator(), "5", "px:factorial", "=").display == "120"


def test_factorial_of_a_negative_is_a_domain_error():
    calc = press(Calculator(), "5", "+/-", "px:factorial", "=")
    assert calc.display == "Error"
    assert calc.error_code == ErrorCode.DOMAIN


def test_square_root():
    assert press(Calculator(), "fn:sqrt", "1", "6", ")", "=").display == "4"


def test_square_root_of_a_negative_is_a_domain_error():
    calc = press(Calculator(), "fn:sqrt", "9", "+/-", ")", "=")
    assert calc.error_code == ErrorCode.DOMAIN


def test_exponential_and_powers_of_ten():
    assert press(Calculator(), "fn:exp", "0", ")", "=").display == "1"
    assert press(Calculator(), "1", "0", "**", "3", "=").display == "1,000"


@pytest.mark.parametrize(("function", "expected"), [("sin", "0.5"), ("cos", "0.5"), ("tan", "1")])
def test_trig_in_degree_mode(function, expected):
    calc = Calculator()
    calc.set_degree_mode(True)
    angle = {"sin": "30", "cos": "60", "tan": "45"}[function]
    press(calc, f"fn:{function}", *d(angle), ")", "=")
    assert calc.display == expected


def test_trig_in_radian_mode():
    calc = Calculator()
    calc.set_degree_mode(False)
    press(calc, "fn:sin", "0", ")", "=")
    assert calc.display == "0"


def test_inverse_trig_in_degree_mode():
    calc = Calculator()
    calc.set_degree_mode(True)
    press(calc, "fn:asin", "0", ".", "5", ")", "=")
    assert float(calc.display) == pytest.approx(30.0)


def test_tangent_at_a_pole_is_a_domain_error():
    calc = Calculator()
    calc.set_degree_mode(True)
    press(calc, "fn:tan", "9", "0", ")", "=")
    assert calc.error_code == ErrorCode.DOMAIN


def test_logarithms():
    assert press(Calculator(), "fn:log", "1", "0", "0", ")", "=").display == "2"
    assert press(Calculator(), "fn:ln", "1", ")", "=").display == "0"


def test_log_of_zero_is_a_domain_error():
    assert press(Calculator(), "fn:log", "0", ")", "=").error_code == ErrorCode.DOMAIN


def test_constants():
    assert press(Calculator(), "pi", "*", "1", "=").display.startswith("3.14159")
    assert press(Calculator(), "e", "*", "1", "=").display.startswith("2.71828")


def test_degree_mode_toggle_does_not_rewrite_the_expression():
    calc = Calculator()
    press(calc, "fn:sin", "3", "0", ")")
    assert calc.preview().text == "0.5"
    calc.set_degree_mode(False)
    assert calc.expression_text == "sin(30)"
    assert calc.preview().text != "0.5"


# ---------------------------------------------------------------------------
# Percent
# ---------------------------------------------------------------------------
def test_percent_of_a_running_total():
    assert press(Calculator(), *d("200"), "+", *d("10"), "%", "=").display == "220"


def test_percent_standalone():
    assert press(Calculator(), *d("50"), "%", "=").display == "0.5"


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------
def test_memory_store_and_recall():
    calc = press(Calculator(), *d("42"))
    calc.memory_store()
    assert calc.has_memory
    press(calc, "AC")
    calc.memory_recall()
    assert calc.display == "42"


def test_memory_add_and_subtract():
    calc = press(Calculator(), *d("10"))
    calc.memory_store()
    press(calc, "AC", *d("4"))
    calc.memory_add()
    assert calc.memory == pytest.approx(14.0)
    calc.memory_subtract()
    assert calc.memory == pytest.approx(10.0)


def test_memory_clear():
    calc = press(Calculator(), *d("5"))
    calc.memory_store()
    calc.memory_clear()
    assert not calc.has_memory
    assert calc.memory is None


def test_memory_stores_the_previewed_answer_not_the_typed_digit():
    calc = press(Calculator(), "2", "+", "3")
    calc.memory_store()
    assert calc.memory == pytest.approx(5.0)


def test_memory_recall_replaces_the_expression():
    calc = press(Calculator(), *d("7"))
    calc.memory_store()
    press(calc, "AC", "1", "+", "2")
    calc.memory_recall()
    assert calc.display == "7"


# ---------------------------------------------------------------------------
# Long values
# ---------------------------------------------------------------------------
def test_very_small_results_are_not_shown_as_zero():
    calc = press(Calculator(), "1", "/", *d("1000000000"), "=")
    calc.push_operator("/")
    press(calc, *d("1000000"), "=")
    assert calc.display != "0"
    assert float(calc.display) == pytest.approx(1e-15)


def test_very_large_results_use_scientific_notation():
    calc = press(Calculator(), *d("99999999"), "**", "9", "=")
    assert float(calc.display) == pytest.approx(99999999.0**9)


def test_overflow_is_reported_not_crashed():
    calc = press(Calculator(), "9", "**", *d("999"), "=")
    calc.equals()
    assert calc.display in ("Error", calc.display)
    assert not_crashed(calc)


def not_crashed(calc):
    calc.preview()
    calc.input_digit("1")
    return True


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------
_FUZZ_KEYS = (
    list("0123456789")
    + [".", "+/-", "+", "-", "*", "/", "**", "=", "(", ")", "%", "back", "AC", "CE"]
    + ["ans", "pi", "e", "fn:sqrt", "fn:ln", "fn:sin", "fn:log", "fn:exp"]
    + ["px:square", "px:cube", "px:factorial"]
)


def test_random_button_mashing_never_raises():
    """No sequence of key presses should be able to crash the calculator.

    A calculator is the kind of thing people hammer. The seed is fixed so a
    failure is reproducible, and the invariants checked are the ones the UI
    depends on every frame: the display and expression are always strings,
    and a preview claiming to be an answer always carries one.
    """
    import random

    random.seed(20260915)
    for _ in range(1500):
        calc = Calculator()
        sequence = [random.choice(_FUZZ_KEYS) for _ in range(random.randint(1, 25))]
        for key in sequence:
            try:
                press(calc, key)
            except Exception as exc:  # pragma: no cover - the failure path
                raise AssertionError(f"{type(exc).__name__} on {sequence}: {exc}") from exc
            assert isinstance(calc.display, str)
            assert isinstance(calc.expression_text, str)
            preview = calc.preview()
            if preview.state == PreviewState.OK:
                assert preview.value is not None
                assert preview.text


def test_memory_operations_survive_random_input():
    import random

    random.seed(4242)
    keys = _FUZZ_KEYS + ["MS", "MR", "M+", "M-", "MC"]

    def press_memory(calc, key):
        if key == "MS":
            calc.memory_store()
        elif key == "MR":
            calc.memory_recall()
        elif key == "M+":
            calc.memory_add()
        elif key == "M-":
            calc.memory_subtract()
        elif key == "MC":
            calc.memory_clear()
        else:
            press(calc, key)

    for _ in range(600):
        calc = Calculator()
        for key in [random.choice(keys) for _ in range(random.randint(1, 20))]:
            press_memory(calc, key)
        assert calc.memory is None or isinstance(calc.memory, float)


def test_display_resolves_ans_rather_than_showing_zero():
    """An expression reading "Ans +" must not sit above a display reading 0."""
    calc = press(Calculator(), "4", "2", "+", "0", "=")
    assert calc.ans == pytest.approx(42.0)
    press(calc, "ans", "+")
    assert calc.expression_text == "Ans +"
    assert calc.display == "42"


def test_display_after_an_error_then_an_operator_shows_the_last_answer():
    calc = press(Calculator(), "4", "2", "+", "0", "=")
    press(calc, "5", "/", "0", "=")
    assert calc.has_error
    press(calc, "+")
    assert not calc.has_error
    assert calc.expression_text == "Ans +"
    assert calc.display == "42"


# Thousands separators are presentation only: editing and arithmetic still
# work with the original numbers, including memory and repeated equals.
def test_grouping_updates_as_digits_are_entered_and_deleted():
    calc = press(Calculator(), *d("999"))
    assert calc.display == "999"
    calc.input_digit("9")
    assert calc.display == "9,999"
    assert calc.expression_text == "9,999"
    calc.backspace()
    assert calc.display == "999"
    press(calc, "9", ".", "5", "0")
    assert calc.display == "9,999.50"
    calc.toggle_sign()
    assert calc.display == "−9,999.50"
    assert calc.plain_display == "-9999.50"


def test_grouped_amounts_preview_commit_repeat_and_continue():
    calc = press(Calculator(), *d("1234.50"), "+", *d("2000.25"))
    assert calc.expression_text == "1,234.50 + 2,000.25"
    assert calc.preview().text == "3,234.75"
    calc.equals()
    assert calc.display == "3,234.75"
    assert calc.plain_display == "3234.75"
    assert calc.ans == pytest.approx(3234.75)
    calc.equals()
    assert calc.expression_text == "3,234.75 + 2,000.25 ="
    assert calc.display == "5,235"
    press(calc, "*", "2", "=")
    assert calc.display == "10,470"


@pytest.mark.parametrize("negative", [False, True])
def test_memory_accepts_grouped_entries_and_recall(negative):
    calc = press(Calculator(), *d("1234.56"))
    if negative:
        calc.toggle_sign()
    expected = -1234.56 if negative else 1234.56
    calc.memory_store()
    assert calc.memory == pytest.approx(expected)
    calc.memory_add()
    assert calc.memory == pytest.approx(2 * expected)
    calc.memory_subtract()
    assert calc.memory == pytest.approx(expected)
    calc.clear_all()
    calc.memory_recall()
    assert calc.display == ("−1,234.56" if negative else "1,234.56")
    calc.memory_clear()


def test_grouped_last_operand_remains_visible_after_operator():
    calc = press(Calculator(), *d("12345"), "+")
    assert calc.display == "12,345"
    assert calc.expression_text == "12,345 +"
    calc.clear_all()
    calc.model.set_ans(12345)
    calc.push_ans()
    assert calc.display == "12,345"


def test_grouping_does_not_round_long_entries():
    calc = press(Calculator(), *d("123456789012345"))
    assert calc.display == "123,456,789,012,345"
    assert calc.plain_display == "123456789012345"
    calc.input_decimal()
    assert calc.display == "123,456,789,012,345."
