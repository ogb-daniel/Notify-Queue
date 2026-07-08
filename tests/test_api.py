
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestScheduleJob:
    async def test_create_job_returns_201(self, client: AsyncClient):
        response = await client.post("/api/v1/jobs", json={
            "recipient": "user@example.com",
            "channel": "email",
            "payload": {"subject": "Test", "body": "Hello"},
            "priority": 3,
            "delay_seconds": 60,
            "idempotency_key": f"test-{uuid.uuid4().hex}",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["recipient"] == "user@example.com"
        assert data["channel"] == "email"
        assert data["priority"] == 3

    async def test_create_job_immediate(self, client: AsyncClient):
        response = await client.post("/api/v1/jobs", json={
            "recipient": "user@example.com",
            "channel": "sms",
            "payload": {"message": "Hello"},
            "idempotency_key": f"test-{uuid.uuid4().hex}",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"

    async def test_invalid_channel_returns_422(self, client: AsyncClient):
        response = await client.post("/api/v1/jobs", json={
            "recipient": "user@example.com",
            "channel": "carrier_pigeon",
            "payload": {},
            "idempotency_key": f"test-{uuid.uuid4().hex}",
        })
        assert response.status_code == 422

    async def test_missing_recipient_returns_422(self, client: AsyncClient):
        response = await client.post("/api/v1/jobs", json={
            "channel": "email",
            "payload": {},
            "idempotency_key": f"test-{uuid.uuid4().hex}",
        })
        assert response.status_code == 422

    async def test_priority_out_of_range_returns_422(self, client: AsyncClient):
        response = await client.post("/api/v1/jobs", json={
            "recipient": "user@example.com",
            "channel": "email",
            "payload": {},
            "priority": 99,
            "idempotency_key": f"test-{uuid.uuid4().hex}",
        })
        assert response.status_code == 422


@pytest.mark.asyncio
class TestGetJobStatus:
    async def test_get_existing_job(self, client: AsyncClient):
        key = f"test-{uuid.uuid4().hex}"
        create_resp = await client.post("/api/v1/jobs", json={
            "recipient": "user@example.com",
            "channel": "email",
            "payload": {},
            "idempotency_key": key,
        })
        job_id = create_resp.json()["id"]

        response = await client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

    async def test_get_nonexistent_job_returns_404(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v1/jobs/{fake_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestMetrics:
    async def test_metrics_returns_counts(self, client: AsyncClient):
        response = await client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "pending" in data
        assert "sent" in data
        assert "failed" in data
        assert "dead_lettered" in data
        assert "total" in data
