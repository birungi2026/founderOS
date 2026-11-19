import time

import pytest
from conftest import project, register

from app.models import SocialAccount
from app.platforms import GUIDANCE, guidance_snapshot
from app.workflows import agents


def test_guidance_is_tenant_scoped_and_does_not_invent_account_metrics(client, database):
    register(client)
    pid = project(client)
    with database() as db:
        db.add(
            SocialAccount(
                project_id=pid,
                provider="linkedin",
                external_id="member",
                name="Founder",
                encrypted_token="not-exposed-secret",
                permissions=["openid", "profile"],
                expires_at=time.time() + 3600,
                status="connected",
                snapshot={
                    "observed_at": time.time(),
                    "profile": {"name": "Founder"},
                    "posts": [],
                    "limitations": "Profile only",
                },
            )
        )
        db.commit()
    response = client.get(f"/v1/projects/{pid}/platform-intelligence")
    assert response.status_code == 200
    assert len(response.json()["platforms"]) == 4
    assert "not-exposed-secret" not in response.text
    linkedin = next(p for p in response.json()["platforms"] if p["platform"] == "linkedin")
    assert linkedin["account_data"][0]["followers_count"] is None
    assert linkedin["account_data"][0]["limitations"] == "Profile only"
    register(client, "outsider-platform@example.com")
    assert client.get(f"/v1/projects/{pid}/platform-intelligence").status_code == 404


def test_platform_experiments_cite_versioned_guidance_and_reject_unknown_ids(
    client, database, monkeypatch
):
    register(client)
    pid = project(client)
    with database() as db:
        guidance = guidance_snapshot(db, pid)
    ctx = {
        "project": {
            "product_name": "Project",
            "description": "Useful product",
            "audience": "Founders",
        },
        "brand": {"content_pillars": ["Growth"]},
        "sources": [
            {
                "id": "source",
                "excerpt": "Founders need practical examples to assess products.",
                "provider": "brave",
            }
        ],
        "generation_mode": "template",
        "platform_guidance": guidance,
    }
    payload, _, _ = agents.run_agent("research", ctx, {})
    assert {p["platform"] for p in payload["platform_strategies"]} == {
        p["platform"] for p in GUIDANCE
    }
    assert all(
        p["evidence_ids"][0] in {g["source_id"] for g in guidance}
        for p in payload["platform_strategies"]
    )
    original = agents.templates

    def bad(agent, context, artifacts):
        result = original(agent, context, artifacts)
        result["platform_strategies"][0]["evidence_ids"] = ["invented-id"]
        return result

    monkeypatch.setattr(agents, "templates", bad)
    with pytest.raises(ValueError, match="unknown_citation"):
        agents.run_agent("research", ctx, {})
