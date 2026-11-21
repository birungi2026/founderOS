"""Pilot evidence, weekly review, campaign links and server-reported conversions."""

import csv
import hashlib
import hmac
import io
import secrets
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Draft, GrowthEvent, GrowthJourney, PilotObservation, Project
from .security import Tenant, audit, editor, owner, tenant
from .workflows.api import project_for
from .workflows.contracts import StrictModel, revision_hash

router = APIRouter(prefix="/v1", tags=["Weekly review and pilot evidence"])


@router.get("/projects/{project_id}/week")
def week(
    project_id: str,
    start: date | None = None,
    context: Tenant = Depends(tenant),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    start = start or (datetime.now(UTC).date() - timedelta(days=datetime.now(UTC).weekday()))
    end = start + timedelta(days=6)
    rows = db.scalars(select(Draft).where(Draft.project_id == project_id).order_by(Draft.id)).all()
    drafts = [
        {
            "id": d.id,
            "content": d.content,
            "channel": d.channel,
            "status": d.status,
            "planned_date": d.generation.get("planned_date"),
            "revision_hash": revision_hash(d),
            "version": d.revision_number,
        }
        for d in rows
        if d.generation.get("planned_date")
        and start.isoformat() <= d.generation["planned_date"] <= end.isoformat()
    ]
    journeys = db.scalars(
        select(GrowthJourney)
        .where(GrowthJourney.project_id == project_id)
        .order_by(GrowthJourney.created_at.desc())
        .limit(30)
    ).all()
    return {
        "start": start,
        "end": end,
        "drafts": drafts,
        "videos": [
            {
                "id": r.id,
                "status": r.status,
                "caption": r.data.get("caption", ""),
                "results": r.data.get("results"),
                "observed_at": r.data.get("observed_at"),
                "publication": {
                    k: v for k, v in r.data.get("publication", {}).items() if k not in {"video_url"}
                },
                "created_at": r.created_at,
            }
            for r in journeys
        ],
        "note": "Draft approval does not publish. Each video needs its own account/time approval.",
    }


@router.get("/projects/{project_id}/week/export")
def export_week(
    project_id: str,
    start: date | None = None,
    context: Tenant = Depends(tenant),
    db: Session = Depends(get_db),
):
    result = week(project_id, start, context, db)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Channel", "Content", "Status"])
    for draft in result["drafts"]:
        writer.writerow(
            [
                ("'" + str(v)) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v
                for v in [
                    draft["planned_date"],
                    draft["channel"],
                    draft["content"],
                    draft["status"],
                ]
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rymu-week.csv"},
    )


class PilotConfig(StrictModel):
    revision: int = Field(default=0, ge=0)
    cohort: Literal["immediate", "delayed", "not_enrolled"] = "not_enrolled"
    segment: Literal["coach", "creator", "founder", "other"] = "other"
    primary_goal: Literal["followers", "inquiries", "paying_customers"] = "followers"
    starts_on: date
    offer: str = Field(default="", max_length=500)


@router.post("/projects/{project_id}/pilot/config")
def configure(
    project_id: str,
    data: PilotConfig,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    project = project_for(db, project_id, context)
    db.refresh(context.organization, with_for_update=True)
    db.refresh(project)
    current = project.data.get("pilot", {})
    if current.get("revision", 0) != data.revision:
        raise HTTPException(409, "Pilot settings changed. Reload first.")
    project.data = {
        **project.data,
        "pilot": {**data.model_dump(mode="json"), "revision": data.revision + 1},
    }
    audit(db, context, "pilot.configured", project.id)
    return project.data["pilot"]


class Observation(StrictModel):
    external_id: str = Field(min_length=8, max_length=100)
    kind: Literal["baseline", "followup"]
    channel: str = Field(min_length=2, max_length=30)
    starts_on: date
    ends_on: date
    followers: int | None = Field(default=None, ge=0, le=1000000000)
    inquiries: int | None = Field(default=None, ge=0, le=1000000)
    paying_customers: int | None = Field(default=None, ge=0, le=1000000)
    delivered: int = Field(default=0, ge=0, le=1000)
    published: int = Field(default=0, ge=0, le=1000)
    editing_minutes: int = Field(default=0, ge=0, le=100000)
    revenue_cents: int | None = Field(default=None, ge=0, le=100000000)
    cost_cents: int | None = Field(default=None, ge=0, le=100000000)
    renewed: bool | None = None
    likely_authentic: int = Field(default=0, ge=0, le=1000)
    suspicious: int = Field(default=0, ge=0, le=1000)
    unknown: int = Field(default=0, ge=0, le=1000)
    paid_promotion: bool = False
    attested: Literal[True]

    @model_validator(mode="after")
    def valid(self):
        if (
            self.ends_on < self.starts_on
            or self.ends_on > datetime.now(UTC).date()
            or (self.ends_on - self.starts_on).days > 90
        ):
            raise ValueError("Use a completed observation window of at most 91 days")
        if self.published > self.delivered:
            raise ValueError("Published posts cannot exceed delivered posts")
        if self.likely_authentic + self.suspicious + self.unknown > 1000:
            raise ValueError("Limit the review sample to 1000 accounts")
        return self


@router.post("/projects/{project_id}/pilot/observations", status_code=201)
def observe(
    project_id: str,
    data: Observation,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    db.refresh(context.organization, with_for_update=True)
    existing = db.scalar(
        select(PilotObservation).where(
            PilotObservation.project_id == project_id,
            PilotObservation.external_id == data.external_id,
        )
    )
    payload = {**data.model_dump(mode="json"), "source": "operator_reported"}
    if existing:
        if existing.data != payload:
            raise HTTPException(409, "Observation ID already used with different data")
        return {"id": existing.id}
    row = PilotObservation(
        project_id=project_id,
        external_id=data.external_id,
        observed_by=context.user.id,
        data=payload,
    )
    db.add(row)
    db.flush()
    audit(db, context, "pilot.observed", row.id)
    return {"id": row.id}


@router.get("/projects/{project_id}/pilot")
def report(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project = project_for(db, project_id, context)
    rows = db.scalars(
        select(PilotObservation)
        .where(PilotObservation.project_id == project_id)
        .order_by(PilotObservation.created_at, PilotObservation.id)
    ).all()
    channels = {}
    for row in rows:
        channels.setdefault(row.data["channel"], []).append(row)
    comparisons = []
    for channel, observations in channels.items():
        baseline = next(
            (r.data for r in reversed(observations) if r.data["kind"] == "baseline"), None
        )
        latest = next(
            (r.data for r in reversed(observations) if r.data["kind"] == "followup"), None
        )
        if not baseline or not latest:
            continue
        # Overlapping baseline/follow-up windows are reported, never described as growth evidence.
        nonoverlap = baseline["ends_on"] < latest["starts_on"]
        delta = (
            latest["followers"] - baseline["followers"]
            if nonoverlap and latest["followers"] is not None and baseline["followers"] is not None
            else None
        )
        comparisons.append(
            {
                "channel": channel,
                "follower_change": delta,
                "baseline": baseline,
                "latest": latest,
                "comparable": nonoverlap,
                "note": "Separate paid promotion; counts are operator reported. This does not establish causation or certify followers as human.",
            }
        )
    return {
        "config": project.data.get("pilot"),
        "observations": [{"id": r.id, **r.data, "created_at": r.created_at} for r in rows],
        "comparisons": comparisons,
        "note": "Pilot evidence, not a growth guarantee. Manual audience samples are judgments; unknown accounts stay unknown. Compare equal windows and cohorts outside the app before making claims.",
    }


class LinkInput(StrictModel):
    source: Literal["instagram", "facebook", "linkedin", "tiktok"]
    campaign: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


@router.post("/projects/{project_id}/campaign-link")
def campaign_link(
    project_id: str,
    data: LinkInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    from .workflows.api import latest_brand

    project_for(db, project_id, context)
    brand = latest_brand(db, project_id)
    url = brand.data.get("website_url") if brand and brand.status == "approved" else None
    parsed = urlsplit(url or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(409, "Approve an HTTPS website in your brand profile first")
    query = {k: v for k, v in parse_qsl(parsed.query) if not k.startswith("utm_")}
    query.update(utm_source=data.source, utm_medium="organic_social", utm_campaign=data.campaign)
    return {
        "url": urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
        ),
        "note": "UTM tags identify referral sources in your website analytics; they do not prove causation.",
    }


@router.post("/projects/{project_id}/conversion-key")
def conversion_key(
    project_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)
):
    project = project_for(db, project_id, context)
    key = secrets.token_urlsafe(32)
    project.data = {**project.data, "conversion_key_hash": hashlib.sha256(key.encode()).hexdigest()}
    audit(db, context, "conversion.key_rotated", project_id)
    return {"key": key, "note": "Store server-side only. Rotating invalidates the previous key."}


class Conversion(StrictModel):
    project_id: str = Field(max_length=36)
    external_id: str = Field(min_length=8, max_length=200)
    kind: Literal["lead", "signup", "paying_customer"]
    channel: str = Field(min_length=2, max_length=100)
    campaign: str = Field(default="unassigned", max_length=100)


@router.post("/conversions", status_code=201)
def conversion(
    data: Conversion, x_rymu_conversion_key: str = Header(default=""), db: Session = Depends(get_db)
):
    project = db.get(Project, data.project_id)
    supplied = hashlib.sha256(x_rymu_conversion_key.encode()).hexdigest()
    if not project or not hmac.compare_digest(
        project.data.get("conversion_key_hash", ""), supplied
    ):
        raise HTTPException(401, "Invalid conversion credentials")
    db.refresh(db.get(Project, project.id), with_for_update=True)
    row = db.scalar(
        select(GrowthEvent).where(
            GrowthEvent.project_id == project.id, GrowthEvent.external_id == data.external_id
        )
    )
    fields = data.model_dump(exclude={"project_id"})
    if row:
        if any(getattr(row, k) != v for k, v in fields.items()):
            raise HTTPException(409, "Conversion ID already used")
        return {"id": row.id, "duplicate": True, "verification": "server_reported"}
    row = GrowthEvent(project_id=project.id, **fields)
    db.add(row)
    db.flush()
    return {"id": row.id, "verification": "server_reported_not_independently_payment_verified"}


class AccountObservation(StrictModel):
    account_id: str = Field(max_length=36)
    external_id: str = Field(min_length=8, max_length=100)
    kind: Literal["baseline", "followup"]


@router.post("/projects/{project_id}/pilot/account-observation", status_code=201)
def account_observation(
    project_id: str,
    data: AccountObservation,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    from .models import SocialAccount
    from .social import sync

    project_for(db, project_id, context)
    row = db.get(SocialAccount, data.account_id)
    if not row or row.project_id != project_id:
        raise HTTPException(404, "Account not found")
    existing = db.scalar(
        select(PilotObservation).where(
            PilotObservation.project_id == project_id,
            PilotObservation.external_id == data.external_id,
        )
    )
    if existing:
        if existing.data.get("account_id") != row.id or existing.data.get("kind") != data.kind:
            raise HTTPException(409, "Observation ID already used")
        return {"id": existing.id}
    snapshot = sync(row.id, context, db)["snapshot"]
    count = snapshot.get("profile", {}).get("followers_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise HTTPException(
            409, "This account does not expose a follower total; record a manual baseline instead"
        )
    observed = datetime.fromtimestamp(snapshot["observed_at"], UTC).date().isoformat()
    result = PilotObservation(
        project_id=project_id,
        external_id=data.external_id,
        observed_by=context.user.id,
        data={
            "kind": data.kind,
            "channel": row.provider,
            "account_id": row.id,
            "source": "connected_account_snapshot",
            "starts_on": observed,
            "ends_on": observed,
            "followers": count,
            "inquiries": None,
            "paying_customers": None,
            "delivered": 0,
            "published": 0,
            "editing_minutes": 0,
            "likely_authentic": 0,
            "suspicious": 0,
            "unknown": 0,
            "paid_promotion": False,
            "cost_cents": None,
            "revenue_cents": None,
            "renewed": None,
        },
    )
    db.add(result)
    db.flush()
    return {"id": result.id}
