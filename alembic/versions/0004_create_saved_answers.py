"""Create saved_answers table

Revision ID: 0004_create_saved_answers
Revises: 0003_add_auth_to_users
Create Date: 2025-11-02
"""
from alembic import op

revision = '0004_create_saved_answers'
down_revision = '0003_add_auth_to_users'
branch_labels = None
depends_on = None

def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_answers (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            tags TEXT[],
            saved_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, question_id)
        );
        
        -- Create indexes for faster queries
        CREATE INDEX IF NOT EXISTS idx_saved_answers_user_id ON saved_answers(user_id);
        CREATE INDEX IF NOT EXISTS idx_saved_answers_saved_at ON saved_answers(saved_at);
        CREATE INDEX IF NOT EXISTS idx_saved_answers_tags ON saved_answers USING GIN(tags);
        """
    )

def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS saved_answers;
        """
    )
