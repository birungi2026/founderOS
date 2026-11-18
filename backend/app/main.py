import csv
import io
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db
from .generation import generate
from .models import (
    AuditLog,
    Draft,
    GrowthEvent,
    LoginSession,
    Membership,
    Metric,
    Organization,
    Project,
    Publication,
    ResearchSource,
    User,
)
from .security import (
    COOKIE,
    Tenant,
    audit,
    current_user,
    editor,
    hash_password,
    issue_session,
    owner,
    tenant,
    token_hash,
    verify_password,
)
from .workflows.api import router as workflow_router
from .workflows.contracts import revision_hash

logger = logging.getLogger("founderos.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False

app = FastAPI(title="FounderOS API", version="0.3.0")
app.include_router(workflow_router)
origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Organization-ID", "Idempotency-Key"],
)
# Single-process limiter. Production multi-replica deployments require a shared ingress limiter.
rate_buckets: OrderedDict = OrderedDict()
rate_lock = threading.Lock()


@app.middleware("http")
async def boundary(request: Request, call_next):
    if request.method == "POST":
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        # Browser cross-site form submissions cannot bypass the origin check above.
        key = (
            request.client.host if request.client else "unknown",
            "auth" if request.url.path.startswith("/auth/") else "write",
        )
        with rate_lock:
            now = time.monotonic()
            count, start = rate_buckets.pop(key, (0, now))
            if now - start >= 60:
                count, start = 0, now
            rate_buckets[key] = (count + 1, start)
            if len(rate_buckets) > 4096:
                rate_buckets.popitem(last=False)
        if count >= (15 if key[1] == "auth" else 120):
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
    started = time.monotonic()
    request_id = str(uuid4())
    response = await call_next(request)
    route = request.scope.get("route")
    logger.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            }
        )
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Valid email required")
        return value


class Registration(Credentials):
    organization_name: str = Field(min_length=2, max_length=100)


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


class MemberInput(BaseModel):
    email: str = Field(max_length=254)
    role: Literal["editor", "viewer"]


class SourceInput(BaseModel):
    url: str = Field(max_length=2000)
    title: str = Field(min_length=2, max_length=200)
    excerpt: str = Field(min_length=10, max_length=4000)
    permission_confirmed: Literal[True]

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use an HTTPS source URL without credentials")
        return value


class EventInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=200)
    kind: Literal["impression", "lead", "signup", "paying_customer"]
    channel: str = Field(min_length=2, max_length=100)
    campaign: str = Field(default="unassigned", max_length=100)


class PublishInput(BaseModel):
    confirm: Literal[True]


def project_dict(p):
    return {
        "id": p.id,
        "organization_id": p.organization_id,
        **p.data,
        "created_at": p.created_at,
    }


def draft_dict(d):
    return {
        "id": d.id,
        "project_id": d.project_id,
        "channel": d.channel,
        "content": d.content,
        "status": d.status,
        "generation": d.generation,
        "revision_hash": revision_hash(d),
        "revision_number": d.revision_number,
    }


def require_project(db, project_id, context):
    p = db.scalar(
        select(Project).where(
            Project.id == project_id, Project.organization_id == context.organization.id
        )
    )
    if not p:
        raise HTTPException(404, "Project not found")
    return p


def require_draft(db, draft_id, context):
    d = db.scalar(
        select(Draft)
        .join(Project)
        .where(Draft.id == draft_id, Project.organization_id == context.organization.id)
    )
    if not d:
        raise HTTPException(404, "Draft not found")
    return d


def sources_for(db, project_id):
    return db.scalars(
        select(ResearchSource)
        .where(ResearchSource.project_id == project_id)
        .order_by(ResearchSource.created_at.desc())
        .limit(20)
    ).all()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db.execute(select(User.id).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503, "Database not ready; check migrations") from None
    return {"status": "ready"}


@app.post("/auth/register", status_code=201)
def register(data: Registration, response: Response, db: Session = Depends(get_db)):
    user = User(email=data.email, password_hash=hash_password(data.password))
    org = Organization(name=data.organization_name)
    db.add_all([user, org])
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Account already exists") from None
    db.add(Membership(user_id=user.id, organization_id=org.id, role="owner"))
    audit(db, Tenant(user, org, "owner"), "organization.created", org.id)
    issue_session(db, user, response)
    return {"id": user.id, "email": user.email}


@app.post("/auth/login")
def login(data: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    # Run the same expensive hash on missing accounts to reduce account enumeration.
    valid = (
        verify_password(data.password, user.password_hash)
        if user
        else verify_password(data.password, "00" * 16 + ":" + "00" * 64)
    )
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    issue_session(db, user, response)
    return {"id": user.id, "email": user.email}


@app.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session = db.get(LoginSession, token_hash(request.cookies.get(COOKIE, "")))
    if session:
        db.delete(session)
    response.delete_cookie(COOKIE, path="/")
    return {"status": "signed_out"}


@app.get("/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Organization, Membership.role).join(Membership).where(Membership.user_id == user.id)
    ).all()
    return {
        "id": user.id,
        "email": user.email,
        "organizations": [{"id": o.id, "name": o.name, "role": role} for o, role in rows],
    }


@app.post("/organization/members")
def add_member(data: MemberInput, context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not user:
        raise HTTPException(404, "Registered account not found")
    member = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == context.organization.id,
        )
    )
    if member and member.role == "owner":
        raise HTTPException(409, "Owner role cannot be changed here")
    if member:
        member.role = data.role
    else:
        db.add(Membership(user_id=user.id, organization_id=context.organization.id, role=data.role))
    audit(db, context, "membership." + data.role, user.id)
    return {"user_id": user.id, "role": data.role}


@app.get("/organization/audit")
def audit_log(context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.organization_id == context.organization.id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    ).all()
    return {
        "events": [
            {
                "id": r.id,
                "actor_id": r.actor_id,
                "action": r.action,
                "resource_id": r.resource_id,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@app.get("/agents")
def agents(context: Tenant = Depends(tenant)):
    return {
        "agents": ["Growth Strategist", "Growth Executor", "Growth Analyst"],
        "generation_mode": os.getenv("GENERATION_MODE", "template"),
    }


@app.get("/projects")
def list_projects(context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    return {
        "projects": [
            project_dict(p)
            for p in db.scalars(
                select(Project)
                .where(Project.organization_id == context.organization.id)
                .order_by(Project.created_at.desc())
                .limit(200)
            )
        ]
    }


@app.post("/projects", status_code=201)
def create_project(
    data: ProjectInput, context: Tenant = Depends(editor), db: Session = Depends(get_db)
):
    p = Project(organization_id=context.organization.id, data=data.model_dump())
    db.add(p)
    db.flush()
    audit(db, context, "project.created", p.id)
    return project_dict(p)


@app.get("/projects/{project_id}")
def get_project(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    return project_dict(require_project(db, project_id, context))


@app.post("/projects/{project_id}/strategy")
def strategy(project_id: str, context: Tenant = Depends(editor), db: Session = Depends(get_db)):
    p = require_project(db, project_id, context)
    sources = sources_for(db, p.id)
    plan, mode = generate(p.data, sources)
    result = {
        "goal": f"Acquire {p.data['goal_customers']} paying customers",
        "audience": p.data["audience"],
        "steps": plan.steps,
        "generation_mode": mode,
        "citations": [
            {"id": s.id, "url": s.url, "title": s.title}
            for s in sources
            if s.id in plan.citation_ids
        ],
    }
    p.data = {**p.data, "strategy": result}
    audit(db, context, "strategy.generated", p.id)
    return {"project_id": p.id, **result}


@app.post("/projects/{project_id}/drafts")
def create_drafts(
    project_id: str, context: Tenant = Depends(editor), db: Session = Depends(get_db)
):
    p = require_project(db, project_id, context)
    plan, mode = generate(p.data, sources_for(db, p.id))
    items = [
        Draft(
            project_id=p.id,
            channel=d.channel,
            content=d.content,
            generation={"mode": mode, "citation_ids": plan.citation_ids},
        )
        for d in plan.drafts
    ]
    db.add_all(items)
    db.flush()
    for d in items:
        audit(db, context, "draft.created", d.id)
    return {"drafts": [draft_dict(d) for d in items]}


@app.get("/projects/{project_id}/drafts")
def list_drafts(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    require_project(db, project_id, context)
    return {
        "drafts": [
            draft_dict(d) for d in db.scalars(select(Draft).where(Draft.project_id == project_id))
        ]
    }


@app.post("/drafts/{draft_id}/review")
def review_draft(
    draft_id: str,
    decision: Literal["approved", "rejected"],
    revision: str | None = None,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    d = require_draft(db, draft_id, context)
    if (revision is not None or d.generation.get("run_id")) and revision != revision_hash(d):
        raise HTTPException(409, "Content revision changed. Reload and review the current draft.")
    changed = db.execute(
        update(Draft)
        .where(
            Draft.id == d.id, Draft.status == "pending", Draft.revision_number == d.revision_number
        )
        .values(status=decision)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Only pending drafts can be reviewed")
    db.refresh(d)
    audit(db, context, "draft." + decision, d.id)
    return draft_dict(d)


@app.post("/drafts/{draft_id}/publish", status_code=202)
def queue_publication(
    draft_id: str,
    data: PublishInput,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    d = require_draft(db, draft_id, context)
    changed = db.execute(
        update(Draft).where(Draft.id == d.id, Draft.status == "approved").values(status="queued")
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "An approved draft is required; it may already be queued")
    job = Publication(
        draft_id=d.id, content=d.content, channel=d.channel, approved_by=context.user.id
    )
    db.add(job)
    db.flush()
    audit(db, context, "publication.queued", job.id)
    return {
        "id": job.id,
        "status": job.status,
        "note": "Queued for a server-side connector. Nothing has been sent.",
    }


@app.get("/projects/{project_id}/publications")
def publications(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    require_project(db, project_id, context)
    rows = db.scalars(select(Publication).join(Draft).where(Draft.project_id == project_id)).all()
    return {
        "publications": [
            {
                "id": r.id,
                "draft_id": r.draft_id,
                "status": r.status,
                "provider_reference": r.provider_reference,
                "error_code": r.error_code,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@app.post("/projects/{project_id}/sources", status_code=201)
def add_source(
    project_id: str,
    data: SourceInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    require_project(db, project_id, context)
    source = ResearchSource(
        project_id=project_id,
        url=data.url,
        title=data.title,
        excerpt=data.excerpt,
        verified_by=context.user.id,
    )
    db.add(source)
    db.flush()
    audit(db, context, "source.attested", source.id)
    return {"id": source.id, "verification": "operator_attested"}


@app.get("/projects/{project_id}/sources")
def list_sources(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    require_project(db, project_id, context)
    return {
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "title": s.title,
                "excerpt": s.excerpt,
                "verification": "operator_attested",
            }
            for s in sources_for(db, project_id)
        ]
    }


@app.post("/projects/{project_id}/metrics", status_code=201)
def add_metric(
    project_id: str,
    metric: MetricInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    require_project(db, project_id, context)
    item = Metric(project_id=project_id, data=metric.model_dump())
    db.add(item)
    db.flush()
    audit(db, context, "metric.created", item.id)
    return {"id": item.id, **item.data}


@app.post("/projects/{project_id}/events")
def ingest_event(
    project_id: str,
    data: EventInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    require_project(db, project_id, context)
    existing = db.scalar(
        select(GrowthEvent).where(
            GrowthEvent.project_id == project_id,
            GrowthEvent.external_id == data.external_id,
        )
    )
    if existing:
        if any(getattr(existing, k) != v for k, v in data.model_dump().items()):
            raise HTTPException(409, "Event ID already used with different data")
        return {"id": existing.id, "duplicate": True}
    item = GrowthEvent(project_id=project_id, **data.model_dump())
    try:
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError:
        raise HTTPException(
            409, "Concurrent event submission; retry with the same event ID"
        ) from None
    audit(db, context, "event.created", item.id)
    return {"id": item.id, "duplicate": False}


def calculate(db, project_id):
    keys = ("impressions", "leads", "signups", "paying_customers")
    channels = {}
    rows = db.scalars(select(Metric).where(Metric.project_id == project_id)).all()
    for row in rows:
        bucket = channels.setdefault(row.data["channel"], dict.fromkeys(keys, 0))
        for k in keys:
            bucket[k] += row.data[k]
    event_keys = {
        "impression": "impressions",
        "lead": "leads",
        "signup": "signups",
        "paying_customer": "paying_customers",
    }
    campaigns = {}
    for event in db.scalars(select(GrowthEvent).where(GrowthEvent.project_id == project_id)):
        channels.setdefault(event.channel, dict.fromkeys(keys, 0))[event_keys[event.kind]] += 1
        campaigns.setdefault(event.campaign, dict.fromkeys(keys, 0))[event_keys[event.kind]] += 1
    totals = {k: sum(c[k] for c in channels.values()) for k in keys}
    totals["signup_to_paid_rate"] = (
        round(100 * totals["paying_customers"] / totals["signups"], 2) if totals["signups"] else 0
    )
    return {
        "project_id": project_id,
        "totals": totals,
        "channels": channels,
        "campaigns": campaigns,
        "events": [{"id": r.id, **r.data} for r in rows],
        "attribution_model": "explicit channel and campaign; no inferred attribution",
    }


@app.get("/projects/{project_id}/analytics")
def analytics(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    require_project(db, project_id, context)
    return calculate(db, project_id)


@app.get("/projects/{project_id}/analytics.csv")
def export_csv(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    require_project(db, project_id, context)
    result = calculate(db, project_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["channel", "impressions", "leads", "signups", "paying_customers"])
    for channel, counts in result["channels"].items():
        # Prevent spreadsheet formula injection in user-controlled channel labels.
        safe = (
            "'" + channel
            if channel.lstrip().startswith(("=", "+", "-", "@"))
            or channel.startswith(("\t", "\r", "\n"))
            else channel
        )
        writer.writerow([safe, *counts.values()])
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="founderos-analytics.csv"'},
    )
