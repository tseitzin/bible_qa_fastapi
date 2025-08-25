#!/usr/bin/env python3
"""
Database setup script for Heroku deployment.
This script creates the necessary database tables after deployment.
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment variables."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not found")
        sys.exit(1)
    return database_url


def parse_database_url(database_url):
    """Parse Heroku DATABASE_URL into connection parameters."""
    parsed = urlparse(database_url)
    return {
        'host': parsed.hostname,
        'port': parsed.port,
        'database': parsed.path[1:],  # Remove leading slash
        'user': parsed.username,
        'password': parsed.password
    }


def create_tables(conn_params):
    """Create database tables."""
    try:
        # Connect to database
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        
        logger.info("Creating database tables...")
        
        # Create tables
        cur.execute("""
            -- Create questions table
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                asked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create answers table
            CREATE TABLE IF NOT EXISTS answers (
                id SERIAL PRIMARY KEY,
                question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
                answer TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS idx_questions_user_id ON questions(user_id);
            CREATE INDEX IF NOT EXISTS idx_questions_asked_at ON questions(asked_at);
            CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id);
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("✅ Database tables created successfully")
        
    except psycopg2.Error as e:
        logger.error(f"❌ Database setup failed: {e}")
        sys.exit(1)


def main():
    """Main function to set up the database."""
    logger.info("🚀 Setting up database for Bible Q&A API...")
    
    # Get database URL
    database_url = get_database_url()
    
    # Parse connection parameters
    conn_params = parse_database_url(database_url)
    
    # Create tables
    create_tables(conn_params)
    
    logger.info("🎉 Database setup completed successfully!")


if __name__ == "__main__":
    main()