"""Discover evidence through a fixed search API. Never fetch arbitrary result URLs."""

import html
import ipaddress
import os
import re
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import select

from ..models import ResearchSource, now
from .contracts import digest


def configured():
    return bool(os.getenv("BRAVE_SEARCH_API_KEY"))


def canonical_url(value):
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            return None
        hostname = parsed.hostname.lower().rstrip(".")
        if (
            hostname == "localhost"
            or hostname.endswith((".local", ".internal", ".localhost"))
            or "." not in hostname
        ):
            return None
        try:
            if not ipaddress.ip_address(hostname).is_global:
                return None
        except ValueError:
            pass
        canonical = urlunsplit(("https", hostname, parsed.path or "/", parsed.query, ""))
        return canonical if len(canonical) <= 2000 else None
    except (ValueError, TypeError):
        return None


def plain(value, limit):
    return html.unescape(re.sub(r"<[^>]+>", "", str(value))).strip()[:limit]


def discover(ctx):
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not key:
        raise ValueError("research_not_configured")
    audience = ctx["project"]["audience"][:180]
    pillars = ctx["brand"]["content_pillars"]
    queries = [
        (f"site:{domain} {pillars[0][:120]} {audience} trends", "pw")
        for domain in ["instagram.com", "tiktok.com", "facebook.com", "linkedin.com"]
    ]
    queries.append((f"{pillars[0][:120]} {audience} daily news latest developments", "pd"))
    from urllib.parse import urlsplit

    for competitor in ctx.get("company", {}).get("competitors", [])[:3]:
        queries.append(
            (
                f"site:{urlsplit(competitor).hostname} product updates announcements differentiation",
                "pw",
            )
        )
    queries.append(
        (f"{ctx['project']['description'][:150]} alternatives competitors {audience}", None)
    )
    queries.append(
        (
            f"{audience} {ctx['project']['description'][:150]} "
            + (
                "creators audience interests opportunities"
                if ctx["project"].get("mode") == "personal"
                else "companies customers"
            ),
            None,
        )
    )
    # Four bounded searches for public platform guidance, in addition to niche trends.
    for platform, domain in [
        ("Instagram", "about.fb.com"),
        ("TikTok", "support.tiktok.com"),
        ("Facebook", "about.fb.com"),
        ("LinkedIn", "news.linkedin.com"),
    ]:
        queries.append((f"site:{domain} {platform} ranking recommendations creators updates", "pw"))
    results, seen = [], set()
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for query, freshness in queries:
            params = {"q": query, "count": 5, "safesearch": "moderate"}
            if freshness:
                params["freshness"] = freshness
            response = client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": key, "Accept": "application/json"},
                params=params,
            )
            response.raise_for_status()
            if len(response.content) > 500000:
                raise ValueError("research_response_too_large")
            for row in response.json().get("web", {}).get("results", [])[:5]:
                url = canonical_url(row.get("url"))
                title, excerpt = (
                    plain(row.get("title", ""), 200),
                    plain(row.get("description", ""), 4000),
                )
                if not url or url in seen or len(title) < 2 or len(excerpt) < 10:
                    continue
                seen.add(url)
                results.append({"url": url, "title": title, "excerpt": excerpt})
                break
    if not results:
        raise ValueError("research_no_results")
    return results[:14]


def save_discovered(db, project_id, user_id, items):
    saved = []
    for item in items:
        key = digest(item["url"])
        source = db.scalar(
            select(ResearchSource).where(
                ResearchSource.project_id == project_id,
                ResearchSource.source_key == key,
                ResearchSource.provider == "brave",
            )
        )
        if not source:
            source = ResearchSource(
                project_id=project_id, verified_by=user_id, provider="brave", source_key=key, **item
            )
            db.add(source)
        else:
            source.title, source.excerpt = item["title"], item["excerpt"]
        source.observed_at = now()
        db.flush()
        saved.append(
            {
                "id": source.id,
                "url": source.url,
                "title": source.title,
                "excerpt": source.excerpt,
                "observed_at": source.observed_at,
                "verification": "search_result_unverified",
                "provider": "brave",
            }
        )
    return saved
