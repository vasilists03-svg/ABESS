from datetime import datetime
import math
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
import sympy as sp

from app.api_keys import hash_api_key
from app.database import get_db
from app.models.guest_usage import GuestUsage
from app.models.solve_history import SolveHistory
from app.models.user import User
from app.schemas.equation import EquationSolveRequest
from app.schemas.raison import RaisonRequest
from app.security import decode_access_token
from app.services.equation_solver import (
    make_function,
    prepare_expression,
    solve_equation,
)
from app.services.raison_service import call_raison


router = APIRouter(prefix="/equation", tags=["Equation"])
logger = logging.getLogger(__name__)

GUEST_SOLVE_LIMIT = int(os.getenv("GUEST_SOLVE_LIMIT", "3"))


class GraphRequest(BaseModel):
    equation: str
    x_min: float = -10
    x_max: float = 10
    points: int = 200


RAISON_CRITERIA = {
    "no_context": {
        "label": "no context",
        "id": "OPT450268",
    },
    "seek_analytical_solution": {
        "label": "I seek analytical solution",
        "id": "OPT450218",
    },
    "function_is_polynomial": {
        "label": "function is polynomial",
        "id": "OPT450168",
    },
    "seek_complex_root": {
        "label": "I seek complex root",
        "id": "OPT450118",
    },
    "derivative_is_available": {
        "label": "derivative is available",
        "id": "OPT450068",
    },
    "good_initial_approximation": {
        "label": "I have a good initial approximation",
        "id": "OPT450018",
    },
    "integer_valued_threshold_problem": {
        "label": "integer valued threshold problem",
        "id": "OPT449968",
    },
    "opposite_signs_interval": {
        "label": "f(a) * f(b) < 0",
        "id": "OPT449918",
    },
    "continuous_extension_available": {
        "label": "continuous extension is available",
        "id": "OPT449868",
    },
    "length_interval_large": {
        "label": "length of [a,b] >> 1",
        "id": "OPT449818",
    },
    "steep_gradient_or_no_gradient_near_root": {
        "label": "steep gradient or no gradient near root",
        "id": "OPT449768",
    },
    "inflection_points_near_solution": {
        "label": "inflection points near solution",
        "id": "OPT449718",
    },
    "extremum_points_near_solution": {
        "label": "extremum points near solution",
        "id": "OPT449668",
    },
    "function_behaves_smoothly_near_root": {
        "label": "function behaves smoothly near root",
        "id": "OPT449618",
    },
    "known_k_multiplicity_of_root": {
        "label": "known k-multiplicity of root",
        "id": "OPT449568",
    },
    "function_is_monotonic": {
        "label": "function is monotonic",
        "id": "OPT449518",
    },
    "need_simplicity": {
        "label": "I need simplicity",
        "id": "OPT449468",
    },
    "need_robustness": {
        "label": "I need robustness",
        "id": "OPT449418",
    },
    "need_speed": {
        "label": "I need speed",
        "id": "OPT449368",
    },
}


PRIMARY_CONTEXT_CRITERIA_KEYS = {
    "seek_analytical_solution",
    "function_is_polynomial",
    "seek_complex_root",
    "good_initial_approximation",
    "opposite_signs_interval",
    "integer_valued_threshold_problem",
}


RAISON_METHOD_MAP = {
    "binary search": "bisection",
    "bisection": "bisection",
    "bisection method": "bisection",

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
    "integer exhastive scan": "integer_exhaustive_scan",
    "integer exhaustive search": "integer_exhaustive_scan",
    "integer_exhaustive_scan": "integer_exhaustive_scan",
}


SUPPORTED_RAISON_METHODS = set(RAISON_METHOD_MAP.values())


METHOD_FULL_NAMES = {
    "bisection": "Bisection Method",
    "newton": "Newton-Raphson Method",
    "secant": "Secant Method",
    "fzero": "fzero",
    "itp": "ITP Method (Interpolate-Truncate-Project)",
    "muller": "Muller Method",
    "solve": "Symbolic Solve",
    "roots": "Polynomial Roots",
    "integer_exhaustive_scan": "Integer Exhaustive Scan",
}


def get_method_full_name(method):
    if method is None:
        return None

    normalized = str(method).strip().lower()

    return METHOD_FULL_NAMES.get(
        normalized,
        str(method),
    )


NO_CONTEXT_VALUE = (
    RAISON_CRITERIA["no_context"]
    .get("id", "")
    .strip()
    or RAISON_CRITERIA["no_context"]["label"]
)


PRIMARY_CONTEXT_VALUES = {
    (
        RAISON_CRITERIA[key]
        .get("id", "")
        .strip()
        or RAISON_CRITERIA[key]["label"]
    )
    for key in PRIMARY_CONTEXT_CRITERIA_KEYS
}


def get_optional_current_user(
    authorization: str | None,
    db: Session,
):
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    token = authorization.removeprefix(
        "Bearer "
    ).strip()

    if not token:
        return None

    try:
        payload = decode_access_token(
            token
        )

        if not payload:
            return None

        user_id = payload.get(
            "sub"
        )

        if user_id is None:
            return None

        user = (
            db.query(User)
            .filter(
                User.id == int(user_id)
            )
            .first()
        )

        if not user:
            return None

        if not getattr(
            user,
            "is_active",
            False,
        ):
            return None

        if not getattr(
            user,
            "is_verified",
            False,
        ):
            return None

        return user

    except (
        TypeError,
        ValueError,
    ):
        return None


def get_user_from_api_key(
    api_key: str | None,
    db: Session,
):
    """
    Resolve an authenticated user from the X-API-Key header.

    The plain API key is never written to logs or stored in plaintext.
    The incoming key is converted to the same HMAC-SHA256 digest used
    when the key was created, and only that digest is queried.
    """

    if api_key is None:
        return None

    normalized_key = str(api_key).strip()

    if (
        not normalized_key
        or len(normalized_key) > 512
        or not normalized_key.startswith("abess_sk_")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    try:
        api_key_digest = hash_api_key(
            normalized_key
        )

    except Exception:
        logger.exception(
            "API key validation could not be completed."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "API authentication is temporarily unavailable."
            ),
        )

    try:
        user = (
            db.query(User)
            .filter(
                User.api_key_hash
                == api_key_digest
            )
            .first()
        )

    except Exception:
        logger.exception(
            "Database error while validating an API key."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "API authentication is temporarily unavailable."
            ),
        )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    if not getattr(
        user,
        "is_active",
        False,
    ):
        raise HTTPException(
            status_code=403,
            detail="This account is inactive.",
        )

    if not getattr(
        user,
        "is_verified",
        False,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "This account must be verified "
                "before the API can be used."
            ),
        )

    return user


def resolve_solve_user(
    authorization: str | None,
    api_key: str | None,
    db: Session,
):
    """
    Resolve the identity used for a solve request.

    X-API-Key has explicit API-client semantics. If it is supplied,
    it must be valid and the request is classified as an API call.

    Without X-API-Key, the existing Bearer/JWT flow is preserved for
    the web application. Anonymous requests continue through the
    existing guest flow.
    """

    web_user = get_optional_current_user(
        authorization,
        db,
    )

    if api_key is None:
        return web_user, "WEB"

    api_user = get_user_from_api_key(
        api_key,
        db,
    )

    if (
        web_user is not None
        and web_user.id != api_user.id
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "The supplied authentication credentials "
                "do not belong to the same account."
            ),
        )

    return api_user, "API"


def get_required_current_user(
    authorization: str | None,
    db: Session,
):
    current_user = (
        get_optional_current_user(
            authorization,
            db,
        )
    )

    if current_user is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "You must be logged in "
                "to view your solve history."
            ),
        )

    return current_user


def get_required_admin_user(
    authorization: str | None,
    db: Session,
):
    current_user = (
        get_required_current_user(
            authorization,
            db,
        )
    )

    if (
        getattr(
            current_user,
            "role",
            None,
        )
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Administrator access "
                "is required."
            ),
        )

    return current_user


def check_and_update_guest_usage(
    data: EquationSolveRequest,
    db: Session,
):
    if not data.guest_id:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "error": "GUEST_ID_REQUIRED",
                "message": (
                    "Log in or continue as a guest "
                    "to use the application."
                ),
            },
        )

    guest = (
        db.query(GuestUsage)
        .filter(
            GuestUsage.guest_id
            == data.guest_id
        )
        .first()
    )

    if not guest:
        guest = GuestUsage(
            guest_id=data.guest_id,
            solve_count=0,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow(),
        )

        db.add(guest)
        db.commit()
        db.refresh(guest)

    if (
        guest.solve_count
        >= GUEST_SOLVE_LIMIT
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "success": False,
                "error": "GUEST_LIMIT_REACHED",
                "message": (
                    f"You have reached the limit of "
                    f"{GUEST_SOLVE_LIMIT} free solves. "
                    "Log in to continue."
                ),
            },
        )

    guest.solve_count += 1
    guest.last_used_at = (
        datetime.utcnow()
    )

    db.commit()
    db.refresh(guest)

    return guest


def add_user_usage_info(
    result,
    current_user,
    guest_usage,
    request_source="WEB",
):
    if not isinstance(
        result,
        dict,
    ):
        return result

    result[
        "request_source"
    ] = request_source

    if current_user:
        result[
            "user_type"
        ] = "registered"

        result[
            "user_email"
        ] = current_user.email

        result[
            "guest_solves_remaining"
        ] = None

        return result

    result[
        "user_type"
    ] = "guest"

    if guest_usage is None:
        result[
            "guest_solves_used"
        ] = None

        result[
            "guest_solves_remaining"
        ] = None

        return result

    result[
        "guest_solves_used"
    ] = guest_usage.solve_count

    result[
        "guest_solves_remaining"
    ] = max(
        GUEST_SOLVE_LIMIT
        - guest_usage.solve_count,
        0,
    )

    return result


def get_no_context_suggestion():
    return (
        "rAIson also tried its general "
        "no-context selection, but no suitable "
        "method was returned. Provide more "
        "information about the equation or "
        "select an implemented rAIson method manually."
    )


def get_criterion_value(
    criterion_key
):
    criterion_data = (
        RAISON_CRITERIA.get(
            criterion_key
        )
    )

    if criterion_data is None:
        return None

    criterion_id = (
        criterion_data
        .get("id", "")
        .strip()
    )

    if criterion_id:
        return criterion_id

    return criterion_data.get(
        "label"
    )


def normalize_criterion(
    criterion
):
    if criterion is None:
        return None

    criterion_text = str(
        criterion
    ).strip()

    if not criterion_text:
        return None

    if (
        criterion_text
        in RAISON_CRITERIA
    ):
        return get_criterion_value(
            criterion_text
        )

    for (
        criterion_key,
        criterion_data,
    ) in RAISON_CRITERIA.items():

        label = (
            criterion_data.get(
                "label",
                "",
            )
        )

        criterion_id = (
            criterion_data
            .get("id", "")
            .strip()
        )

        if (
            criterion_id
            and criterion_text
            == criterion_id
        ):
            return criterion_id

        if (
            criterion_text.lower()
            == label.lower()
        ):
            return get_criterion_value(
                criterion_key
            )

    return None


def add_selected_criterion(
    selected_elements,
    criterion,
    allow_no_context=False,
):
    normalized = (
        normalize_criterion(
            criterion
        )
    )

    if not normalized:
        return

    if (
        normalized
        == NO_CONTEXT_VALUE
        and not allow_no_context
    ):
        return

    if (
        normalized
        not in selected_elements
    ):
        selected_elements.append(
            normalized
        )


def normalize_raison_method(
    method_label
):
    if method_label is None:
        return None

    normalized_label = str(
        method_label
    ).lower().strip()

    return RAISON_METHOD_MAP.get(
        normalized_label
    )


def should_use_raison(
    method
):
    if method is None:
        return True

    normalized_method = str(
        method
    ).lower().strip()

    return normalized_method in {
        "",
        "automatic",
        "automatic / raison",
        "raison",
        "auto",
        "ai",
    }


def get_selected_criteria(
    data
):
    selected_elements = []

    criteria = getattr(
        data,
        "criteria",
        None,
    )

    if criteria:
        for criterion in criteria:
            add_selected_criterion(
                selected_elements,
                criterion,
            )

        return selected_elements

    selected_values = getattr(
        data,
        "selected_elements",
        None,
    )

    if selected_values:
        for criterion in selected_values:
            add_selected_criterion(
                selected_elements,
                criterion,
            )

        return selected_elements

    for criterion_key in RAISON_CRITERIA:
        if (
            criterion_key
            == "no_context"
        ):
            continue

        if getattr(
            data,
            criterion_key,
            False,
        ):
            add_selected_criterion(
                selected_elements,
                criterion_key,
            )

    return selected_elements


def has_primary_context_criterion(
    selected_elements
):
    return any(
        criterion
        in PRIMARY_CONTEXT_VALUES
        for criterion
        in selected_elements
    )


def prepare_raison_criteria(
    selected_elements
):
    effective_criteria = [
        criterion
        for criterion
        in selected_elements
        if criterion
        != NO_CONTEXT_VALUE
    ]

    automatic_no_context_added = (
        False
    )

    if not has_primary_context_criterion(
        effective_criteria
    ):
        effective_criteria.append(
            NO_CONTEXT_VALUE
        )

        automatic_no_context_added = (
            True
        )

    return (
        effective_criteria,
        automatic_no_context_added,
    )


def get_raison_solutions(
    raison_result
):
    if not isinstance(
        raison_result,
        dict,
    ):
        return []

    solutions = raison_result.get(
        "solutions",
        [],
    )

    if not isinstance(
        solutions,
        list,
    ):
        return []

    return solutions


def get_supported_method_from_solution(
    solution
):
    if not isinstance(
        solution,
        dict,
    ):
        return None

    normalized_method = (
        solution.get(
            "normalized_method"
        )
    )

    if (
        normalized_method
        in SUPPORTED_RAISON_METHODS
    ):
        return normalized_method

    normalized_method = (
        normalize_raison_method(
            solution.get(
                "label"
            )
        )
    )

    if (
        normalized_method
        in SUPPORTED_RAISON_METHODS
    ):
        return normalized_method

    return None


def get_supported_raison_solution(
    raison_result
):
    for solution in get_raison_solutions(
        raison_result
    ):
        method = (
            get_supported_method_from_solution(
                solution
            )
        )

        if not method:
            continue

        normalized_solution = dict(
            solution
        )

        normalized_solution[
            "normalized_method"
        ] = method

        return normalized_solution

    return None


def get_first_raison_solution(
    raison_result
):
    for solution in get_raison_solutions(
        raison_result
    ):
        if isinstance(
            solution,
            dict,
        ):
            return solution

    return None


def normalize_raison_explanation(
    explanation
):
    """
    Convert the explanation returned by rAIson into clean
    user-facing text while preserving the actual rAIson reasoning.
    """

    if explanation is None:
        return None

    if isinstance(
        explanation,
        str,
    ):
        clean_text = explanation.strip()

        if not clean_text:
            return None

        # Match the capitalization of the live rAIson criteria.
        clean_text = clean_text.replace(
            "i have a good initial approximation",
            "I have a good initial approximation",
        )

        clean_text = clean_text.replace(
            "i seek complex root",
            "I seek complex root",
        )

        clean_text = clean_text.replace(
            "i seek analytical solution",
            "I seek analytical solution",
        )

        # "no context" is an internal fallback criterion and
        # should not be exposed to the user.
        clean_text = clean_text.replace(
            " because no context",
            "",
        )

        clean_text = clean_text.strip()

        return clean_text or None

    if isinstance(
        explanation,
        (
            list,
            tuple,
            set,
        ),
    ):
        parts = []

        for item in explanation:
            normalized_item = (
                normalize_raison_explanation(
                    item
                )
            )

            if (
                normalized_item
                and normalized_item
                not in parts
            ):
                parts.append(
                    normalized_item
                )

        if not parts:
            return None

        return " ".join(parts)

    if isinstance(
        explanation,
        dict,
    ):
        parts = []

        for key in (
            "text",
            "message",
            "statement",
            "reason",
            "description",
            "explanation",
        ):
            if key not in explanation:
                continue

            normalized_item = (
                normalize_raison_explanation(
                    explanation.get(key)
                )
            )

            if (
                normalized_item
                and normalized_item
                not in parts
            ):
                parts.append(
                    normalized_item
                )

        if not parts:
            return None

        return " ".join(parts)

    return None


def build_raison_suggestion_text(
    raison_method,
    raison_explanation,
):
    """
    Build the exact user-facing rAIson line used by the frontend.

    Example:
    rAIson suggested: Symbolic Solve, solve is a solution because
    I seek analytical solution
    """

    method_name = get_method_full_name(
        raison_method
    )

    if not method_name:
        return None

    suggestion_text = (
        f"rAIson suggested: {method_name}"
    )

    if raison_explanation:
        suggestion_text += (
            f", {raison_explanation}"
        )

    return suggestion_text


def get_history_result_value(
    result
):
    """
    Return the meaningful solver output for history storage.

    Numerical methods usually expose ``root`` while symbolic and
    polynomial methods may expose a collection such as ``roots`` or
    ``solutions``.
    """

    if not isinstance(
        result,
        dict,
    ):
        return ""

    for key in (
        "root",
        "roots",
        "solutions",
        "solution",
        "result",
        "value",
    ):
        value = result.get(key)

        if (
            value is not None
            and value != ""
        ):
            return str(value)

    return ""


def persist_solve_history(
    db,
    data,
    current_user,
    request_source,
    result,
    *,
    used_raison,
    selection_source,
    raison_method=None,
    raison_explanation=None,
):
    """
    Persist every solve attempt that reached the solver route.

    Both successful and failed attempts are stored. A database-history
    failure is logged but does not replace the actual solver response.
    """

    if not isinstance(
        result,
        dict,
    ):
        return

    success = bool(
        result.get(
            "success"
        )
    )

    stored_method = (
        result.get(
            "method"
        )
        or result.get(
            "final_method"
        )
        or raison_method
        or getattr(
            data,
            "method",
            None,
        )
        or "unknown"
    )

    error_code = None
    error_message = None

    if not success:
        raw_error_code = (
            result.get(
                "error"
            )
            or "SOLVE_FAILED"
        )

        error_code = str(
            raw_error_code
        )

        raw_error_message = (
            result.get(
                "message"
            )
            or result.get(
                "title"
            )
            or raw_error_code
        )

        error_message = str(
            raw_error_message
        )

    history_entry = SolveHistory(
        user_id=(
            current_user.id
            if current_user
            else None
        ),
        guest_id=(
            getattr(
                data,
                "guest_id",
                None,
            )
            if current_user
            is None
            else None
        ),
        equation=str(
            getattr(
                data,
                "equation",
                "",
            )
            or ""
        ),
        method=str(
            stored_method
        ),
        result=(
            get_history_result_value(
                result
            )
            if success
            else ""
        ),
        iterations=(
            result.get(
                "iterations"
            )
        ),
        success=success,
        error_code=error_code,
        error_message=error_message,
        used_raison=bool(
            used_raison
        ),
        selection_source=(
            selection_source
            or "unknown"
        ),
        request_source=(
            request_source
            or "WEB"
        ),
        raison_method=(
            str(
                raison_method
            )
            if raison_method
            else None
        ),
        raison_explanation=(
            raison_explanation
            or None
        ),
    )

    try:
        db.add(
            history_entry
        )

        db.commit()

        db.refresh(
            history_entry
        )

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to persist solve history."
        )


def attach_solve_metadata(
    result,
    *,
    raison_method,
    raison_label,
    raison_explanation,
    fallback_used,
    automatic_no_context_added,
    raison_no_context_fallback_used,
    used_raison,
    selection_source,
):
    if not isinstance(
        result,
        dict,
    ):
        return result

    result[
        "raison_method"
    ] = raison_method

    result[
        "raison_label"
    ] = raison_label

    result[
        "raison_explanation"
    ] = raison_explanation

    result[
        "raison_suggestion"
    ] = build_raison_suggestion_text(
        raison_method,
        raison_explanation,
    )

    result[
        "final_method"
    ] = (
        result.get(
            "method"
        )
        or result.get(
            "final_method"
        )
        or raison_method
    )

    result[
        "raison_method_full_name"
    ] = get_method_full_name(
        raison_method
    )

    result[
        "python_method_full_name"
    ] = get_method_full_name(
        result.get(
            "final_method"
        )
    )

    result[
        "fallback_used"
    ] = fallback_used

    result[
        "automatic_no_context_added"
    ] = automatic_no_context_added

    result[
        "raison_no_context_fallback_used"
    ] = (
        raison_no_context_fallback_used
    )

    result[
        "used_raison"
    ] = used_raison

    result[
        "selection_source"
    ] = selection_source

    return result


def raison_returned_supported_method(
    raison_result
):
    return (
        get_supported_raison_solution(
            raison_result
        )
        is not None
    )


def call_raison_with_no_context_fallback(
    selected_elements
):
    (
        effective_criteria,
        automatic_no_context_added,
    ) = prepare_raison_criteria(
        selected_elements
    )

    logger.debug(
        "rAIson user criteria: %s",
        selected_elements,
    )

    logger.debug(
        "rAIson effective criteria: %s",
        effective_criteria,
    )

    raison_result = call_raison(
        effective_criteria
    )

    criteria_used = list(
        effective_criteria
    )

    no_context_fallback_used = (
        False
    )

    if (
        not raison_returned_supported_method(
            raison_result
        )
        and effective_criteria
        != [NO_CONTEXT_VALUE]
    ):
        logger.info(
            "rAIson returned no supported "
            "method; retrying once with "
            "the internal no-context fallback."
        )

        raison_result = call_raison([
            NO_CONTEXT_VALUE
        ])

        criteria_used = [
            NO_CONTEXT_VALUE
        ]

        no_context_fallback_used = (
            True
        )

    return {
        "result": raison_result,
        "criteria_used": criteria_used,
        "automatic_no_context_added": (
            automatic_no_context_added
        ),
        "no_context_fallback_used": (
            no_context_fallback_used
        ),
    }


def friendly_raison_error(
    error_text
):
    error_text_lower = str(
        error_text
    ).lower()

    if (
        "timeout"
        in error_text_lower
        or "timed out"
        in error_text_lower
    ):
        return (
            "Automatic method selection took "
            "too long to respond. Try again "
            "or select a method manually."
        )

    if (
        "401"
        in error_text_lower
        or "403"
        in error_text_lower
    ):
        return (
            "Automatic method selection is "
            "temporarily unavailable. You can "
            "continue by selecting a method manually."
        )

    if (
        "404"
        in error_text_lower
    ):
        return (
            "The automatic method-selection "
            "service is currently unavailable. "
            "Try again later or select a method manually."
        )

    if (
        "criterion"
        in error_text_lower
        or "criteria"
        in error_text_lower
    ):
        return (
            "One or more selected criteria "
            "were not recognized. Review the "
            "criteria and try again."
        )

    return (
        "Automatic method selection could "
        "not be completed. Try again or "
        "select a method manually."
    )


def build_raison_failure_response(
    message,
    suggestion,
    selected_elements,
    automatic_no_context_added,
    raison_no_context_fallback_used,
    *,
    title=(
        "Automatic method selection "
        "could not be completed."
    ),
    error="RAISON_SELECTION_FAILED",
):
    return {
        "success": False,
        "error": error,
        "title": title,
        "message": message,
        "suggestion": suggestion,
        "selected_criteria": (
            selected_elements
        ),
        "automatic_no_context_added": (
            automatic_no_context_added
        ),
        "raison_no_context_fallback_used": (
            raison_no_context_fallback_used
        ),
    }


def criterion_is_selected(
    selected_elements,
    criterion_key,
):
    criterion_value = (
        get_criterion_value(
            criterion_key
        )
    )

    return bool(
        criterion_value
        and criterion_value
        in selected_elements
    )


def validate_equation_input(
    equation_text
):
    if (
        equation_text is None
        or not str(
            equation_text
        ).strip()
    ):
        return {
            "success": False,
            "error": "EQUATION_REQUIRED",
            "title": (
                "No equation was entered."
            ),
            "message": (
                "Enter an equation before "
                "pressing Solve."
            ),
            "suggestion": (
                "Enter an equation using x "
                "as the free unknown, then try again."
            ),
        }

    try:
        prepare_expression(
            equation_text
        )

        return None

    except Exception as error:
        error_text = str(
            error
        ).lower()

        if (
            "only the free variable x"
            in error_text
            or "only the variable x"
            in error_text
            or "unsupported free symbols"
            in error_text
        ):
            return {
                "success": False,
                "error": (
                    "UNSUPPORTED_VARIABLE"
                ),
                "title": (
                    "Unsupported variable detected."
                ),
                "message": (
                    "The free unknown of the equation "
                    "must be x. Bound variables may "
                    "still be used inside constructs "
                    "such as definite integrals."
                ),
                "suggestion": (
                    "Rewrite the equation using x "
                    "as the free unknown."
                ),
            }

        if (
            "must contain the variable x"
            in error_text
        ):
            return {
                "success": False,
                "error": (
                    "VARIABLE_X_REQUIRED"
                ),
                "title": (
                    "The equation does not contain x."
                ),
                "message": (
                    "The equation must contain "
                    "the free variable x."
                ),
                "suggestion": (
                    "Enter an equation whose unknown "
                    "is x and try again."
                ),
            }

        if (
            "use only one '='"
            in error_text
        ):
            return {
                "success": False,
                "error": (
                    "MULTIPLE_EQUAL_SIGNS"
                ),
                "title": (
                    "The equation could not "
                    "be interpreted."
                ),
                "message": (
                    "Use only one '=' symbol "
                    "in the equation."
                ),
                "suggestion": (
                    "Rewrite the input as one "
                    "scalar equation, for example "
                    "x^2 - 4 = 0."
                ),
            }

        if (
            "both sides of the equation"
            in error_text
        ):
            return {
                "success": False,
                "error": (
                    "INCOMPLETE_EQUATION"
                ),
                "title": (
                    "The equation is incomplete."
                ),
                "message": (
                    "Enter an expression on both "
                    "sides of the '=' symbol."
                ),
                "suggestion": (
                    "Complete the equation "
                    "and try again."
                ),
            }

        return {
            "success": False,
            "error": (
                "INVALID_EQUATION_SYNTAX"
            ),
            "title": (
                "The equation could not "
                "be interpreted."
            ),
            "message": (
                "The mathematical expression "
                "could not be parsed."
            ),
            "suggestion": (
                "Check the mathematical notation, "
                "function names and parentheses. "
                "Open Help to see the supported notation."
            ),
        }


def validate_selected_criteria(
    data,
    selected_elements,
):
    if not criterion_is_selected(
        selected_elements,
        "function_is_polynomial",
    ):
        return None

    try:
        x, expression = (
            prepare_expression(
                data.equation
            )
        )

        sp.Poly(
            expression,
            x,
        )

        is_polynomial = True

    except sp.PolynomialError:
        is_polynomial = False

    except Exception:
        return None

    if is_polynomial:
        return None

    return {
        "success": False,
        "error": (
            "CRITERION_MISMATCH"
        ),
        "title": (
            "The selected criterion "
            "does not match the equation."
        ),
        "message": (
            "'Function is polynomial' was "
            "selected, but the entered equation "
            "is not polynomial in x."
        ),
        "suggestion": (
            "Uncheck 'Function is polynomial' "
            "or enter a polynomial equation."
        ),
        "selected_criteria": (
            selected_elements
        ),
    }


def describe_provided_inputs(
    data,
    method=None,
):
    method_key = str(
        method
        or getattr(
            data,
            "method",
            None,
        )
        or ""
    ).strip().lower()

    if method_key in {
        "bisection",
        "fzero",
        "itp",
    }:
        return "interval"

    if method_key in {
        "newton",
        "newton-raphson",
        "newton_raphson",
    }:
        return "initial_value"

    if method_key == "secant":
        return "initial_values"

    if method_key == "integer_exhaustive_scan":
        return "integer_range"

    if method_key in {
        "muller",
        "solve",
        "roots",
    }:
        return "none"

    # Compatibility fallback for an unknown or legacy method.
    has_a = (
        getattr(
            data,
            "a",
            None,
        )
        is not None
    )

    has_b = (
        getattr(
            data,
            "b",
            None,
        )
        is not None
    )

    has_x0 = (
        getattr(
            data,
            "x0",
            None,
        )
        is not None
    )

    has_x1 = (
        getattr(
            data,
            "x1",
            None,
        )
        is not None
    )

    if (
        has_x0
        and has_x1
    ):
        return "initial_values"

    if has_x0:
        return "initial_value"

    if (
        has_a
        and has_b
    ):
        return "interval"

    return "none"


def build_generic_method_failure_message(
    data,
    method=None,
):
    input_kind = (
        describe_provided_inputs(
            data,
            method,
        )
    )

    if (
        input_kind
        == "interval"
    ):
        return (
            "The selected method could not "
            "solve the equation within the "
            "provided interval."
        )

    if (
        input_kind
        == "integer_range"
    ):
        return (
            "The selected method could not "
            "solve the equation within the "
            "provided integer search range."
        )

    if (
        input_kind
        == "initial_values"
    ):
        return (
            "The selected method could not "
            "solve the equation from the "
            "provided initial values."
        )

    if (
        input_kind
        == "initial_value"
    ):
        return (
            "The selected method could not "
            "solve the equation from the "
            "provided initial value."
        )

    return (
        "The selected method could "
        "not solve this equation."
    )


def make_solver_failure_response(
    result,
    data,
    *,
    use_raison,
    raison_method,
):
    raw_error = str(
        result.get(
            "error"
        )
        or ""
    ).strip()

    error_text = (
        raw_error.lower()
    )

    final_method = (
        result.get(
            "method"
        )
        or data.method
    )

    method_name = (
        get_method_full_name(
            final_method
        )
    )

    is_muller_method = (
        str(
            final_method or ""
        )
        .strip()
        .lower()
        in {
            "muller",
            "müller",
        }
    )

    title = (
        "Unable to solve the equation."
    )

    error_code = (
        "SOLVE_FAILED"
    )

    message = (
        build_generic_method_failure_message(
            data,
            final_method,
        )
    )

    suggestion = (
        "Check the equation and the inputs "
        "required by the selected method."
    )

    if (
        "not supported"
        in error_text
    ):
        title = (
            "The selected method "
            "is not supported."
        )

        error_code = (
            "METHOD_NOT_SUPPORTED"
        )

        message = (
            f"{method_name or 'The selected method'} "
            "is not available in the current "
            "solver configuration."
        )

        suggestion = (
            "Select one of the methods "
            "available in the Method menu."
        )

    elif (
        "only applicable to polynomial"
        in error_text
        or "not polynomial"
        in error_text
        or "equation is not polynomial"
        in error_text
    ):
        title = (
            "Polynomial Roots cannot be "
            "applied to this equation."
        )

        error_code = (
            "NON_POLYNOMIAL_EQUATION"
        )

        message = (
            "The entered equation is not "
            "polynomial in x, so Polynomial "
            "Roots cannot be used for this problem."
        )

        suggestion = (
            "Use a method suitable for a "
            "non-polynomial equation. In "
            "Automatic / rAIson mode, review "
            "the selected criteria."
        )

    elif (
        "no symbolic solution"
        in error_text
        or "symbolic solve failed"
        in error_text
        or "no analytical"
        in error_text
    ):
        title = (
            "No analytical solution was found."
        )

        error_code = (
            "NO_SYMBOLIC_SOLUTION"
        )

        message = (
            "The selected symbolic method did "
            "not obtain a closed-form solution "
            "for this equation."
        )

        suggestion = (
            "A numerical root-finding method "
            "may still be able to solve the equation."
        )

    elif (
        "could not automatically find interval"
        in error_text
    ):
        title = (
            "A suitable interval "
            "could not be found."
        )

        error_code = (
            "INTERVAL_NOT_FOUND"
        )

        message = (
            "The solver could not automatically "
            "find an [a,b] interval containing "
            "a sign change."
        )

        suggestion = (
            "Provide an interval where f(a) "
            "and f(b) have opposite signs, or "
            "use a method that does not require "
            "a sign-change bracket."
        )

    elif (
        "opposite signs"
        in error_text
        or "invalid interval"
        in error_text
        or "sign-change interval"
        in error_text
    ):
        title = (
            "The selected interval is "
            "not valid for this method."
        )

        error_code = (
            "INVALID_INTERVAL"
        )

        message = (
            "The interval does not provide "
            "the sign-change condition required "
            "by the selected method."
        )

        suggestion = (
            "Choose a and b so that f(a) "
            "and f(b) have opposite signs."
        )

    elif (
        "derivative is zero"
        in error_text
    ):
        title = (
            "Newton-Raphson could not continue."
        )

        error_code = (
            "DERIVATIVE_ZERO"
        )

        message = (
            "The derivative became zero or "
            "too close to zero at the current "
            "approximation."
        )

        suggestion = (
            "Try a different initial value x0, "
            "or select another method."
        )

    elif (
        "secant method requires different"
        in error_text
    ):
        title = (
            "The Secant Method requires "
            "two different starting values."
        )

        error_code = (
            "INVALID_INITIAL_VALUES"
        )

        message = (
            "x0 and x1 must be "
            "different values."
        )

        suggestion = (
            "Enter two different starting "
            "values and try again."
        )

    elif (
        "division by zero"
        in error_text
        or "zero denominator"
        in error_text
    ):
        title = (
            "The selected method "
            "could not continue."
        )

        error_code = (
            "ZERO_DENOMINATOR"
        )

        message = (
            "A zero or near-zero denominator "
            "occurred during the iteration."
        )

        if is_muller_method:
            suggestion = (
                "Muller starting points are selected "
                "automatically in this interface. "
                "Try another suitable method if the "
                "iteration cannot continue."
            )

        else:
            suggestion = (
                "Try different starting values "
                "or select another method."
            )

    elif (
        "three distinct starting points"
        in error_text
    ):
        title = (
            "Muller Method requires "
            "distinct starting points."
        )

        error_code = (
            "INVALID_INITIAL_VALUES"
        )

        message = (
            "The starting points used by "
            "Muller were not sufficiently distinct."
        )

        suggestion = (
            "Muller starting points are selected "
            "automatically in this interface. "
            "Try another suitable method if the "
            "automatically selected points are "
            "not appropriate for this equation."
        )

    elif (
        "could not be evaluated"
        in error_text
        or "non-finite"
        in error_text
        or "returned a complex value"
        in error_text
    ):
        title = (
            "The function could not be "
            "evaluated for the required values."
        )

        error_code = (
            "FUNCTION_EVALUATION_FAILED"
        )

        message = (
            "The selected method reached a "
            "value where the function is undefined, "
            "non-finite, or outside the real-valued "
            "domain required by that method."
        )

        if is_muller_method:
            suggestion = (
                "Check the equation domain or select "
                "another suitable method. Muller "
                "starting points are selected "
                "automatically in this interface."
            )

        else:
            suggestion = (
                "Check the equation domain and use "
                "different starting values or an "
                "appropriate method."
            )

    elif (
        "no integer root"
        in error_text
        or "threshold crossing"
        in error_text
    ):
        title = (
            "No integer solution was found "
            "in the search range."
        )

        error_code = (
            "INTEGER_SOLUTION_NOT_FOUND"
        )

        message = (
            "Integer Exhaustive Scan did not "
            "find an integer root or threshold "
            "crossing in the selected range."
        )

        suggestion = (
            "Use a wider integer range or verify "
            "that the problem has an integer "
            "solution or threshold crossing."
        )

    elif (
        "did not converge"
        in error_text
    ):
        title = (
            "The selected method did not converge."
        )

        error_code = (
            "NO_CONVERGENCE"
        )

        input_kind = (
            describe_provided_inputs(
                data,
                final_method,
            )
        )

        if (
            input_kind
            == "interval"
        ):
            message = (
                "The method did not converge "
                "to a valid root within the "
                "provided interval."
            )

        elif (
            input_kind
            == "integer_range"
        ):
            message = (
                "The method did not converge "
                "to a valid solution within the "
                "provided integer search range."
            )

        elif (
            input_kind
            == "initial_values"
        ):
            message = (
                "The method did not converge "
                "from the provided initial values."
            )

        elif (
            input_kind
            == "initial_value"
        ):
            message = (
                "The method did not converge "
                "from the provided initial value."
            )

        else:
            message = (
                "The method did not converge "
                "to a valid root."
            )

        suggestion = (
            "Review the equation and the method "
            "requirements. If a different method "
            "is needed, select it manually or let "
            "rAIson select it in Automatic mode."
        )

    response = dict(
        result
    )

    response[
        "success"
    ] = False

    response[
        "error"
    ] = error_code

    response[
        "title"
    ] = title

    response[
        "message"
    ] = message

    response[
        "suggestion"
    ] = suggestion

    for technical_key in (
        "traceback",
        "exception",
        "raw_error",
        "raw_response",
        "technical_details",
        "details",
        "debug",
    ):
        response.pop(
            technical_key,
            None,
        )

    return response


@router.post("/solve")
def solve_equation_route(
    data: EquationSolveRequest,
    db: Session = Depends(
        get_db
    ),
    authorization: str | None = Header(
        None
    ),
    x_api_key: str | None = Header(
        None,
        alias="X-API-Key",
    ),
):
    original_method = (
        data.method
    )

    (
        current_user,
        request_source,
    ) = resolve_solve_user(
        authorization,
        x_api_key,
        db,
    )

    guest_usage = None

    if current_user is None:
        guest_usage = (
            check_and_update_guest_usage(
                data,
                db,
            )
        )

    use_raison = (
        should_use_raison(
            original_method
        )
    )

    selection_source = (
        "raison"
        if use_raison
        else "manual"
    )

    equation_validation = (
        validate_equation_input(
            data.equation
        )
    )

    if equation_validation:
        equation_validation[
            "used_raison"
        ] = use_raison

        equation_validation[
            "selection_source"
        ] = selection_source

        add_user_usage_info(
            equation_validation,
            current_user,
            guest_usage,
            request_source,
        )

        persist_solve_history(
            db,
            data,
            current_user,
            request_source,
            equation_validation,
            used_raison=use_raison,
            selection_source=(
                selection_source
            ),
        )

        return equation_validation

    raison_method = None
    raison_label = None
    raison_explanation = None

    fallback_used = False

    automatic_no_context_added = (
        False
    )

    raison_no_context_fallback_used = (
        False
    )

    user_note = None

    if use_raison:
        selected_elements = (
            get_selected_criteria(
                data
            )
        )

        criteria_validation = (
            validate_selected_criteria(
                data,
                selected_elements,
            )
        )

        if criteria_validation:
            criteria_validation[
                "used_raison"
            ] = True

            criteria_validation[
                "selection_source"
            ] = "raison"

            add_user_usage_info(
                criteria_validation,
                current_user,
                guest_usage,
                request_source,
            )

            persist_solve_history(
                db,
                data,
                current_user,
                request_source,
                criteria_validation,
                used_raison=True,
                selection_source="raison",
            )

            return criteria_validation

        try:
            logger.debug(
                "Starting rAIson "
                "method-selection flow."
            )

            raison_execution = (
                call_raison_with_no_context_fallback(
                    selected_elements
                )
            )

            raison_result = (
                raison_execution[
                    "result"
                ]
            )

            automatic_no_context_added = (
                raison_execution[
                    "automatic_no_context_added"
                ]
            )

            raison_no_context_fallback_used = (
                raison_execution[
                    "no_context_fallback_used"
                ]
            )

            logger.debug(
                "rAIson result received."
            )

            supported_solution = (
                get_supported_raison_solution(
                    raison_result
                )
            )

            if supported_solution:
                raison_label = (
                    supported_solution.get(
                        "label"
                    )
                )

                raison_method = (
                    supported_solution.get(
                        "normalized_method"
                    )
                )

                raison_explanation = (
                    normalize_raison_explanation(
                        supported_solution.get(
                            "explanation"
                        )
                    )
                )

                data.method = (
                    raison_method
                )

                if (
                    raison_no_context_fallback_used
                ):
                    user_note = (
                        "No supported method was found "
                        "with the initial criteria. The "
                        "application performed one automatic "
                        "general fallback attempt and selected "
                        f"{get_method_full_name(raison_method)}."
                    )

                elif (
                    automatic_no_context_added
                ):
                    user_note = (
                        "None of the six primary criteria "
                        "was selected. The application "
                        "automatically used the general "
                        "fallback criterion and selected "
                        f"{get_method_full_name(raison_method)}."
                    )

            else:
                raw_solution = (
                    get_first_raison_solution(
                        raison_result
                    )
                )

                raw_label = (
                    raw_solution.get(
                        "label"
                    )
                    if raw_solution
                    else None
                )

                raw_explanation = (
                    normalize_raison_explanation(
                        raw_solution.get(
                            "explanation"
                        )
                    )
                    if raw_solution
                    else None
                )

                if raw_label:
                    response = (
                        build_raison_failure_response(
                            message=(
                                "rAIson suggested "
                                f"'{raw_label}', but that "
                                "label is not mapped to an "
                                "implemented project method."
                            ),
                            suggestion=(
                                "Review the active rAIson "
                                "policy or method mapping. "
                                "The backend will not substitute "
                                "a different solver."
                            ),
                            selected_elements=(
                                selected_elements
                            ),
                            automatic_no_context_added=(
                                automatic_no_context_added
                            ),
                            raison_no_context_fallback_used=(
                                raison_no_context_fallback_used
                            ),
                        )
                    )

                    response[
                        "raison_method"
                    ] = raw_label

                    response[
                        "raison_explanation"
                    ] = raw_explanation

                    response[
                        "raison_suggestion"
                    ] = (
                        build_raison_suggestion_text(
                            raw_label,
                            raw_explanation,
                        )
                    )

                    response[
                        "used_raison"
                    ] = True

                    response[
                        "selection_source"
                    ] = "raison"

                    response[
                        "supported_methods"
                    ] = sorted(
                        SUPPORTED_RAISON_METHODS
                    )

                    add_user_usage_info(
                        response,
                        current_user,
                        guest_usage,
                        request_source,
                    )

                    persist_solve_history(
                        db,
                        data,
                        current_user,
                        request_source,
                        response,
                        used_raison=True,
                        selection_source="raison",
                        raison_method=(
                            raw_label
                        ),
                        raison_explanation=(
                            raw_explanation
                        ),
                    )

                    return response

                response = (
                    build_raison_failure_response(
                        message=(
                            "rAIson could not suggest "
                            "a supported method."
                        ),
                        suggestion=(
                            get_no_context_suggestion()
                        ),
                        selected_elements=(
                            selected_elements
                        ),
                        automatic_no_context_added=(
                            automatic_no_context_added
                        ),
                        raison_no_context_fallback_used=(
                            raison_no_context_fallback_used
                        ),
                    )
                )

                response[
                    "used_raison"
                ] = True

                response[
                    "selection_source"
                ] = "raison"

                add_user_usage_info(
                    response,
                    current_user,
                    guest_usage,
                    request_source,
                )

                persist_solve_history(
                    db,
                    data,
                    current_user,
                    request_source,
                    response,
                    used_raison=True,
                    selection_source="raison",
                )

                return response

        except Exception as error:
            logger.exception(
                "rAIson method-selection failed."
            )

            response = (
                build_raison_failure_response(
                    message=(
                        friendly_raison_error(
                            str(error)
                        )
                    ),
                    suggestion=(
                        "Try again or manually select "
                        "one of the implemented rAIson "
                        "methods: Bisection, Newton-Raphson, "
                        "Secant, fzero, ITP, Muller, solve, "
                        "roots, or integer exhaustive scan."
                    ),
                    selected_elements=(
                        selected_elements
                    ),
                    automatic_no_context_added=(
                        automatic_no_context_added
                    ),
                    raison_no_context_fallback_used=(
                        raison_no_context_fallback_used
                    ),
                )
            )

            response[
                "used_raison"
            ] = True

            response[
                "selection_source"
            ] = "raison"

            add_user_usage_info(
                response,
                current_user,
                guest_usage,
                request_source,
            )

            persist_solve_history(
                db,
                data,
                current_user,
                request_source,
                response,
                used_raison=True,
                selection_source="raison",
            )

            return response

    try:
        result = solve_equation(
            data
        )

    except Exception:
        logger.exception(
            "Equation solver failed "
            "unexpectedly for method %s.",
            data.method,
        )

        result = {
            "success": False,
            "error": (
                "Unexpected solver error"
            ),
        }

    if not isinstance(
        result,
        dict,
    ):
        logger.error(
            "Equation solver returned "
            "a non-dictionary response."
        )

        result = {
            "success": False,
            "error": (
                "Unexpected solver response"
            ),
        }

    if not result.get(
        "success"
    ):
        raw_error = str(
            result.get(
                "error",
                "",
            )
        )

        if raw_error:
            logger.warning(
                "Equation solve failed "
                "for method %s: %s",
                data.method,
                raw_error,
            )

        result = (
            make_solver_failure_response(
                result,
                data,
                use_raison=(
                    use_raison
                ),
                raison_method=(
                    raison_method
                ),
            )
        )

    attach_solve_metadata(
        result,
        raison_method=(
            raison_method
        ),
        raison_label=(
            raison_label
        ),
        raison_explanation=(
            raison_explanation
        ),
        fallback_used=(
            fallback_used
        ),
        automatic_no_context_added=(
            automatic_no_context_added
        ),
        raison_no_context_fallback_used=(
            raison_no_context_fallback_used
        ),
        used_raison=(
            use_raison
        ),
        selection_source=(
            selection_source
        ),
    )

    if user_note:
        result[
            "note"
        ] = user_note

    add_user_usage_info(
        result,
        current_user,
        guest_usage,
        request_source,
    )

    persist_solve_history(
        db,
        data,
        current_user,
        request_source,
        result,
        used_raison=(
            use_raison
        ),
        selection_source=(
            selection_source
        ),
        raison_method=(
            raison_method
        ),
        raison_explanation=(
            raison_explanation
        ),
    )

    return result


def prepare_graph_expression(
    equation_text
):
    return prepare_expression(
        equation_text
    )


@router.post("/graph")
def generate_graph(
    data: GraphRequest
):
    try:
        if data.points <= 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Points must be "
                    "greater than 0"
                ),
            )

        if data.points > 5000:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Points cannot be "
                    "greater than 5000"
                ),
            )

        if (
            data.x_min
            >= data.x_max
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "x_min must be smaller "
                    "than x_max"
                ),
            )

        function = make_function(
            data.equation
        )

        step = (
            data.x_max
            - data.x_min
        ) / data.points

        graph_points = []

        # Preserve numerical precision and discontinuities.
        for index in range(data.points + 1):
            x_value = data.x_min + index * step
            graph_y = None

            try:
                calculated_y = function(x_value)

                if hasattr(calculated_y, "item"):
                    calculated_y = calculated_y.item()

                if isinstance(calculated_y, complex):
                    if abs(calculated_y.imag) <= 1e-12:
                        calculated_y = calculated_y.real
                    else:
                        calculated_y = None

                if calculated_y is not None:
                    numerical_y = float(calculated_y)

                    if math.isfinite(numerical_y):
                        graph_y = numerical_y

            except Exception:
                # Leave a gap for undefined sample values.
                pass

            graph_points.append({
                "x": float(x_value),
                "y": graph_y,
            })

        return {
            "success": True,
            "equation": (
                data.equation
            ),
            "points": (
                graph_points
            ),
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.exception(
            "Graph generation failed."
        )

        error_text = str(
            error
        ).lower()

        if (
            "equation is required"
            in error_text
        ):
            detail = (
                "Enter an equation before "
                "drawing the graph."
            )

        elif (
            "only the variable x"
            in error_text
            or "only the free variable x"
            in error_text
        ):
            detail = (
                "The graph supports equations "
                "using only the free variable x."
            )

        elif (
            "must contain the variable x"
            in error_text
        ):
            detail = (
                "The equation must contain "
                "the variable x."
            )

        elif (
            "use only one '='"
            in error_text
        ):
            detail = (
                "Use only one '=' symbol "
                "in the equation."
            )

        elif (
            "both sides of the equation"
            in error_text
        ):
            detail = (
                "Enter an expression on both "
                "sides of the '=' symbol."
            )

        else:
            detail = (
                "The graph could not be "
                "generated from the entered equation."
            )

        raise HTTPException(
            status_code=400,
            detail=detail,
        ) from error


@router.get("/history")
def get_history(
    db: Session = Depends(
        get_db
    ),
    authorization: str | None = Header(
        None
    ),
):
    get_required_admin_user(
        authorization,
        db,
    )

    return (
        db.query(
            SolveHistory
        )
        .order_by(
            SolveHistory.id.desc()
        )
        .all()
    )


@router.get("/my-history")
def get_my_history(
    db: Session = Depends(
        get_db
    ),
    credentials: (
        HTTPAuthorizationCredentials
        | None
    ) = Depends(
        HTTPBearer(
            auto_error=False
        )
    ),
):
    authorization = (
        f"Bearer {credentials.credentials}"
        if credentials
        else None
    )

    current_user = (
        get_required_current_user(
            authorization,
            db,
        )
    )

    history = (
        db.query(
            SolveHistory
        )
        .filter(
            SolveHistory.user_id
            == current_user.id
        )
        .order_by(
            SolveHistory.id.desc()
        )
        .all()
    )

    return {
        "success": True,
        "user_id": (
            current_user.id
        ),
        "email": (
            current_user.email
        ),
        "history": history,
    }


@router.post("/raison")
def get_raison_solution(
    data: RaisonRequest
):
    selected_elements = []

    if hasattr(
        data,
        "model_dump",
    ):
        request_values = (
            data.model_dump()
        )

    else:
        request_values = (
            data.dict()
        )

    for (
        key,
        value,
    ) in request_values.items():

        if value:
            add_selected_criterion(
                selected_elements,
                key,
            )

    try:
        raison_execution = (
            call_raison_with_no_context_fallback(
                selected_elements
            )
        )

        result = (
            raison_execution[
                "result"
            ]
        )

        if not isinstance(
            result,
            dict,
        ):
            result = {
                "success": False,
                "message": (
                    "rAIson returned an "
                    "unexpected response."
                ),
            }

        for technical_key in (
            "raw_response",
            "traceback",
            "exception",
            "raw_error",
            "technical_details",
            "details",
            "debug",
        ):
            result.pop(
                technical_key,
                None,
            )

        if (
            result.get(
                "success"
            )
            is False
        ):
            raw_error = str(
                result.get(
                    "error"
                )
                or result.get(
                    "message"
                )
                or ""
            )

            if raw_error:
                logger.warning(
                    "rAIson returned a "
                    "failure response: %s",
                    raw_error,
                )

            result[
                "error"
            ] = (
                "RAISON_UNAVAILABLE"
            )

            result[
                "title"
            ] = (
                "Automatic method selection "
                "could not be completed."
            )

            result[
                "message"
            ] = (
                friendly_raison_error(
                    raw_error
                )
            )

            result[
                "suggestion"
            ] = (
                get_no_context_suggestion()
            )

        supported_solution = (
            get_supported_raison_solution(
                result
            )
        )

        if supported_solution:
            result[
                "final_method"
            ] = (
                supported_solution.get(
                    "normalized_method"
                )
            )

        else:
            result[
                "final_method"
            ] = None

        result[
            "automatic_no_context_added"
        ] = (
            raison_execution[
                "automatic_no_context_added"
            ]
        )

        result[
            "raison_no_context_fallback_used"
        ] = (
            raison_execution[
                "no_context_fallback_used"
            ]
        )

        return result

    except Exception as error:
        logger.exception(
            "rAIson endpoint failed."
        )

        return {
            "success": False,
            "error": (
                "RAISON_UNAVAILABLE"
            ),
            "title": (
                "Automatic method selection "
                "could not be completed."
            ),
            "message": (
                friendly_raison_error(
                    str(error)
                )
            ),
            "suggestion": (
                get_no_context_suggestion()
            ),
            "selected_criteria": (
                selected_elements
            ),
        }