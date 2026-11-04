import cmath
import logging
import math
import re

import numpy as np
import sympy as sp

from scipy import special as scipy_special
from sympy import (
    Integral,
    Poly,
    diff,
    integrate,
    lambdify,
    solve as sympy_solve,
    symbols,
    sympify,
)
from scipy.optimize import root_scalar
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)



logger = logging.getLogger(__name__)


SUPPORTED_METHODS = {
    "bisection",
    "newton",
    "secant",
    "fzero",
    "itp",
    "muller",
    "solve",
    "roots",
    "integer_exhaustive_scan",
}


def normalize_method(method: str):
    if method is None:
        return None

    method = str(method).lower().strip()

    method_map = {
        "bisection": "bisection",
        "bisection method": "bisection",
        "binary search": "bisection",

        "newton": "newton",
        "newton method": "newton",
        "newton-raphson": "newton",
        "newton raphson": "newton",
        "newton-raphson method": "newton",
        "newton raphson method": "newton",

        "secant": "secant",
        "secant method": "secant",

        "fzero": "fzero",
        "fzero method": "fzero",

        # Legacy aliases kept only so older API clients do not break.
        # The canonical rAIson method name exposed by the project is fzero.
        "brentq": "fzero",
        "brentq method": "fzero",
        "brent": "fzero",
        "brent method": "fzero",
        "brent-dekker": "fzero",
        "brent dekker": "fzero",
        "brent-dekker method": "fzero",
        "brent dekker method": "fzero",
        "brent/dekker": "fzero",
        "brent-dekker/fzero": "fzero",
        "brent dekker/fzero": "fzero",

        "itp": "itp",
        "itp method": "itp",
        "interpolate truncate project": "itp",
        "interpolate-truncate-project": "itp",

        "muller": "muller",
        "muller method": "muller",
        "müller": "muller",
        "müller method": "muller",

        "solve": "solve",
        "symbolic solve": "solve",
        "analytical solve": "solve",
        "analytical solution": "solve",

        "roots": "roots",
        "polynomial roots": "roots",
        "poly roots": "roots",

        "integer exhaustive scan": "integer_exhaustive_scan",
        "integer_exhaustive_scan": "integer_exhaustive_scan",
        "integer exhaustive search": "integer_exhaustive_scan",
        "exhaustive integer scan": "integer_exhaustive_scan",
    }

    return method_map.get(method, method)


PARSER_TRANSFORMATIONS = (
    standard_transformations
    + (implicit_multiplication_application,)
)


def normalize_equation_text(equation_str):
    """
    Normalize common mathematical, Unicode and MATLAB-like notation into
    syntax understood by the shared SymPy parser.

    This normalization belongs to the core solver, so it is used by the web
    interface, manual methods, Automatic/rAIson mode and every API client.
    """
    if equation_str is None or not str(equation_str).strip():
        raise ValueError("Equation is required")

    text = str(equation_str).strip()

    # MATLAB element-wise operators have the same scalar meaning here.
    text = text.replace(".^", "^")
    text = text.replace(".*", "*")
    text = text.replace("./", "/")

    # Common Unicode mathematical symbols copied from documents/web pages.
    unicode_replacements = {
        "−": "-",
        "–": "-",
        "—": "-",
        "×": "*",
        "·": "*",
        "÷": "/",
        "π": "pi",
        "∞": "oo",
        "²": "**2",
        "³": "**3",
    }

    for source, target in unicode_replacements.items():
        text = text.replace(source, target)

    # Accept equation-style equality copied from MATLAB/Python-like material.
    # Inequality syntax is outside the scope of this scalar equation solver.
    if "!=" in text:
        raise ValueError(
            "Inequalities are not supported; enter an equation"
        )

    text = text.replace("==", "=")

    # SymPy uses ** for powers. Existing ** syntax is preserved.
    text = text.replace("^", "**")

    # Friendly aliases.
    text = re.sub(
        r"\binfinity\b",
        "oo",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\binf\b",
        "oo",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bln\s*\(",
        "log(",
        text,
        flags=re.IGNORECASE,
    )

    # Square-root symbol: both √x and √(expression).
    text = re.sub(
        r"√\s*\(",
        "sqrt(",
        text,
    )

    text = re.sub(
        r"√\s*([A-Za-z_]\w*|(?:\d+(?:\.\d*)?|\.\d+))",
        r"sqrt(\1)",
        text,
    )

    # Simple absolute-value notation such as |x| or |x-2|.
    absolute_value_pattern = re.compile(
        r"\|([^|]+)\|"
    )

    previous_text = None

    while previous_text != text:
        previous_text = text

        text = absolute_value_pattern.sub(
            r"Abs(\1)",
            text,
        )

    # A trailing semicolon is common in MATLAB input.
    text = text.rstrip().rstrip(";").strip()

    return text


def build_parser_locals(x):
    """
    Return the mathematical names accepted by the general equation input.
    """
    return {
        "x": x,

        # Constants
        "pi": sp.pi,
        "e": sp.E,
        "E": sp.E,
        "i": sp.I,
        "j": sp.I,
        "I": sp.I,
        "oo": sp.oo,

        # Elementary functions
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "asin": sp.asin,
        "acos": sp.acos,
        "atan": sp.atan,

        "sinh": sp.sinh,
        "cosh": sp.cosh,
        "tanh": sp.tanh,

        "exp": sp.exp,

        "log": sp.log,

        "log10": lambda value: sp.log(
            value,
            10,
        ),

        "sqrt": sp.sqrt,

        "abs": sp.Abs,
        "Abs": sp.Abs,

        # Calculus
        "Integral": sp.Integral,
        "integrate": sp.integrate,
        "Derivative": sp.Derivative,
        "diff": sp.diff,

        # Other mathematical functions
        "factorial": sp.factorial,

        "gamma": sp.gamma,
        "Gamma": sp.gamma,

        "lowergamma": sp.lowergamma,
        "uppergamma": sp.uppergamma,

        "erf": sp.erf,

        # Integer-valued mathematical functions
        "floor": sp.floor,
        "ceil": sp.ceiling,
        "ceiling": sp.ceiling,

        # Finite symbolic sums and products
        "Sum": sp.Sum,
        "sum": sp.Sum,
        "Product": sp.Product,
        "product": sp.Product,

        # Regularized lower incomplete gamma.
        # Equivalent to scipy.special.gammainc(a, z).
        "gammainc": (
            lambda a, z:
            sp.lowergamma(a, z)
            / sp.gamma(a)
        ),

        "min": sp.Min,
        "max": sp.Max,
        "Min": sp.Min,
        "Max": sp.Max,
    }


def parse_math_expression(
    expression_text,
    x,
):
    """
    Parse one mathematical expression using the shared input vocabulary.
    """

    safe_global_dict = {
        "Symbol": sp.Symbol,
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "__builtins__": {},
    }

    if "__" in expression_text:
        raise ValueError(
            "Unsupported expression syntax"
        )

    return parse_expr(
        expression_text,
        local_dict=build_parser_locals(x),
        global_dict=safe_global_dict,
        transformations=PARSER_TRANSFORMATIONS,
        evaluate=True,
    )


def prepare_expression(equation_str):
    if (
        equation_str is None
        or not str(equation_str).strip()
    ):
        raise ValueError(
            "Equation is required"
        )

    x = symbols("x")

    equation_text = (
        normalize_equation_text(
            equation_str
        )
    )

    # Both f(x) and left = right are supported.
    if "=" in equation_text:
        parts = equation_text.split("=")

        if len(parts) != 2:
            raise ValueError(
                "Use only one '=' symbol in the equation"
            )

        left_text = parts[0].strip()
        right_text = parts[1].strip()

        if (
            not left_text
            or not right_text
        ):
            raise ValueError(
                "Both sides of the equation must contain an expression"
            )

        left_expr = (
            parse_math_expression(
                left_text,
                x,
            )
        )

        right_expr = (
            parse_math_expression(
                right_text,
                x,
            )
        )

        expr = (
            left_expr
            - right_expr
        )

    else:
        expr = parse_math_expression(
            equation_text,
            x,
        )

    # Evaluate symbolic constructs when possible.
    #
    # Examples:
    # Integral(t**2, (t, 0, x)) = 9
    # integrate(exp(-t**2), (t, 0, x)) = 0.5
    # Derivative(sin(x), x) = 0.5
    try:
        expr = expr.doit()

    except Exception:
        # The selected solver is not changed.
        pass

    unsupported_symbols = (
        expr.free_symbols
        - {x}
    )

    if unsupported_symbols:
        symbol_names = ", ".join(
            sorted(
                str(symbol)
                for symbol
                in unsupported_symbols
            )
        )

        raise ValueError(
            "Only the free variable x is supported. "
            f"Unsupported free symbols: {symbol_names}"
        )

    if x not in expr.free_symbols:
        raise ValueError(
            "The equation must contain the variable x"
        )

    return x, expr


_ABESS_REGULARIZED_GAMMA = sp.Function(
    "_abess_regularized_gammainc"
)

_MAX_FAST_PRODUCT_TERMS = 100000


def _numeric_lambdify_modules():
    """
    Numeric modules shared by the fast evaluator.

    The custom function maps the symbolic regularized
    lower incomplete gamma representation directly to
    scipy.special.gammainc. This avoids intermediate
    gamma-function overflow for large parameters.
    """
    return [
        {
            "_abess_regularized_gammainc":
                scipy_special.gammainc,
        },
        "scipy",
        "numpy",
        "math",
    ]


def _rewrite_regularized_gamma_for_numeric(
    expression
):
    """
    Rewrites

        lowergamma(a, z) / gamma(a)

    to a temporary numerical function that is evaluated
    directly by scipy.special.gammainc(a, z).

    The symbolic representation used elsewhere in ABESS
    remains unchanged.
    """
    replacements = {}

    for node in sp.preorder_traversal(
        expression
    ):
        if not isinstance(
            node,
            sp.Mul,
        ):
            continue

        factors = list(
            node.args
        )

        for factor in factors:
            if (
                factor.func
                != sp.lowergamma
            ):
                continue

            a, z_value = (
                factor.args
            )

            inverse_gamma = sp.Pow(
                sp.gamma(a),
                -1,
            )

            if (
                inverse_gamma
                not in factors
            ):
                continue

            replacement = (
                node
                / (
                    factor
                    * inverse_gamma
                )
                * _ABESS_REGULARIZED_GAMMA(
                    a,
                    z_value,
                )
            )

            replacements[node] = (
                replacement
            )

            break

    if not replacements:
        return expression

    return expression.xreplace(
        replacements
    )


def _build_fast_finite_product_function(
    x,
    expression,
):
    """
    Builds a vectorized numerical evaluator when an
    expression contains exactly one finite Product with
    one bound variable.

    More complicated Product structures simply return
    None so make_function() can use the existing symbolic
    fallback instead.
    """
    products = list(
        expression.atoms(
            sp.Product
        )
    )

    if len(products) != 1:
        return None

    product = products[0]

    if len(product.limits) != 1:
        return None

    try:
        (
            bound_variable,
            lower,
            upper,
        ) = product.limits[0]

        modules = (
            _numeric_lambdify_modules()
        )

        term_function = lambdify(
            (
                x,
                bound_variable,
            ),
            product.function,
            modules=modules,
        )

        lower_function = lambdify(
            x,
            lower,
            modules=modules,
        )

        upper_function = lambdify(
            x,
            upper,
            modules=modules,
        )

        product_placeholder = (
            sp.Symbol(
                "_abess_product_value"
            )
        )

        outer_expression = (
            expression.xreplace({
                product:
                    product_placeholder,
            })
        )

        outer_function = lambdify(
            (
                x,
                product_placeholder,
            ),
            outer_expression,
            modules=modules,
        )

    except Exception:
        return None

    def fast_product_function(
        value
    ):
        numeric_value = float(
            value
        )

        lower_value = int(
            round(
                float(
                    lower_function(
                        numeric_value
                    )
                )
            )
        )

        upper_value = int(
            round(
                float(
                    upper_function(
                        numeric_value
                    )
                )
            )
        )

        if lower_value > upper_value:
            product_value = 1.0

        else:
            term_count = (
                upper_value
                - lower_value
                + 1
            )

            if (
                term_count
                > _MAX_FAST_PRODUCT_TERMS
            ):
                raise ValueError(
                    "Finite Product contains "
                    "too many terms for safe "
                    "numeric evaluation"
                )

            indices = np.arange(
                lower_value,
                upper_value + 1,
                dtype=float,
            )

            terms = np.asarray(
                term_function(
                    numeric_value,
                    indices,
                )
            )

            if terms.ndim == 0:
                terms = np.full(
                    indices.shape,
                    terms.item(),
                )

            else:
                try:
                    terms = (
                        np.broadcast_to(
                            terms,
                            indices.shape,
                        )
                    )

                except ValueError as error:
                    raise ValueError(
                        "Finite Product terms "
                        "could not be evaluated "
                        "over the required range"
                    ) from error

            if np.iscomplexobj(
                terms
            ):
                imaginary = np.abs(
                    np.imag(
                        terms
                    )
                )

                if np.any(
                    imaginary
                    > 1e-12
                ):
                    raise ValueError(
                        "Finite Product returned "
                        "complex terms"
                    )

                terms = np.real(
                    terms
                )

            terms = np.asarray(
                terms,
                dtype=float,
            )

            if not np.all(
                np.isfinite(
                    terms
                )
            ):
                raise ValueError(
                    "Finite Product returned "
                    "non-finite terms"
                )

            product_value = float(
                np.prod(
                    terms
                )
            )

        result = outer_function(
            numeric_value,
            product_value,
        )

        if hasattr(
            result,
            "item",
        ):
            result = result.item()

        return result

    return fast_product_function


def make_function(equation_str):
    x, expr = prepare_expression(
        equation_str
    )

    # Preserve the symbolic expression used throughout
    # the application. Numerical-only rewrites are applied
    # to a separate expression.
    numeric_expression = (
        _rewrite_regularized_gamma_for_numeric(
            expr
        )
    )

    numeric_function = None

    try:
        # Fast path for ordinary expressions.
        #
        # The numerical rewrite also evaluates regularized
        # gammainc directly through SciPy, preventing
        # gamma(a) overflow in expressions such as
        # lowergamma(a,z) / gamma(a).
        numeric_function = lambdify(
            x,
            numeric_expression,
            modules=(
                _numeric_lambdify_modules()
            ),
        )

    except Exception:
        # Product with x-dependent limits cannot normally
        # be emitted by the SciPy lambdify printer.
        #
        # Attempt a vectorized finite-Product evaluator.
        numeric_function = (
            _build_fast_finite_product_function(
                x,
                numeric_expression,
            )
        )

    def f(value):
        numeric_value = float(
            value
        )

        if numeric_function is not None:
            result = numeric_function(
                numeric_value
            )

            if hasattr(
                result,
                "item",
            ):
                result = result.item()

            if isinstance(
                result,
                complex,
            ):
                if (
                    abs(result.imag)
                    > 1e-12
                ):
                    raise ValueError(
                        "The function returned "
                        "a complex value"
                    )

                result = result.real

            result = float(
                result
            )

        else:
            # Compatibility fallback for valid expressions
            # that cannot use either numerical fast path.
            evaluated = (
                expr.subs(
                    x,
                    numeric_value,
                )
                .doit()
                .evalf()
            )

            evaluated_complex = complex(
                evaluated
            )

            if (
                abs(
                    evaluated_complex.imag
                )
                > 1e-12
            ):
                raise ValueError(
                    "The function returned "
                    "a complex value"
                )

            result = float(
                evaluated_complex.real
            )

        if not math.isfinite(
            result
        ):
            raise ValueError(
                "The function returned "
                "a non-finite value"
            )

        return result

    return f


def serialize_number(
    value,
    imag_tol=1e-12,
):
    """
    Converts real/complex numeric values to JSON-safe output.
    """
    numeric_value = complex(
        value
    )

    if (
        abs(numeric_value.imag)
        <= imag_tol
    ):
        return float(
            numeric_value.real
        )

    return {
        "real": float(
            numeric_value.real
        ),

        "imag": float(
            numeric_value.imag
        ),
    }


def make_complex_function(
    equation_str
):
    """
    Complex-capable evaluator used by Muller.

    Expressions containing ordering/integer-valued constructs
    such as floor, ceiling, Min and Max are evaluated through
    the general real evaluator while the approximation remains
    on the real axis. Other expressions retain the existing
    complex SymPy evaluation path.
    """

    x, expr = prepare_expression(
        equation_str
    )

    requires_real_input = expr.has(
        sp.floor,
        sp.ceiling,
        sp.Min,
        sp.Max,
    )

    real_function = (
        make_function(equation_str)
        if requires_real_input
        else None
    )

    def f(value):
        numeric_value = complex(
            value
        )

        if requires_real_input:
            if (
                abs(numeric_value.imag)
                > 1e-12
            ):
                raise ValueError(
                    "The expression contains mathematical "
                    "constructs that require real-valued input"
                )

            result = complex(
                real_function(
                    float(
                        numeric_value.real
                    )
                )
            )

        else:
            result = expr.evalf(
                subs={
                    x: numeric_value
                }
            )

            result = complex(
                result
            )

        if (
            not math.isfinite(
                result.real
            )
            or not math.isfinite(
                result.imag
            )
        ):
            raise ValueError(
                "The function returned a non-finite value"
            )

        return result

    return f


def safe_eval_complex(
    function,
    value,
):
    try:
        result = complex(
            function(value)
        )

        if (
            not math.isfinite(
                result.real
            )
            or not math.isfinite(
                result.imag
            )
        ):
            return None

        return result

    except Exception:
        return None


def safe_eval(
    function,
    value,
):
    try:
        result = function(value)

        if not math.isfinite(
            result
        ):
            return None

        return result

    except Exception:
        return None


def add_auto_parameters_info(
    result,
    auto_parameters,
):
    if not isinstance(
        result,
        dict,
    ):
        return result

    if auto_parameters:
        result[
            "auto_parameters_used"
        ] = True

        result[
            "auto_parameters"
        ] = auto_parameters

        if not result.get(
            "message"
        ):
            result["message"] = (
                "The application automatically "
                "calculated the required parameters."
            )

    else:
        result[
            "auto_parameters_used"
        ] = False

    return result


def _requires_symbolic_numeric_fallback(
    equation_str
):
    """
    Return True when the parsed expression cannot be compiled
    through the normal SciPy/math lambdify fast path.

    Such expressions remain fully supported through the
    general substitution/doit/evalf numeric fallback.
    """
    try:
        x, expr = prepare_expression(
            equation_str
        )

        lambdify(
            x,
            expr,
            modules=[
                "scipy",
                "math",
            ],
        )

        return False

    except Exception:
        return True


def find_sign_change_interval(
    equation_str,
    search_min=-50,
    search_max=50,
    step=0.5,
    tol=1e-8,
):
    """
    Automatically searches for an interval [a,b]
    where f(a) and f(b) have opposite signs.
    """

    if step <= 0:
        raise ValueError(
            "Search step must be greater than zero"
        )

    if search_min >= search_max:
        raise ValueError(
            "search_min must be smaller than search_max"
        )

    uses_fallback = (
        _requires_symbolic_numeric_fallback(
            equation_str
        )
    )

    is_default_search = (
        search_min == -50
        and search_max == 50
        and step == 0.5
    )

    # Expensive symbolic-numeric expressions should not
    # immediately scan the entire [-50, 50] range.
    #
    # Existing fast/lambdified expressions retain the
    # original search behaviour unchanged.
    if (
        uses_fallback
        and is_default_search
    ):
        focused_bracket = (
            find_sign_change_interval(
                equation_str,
                search_min=-2,
                search_max=2,
                step=0.5,
                tol=tol,
            )
        )

        if focused_bracket:
            function = make_function(
                equation_str
            )

            a = float(
                focused_bracket[0]
            )

            b = float(
                focused_bracket[1]
            )

            fa = safe_eval(
                function,
                a,
            )

            fb = safe_eval(
                function,
                b,
            )

            if (
                fa is not None
                and fb is not None
                and fa * fb < 0
            ):
                for _ in range(6):
                    midpoint = (
                        a + b
                    ) / 2.0

                    fm = safe_eval(
                        function,
                        midpoint,
                    )

                    if fm is None:
                        break

                    if abs(fm) <= tol:
                        return [
                            float(midpoint),
                            float(midpoint),
                        ]

                    if fa * fm < 0:
                        b = midpoint
                        fb = fm

                    elif fm * fb < 0:
                        a = midpoint
                        fa = fm

                    else:
                        break

                return [
                    float(a),
                    float(b),
                ]

            return [
                float(
                    focused_bracket[0]
                ),
                float(
                    focused_bracket[1]
                ),
            ]

    function = make_function(
        equation_str
    )

    previous_x = None
    previous_y = None

    total_steps = int(
        math.ceil(
            (
                search_max
                - search_min
            )
            / step
        )
    )

    for index in range(
        total_steps + 1
    ):
        current_x = min(
            search_min
            + index * step,
            search_max,
        )

        current_y = safe_eval(
            function,
            current_x,
        )

        if current_y is None:
            previous_x = None
            previous_y = None
            continue

        if abs(current_y) <= tol:
            right_x = min(
                current_x + step,
                search_max,
            )

            right_y = safe_eval(
                function,
                right_x,
            )

            if (
                right_x
                != current_x
                and right_y
                is not None
            ):
                return sorted([
                    current_x,
                    right_x,
                ])

            left_x = max(
                current_x - step,
                search_min,
            )

            left_y = safe_eval(
                function,
                left_x,
            )

            if (
                left_x
                != current_x
                and left_y
                is not None
            ):
                return sorted([
                    left_x,
                    current_x,
                ])

        if (
            previous_y
            is not None
            and previous_x
            is not None
            and previous_y
            * current_y
            < 0
        ):
            return sorted([
                previous_x,
                current_x,
            ])

        previous_x = current_x
        previous_y = current_y

    return None


def find_best_initial_guess(
    equation_str
):
    """
    Finds x0 where |f(x)| is smallest
    across successive search ranges.
    """

    if _requires_symbolic_numeric_fallback(
        equation_str
    ):
        bracket = find_sign_change_interval(
            equation_str
        )

        if bracket:
            return float(
                (
                    float(bracket[0])
                    + float(bracket[1])
                )
                / 2.0
            )

    function = make_function(
        equation_str
    )

    best_x = None
    best_abs_y = None

    scan_ranges = [
        (-10, 10, 0.25),
        (-50, 50, 1.0),
        (-100, 100, 2.0),
    ]

    for (
        search_min,
        search_max,
        step,
    ) in scan_ranges:

        total_steps = int(
            math.ceil(
                (
                    search_max
                    - search_min
                )
                / step
            )
        )

        for index in range(
            total_steps + 1
        ):
            current_x = min(
                search_min
                + index * step,
                search_max,
            )

            current_y = safe_eval(
                function,
                current_x,
            )

            if current_y is None:
                continue

            absolute_y = abs(
                current_y
            )

            if (
                best_abs_y is None
                or absolute_y
                < best_abs_y
            ):
                best_abs_y = (
                    absolute_y
                )

                best_x = current_x

                if (
                    best_abs_y
                    <= 1e-10
                ):
                    return best_x

    if best_x is None:
        return 0.0

    return float(best_x)


def find_secant_initial_guesses(
    equation_str
):
    """
    Automatically finds x0 and x1 for Secant.
    """

    bracket = (
        find_sign_change_interval(
            equation_str
        )
    )

    if bracket:
        return (
            float(bracket[0]),
            float(bracket[1]),
        )

    x0 = (
        find_best_initial_guess(
            equation_str
        )
    )

    return (
        float(x0 - 1.0),
        float(x0 + 1.0),
    )


def bisection_method(
    equation_str,
    a,
    b,
    tol=1e-6,
    max_iter=100,
):
    function = make_function(
        equation_str
    )

    a = float(a)
    b = float(b)

    if a > b:
        a, b = b, a

    if a == b:
        return {
            "success": False,
            "method": "bisection",
            "error": (
                "Invalid interval: "
                "a and b cannot be equal"
            ),
        }

    fa = safe_eval(
        function,
        a,
    )

    fb = safe_eval(
        function,
        b,
    )

    if (
        fa is None
        or fb is None
    ):
        return {
            "success": False,
            "method": "bisection",
            "error": (
                "The function could not be evaluated "
                "at one or both interval endpoints"
            ),
        }

    if abs(fa) <= tol:
        return {
            "success": True,
            "method": "bisection",
            "root": a,
            "iterations": 0,
            "steps": [],
            "message": (
                "Root found at interval endpoint a"
            ),
        }

    if abs(fb) <= tol:
        return {
            "success": True,
            "method": "bisection",
            "root": b,
            "iterations": 0,
            "steps": [],
            "message": (
                "Root found at interval endpoint b"
            ),
        }

    if fa * fb > 0:
        return {
            "success": False,
            "method": "bisection",
            "error": (
                "Invalid interval: "
                "f(a) and f(b) must have opposite signs"
            ),
        }

    steps = []

    midpoint = (
        a + b
    ) / 2

    f_midpoint = safe_eval(
        function,
        midpoint,
    )

    for iteration in range(
        1,
        max_iter + 1,
    ):
        midpoint = (
            a + b
        ) / 2

        f_midpoint = safe_eval(
            function,
            midpoint,
        )

        if f_midpoint is None:
            return {
                "success": False,
                "method": "bisection",
                "error": (
                    "The function could not be evaluated "
                    "inside the interval"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        steps.append({
            "iteration": iteration,
            "a": a,
            "b": b,
            "c": midpoint,
            "f(c)": f_midpoint,
        })

        if (
            abs(f_midpoint)
            <= tol
            or abs(b - a) / 2
            <= tol
        ):
            return {
                "success": True,
                "method": "bisection",
                "root": float(
                    midpoint
                ),
                "iterations": iteration,
                "steps": steps,
            }

        if (
            fa
            * f_midpoint
            < 0
        ):
            b = midpoint
            fb = f_midpoint

        else:
            a = midpoint
            fa = f_midpoint

    return {
        "success": False,
        "method": "bisection",
        "root": float(
            midpoint
        ),
        "f(root)": f_midpoint,
        "iterations": max_iter,
        "steps": steps,
        "error": (
            "Bisection method did not converge "
            "within the maximum number of iterations"
        ),
    }


def fzero_method(
    equation_str,
    a,
    b,
    tol=1e-6,
    max_iter=100,
):
    function = make_function(
        equation_str
    )

    a = float(a)
    b = float(b)

    if a > b:
        a, b = b, a

    if a == b:
        return {
            "success": False,
            "method": "fzero",
            "error": (
                "Invalid interval: "
                "a and b cannot be equal"
            ),
        }

    fa = safe_eval(
        function,
        a,
    )

    fb = safe_eval(
        function,
        b,
    )

    if (
        fa is None
        or fb is None
    ):
        return {
            "success": False,
            "method": "fzero",
            "error": (
                "The function could not be evaluated "
                "at one or both interval endpoints"
            ),
        }

    if abs(fa) <= tol:
        return {
            "success": True,
            "method": "fzero",
            "root": a,
            "iterations": 0,
            "steps": [],
            "message": (
                "Root found at interval endpoint a"
            ),
        }

    if abs(fb) <= tol:
        return {
            "success": True,
            "method": "fzero",
            "root": b,
            "iterations": 0,
            "steps": [],
            "message": (
                "Root found at interval endpoint b"
            ),
        }

    if fa * fb > 0:
        return {
            "success": False,
            "method": "fzero",
            "error": (
                "Invalid interval: "
                "f(a) and f(b) must have opposite signs"
            ),
        }

    scalar_result = root_scalar(
        function,
        bracket=[
            a,
            b,
        ],
        method="brentq",
        xtol=tol,
        maxiter=max_iter,
    )

    root = float(
        scalar_result.root
    )

    f_root = safe_eval(
        function,
        root,
    )

    residual_tolerance = max(
        tol * 10,
        1e-8,
    )

    if (
        not scalar_result.converged
        or f_root is None
        or abs(f_root)
        > residual_tolerance
    ):
        return {
            "success": False,
            "method": "fzero",
            "root": root,
            "f(root)": f_root,
            "iterations": (
                scalar_result.iterations
            ),
            "steps": [],
            "error": (
                "fzero-compatible solver did not "
                "converge to a valid root"
            ),
        }

    return {
        "success": True,
        "method": "fzero",
        "root": root,
        "f(root)": f_root,
        "iterations": (
            scalar_result.iterations
        ),
        "steps": [],
        "message": (
            "fzero-compatible solver "
            "completed successfully"
        ),
    }


def newton_method(
    equation_str,
    x0,
    tol=1e-6,
    max_iter=100,
):
    function = make_function(
        equation_str
    )

    x, expr = prepare_expression(
        equation_str
    )

    derivative_function_raw = None

    try:
        # Use the symbolic derivative whenever SymPy/SciPy
        # can compile it through the normal fast path.
        derivative = diff(
            expr,
            x,
        )

        derivative_function_raw = (
            lambdify(
                x,
                derivative,
                modules=[
                    "scipy",
                    "math",
                ],
            )
        )

    except Exception:
        # Advanced expressions such as Product with
        # x-dependent limits may not have a derivative
        # representation that SciPy can compile.
        #
        # Newton then uses a numerical derivative of the
        # same general equation function.
        derivative_function_raw = None

    if derivative_function_raw is not None:

        def derivative_function(
            value
        ):
            result = (
                derivative_function_raw(
                    float(value)
                )
            )

            if hasattr(
                result,
                "item",
            ):
                result = result.item()

            if isinstance(
                result,
                complex,
            ):
                if (
                    abs(result.imag)
                    > 1e-12
                ):
                    raise ValueError(
                        "The derivative returned "
                        "a complex value"
                    )

                result = result.real

            result = float(result)

            if not math.isfinite(
                result
            ):
                raise ValueError(
                    "The derivative returned "
                    "a non-finite value"
                )

            return result

    else:

        def derivative_function(
            value
        ):
            value = float(value)

            h = (
                1e-6
                * max(
                    1.0,
                    abs(value),
                )
            )

            f_plus = safe_eval(
                function,
                value + h,
            )

            f_minus = safe_eval(
                function,
                value - h,
            )

            if (
                f_plus is not None
                and f_minus is not None
            ):
                result = (
                    (f_plus - f_minus)
                    / (2.0 * h)
                )

            else:
                # One-sided fallback near a domain boundary.
                f_center = safe_eval(
                    function,
                    value,
                )

                if f_center is None:
                    raise ValueError(
                        "The derivative could not "
                        "be evaluated"
                    )

                if f_plus is not None:
                    result = (
                        (f_plus - f_center)
                        / h
                    )

                elif f_minus is not None:
                    result = (
                        (f_center - f_minus)
                        / h
                    )

                else:
                    raise ValueError(
                        "The derivative could not "
                        "be evaluated"
                    )

            result = float(result)

            if not math.isfinite(
                result
            ):
                raise ValueError(
                    "The derivative returned "
                    "a non-finite value"
                )

            return result

    current_x = float(x0)

    steps = []

    derivative_epsilon = (
        1e-14
    )

    residual_tolerance = max(
        tol * 10,
        1e-8,
    )

    for iteration in range(
        1,
        max_iter + 1,
    ):
        fx = safe_eval(
            function,
            current_x,
        )

        fpx = safe_eval(
            derivative_function,
            current_x,
        )

        if fx is None:
            return {
                "success": False,
                "method": "newton",
                "error": (
                    "The function could not be evaluated "
                    "at the current approximation"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        if (
            fpx is None
            or abs(fpx)
            <= derivative_epsilon
        ):
            return {
                "success": False,
                "method": "newton",
                "error": (
                    "Derivative is zero or "
                    "too close to zero"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        next_x = (
            current_x
            - fx / fpx
        )

        if not math.isfinite(
            next_x
        ):
            return {
                "success": False,
                "method": "newton",
                "error": (
                    "Newton method produced "
                    "a non-finite approximation"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        steps.append({
            "iteration": iteration,
            "x": current_x,
            "f(x)": fx,
            "f'(x)": fpx,
            "next_x": next_x,
        })

        next_fx = safe_eval(
            function,
            next_x,
        )

        if (
            abs(
                next_x
                - current_x
            )
            <= tol
            and next_fx
            is not None
            and abs(next_fx)
            <= residual_tolerance
        ):
            return {
                "success": True,
                "method": "newton",
                "root": float(
                    next_x
                ),
                "f(root)": next_fx,
                "iterations": iteration,
                "steps": steps,
            }

        current_x = next_x

    final_fx = safe_eval(
        function,
        current_x,
    )

    return {
        "success": False,
        "method": "newton",
        "root": float(
            current_x
        ),
        "f(root)": final_fx,
        "iterations": max_iter,
        "steps": steps,
        "error": (
            "Newton method did not converge "
            "within the maximum number of iterations"
        ),
    }


def secant_method(
    equation_str,
    x0,
    x1,
    tol=1e-6,
    max_iter=100,
):
    function = make_function(
        equation_str
    )

    previous_x = float(x0)
    current_x = float(x1)

    if previous_x == current_x:
        return {
            "success": False,
            "method": "secant",
            "error": (
                "Secant method requires "
                "different x0 and x1 values"
            ),
        }

    steps = []

    denominator_epsilon = (
        1e-14
    )

    residual_tolerance = max(
        tol * 10,
        1e-8,
    )

    for iteration in range(
        1,
        max_iter + 1,
    ):
        previous_fx = safe_eval(
            function,
            previous_x,
        )

        current_fx = safe_eval(
            function,
            current_x,
        )

        if (
            previous_fx is None
            or current_fx is None
        ):
            return {
                "success": False,
                "method": "secant",
                "error": (
                    "The function could not be evaluated "
                    "at one of the current approximations"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        denominator = (
            current_fx
            - previous_fx
        )

        if (
            abs(denominator)
            <= denominator_epsilon
        ):
            return {
                "success": False,
                "method": "secant",
                "error": (
                    "Division by zero or near-zero "
                    "in secant method"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        next_x = (
            current_x
            - current_fx
            * (
                current_x
                - previous_x
            )
            / denominator
        )

        if not math.isfinite(
            next_x
        ):
            return {
                "success": False,
                "method": "secant",
                "error": (
                    "Secant method produced "
                    "a non-finite approximation"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        steps.append({
            "iteration": iteration,
            "x0": previous_x,
            "x1": current_x,
            "f(x0)": previous_fx,
            "f(x1)": current_fx,
            "next_x": next_x,
        })

        next_fx = safe_eval(
            function,
            next_x,
        )

        if (
            abs(
                next_x
                - current_x
            )
            <= tol
            and next_fx
            is not None
            and abs(next_fx)
            <= residual_tolerance
        ):
            return {
                "success": True,
                "method": "secant",
                "root": float(
                    next_x
                ),
                "f(root)": next_fx,
                "iterations": iteration,
                "steps": steps,
            }

        previous_x = current_x
        current_x = next_x

    final_fx = safe_eval(
        function,
        current_x,
    )

    return {
        "success": False,
        "method": "secant",
        "root": float(
            current_x
        ),
        "f(root)": final_fx,
        "iterations": max_iter,
        "steps": steps,
        "error": (
            "Secant method did not converge "
            "within the maximum number of iterations"
        ),
    }


def itp_method(
    equation_str,
    a,
    b,
    tol=1e-6,
    max_iter=100,
    kappa2=2.0,
    n0=1,
):
    """
    Interpolate-Truncate-Project (ITP) root-finding method.

    It preserves a valid sign-change bracket while using interpolation
    to accelerate convergence.
    """

    function = make_function(
        equation_str
    )

    a = float(a)
    b = float(b)

    if a > b:
        a, b = b, a

    if a == b:
        return {
            "success": False,
            "method": "itp",
            "error": (
                "Invalid interval: "
                "a and b cannot be equal"
            ),
        }

    fa = safe_eval(
        function,
        a,
    )

    fb = safe_eval(
        function,
        b,
    )

    if (
        fa is None
        or fb is None
    ):
        return {
            "success": False,
            "method": "itp",
            "error": (
                "The function could not be evaluated "
                "at one or both interval endpoints"
            ),
        }

    if abs(fa) <= tol:
        return {
            "success": True,
            "method": "itp",
            "root": a,
            "f(root)": fa,
            "iterations": 0,
            "steps": [],
        }

    if abs(fb) <= tol:
        return {
            "success": True,
            "method": "itp",
            "root": b,
            "f(root)": fb,
            "iterations": 0,
            "steps": [],
        }

    if fa * fb > 0:
        return {
            "success": False,
            "method": "itp",
            "error": (
                "Invalid interval: "
                "f(a) and f(b) must have opposite signs"
            ),
        }

    initial_width = (
        b - a
    )

    n_half = max(
        0,
        math.ceil(
            math.log2(
                max(
                    initial_width
                    / (2.0 * tol),
                    1.0,
                )
            )
        ),
    )

    n_max = (
        n_half
        + max(
            int(n0),
            0,
        )
    )

    kappa1 = (
        0.2
        / max(
            initial_width,
            1e-15,
        )
    )

    steps = []

    for iteration in range(
        max_iter
    ):
        width = (
            b - a
        )

        if width <= 2.0 * tol:
            root = (
                a + b
            ) / 2.0

            f_root = safe_eval(
                function,
                root,
            )

            return {
                "success": (
                    f_root is not None
                    and abs(f_root)
                    <= max(
                        tol * 10,
                        1e-8,
                    )
                ),
                "method": "itp",
                "root": float(root),
                "f(root)": f_root,
                "iterations": iteration,
                "steps": steps,
            }

        midpoint = (
            a + b
        ) / 2.0

        denominator = (
            fb - fa
        )

        if (
            abs(denominator)
            <= 1e-30
        ):
            x_f = midpoint

        else:
            x_f = (
                a * fb
                - b * fa
            ) / denominator

        sigma = (
            1.0
            if midpoint - x_f >= 0
            else -1.0
        )

        delta = (
            kappa1
            * (
                width
                ** kappa2
            )
        )

        x_t = (
            x_f
            + sigma
            * min(
                delta,
                abs(
                    midpoint
                    - x_f
                ),
            )
        )

        r = (
            tol
            * (
                2.0
                ** max(
                    n_max
                    - iteration,
                    0,
                )
            )
            - width / 2.0
        )

        r = max(
            r,
            0.0,
        )

        x_itp = (
            x_t
            + sigma
            * min(
                r,
                abs(
                    midpoint
                    - x_t
                ),
            )
        )

        tiny = min(
            tol * 0.1,
            width * 1e-12,
        )

        x_itp = min(
            max(
                x_itp,
                a + tiny,
            ),
            b - tiny,
        )

        f_itp = safe_eval(
            function,
            x_itp,
        )

        if f_itp is None:
            return {
                "success": False,
                "method": "itp",
                "error": (
                    "The function could not be evaluated "
                    "at the ITP approximation"
                ),
                "iterations": iteration,
                "steps": steps,
            }

        steps.append({
            "iteration": (
                iteration + 1
            ),
            "a": a,
            "b": b,
            "x": x_itp,
            "f(x)": f_itp,
        })

        if abs(f_itp) <= tol:
            return {
                "success": True,
                "method": "itp",
                "root": float(
                    x_itp
                ),
                "f(root)": f_itp,
                "iterations": (
                    iteration + 1
                ),
                "steps": steps,
            }

        if (
            fa
            * f_itp
            < 0
        ):
            b = x_itp
            fb = f_itp

        else:
            a = x_itp
            fa = f_itp

    root = (
        a + b
    ) / 2.0

    f_root = safe_eval(
        function,
        root,
    )

    residual_tolerance = max(
        tol * 10,
        1e-8,
    )

    success = (
        f_root is not None
        and abs(f_root)
        <= residual_tolerance
    )

    return {
        "success": success,
        "method": "itp",
        "root": float(root),
        "f(root)": f_root,
        "iterations": max_iter,
        "steps": steps,
        "error": (
            None
            if success
            else (
                "ITP method did not converge "
                "to a valid root"
            )
        ),
    }


def find_muller_initial_guesses(
    equation_str
):
    # Muller benefits from starting close to the root.
    # Search near zero first so expensive advanced
    # expressions do not require a full [-50, 50] scan.
    bracket = find_sign_change_interval(
        equation_str,
        search_min=-2,
        search_max=2,
        step=0.5,
    )

    # Preserve the previous broad search as a fallback.
    if bracket is None:
        bracket = find_sign_change_interval(
            equation_str
        )

    if bracket:
        a, b = (
            float(bracket[0]),
            float(bracket[1]),
        )

        function = make_function(
            equation_str
        )

        fa = safe_eval(
            function,
            a,
        )

        fb = safe_eval(
            function,
            b,
        )

        # Refine only genuine sign-change brackets.
        # Six bisection-style refinements reduce a
        # width of 0.5 to less than 0.008.
        if (
            fa is not None
            and fb is not None
            and fa * fb < 0
        ):
            for _ in range(6):
                midpoint = (
                    a + b
                ) / 2.0

                fm = safe_eval(
                    function,
                    midpoint,
                )

                if fm is None:
                    break

                if abs(fm) <= 1e-12:
                    return (
                        complex(a),
                        complex(b),
                        complex(midpoint),
                    )

                if fa * fm < 0:
                    b = midpoint
                    fb = fm

                elif fm * fb < 0:
                    a = midpoint
                    fa = fm

                else:
                    break

        midpoint = (
            a + b
        ) / 2.0

        # Muller uses x2 as the current approximation.
        return (
            complex(a),
            complex(b),
            complex(midpoint),
        )

    center = (
        find_best_initial_guess(
            equation_str
        )
    )

    return (
        complex(
            center - 1.0
        ),
        complex(center),
        complex(
            center + 1.0
        ),
    )


def muller_method(
    equation_str,
    x0,
    x1,
    x2,
    tol=1e-6,
    max_iter=100,
):
    function = (
        make_complex_function(
            equation_str
        )
    )

    x0 = complex(x0)
    x1 = complex(x1)
    x2 = complex(x2)

    steps = []

    residual_tolerance = max(
        tol * 10,
        1e-8,
    )

    for iteration in range(
        1,
        max_iter + 1,
    ):
        f0 = safe_eval_complex(
            function,
            x0,
        )

        f1 = safe_eval_complex(
            function,
            x1,
        )

        f2 = safe_eval_complex(
            function,
            x2,
        )

        if (
            f0 is None
            or f1 is None
            or f2 is None
        ):
            return {
                "success": False,
                "method": "muller",
                "error": (
                    "The function could not be evaluated "
                    "at one of the Muller approximations"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        # Recognize an existing root before interpolation.
        exact_root_tolerance = min(
            1e-12,
            residual_tolerance,
        )

        for candidate_x, candidate_value in (
            (x2, f2),
            (x1, f1),
            (x0, f0),
        ):
            if abs(candidate_value) <= exact_root_tolerance:
                return {
                    "success": True,
                    "method": "muller",
                    "root": serialize_number(candidate_x),
                    "f(root)": serialize_number(candidate_value),
                    "iterations": iteration - 1,
                    "steps": steps,
                }

        h1 = (
            x1 - x0
        )

        h2 = (
            x2 - x1
        )

        if (
            abs(h1)
            <= 1e-30
            or abs(h2)
            <= 1e-30
        ):
            return {
                "success": False,
                "method": "muller",
                "error": (
                    "Muller method requires "
                    "three distinct starting points"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        d1 = (
            f1 - f0
        ) / h1

        d2 = (
            f2 - f1
        ) / h2

        denominator_h = (
            h2 + h1
        )

        if (
            abs(denominator_h)
            <= 1e-30
        ):
            return {
                "success": False,
                "method": "muller",
                "error": (
                    "Muller interpolation "
                    "became singular"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        d = (
            d2 - d1
        ) / denominator_h

        b_value = (
            d2
            + h2 * d
        )

        discriminant = cmath.sqrt(
            b_value
            * b_value
            - 4.0
            * f2
            * d
        )

        denominator_1 = (
            b_value
            + discriminant
        )

        denominator_2 = (
            b_value
            - discriminant
        )

        denominator = (
            denominator_1
            if (
                abs(denominator_1)
                >= abs(denominator_2)
            )
            else denominator_2
        )

        if (
            abs(denominator)
            <= 1e-30
        ):
            return {
                "success": False,
                "method": "muller",
                "error": (
                    "Muller method encountered "
                    "a zero denominator"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        h = (
            -2.0
            * f2
            / denominator
        )

        x3 = (
            x2 + h
        )

        f3 = safe_eval_complex(
            function,
            x3,
        )

        if f3 is None:
            return {
                "success": False,
                "method": "muller",
                "error": (
                    "The next Muller approximation "
                    "is not evaluable"
                ),
                "iterations": (
                    iteration - 1
                ),
                "steps": steps,
            }

        steps.append({
            "iteration": iteration,
            "x": serialize_number(
                x2
            ),
            "next_x": serialize_number(
                x3
            ),
            "f(next_x)": serialize_number(
                f3
            ),
        })

        if (
            abs(f3) <= exact_root_tolerance
            or (
                abs(h) <= tol
                and abs(f3) <= residual_tolerance
            )
        ):
            return {
                "success": True,
                "method": "muller",
                "root": serialize_number(
                    x3
                ),
                "f(root)": serialize_number(
                    f3
                ),
                "iterations": iteration,
                "steps": steps,
            }

        x0 = x1
        x1 = x2
        x2 = x3

    final_value = (
        safe_eval_complex(
            function,
            x2,
        )
    )

    success = (
        final_value
        is not None
        and abs(final_value)
        <= residual_tolerance
    )

    return {
        "success": success,
        "method": "muller",
        "root": serialize_number(
            x2
        ),
        "f(root)": (
            serialize_number(
                final_value
            )
            if final_value
            is not None
            else None
        ),
        "iterations": max_iter,
        "steps": steps,
        "error": (
            None
            if success
            else (
                "Muller method did not converge "
                "to a valid root"
            )
        ),
    }


def roots_method(
    equation_str,
    max_iter=100,
):
    x, expr = prepare_expression(
        equation_str
    )

    try:
        polynomial = Poly(
            expr,
            x,
        )

    except Exception:
        return {
            "success": False,
            "method": "roots",
            "error": (
                "The equation is not "
                "polynomial in x"
            ),
        }

    try:
        calculated_roots = (
            polynomial.nroots(
                maxsteps=max_iter,
            )
        )

    except Exception as error:
        return {
            "success": False,
            "method": "roots",
            "error": (
                "Polynomial roots could not "
                f"be calculated: {error}"
            ),
        }

    roots_output = [
        serialize_number(
            complex(root)
        )
        for root
        in calculated_roots
    ]

    if not roots_output:
        return {
            "success": False,
            "method": "roots",
            "error": (
                "No polynomial roots "
                "were returned"
            ),
        }

    analytical_solutions = []

    try:
        exact_roots = (
            polynomial.all_roots(
                multiple=True,
                radicals=True,
            )
        )

        analytical_solutions = [
            str(root)
            for root
            in exact_roots
        ]

    except Exception:
        analytical_solutions = []

    return {
        "success": True,
        "method": "roots",
        "root": roots_output[0],
        "roots": roots_output,
        "analytical_solutions": (
            analytical_solutions
        ),
        "numeric_solutions": (
            roots_output
        ),
        "solution_variable": "x",
        "iterations": None,
        "steps": [],
    }


def symbolic_solve_method(
    equation_str
):
    x, expr = prepare_expression(
        equation_str
    )

    try:
        solutions = sympy_solve(
            expr,
            x,
        )

    except Exception as error:
        return {
            "success": False,
            "method": "solve",
            "error": (
                "Symbolic solve failed: "
                f"{error}"
            ),
        }

    if not solutions:
        return {
            "success": False,
            "method": "solve",
            "error": (
                "No symbolic solution was found"
            ),
        }

    symbolic_solutions = [
        str(solution)
        for solution
        in solutions
    ]

    numeric_solutions = []

    for solution in solutions:
        try:
            if getattr(
                solution,
                "free_symbols",
                set(),
            ):
                numeric_solutions.append(
                    None
                )
                continue

            numeric_solutions.append(
                serialize_number(
                    complex(
                        solution.evalf()
                    )
                )
            )

        except Exception:
            numeric_solutions.append(
                None
            )

    compatible_root = next(
        (
            value
            for value
            in numeric_solutions
            if value is not None
        ),
        symbolic_solutions[0],
    )

    return {
        "success": True,
        "method": "solve",
        "root": compatible_root,
        "solutions": symbolic_solutions,
        "analytical_solutions": (
            symbolic_solutions
        ),
        "numeric_solutions": (
            numeric_solutions
        ),
        "solution_variable": "x",
        "iterations": None,
        "steps": [],
    }


def integer_exhaustive_scan_method(
    equation_str,
    a=None,
    b=None,
    tol=1e-8,
    default_min=-1000,
    default_max=1000,
):
    """
    Exhaustive integer search.

    For a monotonic threshold problem, if a sign change occurs
    between consecutive integers, the first integer on the
    target side of zero is returned.
    """

    function = make_function(
        equation_str
    )

    start = (
        math.ceil(
            float(a)
        )
        if a is not None
        else int(
            default_min
        )
    )

    end = (
        math.floor(
            float(b)
        )
        if b is not None
        else int(
            default_max
        )
    )

    if start > end:
        start, end = (
            end,
            start,
        )

    previous_n = None
    previous_value = None
    best_n = None
    best_value = None

    for n in range(
        start,
        end + 1,
    ):
        value = safe_eval(
            function,
            n,
        )

        if value is None:
            continue

        if (
            best_value is None
            or abs(value)
            < abs(best_value)
        ):
            best_n = n
            best_value = value

        if abs(value) <= tol:
            return {
                "success": True,
                "method": (
                    "integer_exhaustive_scan"
                ),
                "root": int(n),
                "f(root)": value,
                "iterations": (
                    n - start + 1
                ),
                "steps": [],
            }

        if (
            previous_value
            is not None
            and previous_n
            is not None
            and previous_value
            * value
            < 0
        ):
            return {
                "success": True,
                "method": (
                    "integer_exhaustive_scan"
                ),
                "root": int(n),
                "f(root)": value,
                "crossing_from": int(
                    previous_n
                ),
                "iterations": (
                    n - start + 1
                ),
                "steps": [],
                "message": (
                    "No exact integer root exists; "
                    "returned the first integer after "
                    "the zero/threshold crossing."
                ),
            }

        previous_n = n
        previous_value = value

    return {
        "success": False,
        "method": (
            "integer_exhaustive_scan"
        ),
        "root": (
            int(best_n)
            if best_n is not None
            else None
        ),
        "f(root)": best_value,
        "iterations": (
            end - start + 1
        ),
        "steps": [],
        "error": (
            "No integer root or threshold crossing "
            "was found inside the scan interval"
        ),
    }


def solve_equation(data):
    method = normalize_method(
        data.method
    )

    # Automatic selection must be resolved
    # by the rAIson router first.
    if method is None:
        return {
            "success": False,
            "error": (
                "NO_METHOD_SELECTED"
            ),
            "message": (
                "No concrete method was selected. "
                "Automatic mode must receive a "
                "method from rAIson first."
            ),
            "supported_methods": sorted(
                SUPPORTED_METHODS
            ),
        }

    if (
        method
        not in SUPPORTED_METHODS
    ):
        return {
            "success": False,
            "method": method,
            "error": (
                "The selected method "
                "is not supported."
            ),
            "supported_methods": sorted(
                SUPPORTED_METHODS
            ),
        }

    try:

        if method == "bisection":
            auto_parameters = {}

            a = data.a
            b = data.b

            if (
                a is None
                or b is None
            ):
                bracket = (
                    find_sign_change_interval(
                        data.equation
                    )
                )

                if not bracket:
                    return {
                        "success": False,
                        "method": (
                            "bisection"
                        ),
                        "error": (
                            "Could not automatically "
                            "find interval [a,b] "
                            "with opposite signs"
                        ),
                    }

                a, b = bracket

                auto_parameters = {
                    "a": a,
                    "b": b,
                }

            result = (
                bisection_method(
                    data.equation,
                    a,
                    b,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "fzero":
            auto_parameters = {}

            a = data.a
            b = data.b

            if (
                a is None
                or b is None
            ):
                bracket = (
                    find_sign_change_interval(
                        data.equation
                    )
                )

                if not bracket:
                    return {
                        "success": False,
                        "method": "fzero",
                        "error": (
                            "fzero requires a valid "
                            "sign-change interval and "
                            "no interval could be found "
                            "automatically"
                        ),
                    }

                a, b = bracket

                auto_parameters = {
                    "a": a,
                    "b": b,
                }

            result = (
                fzero_method(
                    data.equation,
                    a,
                    b,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "itp":
            auto_parameters = {}

            a = data.a
            b = data.b

            if (
                a is None
                or b is None
            ):
                bracket = (
                    find_sign_change_interval(
                        data.equation
                    )
                )

                if not bracket:
                    return {
                        "success": False,
                        "method": "itp",
                        "error": (
                            "ITP requires a valid "
                            "sign-change interval and "
                            "no interval could be found "
                            "automatically"
                        ),
                    }

                a, b = bracket

                auto_parameters = {
                    "a": a,
                    "b": b,
                }

            result = (
                itp_method(
                    data.equation,
                    a,
                    b,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "newton":
            auto_parameters = {}

            x0 = data.x0

            if x0 is None:
                x0 = (
                    find_best_initial_guess(
                        data.equation
                    )
                )

                auto_parameters = {
                    "x0": x0
                }

            result = (
                newton_method(
                    data.equation,
                    x0,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "secant":
            auto_parameters = {}

            x0 = data.x0
            x1 = data.x1

            if (
                x0 is None
                or x1 is None
            ):
                x0, x1 = (
                    find_secant_initial_guesses(
                        data.equation
                    )
                )

                auto_parameters = {
                    "x0": x0,
                    "x1": x1,
                }

            result = (
                secant_method(
                    data.equation,
                    x0,
                    x1,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "muller":
            auto_parameters = {}

            x0 = getattr(
                data,
                "x0",
                None,
            )

            x1 = getattr(
                data,
                "x1",
                None,
            )

            x2 = getattr(
                data,
                "x2",
                None,
            )

            if (
                x0 is None
                or x1 is None
                or x2 is None
            ):
                x0, x1, x2 = (
                    find_muller_initial_guesses(
                        data.equation
                    )
                )

                auto_parameters = {
                    "x0": (
                        serialize_number(
                            x0
                        )
                    ),
                    "x1": (
                        serialize_number(
                            x1
                        )
                    ),
                    "x2": (
                        serialize_number(
                            x2
                        )
                    ),
                }

            result = (
                muller_method(
                    data.equation,
                    x0,
                    x1,
                    x2,
                )
            )

            return (
                add_auto_parameters_info(
                    result,
                    auto_parameters,
                )
            )


        if method == "roots":
            return (
                add_auto_parameters_info(
                    roots_method(
                        data.equation
                    ),
                    {},
                )
            )


        if method == "solve":
            return (
                add_auto_parameters_info(
                    symbolic_solve_method(
                        data.equation
                    ),
                    {},
                )
            )


        if (
            method
            == "integer_exhaustive_scan"
        ):
            return (
                add_auto_parameters_info(
                    integer_exhaustive_scan_method(
                        data.equation,
                        a=getattr(
                            data,
                            "a",
                            None,
                        ),
                        b=getattr(
                            data,
                            "b",
                            None,
                        ),
                    ),
                    {},
                )
            )


        return {
            "success": False,
            "method": method,
            "error": (
                "The selected method "
                "is not supported."
            ),
            "supported_methods": sorted(
                SUPPORTED_METHODS
            ),
        }

    except Exception:
        logger.exception(
            "Unexpected equation solver error."
        )

        return {
            "success": False,
            "method": method,
            "error": (
                "The equation could not be solved "
                "with the provided values."
            ),
        }