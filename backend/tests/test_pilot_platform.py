import hashlib
import hmac
import json
import shutil
import subprocess
import time
from datetime import UTC, datetime

import pytest
from conftest import project, register
from sqlalchemy import select

from app import billing, media
from app.journey import providers, worker
from app.models import (
    BillingAccount,
    GrowthJourney,
    Membership,
    PilotObservation,
    ResourceUsage,
    SocialAccount,
    VideoAsset,
)
from app.social import vault


def signed(body, timestamp=None):
    timestamp = timestamp or int(time.time())
    digest = hmac.new(
        b"fixture-secret", str(timestamp).encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return {"Stripe-Signature": f"t={timestamp},v1={digest}"}


def setup(client):
    org, pid = register(client), project(client)
    return org, pid, f"/v1/projects/{pid}"


def test_billing_webhook_canonical_state_and_quota(client, database, monkeypatch):
    org, _, _ = setup(client)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "fixture-secret")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_growth")
    monkeypatch.setenv("BILLING_ENFORCED", "true")
    monkeypatch.setenv("PLAN_VIDEO_SECONDS", "60")
    current = {
        "id": "sub_fixture",
        "customer": "cus_fixture",
        "metadata": {"organization_id": org},
        "status": "active",
        "current_period_end": time.time() + 86400,
        "items": {"data": [{"price": {"id": "price_growth"}}]},
    }
    monkeypatch.setattr(billing, "stripe_get", lambda _: current)
    event = {
        "id": "evt_first",
        "created": int(time.time()),
        "type": "customer.subscription.updated",
        "data": {"object": {"id": "sub_fixture"}},
    }
    body = json.dumps(event).encode()
    assert client.post("/v1/billing/webhook", content=body).status_code == 400
    assert (
        client.post(
            "/v1/billing/webhook", content=body, headers=signed(body, int(time.time()) - 600)
        ).status_code
        == 400
    )
    assert client.post("/v1/billing/webhook", content=body, headers=signed(body)).status_code == 200
    assert client.post("/v1/billing/webhook", content=body, headers=signed(body)).status_code == 200
    with database() as db:
        billing.reserve(db, org, "video_seconds", 30, "first")
        billing.reserve(db, org, "video_seconds", 30, "first")
        billing.reserve(db, org, "video_seconds", 30, "second")
        db.commit()
        with pytest.raises(Exception) as failure:
            billing.reserve(db, org, "video_seconds", 30, "third")
        assert failure.value.status_code == 429
    assert client.get("/v1/billing").json()["usage"]["video_seconds"] == 60
    current["status"] = "canceled"
    event.update(id="evt_delayed", created=event["created"] - 1)
    body = json.dumps(event).encode()
    assert client.post("/v1/billing/webhook", content=body, headers=signed(body)).status_code == 200
    with database() as db:
        with pytest.raises(Exception) as failure:
            billing.active(db, org)
        assert failure.value.status_code == 402
        assert len(db.scalars(select(ResourceUsage)).all()) == 2
    assert billing.render_seconds("界" * 1200) >= 300


def test_checkout_validates_price_and_never_grants_access(client, database, monkeypatch):
    org, _, _ = setup(client)
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_growth")
    monkeypatch.setenv("JOURNEY_ENABLED_ORGANIZATIONS", org)
    monkeypatch.setenv("APP_PUBLIC_URL", "https://rymu.example")
    monkeypatch.setattr(billing, "stripe_get", lambda _: {"unit_amount": 100})
    assert client.post("/v1/billing/checkout").status_code == 503
    monkeypatch.setattr(
        billing,
        "stripe_get",
        lambda _: {"unit_amount": 5900, "currency": "usd", "recurring": {"interval": "month"}},
    )
    calls = []

    def stripe(path, fields, key):
        calls.append((path, fields, key))
        return {
            "id": "cs_test",
            "url": "https://checkout.stripe.com/c/pay/test"
            if path == "checkout/sessions"
            else "https://billing.stripe.com/p/session/test",
        }

    monkeypatch.setattr(billing, "stripe", stripe)
    assert client.post("/v1/billing/checkout").status_code == 200
    assert calls[-1][1]["client_reference_id"] == org
    assert client.get("/v1/billing").json()["status"] == "inactive"
    with database() as db:
        row = db.get(BillingAccount, org)
        row.customer_id, row.status, row.subscription_id, row.period_end = (
            "cus_test",
            "active",
            "sub_test",
            time.time() + 1000,
        )
        db.commit()
    assert client.post("/v1/billing/checkout").status_code == 409
    assert client.post("/v1/billing/portal").status_code == 200
    assert calls[-1][1]["customer"] == "cus_test"
    client.post("/auth/logout")
    register(client, "other@example.com")
    assert client.post("/v1/billing/portal").status_code == 409


def test_pilot_evidence_preserves_unknowns_and_tenant_scope(client, database):
    _, pid, root = setup(client)
    before = {
        "external_id": "baseline-001",
        "kind": "baseline",
        "channel": "instagram",
        "starts_on": "2025-01-01",
        "ends_on": "2025-01-07",
        "followers": 100,
        "attested": True,
    }
    after = {
        **before,
        "external_id": "followup-001",
        "kind": "followup",
        "starts_on": "2025-01-08",
        "ends_on": "2025-01-14",
        "followers": 120,
        "delivered": 3,
        "published": 2,
        "likely_authentic": 5,
        "suspicious": 2,
        "unknown": 3,
    }
    assert client.post(root + "/pilot/observations", json=before).status_code == 201
    assert client.post(root + "/pilot/observations", json=before).status_code == 201
    assert client.post(root + "/pilot/observations", json=after).status_code == 201
    report = client.get(root + "/pilot").json()
    assert len(report["observations"]) == 2
    assert report["comparisons"][0]["follower_change"] == 20
    assert report["observations"][1]["paying_customers"] is None
    assert report["observations"][1]["source"] == "operator_reported"
    after.update(external_id="overlap-001", starts_on="2025-01-07")
    assert client.post(root + "/pilot/observations", json=after).status_code == 201
    assert client.get(root + "/pilot").json()["comparisons"][0]["follower_change"] is None
    after["published"] = 4
    assert client.post(root + "/pilot/observations", json=after).status_code == 422
    config = {
        "revision": 0,
        "cohort": "delayed",
        "segment": "coach",
        "primary_goal": "inquiries",
        "starts_on": "2026-01-01",
    }
    assert client.post(root + "/pilot/config", json=config).status_code == 200
    assert client.post(root + "/pilot/config", json=config).status_code == 409
    client.post("/auth/logout")
    register(client, "other@example.com")
    assert client.get(root + "/pilot").status_code == 404
    with database() as db:
        assert (
            len(
                db.scalars(select(PilotObservation).where(PilotObservation.project_id == pid)).all()
            )
            == 3
        )


def test_server_conversion_key_rotation_and_replay(client):
    _, pid, root = setup(client)
    key = client.post(root + "/conversion-key").json()["key"]
    event = {
        "project_id": pid,
        "external_id": "customer-order-1",
        "kind": "paying_customer",
        "channel": "instagram",
        "campaign": "coach_pilot",
    }
    assert client.post("/v1/conversions", json=event).status_code == 401
    headers = {"X-Rymu-Conversion-Key": key}
    assert client.post("/v1/conversions", json=event, headers=headers).status_code == 201
    assert client.post("/v1/conversions", json=event, headers=headers).json()["duplicate"]
    event["kind"] = "lead"
    assert client.post("/v1/conversions", json=event, headers=headers).status_code == 409
    client.post(root + "/conversion-key")
    assert client.post("/v1/conversions", json=event, headers=headers).status_code == 401


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_real_ffmpeg_clip_private_url_and_journey(client, database, monkeypatch, tmp_path):
    org, pid, root = setup(client)
    for key, value in {
        "JOURNEY_MEDIA_DIR": str(tmp_path / "media"),
        "JOURNEY_MEDIA_SIGNING_KEY": "x" * 40,
        "PUBLIC_API_URL": "https://api.rymu.example",
        "JOURNEY_ENABLED_ORGANIZATIONS": org,
    }.items():
        monkeypatch.setenv(key, value)
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=15:d=3",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    upload = client.post(
        root + "/assets", content=source.read_bytes(), headers={"Content-Type": "video/mp4"}
    )
    assert upload.status_code == 201, upload.text
    aid = upload.json()["id"]
    assert "source_path" not in upload.text
    assert (
        client.post(
            root + f"/assets/{aid}/render",
            json={
                "start": 1,
                "end": 2,
                "caption": "A real short clip for review",
                "subtitles": "Hello from real footage",
            },
        ).status_code
        == 202
    )
    assert media.process_one(database)
    asset = client.get(root + "/assets").json()["assets"][0]
    assert asset["status"] == "ready", asset
    url = asset["video_url"].replace("https://api.rymu.example", "")
    assert client.get(url).status_code == 200
    assert client.get(url.replace("signature=", "signature=bad")).status_code == 403
    with database() as db:
        assert 0.9 <= media.probe(db.get(VideoAsset, aid).data["output_path"]) <= 1.5
    use = client.post(root + f"/assets/{aid}/use").json()
    assert client.post(root + f"/assets/{aid}/use").json() == use
    assert client.get(root + "/journeys/" + use["journey_id"]).json()["status"] == "video_ready"
    client.post("/auth/logout")
    register(client, "other@example.com")
    assert client.post(root + f"/assets/{aid}/use").status_code == 404


@pytest.mark.parametrize("fail_publish", [False, True])
def test_instagram_publish_requires_processing_then_separate_write(
    client, database, monkeypatch, fail_publish
):
    org, pid, root = setup(client)
    monkeypatch.setenv("JOURNEY_ENABLED_ORGANIZATIONS", org)
    monkeypatch.setenv("INSTAGRAM_PUBLISHING_ENABLED", "true")
    monkeypatch.setenv(
        "SOCIAL_TOKEN_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
    )
    with database() as db:
        actor = db.scalar(select(Membership).where(Membership.organization_id == org)).user_id
        account = SocialAccount(
            project_id=pid,
            provider="instagram",
            external_id="178900",
            name="Coach",
            encrypted_token=vault().encrypt(b"fixture").decode(),
            permissions=["instagram_business_basic", "instagram_business_content_publish"],
            expires_at=time.time() + 86400,
        )
        db.add(account)
        db.flush()
        journey = GrowthJourney(
            project_id=pid,
            requested_by=actor,
            status="video_ready",
            data={
                "video_id": "video_test",
                "video_url": "https://media.example/video.mp4",
                "caption": "Useful coaching content for review",
            },
        )
        db.add(journey)
        db.commit()
        jid, aid = journey.id, account.id
    monkeypatch.setattr(
        providers, "video_status", lambda _: ("ready", "https://media.example/video.mp4")
    )
    calls = []
    monkeypatch.setattr(
        providers, "instagram_container", lambda *a: calls.append("container") or "container1"
    )
    monkeypatch.setattr(providers, "instagram_status", lambda *a: "FINISHED")

    def publish(*args):
        calls.append("publish")
        if fail_publish:
            raise RuntimeError("Simulated ambiguous provider write")
        return "media1"

    monkeypatch.setattr(providers, "instagram_publish", publish)
    monkeypatch.setattr(
        providers,
        "instagram_results",
        lambda *a: {"processing_status": "ready", "metrics": {"likes": 4}, "permalink": None},
    )
    scheduled = client.post(
        root + f"/journeys/{jid}/schedule",
        json={
            "revision": 1,
            "account_id": aid,
            "publish_at": datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
            "approve": True,
        },
    )
    assert scheduled.status_code == 200, scheduled.text

    def run():
        with database() as db:
            db.get(GrowthJourney, jid).next_check = 0
            db.commit()
        worker.process_one(database)

    run()
    assert calls == ["container"]
    run()
    assert calls == ["container"]
    run()
    assert calls == ["container", "publish"]
    if fail_publish:
        assert client.get(root + f"/journeys/{jid}").json()["status"] == "uncertain"
        assert not worker.process_one(database)
        assert calls == ["container", "publish"]
        return
    run()
    assert client.get(root + f"/journeys/{jid}").json()["results"]["metrics"] == {"likes": 4}
    monkeypatch.setenv("INSTAGRAM_PUBLISHING_ENABLED", "false")
    run()
    assert client.get(root + f"/journeys/{jid}").json()["status"] == "access_revoked"


def test_instagram_contract_missing_insights_stays_missing(monkeypatch):
    calls = []

    def fake(method, path, token, payload=None):
        calls.append((method, path, payload))
        if path.endswith("/media") or path.endswith("/media_publish"):
            return {"id": "media1"}
        if payload == {"fields": "status_code"}:
            return {"status_code": "FINISHED"}
        if path.endswith("/insights"):
            raise providers.ProviderFailure("unavailable")
        return {"like_count": 2, "permalink": "https://www.instagram.com/reel/test/"}

    monkeypatch.setattr(providers, "instagram", fake)
    assert (
        providers.instagram_container("123", "token", "https://media.example/video.mp4", "caption")
        == "media1"
    )
    assert calls[-1][2]["media_type"] == "REELS"
    assert providers.instagram_status("media1", "token") == "FINISHED"
    assert providers.instagram_publish("123", "media1", "token") == "media1"
    assert providers.instagram_results("media1", "token", True)["metrics"] == {"likes": 2}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_automatic_captions_use_timestamped_clip_transcription(monkeypatch, tmp_path):
    from uuid import uuid4

    import httpx

    source = tmp_path / "input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=15:d=2",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        check=True,
    )
    monkeypatch.setenv("JOURNEY_MEDIA_DIR", str(tmp_path))
    monkeypatch.setenv("TRANSCRIPTION_API_KEY", "fixture-caption-key")
    real_client = httpx.Client
    calls = []

    def reply(request):
        calls.append(request)
        assert request.url.path == "/v1/audio/transcriptions"
        assert request.headers["Authorization"] == "Bearer fixture-caption-key"
        assert b"verbose_json" in request.content and b"whisper-1" in request.content
        return httpx.Response(
            200, json={"segments": [{"start": 0.0, "end": 1.0, "text": "Hello caption"}]}
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(reply), **kwargs),
    )
    row = VideoAsset(
        id=str(uuid4()),
        project_id="fixture",
        requested_by="fixture",
        data={
            "source_path": str(source),
            "start": 0,
            "end": 1,
            "clip_seconds": 1,
            "subtitles": "",
            "transcribe": True,
        },
    )
    output = media.edit_video(row)
    assert len(calls) == 1 and media.probe(output) >= 0.9


def test_week_export_escapes_formulas_and_excludes_other_weeks(client, database):
    from app.models import Draft

    _, pid, root = setup(client)
    with database() as db:
        db.add(
            Draft(
                project_id=pid,
                channel="instagram",
                content="=SUM(1,1)",
                generation={"planned_date": "2026-01-05"},
            )
        )
        db.add(
            Draft(
                project_id=pid,
                channel="instagram",
                content="Other week should be excluded",
                generation={"planned_date": "2026-02-05"},
            )
        )
        db.commit()
    result = client.get(root + "/week?start=2026-01-05").json()
    assert len(result["drafts"]) == 1 and len(result["drafts"][0]["revision_hash"]) == 64
    response = client.get(root + "/week/export?start=2026-01-05")
    assert "'=SUM(1,1)" in response.text
    assert "Other week" not in response.text
    client.post("/auth/logout")
    register(client, "other@example.com")
    assert client.get(root + "/week").status_code == 404


def test_subscription_alone_cannot_enable_avatar_setup(client, database, monkeypatch):
    org, pid, root = setup(client)
    monkeypatch.setenv("JOURNEY_ENABLED_ORGANIZATIONS", org)
    monkeypatch.setenv("TAVUS_TRAINING_ORGANIZATIONS", "")
    with database() as db:
        actor = db.scalar(select(Membership).where(Membership.organization_id == org)).user_id
        row = GrowthJourney(project_id=pid, requested_by=actor, status="content_review", data={})
        db.add(row)
        db.commit()
        jid = row.id
    assert (
        client.post(
            root + f"/journeys/{jid}/train", json={"revision": 1, "consent": True}
        ).status_code
        == 403
    )
    assert not client.get(root + "/journeys").json()["capabilities"]["training"]
