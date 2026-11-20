from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    onboarding_mode: Mapped[str] = mapped_column(
        String(20), default="business", server_default="business"
    )


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[float]


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(String(6000))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    generation: Mapped[dict] = mapped_column(JSON, default=dict)
    revision_number: Mapped[int] = mapped_column(default=1, server_default="1")


class Metric(Base):
    __tablename__ = "metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class GrowthEvent(Base):
    __tablename__ = "growth_events"
    __table_args__ = (UniqueConstraint("project_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    channel: Mapped[str] = mapped_column(String(100))
    campaign: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class ResearchSource(Base):
    __tablename__ = "research_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(200))
    excerpt: Mapped[str] = mapped_column(String(4000))
    verified_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(30), default="manual", server_default="manual")
    source_key: Mapped[str | None] = mapped_column(String(64), index=True)
    observed_at: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Publication(Base):
    __tablename__ = "publications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"), unique=True)
    content: Mapped[str] = mapped_column(String(6000))
    channel: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    provider_reference: Mapped[str | None] = mapped_column(String(300), default=None)
    error_code: Mapped[str | None] = mapped_column(String(80), default=None)
    approved_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class BrandVersion(Base):
    __tablename__ = "brand_versions"
    __table_args__ = (UniqueConstraint("project_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int]
    data: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    brand_version_id: Mapped[str] = mapped_column(ForeignKey("brand_versions.id"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    context: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    progress: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    claim_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[float | None]
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("run_id", "agent"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    agent: Mapped[str] = mapped_column(String(30))
    artifact: Mapped[dict] = mapped_column(JSON)
    generation_mode: Mapped[str] = mapped_column(String(20))
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class WorkflowUsage(Base):
    __tablename__ = "workflow_usage"
    __table_args__ = (UniqueConstraint("organization_id", "period"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    period: Mapped[str] = mapped_column(String(7))
    runs_reserved: Mapped[int] = mapped_column(default=0)


class ContentRevision(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (UniqueConstraint("draft_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    draft_id: Mapped[str] = mapped_column(ForeignKey("drafts.id"), index=True)
    version: Mapped[int]
    content: Mapped[str] = mapped_column(String(6000))
    planned_date: Mapped[str] = mapped_column(String(10))
    revision_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class LaunchTask(Base):
    __tablename__ = "launch_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    phase: Mapped[str] = mapped_column(String(30))
    due_date: Mapped[str] = mapped_column(String(10))
    completed: Mapped[bool] = mapped_column(default=False)


class DailySchedule(Base):
    __tablename__ = "daily_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    enabled: Mapped[bool] = mapped_column(default=False)
    goal: Mapped[str] = mapped_column(String(1000))
    timezone: Mapped[str] = mapped_column(String(100))
    hour: Mapped[int]
    frequency: Mapped[str] = mapped_column(String(10), default="daily", server_default="daily")
    posts_per_day: Mapped[int] = mapped_column(default=1, server_default="1")
    weekday: Mapped[int] = mapped_column(default=0, server_default="0")
    month_day: Mapped[int] = mapped_column(default=1, server_default="1")
    next_run: Mapped[float]
    next_monitor: Mapped[float] = mapped_column(default=0, server_default="0")
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"))
    last_error: Mapped[str | None] = mapped_column(String(100))
    revision: Mapped[int] = mapped_column(default=1)


class CustomerLead(Base):
    __tablename__ = "customer_leads"
    __table_args__ = (UniqueConstraint("project_id", "identity_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(2000))
    identity_key: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("research_sources.id"))
    stage: Mapped[str] = mapped_column(String(20), default="identified")
    next_action: Mapped[str] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class SocialAuthorization(Base):
    __tablename__ = "social_authorizations"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    session_hash: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[float]


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("project_id", "provider", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    encrypted_token: Mapped[str] = mapped_column(String(6000))
    permissions: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[float]
    status: Mapped[str] = mapped_column(String(30), default="connected")
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class GrowthJourney(Base):
    __tablename__ = "growth_journeys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="interview_uploaded")
    revision: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    claim_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[float] = mapped_column(default=0)
    next_check: Mapped[float] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="inactive")
    period_end: Mapped[float] = mapped_column(default=0)
    updated_event: Mapped[int] = mapped_column(default=0)
    checkout_key: Mapped[str | None] = mapped_column(String(36))
    checkout_session_id: Mapped[str | None] = mapped_column(String(100))
    checkout_url: Mapped[str | None] = mapped_column(String(1000))
    checkout_expires: Mapped[float] = mapped_column(default=0)


class BillingEvent(Base):
    __tablename__ = "billing_events"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class ResourceUsage(Base):
    __tablename__ = "resource_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))
    resource_key: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    units: Mapped[int]
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class VideoAsset(Base):
    __tablename__ = "video_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    lease_until: Mapped[float] = mapped_column(default=0)


class PilotObservation(Base):
    __tablename__ = "pilot_observations"
    __table_args__ = (UniqueConstraint("project_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(100))
    observed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
