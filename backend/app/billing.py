"""Hosted Stripe checkout and signed webhooks. Redirects never grant entitlements."""

import hashlib
import hmac
import json
import math
import os
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import BillingAccount, BillingEvent, Organization, ResourceUsage
from .security import Tenant, owner, tenant

router = APIRouter(prefix="/v1", tags=["Subscription and usage"])


def active(db, organization_id):
    if os.getenv("BILLING_ENFORCED") != "true":
        return
    row = db.get(BillingAccount, organization_id)
    if not row or row.status != "active" or row.period_end <= time.time():
        raise HTTPException(
            402, "An active subscription is required. Open Settings → Plan and usage."
        )


def reserve(db, organization_id, kind, units, resource_key):
    active(db, organization_id)
    db.refresh(db.get(Organization, organization_id), with_for_update=True)
    if db.scalar(select(ResourceUsage).where(ResourceUsage.resource_key == resource_key)):
        return
    period = datetime.now(UTC).strftime("%Y-%m")
    limits = {
        "video_seconds": int(os.getenv("PLAN_VIDEO_SECONDS", "900")),
        "footage_seconds": int(os.getenv("PLAN_FOOTAGE_SECONDS", "1800")),
        "research_runs": int(os.getenv("PLAN_RESEARCH_RUNS", "20")),
    }
    used = db.scalar(
        select(func.coalesce(func.sum(ResourceUsage.units), 0)).where(
            ResourceUsage.organization_id == organization_id,
            ResourceUsage.period == period,
            ResourceUsage.kind == kind,
        )
    )
    if units < 1 or used + units > limits[kind]:
        raise HTTPException(429, "Monthly allowance reached. No extra charge was made.")
    db.add(
        ResourceUsage(
            organization_id=organization_id,
            period=period,
            kind=kind,
            units=units,
            resource_key=resource_key,
        )
    )
    db.flush()


def render_seconds(script):
    # Reserve conservatively at 100 words/minute, rounded to 6 seconds, minimum 30s.
    return max(30, math.ceil(max(len(script.split()) * 0.6, len(script) / 4) / 6) * 6)


@router.get("/billing")
def summary(context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    row = db.get(BillingAccount, context.organization.id)
    period = datetime.now(UTC).strftime("%Y-%m")
    usage = dict(
        db.execute(
            select(ResourceUsage.kind, func.sum(ResourceUsage.units))
            .where(
                ResourceUsage.organization_id == context.organization.id,
                ResourceUsage.period == period,
            )
            .group_by(ResourceUsage.kind)
        ).all()
    )
    return {
        "status": row.status if row else "inactive",
        "period_end": row.period_end if row else None,
        "period": period,
        "enforced": os.getenv("BILLING_ENFORCED") == "true",
        "checkout_ready": bool(
            os.getenv("STRIPE_SECRET_KEY")
            and os.getenv("STRIPE_PRICE_ID")
            and os.getenv("APP_PUBLIC_URL", "").startswith("https://")
        ),
        "monthly_price_usd": 59,
        "usage": usage,
        "limits": {
            "video_seconds": int(os.getenv("PLAN_VIDEO_SECONDS", "900")),
            "footage_seconds": int(os.getenv("PLAN_FOOTAGE_SECONDS", "1800")),
            "research_runs": int(os.getenv("PLAN_RESEARCH_RUNS", "20")),
        },
        "note": "Calendar-month allowances. Rerenders reserve minutes again. Avatar training is separately provisioned; no unlimited clones or videos.",
    }


def stripe(path, fields, key):
    secret = os.getenv("STRIPE_SECRET_KEY", "")
    if not secret:
        raise HTTPException(503, "Billing is not configured")
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.post(
                "https://api.stripe.com/v1/" + path,
                headers={"Authorization": "Bearer " + secret, "Idempotency-Key": key},
                data=fields,
            )
            response.raise_for_status()
            result = response.json()
        if len(response.content) > 100000 or not isinstance(result, dict):
            raise ValueError()
        return result
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            502, "Billing provider request failed. Try again with the same request ID."
        ) from None


def stripe_get(path):
    if not os.getenv("STRIPE_SECRET_KEY"):
        raise HTTPException(503, "Billing is not configured")
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(
                "https://api.stripe.com/v1/" + path,
                headers={"Authorization": "Bearer " + os.environ["STRIPE_SECRET_KEY"]},
            )
            response.raise_for_status()
            value = response.json()
        if len(response.content) > 100000 or not isinstance(value, dict):
            raise ValueError()
        return value
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            502, "Could not verify billing state. The provider will retry its webhook."
        ) from None


def app_url():
    value = os.getenv("APP_PUBLIC_URL", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(503, "Public HTTPS app URL is required")
    return value.rstrip("/")


@router.post("/billing/checkout")
def checkout(request: Request, context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    from .journey.api import require_enabled

    require_enabled(context)
    price = os.getenv("STRIPE_PRICE_ID", "")
    if not price:
        raise HTTPException(503, "Configure the $59 monthly USD price before checkout")
    verified = stripe_get("prices/" + price)
    if (
        verified.get("unit_amount") != 5900
        or verified.get("currency") != "usd"
        or verified.get("recurring", {}).get("interval") != "month"
        or verified.get("recurring", {}).get("interval_count", 1) != 1
    ):
        raise HTTPException(503, "The configured price must be USD $59 per month")
    db.refresh(context.organization, with_for_update=True)
    row = db.get(BillingAccount, context.organization.id)
    if (
        row
        and row.subscription_id
        and row.status not in {"canceled", "inactive", "incomplete_expired"}
    ):
        raise HTTPException(409, "Manage your existing subscription instead")
    if not row:
        row = BillingAccount(organization_id=context.organization.id)
        db.add(row)
        db.flush()
    if row.checkout_session_id:
        session = stripe_get("checkout/sessions/" + row.checkout_session_id)
        if session.get("status") == "complete":
            raise HTTPException(
                409, "Payment is processing. Wait for billing confirmation before trying again."
            )
        if session.get("status") == "open" and row.checkout_url:
            return {"url": row.checkout_url}
        if session.get("status") == "expired":
            row.checkout_expires = 0
    if row.checkout_key and not row.checkout_session_id and row.checkout_expires <= time.time():
        raise HTTPException(
            409, "An earlier checkout needs administrator reconciliation before retrying"
        )
    if not row.checkout_key or (row.checkout_expires <= time.time() and row.checkout_session_id):
        row.checkout_key = str(uuid4())
        row.checkout_session_id, row.checkout_url = None, None
        row.checkout_expires = time.time() + 90000
    key = row.checkout_key
    db.commit()  # Durable key before Stripe; retries of uncertain requests reuse it.
    result = stripe(
        "checkout/sessions",
        {
            "mode": "subscription",
            "line_items[0][price]": price,
            "line_items[0][quantity]": "1",
            "client_reference_id": context.organization.id,
            "subscription_data[metadata][organization_id]": context.organization.id,
            "success_url": app_url() + "/?billing=return",
            "cancel_url": app_url() + "/?billing=cancel",
            **({"customer": row.customer_id} if row.customer_id else {}),
        },
        "rymu-checkout-" + key,
    )
    url = result.get("url", "")
    if not url.startswith("https://checkout.stripe.com/"):
        raise HTTPException(502, "Invalid checkout response")
    session_id = result.get("id", "")
    if not re.fullmatch(r"cs_[A-Za-z0-9_]{1,90}", session_id):
        raise HTTPException(502, "Invalid checkout session")
    row.checkout_session_id, row.checkout_url = session_id, url
    row.checkout_expires = result.get("expires_at", time.time() + 86400) + 60
    return {"url": url}


@router.post("/billing/portal")
def portal(context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    row = db.get(BillingAccount, context.organization.id)
    if not row or not row.customer_id:
        raise HTTPException(409, "No billing account yet")
    result = stripe(
        "billing_portal/sessions",
        {"customer": row.customer_id, "return_url": app_url() + "/"},
        "rymu-portal-" + context.organization.id + "-" + str(int(time.time()) // 60),
    )
    url = result.get("url", "")
    if not url.startswith("https://billing.stripe.com/"):
        raise HTTPException(502, "Invalid billing portal response")
    return {"url": url}


@router.post("/billing/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret or len(body) > 200000:
        raise HTTPException(400, "Invalid billing webhook")
    values = request.headers.get("Stripe-Signature", "").split(",")
    try:
        timestamp = next(int(v[2:]) for v in values if v.startswith("t="))
        signatures = [v[3:] for v in values if v.startswith("v1=")]
        expected = hmac.new(
            secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if abs(time.time() - timestamp) > 300 or not any(
            hmac.compare_digest(expected, s) for s in signatures
        ):
            raise ValueError()
        event = json.loads(body)
        if not isinstance(event.get("id"), str) or len(event["id"]) > 100:
            raise ValueError()
    except (ValueError, StopIteration, KeyError):
        raise HTTPException(400, "Invalid billing signature") from None
    if db.get(BillingEvent, event["id"]):
        return {"received": True}
    if event.get("type") in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        event_object = event.get("data", {}).get("object", {})
        sub_id = event_object.get("id", "")
        if not re.fullmatch(r"sub_[A-Za-z0-9]{1,90}", sub_id):
            raise HTTPException(400, "Invalid subscription event")
        # Fetch canonical state; delayed or same-second events cannot restore canceled access.
        obj = stripe_get("subscriptions/" + sub_id)
        org_id = obj.get("metadata", {}).get("organization_id")
        organization = db.get(Organization, org_id) if org_id else None
        if organization:
            db.refresh(organization, with_for_update=True)
            if db.get(BillingEvent, event["id"]):
                return {"received": True}
            row = db.get(BillingAccount, org_id)
            if not row:
                row = BillingAccount(organization_id=org_id)
                db.add(row)
                db.flush()
            # A newer subscription must not be revoked by a late event from an old subscription.
            if (
                not row.subscription_id
                or row.subscription_id == obj["id"]
                or row.status in {"canceled", "inactive", "incomplete_expired"}
            ):
                items = obj.get("items", {}).get("data", [])
                correct_price = any(
                    i.get("price", {}).get("id") == os.getenv("STRIPE_PRICE_ID") for i in items
                )
                row.customer_id, row.subscription_id = obj["customer"], obj["id"]
                row.status = obj.get("status", "inactive") if correct_price else "inactive"
                row.period_end = obj.get("current_period_end") or max(
                    [i.get("current_period_end", 0) for i in items], default=0
                )
                row.updated_event = max(row.updated_event, event["created"])
                if row.status in {"canceled", "incomplete_expired"}:
                    row.checkout_key = row.checkout_session_id = row.checkout_url = None
                    row.checkout_expires = 0
    try:
        with db.begin_nested():
            db.add(BillingEvent(id=event["id"]))
            db.flush()
    except IntegrityError:
        pass
    return {"received": True}
