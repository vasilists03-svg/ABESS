import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.guest_usage import GuestUsage
from app.models.solve_history import SolveHistory
from app.models.user import User
from app.security import decode_access_token


load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
        )

    token = (credentials.credentials or "").strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    try:
        payload = decode_access_token(token)
    except Exception:
        logger.exception(
            "Unexpected error while decoding an admin token."
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    user_id = payload.get("sub")

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

    except SQLAlchemyError:
        logger.exception(
            "Database error while loading the admin user."
        )

        raise HTTPException(
            status_code=500,
            detail="The server could not process the request.",
        )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account is inactive.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before continuing.",
        )

    configured_admin_email = os.getenv(
        "ADMIN_EMAIL",
        "",
    ).strip().lower()

    user_email = (
        user.email or ""
    ).strip().lower()

    user_role = (
        user.role or ""
    ).strip().lower()

    is_admin_by_role = (
        user_role == "admin"
    )

    is_admin_by_email = (
        bool(configured_admin_email)
        and user_email == configured_admin_email
    )

    if not (
        is_admin_by_role
        or is_admin_by_email
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You do not have permission to access "
                "the Admin Dashboard."
            ),
        )

    return user


def database_failure(log_message):
    logger.exception(log_message)

    raise HTTPException(
        status_code=500,
        detail="The server could not process the request.",
    )


@router.get("/me")
def admin_me(
    current_admin: User = Depends(get_current_admin),
):
    return {
        "success": True,
        "is_admin": True,
        "id": current_admin.id,
        "email": current_admin.email,
        "role": current_admin.role,
    }


@router.get(
    "/manual-content",
    response_class=HTMLResponse,
)
def admin_manual_content(
    current_admin: User = Depends(get_current_admin),
):
    # Dependency above guarantees that only an authenticated
    # administrator can retrieve the operations manual.
    _ = current_admin

    manual_path = (
        Path(__file__).resolve().parent.parent
        / "manual"
        / "admin_manual.html"
    )

    try:
        manual_html = manual_path.read_text(
            encoding="utf-8"
        )

    except OSError:
        logger.exception(
            "Administrator manual could not be loaded."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The administrator manual could not be loaded."
            ),
        )

    return HTMLResponse(
        content=manual_html,
        headers={
            "Cache-Control": "no-store, private",
        },
    )


# Reporting is deliberately separate from solver dispatch and stored history.
ADMIN_SUPPORTED_METHODS = (
    ("bisection", "Bisection"),
    ("newton", "Newton-Raphson"),
    ("secant", "Secant"),
    ("fzero", "fzero"),
    ("itp", "ITP"),
    ("muller", "Muller"),
    ("solve", "Symbolic Solve"),
    ("roots", "Polynomial Roots"),
    ("integer_exhaustive_scan", "Integer Exhaustive Scan"),
)

ADMIN_PRE_SELECTION_ERRORS = frozenset({
    "EQUATION_REQUIRED", "UNSUPPORTED_VARIABLE", "VARIABLE_X_REQUIRED",
    "MULTIPLE_EQUAL_SIGNS", "INCOMPLETE_EQUATION", "INVALID_EQUATION_SYNTAX",
    "CRITERION_MISMATCH",
})

ADMIN_SOLVER_STAGE_ERRORS = frozenset({
    "DERIVATIVE_ZERO", "FUNCTION_EVALUATION_FAILED", "INTEGER_SOLUTION_NOT_FOUND",
    "INTERVAL_NOT_FOUND", "INVALID_INITIAL_VALUES", "INVALID_INTERVAL",
    "NON_POLYNOMIAL_EQUATION", "NO_CONVERGENCE", "NO_SYMBOLIC_SOLUTION",
    "ZERO_DENOMINATOR",
})

ADMIN_AUTOMATIC_MODES = frozenset({
    "automatic", "automatic / raison", "raison", "auto", "ai",
})


def build_admin_method_statistics(history_records):
    """Count selection workflows separately from recorded solving attempts.

    A workflow corresponds to one /solve history row, including its internal
    no-context retry. /raison previews are not part of solve history. A solving
    attempt includes setup, not just iterations of a numerical routine.

    Existing records have no explicit stage flags. Recognized prevalidation and
    selection errors are never attributed to a solver. Ambiguous historical
    outcomes are accounted for separately, without guessing or rewriting them.
    """
    methods = {
        key: {"method": key, "label": label, "attempts": 0,
              "successful": 0, "failed": 0, "unknown_status": 0}
        for key, label in ADMIN_SUPPORTED_METHODS
    }
    selections = {
        key: {"method": key, "label": label, "attempts": 0,
              "successful": 0, "failed": 0}
        for key, label in ADMIN_SUPPORTED_METHODS
    }
    selection_summary = {
        "attempts": 0, "successful": 0, "failed": 0,
        "not_attempted": 0, "unclassified": 0,
    }
    method_summary = {
        "attempts": 0, "successful": 0, "failed": 0,
        "not_attempted": 0, "not_displayed": 0, "unclassified": 0,
    }

    for item in history_records:
        method = str(getattr(item, "method", "") or "").strip().lower()
        selected = str(getattr(item, "raison_method", "") or "").strip().lower()
        source = str(getattr(item, "selection_source", "") or "").strip().lower()
        error = str(getattr(item, "error_code", "") or "").strip().upper()
        success = getattr(item, "success", None)
        used_raison = getattr(item, "used_raison", False) is True
        raison_provenance = source == "raison" or used_raison
        prevalidation = error in ADMIN_PRE_SELECTION_ERRORS
        selection_failed = error == "RAISON_SELECTION_FAILED"
        raison_context = (
            raison_provenance or bool(selected) or method in ADMIN_AUTOMATIC_MODES
            or selection_failed
        )
        contradictory = (
            (success is True and (prevalidation or selection_failed))
            or (source == "manual" and raison_context)
        )
        selection_outcome = None

        if raison_context:
            if contradictory:
                selection_summary["unclassified"] += 1
            elif prevalidation:
                selection_summary["not_attempted"] += 1
            elif raison_provenance and selection_failed:
                selection_outcome = "failed"
            elif raison_provenance and selected in selections:
                selection_outcome = "successful"
                row = selections[selected]
                row["attempts"] += 1
                row["successful"] += 1
            else:
                selection_summary["unclassified"] += 1

        if selection_outcome is not None:
            selection_summary["attempts"] += 1
            selection_summary[selection_outcome] += 1

        # These branches terminate before solve_equation in the supplied router.
        if contradictory:
            method_summary["unclassified"] += 1
            continue
        if prevalidation or selection_failed:
            method_summary["not_attempted"] += 1
            continue
        if method not in methods:
            method_summary["not_displayed"] += 1
            continue

        outcome = None
        if success is True:
            outcome = "successful"
        elif success is False:
            if error in ADMIN_SOLVER_STAGE_ERRORS:
                outcome = "failed"
            elif error == "SOLVE_FAILED" and (
                source == "manual" or selection_outcome == "successful"
            ):
                # Current router emits this after dispatch; a legacy row with
                # no provenance does not establish that the solver was called.
                outcome = "failed"

        if outcome is None:
            method_summary["unclassified"] += 1
            continue

        methods[method]["attempts"] += 1
        methods[method][outcome] += 1
        method_summary["attempts"] += 1
        method_summary[outcome] += 1

    selection_rows = list(selections.values())
    if selection_summary["failed"]:
        selection_rows.append({
            "method": "no_method_selected",
            "label": "No supported method selected",
            "attempts": selection_summary["failed"],
            "successful": 0,
            "failed": selection_summary["failed"],
        })

    return {
        "method_usage": list(methods.values()),
        "method_usage_summary": method_summary,
        "raison_method_selection": selection_rows,
        "raison_selection_summary": selection_summary,
    }


@router.get("/stats")
def admin_stats(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        total_users = (
            db.query(User)
            .count()
        )

        active_users = (
            db.query(User)
            .filter(
                User.is_active.is_(True)
            )
            .count()
        )

        verified_users = (
            db.query(User)
            .filter(
                User.is_verified.is_(True)
            )
            .count()
        )

        total_attempts = (
            db.query(SolveHistory)
            .count()
        )

        successful_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.success.is_(True)
            )
            .count()
        )

        failed_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.success.is_(False)
            )
            .count()
        )

        unknown_status_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.success.is_(None)
            )
            .count()
        )

        manual_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.selection_source
                == "manual"
            )
            .count()
        )

        raison_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.selection_source
                == "raison"
            )
            .count()
        )

        legacy_fallback_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.selection_source
                == "automatic_fallback"
            )
            .count()
        )

        unknown_source_attempts = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.selection_source
                == "unknown"
            )
            .count()
        )

        web_requests = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.request_source
                == "WEB"
            )
            .count()
        )

        api_requests = (
            db.query(SolveHistory)
            .filter(
                SolveHistory.request_source
                == "API"
            )
            .count()
        )

        total_guest_records = (
            db.query(GuestUsage)
            .count()
        )

        guest_records = (
            db.query(GuestUsage)
            .all()
        )

        total_guest_solves = sum(
            guest.solve_count or 0
            for guest in guest_records
        )

        history_records = (
            db.query(SolveHistory)
            .all()
        )

        method_statistics = build_admin_method_statistics(history_records)
        method_usage = method_statistics["method_usage"]

    except SQLAlchemyError:
        database_failure(
            "Database error while loading admin statistics."
        )

    return {
        "success": True,
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,

            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "unknown_status_attempts": (
                unknown_status_attempts
            ),

            "manual_attempts": manual_attempts,
            "raison_attempts": raison_attempts,

            "web_requests": web_requests,
            "api_requests": api_requests,

            "method_usage": method_usage,
            "method_usage_summary": method_statistics["method_usage_summary"],
            "raison_method_selection": method_statistics["raison_method_selection"],
            "raison_selection_summary": method_statistics["raison_selection_summary"],

            "legacy_automatic_fallback_attempts": (
                legacy_fallback_attempts
            ),
            "unknown_source_attempts": (
                unknown_source_attempts
            ),

            "total_guest_records": (
                total_guest_records
            ),
            "total_guest_solves": (
                total_guest_solves
            ),

            "total_solves": total_attempts,
            "manual_solves": manual_attempts,
            "raison_solves": raison_attempts,
            "automatic_fallback_solves": (
                legacy_fallback_attempts
            ),
            "unknown_source_solves": (
                unknown_source_attempts
            ),
        },
    }


@router.get("/users")
def admin_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        users = (
            db.query(User)
            .order_by(
                User.created_at.desc()
            )
            .all()
        )

    except SQLAlchemyError:
        database_failure(
            "Database error while loading admin users."
        )

    return {
        "success": True,
        "total": len(users),
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at,
            }
            for user in users
        ],
    }


@router.get("/guests")
def admin_guests(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        guests = (
            db.query(GuestUsage)
            .order_by(
                GuestUsage.last_used_at.desc()
            )
            .all()
        )

    except SQLAlchemyError:
        database_failure(
            "Database error while loading guest usage."
        )

    return {
        "success": True,
        "total": len(guests),
        "guests": [
            {
                "id": guest.id,
                "guest_id": guest.guest_id,
                "solve_count": guest.solve_count,
                "created_at": guest.created_at,
                "last_used_at": guest.last_used_at,
            }
            for guest in guests
        ],
    }


@router.get("/history")
def admin_history(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        history = (
            db.query(SolveHistory)
            .order_by(
                SolveHistory.created_at.desc()
            )
            .all()
        )

        users = (
            db.query(User)
            .all()
        )

    except SQLAlchemyError:
        database_failure(
            "Database error while loading solve history."
        )

    user_emails = {
        user.id: user.email
        for user in users
    }

    history_items = []

    for item in history:
        if item.user_id is not None:
            user_type = "registered"

            user_email = user_emails.get(
                item.user_id,
                "Unknown user",
            )

        else:
            user_type = "guest"
            user_email = None

        history_items.append(
            {
                "id": item.id,
                "user_id": item.user_id,
                "user_email": user_email,
                "guest_id": item.guest_id,
                "user_type": user_type,

                "equation": item.equation,
                "method": item.method,
                "result": item.result,
                "iterations": item.iterations,

                "success": item.success,
                "error_code": item.error_code,
                "error_message": item.error_message,

                "used_raison": item.used_raison,
                "selection_source": (
                    item.selection_source
                ),

                "request_source": (
                    item.request_source
                ),

                "raison_method": (
                    item.raison_method
                ),
                "raison_explanation": (
                    item.raison_explanation
                ),

                "created_at": item.created_at,
            }
        )

    return {
        "success": True,
        "total": len(history_items),
        "history": history_items,
    }
