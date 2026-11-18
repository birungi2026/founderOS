import time
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import project, register
from cryptography.fernet import Fernet
from sqlalchemy import select

from app import social
from app.models import Membership, SocialAccount, SocialAuthorization
from app.workflows.api import social_context


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for provider in ("INSTAGRAM", "FACEBOOK"):
        monkeypatch.setenv(provider + "_APP_ID", "123")
        monkeypatch.setenv(provider + "_APP_SECRET", "secret")
        monkeypatch.setenv(
            provider + "_REDIRECT_URI",
            "http://localhost:8000/v1/social/" + provider.lower() + "/callback",
        )


def authorize(client, pid, provider="instagram"):
    response = client.post(f"/v1/projects/{pid}/social/{provider}/connect", json={})
    assert response.status_code == 200, response.text
    return parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]


def fake_provider(monkeypatch, provider="instagram"):
    calls = []

    def call(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url == "https://api.instagram.com/oauth/access_token":
            return {
                "data": [
                    {"access_token": "short-secret", "permissions": "instagram_business_basic"}
                ]
            }
        if url.endswith("/access_token"):
            return {"access_token": "long-secret", "expires_in": 5184000}
        if url.endswith("/oauth/access_token"):
            return {"access_token": "long-secret", "expires_in": 5184000}
        if url.endswith("/me/permissions"):
            return {
                "data": [{"permission": p, "status": "granted"} for p in social.SCOPES[provider]]
            }
        if url.endswith("/me/accounts"):
            return {"data": [{"id": "1234", "name": "Founder page", "access_token": "page-secret"}]}
        if url.endswith("/media") or url.endswith("/posts"):
            return {
                "data": [
                    {
                        "id": "post1",
                        "caption": "Founder story",
                        "message": "Hello",
                        "access_token": "never-store",
                    }
                ],
                "paging": {"next": "https://evil.test"},
            }
        return {
            "user_id": "1234",
            "username": "founder",
            "name": "Founder page",
            "followers_count": 42,
            "access_token": "never-store",
        }

    monkeypatch.setattr(social, "call", call)
    return calls


@pytest.mark.parametrize("provider", ["instagram", "facebook"])
def test_connect_sync_disconnect(client, database, configured, monkeypatch, provider):
    register(client)
    pid = project(client)
    calls = fake_provider(monkeypatch, provider)
    state = authorize(client, pid, provider)
    response = client.get(
        f"/v1/social/{provider}/callback", params={"state": state, "code": "code"}
    )
    assert response.status_code == 200, response.text
    assert (
        client.get(
            f"/v1/social/{provider}/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )
    data = client.get(f"/v1/projects/{pid}/social").json()
    assert "secret" not in str(data)
    account = data["accounts"][0]
    with database() as db:
        stored = db.get(SocialAccount, account["id"])
        assert "secret" not in stored.encrypted_token
        assert social.vault().decrypt(stored.encrypted_token.encode()) in {
            b"long-secret",
            b"page-secret",
        }
    result = client.post(f"/v1/social/accounts/{account['id']}/sync", json={})
    assert result.status_code == 200, result.text
    assert result.json()["snapshot"]["profile"]["followers_count"] == 42
    assert "secret" not in result.text and "evil.test" not in result.text
    with database() as db:
        context = social_context(db, pid)
        assert context and "secret" not in str(context)
    assert all("evil.test" not in url for _, url, _ in calls)
    assert (
        client.post(f"/v1/social/accounts/{account['id']}/disconnect", json={}).status_code == 200
    )
    with database() as db:
        stored = db.get(SocialAccount, account["id"])
        assert stored.encrypted_token == "" and stored.snapshot == {}
        assert social_context(db, pid) == []
    assert client.post(f"/v1/social/accounts/{account['id']}/sync", json={}).status_code == 409


def test_oauth_is_bound_to_session_owner_project_and_expiry(
    client, database, configured, monkeypatch
):
    org = register(client)
    pid = project(client)
    state = authorize(client, pid)
    fake_provider(monkeypatch)
    register(client, "other@example.com")
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )
    assert client.get(f"/v1/projects/{pid}/social").status_code == 404
    assert client.post(f"/v1/projects/{pid}/social/instagram/connect", json={}).status_code == 404
    with database() as db:
        row = db.scalar(select(SocialAuthorization))
        row.expires_at = time.time() - 1
        db.commit()
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "viewer"
        db.commit()


def test_unconfigured_and_denied_flow(client, configured, monkeypatch, database):
    register(client)
    pid = project(client)
    state = authorize(client, pid)
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "error": "access_denied"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "code": "x"}
        ).status_code
        == 400
    )
    monkeypatch.delenv("SOCIAL_TOKEN_ENCRYPTION_KEY")
    assert client.post(f"/v1/projects/{pid}/social/instagram/connect", json={}).status_code == 503
    assert not client.get(f"/v1/projects/{pid}/social").json()["providers"][0]["configured"]


def test_revoked_owner_and_missing_scope_cannot_connect(client, database, configured, monkeypatch):
    org = register(client)
    pid = project(client)
    state = authorize(client, pid)
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "viewer"
        db.commit()
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "code": "code"}
        ).status_code
        == 403
    )
    assert client.post(f"/v1/projects/{pid}/social/instagram/connect", json={}).status_code == 403
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "owner"
        db.commit()
    monkeypatch.setattr(
        social, "call", lambda *a, **k: {"access_token": "secret", "permissions": []}
    )
    assert (
        client.get(
            "/v1/social/instagram/callback", params={"state": state, "code": "code"}
        ).status_code
        == 400
    )
    with database() as db:
        assert db.scalar(select(SocialAccount)) is None


def test_cross_tenant_sync_and_disconnect_denied(client, configured, monkeypatch):
    register(client)
    pid = project(client)
    fake_provider(monkeypatch)
    state = authorize(client, pid)
    client.get("/v1/social/instagram/callback", params={"state": state, "code": "code"})
    aid = client.get(f"/v1/projects/{pid}/social").json()["accounts"][0]["id"]
    register(client, "outsider@example.com")
    assert client.post(f"/v1/social/accounts/{aid}/sync", json={}).status_code == 404
    assert client.post(f"/v1/social/accounts/{aid}/disconnect", json={}).status_code == 404
