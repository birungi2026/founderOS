# FounderOS — Implementation Plan

**Version:** 1.0 | **Horizon:** 12 weeks for a focused MVP | **Assumption:** 2–3 experienced full-stack/AI engineers; schedule is indicative, not guaranteed.

This document is an executable engineering roadmap for the architecture in `ARCHITECTURE.md`. It specifies repository structure, development sequence, agent behavior, acceptance criteria, test plan, and ready-to-use Codex prompts.

## 1. MVP definition
**Must ship:** founder onboarding, versioned brand profile, source-backed trend discovery, weekly growth plan, editable content calendar, script-to-video render with subtitles, product launch planner, human approval queue, one production-ready social publishing integration where approved, analytics dashboard, Stripe billing, usage limits.

**Post-MVP:** AI avatar/voice clone, multi-channel automatic adaptation, deep competitor intelligence, full attribution integrations, agency white-label, automated A/B testing, advanced growth prediction.

## 2. Repository layout
```text
founderos/
├── apps/
│   └── web/                         # Next.js App Router + TypeScript
│       ├── app/(auth)/
│       ├── app/(dashboard)/
│       │   ├── onboarding/
│       │   ├── brand/
│       │   ├── research/
│       │   ├── calendar/
│       │   ├── studio/
│       │   ├── launches/
│       │   ├── approvals/
│       │   ├── analytics/
│       │   └── settings/
│       ├── components/
│       └── lib/api/
├── services/
│   ├── api/
│   │   ├── app/main.py
│   │   ├── app/api/v1/
│   │   ├── app/models/
│   │   ├── app/schemas/
│   │   ├── app/security/
│   │   ├── app/services/
│   │   └── migrations/
│   ├── agent_worker/
│   │   ├── workflows/
│   │   ├── agents/{brand,research,growth,video,launch}/
│   │   ├── tools/
│   │   ├── prompts/
│   │   └── evaluations/
│   └── video_worker/
│       ├── renderer/
│       ├── templates/
│       └── tests/
├── packages/
│   ├── contracts/                   # OpenAPI-derived TS client + schemas
│   └── design-system/
├── infra/
│   ├── docker-compose.yml
│   ├── terraform/                   # optional after MVP
│   └── monitoring/
├── tests/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION.md
│   ├── SECURITY.md
│   └── API.md
├── .github/workflows/ci.yml
├── .env.example
├── Makefile
└── README.md
```

## 3. Development setup
1. Initialize a pnpm workspace for Next.js and a Python `uv` workspace for services.
2. Run PostgreSQL, Redis, Temporal dev server, and S3-compatible local storage with Docker Compose.
3. Add migrations (Alembic), typed Pydantic schemas, OpenAPI-generated TypeScript client, and seeded demo workspace.
4. Configure OIDC auth; verify JWT signatures, issuer, audience, expiration, and workspace membership server-side.
5. Define environment variables in `.env.example`: `DATABASE_URL`, `REDIS_URL`, `TEMPORAL_ADDRESS`, `OBJECT_STORAGE_*`, `OIDC_*`, `LLM_PROVIDER_*`, `STRIPE_*`, `SOCIAL_OAUTH_*`, `SENTRY_DSN`. Never commit secrets.
6. Set up pre-commit hooks, ruff, mypy/pyright, eslint, TypeScript strict mode, pytest, Playwright, and GitHub Actions.

## 4. Delivery phases
### Phase 0 — Product and integration validation (Week 1)
- [ ] Interview 10 technical founders about posting, video creation, and launch workflow.
- [ ] Define 3 jobs-to-be-done and measurable activation criteria.
- [ ] Verify current API eligibility, app review, rate limits, pricing, and publishing permissions for target platforms.
- [ ] Select one social provider for MVP and a manual export fallback.
- [ ] Confirm media licensing, AI voice consent, and privacy policy requirements.
**Exit:** written PRD, verified provider feasibility, prioritized backlog, and clickable dashboard wireframes.

### Phase 1 — Core platform and brand memory (Weeks 2–3)
- [ ] Implement auth, workspace membership, RBAC, and tenant-scoped models.
- [ ] Create onboarding: website URL, target audience, goals, founder Q&A, brand assets.
- [ ] Build safe website fetcher and source extraction.
- [ ] Implement Brand Agent using JSON-schema structured output and grounded source context.
- [ ] Add brand profile editor, version history, approval, and story bank.
- [ ] Add agent run tracing, usage ledger, cost budgets, and job status UI.
**Exit:** a founder can create a workspace, import a website, and approve a grounded brand profile.

### Phase 2 — Trend research and growth planning (Weeks 4–5)
- [ ] Implement approved research adapters with source URLs, dates, and quota handling.
- [ ] Store and deduplicate trend sources; calculate relevance scores.
- [ ] Build Trend Agent: opportunity, evidence, audience fit, original angle, uncertainty.
- [ ] Build Growth Agent: weekly plan, channels, content pillars, hypotheses, KPIs.
- [ ] Create content calendar and rich-text editor with immutable revisions.
- [ ] Add voice consistency and unsupported-claim evaluation before review.
**Exit:** user can generate and edit a seven-day calendar with source-backed content ideas.

### Phase 3 — Video studio (Weeks 6–7)
- [ ] Generate 15–60 second scripts with hooks, scene descriptions, captions, and CTA.
- [ ] Implement asset upload, licensing metadata, and template selection.
- [ ] Create FFmpeg rendering worker: 9:16 MP4, overlays, captions, audio normalization, thumbnails.
- [ ] Add optional licensed TTS and STT adapters, disabled by default.
- [ ] Build render queue, progress states, retries, preview, and download.
- [ ] Add render QA: duration, aspect ratio, subtitle timing, safe media usage.
**Exit:** founder can generate, edit, render, and download a short video from a brief.

### Phase 4 — Product launch and publishing (Weeks 8–9)
- [ ] Implement launch projects, timeline, checklists, content bundles, and scheduled tasks.
- [ ] Generate teaser, announcement, follow-up, landing-page copy, and video briefs.
- [ ] Add channel OAuth, token refresh, scope verification, and encrypted storage.
- [ ] Implement immutable approvals tied to revision hash, channel, account, and schedule.
- [ ] Build idempotent publisher and provider-specific error handling.
- [ ] Add manual copy/export for unsupported platforms.
**Exit:** founder can plan a launch and publish approved content through a supported provider, or export it manually.

### Phase 5 — Analytics, billing, hardening (Weeks 10–11)
- [ ] Ingest available provider metrics and instrument campaign UTM links.
- [ ] Implement analytics for content performance, traffic, and attributed conversions where available.
- [ ] Add Stripe plans, checkout, customer portal, webhook verification, usage enforcement.
- [ ] Add deletion/export, retention settings, audit logs, rate limits, and security review.
- [ ] Run E2E tests, load tests, accessibility checks, and prompt-injection evaluations.
**Exit:** end-to-end paid onboarding, generation, approval, publishing, reporting, and cancellation work.

### Phase 6 — Private beta (Week 12)
- [ ] Recruit 10–20 founders across 2–3 segments.
- [ ] Observe onboarding and content creation sessions.
- [ ] Track activation, approved output, weekly retention, render costs, and willingness to pay.
- [ ] Fix top failure modes and cut features with poor usage.
**Exit:** beta report with evidence of repeat use and unit economics; decide expand/pivot.

## 5. Suggested core interfaces
```python
from typing import Literal
from pydantic import BaseModel, Field

class AgentContext(BaseModel):
    workspace_id: str
    campaign_id: str | None = None
    brand_profile_version: int
    goal: str
    budget_usd: float = Field(ge=0)
    trace_id: str

class Evidence(BaseModel):
    url: str
    title: str
    observed_at: str

class AgentArtifact(BaseModel):
    kind: Literal['brand_profile', 'trend_opportunity', 'growth_plan', 'video_brief', 'launch_plan']
    payload: dict
    evidence: list[Evidence] = []
    warnings: list[str] = []

class ApprovalRequest(BaseModel):
    content_revision_id: str
    revision_sha256: str
    social_connection_id: str
    channel: str
    scheduled_at: str | None = None
```

All API inputs require server-side tenant authorization. `AgentArtifact.payload` should be specialized into strict, versioned schemas for each artifact before production.

## 6. Workflow pseudocode
```python
async def build_weekly_campaign(ctx):
    brand = await load_approved_brand(ctx.workspace_id)
    trends = await run_trend_agent(ctx, brand)
    plan = await run_growth_agent(ctx, brand, trends)
    drafts = await create_channel_drafts(ctx, plan, brand)
    await check_claims_and_voice(drafts, brand)
    await save_drafts_for_review(drafts)
    return {"status": "needs_review", "draft_count": len(drafts)}

async def publish_approved_post(approval_id):
    approval = await load_valid_approval(approval_id)
    revision = await load_immutable_revision(approval.content_revision_id)
    assert sha256_revision(revision) == approval.revision_sha256
    assert approval.status == "approved"
    assert await connection_has_required_scopes(approval.social_connection_id)
    return await publish_idempotently(approval, revision)
```

**Important:** workflow code should use Temporal activities for external API calls and durable waiting for human approvals. The pseudocode is illustrative, not a drop-in implementation.

## 7. UI screens
| Screen | Essential controls |
|---|---|
| Onboarding | URL import, founder interview, target audience, goals |
| Brand Studio | Brand voice, pillars, story bank, edit and approve |
| Research Radar | Sources, timestamps, opportunity score, save idea |
| Growth Dashboard | Weekly objectives, experiments, KPI summary |
| Content Calendar | Draft cards, drag schedule, editor, approval status |
| Video Studio | Script, template, assets, preview, render progress |
| Launch Center | Countdown, phases, tasks, channel bundles |
| Approval Inbox | Diff, channel, destination, schedule, approve/reject |
| Analytics | Reach, engagement, clicks, conversions, caveats |
| Settings | Team roles, connections, consent, usage, billing |

## 8. Testing and acceptance criteria
### Functional
- [ ] New founder can onboard and approve brand profile without developer assistance.
- [ ] Brand outputs do not invent founder achievements or testimonials in curated evaluation fixtures.
- [ ] Research ideas display verifiable source URL and observed timestamp.
- [ ] Weekly plan creates seven days of editable drafts, without publishing them.
- [ ] Video renderer exports playable 1080x1920 H.264/AAC MP4 with aligned captions.
- [ ] Launch project generates phased tasks and assets tied to one campaign.
- [ ] Edited content invalidates prior approval.
- [ ] No post is published without an active, exact-revision approval.
- [ ] Duplicate delivery of publish job does not create duplicate posts under tested provider behavior.
- [ ] Cross-workspace resource access returns 403/404 and no leaked data.
- [ ] Stripe webhook signatures are verified; repeated events are idempotent.

### Non-functional targets (initial engineering targets, validate in beta)
- [ ] API p95 under 500 ms for ordinary CRUD (excluding model/render jobs).
- [ ] First draft generation p95 under 60 seconds under normal provider availability.
- [ ] Video render jobs expose progress and recover from transient failures.
- [ ] 100% of external publish attempts have auditable approval records.
- [ ] Per-workspace cost limits are enforced and surfaced in UI.
- [ ] Secrets never appear in logs or client bundles.

### Security and adversarial tests
- Prompt injection in website copy instructing the agent to reveal secrets.
- SSRF through URLs and redirects to internal networks.
- Cross-tenant IDOR, role escalation, stale JWT, OAuth state mismatch.
- Unapproved revision swapping between approval and publication.
- Malicious uploads, unsupported MIME types, oversized video, FFmpeg timeouts.
- Platform API 401/429/5xx, token expiration, partial publish failure.
- Unauthorized likeness or voice clone request.

## 9. Codex implementation prompts (run sequentially)
Use each prompt after reviewing the previous PR. Keep the agent within the repository and require tests with every change.

### Prompt 1 — Scaffold
> Build the FounderOS monorepo described in docs/ARCHITECTURE.md and docs/IMPLEMENTATION.md. Set up Next.js TypeScript, FastAPI, Postgres, Redis, Temporal dev, S3-compatible local storage, Docker Compose, CI, linting, tests, environment examples, and a README. Do not implement agent business logic yet. Add a working health-check path and a local startup command.

### Prompt 2 — Auth and tenants
> Implement OIDC authentication, workspaces, memberships, RBAC, SQLAlchemy models, Alembic migrations, and workspace-scoped API authorization. Add unit/integration tests for cross-tenant access, invalid tokens, and role permissions. Never trust workspace_id from a client without membership verification.

### Prompt 3 — Brand onboarding
> Implement safe product website import, founder interview forms, brand profile generation through a provider-neutral LLM adapter using strict JSON schemas, versioned brand memory, editing, and explicit approval. Include source provenance, no-fabrication guardrails, API tests, and dashboard pages.

### Prompt 4 — Research and strategy
> Implement permitted research adapters, evidence-backed trend opportunities with source timestamps, a research dashboard, Growth Agent weekly plans, and a seven-day content calendar. Add duplicate filtering, uncertainty labels, token cost accounting, and test fixtures with mocked providers.

### Prompt 5 — Video generation
> Implement a video studio that transforms an approved creative brief into a short-form script, storyboard, subtitle track, and 9:16 MP4 using templates and FFmpeg. Build isolated video workers, object storage, render job progress, asset-rights metadata, preview/download, and tests. Do not implement unauthorized voice or likeness cloning.

### Prompt 6 — Launch planning
> Implement product launch projects with configurable launch date, phased tasks, generated content bundles, founder approvals, and a launch calendar. Reuse brand context, research, content revisions, and video artifacts. Include integration tests.

### Prompt 7 — Publishing
> Implement one official social provider adapter behind a generic publisher interface, OAuth state/PKCE as supported, secure tokens, immutable revision approvals, scheduled jobs, idempotency, provider error handling, and audit logs. Add a manual export fallback. Never publish without explicit approval tied to exact revision, account, and schedule.

### Prompt 8 — Analytics and billing
> Add UTM tagging, provider metrics ingestion where available, analytics dashboard with attribution caveats, Stripe subscription checkout/portal/webhooks, usage ledger, plan limits, and secure idempotent billing handlers. Include tests for duplicate webhooks and rate limits.

### Prompt 9 — Hardening and beta
> Run a security and reliability audit of the whole FounderOS repository. Add prompt-injection defenses, SSRF tests, cross-tenant E2E tests, accessibility checks, load tests, operational dashboards, backup/restore documentation, deployment runbooks, and a beta feedback instrumentation plan. Report unresolved risks rather than claiming completion.

## 10. Launch checklist
- [ ] Production domains, TLS, backups, error alerting, secret rotation.
- [ ] Privacy policy, terms, consent capture, data deletion/export.
- [ ] Social platform API access reviewed and approved for intended use.
- [ ] Usage and billing tested in Stripe test mode.
- [ ] Founder approval required for every external post.
- [ ] Content/media rights and AI-generated-media disclosures addressed.
- [ ] Support email, incident response owner, rollback procedure.
- [ ] Pilot onboarding guide, tutorial, feedback form, and KPI dashboard.

## 11. First beta hypotheses
1. Founders who approve a brand profile will create at least three usable drafts in their first session.
2. A guided founder interview yields more accepted content than website-only context.
3. Source-backed ideas improve founder trust and draft acceptance.
4. Template-based video production is valuable without expensive avatars.
5. A combined growth + launch workflow retains users better than one-off content generation.

Measure each hypothesis with actual user behavior. Do not infer product-market fit from impressions alone.
