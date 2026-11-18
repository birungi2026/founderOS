import time

import pytest
from conftest import project, register
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import LoginSession, Project, User


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_growth_workflow(client):
    register(client)
    pid = project(client)
    assert client.post(f"/projects/{pid}/strategy").json()["generation_mode"] == "template"
    drafts = client.post(f"/projects/{pid}/drafts").json()["drafts"]
    assert len(drafts) == 2
    did = drafts[0]["id"]
    assert client.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 409
    assert client.post(f"/drafts/{did}/review?decision=approved").json()["status"] == "approved"
    assert client.post(f"/drafts/{did}/review?decision=rejected").status_code == 409
    assert client.post(f"/drafts/{did}/publish", json={"confirm": False}).status_code == 422
    assert client.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 202
    assert client.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 409
    assert (
        client.get(f"/projects/{pid}/publications").json()["publications"][0]["status"] == "queued"
    )
    client.post(
        f"/projects/{pid}/metrics",
        json={
            "channel": "linkedin",
            "impressions": 200,
            "leads": 10,
            "signups": 4,
            "paying_customers": 1,
        },
    )
    assert client.get(f"/projects/{pid}/analytics").json()["totals"]["signup_to_paid_rate"] == 25
    actions = [e["action"] for e in client.get("/organization/audit").json()["events"]]
    assert "publication.queued" in actions and "draft.approved" in actions


def test_auth_storage_expiry(client, database):
    assert client.get("/projects").status_code == 401
    register(client)
    with database() as db:
        assert db.scalar(select(User)).password_hash != "a-long-test-password"
    r = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "a-long-test-password"},
    )
    assert "HttpOnly" in r.headers["set-cookie"]
    with database() as db:
        for row in db.scalars(select(LoginSession)):
            row.expires_at = time.time() - 1
        db.commit()
    assert client.get("/auth/me").status_code == 401
    assert (
        client.post(
            "/auth/login",
            json={"email": "owner@example.com", "password": "wrong-password-long"},
        ).status_code
        == 401
    )


def test_logout_revokes_token(client):
    register(client)
    cookie = client.cookies.get("founderos_session")
    client.post("/auth/logout")
    client.cookies.set("founderos_session", cookie)
    assert client.get("/auth/me").status_code == 401


def test_tenant_isolation(client):
    org = register(client)
    pid = project(client)
    did = client.post(f"/projects/{pid}/drafts").json()["drafts"][0]["id"]
    with TestClient(app) as other:
        register(other, "other@example.com")
        assert other.get("/projects").json() == {"projects": []}
        assert other.get("/projects", headers={"X-Organization-ID": org}).status_code == 403
        for suffix in [
            "",
            "/drafts",
            "/sources",
            "/analytics",
            "/analytics.csv",
            "/publications",
        ]:
            assert other.get(f"/projects/{pid}{suffix}").status_code == 404
        for suffix in ["strategy", "drafts"]:
            assert other.post(f"/projects/{pid}/{suffix}").status_code == 404
        assert other.post(f"/drafts/{did}/review?decision=approved").status_code == 404
        assert other.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 404


def test_roles(client):
    org = register(client)
    pid = project(client)
    with TestClient(app) as viewer:
        register(viewer, "viewer@example.com")
        assert (
            client.post(
                "/organization/members",
                json={"email": "viewer@example.com", "role": "viewer"},
            ).status_code
            == 200
        )
        h = {"X-Organization-ID": org}
        assert viewer.get(f"/projects/{pid}", headers=h).status_code == 200
        assert viewer.post(f"/projects/{pid}/drafts", headers=h).status_code == 403
        assert viewer.get("/organization/audit", headers=h).status_code == 403
        assert (
            viewer.post(
                "/organization/members",
                headers=h,
                json={"email": "owner@example.com", "role": "editor"},
            ).status_code
            == 403
        )
        client.post(
            "/organization/members",
            json={"email": "viewer@example.com", "role": "editor"},
        )
        assert viewer.post(f"/projects/{pid}/drafts", headers=h).status_code == 200
    assert (
        client.post(
            "/organization/members",
            json={"email": "owner@example.com", "role": "viewer"},
        ).status_code
        == 409
    )


def test_persistence(client, database):
    register(client)
    pid = project(client)
    with database() as db:
        assert db.get(Project, pid).data["product_name"] == "Qopanza"
    with TestClient(app) as restored:
        restored.post(
            "/auth/login",
            json={"email": "owner@example.com", "password": "a-long-test-password"},
        )
        assert restored.get("/projects").json()["projects"][0]["id"] == pid


def test_sources(client):
    register(client)
    pid = project(client)
    s = {
        "url": "https://example.com/research",
        "title": "Interview summary",
        "excerpt": "Customers need faster security reviews.",
        "permission_confirmed": True,
    }
    assert (
        client.post(
            f"/projects/{pid}/sources", json={**s, "permission_confirmed": False}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/projects/{pid}/sources", json={**s, "url": "javascript:alert(1)"}
        ).status_code
        == 422
    )
    assert (
        client.post(f"/projects/{pid}/sources", json=s).json()["verification"]
        == "operator_attested"
    )
    assert len(client.get(f"/projects/{pid}/sources").json()["sources"]) == 1


def test_events(client):
    register(client)
    pid = project(client)
    e = {
        "external_id": "crm-001",
        "kind": "signup",
        "channel": "linkedin",
        "campaign": "launch",
    }
    assert client.post(f"/projects/{pid}/events", json=e).json()["duplicate"] is False
    assert client.post(f"/projects/{pid}/events", json=e).json()["duplicate"] is True
    assert client.post(f"/projects/{pid}/events", json={**e, "kind": "lead"}).status_code == 409
    a = client.get(f"/projects/{pid}/analytics").json()
    assert a["totals"]["signups"] == 1 and a["campaigns"]["launch"]["signups"] == 1
    assert a["totals"]["signup_to_paid_rate"] == 0


def test_csv(client):
    register(client)
    pid = project(client)
    client.post(f"/projects/{pid}/metrics", json={"channel": "=SUM(1)", "leads": 2})
    assert "'=SUM(1)" in client.get(f"/projects/{pid}/analytics.csv").text


def test_csrf_and_rate_limit(client):
    assert (
        client.post("/auth/logout", headers={"origin": "https://evil.example"}).status_code == 403
    )
    for _ in range(15):
        assert client.post("/auth/logout").status_code == 200
    assert client.post("/auth/logout").status_code == 429


@pytest.mark.parametrize(
    "email,password", [("bad", "a-long-test-password"), ("ok@example.com", "short")]
)
def test_validation(client, email, password):
    assert (
        client.post(
            "/auth/register",
            json={"email": email, "password": password, "organization_name": "Org"},
        ).status_code
        == 422
    )
