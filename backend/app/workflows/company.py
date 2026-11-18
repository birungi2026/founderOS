from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, HttpUrl
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import Tenant, audit, editor, tenant
from .api import project_for
from .contracts import StrictModel

router = APIRouter(prefix="/v1", tags=["Company understanding"])


class CompanyInput(StrictModel):
    problem: str = Field(min_length=10, max_length=2000)
    solution: str = Field(min_length=10, max_length=2000)
    target_customers: str = Field(min_length=3, max_length=500)
    differentiator: str = Field(default="", max_length=1500)
    competitors: list[HttpUrl] = Field(default_factory=list, max_length=3)
    expected_version: int = Field(default=0, ge=0)


def company_snapshot(project):
    return project.data.get(
        "company_profile",
        {
            "problem": project.data.get("problem", ""),
            "solution": project.data["description"],
            "target_customers": project.data["audience"],
            "differentiator": "",
            "competitors": [],
            "version": 0,
        },
    )


@router.get("/projects/{project_id}/company")
def get_company(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    return company_snapshot(project_for(db, project_id, context))


@router.post("/projects/{project_id}/company")
def save_company(
    project_id: str,
    data: CompanyInput,
    context: Tenant = Depends(editor),
    db: Session = Depends(get_db),
):
    project = project_for(db, project_id, context)
    previous = company_snapshot(project)
    if data.expected_version != previous.get("version", 0):
        raise HTTPException(409, "Company profile changed; reload before editing")
    profile = {
        **data.model_dump(mode="json", exclude={"expected_version"}),
        "version": data.expected_version + 1,
    }
    # Serialize with other company-profile writes without altering the product's identity.
    # JSON equality is unavailable for PostgreSQL's JSON type, so use a row lock there.
    db.refresh(project, with_for_update=True)
    if company_snapshot(project).get("version", 0) != data.expected_version:
        raise HTTPException(409, "Company profile changed; reload before editing")
    project.data = {
        **project.data,
        "problem": data.problem,
        "description": data.solution,
        "audience": data.target_customers,
        "company_profile": profile,
    }
    audit(db, context, "company.profile_updated", project.id)
    return profile
