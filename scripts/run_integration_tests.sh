#!/bin/bash

# Integration Test Setup Script
# This script sets up the test database and runs integration tests

set -e  # Exit on any error

echo "🔧 Setting up integration test environment..."

# Load test environment variables
export $(cat .env.test | xargs)

# Check if PostgreSQL is running
if ! pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running or not accessible"
    echo "Please ensure PostgreSQL is running on $DB_HOST:$DB_PORT"
    echo "You can start it with: brew services start postgresql (on macOS)"
    exit 1
fi

echo "✅ PostgreSQL is running"

# Create test database if it doesn't exist
echo "🗃️  Setting up test database: $DB_NAME"

# Connect to postgres database to create test database
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
" > /dev/null 2>&1

echo "✅ Test database '$DB_NAME' created"

# Create tables in test database
echo "📋 Creating database tables..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
" > /dev/null 2>&1

echo "✅ Database tables created"

# Run integration tests
echo "🧪 Running integration tests..."
pytest tests/integration/ -v --tb=short

# Cleanup test database
echo "🧹 Cleaning up test database..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "
DROP DATABASE IF EXISTS $DB_NAME;
" > /dev/null 2>&1

echo "✅ Integration tests completed and cleaned up"
