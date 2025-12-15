"""Add geolocation fields to users and api_request_logs

Revision ID: 0015_add_geolocation
Revises: 0014_add_ip_to_users
Create Date: 2025-12-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0015_add_geolocation'
down_revision = '0014_add_ip_to_users'
branch_labels = None
depends_on = None

def upgrade():
    # Add geolocation columns to users table
    op.execute("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS country_code VARCHAR(2),
        ADD COLUMN IF NOT EXISTS country_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS city VARCHAR(100),
        ADD COLUMN IF NOT EXISTS region VARCHAR(100);
        
        CREATE INDEX IF NOT EXISTS idx_users_country_code ON users(country_code);
        CREATE INDEX IF NOT EXISTS idx_users_city ON users(city);
    """)
    
    # Add geolocation columns to api_request_logs table
    op.execute("""
        ALTER TABLE api_request_logs
        ADD COLUMN IF NOT EXISTS country_code VARCHAR(2),
        ADD COLUMN IF NOT EXISTS country_name VARCHAR(100),
        ADD COLUMN IF NOT EXISTS city VARCHAR(100);
        
        CREATE INDEX IF NOT EXISTS idx_api_request_logs_country_code ON api_request_logs(country_code);
    """)

def downgrade():
    op.execute("""
        DROP INDEX IF EXISTS idx_users_country_code;
        DROP INDEX IF EXISTS idx_users_city;
        DROP INDEX IF EXISTS idx_api_request_logs_country_code;
        
        ALTER TABLE users 
        DROP COLUMN IF EXISTS country_code,
        DROP COLUMN IF EXISTS country_name,
        DROP COLUMN IF EXISTS city,
        DROP COLUMN IF EXISTS region;
        
        ALTER TABLE api_request_logs
        DROP COLUMN IF EXISTS country_code,
        DROP COLUMN IF EXISTS country_name,
        DROP COLUMN IF EXISTS city;
    """)
