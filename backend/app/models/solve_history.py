from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class SolveHistory(Base):
    __tablename__ = "solve_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        nullable=True
    )

    guest_id = Column(
        String,
        nullable=True
    )

    equation = Column(
        String,
        nullable=False
    )

    method = Column(
        String,
        nullable=False
    )

    result = Column(
        String,
        nullable=False,
        default=""
    )

    iterations = Column(
        Integer,
        nullable=True
    )

    # True όταν η επίλυση ολοκληρώθηκε επιτυχώς.
    # False όταν έγινε προσπάθεια αλλά επέστρεψε σφάλμα.
    success = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # Σύντομος κωδικός σφάλματος, π.χ.
    # NO_CONVERGENCE, INVALID_INTERVAL κ.λπ.
    error_code = Column(
        String,
        nullable=True
    )

    # Το φιλικό μήνυμα σφάλματος που εμφανίζεται
    # και στον χρήστη.
    error_message = Column(
        String,
        nullable=True
    )

    # Αν χρησιμοποιήθηκε η rAIson
    # κατά την επιλογή μεθόδου.
    used_raison = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # Πηγή της τελικής επιλογής μεθόδου:
    # manual ή raison.
    selection_source = Column(
        String,
        default="unknown",
        nullable=False
    )

    # Πηγή του request:
    # WEB = browser/JWT
    # API = εξωτερική κλήση με X-API-Key
    request_source = Column(
        String,
        default="WEB",
        nullable=False
    )

    # Η μέθοδος που πρότεινε η rAIson.
    raison_method = Column(
        String,
        nullable=True
    )

    # Το πραγματικό explanation/OTP που
    # επιστρέφει η rAIson για την επιλογή.
    raison_explanation = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )