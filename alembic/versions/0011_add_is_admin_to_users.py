"""Add is_admin field to users table

Revision ID: 0011_add_is_admin_to_users
Revises: 0010_create_user_reading_plan_tracking
Create Date: 2025-11-29
"""
from alembic import op

revision = '0011_add_is_admin_to_users'
down_revision = '0010_user_reading_plan_tracking'
branch_labels = None
depends_on = None

def upgrade():
    op.execute(
        """
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
        """
    )

def downgrade():
    op.execute(
        """
        ALTER TABLE users 
        DROP COLUMN IF EXISTS is_admin;
        """
    )
