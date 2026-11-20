"""Durable state transitions; a charged or publishing request is never silently replayed."""

import os
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update

from ..database import SessionLocal
from ..models import AgentStep, AuditLog, Draft, GrowthJourney, Membership, Project, WorkflowRun
from ..social import vault
from . import providers
from .api import account_for, media_url, workspace_enabled

STAGES = {
    "interview_uploaded": "transcribing",
    "researching": "checking_research",
    "training_queued": "training_request",
    "training": "checking_training",
    "render_queued": "render_request",
    "rendering": "checking_video",
    "scheduled": "publishing",
    "instagram_processing": "checking_instagram",
    "instagram_ready": "publishing_instagram",
    "posted": "measuring",
    "measured": "measuring",
}
READS = {
    "checking_research",
    "checking_training",
    "checking_video",
    "measuring",
    "checking_instagram",
}


def finish(factory, journey_id, token, status, payload=None, error=None, delay=0):
    with factory() as db:
        row = db.scalar(
            select(GrowthJourney).where(
                GrowthJourney.id == journey_id, GrowthJourney.claim_token == token
            )
        )
        if not row:
            return
        row.status, row.error_code = status, error
        row.revision += 1
        row.data = {**row.data, **(payload or {})}
        row.claim_token, row.lease_until, row.next_check = None, 0, time.time() + delay
        db.add(
            AuditLog(
                organization_id=db.get(Project, row.project_id).organization_id,
                actor_id=row.requested_by,
                action="journey." + status,
                resource_id=row.id,
            )
        )
        db.commit()


def process_one(factory=SessionLocal):
    now, token = time.time(), str(uuid4())
    with factory() as db:
        stale = db.scalars(
            select(GrowthJourney).where(
                GrowthJourney.claim_token.is_not(None), GrowthJourney.lease_until < now
            )
        ).all()
        for row in stale:
            previous = row.data.get("worker_previous")
            safe = row.status in READS and previous in STAGES
            row.status = previous if safe else "uncertain"
            row.error_code = None if safe else "worker_interrupted_do_not_resubmit"
            row.claim_token, row.lease_until, row.next_check = None, 0, now + 30
            row.revision += 1
        db.commit()
        row = db.scalar(
            select(GrowthJourney)
            .where(GrowthJourney.status.in_(list(STAGES)), GrowthJourney.next_check <= now)
            .order_by(GrowthJourney.created_at)
            .limit(1)
        )
        if not row:
            return False
        previous, journey_id, project_id = row.status, row.id, row.project_id
        actor, data = row.requested_by, dict(row.data)
        changed = db.execute(
            update(GrowthJourney)
            .where(
                GrowthJourney.id == journey_id,
                GrowthJourney.status == previous,
                GrowthJourney.revision == row.revision,
            )
            .values(
                status=STAGES[previous],
                claim_token=token,
                lease_until=now + 600,
                revision=row.revision + 1,
                data={**data, "worker_previous": previous},
            )
        )
        if changed.rowcount != 1:
            db.rollback()
            return True
        project = db.get(Project, project_id)
        allowed = db.scalar(
            select(Membership.id).where(
                Membership.organization_id == project.organization_id,
                Membership.user_id == actor,
                Membership.role == "owner",
            )
        )
        db.commit()
    if not allowed or not workspace_enabled(project.organization_id):
        finish(
            factory, journey_id, token, "access_revoked", error="owner_or_workspace_access_revoked"
        )
        return True
    write_started = False
    try:
        if previous in {
            "interview_uploaded",
            "training_queued",
            "render_queued",
            "scheduled",
            "instagram_ready",
        }:
            from ..billing import active

            with factory() as db:
                active(db, project.organization_id)
        if previous == "interview_uploaded":
            transcript, brief = providers.interview(data["media_path"], data["media_mime"])
            finish(
                factory,
                journey_id,
                token,
                "interview_review",
                {"transcript": transcript, "brief": brief},
            )
        elif previous == "researching":
            with factory() as db:
                run = db.get(WorkflowRun, data["run_id"])
                if not run or run.project_id != project_id:
                    raise providers.ProviderFailure("workflow_not_found")
                if run.status in {"failed", "cancelled"}:
                    finish(factory, journey_id, token, "failed", error="research_workflow_failed")
                elif run.status == "needs_review":
                    step = db.scalar(
                        select(AgentStep).where(
                            AgentStep.run_id == run.id, AgentStep.agent == "video"
                        )
                    )
                    drafts = db.scalars(select(Draft).where(Draft.project_id == project_id)).all()
                    draft = next((d for d in drafts if d.generation.get("run_id") == run.id), None)
                    if not step or not draft:
                        raise providers.ProviderFailure("content_not_available")
                    script = " ".join(scene["narration"] for scene in step.artifact["scenes"])
                    finish(
                        factory,
                        journey_id,
                        token,
                        "content_review",
                        {
                            "script": script,
                            "caption": draft.content,
                            "generation_mode": run.context["generation_mode"],
                        },
                    )
                else:
                    finish(factory, journey_id, token, "researching", delay=5)
        elif previous == "training_queued":
            write_started = True
            face_id = providers.create_face(media_url(journey_id), "Rymu " + journey_id)
            finish(
                factory,
                journey_id,
                token,
                "training",
                {"replica_id": face_id, "training_started_at": now},
                delay=30,
            )
        elif previous == "training":
            status = providers.face_status(data["replica_id"])
            if status == "completed":
                finish(factory, journey_id, token, "content_review", {"trained_at": now})
            elif status in {"error", "failed"} or now - data["training_started_at"] > 86400:
                finish(factory, journey_id, token, "failed", error="tavus_training_failed")
            else:
                finish(factory, journey_id, token, "training", delay=30)
        elif previous == "render_queued":
            write_started = True
            video_id = providers.create_video(data["replica_id"], data["script"])
            finish(
                factory,
                journey_id,
                token,
                "rendering",
                {"video_id": video_id, "render_started_at": now},
                delay=30,
            )
        elif previous == "rendering":
            status, url = providers.video_status(data["video_id"])
            if status == "ready":
                finish(
                    factory,
                    journey_id,
                    token,
                    "video_ready",
                    {"video_url": url, "rendered_at": now},
                )
            elif status in {"error", "failed"} or now - data["render_started_at"] > 86400:
                finish(factory, journey_id, token, "failed", error="tavus_render_failed")
            else:
                finish(factory, journey_id, token, "rendering", delay=30)
        elif previous in {
            "scheduled",
            "posted",
            "measured",
            "instagram_processing",
            "instagram_ready",
        }:
            publication = data["publication"]
            with factory() as db:
                account = account_for(db, project_id, publication["account_id"])
                approver = db.scalar(
                    select(Membership.id).where(
                        Membership.organization_id == project.organization_id,
                        Membership.user_id == data["approved_by"],
                        Membership.role == "owner",
                    )
                )
                flag = (
                    "JOURNEY_PUBLISHING_ENABLED"
                    if account.provider == "facebook"
                    else "INSTAGRAM_PUBLISHING_ENABLED"
                )
                if not approver or os.getenv(flag) != "true":
                    raise HTTPException(409, "Publishing access revoked")
                access_token = vault().decrypt(account.encrypted_token.encode()).decode()
                external_id = account.external_id
            if previous == "scheduled":
                if now - publication["publish_at"] > 3600:
                    finish(factory, journey_id, token, "missed", error="posting_time_missed")
                else:
                    if publication.get("asset_id"):
                        from ..media import video_url
                        from ..models import VideoAsset

                        with factory() as db:
                            asset = db.get(VideoAsset, publication["asset_id"])
                            if (
                                not asset
                                or asset.project_id != project_id
                                or asset.status != "ready"
                            ):
                                raise providers.ProviderFailure("approved_video_not_available")
                        fresh_url = video_url(asset.id)
                    else:
                        video_status, fresh_url = providers.video_status(publication["video_id"])
                        if video_status != "ready" or not fresh_url:
                            raise providers.ProviderFailure("approved_video_not_available")
                    write_started = True
                    if account.provider == "instagram":
                        container_id = providers.instagram_container(
                            external_id, access_token, fresh_url, publication["caption"]
                        )
                        finish(
                            factory,
                            journey_id,
                            token,
                            "instagram_processing",
                            {"instagram_container_id": container_id, "instagram_started_at": now},
                            delay=30,
                        )
                    else:
                        video_id = providers.facebook_publish(
                            external_id, access_token, fresh_url, publication["caption"]
                        )
                        finish(
                            factory,
                            journey_id,
                            token,
                            "posted",
                            {"facebook_video_id": video_id, "submitted_at": now},
                            delay=60,
                        )
            elif previous == "instagram_processing":
                status = providers.instagram_status(data["instagram_container_id"], access_token)
                if status == "FINISHED":
                    finish(factory, journey_id, token, "instagram_ready")
                elif status in {"ERROR", "EXPIRED"} or now - data["instagram_started_at"] > 600:
                    finish(
                        factory, journey_id, token, "failed", error="instagram_processing_failed"
                    )
                else:
                    finish(factory, journey_id, token, "instagram_processing", delay=30)
            elif previous == "instagram_ready":
                write_started = True
                media_id = providers.instagram_publish(
                    external_id, data["instagram_container_id"], access_token
                )
                finish(
                    factory,
                    journey_id,
                    token,
                    "posted",
                    {"instagram_media_id": media_id, "submitted_at": now},
                    delay=60,
                )
            else:
                metrics = (
                    providers.instagram_results(
                        data["instagram_media_id"],
                        access_token,
                        "instagram_business_manage_insights" in account.permissions,
                    )
                    if account.provider == "instagram"
                    else providers.facebook_results(data["facebook_video_id"], access_token)
                )
                finish(
                    factory,
                    journey_id,
                    token,
                    "measured",
                    {"results": metrics, "observed_at": now},
                    delay=60 if metrics["processing_status"] != "ready" else 3600,
                )
    except HTTPException:
        finish(
            factory, journey_id, token, "access_revoked", error="connection_or_permission_revoked"
        )
    except Exception:
        # No provider body, access token, transcript or prompt is logged.
        if previous == "scheduled" and not write_started:
            finish(
                factory, journey_id, token, "scheduled", error="video_status_check_failed", delay=60
            )
        elif STAGES[previous] in READS:
            finish(factory, journey_id, token, previous, error="provider_read_failed", delay=300)
        else:
            finish(
                factory,
                journey_id,
                token,
                "uncertain"
                if previous in {"training_queued", "render_queued", "scheduled", "instagram_ready"}
                else "failed",
                error="provider_request_failed_do_not_resubmit",
            )
    return True
