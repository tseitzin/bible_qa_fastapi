# Bible Q&A FastAPI Application

A RESTful API for asking Bible-related questions powered by OpenAI's GPT models.

## Features

- 🤖 AI-powered Bible Q&A using OpenAI
- 📚 Question and answer history storage
- 🔒 Environment-based configuration
- 🚀 Ready for deployment on Heroku
- 📊 Structured logging and error handling
- 🧪 Clean architecture with separation of concerns

## Project Structure

```
bible_qa_fastapi/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database operations
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── services/
│   │   ├── openai_service.py    # OpenAI integration
│   │   └── question_service.py  # Business logic
│   └── utils/
│       └── exceptions.py    # Custom exceptions
├── scripts/
│   └── create_tables.sql    # Database schema
├── tests/                   # Test files
├── requirements.txt         # Python dependencies
├── Procfile                # Heroku configuration
└── .env.example            # Environment template
```

## Setup

1. **Clone and setup environment:**
   ```bash
   cd bible_qa_fastapi
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Setup database:**
   - Create a PostgreSQL database
   - Run the SQL script: `psql -d your_db -f scripts/create_tables.sql`

4. **Run locally:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Run tests:**
   ```bash
   # Install test dependencies (if not already installed)
   pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
   
   # Run only unit tests (fast, no external dependencies)
   pytest tests/ -m "not integration" -v
   
   # Run only integration tests (requires database setup)
   pytest tests/ -m integration -v
   
   # Run all tests
   pytest tests/ -v
   
   # Run tests with coverage
   pytest tests/ -v --cov=app --cov-report=term-missing
   
   # Run specific test file
   pytest tests/test_main.py -v
   
   # Use test category runner
   python run_test_categories.py unit
   python run_test_categories.py integration
   python run_test_categories.py all
   python run_test_categories.py coverage
   ```

## API Endpoints

- `GET /` - Health check
- `POST /api/ask` - Submit a Bible question
- `GET /api/history/{user_id}` - Get question history

## Environment Variables

See `.env.example` for required configuration.

## Deployment

This project is configured for Heroku deployment with the included `Procfile`.

## Architecture Benefits

✅ **Separation of Concerns**: Clear separation between API, business logic, and data access  
✅ **Configuration Management**: Centralized settings with environment variables  
✅ **Error Handling**: Structured exception handling and logging  
✅ **Type Safety**: Pydantic models for request/response validation  
✅ **Testability**: Modular design enables easy unit testing  
✅ **Scalability**: Clean architecture supports future enhancements  
✅ **Test Coverage**: Comprehensive unit tests with mocking  

## Testing

The project includes comprehensive unit tests covering:

- **API Endpoints**: All FastAPI routes with various scenarios
- **Business Logic**: Service layer with mocked dependencies  
- **Database Operations**: Repository pattern with connection management
- **External APIs**: OpenAI service with error handling
- **Error Scenarios**: Custom exceptions and edge cases

### Test Structure:
```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── test_main.py            # API endpoint tests (unit)
├── test_question_service.py # Business logic tests (unit)
├── test_openai_service.py   # OpenAI integration tests (unit)
├── test_database.py        # Database operation tests (unit)
└── integration/            # Integration tests
    ├── __init__.py
    └── test_integration_example.py  # Real DB + API integration
```

### Test Categories:
- **Unit Tests** (39 tests): Fast, isolated, heavily mocked
- **Integration Tests**: Real database, real API calls, slower but more realistic

### Running Tests:
```bash
# Quick unit tests only (recommended for development)
pytest tests/ -m "not integration" -v

# Integration tests (requires PostgreSQL setup)
python run_integration_tests.py

# Or run integration tests manually
pytest tests/ -m integration -v

# All tests with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test categories with the runner script
python run_tests.py unit        # Fast unit tests
python run_tests.py integration # Integration tests  
python run_tests.py all         # All tests
python run_tests.py coverage    # All tests with coverage
```

For detailed integration test setup, see [docs/INTEGRATION_TESTS.md](docs/INTEGRATION_TESTS.md).
