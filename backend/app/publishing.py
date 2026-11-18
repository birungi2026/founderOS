"""Explicit, single-job LinkedIn delivery. Never run automatically on draft approval."""

import argparse
import json
import os

import httpx
from sqlalchemy import select, update

from .database import SessionLocal
from .models import AuditLog, Draft, Membership, Project, Publication


def deliver_one(factory, organization_id, publication_id, connector, transport=None):
    # The connector is provisioned by the server operator, never supplied by a browser request.
    if (
        connector.get("organization_id") != organization_id
        or connector.get("channel") != "linkedin"
    ):
        raise ValueError("Connector scope does not match organization and channel")
    if (
        not connector.get("access_token")
        or not connector.get("author", "").startswith("urn:li:")
        or not connector.get("api_version", "").isdigit()
    ):
        raise ValueError("LinkedIn OAuth connector is not configured")
    with factory() as db:
        job = db.scalar(
            select(Publication)
            .join(Draft)
            .join(Project)
            .where(
                Publication.id == publication_id,
                Project.organization_id == organization_id,
            )
        )
        if not job or job.channel != "linkedin":
            raise ValueError("LinkedIn publication not found in organization")
        member = db.scalar(
            select(Membership).where(
                Membership.user_id == job.approved_by,
                Membership.organization_id == organization_id,
                Membership.role == "owner",
            )
        )
        if not member:
            raise ValueError("Approving owner no longer has publishing access")
        changed = db.execute(
            update(Publication)
            .where(Publication.id == job.id, Publication.status == "queued")
            .values(status="sending")
        )
        if changed.rowcount != 1:
            raise ValueError("Job is not queued; never automatically retry uncertain delivery")
        content, actor_id = job.content, job.approved_by
        db.add(
            AuditLog(
                organization_id=organization_id,
                actor_id=actor_id,
                action="publication.sending",
                resource_id=job.id,
            )
        )
        db.commit()  # Durable claim before an irreversible external call.
    status, reference, error = "uncertain", None, "delivery_unknown"
    try:
        with httpx.Client(timeout=20, follow_redirects=False, transport=transport) as client:
            response = client.post(
                "https://api.linkedin.com/rest/posts",
                headers={
                    "Authorization": "Bearer " + connector["access_token"],
                    "LinkedIn-Version": connector["api_version"],
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                json={
                    "author": connector["author"],
                    "commentary": content,
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MAIN_FEED",
                        "targetEntities": [],
                        "thirdPartyDistributionChannels": [],
                    },
                    "lifecycleState": "PUBLISHED",
                    "isReshareDisabledByAuthor": False,
                },
            )
        if response.status_code == 201:
            status, reference, error = (
                "sent",
                response.headers.get("x-restli-id", "")[:300],
                None,
            )
        elif 400 <= response.status_code < 500:
            status, error = "failed", "provider_rejected"
        # Redirects, server failures and transport errors are ambiguous; do not replay.
    except httpx.HTTPError:
        pass
    with factory() as db:
        job = db.get(Publication, publication_id)
        job.status, job.provider_reference, job.error_code = status, reference, error
        db.get(Draft, job.draft_id).status = status
        db.add(
            AuditLog(
                organization_id=organization_id,
                actor_id=actor_id,
                action="publication." + status,
                resource_id=job.id,
            )
        )
        db.commit()
    return status


def main():
    parser = argparse.ArgumentParser(
        description="Deliver one explicitly queued LinkedIn publication"
    )
    parser.add_argument("--organization", required=True)
    parser.add_argument("--publication", required=True)
    parser.add_argument(
        "--deliver",
        action="store_true",
        required=True,
        help="Confirms a real external publishing request",
    )
    args = parser.parse_args()
    try:
        connector = json.loads(os.environ.get("LINKEDIN_CONNECTOR_JSON", "{}"))
        print(deliver_one(SessionLocal, args.organization, args.publication, connector))
    except (ValueError, KeyError):
        parser.exit(
            1,
            "Delivery refused: check connector scope, OAuth configuration and job state.\n",
        )


if __name__ == "__main__":
    main()
