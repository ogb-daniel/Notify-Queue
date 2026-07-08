
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestIdempotency:
    async def test_duplicate_idempotency_key_returns_409(self, client: AsyncClient):
        key = f"idempotent-{uuid.uuid4().hex}"
        job_data = {
            "recipient": "user@example.com",
            "channel": "email",
            "payload": {"subject": "Test"},
            "idempotency_key": key,
        }

        resp1 = await client.post("/api/v1/jobs", json=job_data)
        assert resp1.status_code == 201
        job1_id = resp1.json()["id"]

        resp2 = await client.post("/api/v1/jobs", json=job_data)
        assert resp2.status_code == 409

        detail = resp2.json()["detail"]
        assert detail["existing_job"]["id"] == job1_id

    async def test_different_keys_create_separate_jobs(self, client: AsyncClient):
        base_data = {
            "recipient": "user@example.com",
            "channel": "email",
            "payload": {"subject": "Test"},
        }

        resp1 = await client.post("/api/v1/jobs", json={
            **base_data,
            "idempotency_key": f"key-{uuid.uuid4().hex}",
        })
        resp2 = await client.post("/api/v1/jobs", json={
            **base_data,
            "idempotency_key": f"key-{uuid.uuid4().hex}",
        })

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]
