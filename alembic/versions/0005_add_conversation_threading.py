"""Add conversation threading support

Revision ID: 0005_add_conversation_threading
Revises: 0004_create_saved_answers
Create Date: 2025-11-03
"""
from alembic import op

revision = '0005_add_conversation_threading'
down_revision = '0004_create_saved_answers'
branch_labels = None
depends_on = None

def upgrade():
    # Add parent_question_id to track conversation threads
    op.execute(
        """
        ALTER TABLE questions 
        ADD COLUMN IF NOT EXISTS parent_question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE;
        
        CREATE INDEX IF NOT EXISTS idx_questions_parent_id ON questions(parent_question_id);
        """
    )

def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_questions_parent_id;
        ALTER TABLE questions DROP COLUMN IF EXISTS parent_question_id;
        """
    )
