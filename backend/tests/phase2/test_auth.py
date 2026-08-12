from __future__ import annotations

from app.db import Repository, SiteModel, UserModel
from app.config import get_settings


def test_all_seeded_users_can_sign_in_and_me_is_role_scoped(client, login_as):
    accounts = [
        "operator1@nexusai.demo", "operator2@nexusai.demo", "operator3@nexusai.demo",
        "lead1@nexusai.demo", "lead2@nexusai.demo", "lead3@nexusai.demo",
        "manager1@nexusai.demo", "manager2@nexusai.demo", "manager3@nexusai.demo",
        "quality1@nexusai.demo", "quality2@nexusai.demo", "quality3@nexusai.demo",
        "director@nexusai.demo", "auditor@nexusai.demo", "admin@nexusai.demo",
    ]
    for email in accounts:
        headers = login_as(client, email)
        principal = client.get("/api/auth/me", headers=headers)
        assert principal.status_code == 200
        assert principal.json()["email"] == email
        assert "permitted_sites" in principal.json()


def test_signin_rejects_wrong_password_and_signout_invalidates_session(client):
    assert client.post("/api/auth/signin", json={"email": "operator1@nexusai.demo", "password": "wrong"}).status_code == 401
    headers = {"Authorization": f"Bearer {client.post('/api/auth/signin', json={'email': 'operator1@nexusai.demo', 'password': 'nexusai2026'}).json()['session_token']}"}
    assert client.post("/api/auth/signout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_sites_and_invalid_tokens_are_protected(client, login_as):
    assert client.get("/api/sites").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer forged"}).status_code == 401
    headers = login_as(client, "operator1@nexusai.demo")
    sites = client.get("/api/sites", headers=headers)
    assert sites.status_code == 200
    assert {site["site_id"] for site in sites.json()["items"]} == {"wolfsburg"}


def test_seed_has_three_sites_and_fifteen_users():
    repository = Repository(get_settings())
    with repository.session() as session:
        assert len(session.query(SiteModel).all()) == 3
        seeded = {row.email for row in session.query(UserModel).all() if row.email.endswith("@nexusai.demo") and row.email != "new@nexusai.demo"}
        assert len(seeded) >= 15
