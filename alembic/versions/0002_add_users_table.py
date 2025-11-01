"""Add users table

Revision ID: 0002_add_users_table
Revises: 0001_create_questions_answers
Create Date: 2025-10-31
"""
from alembic import op

revision = '0002_add_users_table'
down_revision = '0001_create_questions_answers'
branch_labels = None
depends_on = None

def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
        -- Backfill placeholder users for any existing question rows to satisfy forthcoming FK
        INSERT INTO users (id, username)
        SELECT DISTINCT q.user_id, 'user_' || q.user_id
        FROM questions q
        WHERE q.user_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM users u WHERE u.id = q.user_id);

        -- Ensure users sequence is set beyond highest id we just inserted (idempotent)
        -- Compute highest existing id across users and questions; if none, seed sequence at 1
        DO $$
        DECLARE
            highest INTEGER;
        BEGIN
            SELECT GREATEST(
                COALESCE((SELECT MAX(id) FROM users),0),
                COALESCE((SELECT MAX(user_id) FROM questions),0)
            ) INTO highest;
            IF highest < 1 THEN
                PERFORM setval(pg_get_serial_sequence('users','id'), 1, false);
            ELSE
                -- setval with is_called=true makes next value highest+1
                PERFORM setval(pg_get_serial_sequence('users','id'), highest, true);
            END IF;
        END$$;

        -- If questions table exists without FK, add it safely
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_type='FOREIGN KEY'
                  AND table_name='questions'
                  AND constraint_name='questions_user_id_fkey'
            ) THEN
                BEGIN
                    ALTER TABLE questions
                    ADD CONSTRAINT questions_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                EXCEPTION WHEN duplicate_object THEN
                    -- Ignore if added concurrently
                    NULL;
                END;
            END IF;
        END$$;
        """
    )

def downgrade():
    op.execute(
        """
        ALTER TABLE questions DROP CONSTRAINT IF EXISTS questions_user_id_fkey;
        DROP TABLE IF EXISTS users;
        """
    )
