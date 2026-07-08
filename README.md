# NotifyQueue

A distributed, delayed job & notification delivery system built with FastAPI, PostgreSQL, and Redis.

Designed to be the "Gold Standard" for scheduling and delivering notifications (Email, SMS, Push) with strict exactly-once delivery guarantees, graceful retry mechanisms, and horizontal scalability.

## Features

- **Robust Scheduling:** Schedule notifications for immediate delivery or delayed to an absolute timestamp (`send_at`) or relative delay (`delay_seconds`).
- **Distributed Concurrency:** Run multiple worker processes safely. Uses a dual-layer lock (Redis `SET NX EX` + Postgres Compare-And-Swap) to guarantee exactly-once delivery without database contention.
- **Priority Queues:** 5-tier priority system (Critical to Bulk) ensures important messages skip the line.
- **Sliding Window Rate Limiting:** Built-in Redis-backed rate limiting ($O(\log N)$ via Sorted Sets) prevents spamming users.
- **Fault Tolerance:** Exponential backoff with jitter for transient network failures. Hard failures are routed to a Dead Letter Queue (DLQ) to prevent poison message loops.
- **Webhooks:** Push-based event system. Register webhooks to receive real-time HTTP POSTs when jobs are sent, failed, or dead-lettered.

## Architecture & Design

Please refer to the detailed [DESIGN.md](./DESIGN.md) document for a deep dive into the architecture, the Redis/Postgres locking model, and trade-offs made.

## Quick Start (Docker)

The easiest way to run the application is via Docker Compose, which spins up PostgreSQL and Redis automatically.

### 1. Start Infrastructure

```bash
docker-compose up -d
```
*Wait a few seconds for Postgres and Redis to become healthy.*

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
