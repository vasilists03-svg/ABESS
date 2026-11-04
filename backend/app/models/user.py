from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)

    # Email verification
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_token = Column(String, unique=True, index=True, nullable=True)
    verification_token_expires_at = Column(DateTime, nullable=True)

    # Password reset
    #
    # Only a hash of the reset token is stored.
    # The plain reset token is sent only to the user's email.
    password_reset_token_hash = Column(
        String,
        unique=True,
        index=True,
        nullable=True,
    )

    password_reset_token_expires_at = Column(
        DateTime,
        nullable=True,
    )

    # API key
    #
    # api_key_encrypted:
    #   Κρατάει το API key κρυπτογραφημένο ώστε ο χρήστης
    #   να μπορεί να το δει και να το αντιγράψει από το My Information.
    #
    # api_key_hash:
    #   Χρησιμοποιείται για την ταυτοποίηση εισερχόμενων API requests.
    #   Δεν χρειάζεται αποκρυπτογράφηση για κάθε request.
    #
    # api_key_last4:
    #   Επιτρέπει ασφαλή masked εμφάνιση στο frontend.
    #
    api_key_encrypted = Column(String, nullable=True)

    api_key_hash = Column(
        String,
        unique=True,
        index=True,
        nullable=True,
    )

    api_key_last4 = Column(
        String(4),
        nullable=True,
    )

    api_key_created_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)