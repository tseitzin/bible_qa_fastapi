"""
Alembic migration for API request log table
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0012_create_api_request_logs'
down_revision = '0011_add_is_admin_to_users'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "api_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), index=True, nullable=True),
        sa.Column("endpoint", sa.String(length=256), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("payload_summary", sa.Text(), nullable=True),
    )

def downgrade():
    op.drop_table("api_request_logs")
