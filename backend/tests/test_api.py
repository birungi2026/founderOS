from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_growth_workflow():
    project = client.post("/projects", json={
        "product_name": "Qopanza",
        "description": "Developer security and cryptographic discovery",
        "audience": "Software startups",
        "goal_customers": 10,
    }).json()
    pid = project["id"]
    assert client.post(f"/projects/{pid}/strategy").status_code == 200
    drafts = client.post(f"/projects/{pid}/drafts").json()["drafts"]
    assert len(drafts) == 2
    reviewed = client.post(f"/drafts/{drafts[0]['id']}/review?decision=approved").json()
    assert reviewed["status"] == "approved"
    client.post(f"/projects/{pid}/metrics", json={
        "channel": "linkedin", "impressions": 200, "leads": 10, "signups": 4, "paying_customers": 1
    })
    assert client.get(f"/projects/{pid}/analytics").json()["totals"]["signup_to_paid_rate"] == 25.0
