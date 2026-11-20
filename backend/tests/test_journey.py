import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from conftest import project, register
from cryptography.fernet import Fernet
from sqlalchemy import select
from test_automatic_growth import search_provider
from test_workflows import BRAND

from app.journey import providers
from app.journey.worker import process_one
from app.models import GrowthJourney, Membership, SocialAccount
from app.workflows.worker import process_one as process_workflow

COMPANY = {
    "problem": "Small teams struggle with security reviews.",
    "solution": "Practical tools for faster security reviews.",
    "target_customers": "Small software teams",
    "differentiator": "Clear practical guidance",
}
BRIEF = {
    **{
        key: BRAND[key]
        for key in ["founder_name", "story", "expertise", "voice", "positioning", "content_pillars"]
    },
    **COMPANY,
}


@pytest.fixture
def configured(monkeypatch, tmp_path):
    for name in [
        "TRANSCRIPTION_API_KEY",
        "LLM_API_KEY",
        "LLM_MODEL",
        "TAVUS_API_KEY",
        "BRAVE_SEARCH_API_KEY",
    ]:
        monkeypatch.setenv(name, "fixture-only")
    monkeypatch.setenv("GENERATION_MODE", "llm")
    from app.workflows import worker as research_worker

    real_agent = research_worker.run_agent
    # External model work is a deterministic fixture; the durable workflow and approval logic are real.
    monkeypatch.setattr(
        research_worker,
        "run_agent",
        lambda agent, ctx, artifacts: real_agent(
            agent, {**ctx, "generation_mode": "template"}, artifacts
        ),
    )
    monkeypatch.setenv("JOURNEY_ENABLED_ORGANIZATIONS", "*")
    monkeypatch.setenv("TAVUS_TRAINING_ORGANIZATIONS", "*")
    monkeypatch.setenv("JOURNEY_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.rymu.test")
    monkeypatch.setenv("JOURNEY_MEDIA_SIGNING_KEY", "fixture-signing-key-not-a-real-secret-12345")
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JOURNEY_PUBLISHING_ENABLED", "true")
    monkeypatch.setattr(
        providers,
        "interview",
        lambda *args: ("The founder's own interview words with enough detail.", BRIEF),
    )


def setup(client):
    org = register(client)
    pid = project(client)
    root = f"/v1/projects/{pid}/journeys"
    response = client.post(
        root + "/interview?consent=yes",
        content=b"\x1aE\xdf\xa3" + b"0" * 100,
        headers={"content-type": "video/webm"},
    )
    assert response.status_code == 202, response.text
    return org, pid, root, response.json()["id"]


def due(database, jid):
    with database() as db:
        row = db.get(GrowthJourney, jid)
        row.next_check = 0
        db.commit()


def get(client, root, jid):
    response = client.get(root + "/" + jid)
    assert response.status_code == 200, response.text
    assert "media_path" not in response.json()
    return response.json()


def post(client, root, jid, path, **data):
    current = get(client, root, jid)
    result = client.post(
        root + "/" + jid + "/" + path, json={"revision": current["revision"], **data}
    )
    assert result.status_code in {200, 202}, result.text
    return result.json()


def through_content(client, database, monkeypatch):
    org, pid, root, jid = setup(client)
    assert process_one(database)
    assert get(client, root, jid)["status"] == "interview_review"
    post(
        client,
        root,
        jid,
        "confirm-brand",
        brand={**BRAND, "base_version_id": None},
        company={**COMPANY, "expected_version": 0},
    )
    search_provider(monkeypatch)
    post(
        client,
        root,
        jid,
        "research",
        goal="Reach the right audience with practical security content",
    )
    assert process_workflow(database)
    current = get(client, root, jid)
    assert current["workflow"]["status"] == "research_review"
    assert not current.get("script")
    post(
        client,
        root,
        jid,
        "confirm-research",
        research_hash=current["workflow"]["research_review_hash"],
    )
    assert process_workflow(database)
    due(database, jid)
    assert process_one(database)
    assert get(client, root, jid)["status"] == "content_review"
    return org, pid, root, jid


def through_video(client, database, monkeypatch):
    org, pid, root, jid = through_content(client, database, monkeypatch)
    monkeypatch.setattr(providers, "create_face", lambda *args: "face123")
    monkeypatch.setattr(providers, "face_status", lambda *args: "completed")
    monkeypatch.setattr(providers, "create_video", lambda *args: "video123")
    monkeypatch.setattr(
        providers, "video_status", lambda *args: ("ready", "https://media.tavus.test/video.mp4")
    )
    post(client, root, jid, "train", consent=True)
    process_one(database)
    due(database, jid)
    process_one(database)
    post(client, root, jid, "render")
    process_one(database)
    due(database, jid)
    process_one(database)
    assert get(client, root, jid)["status"] == "video_ready"
    with database() as db:
        account = SocialAccount(
            project_id=pid,
            provider="facebook",
            external_id="1234",
            name="Founder Page",
            encrypted_token=Fernet(os.environ["SOCIAL_TOKEN_ENCRYPTION_KEY"].encode())
            .encrypt(b"private-token")
            .decode(),
            permissions=["pages_manage_posts", "pages_read_engagement"],
            expires_at=time.time() + 3600,
        )
        db.add(account)
        db.commit()
        account_id = account.id
    return org, pid, root, jid, account_id


def test_complete_journey_and_metrics_are_snapshots(client, database, configured, monkeypatch):
    _, _, root, jid, aid = through_video(client, database, monkeypatch)
    calls = []
    monkeypatch.setattr(providers, "facebook_publish", lambda *args: calls.append(args) or "4567")
    monkeypatch.setattr(
        providers,
        "facebook_results",
        lambda *args: {
            "processing_status": "ready",
            "permalink": "https://facebook.com/4567",
            "metrics": {"likes": 3, "comments": 1},
        },
    )
    when = datetime.fromtimestamp(time.time() + 120, UTC).isoformat()
    scheduled = post(client, root, jid, "schedule", account_id=aid, publish_at=when, approve=True)
    assert scheduled["status"] == "scheduled"
    assert not process_one(database)  # No early post.
    with database() as db:
        row = db.get(GrowthJourney, jid)
        row.data = {
            **row.data,
            "publication": {**row.data["publication"], "publish_at": time.time() - 1},
        }
        row.next_check = 0
        db.commit()
    process_one(database)
    assert get(client, root, jid)["status"] == "posted"
    assert len(calls) == 1 and calls[0][1] == "private-token"
    due(database, jid)
    process_one(database)
    due(database, jid)
    process_one(database)
    assert get(client, root, jid)["results"]["metrics"]["likes"] == 3
    assert len(calls) == 1


def test_stale_approval_cancel_and_edited_script_invalidate_video(
    client, database, configured, monkeypatch
):
    _, _, root, jid, aid = through_video(client, database, monkeypatch)
    original = get(client, root, jid)
    edited = post(
        client,
        root,
        jid,
        "content",
        script=original["script"],
        caption="An updated caption for this reviewed video.",
    )
    rejected = client.post(
        root + "/" + jid + "/schedule",
        json={
            "revision": original["revision"],
            "account_id": aid,
            "publish_at": datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
            "approve": True,
        },
    )
    assert rejected.status_code == 409
    post(
        client,
        root,
        jid,
        "schedule",
        account_id=aid,
        publish_at=datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
        approve=True,
    )
    post(client, root, jid, "cancel")
    current = post(
        client,
        root,
        jid,
        "content",
        script="A new script requires a new video render, and approval.",
        caption=edited["caption"],
    )
    assert current["status"] == "content_review" and "video_url" not in current
    assert "publication" not in current


def test_tenant_access_and_invalid_uploads(client, database, configured):
    _, _, root, jid = setup(client)
    assert (
        client.post(
            root + "/interview?consent=yes",
            content=b"invalid",
            headers={"content-type": "video/webm"},
        ).status_code
        == 422
    )
    assert client.post(root + "/interview", content=b"bad").status_code == 422
    client.post("/auth/logout")
    register(client, "other@example.com")
    assert client.get(root + "/" + jid).status_code == 404
    assert client.post(root + "/" + jid + "/render", json={"revision": 1}).status_code == 404


def test_uncertain_render_is_not_replayed_and_media_requires_signature(
    client, database, configured, monkeypatch
):
    _, _, root, jid = through_content(client, database, monkeypatch)
    from app.journey.api import media_url

    assert client.get(f"/v1/journey-media/{jid}?expires=1&signature=no").status_code == 403
    post(client, root, jid, "train", consent=True)
    url = media_url(jid).split("https://api.rymu.test")[1]
    assert client.get(url).status_code == 200
    calls = []

    def broken(*args):
        calls.append(args)
        raise httpx.ReadTimeout("private request contents")

    monkeypatch.setattr(providers, "create_face", broken)
    process_one(database)
    current = get(client, root, jid)
    assert current["status"] == "uncertain" and "private" not in str(current.get("error_code"))
    assert not process_one(database)
    assert len(calls) == 1
    result = post(client, root, jid, "delete-interview")
    assert "transcript" not in result
    assert client.get(url).status_code == 404
    assert not list(Path(os.environ["JOURNEY_MEDIA_DIR"]).glob("*"))


def test_revoked_owner_and_missed_schedule_never_publish(client, database, configured, monkeypatch):
    org, _, root, jid, aid = through_video(client, database, monkeypatch)
    post(
        client,
        root,
        jid,
        "schedule",
        account_id=aid,
        publish_at=datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
        approve=True,
    )
    with database() as db:
        member = db.scalar(select(Membership).where(Membership.organization_id == org))
        member.role = "viewer"
        row = db.get(GrowthJourney, jid)
        row.next_check = 0
        db.commit()
    monkeypatch.setattr(
        providers, "facebook_publish", lambda *args: pytest.fail("Must not publish")
    )
    process_one(database)
    assert get(client, root, jid)["status"] == "access_revoked"


def test_missed_time_and_interrupted_publish_are_not_replayed(
    client, database, configured, monkeypatch
):
    _, _, root, jid, aid = through_video(client, database, monkeypatch)
    post(
        client,
        root,
        jid,
        "schedule",
        account_id=aid,
        publish_at=datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
        approve=True,
    )
    with database() as db:
        row = db.get(GrowthJourney, jid)
        row.data = {
            **row.data,
            "publication": {**row.data["publication"], "publish_at": time.time() - 7200},
        }
        row.next_check = 0
        db.commit()
    monkeypatch.setattr(
        providers, "facebook_publish", lambda *args: pytest.fail("No late or repeated posting")
    )
    process_one(database)
    assert get(client, root, jid)["status"] == "missed"
    with database() as db:
        row = db.get(GrowthJourney, jid)
        row.status, row.claim_token, row.lease_until = (
            "publishing",
            "crashed-worker",
            time.time() - 1,
        )
        db.commit()
    process_one(database)
    assert get(client, root, jid)["status"] == "uncertain"


def test_no_post_without_approval_permission_and_enabled_delivery(
    client, database, configured, monkeypatch
):
    _, _, root, jid, aid = through_video(client, database, monkeypatch)
    values = {
        "account_id": aid,
        "publish_at": datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
        "approve": False,
    }
    row = get(client, root, jid)
    assert (
        client.post(
            root + "/" + jid + "/schedule", json={"revision": row["revision"], **values}
        ).status_code
        == 422
    )
    monkeypatch.setenv("JOURNEY_PUBLISHING_ENABLED", "false")
    values["approve"] = True
    assert (
        client.post(
            root + "/" + jid + "/schedule", json={"revision": row["revision"], **values}
        ).status_code
        == 422
    )
    monkeypatch.setenv("JOURNEY_PUBLISHING_ENABLED", "true")
    with database() as db:
        account = db.get(SocialAccount, aid)
        account.permissions = ["pages_read_engagement"]
        db.commit()
    assert (
        client.post(
            root + "/" + jid + "/schedule", json={"revision": row["revision"], **values}
        ).status_code
        == 409
    )


def test_provider_http_contracts_and_missing_metrics(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("TRANSCRIPTION_API_KEY", "transcription-fixture")
    monkeypatch.setenv("LLM_API_KEY", "model-fixture")
    monkeypatch.setenv("LLM_MODEL", "model-fixture")
    monkeypatch.setenv("TAVUS_API_KEY", "video-fixture")
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path.endswith("transcriptions"):
            assert request.headers["authorization"] == "Bearer transcription-fixture"
            assert b"interview.webm" in request.content
            return httpx.Response(
                200, json={"text": "The founder explains their own business in this interview."}
            )
        if request.url.path.endswith("chat/completions"):
            body = json.loads(request.content)
            assert "untrusted" in body["messages"][0]["content"]
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(BRIEF)}}]}
            )
        if request.url.host == "tavusapi.com":
            assert request.headers["x-api-key"] == "video-fixture"
            if request.method == "POST" and request.url.path.endswith("faces"):
                assert json.loads(request.content)["model_name"] == "phoenix-4"
                return httpx.Response(200, json={"face_id": "face123", "status": "started"})
            if request.url.path.endswith("faces/face123"):
                return httpx.Response(200, json={"status": "completed"})
            if request.method == "POST":
                assert json.loads(request.content)["replica_id"] == "face123"
                return httpx.Response(200, json={"video_id": "video123"})
            return httpx.Response(
                200, json={"status": "ready", "download_url": "https://media.tavus.test/video.mp4"}
            )
        assert request.headers["authorization"] == "Bearer page-fixture"
        if request.method == "POST":
            assert request.url.host == "graph-video.facebook.com"
            assert b"file_url=" in request.content and b"published=true" in request.content
            return httpx.Response(200, json={"id": "4567"})
        return httpx.Response(200, json={"id": "4567", "status": {"video_status": "processing"}})

    real = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kwargs: real(transport=httpx.MockTransport(respond), **kwargs),
    )
    recording = tmp_path / "interview.webm"
    recording.write_bytes(b"\x1aE\xdf\xa3" + b"fixture")
    text, brief = providers.interview(recording, "video/webm")
    assert "founder" in text and brief["founder_name"] == BRAND["founder_name"]
    face_id = providers.create_face("https://api.rymu.test/signed-interview", "Test founder")
    assert providers.face_status(face_id) == "completed"
    video_id = providers.create_video(face_id, "An explicitly reviewed script.")
    status, url = providers.video_status(video_id)
    assert status == "ready"
    assert providers.facebook_publish("1234", "page-fixture", url, "Reviewed caption") == "4567"
    observed = providers.facebook_results("4567", "page-fixture")
    assert observed["metrics"] == {} and observed["processing_status"] == "processing"
    assert len(calls) == 8


def test_unprovisioned_workspace_cannot_start_paid_jobs(client, configured, monkeypatch):
    register(client)
    pid = project(client)
    monkeypatch.setenv("JOURNEY_ENABLED_ORGANIZATIONS", "")
    response = client.post(
        f"/v1/projects/{pid}/journeys/interview?consent=yes",
        content=b"\x1aE\xdf\xa3" + b"0" * 100,
        headers={"content-type": "video/webm"},
    )
    assert response.status_code == 503
    assert (
        client.get(f"/v1/projects/{pid}/journeys").json()["capabilities"]["workspace_enabled"]
        is False
    )


def test_training_and_render_reservations_respect_operator_limits(
    client, database, configured, monkeypatch
):
    _, _, root, jid = through_content(client, database, monkeypatch)
    monkeypatch.setenv("JOURNEY_MONTHLY_TRAINING_LIMIT", "0")
    current = get(client, root, jid)
    response = client.post(
        root + "/" + jid + "/train", json={"revision": current["revision"], "consent": True}
    )
    assert response.status_code == 429
    assert get(client, root, jid)["status"] == "content_review"
    with database() as db:
        row = db.get(GrowthJourney, jid)
        row.data = {**row.data, "replica_id": "fixture-face", "clone_consent_at": time.time()}
        db.commit()
    monkeypatch.setenv("JOURNEY_MONTHLY_RENDER_LIMIT", "0")
    response = client.post(root + "/" + jid + "/render", json={"revision": current["revision"]})
    assert response.status_code == 429
    assert get(client, root, jid)["status"] == "content_review"


def test_confirmed_brand_and_owned_replica_can_be_reused_without_training(
    client, database, configured, monkeypatch
):
    _, pid, root, source_id, _ = through_video(client, database, monkeypatch)
    response = client.post(root + "/from-brand", json={})
    assert response.status_code == 201, response.text
    new_id = response.json()["id"]
    assert get(client, root, new_id)["status"] == "brand_confirmed"
    assert not get(client, root, new_id)["interview_available"]
    with database() as db:
        row = db.get(GrowthJourney, new_id)
        row.status = "content_review"
        row.data = {
            **row.data,
            "script": "Useful practical advice for a new video.",
            "caption": "A new customer-focused post.",
        }
        db.commit()
    reused = post(client, root, new_id, "reuse-replica", source_journey_id=source_id, consent=True)
    assert reused["replica_id"] == "face123"
    assert reused["replica_source_journey_id"] == source_id
    assert client.get(root).json()["has_approved_brand"] is True
    monkeypatch.setenv("JOURNEY_MONTHLY_TRAINING_LIMIT", "0")
    assert post(client, root, new_id, "render")["status"] == "render_queued"
    # Research gets observed engagement separately from manually confirmed customers.
    from app.workflows.api import performance_snapshot

    with database() as db:
        source = db.get(GrowthJourney, source_id)
        source.status = "measured"
        source.data = {
            **source.data,
            "results": {"metrics": {"likes": 3}},
            "observed_at": time.time(),
            "publication": {"caption": "Approved public caption"},
        }
        db.commit()
        performance = performance_snapshot(db, pid)
        assert performance["published_content"][0]["engagement"] == {"likes": 3}
        assert "video_url" not in str(performance) and "private-token" not in str(performance)
        assert performance["totals"]["paying_customers"] == 0
