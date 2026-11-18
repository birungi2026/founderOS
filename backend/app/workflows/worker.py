"""Durable SQL-backed MVP worker. One claim, bounded agent calls, no automatic publishing."""

import argparse
import logging
import time
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from ..database import SessionLocal
from ..models import (
    AgentStep,
    AuditLog,
    ContentRevision,
    Draft,
    LaunchTask,
    Membership,
    WorkflowRun,
)
from .agents import AGENTS, run_agent
from .contracts import revision_hash

logger = logging.getLogger("founderos.worker")


def authorized(db, run):
    return (
        db.scalar(
            select(Membership.id).where(
                Membership.organization_id == run.organization_id,
                Membership.user_id == run.requested_by,
                Membership.role.in_(["owner", "editor"]),
            )
        )
        is not None
    )


def owned(db, run_id, token):
    return db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.status == "running",
            WorkflowRun.claim_token == token,
            WorkflowRun.lease_until > time.time(),
        )
    )


def fail(factory, run_id, token, code):
    with factory() as db:
        db.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status == "running",
                WorkflowRun.claim_token == token,
            )
            .values(status="failed", error_code=code)
        )
        db.commit()


def process_one(factory=SessionLocal):
    token = str(uuid4())
    with factory() as db:
        # A crashed generation is failed rather than invisibly repeated and billed twice.
        db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.status == "running", WorkflowRun.lease_until < time.time())
            .values(status="failed", error_code="worker_interrupted")
        )
        run = db.scalar(
            select(WorkflowRun)
            .where(WorkflowRun.status == "queued")
            .order_by(WorkflowRun.created_at)
            .limit(1)
        )
        if not run:
            db.commit()
            return False
        run_id = run.id
        changed = db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.id == run_id, WorkflowRun.status == "queued")
            .values(status="running", claim_token=token, lease_until=time.time() + 300)
        )
        if changed.rowcount != 1:
            db.rollback()
            return True
        ctx = run.context
        db.commit()
    artifacts = {}
    try:
        for index, (agent, _) in enumerate(AGENTS, 1):
            with factory() as db:
                run = owned(db, run_id, token)
                if not run:
                    return True
                if not authorized(db, run):
                    fail(factory, run_id, token, "access_revoked")
                    return True
            artifact, usage, mode = run_agent(agent, ctx, artifacts)
            with factory() as db:
                # CAS coordinates cancellation and lease expiry with every persisted step.
                changed = db.execute(
                    update(WorkflowRun)
                    .where(
                        WorkflowRun.id == run_id,
                        WorkflowRun.status == "running",
                        WorkflowRun.claim_token == token,
                        WorkflowRun.lease_until > time.time(),
                    )
                    .values(progress=index * 18)
                )
                if changed.rowcount != 1:
                    db.rollback()
                    return True
                db.add(
                    AgentStep(
                        run_id=run_id,
                        agent=agent,
                        artifact=artifact,
                        usage=usage,
                        generation_mode=mode,
                    )
                )
                db.commit()
            artifacts[agent] = artifact
        with factory() as db:
            run = owned(db, run_id, token)
            if not run or not authorized(db, run):
                db.rollback()
                fail(factory, run_id, token, "access_revoked")
                return True
            changed = db.execute(
                update(WorkflowRun)
                .where(
                    WorkflowRun.id == run_id,
                    WorkflowRun.status == "running",
                    WorkflowRun.claim_token == token,
                    WorkflowRun.lease_until > time.time(),
                )
                .values(status="needs_review", progress=100)
            )
            if changed.rowcount != 1:
                db.rollback()
                return True
            for item in artifacts["growth"]["calendar"]:
                planned = (
                    date.fromisoformat(ctx["week_start"]) + timedelta(days=item["day"] - 1)
                ).isoformat()
                draft = Draft(
                    project_id=run.project_id,
                    channel=item["channel"],
                    content=item["content"],
                    revision_number=1,
                    generation={
                        "mode": ctx["generation_mode"],
                        "run_id": run_id,
                        "brand_version_id": run.brand_version_id,
                        "planned_date": planned,
                        "title": item["title"],
                        "hypothesis": item["hypothesis"],
                        "citation_ids": item["evidence_ids"],
                    },
                )
                db.add(draft)
                db.flush()
                db.add(
                    ContentRevision(
                        draft_id=draft.id,
                        version=1,
                        content=draft.content,
                        planned_date=planned,
                        revision_hash=revision_hash(draft),
                        created_by=run.requested_by,
                    )
                )
            for item in artifacts["launch"]["tasks"]:
                db.add(
                    LaunchTask(
                        run_id=run_id,
                        title=item["title"],
                        phase=item["phase"],
                        due_date=(
                            date.fromisoformat(ctx["launch_date"])
                            + timedelta(days=item["days_from_launch"])
                        ).isoformat(),
                    )
                )
            db.add(
                AuditLog(
                    organization_id=run.organization_id,
                    actor_id=run.requested_by,
                    action="workflow.needs_review",
                    resource_id=run.id,
                )
            )
            db.commit()
    except Exception:
        # Provider errors and worker internals may contain prompt text or credentials.
        # Persist only a fixed public code; never log raw exception/provider bodies.
        fail(factory, run_id, token, "generation_failed")
        logger.error("Growth workflow failed: run_id=%s", run_id)
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the FounderOS growth workflow worker")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job")
    args = parser.parse_args()
    if args.once:
        process_one()
        return
    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
