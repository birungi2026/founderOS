# FounderOS: growth employee product contract

## Outcome and onboarding

The primary outcome is the founder's first **50 paying customers**. Brand visibility and followers matter when they lead to qualified attention, buyer conversations, trials, purchases and retention. Neither virality nor purchases can be guaranteed by software.

Company onboarding collects the problem, solution, target customers, competitors and proposed differentiator. The founder profile supplies story, expertise and communication style. The intended next onboarding interface is a guided video interview that extracts these spoken facts and observable delivery preferences. It must not claim to infer a person's psychological traits from facial appearance.

## Implemented in this increment

- Automatic research is the default. Configure `BRAVE_SEARCH_API_KEY` once server-side; founders do not need to paste sources. Manual sources remain an optional advanced/demo path.
- Research searches indexed public TikTok, Instagram, Facebook and LinkedIn pages, recent news, likely buyers and up to three supplied competitor websites. There are at most fourteen fixed-provider searches per run. News uses the last-24-hours filter, social/competitor searches use the last-week filter, and buyer discovery permits evergreen results. Four additional searches look for public platform ranking/recommendation updates. Search index coverage may be incomplete.
- The worker stores source links/excerpts with provenance and retrieval timestamps. It never fetches arbitrary returned URLs, follows search-provider redirects or uses social passwords. Retrieved text is untrusted evidence, not instructions or independently verified fact.
- Automatic research destined for content pauses in `research_review`. The owner confirms the exact company/source/report hash before generation resumes from its saved steps. Changes to founder/company context invalidate that confirmation attempt. Approval is not inferred from silence.
- An owner can enable daily, weekly or monthly preparation, 1–5 distinct posts per selected day, local hour, IANA timezone, weekly weekday and monthly day 1–28. This currently schedules **preparation**, not public posting. Actual publication still uses the existing separate approval gate and configured adapter.
- News/trend/competitor monitoring runs daily even between weekly/monthly content batches. Those monitoring-only jobs end in `research_ready` and do not generate or publish content. Content batches require their own research confirmation.
- Recurring jobs are idempotent per local day. A short scheduling lease permits recovery after a process interruption; missed days are not backfilled in a posting burst. Disabling a routine cancels its unfinished queued/running/research-review jobs.
- A tenant-scoped customer pipeline tracks identified → contacted → conversation → trial → won/lost, with next actions and optimistic update versions. Only explicitly confirmed `won` records count toward the customer target. Counts are founder-attested, not payment-provider verified. Follower counts and discovered companies never count as sales.
- Pipeline counts enter the next agent context alongside performance data. Model research can suggest source-backed prospective buyers with qualification gaps; it must not invent contact details or label suggestions as qualified leads.

The default allowance is 40 organization-wide workflow runs per UTC month, including monitoring and preparation. One research-only check costs one reserved run; a preparation job normally also satisfies that day's monitoring check. Confirmation/resumption does not reserve another run or repeat completed model calls. Failed/cancelled runs retain reservations. Search API costs and model costs depend on the operator's providers and are not Stripe billing.

## Configuration and update

Keep the existing root `.env` password. Add the search key server-side and set `GENERATION_MODE=llm`, `LLM_MODEL` and `LLM_API_KEY` for AI-generated copy; template mode remains labeled as starter copy. Never use `NEXT_PUBLIC_*` for secret keys.

```powershell
git pull origin main
docker compose up -d --build
docker compose logs --tail=60 worker
```

The migrations preserve existing drafts, add the routine/pipeline data, and change the old default target of 10 to 50. Custom non-default project targets are retained. Historical workflow snapshots are not rewritten.

## Next integrations and truthful limits

Connecting the founder's Instagram and other social accounts, ingesting followers/engagement/profile growth, experimenting with platform-specific content/timing and posting automatically within a founder-approved policy remain integration work. Public search snippets do not provide private account metrics, full trending feeds, competitors' private analytics, or access to proprietary ranking algorithms.

Instagram Business Login serves professional accounts. The Meta app needs the relevant approved access level to serve founders beyond the app's own managed/test accounts. See [Meta's official login and access requirements](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login).

Video interview capture, transcription, consent verification, encrypted media storage, avatar/voice creation and rendered videos are not shipped in this increment. Autonomous production is the goal after onboarding and consent; consent to generate is separate from permission to publish.

Payment/CRM integrations must eventually confirm purchases automatically. The present pipeline intentionally does not fabricate conversion events to make progress appear better.
