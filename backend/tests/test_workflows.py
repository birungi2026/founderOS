import time

import httpx
import pytest
from conftest import project, register
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.main import app
from app.models import Membership, WorkflowRun
from app.workflows import agents, worker

BRAND = {
    "founder_name": "Ada Founder",
    "website_url": "https://example.com",
    "story": "I started building security tools after seeing small teams struggle with reviews.",
    "expertise": ["Developer security"],
    "voice": "Clear, practical and warm",
    "positioning": "Help small software teams understand security reviews without slowing delivery.",
    "content_pillars": ["Practical security", "Building in public"],
    "proof_points": [],
    "avoid_topics": ["Guaranteed outcomes"],
}
BRIEF = {
    "goal": "Find useful messages for our first customers",
    "week_start": "2026-11-23",
    "launch_date": "2026-12-05",
}


def setup(client):
    org = register(client)
    pid = project(client)
    b = client.post(f"/v1/projects/{pid}/brand", json=BRAND)
    assert b.status_code == 201, b.text
    bid = b.json()["id"]
    assert client.post(f"/v1/projects/{pid}/brand/{bid}/approve").status_code == 200
    client.post(
        f"/projects/{pid}/sources",
        json={
            "url": "https://example.com/interviews",
            "title": "Customer interviews",
            "excerpt": "Small teams want faster security reviews.",
            "permission_confirmed": True,
        },
    )
    return org, pid, bid


def queue(client, pid, key="campaign-0001", brief=None):
    return client.post(
        f"/v1/projects/{pid}/workflows", json=brief or BRIEF, headers={"Idempotency-Key": key}
    )


def drafts(client, pid):
    return client.get(f"/projects/{pid}/drafts").json()["drafts"]


def test_full_team_workflow(client, database):
    _, pid, bid = setup(client)
    client.post(f"/projects/{pid}/metrics", json={"channel": "linkedin", "leads": 3, "signups": 2})
    r = queue(client, pid)
    assert r.status_code == 202, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "queued"
    assert worker.process_one(database)
    run = client.get(f"/v1/workflows/{rid}").json()
    assert run["status"] == "needs_review" and run["progress"] == 100
    assert [s["agent"] for s in run["steps"]] == [a[0] for a in agents.AGENTS]
    assert run["brand_version_id"] == bid
    assert run["performance_baseline"]["totals"]["leads"] == 3
    items = drafts(client, pid)
    assert len(items) == 7 and all(d["status"] == "pending" for d in items)
    assert [d["generation"]["planned_date"] for d in items] == [
        f"2026-11-{day}" for day in range(23, 30)
    ]
    assert len(run["tasks"]) == 4
    task = run["tasks"][0]
    assert client.post(f"/v1/launch-tasks/{task['id']}", json={"completed": True}).json()[
        "completed"
    ]
    assert not worker.process_one(database)
    assert len(drafts(client, pid)) == 7
    assert client.get(f"/projects/{pid}/publications").json()["publications"] == []


def test_brand_history_and_approval_gate(client):
    register(client)
    pid = project(client)
    assert queue(client, pid).status_code == 409
    first = client.post(f"/v1/projects/{pid}/brand", json=BRAND).json()
    assert queue(client, pid).status_code == 409
    client.post(f"/v1/projects/{pid}/brand/{first['id']}/approve")
    assert queue(client, pid).status_code == 409  # no source
    assert client.post(f"/v1/projects/{pid}/brand", json=BRAND).status_code == 409
    second = client.post(
        f"/v1/projects/{pid}/brand",
        json={**BRAND, "base_version_id": first["id"], "voice": "Concise and direct"},
    ).json()
    assert second["version"] == 2 and second["status"] == "pending"
    assert client.post(f"/v1/projects/{pid}/brand/{first['id']}/approve").status_code == 409
    history = client.get(f"/v1/projects/{pid}/brand").json()
    assert history["versions"][1]["data"]["voice"] == BRAND["voice"]


def test_snapshot_is_immutable(client, database):
    _, pid, bid = setup(client)
    rid = queue(client, pid).json()["id"]
    client.post(
        f"/v1/projects/{pid}/brand",
        json={
            **BRAND,
            "base_version_id": bid,
            "story": "A different founder story that must not affect an already queued run.",
        },
    )
    client.post(f"/projects/{pid}/metrics", json={"channel": "other", "leads": 100})
    assert worker.process_one(database)
    result = client.get(f"/v1/workflows/{rid}").json()
    assert result["steps"][0]["artifact"]["profile"]["story"] == BRAND["story"]
    assert result["performance_baseline"]["totals"]["leads"] == 0


def test_idempotency_and_allowance(client, monkeypatch):
    _, pid, _ = setup(client)
    monkeypatch.setenv("WORKFLOW_MONTHLY_RUN_LIMIT", "1")
    first = queue(client, pid)
    assert queue(client, pid).json()["id"] == first.json()["id"]
    assert (
        queue(client, pid, brief={**BRIEF, "goal": "A different acquisition objective"}).status_code
        == 409
    )
    assert queue(client, pid, key="campaign-0002").status_code == 429
    assert client.get("/v1/usage").json()["workflow_runs"] == 1


def test_cancel_queued_run(client, database):
    _, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    assert client.post(f"/v1/workflows/{rid}/cancel").json()["status"] == "cancelled"
    assert not worker.process_one(database)
    assert drafts(client, pid) == []


def test_cancel_during_model_call(client, database, monkeypatch):
    _, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    real_agent = worker.run_agent

    def cancelling_agent(agent, ctx, artifacts):
        if agent == "research":
            with database() as db:
                db.execute(
                    update(WorkflowRun).where(WorkflowRun.id == rid).values(status="cancelled")
                )
                db.commit()
        return real_agent(agent, ctx, artifacts)

    monkeypatch.setattr(worker, "run_agent", cancelling_agent)
    worker.process_one(database)
    assert client.get(f"/v1/workflows/{rid}").json()["status"] == "cancelled"
    assert drafts(client, pid) == []


def test_failure_and_expired_lease(client, database, monkeypatch):
    _, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    monkeypatch.setattr(
        worker,
        "run_agent",
        lambda *args: (_ for _ in ()).throw(ValueError("private provider data")),
    )
    worker.process_one(database)
    result = client.get(f"/v1/workflows/{rid}").json()
    assert result["status"] == "failed" and result["error_code"] == "generation_failed"
    assert "private provider data" not in str(result) and drafts(client, pid) == []
    second = queue(client, pid, key="campaign-0002").json()["id"]
    with database() as db:
        db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == second)
            .values(status="running", lease_until=time.time() - 1)
        )
        db.commit()
    assert not worker.process_one(database)
    assert client.get(f"/v1/workflows/{second}").json()["error_code"] == "worker_interrupted"


def test_revoked_membership_prevents_generation(client, database):
    org, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "viewer"
        db.commit()
    assert worker.process_one(database)
    assert client.get(f"/v1/workflows/{rid}").json()["error_code"] == "access_revoked"
    assert drafts(client, pid) == []


def test_content_edit_invalidates_approval_and_stale_review(client, database):
    _, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    worker.process_one(database)
    d = drafts(client, pid)[0]
    did = d["id"]
    assert client.post(f"/drafts/{did}/review?decision=approved").status_code == 409
    assert (
        client.post(
            f"/drafts/{did}/review?decision=approved&revision={d['revision_hash']}"
        ).status_code
        == 200
    )
    edited = client.post(
        f"/v1/content/{did}/revisions",
        json={
            "expected_hash": d["revision_hash"],
            "content": "Edited, founder-reviewed content for our customer audience.",
            "planned_date": "2026-11-30",
        },
    )
    assert edited.status_code == 201, edited.text
    assert edited.json()["status"] == "pending"
    assert client.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 409
    assert (
        client.post(
            f"/drafts/{did}/review?decision=approved&revision={d['revision_hash']}"
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/drafts/{did}/review?decision=approved&revision={edited.json()['revision_hash']}"
        ).status_code
        == 200
    )
    assert client.post(f"/drafts/{did}/publish", json={"confirm": True}).status_code == 202
    assert (
        client.post(
            f"/v1/content/{did}/revisions",
            json={
                "expected_hash": edited.json()["revision_hash"],
                "content": "Another edit after queueing must be refused.",
                "planned_date": "2026-11-30",
            },
        ).status_code
        == 409
    )
    assert len(client.get(f"/v1/content/{did}/revisions").json()["revisions"]) == 2
    assert client.get(f"/v1/workflows/{rid}").json()["status"] == "needs_review"


def test_cross_tenant_workflow_and_artifact_access(client, database):
    org, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    worker.process_one(database)
    did = drafts(client, pid)[0]["id"]
    task = client.get(f"/v1/workflows/{rid}").json()["tasks"][0]["id"]
    with TestClient(app) as other:
        register(other, "other@example.com")
        for route in [
            f"/v1/projects/{pid}/brand",
            f"/v1/projects/{pid}/workflows",
            f"/v1/workflows/{rid}",
            f"/v1/content/{did}/revisions",
        ]:
            assert other.get(route).status_code == 404
        assert (
            other.get(f"/v1/workflows/{rid}", headers={"X-Organization-ID": org}).status_code == 403
        )
        assert other.post(f"/v1/workflows/{rid}/cancel").status_code == 404
        assert other.post(f"/v1/launch-tasks/{task}", json={"completed": True}).status_code == 404


def test_viewer_cannot_change_brand_or_start_workflows(client):
    org, pid, _ = setup(client)
    with TestClient(app) as viewer:
        register(viewer, "viewer@example.com")
        client.post("/organization/members", json={"email": "viewer@example.com", "role": "viewer"})
        headers = {"X-Organization-ID": org}
        assert viewer.get(f"/v1/projects/{pid}/brand", headers=headers).status_code == 200
        assert (
            viewer.post(f"/v1/projects/{pid}/brand", json=BRAND, headers=headers).status_code == 403
        )
        assert (
            viewer.post(
                f"/v1/projects/{pid}/workflows",
                json=BRIEF,
                headers={**headers, "Idempotency-Key": "viewer-attempt"},
            ).status_code
            == 403
        )


def test_llm_workflow_uses_shared_context_and_validates_sources(client, database, monkeypatch):
    _, pid, _ = setup(client)
    monkeypatch.setenv("GENERATION_MODE", "llm")
    monkeypatch.setenv("LLM_API_KEY", "private-model-secret")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    rid = queue(client, pid).json()["id"]
    real_client = httpx.Client
    calls = []

    def model(request):
        body = __import__("json").loads(request.content)
        prompt = __import__("json").loads(body["messages"][1]["content"])
        assert prompt["context"]["brand"]["founder_name"] == BRAND["founder_name"]
        assert "private-model-secret" not in str(prompt)
        agent = {
            "ResearchArtifact": "research",
            "GrowthArtifact": "growth",
            "VideoArtifact": "video",
            "LaunchArtifact": "launch",
        }[prompt["output_schema"]["title"]]
        calls.append(agent)
        data = agents.templates(agent, prompt["context"], prompt["prior_artifacts"])
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": __import__("json").dumps(data)}}],
                "usage": {"total_tokens": 50},
            },
        )

    monkeypatch.setattr(
        agents.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(model), **kwargs),
    )
    assert worker.process_one(database)
    result = client.get(f"/v1/workflows/{rid}").json()
    assert result["status"] == "needs_review", result
    assert calls == ["research", "growth", "video", "launch"]
    assert sum(s["usage"].get("total_tokens", 0) for s in result["steps"]) == 200
    assert "private-model-secret" not in str(result)


def test_invalid_research_citation_fails_without_drafts(client, database, monkeypatch):
    _, pid, _ = setup(client)
    rid = queue(client, pid).json()["id"]
    original = agents.templates

    def bad(agent, ctx, artifacts):
        result = original(agent, ctx, artifacts)
        if agent == "research":
            result["opportunities"][0]["evidence_ids"] = ["invented-source"]
        return result

    monkeypatch.setattr(agents, "templates", bad)
    worker.process_one(database)
    assert client.get(f"/v1/workflows/{rid}").json()["status"] == "failed"
    assert drafts(client, pid) == []


def test_invalid_calendar_shape_and_video_duration():
    from app.workflows.contracts import GrowthArtifact, VideoArtifact

    with pytest.raises(ValueError):
        GrowthArtifact.model_validate(
            {"objective": "Goal", "experiment": "Test", "success_metric": "Leads", "calendar": []}
        )
    with pytest.raises(ValueError):
        VideoArtifact.model_validate(
            {
                "title": "Test",
                "hook": "Hello",
                "scenes": [
                    {
                        "duration_seconds": 2,
                        "narration": "Hello",
                        "caption": "Text",
                        "visual": "Text",
                    }
                ]
                * 2,
                "call_to_action": "Talk to us",
            }
        )
