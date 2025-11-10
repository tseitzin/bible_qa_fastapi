# Backend Dockerfile with multi-stage optional (simple single stage for now)
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps for psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cache layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY tests ./tests
COPY scripts ./scripts
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY start.sh ./start.sh
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]