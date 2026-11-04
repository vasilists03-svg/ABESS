import hashlib
import hmac
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv


load_dotenv()


API_KEY_PREFIX = "abess_sk_"

API_KEY_ENCRYPTION_KEY = os.getenv("API_KEY_ENCRYPTION_KEY")
API_KEY_HASH_SECRET = os.getenv("API_KEY_HASH_SECRET")


def _get_fernet() -> Fernet:
    """
    Returns the Fernet instance used to encrypt/decrypt API keys.

    The encryption key must be stored outside the database,
    preferably as an environment variable.
    """
    if not API_KEY_ENCRYPTION_KEY:
        raise RuntimeError(
            "API_KEY_ENCRYPTION_KEY is not configured."
        )

    try:
        return Fernet(API_KEY_ENCRYPTION_KEY.encode("utf-8"))
    except Exception as exc:
        raise RuntimeError(
            "API_KEY_ENCRYPTION_KEY is invalid."
        ) from exc


def _get_hash_secret() -> bytes:
    """
    Returns the secret used for HMAC hashing of API keys.
    """
    if not API_KEY_HASH_SECRET:
        raise RuntimeError(
            "API_KEY_HASH_SECRET is not configured."
        )

    return API_KEY_HASH_SECRET.encode("utf-8")


def generate_api_key() -> str:
    """
    Generates a cryptographically secure API key.

    Example:
    abess_sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    """
    random_part = secrets.token_urlsafe(32)

    return f"{API_KEY_PREFIX}{random_part}"


def hash_api_key(api_key: str) -> str:
    """
    Creates a deterministic HMAC-SHA256 hash of an API key.

    This value is used to identify the user making an API request
    without storing or comparing the plain API key.
    """
    if not api_key:
        raise ValueError("API key is required.")

    secret = _get_hash_secret()

    return hmac.new(
        secret,
        api_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypts the API key before it is stored in the database.

    Encryption is reversible so the authenticated user can view
    and copy their API key from My Information.
    """
    if not api_key:
        raise ValueError("API key is required.")

    fernet = _get_fernet()

    encrypted = fernet.encrypt(
        api_key.encode("utf-8")
    )

    return encrypted.decode("utf-8")


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypts an API key for an authenticated user.

    The plain API key must never be written to application logs.
    """
    if not encrypted_api_key:
        raise ValueError("Encrypted API key is required.")

    fernet = _get_fernet()

    try:
        decrypted = fernet.decrypt(
            encrypted_api_key.encode("utf-8")
        )

    except InvalidToken as exc:
        raise ValueError(
            "The stored API key could not be decrypted."
        ) from exc

    return decrypted.decode("utf-8")


def get_api_key_last4(api_key: str) -> str:
    """
    Returns only the final four characters for masked display.
    """
    if not api_key:
        raise ValueError("API key is required.")

    return api_key[-4:]