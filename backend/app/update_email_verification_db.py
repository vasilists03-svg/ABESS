import sqlite3


DB_PATH = "app.db"


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    for column in columns:
        if column[1] == column_name:
            return True

    return False


def index_exists(cursor, index_name):
    cursor.execute("PRAGMA index_list(users)")
    indexes = cursor.fetchall()

    for index in indexes:
        if index[1] == index_name:
            return True

    return False


def main():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    print("Checking users table...")

    if not column_exists(cursor, "users", "is_verified"):
        print("Adding column: is_verified")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT 0"
        )
    else:
        print("Column already exists: is_verified")

    if not column_exists(cursor, "users", "verification_token"):
        print("Adding column: verification_token")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN verification_token VARCHAR"
        )
    else:
        print("Column already exists: verification_token")

    if not column_exists(cursor, "users", "verification_token_expires_at"):
        print("Adding column: verification_token_expires_at")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN verification_token_expires_at DATETIME"
        )
    else:
        print("Column already exists: verification_token_expires_at")

    if not index_exists(cursor, "ix_users_verification_token"):
        print("Creating index: ix_users_verification_token")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_verification_token "
            "ON users (verification_token)"
        )
    else:
        print("Index already exists: ix_users_verification_token")

    # Οι ήδη υπάρχοντες χρήστες θεωρούνται verified για να μη χαλάσουν τα παλιά login.
    print("Marking existing users as verified...")
    cursor.execute(
        """
        UPDATE users
        SET is_verified = 1
        WHERE is_verified IS NULL OR is_verified = 0
        """
    )

    connection.commit()
    connection.close()

    print("Database updated successfully.")


if __name__ == "__main__":
    main()