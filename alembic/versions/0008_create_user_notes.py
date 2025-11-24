"""Create user notes table for MCP metadata

Revision ID: 0008_create_user_notes
Revises: 0007_create_recent_questions
Create Date: 2025-11-22
"""
from alembic import op


revision = "0008_create_user_notes"
down_revision = "0007_create_recent_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_notes (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
            content TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            source TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_user_notes_user_id_created_at
            ON user_notes(user_id, created_at DESC);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_user_notes_user_id_created_at;
        DROP TABLE IF EXISTS user_notes;
        """
    )
