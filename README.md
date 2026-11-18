# FounderOS

**The AI Growth Employee for Founders.**

FounderOS helps early-stage founders go from product launch to a repeatable customer acquisition workflow.

## MVP v0.1
- **Growth Strategist:** capture product and target customer, generate a first growth plan
- **Growth Executor:** draft LinkedIn and outreach campaigns, require human approval
- **Growth Analyst:** record leads, signups, customers and report conversion
- **Web dashboard:** Next.js App Router
- **API:** FastAPI

The initial planning and drafting are deterministic placeholders, not autonomous AI. No external messages are sent or published.

## Run backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Run frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. API documentation: http://localhost:8000/docs.

## Roadmap
1. Authentication, tenant isolation and production database
2. LLM-powered planning with citations, guardrails and evaluations
3. Approved outreach/publishing integrations
4. Event-based attribution and analytics

See [docs/ROADMAP.md](docs/ROADMAP.md). Never place API secrets in the frontend.
