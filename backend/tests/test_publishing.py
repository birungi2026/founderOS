import httpx
import pytest
from conftest import project, register

from app.models import Publication
from app.publishing import deliver_one


def queued(client):
    org = register(client)
    pid = project(client)
    did = client.post(f"/projects/{pid}/drafts").json()["drafts"][0]["id"]
    client.post(f"/drafts/{did}/review?decision=approved")
    job = client.post(f"/drafts/{did}/publish", json={"confirm": True}).json()["id"]
    return org, job


def connector(org):
    return {
        "organization_id": org,
        "channel": "linkedin",
        "access_token": "test-scoped-oauth",
        "author": "urn:li:person:fixture",
        "api_version": "202610",
    }


def test_delivery_is_single_use_and_scoped(client, database):
    org, job = queued(client)
    sent = []

    def handler(request):
        assert request.url.host == "api.linkedin.com"
        assert request.headers["authorization"] == "Bearer test-scoped-oauth"
        sent.append(request)
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:fixture"})

    transport = httpx.MockTransport(handler)
    with pytest.raises(ValueError):
        deliver_one(database, "other-org", job, connector(org), transport)
    assert deliver_one(database, org, job, connector(org), transport) == "sent"
    with pytest.raises(ValueError):
        deliver_one(database, org, job, connector(org), transport)
    assert len(sent) == 1
    with database() as db:
        assert db.get(Publication, job).provider_reference == "urn:li:share:fixture"


def test_uncertain_delivery_is_never_replayed(client, database):
    org, job = queued(client)

    def handler(request):
        raise httpx.ReadTimeout("Response lost", request=request)

    assert (
        deliver_one(database, org, job, connector(org), httpx.MockTransport(handler)) == "uncertain"
    )
    with pytest.raises(ValueError):
        deliver_one(database, org, job, connector(org), httpx.MockTransport(handler))


def test_provider_rejection_is_recorded(client, database):
    org, job = queued(client)
    assert (
        deliver_one(
            database,
            org,
            job,
            connector(org),
            httpx.MockTransport(lambda r: httpx.Response(403)),
        )
        == "failed"
    )
    with database() as db:
        assert db.get(Publication, job).error_code == "provider_rejected"
