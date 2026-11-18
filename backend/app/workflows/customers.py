from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import CustomerLead, Project, ResearchSource
from ..security import Tenant, audit, editor, tenant
from .api import project_for
from .contracts import StrictModel, digest

router = APIRouter(prefix="/v1", tags=["Customer acquisition"])
STAGES = ["identified", "contacted", "conversation", "trial", "won", "lost"]


class LeadInput(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    website: HttpUrl = Field(max_length=2000)
    source_id: str | None = None
    next_action: str = Field(min_length=3, max_length=1000)


class LeadUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    stage: Literal["identified", "contacted", "conversation", "trial", "won", "lost"]
    next_action: str = Field(min_length=3, max_length=1000)
    paying_customer_confirmed: bool = False


def lead_dict(lead):
    return {
        key: getattr(lead, key)
        for key in [
            "id",
            "name",
            "website",
            "source_id",
            "stage",
            "next_action",
            "version",
            "created_at",
        ]
    }


def funnel(db, project_id):
    rows = db.scalars(select(CustomerLead).where(CustomerLead.project_id == project_id)).all()
    counts = {stage: sum(row.stage == stage for row in rows) for stage in STAGES}
    project = db.get(Project, project_id)
    target = project.data.get("goal_customers", 50)
    return {
        "counts": counts,
        "paying_customers": counts["won"],
        "target_customers": target,
        "remaining": max(0, target - counts["won"]),
        "verification": "founder_confirmed; not payment-provider verified",
    }


@router.get("/projects/{project_id}/customers")
def customers(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    rows = db.scalars(
        select(CustomerLead)
        .where(CustomerLead.project_id == project_id)
        .order_by(CustomerLead.created_at.desc())
        .limit(200)
    ).all()
    return {"leads": [lead_dict(lead) for lead in rows], "funnel": funnel(db, project_id)}


@router.post("/projects/{project_id}/customers", status_code=201)
def add_customer(
    project_id: str,
    data: LeadInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    if data.source_id and not db.scalar(
        select(ResearchSource.id).where(
            ResearchSource.id == data.source_id, ResearchSource.project_id == project_id
        )
    ):
        raise HTTPException(404, "Research source not found in this project")
    website = str(data.website)
    # One company/site per project; visits and content views never create customers.
    identity = digest(urlsplit(website).hostname.lower().rstrip(".").removeprefix("www."))
    lead = CustomerLead(
        project_id=project_id,
        name=data.name,
        website=website,
        identity_key=identity,
        source_id=data.source_id,
        next_action=data.next_action,
    )
    db.add(lead)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This company is already in the customer pipeline") from None
    audit(db, context, "lead.created", lead.id)
    return lead_dict(lead)


@router.post("/customers/{lead_id}")
def update_customer(
    lead_id: str, data: LeadUpdate, context: Tenant = Depends(editor), db: Session = Depends(get_db)
):

    lead = db.scalar(
        select(CustomerLead)
        .join(Project)
        .where(CustomerLead.id == lead_id, Project.organization_id == context.organization.id)
    )
    if not lead:
        raise HTTPException(404, "Lead not found")
    if data.stage == "won" and not data.paying_customer_confirmed:
        raise HTTPException(422, "Confirm that this lead has actually become a paying customer")
    changed = db.execute(
        update(CustomerLead)
        .where(CustomerLead.id == lead.id, CustomerLead.version == data.expected_version)
        .values(stage=data.stage, next_action=data.next_action, version=CustomerLead.version + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Lead changed; refresh before updating")
    db.refresh(lead)
    audit(db, context, "lead." + data.stage, lead.id)
    return lead_dict(lead)
