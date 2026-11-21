import os
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AgentStep,
    BrandVersion,
    ContentRevision,
    Draft,
    GrowthEvent,
    GrowthJourney,
    LaunchTask,
    Metric,
    Project,
    ResearchSource,
    WorkflowRun,
    WorkflowUsage,
)
from ..security import Tenant, audit, editor, owner, tenant
from . import research
from .agents import AGENTS
from .contracts import (
    BrandInput,
    CampaignInput,
    RevisionInput,
    StrictModel,
    TaskDecision,
    digest,
    revision_hash,
)

router = APIRouter(prefix="/v1", tags=["Founder growth team"])


def project_for(db, project_id, context):
    project = db.scalar(
        select(Project).where(
            Project.id == project_id, Project.organization_id == context.organization.id
        )
    )
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def run_for(db, run_id, context):
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id, WorkflowRun.organization_id == context.organization.id
        )
    )
    if not run:
        raise HTTPException(404, "Workflow not found")
    return run


def draft_for(db, draft_id, context):
    draft = db.scalar(
        select(Draft)
        .join(Project)
        .where(Draft.id == draft_id, Project.organization_id == context.organization.id)
    )
    if not draft:
        raise HTTPException(404, "Draft not found")
    return draft


def brand_dict(brand):
    return {
        "id": brand.id,
        "version": brand.version,
        "data": brand.data,
        "status": brand.status,
        "approved_by": brand.approved_by,
        "created_at": brand.created_at,
    }


def latest_brand(db, project_id):
    return db.scalar(
        select(BrandVersion)
        .where(BrandVersion.project_id == project_id)
        .order_by(BrandVersion.version.desc())
        .limit(1)
    )


def run_dict(run):
    return {
        "id": run.id,
        "project_id": run.project_id,
        "brand_version_id": run.brand_version_id,
        "status": run.status,
        "progress": run.progress,
        "error_code": run.error_code,
        "goal": run.context["goal"],
        "week_start": run.context["week_start"],
        "launch_date": run.context["launch_date"],
        "generation_mode": run.context["generation_mode"],
        "research_mode": run.context.get("research_mode", "manual"),
        "cadence": run.context.get("cadence", "weekly"),
        "created_at": run.created_at,
    }


@router.get("/agents")
def agents(context: Tenant = Depends(tenant)):
    return {
        "agents": [{"id": agent, "name": name} for agent, name in AGENTS],
        "generation_mode": os.getenv("GENERATION_MODE", "template"),
        "video_capability": "script_and_storyboard",
        "research_configured": research.configured(),
    }


@router.get("/projects/{project_id}/brand")
def get_brand(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    rows = db.scalars(
        select(BrandVersion)
        .where(BrandVersion.project_id == project_id)
        .order_by(BrandVersion.version.desc())
        .limit(50)
    ).all()
    return {
        "latest": brand_dict(rows[0]) if rows else None,
        "versions": [brand_dict(row) for row in rows],
    }


@router.post("/projects/{project_id}/brand", status_code=201)
def save_brand(
    project_id: str,
    data: BrandInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    previous = latest_brand(db, project_id)
    if data.base_version_id != (previous.id if previous else None):
        raise HTTPException(409, "Brand memory changed. Reload before saving a new version.")
    brand = BrandVersion(
        project_id=project_id,
        version=previous.version + 1 if previous else 1,
        data=data.model_dump(mode="json", exclude={"base_version_id"}),
        created_by=context.user.id,
    )
    db.add(brand)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Brand memory changed concurrently. Reload and try again."
        ) from None
    audit(db, context, "brand.version_created", brand.id)
    return brand_dict(brand)


@router.post("/projects/{project_id}/brand/{version_id}/approve")
def approve_brand(
    project_id: str,
    version_id: str,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    brand = latest_brand(db, project_id)
    if not brand or brand.id != version_id:
        raise HTTPException(409, "Only the latest brand version can be approved")
    changed = db.execute(
        update(BrandVersion)
        .where(BrandVersion.id == version_id, BrandVersion.status == "pending")
        .values(status="approved", approved_by=context.user.id)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Brand version is already approved")
    db.refresh(brand)
    audit(db, context, "brand.approved", brand.id)
    return brand_dict(brand)


def performance_snapshot(db, project_id):
    totals = dict.fromkeys(["impressions", "leads", "signups", "paying_customers"], 0)
    channels = {}
    for metric in db.scalars(select(Metric).where(Metric.project_id == project_id)):
        channel = channels.setdefault(metric.data["channel"], dict.fromkeys(totals, 0))
        for key in totals:
            channel[key] += metric.data[key]
            totals[key] += metric.data[key]
    keys = {
        "impression": "impressions",
        "lead": "leads",
        "signup": "signups",
        "paying_customer": "paying_customers",
    }
    for kind, channel, count in db.execute(
        select(GrowthEvent.kind, GrowthEvent.channel, func.count())
        .where(GrowthEvent.project_id == project_id)
        .group_by(GrowthEvent.kind, GrowthEvent.channel)
    ):
        channels.setdefault(channel, dict.fromkeys(totals, 0))[keys[kind]] += count
        totals[keys[kind]] += count
    return {
        "totals": totals,
        "channels": channels,
        "approved_writing_examples": [
            {
                "text": draft.content[:1000],
                "revision": draft.revision_number,
                "note": "User-approved wording; a style example, not evidence of growth or factual claims.",
            }
            for draft in db.scalars(
                select(Draft)
                .where(
                    Draft.project_id == project_id,
                    Draft.status.in_(["approved", "sent"]),
                    Draft.revision_number > 1,
                )
                .order_by(Draft.id)
                .limit(5)
            )
        ],
        "published_content": [
            {
                "journey_id": row.id,
                "channel": row.data.get("publication", {}).get("provider", "facebook"),
                "caption": row.data.get("publication", {}).get("caption", "")[:400],
                "observed_at": row.data.get("observed_at"),
                "engagement": row.data.get("results", {}).get("metrics", {}),
                "note": "Observed engagement, not leads, purchases or causal attribution.",
            }
            for row in db.scalars(
                select(GrowthJourney)
                .where(GrowthJourney.project_id == project_id, GrowthJourney.status == "measured")
                .order_by(GrowthJourney.created_at.desc())
                .limit(5)
            )
        ],
        "note": "Observed cumulative counts, not causal attribution or forecasts.",
    }


def reserve_quota(db, organization_id):
    period = datetime.now(UTC).strftime("%Y-%m")
    row = db.scalar(
        select(WorkflowUsage).where(
            WorkflowUsage.organization_id == organization_id, WorkflowUsage.period == period
        )
    )
    if not row:
        try:
            with db.begin_nested():
                row = WorkflowUsage(organization_id=organization_id, period=period, runs_reserved=0)
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.scalar(
                select(WorkflowUsage).where(
                    WorkflowUsage.organization_id == organization_id, WorkflowUsage.period == period
                )
            )
    limit = int(os.getenv("WORKFLOW_MONTHLY_RUN_LIMIT", "40"))
    changed = db.execute(
        update(WorkflowUsage)
        .where(WorkflowUsage.id == row.id, WorkflowUsage.runs_reserved < limit)
        .values(runs_reserved=WorkflowUsage.runs_reserved + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(429, "Monthly workflow allowance reached")


@router.post("/projects/{project_id}/workflows", status_code=202)
def queue_workflow(
    project_id: str,
    data: CampaignInput,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=100)],
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project = project_for(db, project_id, context)
    request_hash = digest({"project_id": project_id, **data.model_dump(mode="json")})
    existing = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.organization_id == context.organization.id,
            WorkflowRun.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "Idempotency key was already used with different input")
        return run_dict(existing)
    brand = latest_brand(db, project_id)
    if not brand or brand.status != "approved":
        raise HTTPException(409, "Save and approve your latest brand profile first")
    sources = db.scalars(
        select(ResearchSource)
        .where(ResearchSource.project_id == project_id)
        .order_by(ResearchSource.created_at.desc())
        .limit(5)
    ).all()
    if data.research_mode == "manual" and not sources:
        raise HTTPException(
            409, "Add at least one permitted research source before starting the team"
        )
    if data.research_mode == "automatic" and not research.configured():
        raise HTTPException(
            503,
            "Automatic research needs a server-side search provider key. Your founder does not need to supply sources.",
        )
    from .company import company_snapshot

    company = company_snapshot(project)
    if (
        data.research_mode == "automatic"
        and project.data.get("mode", "business") != "personal"
        and not company.get("problem")
    ):
        raise HTTPException(
            409, "Complete the company's problem, solution and target customers first"
        )
    mode = os.getenv("GENERATION_MODE", "template")
    if mode not in {"template", "llm"} or (
        mode == "llm" and (not os.getenv("LLM_API_KEY") or not os.getenv("LLM_MODEL"))
    ):
        raise HTTPException(503, "Generation provider is not configured")
    from ..platforms import guidance_snapshot
    from .customers import funnel

    snapshot = {
        **data.model_dump(mode="json"),
        "brand": brand.data,
        "platform_guidance": guidance_snapshot(db, project_id),
        "company": company,
        "requires_research_confirmation": data.research_mode == "automatic"
        or any(s.provider != "manual" for s in sources),
        "brand_version": brand.version,
        "project": {
            key: (
                None
                if key == "goal_customers" and project.data.get("mode") == "personal"
                else project.data.get(key)
            )
            for key in [
                "focus",
                "product_name",
                "description",
                "audience",
                "goal_customers",
                "mode",
                "personal_goal",
                "personal_target",
                "personal_current",
            ]
        },
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "title": s.title,
                "excerpt": s.excerpt,
                "observed_at": s.created_at,
                "verification": "operator_attested"
                if s.provider == "manual"
                else "search_result_unverified",
                "provider": s.provider,
            }
            for s in sources
            if data.research_mode == "manual"
        ],
        "performance": performance_snapshot(db, project_id),
        "customer_pipeline": None
        if project.data.get("mode") == "personal"
        else funnel(db, project_id),
        "social_accounts": social_context(db, project_id),
        "generation_mode": mode,
    }
    from ..billing import reserve

    reserve(
        db,
        context.organization.id,
        "research_runs",
        1,
        "workflow-" + context.organization.id + "-" + idempotency_key,
    )
    reserve_quota(db, context.organization.id)
    run = WorkflowRun(
        organization_id=context.organization.id,
        project_id=project_id,
        brand_version_id=brand.id,
        requested_by=context.user.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        context=snapshot,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Concurrent workflow request; retry with the same idempotency key"
        ) from None
    audit(db, context, "workflow.queued", run.id)
    return run_dict(run)


@router.get("/projects/{project_id}/workflows")
def list_workflows(
    project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)
):
    project_for(db, project_id, context)
    rows = db.scalars(
        select(WorkflowRun)
        .where(
            WorkflowRun.project_id == project_id,
            WorkflowRun.organization_id == context.organization.id,
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(30)
    ).all()
    return {"runs": [run_dict(run) for run in rows]}


@router.get("/workflows/{run_id}")
def get_workflow(run_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    run = run_for(db, run_id, context)
    steps = db.scalars(
        select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.created_at)
    ).all()
    tasks = db.scalars(
        select(LaunchTask).where(LaunchTask.run_id == run_id).order_by(LaunchTask.due_date)
    ).all()
    research_step = next((step for step in steps if step.agent == "research"), None)
    review_hash = (
        digest(
            {
                "sources": run.context["sources"],
                "company": run.context.get("company"),
                "platform_guidance": run.context.get("platform_guidance", []),
                "artifact": research_step.artifact,
            }
        )
        if research_step
        else None
    )
    return {
        **run_dict(run),
        "company": run.context.get("company"),
        "platform_guidance": run.context.get("platform_guidance", []),
        "research_only": run.context.get("research_only", False),
        "research_review_hash": review_hash,
        "research_confirmed": bool(run.context.get("research_confirmation")),
        "brand_version": run.context["brand_version"],
        "sources": run.context["sources"],
        "performance_baseline": run.context["performance"],
        "steps": [
            {
                "agent": s.agent,
                "artifact": s.artifact,
                "generation_mode": s.generation_mode,
                "usage": s.usage,
            }
            for s in steps
        ],
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "phase": task.phase,
                "due_date": task.due_date,
                "completed": task.completed,
            }
            for task in tasks
        ],
    }


@router.post("/workflows/{run_id}/cancel")
def cancel_workflow(run_id: str, context: Tenant = Depends(editor), db: Session = Depends(get_db)):
    run = run_for(db, run_id, context)
    changed = db.execute(
        update(WorkflowRun)
        .where(
            WorkflowRun.id == run.id,
            WorkflowRun.status.in_(["queued", "running", "research_review"]),
        )
        .values(status="cancelled")
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Only queued or running workflows can be cancelled")
    audit(db, context, "workflow.cancelled", run.id)
    db.refresh(run)
    return run_dict(run)


@router.post("/launch-tasks/{task_id}")
def update_task(
    task_id: str,
    data: TaskDecision,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    task = db.scalar(
        select(LaunchTask)
        .join(WorkflowRun)
        .where(LaunchTask.id == task_id, WorkflowRun.organization_id == context.organization.id)
    )
    if not task:
        raise HTTPException(404, "Launch task not found")
    task.completed = data.completed
    audit(db, context, "launch_task.updated", task.id)
    return {"id": task.id, "completed": task.completed}


@router.get("/usage")
def usage(context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    period = datetime.now(UTC).strftime("%Y-%m")
    row = db.scalar(
        select(WorkflowUsage).where(
            WorkflowUsage.organization_id == context.organization.id, WorkflowUsage.period == period
        )
    )
    return {
        "period": period,
        "workflow_runs": row.runs_reserved if row else 0,
        "limit": int(os.getenv("WORKFLOW_MONTHLY_RUN_LIMIT", "40")),
        "unit": "workflow runs; at most four model calls per run",
        "billing": "not_enabled",
    }


@router.post("/content/{draft_id}/revisions", status_code=201)
def edit_content(
    draft_id: str,
    data: RevisionInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    draft = draft_for(db, draft_id, context)
    if not draft.generation.get("run_id"):
        raise HTTPException(409, "Only workflow calendar drafts support this editor")
    if draft.status not in {
        "pending",
        "approved",
        "rejected",
    } or data.expected_hash != revision_hash(draft):
        raise HTTPException(409, "Draft changed or is already queued. Reload before editing.")
    version = draft.revision_number + 1
    generation = {**draft.generation, "planned_date": data.planned_date.isoformat()}
    changed = db.execute(
        update(Draft)
        .where(
            Draft.id == draft_id,
            Draft.revision_number == draft.revision_number,
            Draft.status == draft.status,
        )
        .values(
            content=data.content, generation=generation, revision_number=version, status="pending"
        )
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Draft changed concurrently. Reload before editing.")
    db.refresh(draft)
    db.add(
        ContentRevision(
            draft_id=draft.id,
            version=version,
            content=draft.content,
            planned_date=generation["planned_date"],
            revision_hash=revision_hash(draft),
            created_by=context.user.id,
        )
    )
    audit(db, context, "content.revised", draft.id)
    return {
        "id": draft.id,
        "revision_hash": revision_hash(draft),
        "version": version,
        "status": "pending",
    }


@router.get("/content/{draft_id}/revisions")
def revisions(draft_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    draft_for(db, draft_id, context)
    rows = db.scalars(
        select(ContentRevision)
        .where(ContentRevision.draft_id == draft_id)
        .order_by(ContentRevision.version.desc())
    ).all()
    return {
        "revisions": [
            {
                "version": r.version,
                "content": r.content,
                "planned_date": r.planned_date,
                "revision_hash": r.revision_hash,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


class ResearchConfirmation(StrictModel):
    research_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/workflows/{run_id}/confirm-research")
def confirm_research(
    run_id: str,
    data: ResearchConfirmation,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    run = run_for(db, run_id, context)
    step = db.scalar(
        select(AgentStep).where(AgentStep.run_id == run_id, AgentStep.agent == "research")
    )
    if run.status != "research_review" or not step:
        raise HTTPException(409, "This workflow is not waiting for research confirmation")
    from .company import company_snapshot

    project = project_for(db, run.project_id, context)
    current_brand = latest_brand(db, run.project_id)
    if (
        company_snapshot(project) != run.context.get("company")
        or not current_brand
        or current_brand.id != run.brand_version_id
        or current_brand.status != "approved"
    ):
        raise HTTPException(
            409, "Company or founder facts changed. Start fresh research before confirming."
        )
    current_hash = digest(
        {
            "sources": run.context["sources"],
            "company": run.context.get("company"),
            "platform_guidance": run.context.get("platform_guidance", []),
            "artifact": step.artifact,
        }
    )
    if data.research_hash != current_hash:
        raise HTTPException(409, "Research changed; review the current brief before confirming")
    snapshot = {
        **run.context,
        "research_confirmation": {
            "hash": current_hash,
            "by": context.user.id,
            "at": datetime.now(UTC).isoformat(),
        },
    }
    changed = db.execute(
        update(WorkflowRun)
        .where(WorkflowRun.id == run_id, WorkflowRun.status == "research_review")
        .values(status="queued", claim_token=None, lease_until=None, context=snapshot)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Research confirmation changed concurrently")
    audit(db, context, "research.confirmed", run_id)
    db.refresh(run)
    return run_dict(run)


def social_context(db, project_id):
    from ..models import SocialAccount

    return [
        {
            "provider": row.provider,
            "name": row.name,
            "data": {
                "observed_at": row.snapshot.get("observed_at"),
                "profile": row.snapshot.get("profile", {}),
                "posts": row.snapshot.get("posts", [])[:3],
            },
            "verification": "provider_account_data_untrusted_content",
        }
        for row in db.scalars(
            select(SocialAccount).where(
                SocialAccount.project_id == project_id,
                SocialAccount.status == "connected",
                SocialAccount.expires_at > time.time(),
            )
        )
        if row.snapshot
    ]
