import time
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, field_validator
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import DailySchedule, Membership, Organization, Project, User, WorkflowRun
from ..security import Tenant, audit, owner, tenant
from . import research
from .api import latest_brand, project_for, queue_workflow
from .contracts import CampaignInput, StrictModel

router = APIRouter(prefix="/v1", tags=["Daily growth employee"])


class ScheduleInput(StrictModel):
    enabled: bool
    goal: str = Field(min_length=10, max_length=1000)
    timezone: str = Field(min_length=2, max_length=100)
    hour: int = Field(ge=0, le=23)
    frequency: Literal["daily", "weekly", "monthly"] = "daily"
    posts_per_day: int = Field(default=1, ge=1, le=5)
    weekday: int = Field(default=0, ge=0, le=6)
    month_day: int = Field(default=1, ge=1, le=28)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use a valid IANA timezone") from None
        return value


def next_due(hour, zone, after, frequency="daily", weekday=0, month_day=1):
    local = datetime.fromtimestamp(after, UTC).astimezone(ZoneInfo(zone))
    candidate = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if frequency == "weekly":
        candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
        if candidate <= local:
            candidate += timedelta(days=7)
    elif frequency == "monthly":
        candidate = candidate.replace(day=month_day)
        if candidate <= local:
            year, month = (
                (candidate.year + 1, 1)
                if candidate.month == 12
                else (candidate.year, candidate.month + 1)
            )
            candidate = candidate.replace(year=year, month=month)
    elif candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC).timestamp()


def schedule_dict(row):
    return {
        "id": row.id,
        "enabled": row.enabled,
        "goal": row.goal,
        "hour": row.hour,
        "timezone": row.timezone,
        "frequency": row.frequency,
        "posts_per_day": row.posts_per_day,
        "weekday": row.weekday,
        "month_day": row.month_day,
        "next_run": datetime.fromtimestamp(row.next_run, UTC).isoformat(),
        "next_monitor": datetime.fromtimestamp(row.next_monitor, UTC).isoformat(),
        "last_run_id": row.last_run_id,
        "last_error": row.last_error,
    }


@router.get("/projects/{project_id}/daily")
def get_schedule(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    row = db.scalar(select(DailySchedule).where(DailySchedule.project_id == project_id))
    return {
        "schedule": schedule_dict(row) if row else None,
        "research_configured": research.configured(),
        "publishing": "approval_required",
        "output": "1–5 content drafts and one video script per preparation day",
    }


@router.post("/projects/{project_id}/daily")
def save_schedule(
    project_id: str,
    data: ScheduleInput,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    if data.enabled:
        brand = latest_brand(db, project_id)
        if not brand or brand.status != "approved":
            raise HTTPException(409, "Approve the founder profile before enabling daily work")
        if not research.configured():
            raise HTTPException(503, "The search provider is not configured on the server")
    row = db.scalar(select(DailySchedule).where(DailySchedule.project_id == project_id))
    first_enable = not row or not row.enabled
    if not row:
        row = DailySchedule(
            project_id=project_id,
            requested_by=context.user.id,
            **data.model_dump(),
            next_run=time.time()
            if data.frequency == "daily"
            else next_due(
                data.hour, data.timezone, time.time(), data.frequency, data.weekday, data.month_day
            ),
            revision=1,
        )
        db.add(row)
        db.flush()
    else:
        row.enabled, row.goal, row.timezone, row.hour = (
            data.enabled,
            data.goal,
            data.timezone,
            data.hour,
        )
        row.frequency, row.posts_per_day, row.weekday, row.month_day = (
            data.frequency,
            data.posts_per_day,
            data.weekday,
            data.month_day,
        )
        row.requested_by = context.user.id
        row.revision += 1
        row.next_run = (
            time.time()
            if first_enable and data.frequency == "daily"
            else next_due(
                row.hour, row.timezone, time.time(), row.frequency, row.weekday, row.month_day
            )
        )
    row.last_error = None
    if not data.enabled:
        db.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.project_id == project_id,
                WorkflowRun.idempotency_key.like(f"daily:{row.id}:%"),
                WorkflowRun.status.in_(["queued", "running", "research_review"]),
            )
            .values(status="cancelled")
        )
    audit(db, context, "daily.enabled" if data.enabled else "daily.disabled", row.id)
    return schedule_dict(row)


def schedule_one(factory=SessionLocal, clock=None):
    current = time.time() if clock is None else clock
    with factory() as db:
        row = db.scalar(
            select(DailySchedule)
            .where(
                DailySchedule.enabled.is_(True),
                or_(DailySchedule.next_run <= current, DailySchedule.next_monitor <= current),
            )
            .order_by(DailySchedule.next_run)
            .limit(1)
        )
        if not row:
            return False
        schedule_id, revision = row.id, row.revision
        preparing_content = row.next_run <= current
        claimed = db.execute(
            update(DailySchedule)
            .where(
                DailySchedule.id == schedule_id,
                DailySchedule.enabled.is_(True),
                DailySchedule.revision == revision,
                or_(DailySchedule.next_run <= current, DailySchedule.next_monitor <= current),
            )
            .values(
                **(
                    {
                        "next_run": current + 600,
                        "next_monitor": current + 600,
                        "revision": revision + 1,
                    }
                    if preparing_content
                    else {"next_monitor": current + 600, "revision": revision + 1}
                )
            )
        )
        if claimed.rowcount != 1:
            db.rollback()
            return True
        db.commit()
    try:
        with factory() as db:
            # A write claim serializes disabling with creation of today's job.
            claimed = db.execute(
                update(DailySchedule)
                .where(
                    DailySchedule.id == schedule_id,
                    DailySchedule.enabled.is_(True),
                    DailySchedule.revision == revision + 1,
                )
                .values(revision=revision + 1)
            )
            if claimed.rowcount != 1:
                db.rollback()
                return True
            row = db.get(DailySchedule, schedule_id)
            project = db.get(Project, row.project_id)
            member = db.scalar(
                select(Membership).where(
                    Membership.user_id == row.requested_by,
                    Membership.organization_id == project.organization_id,
                    Membership.role == "owner",
                )
            )
            if not member:
                raise HTTPException(403, "Owner access revoked")
            ctx = Tenant(
                db.get(User, row.requested_by),
                db.get(Organization, project.organization_id),
                "owner",
            )
            today = datetime.fromtimestamp(current, UTC).astimezone(ZoneInfo(row.timezone)).date()
            key = (
                f"daily:{row.id}:{today.isoformat()}"
                if preparing_content
                else f"daily:{row.id}:monitor:{today.isoformat()}"
            )
            existing = db.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == project.organization_id,
                    WorkflowRun.idempotency_key == key,
                )
            )
            if existing:
                row.last_run_id = existing.id
            else:
                queued = queue_workflow(
                    project.id,
                    CampaignInput(
                        goal=row.goal,
                        week_start=today,
                        launch_date=today + timedelta(days=14),
                        research_mode="automatic",
                        cadence="daily",
                        posts_per_day=row.posts_per_day,
                        research_only=not preparing_content,
                    ),
                    key,
                    ctx,
                    db,
                )
                row.last_run_id = queued["id"]
            row.last_error = None
            if preparing_content:
                row.next_run = next_due(
                    row.hour, row.timezone, current, row.frequency, row.weekday, row.month_day
                )
            row.next_monitor = next_due(row.hour, row.timezone, current)
            db.commit()
    except HTTPException as error:
        with factory() as db:
            db.execute(
                update(DailySchedule)
                .where(DailySchedule.id == schedule_id, DailySchedule.revision == revision + 1)
                .values(
                    enabled=False,
                    last_error={
                        403: "owner_access_revoked",
                        409: "brand_approval_required",
                        429: "monthly_allowance_reached",
                        503: "provider_not_configured",
                    }.get(error.status_code, "daily_setup_error"),
                )
            )
            db.commit()
    return True
