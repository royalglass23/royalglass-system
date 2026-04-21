"""
create_user.py
Run this script once to create a staff login account in the database.
Uses bcrypt directly (bypasses passlib compatibility issues with Python 3.14+).

Usage (from D:\\royalglass\\):
    python backend/create_user.py
"""
import sys
import os

from dotenv import load_dotenv
load_dotenv()

import bcrypt
import psycopg2


def main():
    print("\n── Royal Glass: Create Staff Account ──\n")

    name = input("Full name (e.g. Roxy Huang): ").strip()
    email = input("Email address: ").strip().lower()
    password = input("Password: ").strip()
    role = input("Role [staff/admin] (default: staff): ").strip() or "staff"

    if not name or not email or not password:
        print("Error: name, email, and password are all required.")
        sys.exit(1)

    if role not in ("staff", "admin"):
        print("Error: role must be 'staff' or 'admin'.")
        sys.exit(1)

    # Hash the password using bcrypt directly
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=5432,
        )
    except Exception as e:
        print(f"\nCould not connect to the database: {e}")
        print("Make sure Docker is running: docker compose ps")
        sys.exit(1)

    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE
                SET name = EXCLUDED.name,
                    password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role
        """, (name, email, hashed.decode("utf-8"), role))
        conn.commit()
        print(f"\nAccount created successfully.")
        print(f"  Name:  {name}")
        print(f"  Email: {email}")
        print(f"  Role:  {role}")
        print(f"\nTest your login at: http://localhost:8000/docs\n")
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
