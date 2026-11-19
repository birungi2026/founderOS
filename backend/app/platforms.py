"""Versioned public ranking guidance; recommendations are hypotheses, not algorithm access."""

import copy
import time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import SocialAccount
from .security import Tenant, tenant
from .workflows.api import project_for

router = APIRouter(prefix="/v1", tags=["Platform intelligence"])
GUIDANCE = [
    {
        "platform": "instagram",
        "source_id": "platform-instagram-2026-11",
        "source_url": "https://about.fb.com/news/2026/01/2026-ai-drives-performance/",
        "published_on": "2026-01-28",
        "signal": "Meta describes personalized recommendations and increased emphasis on original content. This does not reveal ranking weights.",
        "experiment": "Test two original, audience-specific Reel openings on comparable topics, holding the offer and posting cadence steady.",
        "success_metric": "Compare retention and saves/shares per reached account where insights are available, then track qualified inquiries or purchases separately.",
    },
    {
        "platform": "tiktok",
        "source_id": "platform-tiktok-2026-11",
        "source_url": "https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content",
        "published_on": None,
        "signal": "TikTok describes interaction, content and user information signals; watching or skipping content can influence recommendations. Weights can change.",
        "experiment": "Test a direct problem/benefit opening against a short demonstration for the same audience. Change one variable at a time.",
        "success_metric": "Compare completion and average watch time if supplied by approved analytics; basic public-video counts alone cannot measure retention.",
    },
    {
        "platform": "facebook",
        "source_id": "platform-facebook-2026-11",
        "source_url": "https://about.fb.com/news/2026/03/rewarding-original-creators-on-facebook/",
        "published_on": "2026-03-13",
        "signal": "Meta says Facebook prioritizes original content and reduces distribution of unoriginal content. Reach is personalized and eligibility matters.",
        "experiment": "Test an original practical explanation against an original customer/audience story, with a relevant discussion prompt rather than engagement bait.",
        "success_metric": "Compare meaningful comments and shares per reach where available, plus attributable inquiries or conversions.",
    },
    {
        "platform": "linkedin",
        "source_id": "platform-linkedin-2026-11",
        "source_url": "https://news.linkedin.com/2026/ImprovingTheFeed",
        "published_on": None,
        "signal": "LinkedIn describes ranking based on professional relevance, content understanding and evolving member interests, with emphasis on authentic professional content.",
        "experiment": "Test a specific first-person lesson against a worked example for the same professional audience. Keep the call to action comparable.",
        "success_metric": "Compare relevant professional replies, profile visits and qualified inquiries where reported; basic OpenID profile access provides none of these analytics.",
    },
]


def guidance_snapshot(db, project_id):
    accounts = db.scalars(
        select(SocialAccount).where(
            SocialAccount.project_id == project_id,
            SocialAccount.status == "connected",
            SocialAccount.expires_at > time.time(),
        )
    ).all()
    result = copy.deepcopy(GUIDANCE)
    for item in result:
        matching = [a for a in accounts if a.provider == item["platform"]]
        item.update(
            {
                "curated_reviewed_on": "2026-11-18",
                "verification": "curated_public_guidance_not_live_algorithm_access",
                "account_data": [
                    {
                        "name": a.name,
                        "observed_at": a.snapshot.get("observed_at"),
                        "recent_posts": len(a.snapshot.get("posts", [])),
                        "followers_count": a.snapshot.get("profile", {}).get("followers_count"),
                        "limitations": a.snapshot.get("limitations"),
                    }
                    for a in matching
                ],
                "uncertainty": "Testable guidance, not a reach guarantee or causal proof. Private ranking weights and missing account metrics are unknown.",
            }
        )
    return result


@router.get("/projects/{project_id}/platform-intelligence")
def intelligence(project_id: str, context: Tenant = Depends(tenant), db: Session = Depends(get_db)):
    project_for(db, project_id, context)
    return {
        "platforms": guidance_snapshot(db, project_id),
        "monitoring": "New automatic research runs search for public ranking/recommendation updates. Search excerpts need founder confirmation before content creation.",
    }
