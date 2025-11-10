"""Create bible_verses table

Revision ID: 0006_create_bible_verses
Revises: 0005_add_conversation_threading
Create Date: 2025-11-09
"""
from alembic import op


revision = "0006_create_bible_verses"
down_revision = "0005_add_conversation_threading"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bible_verses (
            id SERIAL PRIMARY KEY,
            book VARCHAR(50) NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_bible_verses_book_chapter_verse
            ON bible_verses (book, chapter, verse);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_bible_verses_book_chapter_verse;
        DROP TABLE IF EXISTS bible_verses;
        """
    )
