import math
import time

import pytest

from cinqic_calculator.evaluator import ErrorCode, EvaluationError, evaluate


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("1 + 2", 3),
        ("10 - 4", 6),
        ("3 * 4", 12),
        ("10 / 4", 2.5),
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("-5 + 2", -3),
        ("2 ** 3", 8),
        ("sqrt(16)", 4),
        ("abs(-7)", 7),
        ("pi", math.pi),
        ("e", math.e),
        ("sin(0)", 0),
        ("cos(0)", 1),
        ("factorial(5)", 120),
    ],
)
def test_valid_expressions(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


def test_division_by_zero_raises():
    with pytest.raises(EvaluationError):
        evaluate("1 / 0")


def test_empty_expression_raises():
    with pytest.raises(EvaluationError):
        evaluate("")
    with pytest.raises(EvaluationError):
        evaluate("   ")


def test_syntax_error_raises():
    with pytest.raises(EvaluationError):
        evaluate("2 +")
    with pytest.raises(EvaluationError):
        evaluate("(1 + 2")


@pytest.mark.parametrize(
    "malicious",
    [
        "__import__('os')",
        "__import__(\"os\").system(\"echo pwned\")",
        "open('file.txt')",
        "object.__subclasses__()",
        "().__class__",
        "[x for x in range(10)]",
        "lambda: 1",
        "1; 2",
        "exec('1')",
        "eval('1')",
        "globals()",
        "getattr(1, '__class__')",
    ],
)
def test_malicious_expressions_rejected(malicious):
    with pytest.raises(EvaluationError):
        evaluate(malicious)


def test_unknown_function_rejected():
    with pytest.raises(EvaluationError):
        evaluate("unknown_func(1)")


def test_unknown_name_rejected():
    with pytest.raises(EvaluationError):
        evaluate("undefined_name")


def test_complex_result_rejected():
    with pytest.raises(EvaluationError):
        evaluate("(-8) ** (1/3)")


# ---------------------------------------------------------------------------
# 1.1.0: typed errors, angle mode, and exponentiation limits
# ---------------------------------------------------------------------------
def test_errors_carry_a_stable_code():
    for expression, code in [
        ("1/0", ErrorCode.DIVIDE_BY_ZERO),
        ("sqrt(-1)", ErrorCode.DOMAIN),
        ("9**99999", ErrorCode.OVERFLOW),
        ("1 +", ErrorCode.INVALID),
    ]:
        with pytest.raises(EvaluationError) as info:
            evaluate(expression)
        assert info.value.code == code, expression


def test_error_messages_are_human_readable():
    """Raw Python exception text must never reach the product UI."""
    for expression in ("1/0", "sqrt(-1)", "log(0)", "9**99999"):
        with pytest.raises(EvaluationError) as info:
            evaluate(expression)
        message = str(info.value)
        assert "Traceback" not in message
        assert "math domain error" not in message
        assert message[0].isupper()


def test_degree_mode_selects_the_trig_table():
    assert evaluate("sin(30)", degrees=True) == pytest.approx(0.5)
    assert evaluate("sin(30)", degrees=False) == pytest.approx(-0.988, abs=1e-3)
    assert evaluate("asin(0.5)", degrees=True) == pytest.approx(30.0)


def test_tangent_at_a_pole_is_rejected_rather_than_returning_a_huge_number():
    with pytest.raises(EvaluationError) as info:
        evaluate("tan(90)", degrees=True)
    assert info.value.code == ErrorCode.DOMAIN


def test_huge_exponent_is_rejected_immediately():
    """Regression: 9**9**9 used to hang the evaluator allocating an integer.

    An unbounded integer power is a denial of service in what is meant to be
    a sandboxed evaluator, so both the exponent and the result magnitude are
    bounded before any work happens.
    """
    started = time.monotonic()
    with pytest.raises(EvaluationError) as info:
        evaluate("9**9**9")
    assert info.value.code == ErrorCode.OVERFLOW
    assert time.monotonic() - started < 1.0, "must fail fast, not grind"


def test_deeply_nested_input_does_not_crash_the_process():
    with pytest.raises(EvaluationError):
        evaluate("(" * 500 + "1" + ")" * 500)


def test_new_functions_are_available():
    assert evaluate("exp(0)") == pytest.approx(1.0)
    assert evaluate("sinh(0)") == pytest.approx(0.0)
    assert evaluate("cosh(0)") == pytest.approx(1.0)
    assert evaluate("atan(0)") == pytest.approx(0.0)


def test_calls_must_take_exactly_one_argument():
    with pytest.raises(EvaluationError):
        evaluate("sqrt(1, 2)")
    with pytest.raises(EvaluationError):
        evaluate("sqrt()")


def test_zero_to_a_negative_power_is_a_division_by_zero():
    with pytest.raises(EvaluationError) as info:
        evaluate("0 ** -1")
    assert info.value.code == ErrorCode.DIVIDE_BY_ZERO


def test_negative_base_with_a_fractional_exponent_is_a_domain_error():
    with pytest.raises(EvaluationError) as info:
        evaluate("(-8) ** 0.5")
    assert info.value.code == ErrorCode.DOMAIN


# ---------------------------------------------------------------------------
# 1.1.1: sums and differences of decimal amounts come out exact
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("expression", "shown"),
    [
        # Closing a cash drawer: counted minus expected, a cent apart. These
        # displayed as 0.00999999999999 and 0.0100000000001 before 1.1.1.
        ("1500.37 - 1500.36", "0.01"),
        ("1234.56 - 1234.55", "0.01"),
        ("981.07 - 981.06", "0.01"),
        ("1234567.89 - 1234567.88", "0.01"),
        ("8085.1 - 8084.23", "0.87"),
        ("-1500.37 + 1500.36", "-0.01"),
        ("200.10 - 200", "0.1"),
        ("0.1 + 0.2", "0.3"),
    ],
)
def test_near_cancellation_shows_the_exact_decimal_difference(expression, shown):
    from cinqic_calculator.expression import format_number

    assert format_number(evaluate(expression)) == shown


def test_cent_amount_sums_and_differences_match_decimal_arithmetic():
    """Randomised cross-check against exact Decimal arithmetic.

    Pairs are drawn both independently and a few cents apart (the over/short
    case), up to 99,999,999.99 -- every result must display exactly.
    """
    import random
    from decimal import Decimal

    from cinqic_calculator.expression import format_number

    rng = random.Random(20261016)
    for _ in range(20000):
        a = rng.randint(0, 9_999_999_999)
        b = a + rng.randint(-500, 500) if rng.random() < 0.5 else rng.randint(0, 9_999_999_999)
        b = abs(b)
        left, right = Decimal(a) / 100, Decimal(b) / 100
        for op, exact in (("+", left + right), ("-", left - right)):
            source = f"{left} {op} {right}"
            assert Decimal(format_number(evaluate(source))) == exact, source


def test_sum_rounding_leaves_integers_overflow_and_tiny_values_alone():
    assert evaluate("123456789012345 - 1") == 123456789012344
    assert evaluate("1e-320 + 1e-320") == 2e-320
    assert evaluate("123456.789 + 0.000000001") == 123456.789000001
    with pytest.raises(EvaluationError) as info:
        evaluate("1e308 * 10 - 1")
    assert info.value.code == ErrorCode.OVERFLOW
