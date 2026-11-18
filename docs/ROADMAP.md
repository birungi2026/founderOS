# FounderOS growth-agent roadmap

## Current connected-team milestone

Brand onboarding, immutable approved brand versions, five coordinated agent steps, durable SQL-backed jobs, context and performance snapshots, monthly run limits, a seven-day editable calendar with review invalidation, video scripts/storyboards, and persistent launch checklists. See IMPLEMENTATION.md for exact behavior and remaining work. The original product blueprint documents are retained under blueprints/ as reference material.

This is the first connected workflow, not the complete paid SaaS. Next priorities are safe research/import connectors, real video rendering and storage, self-service social OAuth/scheduling, then Stripe billing and entitlements.

## Previously delivered foundation

1. **Persistence:** SQLAlchemy models, PostgreSQL support, local SQLite, versioned Alembic migrations.
2. **Identity and organizations:** password hashing, hashed session tokens, expiry/logout, tenant-scoped reads and writes, owner/editor/viewer roles, membership management, transactional audit events.
3. **Generation:** optional server-side OpenAI-compatible LLM adapter, structured output validation, source ID validation, bounded calls, honest template fallback mode. Provider errors fail closed rather than silently using templates.
4. **Research:** permitted-source excerpt collection, operator attestation, provenance and citation links. No fabricated prospects or automated scraping.
5. **Execution:** draft review and explicit owner approval to queue exact content, server-side LinkedIn OAuth adapter, durable single-use job claims, no automatic replay of uncertain delivery.
6. **Analytics:** idempotent event ingestion contract for CRM adapters, explicit channel/campaign attribution, manual increments, CSV export.
7. **Operations:** isolation and provider contract tests, migration checks, PostgreSQL CI, frontend build, single-process rate limiting, request IDs/timing logs, health/readiness endpoints, container deployment files.

## Requires operator configuration

- A database and secret manager for deployment
- An LLM provider/model/API key to enable real generation
- A LinkedIn developer app, approved API access, and an OAuth token scoped to the publishing identity
- A CRM-side adapter mapping its events to FounderOS's ingestion contract
- TLS, exact CORS origins, secure cookies, backups, and shared ingress limits for production

## Follow-up product work

- Email verification, password recovery, MFA/SSO, invitation emails, and session management UI
- Self-service OAuth authorization/refresh/revocation and additional publishing providers
- Provider-specific CRM connectors, webhook signature verification, and least-privilege integration API keys
- Independent source verification, discovery connectors, richer research evaluations, and prompt-injection evaluations
- Statistical attribution, deduplicated identities across channels, cohorts, and cost/revenue analytics
- Shared rate-limit storage, durable task workers, job reconciliation UI, pagination, and load testing

Research is explicitly operator-attested, not independently verified. The LLM verifier checks structure and citation membership, not factual truth. CSV export is an interchange format, not a native CRM connection. These distinctions are part of the current product contract.

## Product rules

- Never claim guaranteed customer acquisition.
- No autonomous unsolicited bulk outreach.
- Require explicit approval before sending or publishing.
- Never scrape prohibited sources or invent prospect information.
- Keep credentials server-side and all customer data tenant-scoped.
