from datetime import datetime, timedelta
from typing import Optional

import os
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# Χρησιμοποιούμε pbkdf2_sha256 για να αποφύγουμε το bcrypt error.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Μετατρέπει τον κανονικό κωδικό σε hashed password.
    Δεν αποθηκεύουμε ποτέ plain password στη βάση.
    """
    if password is None:
        raise ValueError("Password is required.")

    password = str(password)

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Ελέγχει αν ο κωδικός που έβαλε ο χρήστης ταιριάζει
    με το hashed password που υπάρχει στη βάση.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        return pwd_context.verify(str(plain_password), hashed_password)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Δημιουργεί JWT token για τον συνδεδεμένο χρήστη.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


def decode_access_token(token: str):
    """
    Διαβάζει το JWT token και επιστρέφει τα δεδομένα του.
    Αν το token είναι λάθος ή ληγμένο, επιστρέφει None.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload

    except JWTError:
        return None