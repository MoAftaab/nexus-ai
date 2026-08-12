from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app, store


@pytest.fixture
def client():
    # Each integration test owns a fresh source twin. This prevents a valid
    # approval in one test from resolving the finding required by another.
    store.reset_demo()
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str):
    response = client.post("/api/auth/signin", json={"email": email, "password": "nexusai2026"})
    assert response.status_code == 200, response.text
    token = response.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def login_as():
    return login
