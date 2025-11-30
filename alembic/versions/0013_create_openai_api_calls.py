"""
Add openai_api_calls table for tracking OpenAI API usage
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0013_create_openai_api_calls'
down_revision = '0012_create_api_request_logs'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "openai_api_calls",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), index=True, nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer(), nullable=False, default=0),
        sa.Column("status", sa.String(length=20), nullable=False),  # 'success', 'error', 'rate_limit'
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
    )

def downgrade():
    op.drop_table("openai_api_calls")
