#!/usr/bin/env python3
"""
Seed an admin user in the database securely for local and production.
Usage:
  python seed_admin_user.py --email admin@example.com --username admin --password <password>

Environment variables:
  DATABASE_URL (required)
"""
import os
import sys
import argparse
import psycopg2
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_database_url():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL environment variable not found", file=sys.stderr)
        sys.exit(1)
    return database_url

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def seed_admin_user(email: str, username: str, password: str):
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    hashed_pw = hash_password(password)
    # Upsert admin user
    cur.execute("""
        INSERT INTO users (email, username, hashed_password, is_active, is_admin)
        VALUES (%s, %s, %s, TRUE, TRUE)
        ON CONFLICT (email) DO UPDATE SET
            username = EXCLUDED.username,
            hashed_password = EXCLUDED.hashed_password,
            is_active = TRUE,
            is_admin = TRUE
        RETURNING id, email, username, is_admin;
    """, (email, username, hashed_pw))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded admin user: {user}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed an admin user.")
    parser.add_argument('--email', required=True, help='Admin email')
    parser.add_argument('--username', required=True, help='Admin username')
    parser.add_argument('--password', required=True, help='Admin password')
    args = parser.parse_args()
    seed_admin_user(args.email, args.username, args.password)
