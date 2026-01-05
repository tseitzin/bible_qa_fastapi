"""Reset admin user password."""
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from app.database import get_db_connection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_admin_password(email: str, new_password: str):
    """Reset admin user password."""
    hashed_password = pwd_context.hash(new_password)
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET hashed_password = %s WHERE email = %s AND is_admin = true RETURNING id, email, username;",
                (hashed_password, email)
            )
            user = cur.fetchone()
            conn.commit()
            
            if user:
                print(f"✅ Password reset successful for:")
                print(f"   ID: {user['id']}")
                print(f"   Email: {user['email']}")
                print(f"   Username: {user['username']}")
                return True
            else:
                print(f"❌ No admin user found with email: {email}")
                return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_admin_password.py <admin_email> <new_password>")
        print("Example: python reset_admin_password.py admin@example.com newpassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    print(f"Resetting password for: {email}")
    success = reset_admin_password(email, password)
    sys.exit(0 if success else 1)
