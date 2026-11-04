import os

from dotenv import load_dotenv

from app.database import SessionLocal
from app.models.user import User


load_dotenv()


def set_admin_role():
    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()

    if not admin_email:
        print("ERROR: Δεν έχει οριστεί ADMIN_EMAIL στο .env.")
        return

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == admin_email)
            .first()
        )

        if user is None:
            print(
                "ERROR: Δεν βρέθηκε χρήστης με email "
                f"{admin_email}."
            )
            return

        if user.role == "admin":
            print(
                "INFO: Ο χρήστης είναι ήδη admin: "
                f"{user.email}"
            )
            return

        user.role = "admin"
        db.commit()
        db.refresh(user)

        print(
            "OK: Ο ρόλος του χρήστη άλλαξε σε admin: "
            f"{user.email}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    set_admin_role()