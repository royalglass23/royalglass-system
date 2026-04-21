"""
Temporary script to seed the admin user from inside the backend container.
Run with: docker compose exec backend python seed_user.py
"""
import os
import bcrypt
from sqlalchemy import create_engine, text

db_url = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('DB_HOST', 'db')}/{os.getenv('POSTGRES_DB')}"
)

h = bcrypt.hashpw(b"*royalGlass23", bcrypt.gensalt()).decode()

engine = create_engine(db_url)
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (name, email, password_hash, role)
        VALUES ('Royal Glass', 'info@royalglass.co.nz', :h, 'admin')
        ON CONFLICT (email) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role
    """), {"h": h})
    conn.commit()

print("User created: info@royalglass.co.nz / *royalGlass23")
