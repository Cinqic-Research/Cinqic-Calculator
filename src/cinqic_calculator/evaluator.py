"""Deterministic, sandboxed arithmetic expression evaluator.

Parses expressions with Python's ``ast`` module and walks only an explicit
allowlist of node types. Anything else (attribute access, calls to
non-whitelisted names, imports, subscripts, comprehensions, etc.) is rejected
before any evaluation happens. There is no ``eval``/``exec`` anywhere in this
module.

Evaluation is pure: it reads only the expression string and the ``degrees``
flag, and mutates nothing. That property is what lets the live answer preview
(see :mod:`cinqic_calculator.expression`) evaluate a half-typed expression on
every keystroke without touching calculator state.
"""

import ast
import math

__all__ = ["EvaluationError", "ErrorCode", "evaluate", "ALLOWED_FUNCTION_NAMES"]


class ErrorCode:
    """Stable, UI-facing classification of why an expression failed.

    Frontends map these to short human messages instead of showing raw
    Python exception text (which is what ``str(exc)`` would leak).
    """

    DIVIDE_BY_ZERO = "divide_by_zero"
    DOMAIN = "domain"
    OVERFLOW = "overflow"
    INVALID = "invalid"


class EvaluationError(ValueError):
    """Raised for invalid, unsafe, or undefined expressions."""

    def __init__(self, message: str, code: str = ErrorCode.INVALID):
        super().__init__(message)
        self.code = code


# Guard rails for ``**``. Python's integer exponentiation is unbounded, so a
# pasted or fuzzed ``9**9**9`` would otherwise spin forever allocating a
# multi-gigabyte integer -- a denial of service in what is supposed to be a
# sandboxed evaluator. Bound both the exponent and the resulting magnitude
# before doing any work.
_MAX_EXPONENT = 1024
_MAX_MAGNITUDE = 1e308


def _raise_div_zero():
    raise EvaluationError("Cannot divide by zero", ErrorCode.DIVIDE_BY_ZERO)


def _safe_div(a, b):
    if b == 0:
        _raise_div_zero()
    return a / b


def _safe_mod(a, b):
    if b == 0:
        _raise_div_zero()
    return math.fmod(a, b)


def _safe_floordiv(a, b):
    if b == 0:
        _raise_div_zero()
    return a // b


def _safe_pow(a, b):
    if abs(b) > _MAX_EXPONENT:
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW)
    if a == 0 and b < 0:
        _raise_div_zero()
    # A negative base with a fractional exponent is a complex root; reject it
    # up front rather than letting Python hand back a complex number.
    if a < 0 and isinstance(b, float) and b != int(b):
        raise EvaluationError("Undefined for this input", ErrorCode.DOMAIN)
    try:
        result = a**b
    except (OverflowError, ValueError) as exc:
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW) from exc
    if isinstance(result, complex):
        raise EvaluationError("Undefined for this input", ErrorCode.DOMAIN)
    if isinstance(result, int) and abs(result) > _MAX_MAGNITUDE:
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW)
    return result


def _checked(name, func, code=ErrorCode.DOMAIN):
    """Wrap a math function so its native exception becomes a typed one."""

    def wrapper(*args):
        try:
            return func(*args)
        except ZeroDivisionError as exc:
            raise EvaluationError("Cannot divide by zero", ErrorCode.DIVIDE_BY_ZERO) from exc
        except OverflowError as exc:
            raise EvaluationError("Number too large", ErrorCode.OVERFLOW) from exc
        except (ValueError, TypeError) as exc:
            raise EvaluationError(f"Undefined for {name}", code) from exc

    return wrapper


def _factorial(x):
    if x < 0 or x != int(x):
        raise ValueError("factorial needs a whole number")
    if x > 170:  # 171! overflows a float
        raise OverflowError("factorial too large")
    return float(math.factorial(int(x)))


def _tan(x):
    # math.tan never raises at the poles (floating point never lands exactly
    # on pi/2), it just returns an enormous number. Reject it explicitly so
    # "tan(90)" is a clear domain error rather than 1.6e16.
    if abs(math.cos(x)) < 1e-12:
        raise ValueError("tangent is undefined here")
    return math.tan(x)


def _asin(x):
    if x < -1 or x > 1:
        raise ValueError("asin domain")
    return math.asin(x)


def _acos(x):
    if x < -1 or x > 1:
        raise ValueError("acos domain")
    return math.acos(x)


# A double guarantees 15 significant decimal digits (DBL_DIG). When two nearly
# equal amounts are subtracted, the binary representation error of the
# operands -- below those 15 digits -- becomes the leading digits of the
# result: 1500.37 - 1500.36 is 0.009999999999990905 in binary floating point,
# which the 12-digit display showed as "0.00999999999999" instead of "0.01".
# Rounding a sum or difference to 15 significant digits *of its larger
# operand* removes that noise: the accumulated error is at most 2 ulp of
# the larger operand, under half a unit in the 15th digit, so a result that
# is exact to 15 digits always rounds back to itself. The cost is any digit
# beyond the 15th (123456789012345 + 0.5 keeps 123456789012346), which the
# 12-digit display never shows.
_SUM_SIGNIFICANT_DIGITS = 15


def _clean_sum(result, a, b):
    if not isinstance(result, float) or result == 0 or not math.isfinite(result):
        return result  # exact integer arithmetic, or an overflow handled later
    scale = max(abs(a), abs(b))
    if not scale or not math.isfinite(scale):
        return result
    return round(result, _SUM_SIGNIFICANT_DIGITS - 1 - math.floor(math.log10(scale)))


_BIN_OPS = {
    ast.Add: lambda a, b: _clean_sum(a + b, a, b),
    ast.Sub: lambda a, b: _clean_sum(a - b, a, b),
    ast.Mult: lambda a, b: a * b,
    ast.Div: _safe_div,
    ast.Mod: _safe_mod,
    ast.Pow: _safe_pow,
    ast.FloorDiv: _safe_floordiv,
}

_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
}

# Angle-independent functions, shared by both the degree and radian tables.
_BASE_FUNCTIONS = {
    "sqrt": _checked("sqrt", math.sqrt),
    "cbrt": _checked("cbrt", lambda x: math.copysign(abs(x) ** (1 / 3), x)),
    "abs": _checked("abs", abs),
    "log": _checked("log", math.log10),
    "ln": _checked("ln", math.log),
    "exp": _checked("exp", math.exp, ErrorCode.OVERFLOW),
    "factorial": _checked("factorial", _factorial),
    "reciprocal": _checked("reciprocal", lambda x: _safe_div(1.0, x)),
    "sinh": _checked("sinh", math.sinh, ErrorCode.OVERFLOW),
    "cosh": _checked("cosh", math.cosh, ErrorCode.OVERFLOW),
    "tanh": _checked("tanh", math.tanh),
}

_TRIG = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": _tan,
}

_INVERSE_TRIG = {
    "asin": _asin,
    "acos": _acos,
    "atan": math.atan,
}


def _build_table(degrees: bool) -> dict:
    """Build the function allowlist for the requested angle mode.

    Degree mode is applied here, at the single point where a trig function is
    looked up, rather than by rewriting the user's expression -- so the
    expression text stays exactly what the user typed and DEG/RAD can be
    toggled without re-parsing anything.
    """
    table = dict(_BASE_FUNCTIONS)
    for name, func in _TRIG.items():
        if degrees:
            table[name] = _checked(name, lambda x, _f=func: _f(math.radians(x)))
        else:
            table[name] = _checked(name, func)
    for name, func in _INVERSE_TRIG.items():
        if degrees:
            table[name] = _checked(name, lambda x, _f=func: math.degrees(_f(x)))
        else:
            table[name] = _checked(name, func)
    return table


_FUNCTIONS_RAD = _build_table(degrees=False)
_FUNCTIONS_DEG = _build_table(degrees=True)

#: Every function name the evaluator will accept. The expression model uses
#: this to assert it never emits a call the sandbox would reject.
ALLOWED_FUNCTION_NAMES = frozenset(_FUNCTIONS_RAD)

_ALLOWED_NAMES = {
    "pi": math.pi,
    "e": math.e,
}


def evaluate(expression: str, degrees: bool = False) -> float:
    """Evaluate a whitelisted arithmetic expression and return a float.

    ``degrees`` selects the angle mode used by the trigonometric functions.
    Raises :class:`EvaluationError` for empty, malformed, unsafe, or
    undefined input. Never mutates anything.
    """
    if not expression or not expression.strip():
        raise EvaluationError("Empty expression", ErrorCode.INVALID)

    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as exc:
        raise EvaluationError("Invalid expression", ErrorCode.INVALID) from exc

    functions = _FUNCTIONS_DEG if degrees else _FUNCTIONS_RAD
    try:
        result = _eval_node(tree.body, functions)
    except EvaluationError:
        raise
    except ZeroDivisionError as exc:
        raise EvaluationError("Cannot divide by zero", ErrorCode.DIVIDE_BY_ZERO) from exc
    except OverflowError as exc:
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW) from exc
    except RecursionError as exc:
        raise EvaluationError("Expression is too deeply nested", ErrorCode.INVALID) from exc
    except (ValueError, ArithmeticError) as exc:
        raise EvaluationError("Invalid expression", ErrorCode.INVALID) from exc

    if isinstance(result, complex):
        raise EvaluationError("Undefined for this input", ErrorCode.DOMAIN)
    if isinstance(result, float) and math.isnan(result):
        raise EvaluationError("Undefined for this input", ErrorCode.DOMAIN)
    if isinstance(result, float) and math.isinf(result):
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW)
    if isinstance(result, int) and abs(result) > _MAX_MAGNITUDE:
        raise EvaluationError("Number too large", ErrorCode.OVERFLOW)
    return float(result)


def _eval_node(node, functions):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise EvaluationError("Only numeric literals are allowed", ErrorCode.INVALID)
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise EvaluationError("Operator not allowed", ErrorCode.INVALID)
        left = _eval_node(node.left, functions)
        right = _eval_node(node.right, functions)
        return _BIN_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise EvaluationError("Operator not allowed", ErrorCode.INVALID)
        return _UNARY_OPS[op_type](_eval_node(node.operand, functions))

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[node.id]
        raise EvaluationError(f"Unknown identifier: {node.id}", ErrorCode.INVALID)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise EvaluationError("Unsupported call target", ErrorCode.INVALID)
        name = node.func.id
        if name not in functions or node.keywords:
            raise EvaluationError(f"Function not allowed: {name}", ErrorCode.INVALID)
        if len(node.args) != 1:
            raise EvaluationError(f"{name} takes exactly one argument", ErrorCode.INVALID)
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise EvaluationError("Unsupported call form", ErrorCode.INVALID)
        args = [_eval_node(arg, functions) for arg in node.args]
        return functions[name](*args)

    raise EvaluationError(f"Disallowed syntax: {type(node).__name__}", ErrorCode.INVALID)
