"""Create trivia tables

Revision ID: 0016_create_trivia_tables
Revises: 0015_add_geolocation
Create Date: 2026-03-09
"""
from alembic import op

revision = '0016_create_trivia_tables'
down_revision = '0015_add_geolocation'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS trivia_questions (
            id SERIAL PRIMARY KEY,
            question_text TEXT NOT NULL,
            question_type VARCHAR(20) NOT NULL,
            category VARCHAR(50) NOT NULL,
            difficulty VARCHAR(10) NOT NULL,
            options JSONB NOT NULL,
            correct_answer VARCHAR(500) NOT NULL,
            correct_index SMALLINT,
            explanation TEXT,
            scripture_reference VARCHAR(100),
            times_used INTEGER NOT NULL DEFAULT 0,
            times_correct INTEGER NOT NULL DEFAULT 0,
            is_daily_challenge BOOLEAN NOT NULL DEFAULT false,
            daily_date DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_trivia_q_category_difficulty ON trivia_questions(category, difficulty);
        CREATE INDEX IF NOT EXISTS idx_trivia_q_daily ON trivia_questions(daily_date) WHERE is_daily_challenge = true;

        CREATE TABLE IF NOT EXISTS trivia_game_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            difficulty VARCHAR(10) NOT NULL,
            question_count SMALLINT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            correct_count SMALLINT NOT NULL DEFAULT 0,
            time_taken_seconds INTEGER,
            streak_max SMALLINT NOT NULL DEFAULT 0,
            is_daily_challenge BOOLEAN NOT NULL DEFAULT false,
            daily_date DATE,
            answers JSONB NOT NULL DEFAULT '[]',
            completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_trivia_sessions_user_id ON trivia_game_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_trivia_sessions_leaderboard ON trivia_game_sessions(category, difficulty, score DESC, completed_at);
        CREATE INDEX IF NOT EXISTS idx_trivia_sessions_weekly ON trivia_game_sessions(completed_at, score DESC);
        CREATE INDEX IF NOT EXISTS idx_trivia_sessions_daily ON trivia_game_sessions(daily_date, score DESC) WHERE is_daily_challenge = true;
    """)


def downgrade():
    op.execute("""
        DROP INDEX IF EXISTS idx_trivia_sessions_daily;
        DROP INDEX IF EXISTS idx_trivia_sessions_weekly;
        DROP INDEX IF EXISTS idx_trivia_sessions_leaderboard;
        DROP INDEX IF EXISTS idx_trivia_sessions_user_id;
        DROP TABLE IF EXISTS trivia_game_sessions;
        DROP INDEX IF EXISTS idx_trivia_q_daily;
        DROP INDEX IF EXISTS idx_trivia_q_category_difficulty;
        DROP TABLE IF EXISTS trivia_questions;
    """)
