"""Tenant-scoped, explicitly approved interview/video/publication journey."""

import hashlib
import hmac
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..billing import active, render_seconds, reserve
from ..database import get_db
from ..models import GrowthJourney, Project, SocialAccount
from ..security import Tenant, audit, owner, tenant
from ..workflows.api import (
    approve_brand,
    get_workflow,
    latest_brand,
    project_for,
    queue_workflow,
    save_brand,
)
from ..workflows.company import CompanyInput, save_company
from ..workflows.contracts import BrandInput, CampaignInput, StrictModel

router = APIRouter(prefix="/v1", tags=["Growth journey"])


def workspace_enabled(organization_id):
    allowed = {
        value.strip()
        for value in os.getenv("JOURNEY_ENABLED_ORGANIZATIONS", "").split(",")
        if value.strip()
    }
    return organization_id in allowed or "*" in allowed


def training_enabled(organization_id):
    allowed = {
        value.strip()
        for value in os.getenv("TAVUS_TRAINING_ORGANIZATIONS", "").split(",")
        if value.strip()
    }
    return organization_id in allowed or "*" in allowed


def require_enabled(context):
    if not workspace_enabled(context.organization.id):
        raise HTTPException(
            503, "This workspace is not enabled for paid provider jobs. Ask your administrator."
        )


def media_root():
    return Path(os.getenv("JOURNEY_MEDIA_DIR", "/tmp/rymu-media"))


def media_url(journey_id):
    key = os.getenv("JOURNEY_MEDIA_SIGNING_KEY", "")
    base = os.getenv("PUBLIC_API_URL", "")
    if len(key) < 32 or not base.startswith("https://"):
        raise HTTPException(
            503, "Public HTTPS media URL and signing key are required for Tavus training"
        )
    expiry = int(time.time()) + 86400
    message = f"{journey_id}:{expiry}"
    signature = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return (
        f"{base.rstrip('/')}/v1/journey-media/{journey_id}?expires={expiry}&signature={signature}"
    )


def lookup(db, project_id, journey_id, context):
    project_for(db, project_id, context)
    row = db.scalar(
        select(GrowthJourney).where(
            GrowthJourney.id == journey_id, GrowthJourney.project_id == project_id
        )
    )
    if not row:
        raise HTTPException(404, "Journey not found")
    return row


def change(db, row, revision, statuses):
    changed = db.execute(
        update(GrowthJourney)
        .where(
            GrowthJourney.id == row.id,
            GrowthJourney.revision == revision,
            GrowthJourney.status.in_(statuses),
        )
        .values(revision=revision + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "This journey changed. Refresh before continuing.")
    db.refresh(row)


def public(row):
    fields = {k: v for k, v in row.data.items() if k not in {"media_path", "media_mime"}}
    if row.data.get("asset_id") and row.status == "video_ready":
        from ..media import video_url

        fields["video_url"] = video_url(row.data["asset_id"])
    return {
        "id": row.id,
        "status": row.status,
        "revision": row.revision,
        "error_code": row.error_code,
        "created_at": row.created_at,
        "interview_available": bool(row.data.get("media_path")),
        **fields,
    }


def capabilities():
    return {
        "transcription": bool(os.getenv("TRANSCRIPTION_API_KEY")),
        "model": bool(
            os.getenv("LLM_API_KEY")
            and os.getenv("LLM_MODEL")
            and os.getenv("GENERATION_MODE") == "llm"
        ),
        "research": bool(os.getenv("BRAVE_SEARCH_API_KEY")),
        "video": bool(os.getenv("TAVUS_API_KEY")),
        "training": bool(
            os.getenv("PUBLIC_API_URL", "").startswith("https://")
            and len(os.getenv("JOURNEY_MEDIA_SIGNING_KEY", "")) >= 32
        ),
        "publishing": os.getenv("JOURNEY_PUBLISHING_ENABLED") == "true"
        or os.getenv("INSTAGRAM_PUBLISHING_ENABLED") == "true",
    }


@router.get("/projects/{project_id}/journeys")
def journeys(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    rows = db.scalars(
        select(GrowthJourney)
        .where(GrowthJourney.project_id == project_id)
        .order_by(GrowthJourney.created_at.desc())
        .limit(30)
    )
    return {
        "capabilities": {
            **capabilities(),
            "workspace_enabled": workspace_enabled(context.organization.id),
            "training": capabilities()["training"] and training_enabled(context.organization.id),
        },
        "has_approved_brand": bool(
            (brand := latest_brand(db, project_id)) and brand.status == "approved"
        ),
        "journeys": [
            {
                **public(row),
                "can_reuse_replica": bool(
                    row.data.get("trained_at")
                    and row.data.get("clone_consented_by") == context.user.id
                ),
            }
            for row in rows
        ],
    }


@router.get("/projects/{project_id}/journeys/{journey_id}")
def get_journey(
    project_id: str,
    journey_id: str,
    context: Tenant = Depends(tenant),
    db: Session = Depends(get_db),
):
    row = lookup(db, project_id, journey_id, context)
    result = public(row)
    if row.data.get("run_id"):
        result["workflow"] = get_workflow(row.data["run_id"], context, db)
    return result


@router.post("/projects/{project_id}/journeys/interview", status_code=202)
async def upload(
    project_id: str,
    request: Request,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    project_for(db, project_id, context)
    if request.query_params.get("consent") != "yes":
        raise HTTPException(422, "Consent to transcription is required")
    if not capabilities()["transcription"] or not capabilities()["model"]:
        raise HTTPException(503, "Interview transcription and the model must be configured first")
    if (
        db.scalar(
            select(func.count())
            .select_from(GrowthJourney)
            .where(
                GrowthJourney.project_id == project_id,
                GrowthJourney.data["media_path"].as_string().is_not(None),
            )
        )
        >= 30
    ):
        raise HTTPException(429, "Journey storage limit reached; delete an old interview first")
    mime = request.headers.get("content-type", "").split(";")[0]
    if mime not in {"video/webm", "video/mp4"}:
        raise HTTPException(422, "Upload an MP4 or WebM video")
    size = 0
    root = media_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (secrets.token_hex(24) + (".mp4" if mime == "video/mp4" else ".webm"))
    try:
        with path.open("xb") as target:
            os.chmod(path, 0o600)
            async for chunk in request.stream():
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(413, "Interview must be no larger than 25 MB")
                target.write(chunk)
        with path.open("rb") as source:
            head = source.read(32)
        valid = (mime == "video/webm" and head.startswith(b"\x1aE\xdf\xa3")) or (
            mime == "video/mp4" and b"ftyp" in head[:16]
        )
        if size < 16 or not valid:
            raise HTTPException(422, "The file does not match its video format")
        db.refresh(context.organization, with_for_update=True)
        period = datetime.now(UTC).strftime("%Y-%m")
        used = db.scalar(
            select(func.count())
            .select_from(GrowthJourney)
            .join(Project)
            .where(
                Project.organization_id == context.organization.id,
                GrowthJourney.created_at.startswith(period),
                GrowthJourney.data["transcription_consent_at"].as_float().is_not(None),
            )
        )
        if used >= int(os.getenv("JOURNEY_MONTHLY_INTERVIEW_LIMIT", "30")):
            raise HTTPException(429, "Monthly interview processing allowance reached")
        row = GrowthJourney(
            project_id=project_id,
            requested_by=context.user.id,
            data={
                "media_path": str(path),
                "media_mime": mime,
                "transcription_consent_at": time.time(),
            },
        )
        db.add(row)
        db.flush()
        audit(db, context, "journey.interview_uploaded", row.id)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return public(row)


@router.get("/journey-media/{journey_id}")
def training_media(journey_id: str, expires: int, signature: str, db: Session = Depends(get_db)):
    key = os.getenv("JOURNEY_MEDIA_SIGNING_KEY", "")
    expected = hmac.new(
        key.encode(), f"{journey_id}:{expires}".encode(), hashlib.sha256
    ).hexdigest()
    if (
        len(key) < 32
        or not time.time() < expires <= time.time() + 86400
        or not hmac.compare_digest(signature, expected)
    ):
        raise HTTPException(403, "Media link expired or invalid")
    row = db.get(GrowthJourney, journey_id)
    if (
        not row
        or not row.data.get("clone_consent_at")
        or not Path(row.data.get("media_path", "")).is_file()
    ):
        raise HTTPException(404, "Training media unavailable")
    return FileResponse(
        row.data["media_path"],
        media_type=row.data["media_mime"],
        headers={"Cache-Control": "no-store"},
    )


class Decision(StrictModel):
    revision: int = Field(ge=1)


class ConfirmBrand(Decision):
    brand: BrandInput
    company: CompanyInput


@router.post("/projects/{project_id}/journeys/{journey_id}/confirm-brand")
def confirm_brand(
    project_id: str,
    journey_id: str,
    data: ConfirmBrand,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["interview_review"])
    save_company(project_id, data.company, context, db)
    brand = save_brand(project_id, data.brand, context, db)
    approve_brand(project_id, brand["id"], context, db)
    row.data = {**row.data, "brand_id": brand["id"], "confirmed_at": time.time()}
    row.status = "brand_confirmed"
    audit(db, context, "journey.brand_confirmed", row.id)
    return public(row)


class ResearchRequest(Decision):
    goal: str = Field(min_length=10, max_length=1000)


@router.post("/projects/{project_id}/journeys/{journey_id}/research", status_code=202)
def start_research(
    project_id: str,
    journey_id: str,
    data: ResearchRequest,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["brand_confirmed"])
    latest = latest_brand(db, project_id)
    if not latest or latest.id != row.data["brand_id"] or latest.status != "approved":
        raise HTTPException(
            409, "Brand changed. Confirm the latest brand before starting another journey."
        )
    if not capabilities()["model"]:
        raise HTTPException(
            503, "Enable a configured AI model for this journey; template mode is not used here"
        )
    today = datetime.now(UTC).date()
    result = queue_workflow(
        project_id,
        CampaignInput(
            goal=data.goal,
            week_start=today,
            launch_date=today,
            cadence="daily",
            posts_per_day=1,
            research_mode="automatic",
        ),
        "journey-" + row.id,
        context,
        db,
    )
    row.data = {**row.data, "run_id": result["id"]}
    row.status = "researching"
    return public(row)


class ContentInput(Decision):
    script: str = Field(min_length=20, max_length=1200)
    caption: str = Field(min_length=10, max_length=2000)


@router.post("/projects/{project_id}/journeys/{journey_id}/content")
def edit_content(
    project_id: str,
    journey_id: str,
    data: ContentInput,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["content_review", "video_ready"])
    changed_script = data.script != row.data.get("script")
    if row.data.get("asset_id") and changed_script:
        raise HTTPException(
            409,
            "Real footage has no generated script. Make a new clip to change its spoken content.",
        )
    row.data = {**row.data, "script": data.script, "caption": data.caption}
    if changed_script:
        row.data = {k: v for k, v in row.data.items() if k not in {"video_id", "video_url"}}
        row.status = "content_review"
    audit(db, context, "journey.content_edited", row.id)
    return public(row)


class CloneConsent(Decision):
    consent: bool


@router.post("/projects/{project_id}/journeys/{journey_id}/train", status_code=202)
def train(
    project_id: str,
    journey_id: str,
    data: CloneConsent,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["content_review"])
    active(db, context.organization.id)
    if not training_enabled(context.organization.id):
        raise HTTPException(403, "Custom-avatar setup has not been provisioned for this workspace")
    if data.consent is not True or not capabilities()["video"]:
        raise HTTPException(422, "Tavus configuration and your likeness/voice consent are required")
    if not Path(row.data.get("media_path", "")).is_file():
        raise HTTPException(409, "The interview was removed. Upload a new interview for training.")
    media_url(row.id)  # Reject bad deployment configuration before reserving a paid call.
    if row.data.get("replica_id"):
        raise HTTPException(409, "This interview already has a trained replica")
    db.refresh(context.organization, with_for_update=True)
    period = datetime.now(UTC).strftime("%Y-%m")
    rows = db.scalars(
        select(GrowthJourney)
        .join(Project)
        .where(Project.organization_id == context.organization.id)
    ).all()
    used = sum(1 for item in rows if item.data.get("training_period") == period)
    if used >= int(os.getenv("JOURNEY_MONTHLY_TRAINING_LIMIT", "1")):
        raise HTTPException(429, "Monthly replica training allowance reached")
    row.data = {
        **row.data,
        "training_period": period,
        "clone_consent_at": time.time(),
        "clone_consented_by": context.user.id,
    }
    row.status = "training_queued"
    return public(row)


@router.post("/projects/{project_id}/journeys/{journey_id}/render", status_code=202)
def render(
    project_id: str,
    journey_id: str,
    data: Decision,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["content_review"])
    if not row.data.get("replica_id") or not row.data.get("clone_consent_at"):
        raise HTTPException(409, "Complete Tavus training and consent first")
    if not capabilities()["video"]:
        raise HTTPException(503, "Tavus video generation is not configured")
    limit = int(os.getenv("JOURNEY_MONTHLY_RENDER_LIMIT", "10"))
    period = datetime.now(UTC).strftime("%Y-%m")
    db.refresh(context.organization, with_for_update=True)
    rows = db.scalars(
        select(GrowthJourney)
        .join(Project)
        .where(Project.organization_id == context.organization.id)
    ).all()
    reserved = sum(
        r.data.get("period_render_attempts", 0)
        for r in rows
        if r.data.get("render_period") == period
    )
    attempts = row.data.get("render_attempts", 0)
    if reserved >= limit or attempts >= 3:
        raise HTTPException(429, "Video generation allowance reached")
    if (
        not 20 <= len(row.data.get("script", "")) <= 1200
        or not 10 <= len(row.data.get("caption", "")) <= 2000
    ):
        raise HTTPException(
            422, "Save a script of 20–1200 characters and a caption of 10–2000 characters first"
        )
    seconds = render_seconds(row.data["script"])
    reserve(
        db, context.organization.id, "video_seconds", seconds, f"render-{row.id}-{attempts + 1}"
    )
    row.data = {
        **row.data,
        "reserved_seconds": seconds,
        "render_attempts": attempts + 1,
        "render_period": period,
        "period_render_attempts": (
            row.data.get("period_render_attempts", 0)
            if row.data.get("render_period") == period
            else 0
        )
        + 1,
    }
    row.status = "render_queued"
    return public(row)


def account_for(db, project_id, account_id):
    row = db.scalar(
        select(SocialAccount).where(
            SocialAccount.id == account_id,
            SocialAccount.project_id == project_id,
            SocialAccount.provider.in_(["facebook", "instagram"]),
            SocialAccount.status == "connected",
            SocialAccount.expires_at > time.time(),
        )
    )
    required = (
        {"pages_manage_posts", "pages_read_engagement"}
        if row and row.provider == "facebook"
        else {"instagram_business_basic", "instagram_business_content_publish"}
    )
    if not row or not required.issubset(row.permissions):
        raise HTTPException(
            409,
            "Connect a Facebook Page or Instagram professional account with publishing permission",
        )
    return row


class ScheduleInput(Decision):
    account_id: str = Field(min_length=1, max_length=36)
    publish_at: datetime
    approve: bool


@router.post("/projects/{project_id}/journeys/{journey_id}/schedule")
def schedule(
    project_id: str,
    journey_id: str,
    data: ScheduleInput,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    row = lookup(db, project_id, journey_id, context)
    active(db, context.organization.id)
    change(db, row, data.revision, ["video_ready"])
    account = account_for(db, project_id, data.account_id)
    flag = (
        "JOURNEY_PUBLISHING_ENABLED"
        if account.provider == "facebook"
        else "INSTAGRAM_PUBLISHING_ENABLED"
    )
    if os.getenv(flag) != "true" or not data.approve or data.publish_at.tzinfo is None:
        raise HTTPException(
            422,
            "Enable publishing, approve the exact video/caption and choose a time with a timezone",
        )
    when = data.publish_at.timestamp()
    if not time.time() + 60 <= when <= time.time() + 30 * 86400:
        raise HTTPException(422, "Choose a posting time between one minute and 30 days from now")
    if account.expires_at <= when:
        raise HTTPException(
            409,
            "This Page connection expires before the posting time. Reconnect or choose an earlier time.",
        )
    snapshot = {
        "video_id": row.data["video_id"],
        "video_url": row.data["video_url"],
        "caption": row.data["caption"],
        "account_id": account.id,
        "provider": account.provider,
        "asset_id": row.data.get("asset_id"),
        "publish_at": when,
    }
    row.data = {
        **row.data,
        "publication": snapshot,
        "approved_by": context.user.id,
        "approved_at": time.time(),
    }
    row.status, row.next_check = "scheduled", when
    audit(db, context, "journey.post_approved_and_scheduled", row.id)
    return public(row)


@router.post("/projects/{project_id}/journeys/{journey_id}/cancel")
def cancel(
    project_id: str,
    journey_id: str,
    data: Decision,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["scheduled"])
    row.status = "video_ready"
    row.data = {
        k: v for k, v in row.data.items() if k not in {"publication", "approved_by", "approved_at"}
    }
    audit(db, context, "journey.post_cancelled", row.id)
    return public(row)


@router.post("/projects/{project_id}/journeys/{journey_id}/delete-interview")
def delete_interview(
    project_id: str,
    journey_id: str,
    data: Decision,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    row = lookup(db, project_id, journey_id, context)
    change(
        db,
        row,
        data.revision,
        [
            "interview_review",
            "brand_confirmed",
            "content_review",
            "video_ready",
            "failed",
            "uncertain",
            "posted",
            "measured",
            "access_revoked",
            "missed",
        ],
    )
    if row.data.get("media_path"):
        Path(row.data["media_path"]).unlink(missing_ok=True)
    row.data = {
        k: v for k, v in row.data.items() if k not in {"media_path", "media_mime", "transcript"}
    }
    audit(db, context, "journey.interview_deleted", row.id)
    return public(row)


class ConfirmResearch(Decision):
    research_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/projects/{project_id}/journeys/{journey_id}/confirm-research")
def confirm_journey_research(
    project_id: str,
    journey_id: str,
    data: ConfirmResearch,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    from ..workflows.api import ResearchConfirmation, confirm_research

    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["researching"])
    confirm_research(
        row.data["run_id"], ResearchConfirmation(research_hash=data.research_hash), context, db
    )
    return public(row)


@router.post("/projects/{project_id}/journeys/from-brand", status_code=201)
def from_brand(project_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    require_enabled(context)
    project_for(db, project_id, context)
    brand = latest_brand(db, project_id)
    if not brand or brand.status != "approved":
        raise HTTPException(409, "Confirm your brand before creating another post")
    if (
        db.scalar(
            select(func.count())
            .select_from(GrowthJourney)
            .where(GrowthJourney.project_id == project_id)
        )
        >= 300
    ):
        raise HTTPException(
            429, "Journey history limit reached; ask your administrator to archive older history"
        )
    row = GrowthJourney(
        project_id=project_id,
        requested_by=context.user.id,
        status="brand_confirmed",
        data={"brand_id": brand.id, "confirmed_at": time.time()},
    )
    db.add(row)
    db.flush()
    audit(db, context, "journey.started_from_confirmed_brand", row.id)
    return public(row)


class ReuseReplica(Decision):
    source_journey_id: str = Field(min_length=1, max_length=36)
    consent: bool


@router.post("/projects/{project_id}/journeys/{journey_id}/reuse-replica")
def reuse_replica(
    project_id: str,
    journey_id: str,
    data: ReuseReplica,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    require_enabled(context)
    row = lookup(db, project_id, journey_id, context)
    change(db, row, data.revision, ["content_review"])
    source = lookup(db, project_id, data.source_journey_id, context)
    if (
        not data.consent
        or not source.data.get("trained_at")
        or source.data.get("clone_consented_by") != context.user.id
    ):
        raise HTTPException(
            409, "Choose a trained replica that you personally consented to in this project"
        )
    row.data = {
        **row.data,
        "replica_id": source.data["replica_id"],
        "trained_at": source.data["trained_at"],
        "clone_consent_at": time.time(),
        "clone_consented_by": context.user.id,
        "replica_source_journey_id": source.id,
    }
    audit(db, context, "journey.replica_reuse_consented", row.id)
    return public(row)
