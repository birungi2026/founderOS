# FounderOS

**Your AI-powered growth team.**

FounderOS helps early-stage founders plan customer acquisition, research buyer needs, review campaign drafts, and measure conversion in a shared organization workspace.

## Connected growth team

FounderOS is being built around five coordinated agents: Personal Brand, Viral Content Research, Founder Growth, AI Video Creator, and Product Launch.

The first connected workflow includes a versioned founder profile, explicit brand approval, a durable background job, source-backed opportunities, seven editable calendar drafts, a video script/storyboard, and a launch checklist. Agents share an immutable brand, evidence, and actual-performance snapshot. Outputs remain subject to founder review. Automatic public-web research, company briefs, research confirmation and flexible recurring preparation are now available when the search provider is configured. Video rendering, social account metrics/publishing connections, billing and self-service OAuth remain later milestones.

See [the implementation status](docs/IMPLEMENTATION.md) for capability boundaries and the founder-supplied [reference blueprints](docs/blueprints/README.md).

## Research and conversion automation

The default business milestone is the first **50 paying customers**. Company onboarding captures the problem, solution, target customers, competitors and proposed differentiator. Automatic research pauses for owner confirmation before content creation. Owners can choose daily/weekly/monthly preparation, 1–5 posts per selected day, timezone and timing. Daily news/competitor monitoring continues between content batches. A customer pipeline separates potential buyers, conversations, trials and confirmed customers.

Configure `BRAVE_SEARCH_API_KEY` in the root Compose `.env` once, then rebuild/recreate services. No source copying is required in automatic mode. Search is based on indexed public sources, not private social account access or secret algorithm analysis. See [the current growth employee contract](docs/GROWTH_EMPLOYEE.md) and [avatar provider recommendation](docs/AVATAR_PROVIDER.md).

## Implemented

- Registration, sign-in, expiring/revocable HttpOnly sessions, and organization owner/editor/viewer roles
- Persistent PostgreSQL storage (SQLite for local use), Alembic migrations, and tenant-scoped queries
- Saved projects and strategies; template mode by default, optional structured LLM generation
- Operator-attested research excerpts and validated citation references
- Campaign review, immutable publication snapshots, and explicit owner-approved publishing queue
- Operator-run LinkedIn OAuth delivery adapter with single-job claiming and uncertain-delivery handling
- Idempotent growth event ingestion, channel/campaign attribution, manual metrics, CSV export
- Audit logs, rate limits, readiness probes, request telemetry, CI, and container configuration

## Run locally

Python 3.12 and Node.js 22 are recommended.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
alembic upgrade head
uvicorn app.main:app --reload --no-access-log
```

Run the growth worker in a second terminal with the same backend environment:

```bash
cd backend
source .venv/bin/activate
python -m app.workflows.worker
```

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000 and create an account. API docs: http://localhost:8000/docs. The first account owns its new organization. Owners can add already-registered users as editors or viewers. Choose an organization before selecting a saved project. Projects and approvals survive reloads and server restarts.

The database schema is created by migrations, never implicitly at API startup. The old in-memory MVP had no durable data to migrate.

## Configure real AI

Set server-side `GENERATION_MODE=llm`, `LLM_API_KEY`, and `LLM_MODEL`. Optional `LLM_BASE_URL` defaults to `https://api.openai.com/v1` and must be a trusted operator-configured OpenAI-compatible endpoint. Use `uvicorn --env-file .env` or export variables; Alembic reads exported `DATABASE_URL`.

Generation has a 30-second timeout, a bounded output schema, and validates cited source IDs against the current project's sources. Invalid/provider-failed output creates no drafts. No tools or outbound messaging are exposed to the model. `template` mode requires no API key and is clearly labeled in the dashboard. Source text and project details are sent to the configured model provider when LLM mode is enabled.

## PostgreSQL and containers

Use `DATABASE_URL=postgresql+psycopg://user:password@host/database`, then run `alembic upgrade head` before starting the API. URL-encode special characters in database credentials.

For a local full-stack container deployment:

```bash
export POSTGRES_PASSWORD=choose-a-local-url-safe-password
docker compose up --build
```

Compose binds the API and frontend to localhost and runs one migration job before the API. Its default generation mode is `template`. Configure provider secrets through your deployment secret manager to enable real AI. See [deployment notes](docs/DEPLOYMENT.md) before exposing the service.

## Verify

```bash
cd backend
python -m pytest -q
alembic check
# Optional isolated PostgreSQL test schemas; use a dedicated test database:
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/founderos_test python -m pytest -q
cd ../frontend
npm run build
```

CI exercises SQLite, PostgreSQL, migrations, backend lint, and the frontend production build. Tests mock LLM and publishing providers; they never send real messages. A repeatable browser workflow is in `frontend/tests/smoke.py` (requires Python Playwright and Chromium, plus the running local services).

See [integration contracts](docs/INTEGRATIONS.md), [deployment notes](docs/DEPLOYMENT.md), and the [roadmap](docs/ROADMAP.md) for configuration and remaining work.

For Windows Docker users: keep your existing `.env` password when updating. Compose starts the worker automatically. If port 8000 is occupied, put `API_PORT=8001` and `NEXT_PUBLIC_API_URL=http://localhost:8001` in the root `.env`, then run `docker compose up -d --build`. These are file settings, not PowerShell commands.

Social account OAuth access for Instagram professional accounts and Facebook Pages is available through the project account panel. See [configuration, permissions and current limits](docs/SOCIAL_ACCOUNTS.md). Retrieved snapshots inform new agent workflows; publishing, messaging and unattended refresh are separate integrations.
