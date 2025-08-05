# Integration Tests Setup Guide

This guide helps you set up and run integration tests for the Bible Q&A FastAPI application.

## Prerequisites

1. **PostgreSQL**: Ensure PostgreSQL is installed and running
   ```bash
   # macOS with Homebrew
   brew install postgresql
   brew services start postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   sudo systemctl start postgresql
   ```

2. **Database User**: Ensure you have a PostgreSQL user with database creation privileges
   ```sql
   -- Connect to PostgreSQL as superuser
   CREATE USER postgres WITH PASSWORD 'postgres';
   ALTER USER postgres CREATEDB;
   ```

## Configuration

1. **Test Environment File**: Create `.env.test` with your test database configuration:
   ```bash
   cp .env.example .env.test
   ```
   
   Update `.env.test` with your test database settings:
   ```bash
   DB_NAME=bible_qa_test
   DB_USER=postgres
   DB_PASSWORD=postgres
   DB_HOST=localhost
   DB_PORT=5432
   ```

## Running Integration Tests

### Option 1: Using the Python Runner (Recommended)
```bash
# Automatic setup, run tests, and cleanup
python run_integration_tests.py
```

### Option 2: Using the Shell Script
```bash
# On macOS/Linux
chmod +x scripts/run_integration_tests.sh
./scripts/run_integration_tests.sh
```

### Option 3: Manual pytest
```bash
# Load test environment and run tests manually
export $(cat .env.test | xargs)
pytest tests/integration/ -v -m integration
```

## What Integration Tests Cover

1. **Database Operations**:
   - Real PostgreSQL database connections
   - CRUD operations with actual data persistence
   - Multi-user data isolation
   - Pagination and limits

2. **API Endpoints**:
   - End-to-end request/response flow
   - Database integration with API calls
   - Error handling with real database
   - Authentication and authorization (if implemented)

3. **Service Integration**:
   - OpenAI API integration (mocked for cost control)
   - Database + API + Service layer interaction
   - Real error scenarios and recovery

## Test Database Management

- **Automatic**: The test runners handle database creation and cleanup
- **Manual Cleanup**: If needed, you can manually clean up:
  ```sql
  DROP DATABASE IF EXISTS bible_qa_test;
  ```

## Troubleshooting

### PostgreSQL Connection Issues
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Check if user exists and can connect
psql -h localhost -U postgres -d postgres -c "SELECT version();"
```

### Permission Issues
```sql
-- Grant necessary permissions
ALTER USER postgres CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE bible_qa_test TO postgres;
```

### Environment Variable Issues
```bash
# Verify environment variables are loaded
python -c "from dotenv import load_dotenv; load_dotenv('.env.test'); import os; print(os.getenv('DB_NAME'))"
```

## CI/CD Integration

For continuous integration, add these steps to your workflow:

```yaml
# GitHub Actions example
- name: Start PostgreSQL
  run: |
    sudo systemctl start postgresql
    sudo -u postgres createuser --createdb --login runner
    
- name: Run Integration Tests
  run: python run_integration_tests.py
```
