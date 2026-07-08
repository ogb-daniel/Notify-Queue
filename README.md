# NotifyQueue

A distributed, delayed job & notification delivery system built with FastAPI, PostgreSQL, and Redis.

## Architecture & Design

Please refer to the detailed [DESIGN.md](./DESIGN.md) document for a deep dive into the architecture, the Redis/Postgres locking model, and trade-offs made.

## Quick Start (Docker)

The easiest way to run the application is via Docker Compose, which spins up PostgreSQL and Redis automatically.

### 1. Start Infrastructure

```bash
docker-compose up -d
```

_Wait a few seconds for Postgres and Redis to become healthy._

### 2. Install Dependencies

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the API Server

The API runs on port 8000. It will automatically create the database tables on startup.

```bash
# Export environment variables matching docker-compose
export POSTGRES_USER=notify
export POSTGRES_PASSWORD=notify
export POSTGRES_DB=notifyqueue

uvicorn src.main:app --reload
```

Interactive API Documentation: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### 4. Start Worker Processes

Workers poll the database and deliver notifications. You can run multiple workers in separate terminal windows to see distributed locking in action.

```bash
export POSTGRES_USER=notify
export POSTGRES_PASSWORD=notify
export POSTGRES_DB=notifyqueue

# Terminal 1
python -m src.worker --worker-id=worker-alpha

# Terminal 2
python -m src.worker --worker-id=worker-beta
```

## Seeding Data

To test performance or see workers process a backlog, use the seed script:

```bash
export POSTGRES_USER=notify
export POSTGRES_PASSWORD=notify
export POSTGRES_DB=notifyqueue
export PYTHONPATH=.

# Insert 1,000 randomized jobs
python scripts/seed.py --count 1000
```

## Running Tests

Tests use a real PostgreSQL and Redis instance to accurately test concurrency and locking.

```bash
# Run all tests
export TEST_DATABASE_URL="postgresql+asyncpg://notify:notify@localhost:5432/notifyqueue"
export TEST_REDIS_URL="redis://localhost:6379/1"

pytest -v
```
