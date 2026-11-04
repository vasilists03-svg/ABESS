from datetime import datetime, timedelta

from email.message import EmailMessage


import hashlib
import logging
import os
import secrets
import smtplib


from dotenv import load_dotenv

from fastapi import APIRouter, Depends, HTTPException, Response

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.orm import Session


from app.api_keys import (
    decrypt_api_key,
    encrypt_api_key,
    generate_api_key,
    get_api_key_last4,
    hash_api_key,
)

from app.database import get_db

from app.models.user import User

from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MyInformationResponse,
    RegisterResponse,
    RegenerateApiKeyResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    VerifyEmailResponse,
)

from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


load_dotenv()


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


bearer_scheme = HTTPBearer(auto_error=False)


MAIL_HOST = os.getenv("MAIL_HOST")

MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))

MAIL_USERNAME = os.getenv("MAIL_USERNAME")

MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

MAIL_FROM = os.getenv("MAIL_FROM")

FRONTEND_URL = (
    os.getenv("FRONTEND_URL")
    or ""
).rstrip("/")


# Public URL used in verification emails.
# No localhost fallback is used in production-facing links.
PUBLIC_BASE_URL = (
    os.getenv("PUBLIC_BASE_URL")
    or os.getenv("BACKEND_URL")
    or ""
).rstrip("/")


def database_failure(
    db: Session,
    log_message: str,
):
    db.rollback()

    logger.exception(log_message)

    raise HTTPException(
        status_code=500,
        detail="The server could not process the request.",
    )


def create_verification_token() -> str:
    return secrets.token_urlsafe(32)


def assign_new_api_key(user: User) -> str:
    """
    Generates a new API key for a user.

    The plain API key is never stored directly in the database.

    We store:
    - encrypted version: used when the authenticated user wants
      to view/copy the key from My Information.
    - HMAC hash: used to authenticate API requests.
    - last 4 characters: used for masked display.
    - creation date.
    """
    api_key = generate_api_key()

    user.api_key_encrypted = encrypt_api_key(api_key)

    user.api_key_hash = hash_api_key(api_key)

    user.api_key_last4 = get_api_key_last4(api_key)

    user.api_key_created_at = datetime.utcnow()

    return api_key


def send_verification_email(
    to_email: str,
    token: str,
):
    if (
        not MAIL_HOST
        or not MAIL_USERNAME
        or not MAIL_PASSWORD
        or not MAIL_FROM
    ):
        logger.error(
            "Email service configuration is incomplete."
        )

        raise RuntimeError(
            "Email service configuration is incomplete."
        )

    if not PUBLIC_BASE_URL:
        logger.error(
            "PUBLIC_BASE_URL or BACKEND_URL is not configured."
        )

        raise RuntimeError(
            "Public base URL is not configured."
        )

    verification_link = (
        f"{PUBLIC_BASE_URL}/auth/verify-email?token={token}"
    )

    message = EmailMessage()

    message["Subject"] = (
        "Equation Solver - Email Verification"
    )

    message["From"] = MAIL_FROM

    message["To"] = to_email

    message.set_content(
        f"""Hello!

An account has been created for you in the Equation Solver application.

To activate your account, please click the following link:

{verification_link}

This verification link is valid for 24 hours.

If you did not create this account, please ignore this email.

Equation Solver
"""
    )

    try:
        with smtplib.SMTP(
            MAIL_HOST,
            MAIL_PORT,
            timeout=15,
        ) as server:
            server.starttls()

            server.login(
                MAIL_USERNAME,
                MAIL_PASSWORD,
            )

            server.send_message(message)

    except Exception:
        logger.exception(
            "Failed to send a verification email."
        )

        raise


def create_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_password_reset_token(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def send_password_reset_email(
    to_email: str,
    token: str,
):
    if (
        not MAIL_HOST
        or not MAIL_USERNAME
        or not MAIL_PASSWORD
        or not MAIL_FROM
    ):
        logger.error(
            "Email service configuration is incomplete."
        )

        raise RuntimeError(
            "Email service configuration is incomplete."
        )

    if not FRONTEND_URL:
        logger.error(
            "FRONTEND_URL is not configured."
        )

        raise RuntimeError(
            "Frontend URL is not configured."
        )

    reset_link = (
        f"{FRONTEND_URL}/?reset_token={token}"
    )

    message = EmailMessage()

    message["Subject"] = (
        "Equation Solver - Password Reset"
    )

    message["From"] = MAIL_FROM
    message["To"] = to_email

    message.set_content(
        f"""Hello!

A password reset was requested for your Equation Solver account.

To choose a new password, open the following link:

{reset_link}

This link is valid for 30 minutes and can be used only once.

If you did not request a password reset, you can ignore this email.

Equation Solver
"""
    )

    try:
        with smtplib.SMTP(
            MAIL_HOST,
            MAIL_PORT,
            timeout=15,
        ) as server:
            server.starttls()

            server.login(
                MAIL_USERNAME,
                MAIL_PASSWORD,
            )

            server.send_message(
                message
            )

    except Exception:
        logger.exception(
            "Failed to send a password reset email."
        )

        raise


@router.post(
    "/register",
    response_model=RegisterResponse,
)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    try:
        existing_user = (
            db.query(User)
            .filter(
                User.email == user_data.email
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while checking a registration.",
        )

    verification_token = (
        create_verification_token()
    )

    verification_expires_at = (
        datetime.utcnow()
        + timedelta(hours=24)
    )

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This email address is already registered."
                ),
            )

        existing_user.hashed_password = (
            hash_password(
                user_data.password
            )
        )

        existing_user.verification_token = (
            verification_token
        )

        existing_user.verification_token_expires_at = (
            verification_expires_at
        )

        existing_user.is_active = True

        # Existing unverified accounts created before the
        # API-key feature may not have an API key yet.
        if (
            not existing_user.api_key_encrypted
            or not existing_user.api_key_hash
        ):
            assign_new_api_key(existing_user)

        try:
            db.commit()

            db.refresh(existing_user)

        except SQLAlchemyError:
            database_failure(
                db,
                "Database error while updating an unverified account.",
            )

        try:
            send_verification_email(
                existing_user.email,
                verification_token,
            )

        except Exception:
            raise HTTPException(
                status_code=500,
                detail=(
                    "The verification email could not be sent. "
                    "Please try again later."
                ),
            )

        return {
            "success": True,
            "message": (
                "This account has not been verified yet. "
                "A new verification email has been sent."
            ),
            "email": existing_user.email,
        }

    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(
            user_data.password
        ),
        role="user",
        is_active=True,
        is_verified=False,
        verification_token=(
            verification_token
        ),
        verification_token_expires_at=(
            verification_expires_at
        ),
    )

    # Every newly created user receives
    # their own unique API key.
    assign_new_api_key(new_user)

    try:
        db.add(new_user)

        db.commit()

        db.refresh(new_user)

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while creating a user account.",
        )

    try:
        send_verification_email(
            new_user.email,
            verification_token,
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail=(
                "Your account was created, but the "
                "verification email could not be sent. "
                "Please try again later."
            ),
        )

    return {
        "success": True,
        "message": (
            "Your account has been created. "
            "A verification email has been sent."
        ),
        "email": new_user.email,
    }


@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    try:
        user = (
            db.query(User)
            .filter(
                User.verification_token == token
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while verifying an email address.",
        )

    if not user:
        raise HTTPException(
            status_code=400,
            detail=(
                "The verification link is invalid."
            ),
        )

    if (
        user.verification_token_expires_at
        is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The verification link is invalid."
            ),
        )

    if (
        user.verification_token_expires_at
        < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The verification link has expired. "
                "Please register again to receive "
                "a new verification email."
            ),
        )

    user.is_verified = True

    user.verification_token = None

    user.verification_token_expires_at = None

    try:
        db.commit()

        db.refresh(user)

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while completing email verification.",
        )

    return {
        "success": True,
        "message": (
            "Your email address has been verified "
            "successfully. You can now log in."
        ),
    }


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
)
def forgot_password(
    request_data: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    generic_response = {
        "success": True,
        "message": (
            "If an eligible account exists for this email address, "
            "a password reset link has been sent."
        ),
    }

    try:
        user = (
            db.query(User)
            .filter(
                User.email
                == request_data.email
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while processing a password reset request.",
        )

    if (
        not user
        or not user.is_active
        or not user.is_verified
    ):
        return generic_response

    reset_token = (
        create_password_reset_token()
    )

    user.password_reset_token_hash = (
        hash_password_reset_token(
            reset_token
        )
    )

    user.password_reset_token_expires_at = (
        datetime.utcnow()
        + timedelta(minutes=30)
    )

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while creating a password reset token.",
        )

    try:
        send_password_reset_email(
            user.email,
            reset_token,
        )

    except Exception:
        user.password_reset_token_hash = None
        user.password_reset_token_expires_at = None

        try:
            db.commit()

        except SQLAlchemyError:
            db.rollback()

            logger.exception(
                "Failed to clear an unusable password reset token."
            )

        return generic_response

    return generic_response


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
)
def reset_password(
    request_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    token = (
        request_data.token
        or ""
    ).strip()

    if (
        not token
        or len(token) > 512
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The password reset link is invalid or has expired."
            ),
        )

    if len(request_data.new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain at least 6 characters."
            ),
        )

    token_hash = (
        hash_password_reset_token(
            token
        )
    )

    try:
        user = (
            db.query(User)
            .filter(
                User.password_reset_token_hash
                == token_hash
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while validating a password reset token.",
        )

    if (
        not user
        or user.password_reset_token_expires_at is None
        or user.password_reset_token_expires_at
        < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "The password reset link is invalid or has expired."
            ),
        )

    user.hashed_password = (
        hash_password(
            request_data.new_password
        )
    )

    user.password_reset_token_hash = None
    user.password_reset_token_expires_at = None

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while resetting a password.",
        )

    return {
        "success": True,
        "message": (
            "Your password has been changed successfully. "
            "You can now log in with your new password."
        ),
    }


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    try:
        user = (
            db.query(User)
            .filter(
                User.email == user_data.email
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while processing a login.",
        )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    try:
        password_is_valid = verify_password(
            user_data.password,
            user.hashed_password,
        )

    except Exception:
        logger.exception(
            "Password verification failed unexpectedly."
        )

        password_is_valid = False

    if not password_is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account is inactive.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "Please verify your email address before logging in. "
                "Check your inbox or spam folder."
            ),
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are required."
            ),
        )

    token = (
        credentials.credentials or ""
    ).strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are invalid "
                "or have expired."
            ),
        )

    try:
        payload = decode_access_token(token)

    except Exception:
        logger.exception(
            "Unexpected error while decoding an authentication token."
        )

        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are invalid "
                "or have expired."
            ),
        )

    if not payload:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are invalid "
                "or have expired."
            ),
        )

    user_id = payload.get("sub")

    try:
        user_id = int(user_id)

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are invalid "
                "or have expired."
            ),
        )

    try:
        user = (
            db.query(User)
            .filter(
                User.id == user_id
            )
            .first()
        )

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while loading the authenticated user.",
        )

    if not user:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication credentials are invalid "
                "or have expired."
            ),
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="This account is inactive.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "Please verify your email address "
                "before continuing."
            ),
        )

    return user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user


@router.get(
    "/my-information",
    response_model=MyInformationResponse,
)
def get_my_information(
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Returns the authenticated user's account information
    together with the decrypted API key.

    The API key is returned only to the authenticated owner
    of the account. The response is marked as non-cacheable
    because it contains sensitive information.
    """

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate"
    )

    response.headers["Pragma"] = "no-cache"

    if (
        not current_user.api_key_encrypted
        or not current_user.api_key_hash
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "An API key has not been configured "
                "for this account."
            ),
        )

    try:
        api_key = decrypt_api_key(
            current_user.api_key_encrypted
        )

    except Exception:
        logger.exception(
            "Failed to decrypt an API key "
            "for an authenticated user."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The API key could not be loaded."
            ),
        )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "api_key": api_key,
        "api_key_last4": (
            current_user.api_key_last4
            or api_key[-4:]
        ),
        "api_key_created_at": (
            current_user.api_key_created_at
        ),
    }


@router.post(
    "/regenerate-api-key",
    response_model=RegenerateApiKeyResponse,
)
def regenerate_api_key(
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    """
    Replaces the current API key with a newly generated one.

    After this operation succeeds, the previous API key can
    no longer be used for API authentication.
    """

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate"
    )

    response.headers["Pragma"] = "no-cache"

    try:
        new_api_key = assign_new_api_key(
            current_user
        )

        db.commit()

        db.refresh(current_user)

    except SQLAlchemyError:
        database_failure(
            db,
            "Database error while regenerating an API key.",
        )

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to regenerate an API key."
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The API key could not be regenerated."
            ),
        )

    return {
        "success": True,
        "message": (
            "Your API key has been regenerated successfully. "
            "The previous API key is no longer valid."
        ),
        "api_key": new_api_key,
        "api_key_last4": current_user.api_key_last4,
        "api_key_created_at": (
            current_user.api_key_created_at
        ),
    }