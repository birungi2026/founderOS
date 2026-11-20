"""E2E-only worker: real queue/approval logic, mocked external search transport."""

import os

import httpx

if os.getenv("FOUNDEROS_TEST_RESEARCH") != "1":
    raise RuntimeError("This fixture may only run in an explicit test environment")
os.environ["GENERATION_MODE"] = "template"

from app.workflows import research, worker

real_client = httpx.Client


def search(request):
    if (
        request.url.host != "api.search.brave.com"
        or request.headers.get("X-Subscription-Token") != "fixture-search-key"
    ):
        raise RuntimeError("Unexpected outbound request in browser test")
    return httpx.Response(
        200,
        json={
            "web": {
                "results": [
                    {
                        "url": "https://buyer.example/research",
                        "title": "Public buyer research",
                        "description": "Small software teams want clearer customer conversion metrics and relevant product demonstrations.",
                    }
                ]
            }
        },
    )


research.httpx.Client = lambda **kwargs: real_client(
    transport=httpx.MockTransport(search), **kwargs
)
worker.main()
