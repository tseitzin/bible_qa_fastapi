#!/usr/bin/env python3
"""Create the lexicon_entries table."""
from __future__ import annotations

import sys
from pathlib import Path

# Add the parent directory of the script (backend/) to sys.path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from app.database import get_db_connection

def create_lexicon_table():
    """Create the lexicon_entries table and index."""
    sql = """
    CREATE TABLE IF NOT EXISTS lexicon_entries (
        id SERIAL PRIMARY KEY,
        strongs_number TEXT NOT NULL UNIQUE,
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
    
    CREATE INDEX IF NOT EXISTS idx_lexicon_entries_strongs_number 
        ON lexicon_entries(strongs_number);
    """
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        print('✅ lexicon_entries table created successfully')

if __name__ == "__main__":
    create_lexicon_table()
