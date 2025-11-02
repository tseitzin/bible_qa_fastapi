"""Add authentication fields to users table

Revision ID: 0003_add_auth_to_users
Revises: 0002_add_users_table
Create Date: 2025-11-02
"""
from alembic import op

revision = '0003_add_auth_to_users'
down_revision = '0002_add_users_table'
branch_labels = None
depends_on = None

def upgrade():
    op.execute(
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS email TEXT UNIQUE,
        ADD COLUMN IF NOT EXISTS hashed_password TEXT,
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        
        -- Create index on email for faster lookups
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """
    )

def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_users_email;
        ALTER TABLE users 
        DROP COLUMN IF EXISTS email,
        DROP COLUMN IF EXISTS hashed_password,
        DROP COLUMN IF EXISTS is_active;
        """
    )
