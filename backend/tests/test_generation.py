import json

import httpx
from conftest import project, register

from app import generation


def fake_model(monkeypatch, content):
    monkeypatch.setenv("GENERATION_MODE", "llm")
    monkeypatch.setenv("LLM_API_KEY", "fixture-secret")
    monkeypatch.setenv("LLM_MODEL", "fixture-model")
    real_client = httpx.Client

    def handler(request):
        assert request.headers["authorization"] == "Bearer fixture-secret"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(content)}}]}
        )

    monkeypatch.setattr(
        generation.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )


def test_llm_output_and_citations(client, monkeypatch):
    register(client)
    pid = project(client)
    sid = client.post(
        f"/projects/{pid}/sources",
        json={
            "url": "https://example.com",
            "title": "Research",
            "excerpt": "Teams want faster onboarding",
            "permission_confirmed": True,
        },
    ).json()["id"]
    fake_model(
        monkeypatch,
        {
            "steps": ["Interview buyers about onboarding"],
            "drafts": [{"channel": "linkedin", "content": "What slows down your onboarding?"}],
            "citation_ids": [sid],
        },
    )
    r = client.post(f"/projects/{pid}/strategy")
    assert r.status_code == 200, r.text
    assert r.json()["citations"][0]["id"] == sid and r.json()["generation_mode"] == "llm"
    drafts = client.post(f"/projects/{pid}/drafts").json()["drafts"]
    assert drafts[0]["status"] == "pending" and "fixture-secret" not in str(drafts)


def test_invalid_citations_fail_closed(client, monkeypatch):
    register(client)
    pid = project(client)
    fake_model(
        monkeypatch,
        {
            "steps": ["Do research"],
            "drafts": [{"channel": "linkedin", "content": "A useful draft for research"}],
            "citation_ids": ["invented"],
        },
    )
    assert client.post(f"/projects/{pid}/drafts").status_code == 502
    assert client.get(f"/projects/{pid}/drafts").json()["drafts"] == []


def test_missing_provider(client, monkeypatch):
    register(client)
    pid = project(client)
    monkeypatch.setenv("GENERATION_MODE", "llm")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert client.post(f"/projects/{pid}/strategy").status_code == 503
