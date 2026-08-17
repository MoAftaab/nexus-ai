from __future__ import annotations

import os
import tempfile
from pathlib import Path

test_database = Path(tempfile.gettempdir()) / f"warehouse_control_tower_pytest_{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_database.as_posix()}"
os.environ["DEMO_SEED"] = "1234"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ALLOW_LEGACY_DIRECT_APPLY"] = "true"

import pytest
from fastapi.testclient import TestClient

from main import app, store
from app.services.auth import seed_users_and_sites


@pytest.fixture
def client():
    # Each integration test owns a fresh source twin. This prevents a valid
    # approval in one test from resolving the finding required by another.
    store.reset_demo()
    seed_users_and_sites(store.repository)
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
