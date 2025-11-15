"""Create recent questions table for per-user history

Revision ID: 0007_create_recent_questions
Revises: 0006_create_bible_verses
Create Date: 2025-11-14
"""
from alembic import op


revision = '0007_create_recent_questions'
down_revision = '0006_create_bible_verses'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recent_questions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            asked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_recent_questions_user_question UNIQUE (user_id, question)
        );

        CREATE INDEX IF NOT EXISTS idx_recent_questions_user_id_asked_at
            ON recent_questions(user_id, asked_at DESC);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_recent_questions_user_id_asked_at;
        DROP TABLE IF EXISTS recent_questions;
        """
    )
