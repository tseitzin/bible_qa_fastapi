"""Add reference data tables for MCP study tools

Revision ID: 0009_study_resource_tables
Revises: 0008_create_user_notes
Create Date: 2025-02-15
"""
from alembic import op


revision = "0009_study_resource_tables"
down_revision = "0008_create_user_notes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cross_references (
            id SERIAL PRIMARY KEY,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            reference_data JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_references_lookup
            ON cross_references (LOWER(book), chapter, verse);

        CREATE TABLE IF NOT EXISTS lexicon_entries (
            id SERIAL PRIMARY KEY,
            strongs_number TEXT NOT NULL,
            lemma TEXT NOT NULL,
            transliteration TEXT,
            pronunciation TEXT,
            language TEXT,
            definition TEXT,
            usage TEXT,
            reference_list JSONB NOT NULL DEFAULT '[]'::jsonb,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_lexicon_entries_strongs
            ON lexicon_entries (LOWER(strongs_number));

        CREATE INDEX IF NOT EXISTS idx_lexicon_entries_lemma
            ON lexicon_entries (LOWER(lemma));

        CREATE TABLE IF NOT EXISTS topic_index (
            id SERIAL PRIMARY KEY,
            topic TEXT NOT NULL,
            summary TEXT,
            keywords TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            reference_entries JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_topic_index_topic
            ON topic_index (LOWER(topic));

        CREATE INDEX IF NOT EXISTS idx_topic_index_keywords
            ON topic_index USING GIN (keywords);

        CREATE TABLE IF NOT EXISTS reading_plans (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            duration_days INTEGER NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reading_plans_slug
            ON reading_plans (LOWER(slug));

        CREATE TABLE IF NOT EXISTS reading_plan_entries (
            id SERIAL PRIMARY KEY,
            plan_id INTEGER NOT NULL REFERENCES reading_plans(id) ON DELETE CASCADE,
            day_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            passage TEXT NOT NULL,
            notes TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (plan_id, day_number)
        );

        CREATE TABLE IF NOT EXISTS devotional_templates (
            id SERIAL PRIMARY KEY,
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            prompt_1 TEXT NOT NULL,
            prompt_2 TEXT NOT NULL,
            default_passage TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_devotional_templates_slug
            ON devotional_templates (LOWER(slug));
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS uq_devotional_templates_slug;
        DROP TABLE IF EXISTS devotional_templates;

        DROP TABLE IF EXISTS reading_plan_entries;
        DROP INDEX IF EXISTS uq_reading_plans_slug;
        DROP TABLE IF EXISTS reading_plans;

        DROP INDEX IF EXISTS idx_topic_index_keywords;
        DROP INDEX IF EXISTS idx_topic_index_topic;
        DROP TABLE IF EXISTS topic_index;

        DROP INDEX IF EXISTS idx_lexicon_entries_lemma;
        DROP INDEX IF EXISTS uq_lexicon_entries_strongs;
        DROP TABLE IF EXISTS lexicon_entries;

        DROP INDEX IF EXISTS uq_cross_references_lookup;
        DROP TABLE IF EXISTS cross_references;
        """
    )
