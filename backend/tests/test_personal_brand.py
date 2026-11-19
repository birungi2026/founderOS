from conftest import project, register
from sqlalchemy import select

from app.models import User


def test_signup_mode_persists_and_personal_progress_is_tenant_scoped(client, database):
    response = client.post(
        "/auth/register",
        json={
            "email": "creator@example.com",
            "password": "long-creator-password",
            "organization_name": "Creator workspace",
            "onboarding_mode": "personal",
        },
    )
    assert response.status_code == 201
    assert client.get("/auth/me").json()["onboarding_mode"] == "personal"
    payload = {
        "mode": "personal",
        "product_name": "Ada Writes",
        "description": "I share practical lessons about software engineering.",
        "audience": "Early career software developers",
        "personal_goal": "newsletter_subscribers",
        "personal_target": 500,
    }
    response = client.post("/projects", json=payload)
    assert response.status_code == 201, response.text
    pid = response.json()["id"]
    assert response.json()["problem"] == ""
    assert (
        client.post(
            f"/projects/{pid}/personal-progress", json={"current": 75, "expected_version": 0}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{pid}/personal-progress", json={"current": 80, "expected_version": 0}
        ).status_code
        == 409
    )
    p = client.get(f"/projects/{pid}").json()
    assert p["personal_current"] == 75 and p["personal_target"] == 500
    client.post("/auth/logout")
    client.post(
        "/auth/login", json={"email": "creator@example.com", "password": "long-creator-password"}
    )
    assert client.get("/auth/me").json()["onboarding_mode"] == "personal"
    register(client, "outsider@example.com")
    assert (
        client.post(
            f"/projects/{pid}/personal-progress", json={"current": 999, "expected_version": 1}
        ).status_code
        == 404
    )
    with database() as db:
        assert (
            db.scalar(select(User).where(User.email == "creator@example.com")).onboarding_mode
            == "personal"
        )


def test_legacy_signup_business_defaults_and_mode_validation(client):
    register(client)
    assert client.get("/auth/me").json()["onboarding_mode"] == "business"
    pid = project(client)
    assert client.get(f"/projects/{pid}").json()["mode"] == "business"
    assert (
        client.post(
            f"/projects/{pid}/personal-progress", json={"current": 1, "expected_version": 0}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/projects",
            json={
                "mode": "invalid",
                "product_name": "Test",
                "description": "A description long enough",
                "audience": "Developers",
            },
        ).status_code
        == 422
    )


def test_personal_automatic_research_does_not_require_company_problem(
    client, monkeypatch, database
):
    from app.models import WorkflowRun
    from app.workflows.agents import run_agent

    register(client)
    pid = client.post(
        "/projects",
        json={
            "mode": "personal",
            "product_name": "Ada Teaches",
            "description": "Practical software engineering education.",
            "audience": "Junior engineers",
            "personal_goal": "inquiries",
            "personal_target": 20,
        },
    ).json()["id"]
    brand = {
        "founder_name": "Ada Expert",
        "story": "I share lessons from years of mentoring software engineers.",
        "expertise": ["Engineering"],
        "content_pillars": ["Practical engineering"],
        "voice": "Warm and clear",
        "positioning": "I help junior engineers build confidence through practical lessons.",
    }
    response = client.post(f"/v1/projects/{pid}/brand", json=brand)
    assert response.status_code == 201, response.text
    bid = response.json()["id"]
    assert client.post(f"/v1/projects/{pid}/brand/{bid}/approve", json={}).status_code == 200
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fixture-key")
    response = client.post(
        f"/v1/projects/{pid}/workflows",
        headers={"Idempotency-Key": "personal-first-run"},
        json={
            "goal": "Reach 20 qualified mentoring inquiries.",
            "research_mode": "automatic",
            "cadence": "daily",
            "week_start": "2026-11-20",
            "launch_date": "2026-12-01",
        },
    )
    assert response.status_code == 202, response.text
    with database() as db:
        run = db.get(WorkflowRun, response.json()["id"])
        assert run.context["project"]["mode"] == "personal"
        assert run.context["project"]["personal_goal"] == "inquiries"
        assert run.context["customer_pipeline"] is None
        payload, _, _ = run_agent("launch", run.context, {})
        assert payload["tasks"] == []
