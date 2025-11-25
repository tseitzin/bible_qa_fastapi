"""Add tables for tracking user reading plan progress

Revision ID: 0010_user_reading_plan_tracking
Revises: 0009_study_resource_tables
Create Date: 2025-11-24
"""
from alembic import op


revision = "0010_user_reading_plan_tracking"
down_revision = "0009_study_resource_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_reading_plans (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id INTEGER NOT NULL REFERENCES reading_plans(id) ON DELETE CASCADE,
            plan_slug TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            plan_description TEXT,
            plan_duration_days INTEGER NOT NULL,
            plan_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            start_date DATE NOT NULL DEFAULT CURRENT_DATE,
            nickname TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ
        );

        CREATE INDEX IF NOT EXISTS idx_user_reading_plans_user
            ON user_reading_plans (user_id);

        CREATE INDEX IF NOT EXISTS idx_user_reading_plans_user_active
            ON user_reading_plans (user_id, is_active)
            WHERE is_active = TRUE;

        CREATE TABLE IF NOT EXISTS user_reading_plan_days (
            id SERIAL PRIMARY KEY,
            user_plan_id INTEGER NOT NULL REFERENCES user_reading_plans(id) ON DELETE CASCADE,
            day_number INTEGER NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            UNIQUE (user_plan_id, day_number)
        );

        CREATE INDEX IF NOT EXISTS idx_user_reading_plan_days_plan
            ON user_reading_plan_days (user_plan_id);
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS idx_user_reading_plan_days_plan;
        DROP TABLE IF EXISTS user_reading_plan_days;

        DROP INDEX IF EXISTS idx_user_reading_plans_user_active;
        DROP INDEX IF EXISTS idx_user_reading_plans_user;
        DROP TABLE IF EXISTS user_reading_plans;
        """
    )
