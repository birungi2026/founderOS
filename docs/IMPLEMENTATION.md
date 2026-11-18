# FounderOS: coordinated founder growth team

## Product scope

An AI founder growth and personal branding SaaS with five cooperating agents: Founder Growth, AI Video Creator, Personal Brand, Viral Content Research, and Product Launch. Every agent shares tenant-scoped brand, evidence, and performance context. The UI is a connected workflow, with human approval before external publication.

The original founder-supplied documents live in blueprints/ as reference material. Their embedded instructions are not automatically executed. This file records implementation decisions and current capability.

## Current research/conversion increment

See GROWTH_EMPLOYEE.md for the current 50-customer goal, company onboarding, automatic research, exact-snapshot research confirmation, daily monitoring, configurable routines and customer pipeline. This is the source of truth for the latest scope; the first connected milestone below is retained as implementation history.

## First connected milestone

1. Choose or create a product project in the existing organization workspace.
2. Complete the founder interview: story, expertise, positioning, voice, pillars, proof points, topics to avoid, optional website reference.
3. Save a brand version, review it, and explicitly approve it. Changes create a new pending version; older versions remain immutable.
4. Add at least one permitted-source excerpt. URLs are recorded, not fetched. Research sources remain operator-attested.
5. Provide a goal, content-week start and launch date; start one durable workflow.
6. A separate worker runs Personal Brand → Research → Growth → Video → Launch. The Personal Brand step retrieves approved memory; the other four use strict structured schemas through either the model provider or clearly labeled tailored templates.
7. Review research opportunities, seven editable calendar drafts, a 15–60 second video script/storyboard and a dated launch checklist. Edits create content revisions and invalidate approval. Calendar dates are planning dates, not automatic publication schedules.
8. Review calendar drafts in the shared campaign approval section. Existing explicit owner queueing and operator-run LinkedIn delivery remain in place.

## Design choices

Keep backend/ and frontend/ instead of moving a deployed application into a new monorepo layout. Keep existing tenant authorization and revocable sessions. Use relational job claims now rather than introducing multiple workflow engines before the connected path works. The SQL worker is a deliberate MVP choice, not a claim that Temporal, Redis, Celery or LangGraph are installed.

New tables: brand_versions, workflow_runs, agent_steps, workflow_usage, content_revisions, launch_tasks. Drafts receive a monotonic revision number. All new endpoints are under /v1 and enforce current membership and role. Workflow runs store immutable context snapshots and an organization-scoped idempotency key. The worker rechecks membership and role and atomically claims/finalizes runs. It has no publishing tools or credentials in model context.

Jobs transition queued → running → needs_review, or failed/cancelled. A 600-second lease bounds a job. Expired running jobs become failed with worker_interrupted when a worker next polls; they are never invisibly replayed and charged again. Cancellation is checked between steps and before saving drafts. A model request already in flight may finish, but cannot finalize a cancelled run. Intermediate artifacts may remain for inspection; final drafts and tasks commit atomically.

The current default allowance is 40 workflow runs per organization per UTC month, reserved transactionally when queued. Repeating a request with the same idempotency key and input reuses the run without reserving another unit. Different input with the same key returns 409. Failed and cancelled runs retain their reservation because work may have incurred provider cost. Each run performs at most four model calls, each with a 30-second timeout and 3,500 output-token cap. Actual token usage is recorded when the provider supplies it. This is run-based usage enforcement, not Stripe billing or a dollar-denominated spend cap.

## Operational setup

Apply `alembic upgrade head` before starting API and worker. For local development, run `python -m app.workflows.worker` from backend/ in a second terminal with the same database/provider environment as the API. Compose starts a worker automatically. Use `python -m app.workflows.worker --once` for a single queued job.

In Windows PowerShell, after pulling this release into your existing checkout:

```powershell
git pull
docker compose up -d --build
docker compose logs --tail=60 worker
```

Keep your current .env password. If port 8000 is occupied, set API_PORT=8001 and NEXT_PUBLIC_API_URL=http://localhost:8001 in .env; the shared Compose file now supports this without manual edits. Existing custom port mappings in compose.yaml may conflict with a Git pull; preserve .env and reconcile the file before restarting. Provider variables must be configured in the root Compose .env, not only in backend/.env.

## Explicitly not shipped in this milestone

- Private social feed/algorithm access or arbitrary website import (public search discovery is now implemented)
- MP4 rendering, media uploads, avatars, TTS or voice cloning
- Self-service OAuth, scheduled publishing or additional social adapters
- Native CRM sync, causal attribution or automated performance optimization
- Stripe subscriptions, checkout, billing webhooks or a payment UI
- OIDC migration, password recovery, Redis, vector retrieval or production-scale workers

The workflow considers observed performance to propose experiments. It does not promise virality, invent campaign results, or independently learn a new model. Outputs must be checked for factual accuracy and brand fit by the founder.
