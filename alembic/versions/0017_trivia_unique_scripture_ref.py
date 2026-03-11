"""Add unique index on (category, difficulty, scripture_reference) for trivia_questions.

Removes duplicate-passage rows (keeping lowest id per group) then adds a partial
unique index so the question generator cannot store two questions about the same
Bible passage in the same category/difficulty bucket.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-10
"""

from alembic import op

revision = "0017"
down_revision = "0016_create_trivia_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate-passage rows, keeping the one with the lowest id.
    # COALESCE ensures rows without a scripture_reference are each treated
    # as unique (id::text is always distinct).
    op.execute(
        """
        DELETE FROM trivia_questions
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM trivia_questions
            GROUP BY category, difficulty, COALESCE(scripture_reference, id::text)
        )
        """
    )

    # Partial unique index — NULLs are excluded so each NULL is still distinct.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trivia_q_unique_ref
        ON trivia_questions (category, difficulty, scripture_reference)
        WHERE scripture_reference IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_trivia_q_unique_ref")
