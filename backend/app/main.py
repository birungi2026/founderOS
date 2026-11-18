from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="FounderOS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# MVP-only in-memory storage. Replace with tenant-scoped persistent storage before deployment.
projects: dict[str, dict] = {}
drafts: dict[str, dict] = {}
metrics: dict[str, list[dict]] = {}


class ProjectInput(BaseModel):
    product_name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=2000)
    audience: str = Field(min_length=3, max_length=500)
    goal_customers: int = Field(default=10, ge=1, le=10000)


class MetricInput(BaseModel):
    channel: str = Field(min_length=2, max_length=100)
    impressions: int = Field(default=0, ge=0)
    leads: int = Field(default=0, ge=0)
    signups: int = Field(default=0, ge=0)
    paying_customers: int = Field(default=0, ge=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/agents")
def agents():
    return {"agents": ["Growth Strategist", "Growth Executor", "Growth Analyst"]}


@app.post("/projects")
def create_project(data: ProjectInput):
    project_id = str(uuid4())
    project = {"id": project_id, **data.model_dump(), "created_at": datetime.now(timezone.utc).isoformat()}
    projects[project_id] = project
    metrics[project_id] = []
    return project


def require_project(project_id: str):
    if project_id not in projects:
        raise HTTPException(status_code=404, detail="Project not found")
    return projects[project_id]


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    return require_project(project_id)


@app.post("/projects/{project_id}/strategy")
def strategy(project_id: str):
    p = require_project(project_id)
    return {
        "project_id": project_id,
        "goal": f"Acquire {p['goal_customers']} paying customers",
        "audience": p["audience"],
        "steps": [
            "Interview 10 potential customers about their current workflow and buying trigger.",
            "Publish two useful founder-led posts per week addressing buyer pain.",
            "Prepare 15 individually researched, permission-respecting outreach drafts.",
            "Invite qualified prospects to a product demo or free trial.",
            "Review signups, qualified conversations and paying customers weekly.",
        ],
        "note": "Template-based starter strategy; validate recommendations with customer research.",
    }


@app.post("/projects/{project_id}/drafts")
def create_drafts(project_id: str):
    p = require_project(project_id)
    templates = [
        ("linkedin", f"Building {p['product_name']} for {p['audience']}. We're focused on {p['description']}. What's the hardest part of solving this problem today?"),
        ("outreach", f"Hi, I'm building {p['product_name']} for teams like yours. We're working on {p['description']}. Would a brief conversation about your current approach be useful?"),
    ]
    result = []
    for channel, content in templates:
        item = {"id": str(uuid4()), "project_id": project_id, "channel": channel, "content": content, "status": "pending"}
        drafts[item["id"]] = item
        result.append(item)
    return {"drafts": result}


@app.get("/projects/{project_id}/drafts")
def list_drafts(project_id: str):
    require_project(project_id)
    return {"drafts": [d for d in drafts.values() if d["project_id"] == project_id]}


@app.post("/drafts/{draft_id}/review")
def review_draft(draft_id: str, decision: Literal["approved", "rejected"]):
    if draft_id not in drafts:
        raise HTTPException(status_code=404, detail="Draft not found")
    drafts[draft_id]["status"] = decision
    return drafts[draft_id]


@app.post("/projects/{project_id}/metrics")
def add_metric(project_id: str, metric: MetricInput):
    require_project(project_id)
    item = {"id": str(uuid4()), **metric.model_dump()}
    metrics[project_id].append(item)
    return item


@app.get("/projects/{project_id}/analytics")
def analytics(project_id: str):
    require_project(project_id)
    rows = metrics[project_id]
    totals = {key: sum(row[key] for row in rows) for key in ("impressions", "leads", "signups", "paying_customers")}
    totals["signup_to_paid_rate"] = round(100 * totals["paying_customers"] / totals["signups"], 2) if totals["signups"] else 0
    return {"project_id": project_id, "totals": totals, "events": rows}
