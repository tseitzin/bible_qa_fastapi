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

## Bible Data Import

- Run database migrations from `backend/`: `alembic upgrade head`
- Confirm the `kjv.xlsx` workbook exists in the repository root (default path)
- Load verses: `python scripts/import_bible.py --excel-path ../kjv.xlsx`
- Validate without writing by adding `--dry-run`

### Study Resource Import (TSK, Lexicon, Topics, Plans, Devotionals)

- Default datasets live under `app/data/reference_data/` (JSON files kept small for development but scale linearly if you swap in the full public-domain exports).
- After running migrations, load them with:
  ```bash
  python scripts/import_study_resources.py
  ```
- Use `--data-dir <path>` to point at a custom dataset directory or `--skip cross lexicon ...` to avoid reloading specific tables.
- All MCP utility tools now query these tables directly, so no additional API spend is required. Storage cost stays minimal (<10 MB using public TSK + lexicon). The added indexes keep lookups under ~5 ms on a small Postgres dyno; drop specific datasets if you are memory constrained.

## API Endpoints

- `GET /` - Health check
- `POST /api/ask` - Submit a Bible question
- `GET /api/history/{user_id}` - Get question history
- `GET /api/bible/verse?ref=John%203:16` - Retrieve a specific Bible verse by reference (`/api/verse` alias available)

## Environment Variables

See `.env.example` for required configuration.

## Deployment

### Heroku Deployment

This project is configured for easy Heroku deployment:

1. **Prerequisites:**

   ```bash
   # Install Heroku CLI
   # macOS: brew install heroku/brew/heroku
   # Windows: Download from https://devcenter.heroku.com/articles/heroku-cli

   # Login to Heroku
   heroku login
   ```

2. **Deploy to Heroku:**

   ```bash
   # Create Heroku app
   heroku create your-bible-qa-api

   # Add PostgreSQL addon
   heroku addons:create heroku-postgresql:essential-0

   # Set environment variables
   heroku config:set OPENAI_API_KEY=your_openai_api_key_here
   heroku config:set ALLOWED_ORIGINS=https://your-vue-app.netlify.app,https://your-vue-app.vercel.app

   # Deploy
   git push heroku main

   # Database tables will be created automatically via postdeploy script
   ```

3. **One-Click Deploy:**
   [![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

4. **Environment Variables for Heroku:**
   - `OPENAI_API_KEY`: Your OpenAI API key (required)
   - `ALLOWED_ORIGINS`: Comma-separated list of allowed CORS origins (include your Vue.js app URL)
   - `DEBUG`: Set to `false` for production
   - `DATABASE_URL`: Automatically set by Heroku PostgreSQL addon

### Frontend Integration

To connect your Vue.js frontend:

1. **Update your Vue.js API base URL:**

   ```javascript
   // In your Vue.js app
   const API_BASE_URL =
     process.env.NODE_ENV === "production"
       ? "https://your-bible-qa-api.herokuapp.com"
       : "http://localhost:8000";
   ```

2. **Add your frontend URL to CORS:**

   ```bash
   # Add your deployed frontend URL to allowed origins
   heroku config:set ALLOWED_ORIGINS=https://your-vue-app.netlify.app,http://localhost:5173
   ```

3. **API Endpoints for your Vue.js app:**
   - `GET /` - Health check
   - `POST /api/ask` - Submit Bible questions
   - `GET /api/history/{user_id}` - Get question history

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
