"""Initial questions & answers tables

Revision ID: 0001_create_questions_answers
Revises: 
Create Date: 2025-10-31
"""
from alembic import op

revision = '0001_create_questions_answers'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Idempotent raw SQL to allow re-run without failure
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            asked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS answers (
            id SERIAL PRIMARY KEY,
            question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
            answer TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions(user_id);
        CREATE INDEX IF NOT EXISTS idx_questions_asked_at ON questions(asked_at);
        CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
        """
    )

def downgrade():
    # Careful: dropping tables will remove data
    op.execute(
        """
        DROP TABLE IF EXISTS answers;
        DROP TABLE IF EXISTS questions;
        """
    )