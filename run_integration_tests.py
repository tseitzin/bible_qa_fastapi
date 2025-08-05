#!/usr/bin/env python3
"""
Integration Test Runner for Bible Q&A FastAPI

This script provides an easy way to run integration tests with proper setup.
"""

import os
import sys
import subprocess
import psycopg2
from dotenv import load_dotenv


def load_test_env():
    """Load test environment variables."""
    test_env_path = ".env.test"
    if not os.path.exists(test_env_path):
        print("❌ .env.test file not found!")
        print("Please ensure .env.test exists with test database configuration.")
        sys.exit(1)
    
    load_dotenv(test_env_path, override=True)
    return {
        'DB_NAME': os.getenv('DB_NAME'),
        'DB_USER': os.getenv('DB_USER'),
        'DB_PASSWORD': os.getenv('DB_PASSWORD'),
        'DB_HOST': os.getenv('DB_HOST'),
        'DB_PORT': os.getenv('DB_PORT', '5432')
    }


def check_postgresql(db_config):
    """Check if PostgreSQL is accessible."""
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=db_config['DB_USER'],
            password=db_config['DB_PASSWORD'],
            host=db_config['DB_HOST'],
            port=db_config['DB_PORT']
        )
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print(f"Please ensure PostgreSQL is running on {db_config['DB_HOST']}:{db_config['DB_PORT']}")
        return False


def setup_test_database(db_config):
    """Set up the test database and tables."""
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            dbname="postgres",
            user=db_config['DB_USER'],
            password=db_config['DB_PASSWORD'],
            host=db_config['DB_HOST'],
            port=db_config['DB_PORT']
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Drop and create test database
        print(f"🗃️  Setting up test database: {db_config['DB_NAME']}")
        cur.execute(f"DROP DATABASE IF EXISTS {db_config['DB_NAME']}")
        cur.execute(f"CREATE DATABASE {db_config['DB_NAME']}")
        
        cur.close()
        conn.close()
        
        # Connect to test database and create tables
        test_conn = psycopg2.connect(
            dbname=db_config['DB_NAME'],
            user=db_config['DB_USER'],
            password=db_config['DB_PASSWORD'],
            host=db_config['DB_HOST'],
            port=db_config['DB_PORT']
        )
        test_cur = test_conn.cursor()
        
        # Create tables
        print("📋 Creating database tables...")
        test_cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT,
                email TEXT
            );
            
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                question TEXT NOT NULL,
                asked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            );
            
            CREATE TABLE IF NOT EXISTS answers (
                id SERIAL PRIMARY KEY,
                question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
                answer TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Insert some test users
            INSERT INTO users (id, username, email) VALUES 
                (100, 'test_user_100', 'user100@test.com'),
                (123, 'test_user_123', 'user123@test.com'),
                (200, 'test_user_200', 'user200@test.com'),
                (456, 'test_user_456', 'user456@test.com'),
                (789, 'test_user_789', 'user789@test.com'),
                (999, 'test_user_999', 'user999@test.com')
            ON CONFLICT (id) DO NOTHING;
        """)
        
        test_conn.commit()
        test_cur.close()
        test_conn.close()
        
        print("✅ Test database setup complete")
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database setup failed: {e}")
        return False


def cleanup_test_database(db_config):
    """Clean up the test database."""
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=db_config['DB_USER'],
            password=db_config['DB_PASSWORD'],
            host=db_config['DB_HOST'],
            port=db_config['DB_PORT']
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("🧹 Cleaning up test database...")
        cur.execute(f"DROP DATABASE IF EXISTS {db_config['DB_NAME']}")
        
        cur.close()
        conn.close()
        print("✅ Test database cleaned up")
        
    except psycopg2.Error as e:
        print(f"⚠️  Cleanup warning: {e}")


def run_integration_tests():
    """Run the integration tests."""
    print("🧪 Running integration tests...")
    
    cmd = [
        "pytest", 
        "tests/integration/", 
        "-v", 
        "--tb=short",
        "-m", "integration",
        "--no-cov"  # Disable coverage for integration tests
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    """Main function to orchestrate integration test setup and execution."""
    print("🚀 Bible Q&A FastAPI Integration Test Runner")
    print("=" * 50)
    
    # Load test environment
    print("🔧 Loading test environment...")
    db_config = load_test_env()
    
    # Check PostgreSQL connectivity
    print("🔍 Checking PostgreSQL connectivity...")
    if not check_postgresql(db_config):
        sys.exit(1)
    
    print("✅ PostgreSQL is accessible")
    
    # Setup test database
    if not setup_test_database(db_config):
        sys.exit(1)
    
    try:
        # Run integration tests
        test_success = run_integration_tests()
        
        if test_success:
            print("\n🎉 All integration tests passed!")
        else:
            print("\n❌ Some integration tests failed")
            
    finally:
        # Always cleanup
        cleanup_test_database(db_config)
    
    sys.exit(0 if test_success else 1)


if __name__ == "__main__":
    main()
