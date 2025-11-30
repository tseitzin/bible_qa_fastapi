"""Add IP address tracking to users table

Revision ID: 0014_add_ip_to_users
Revises: 0013_create_openai_api_calls
Create Date: 2025-11-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0014_add_ip_to_users'
down_revision = '0013_create_openai_api_calls'
branch_labels = None
depends_on = None

def upgrade():
    # Add IP address column to users table (supports IPv4 and IPv6)
    op.execute(
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS last_ip_address VARCHAR(45);
        
        -- Create index for admin filtering by IP
        CREATE INDEX IF NOT EXISTS idx_users_last_ip_address ON users(last_ip_address);
        
        -- Add is_guest flag to distinguish guest users from registered users
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_guest BOOLEAN DEFAULT FALSE;
        
        CREATE INDEX IF NOT EXISTS idx_users_is_guest ON users(is_guest);
        """
    )

def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_users_last_ip_address;
        DROP INDEX IF EXISTS idx_users_is_guest;
        ALTER TABLE users 
        DROP COLUMN IF EXISTS last_ip_address,
        DROP COLUMN IF EXISTS is_guest;
        """
    )
