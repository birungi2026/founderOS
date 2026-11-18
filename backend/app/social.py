"""Owner-authorized, read-only social account access. Tokens never enter agent prompts."""

import os
import re
import secrets
import time
from html import escape
from urllib.parse import urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .database import get_db
from .models import Membership, Organization, Project, SocialAccount, SocialAuthorization
from .security import COOKIE, Tenant, audit, current_user, owner, tenant, token_hash
from .workflows.api import project_for

router = APIRouter(prefix="/v1", tags=["Social accounts"])
SCOPES = {
    "instagram": ["instagram_business_basic"],
    "facebook": ["pages_show_list", "pages_read_engagement"],
}


def config(provider):
    if provider not in SCOPES:
        raise HTTPException(404, "Unsupported social provider")
    prefix = provider.upper()
    values = [os.getenv(f"{prefix}_{key}", "") for key in ["APP_ID", "APP_SECRET", "REDIRECT_URI"]]
    try:
        Fernet(os.environ["SOCIAL_TOKEN_ENCRYPTION_KEY"].encode())
        redirect = urlsplit(values[2])
        if redirect.scheme != "https" and not (
            redirect.scheme == "http" and redirect.hostname in {"localhost", "127.0.0.1"}
        ):
            raise ValueError()
        if not all(values) or redirect.query or redirect.fragment or redirect.username:
            raise ValueError()
    except (KeyError, ValueError):
        raise HTTPException(503, "Social connection is not configured on the server") from None
    return values


def vault():
    try:
        return Fernet(os.environ["SOCIAL_TOKEN_ENCRYPTION_KEY"].encode())
    except (KeyError, ValueError):
        raise HTTPException(503, "Social token encryption is not configured") from None


def graph(provider):
    version = os.getenv("META_GRAPH_VERSION", "v25.0")
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise HTTPException(503, "Invalid Meta API version configuration")
    host = "graph.instagram.com" if provider == "instagram" else "graph.facebook.com"
    return f"https://{host}/{version}"


def call(method, url, **kwargs):
    # Fixed provider URLs only; never follow provider paging URLs or expose error bodies.
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            if len(response.content) > 1_000_000:
                raise ValueError()
            data = response.json()
            if not isinstance(data, dict) or "error" in data:
                raise ValueError()
            return data
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            502, "Social provider request failed; reconnect if access has expired"
        ) from None


def public(row):
    return {
        "id": row.id,
        "provider": row.provider,
        "name": row.name,
        "status": "expired" if row.expires_at <= time.time() else row.status,
        "permissions": row.permissions,
        "expires_at": row.expires_at,
        "snapshot": row.snapshot,
    }


@router.get("/projects/{project_id}/social")
def accounts(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    providers = []
    for provider in SCOPES:
        try:
            config(provider)
            ready = True
        except HTTPException:
            ready = False
        providers.append(
            {"provider": provider, "configured": ready, "requested_permissions": SCOPES[provider]}
        )
    return {
        "providers": providers,
        "accounts": [
            public(r)
            for r in db.scalars(select(SocialAccount).where(SocialAccount.project_id == project_id))
        ],
    }


@router.post("/projects/{project_id}/social/{provider}/connect")
def connect(
    project_id: str,
    provider: str,
    request: Request,
    context: Tenant = Depends(owner),
    db: Session = Depends(get_db),
):
    project_for(db, project_id, context)
    app_id, _, redirect = config(provider)
    state = secrets.token_urlsafe(32)
    db.execute(delete(SocialAuthorization).where(SocialAuthorization.expires_at < time.time()))
    db.add(
        SocialAuthorization(
            state_hash=token_hash(state),
            project_id=project_id,
            user_id=context.user.id,
            session_hash=token_hash(request.cookies.get(COOKIE, "")),
            provider=provider,
            expires_at=time.time() + 600,
        )
    )
    endpoint = (
        "https://www.instagram.com/oauth/authorize"
        if provider == "instagram"
        else f"https://www.facebook.com/{graph(provider).rsplit('/', 1)[1]}/dialog/oauth"
    )
    return {
        "authorization_url": endpoint
        + "?"
        + urlencode(
            {
                "client_id": app_id,
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": ",".join(SCOPES[provider]),
                "state": state,
            }
        )
    }


@router.get("/social/{provider}/callback", response_class=HTMLResponse)
def callback(
    provider: str,
    request: Request,
    state: str = "",
    code: str = "",
    error: str = "",
    user=Depends(current_user),
    db: Session = Depends(get_db),
):
    app_id, secret, redirect = config(provider)
    row = db.get(SocialAuthorization, token_hash(state))
    if (
        not row
        or row.provider != provider
        or row.user_id != user.id
        or row.session_hash != token_hash(request.cookies.get(COOKIE, ""))
        or row.expires_at <= time.time()
    ):
        raise HTTPException(400, "Invalid or expired social authorization")
    project_id = row.project_id
    project = db.get(Project, project_id)
    member = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == project.organization_id,
            Membership.role == "owner",
        )
    )
    if not member:
        raise HTTPException(403, "Owner role required")
    # Atomically consume state before contacting the provider; replay cannot exchange a code.
    used = db.execute(
        delete(SocialAuthorization).where(SocialAuthorization.state_hash == row.state_hash)
    )
    if used.rowcount != 1:
        raise HTTPException(400, "Authorization already used")
    db.commit()
    if error or not code or len(code) > 4096:
        return HTMLResponse(
            "<p>Connection cancelled. Return to FounderOS to try again.</p>",
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
        )
    params = {"client_id": app_id, "client_secret": secret, "redirect_uri": redirect, "code": code}
    if provider == "instagram":
        short = call(
            "POST",
            "https://api.instagram.com/oauth/access_token",
            data={**params, "grant_type": "authorization_code"},
        )
        if "data" in short:
            if len(short["data"]) != 1:
                raise HTTPException(502, "Unexpected social provider response")
            short = short["data"][0]
        token = short.get("access_token")
        if not token:
            raise HTTPException(502, "Social authorization did not return access")
        granted = short.get("permissions", [])
        if isinstance(granted, str):
            granted = granted.split(",")
        if not set(SCOPES[provider]).issubset(granted):
            raise HTTPException(400, "Required social permission was not granted")
        long = call(
            "GET",
            "https://graph.instagram.com/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": secret,
                "access_token": token,
            },
        )
        token = long.get("access_token")
        profile = call(
            "GET",
            graph(provider) + "/me",
            params={"fields": "user_id,username"},
            headers={"Authorization": f"Bearer {token}"},
        )
        entries = [
            {
                "id": profile.get("user_id") or profile.get("id"),
                "name": profile.get("username"),
                "access_token": token,
            }
        ]
        expires = time.time() + min(float(long.get("expires_in", 3600)), 5184000)
    else:
        short = call("GET", graph(provider) + "/oauth/access_token", params=params)
        long = call(
            "GET",
            graph(provider) + "/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": secret,
                "fb_exchange_token": short.get("access_token", ""),
            },
        )
        token = long.get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        permissions = call("GET", graph(provider) + "/me/permissions", headers=headers)
        granted = [
            p["permission"] for p in permissions.get("data", []) if p.get("status") == "granted"
        ]
        if not set(SCOPES[provider]).issubset(granted):
            raise HTTPException(400, "Required social permission was not granted")
        entries = call(
            "GET",
            graph(provider) + "/me/accounts",
            params={"fields": "id,name,access_token", "limit": 100},
            headers=headers,
        ).get("data", [])
        expires = time.time() + min(float(long.get("expires_in", 3600)), 5184000)
    if not entries:
        raise HTTPException(
            400,
            "No eligible accounts found; connect an Instagram professional account or Facebook Page",
        )
    for entry in entries[:100]:
        external_id = str(entry.get("id", ""))
        access_token = entry.get("access_token")
        if not external_id.isdigit() or not isinstance(access_token, str) or not access_token:
            raise HTTPException(502, "Unexpected social provider account response")
        account = db.scalar(
            select(SocialAccount).where(
                SocialAccount.project_id == project_id,
                SocialAccount.provider == provider,
                SocialAccount.external_id == external_id,
            )
        )
        if not account:
            account = SocialAccount(
                project_id=project_id, provider=provider, external_id=external_id
            )
            db.add(account)
        account.name = str(entry.get("name") or external_id)[:200]
        account.encrypted_token = vault().encrypt(access_token.encode()).decode()
        account.permissions = granted
        account.expires_at, account.status, account.snapshot = expires, "connected", {}
    db.flush()
    audit(
        db,
        Tenant(user, db.get(Organization, project.organization_id), "owner"),
        "social.connected",
        project_id,
    )
    return HTMLResponse(
        '<p>Account connected.</p><p><a href="'
        + escape(os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",")[0], quote=True)
        + '">Return to FounderOS</a> and refresh connected accounts.</p>',
        headers={"Referrer-Policy": "no-referrer", "Cache-Control": "no-store"},
    )


@router.post("/social/accounts/{account_id}/sync")
def sync(account_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    row = db.get(SocialAccount, account_id)
    if not row:
        raise HTTPException(404, "Account not found")
    project_for(db, row.project_id, context)
    if row.status == "disconnected" or row.expires_at <= time.time():
        raise HTTPException(409, "Reconnect this social account")
    try:
        token = vault().decrypt(row.encrypted_token.encode()).decode()
    except InvalidToken:
        raise HTTPException(409, "Reconnect this social account") from None
    fields = (
        "user_id,username,followers_count,media_count"
        if row.provider == "instagram"
        else "id,name,followers_count,fan_count"
    )
    headers = {"Authorization": f"Bearer {token}"}
    profile = call(
        "GET",
        graph(row.provider) + "/" + row.external_id,
        params={"fields": fields},
        headers=headers,
    )
    edge = "media" if row.provider == "instagram" else "posts"
    media_fields = (
        "id,caption,media_type,permalink,timestamp,like_count,comments_count"
        if row.provider == "instagram"
        else "id,message,permalink_url,created_time"
    )
    media = call(
        "GET",
        graph(row.provider) + f"/{row.external_id}/{edge}",
        params={"fields": media_fields, "limit": 25},
        headers=headers,
    )
    # Allowlisted data only. Provider tokens, paging cursors and error bodies are discarded.
    snapshot = {
        "observed_at": time.time(),
        "profile": {k: profile[k] for k in fields.split(",") if k in profile},
        "posts": [
            {k: p[k] for k in media_fields.split(",") if k in p} for p in media.get("data", [])[:25]
        ],
    }
    changed = db.execute(
        update(SocialAccount)
        .where(
            SocialAccount.id == row.id,
            SocialAccount.status == "connected",
            SocialAccount.encrypted_token == row.encrypted_token,
        )
        .values(snapshot=snapshot)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Account changed while retrieving data; refresh account status")
    db.expire(row)
    audit(db, context, "social.synced", row.id)
    return public(row)


@router.post("/social/accounts/{account_id}/disconnect")
def disconnect(account_id: str, context: Tenant = Depends(owner), db: Session = Depends(get_db)):
    row = db.get(SocialAccount, account_id)
    if not row:
        raise HTTPException(404, "Account not found")
    project_for(db, row.project_id, context)
    row.encrypted_token, row.snapshot, row.permissions, row.status = "", {}, [], "disconnected"
    audit(db, context, "social.disconnected", row.id)
    return {"status": "disconnected"}
