import json
import time
from datetime import UTC, datetime

import httpx
import pytest
from conftest import project, register
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_workflows import BRAND, BRIEF

from app.main import app
from app.models import DailySchedule, Membership, ResearchSource
from app.workflows import research, worker
from app.workflows.schedules import next_due, schedule_one


def founder(client):
    org = register(client)
    pid = project(client)
    brand = client.post(f"/v1/projects/{pid}/brand", json=BRAND).json()
    client.post(f"/v1/projects/{pid}/brand/{brand['id']}/approve")
    return org, pid


def search_provider(monkeypatch, broken=False):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "private-search-key")
    real_client = httpx.Client
    requests = []

    def handler(request):
        assert request.url.host == "api.search.brave.com"
        assert request.headers["x-subscription-token"] == "private-search-key"
        assert request.url.params.get("freshness") in {None, "pd", "pw"}
        requests.append(request)
        if broken:
            return httpx.Response(429, json={"error": "private provider message"})
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://buyer.example/needs#fragment",
                            "title": "<b>Buyer research</b>",
                            "description": "Small software teams want faster security reviews.",
                        },
                        {
                            "url": "https://127.0.0.1/private",
                            "title": "Private",
                            "description": "Must never be stored as search evidence.",
                        },
                        {
                            "url": "javascript:alert(1)",
                            "title": "Unsafe",
                            "description": "Must never be stored as search evidence.",
                        },
                    ]
                }
            },
        )

    monkeypatch.setattr(
        research.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    return requests


def start(client, pid, key="automatic-0001", cadence="daily"):
    return client.post(
        f"/v1/projects/{pid}/workflows",
        json={**BRIEF, "research_mode": "automatic", "cadence": cadence},
        headers={"Idempotency-Key": key},
    )


def routine(client, pid, enabled=True):
    return client.post(
        f"/v1/projects/{pid}/daily",
        json={
            "enabled": enabled,
            "goal": "Reach the first 50 paying customers with useful daily content",
            "hour": 9,
            "timezone": "America/Denver",
        },
    )


def test_automatic_research_needs_no_manual_source(client, database, monkeypatch):
    _, pid = founder(client)
    requests = search_provider(monkeypatch)
    response = start(client, pid)
    assert response.status_code == 202, response.text
    rid = response.json()["id"]
    assert worker.process_one(database)
    run = client.get(f"/v1/workflows/{rid}").json()
    assert run["status"] == "research_review", run
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []
    assert (
        client.post(
            f"/v1/workflows/{rid}/confirm-research", json={"research_hash": "0" * 64}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/v1/workflows/{rid}/confirm-research",
            json={"research_hash": run["research_review_hash"]},
        ).status_code
        == 200
    )
    assert worker.process_one(database)
    run = client.get(f"/v1/workflows/{rid}").json()
    assert run["status"] == "needs_review"
    assert len(requests) == 7
    assert len(run["sources"]) == 1
    assert run["sources"][0]["verification"] == "search_result_unverified"
    assert run["sources"][0]["title"] == "Buyer research"
    assert "private-search-key" not in json.dumps(run)
    drafts = client.get(f"/projects/{pid}/drafts").json()["drafts"]
    assert len(drafts) == 1 and drafts[0]["status"] == "pending"
    assert run["tasks"] == []
    assert run["steps"][-1]["generation_mode"] == "not_requested"
    assert client.get(f"/v1/projects/{pid}/customers").json()["funnel"]["paying_customers"] == 0
    assert not worker.process_one(database)
    start(client, pid, key="automatic-0002")
    worker.process_one(database)
    with database() as db:
        assert (
            len(db.scalars(select(ResearchSource).where(ResearchSource.project_id == pid)).all())
            == 1
        )


def test_search_configuration_and_failure_are_explicit(client, database, monkeypatch):
    _, pid = founder(client)
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    assert start(client, pid).status_code == 503
    assert client.get("/v1/usage").json()["workflow_runs"] == 0
    search_provider(monkeypatch, broken=True)
    rid = start(client, pid).json()["id"]
    worker.process_one(database)
    result = client.get(f"/v1/workflows/{rid}").json()
    assert result["status"] == "failed" and result["error_code"] == "research_failed"
    assert "private provider message" not in json.dumps(result)
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/x",
        "https://user:pass@site.example/",
        "https://10.1.1.1/",
        "https://[::1]/",
        "file:///etc/passwd",
        "http://site.example",
        "https://site.example:8443/",
        "https://printer.local/",
    ],
)
def test_unsafe_search_result_urls(url):
    assert research.canonical_url(url) is None


def test_daily_job_is_once_per_local_day_and_cancellable(client, database, monkeypatch):
    _, pid = founder(client)
    search_provider(monkeypatch)
    saved = routine(client, pid)
    assert saved.status_code == 200, saved.text
    sid = saved.json()["id"]
    assert schedule_one(database)
    assert not schedule_one(database)
    first = client.get(f"/v1/projects/{pid}/daily").json()["schedule"]["last_run_id"]
    with database() as db:
        row = db.get(DailySchedule, sid)
        row.next_run = time.time() - 1
        db.commit()
    assert schedule_one(database)
    assert client.get("/v1/usage").json()["workflow_runs"] == 1
    assert client.get(f"/v1/projects/{pid}/daily").json()["schedule"]["last_run_id"] == first
    assert routine(client, pid, enabled=False).status_code == 200
    assert client.get(f"/v1/workflows/{first}").json()["status"] == "cancelled"
    assert not worker.process_one(database)


def test_daily_stops_on_quota_and_revoked_owner(client, database, monkeypatch):
    org, pid = founder(client)
    search_provider(monkeypatch)
    monkeypatch.setenv("WORKFLOW_MONTHLY_RUN_LIMIT", "0")
    sid = routine(client, pid).json()["id"]
    assert schedule_one(database)
    result = client.get(f"/v1/projects/{pid}/daily").json()["schedule"]
    assert result["last_error"] == "monthly_allowance_reached" and not result["enabled"]
    monkeypatch.setenv("WORKFLOW_MONTHLY_RUN_LIMIT", "40")
    routine(client, pid)
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "editor"
        db.commit()
    schedule_one(database)
    with database() as db:
        assert db.get(DailySchedule, sid).last_error == "owner_access_revoked"


def test_daily_timezone_validation_and_owner_permission(client):
    org, pid = founder(client)
    assert (
        client.post(
            f"/v1/projects/{pid}/daily",
            json={
                "enabled": False,
                "goal": "A valid daily goal",
                "hour": 9,
                "timezone": "Invalid/Timezone",
            },
        ).status_code
        == 422
    )
    with TestClient(app) as other:
        register(other, "editor@example.com")
        client.post("/organization/members", json={"email": "editor@example.com", "role": "editor"})
        assert (
            other.post(
                f"/v1/projects/{pid}/daily",
                json={"enabled": False, "goal": "A valid daily goal", "hour": 9, "timezone": "UTC"},
                headers={"X-Organization-ID": org},
            ).status_code
            == 403
        )


def test_next_due_across_dst():
    before = datetime(2026, 3, 7, 17, 0, tzinfo=UTC).timestamp()  # after 9am MST
    due = datetime.fromtimestamp(next_due(9, "America/Denver", before), UTC)
    assert due == datetime(2026, 3, 8, 15, 0, tzinfo=UTC)  # 9am MDT


def test_customer_funnel_counts_only_confirmed_payments(client):
    _, pid = founder(client)
    data = {
        "name": "Real Customer",
        "website": "https://customer.example",
        "next_action": "Arrange a relevant product demo",
    }
    lead = client.post(f"/v1/projects/{pid}/customers", json=data).json()
    assert lead["stage"] == "identified"
    assert client.post(f"/v1/projects/{pid}/customers", json=data).status_code == 409
    assert client.get(f"/v1/projects/{pid}/customers").json()["funnel"]["paying_customers"] == 0
    update_data = {
        "expected_version": 1,
        "stage": "won",
        "next_action": "Welcome the paying customer",
    }
    assert client.post(f"/v1/customers/{lead['id']}", json=update_data).status_code == 422
    response = client.post(
        f"/v1/customers/{lead['id']}", json={**update_data, "paying_customer_confirmed": True}
    )
    assert response.status_code == 200, response.text
    funnel = client.get(f"/v1/projects/{pid}/customers").json()["funnel"]
    assert funnel["paying_customers"] == 1 and funnel["remaining"] == 49
    assert (
        client.post(
            f"/v1/customers/{lead['id']}", json={**update_data, "paying_customer_confirmed": True}
        ).status_code
        == 409
    )
    assert (
        client.get(f"/projects/{pid}/analytics").json()["totals"]["paying_customers"] == 0
    )  # no duplicate analytics inflation


def test_customer_pipeline_tenant_isolation(client):
    org, pid = founder(client)
    lead = client.post(
        f"/v1/projects/{pid}/customers",
        json={
            "name": "Buyer",
            "website": "https://buyer.example",
            "next_action": "Ask about product fit",
        },
    ).json()
    with TestClient(app) as other:
        register(other, "outsider@example.com")
        assert other.get(f"/v1/projects/{pid}/customers").status_code == 404
        assert (
            other.get(
                f"/v1/projects/{pid}/customers", headers={"X-Organization-ID": org}
            ).status_code
            == 403
        )
        assert (
            other.post(
                f"/v1/customers/{lead['id']}",
                json={"expected_version": 1, "stage": "contacted", "next_action": "Ask about fit"},
            ).status_code
            == 404
        )


def test_weekly_and_monthly_routine_dates():
    after = datetime(2026, 11, 18, 12, tzinfo=UTC).timestamp()  # Wednesday
    weekly = datetime.fromtimestamp(next_due(9, "UTC", after, "weekly", weekday=0), UTC)
    monthly = datetime.fromtimestamp(next_due(9, "UTC", after, "monthly", month_day=5), UTC)
    assert weekly == datetime(2026, 11, 23, 9, tzinfo=UTC)
    assert monthly == datetime(2026, 12, 5, 9, tzinfo=UTC)
    year_end = datetime(2026, 12, 30, 12, tzinfo=UTC).timestamp()
    assert datetime.fromtimestamp(
        next_due(9, "UTC", year_end, "monthly", month_day=1), UTC
    ) == datetime(2027, 1, 1, 9, tzinfo=UTC)


def test_multiple_posts_and_explicit_routine_settings(client, database, monkeypatch):
    _, pid = founder(client)
    search_provider(monkeypatch)
    response = client.post(
        f"/v1/projects/{pid}/daily",
        json={
            "enabled": True,
            "goal": "Reach our first fifty paying customers",
            "hour": 9,
            "timezone": "UTC",
            "frequency": "weekly",
            "weekday": 2,
            "month_day": 10,
            "posts_per_day": 3,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["frequency"] == "weekly" and response.json()["posts_per_day"] == 3
    # Simulate the selected day becoming due.
    with database() as db:
        db.get(DailySchedule, response.json()["id"]).next_run = time.time() - 1
        db.commit()
    assert schedule_one(database)
    assert worker.process_one(database)
    run = client.get(f"/v1/projects/{pid}/workflows").json()["runs"][0]
    detail = client.get(f"/v1/workflows/{run['id']}").json()
    assert detail["status"] == "research_review"
    assert (
        client.post(
            f"/v1/workflows/{run['id']}/confirm-research",
            json={"research_hash": detail["research_review_hash"]},
        ).status_code
        == 200
    )
    worker.process_one(database)
    drafts = client.get(f"/projects/{pid}/drafts").json()["drafts"]
    assert len(drafts) == 3
    assert len({draft["content"] for draft in drafts}) == 3
    assert all(draft["status"] == "pending" for draft in drafts)
    assert len({draft["generation"]["planned_date"] for draft in drafts}) == 1
    assert client.get(f"/v1/projects/{pid}/customers").json()["funnel"]["target_customers"] == 50


def test_daily_monitoring_continues_between_monthly_content_batches(client, database, monkeypatch):
    _, pid = founder(client)
    search_provider(monkeypatch)
    saved = client.post(
        f"/v1/projects/{pid}/daily",
        json={
            "enabled": True,
            "goal": "Prepare useful content for our first fifty customers",
            "hour": 9,
            "timezone": "UTC",
            "frequency": "monthly",
            "month_day": 1,
            "posts_per_day": 2,
        },
    ).json()
    with database() as db:
        db.get(DailySchedule, saved["id"]).next_run = time.time() + 20 * 86400
        db.commit()
    assert schedule_one(database)
    assert worker.process_one(database)
    run = client.get(f"/v1/projects/{pid}/workflows").json()["runs"][0]
    detail = client.get(f"/v1/workflows/{run['id']}").json()
    assert detail["research_only"] and detail["status"] == "research_ready"
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []
    with database() as db:
        schedule = db.get(DailySchedule, saved["id"])
        assert schedule.next_monitor < schedule.next_run
    assert not schedule_one(database)


def test_company_profile_and_confirmation_staleness(client, database, monkeypatch):
    _, pid = founder(client)
    search_provider(monkeypatch)
    rid = start(client, pid).json()["id"]
    worker.process_one(database)
    detail = client.get(f"/v1/workflows/{rid}").json()
    assert detail["status"] == "research_review"
    updated = client.post(
        f"/v1/projects/{pid}/company",
        json={
            "problem": "An updated buyer problem with a narrower target audience",
            "solution": "A revised product solution for teams",
            "target_customers": "Small startup teams",
            "competitors": ["https://competitor.example"],
            "expected_version": 0,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 1
    assert (
        client.post(
            f"/v1/workflows/{rid}/confirm-research",
            json={"research_hash": detail["research_review_hash"]},
        ).status_code
        == 409
    )
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []


def test_research_confirmation_is_owner_only(client, database, monkeypatch):
    org, pid = founder(client)
    search_provider(monkeypatch)
    rid = start(client, pid).json()["id"]
    worker.process_one(database)
    detail = client.get(f"/v1/workflows/{rid}").json()
    with TestClient(app) as other:
        register(other, "research-editor@example.com")
        client.post(
            "/organization/members", json={"email": "research-editor@example.com", "role": "editor"}
        )
        assert (
            other.post(
                f"/v1/workflows/{rid}/confirm-research",
                json={"research_hash": detail["research_review_hash"]},
                headers={"X-Organization-ID": org},
            ).status_code
            == 403
        )
    client.post(f"/v1/workflows/{rid}/cancel")
    assert not worker.process_one(database)


def test_switching_to_manual_mode_cannot_bypass_machine_research_confirmation(
    client, database, monkeypatch
):
    _, pid = founder(client)
    search_provider(monkeypatch)
    first = start(client, pid).json()["id"]
    worker.process_one(database)
    client.post(f"/v1/workflows/{first}/cancel")
    second = client.post(
        f"/v1/projects/{pid}/workflows",
        json=BRIEF,
        headers={"Idempotency-Key": "manual-after-search"},
    ).json()["id"]
    worker.process_one(database)
    assert client.get(f"/v1/workflows/{second}").json()["status"] == "research_review"
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []
