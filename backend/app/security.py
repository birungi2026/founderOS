import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditLog, LoginSession, Membership, Organization, User

COOKIE = "founderos_session"


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ":" + digest.hex()


def verify_password(password, encoded):
    salt, expected = encoded.split(":")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(actual.hex(), expected)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db, user, response):
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=time.time() + 86400,
        )
    )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=86400,
        path="/",
    )


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE, "")
    session = db.get(LoginSession, token_hash(token))
    if not session or session.expires_at <= time.time():
        raise HTTPException(401, "Sign in required")
    return db.get(User, session.user_id)


@dataclass
class Tenant:
    user: User
    organization: Organization
    role: str


def tenant(
    user: User = Depends(current_user),
    organization_id: str | None = Header(None, alias="X-Organization-ID"),
    db: Session = Depends(get_db),
):
    query = select(Membership).where(Membership.user_id == user.id)
    if organization_id:
        query = query.where(Membership.organization_id == organization_id)
    member = db.scalar(query.order_by(Membership.id))
    if not member:
        raise HTTPException(403, "Organization access denied")
    return Tenant(user, db.get(Organization, member.organization_id), member.role)


def editor(context: Tenant = Depends(tenant)):
    if context.role not in {"owner", "editor"}:
        raise HTTPException(403, "Editor role required")
    return context


def owner(context: Tenant = Depends(tenant)):
    if context.role != "owner":
        raise HTTPException(403, "Owner role required")
    return context


def audit(db, context, action, resource_id):
    db.add(
        AuditLog(
            organization_id=context.organization.id,
            actor_id=context.user.id,
            action=action,
            resource_id=resource_id,
        )
    )
