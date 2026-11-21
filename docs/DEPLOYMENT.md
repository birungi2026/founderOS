# Deployment and operations

## Configuration

Run migrations with the same `DATABASE_URL` used by the API. Use PostgreSQL for shared deployment. The local SQLite default is intended for one development instance. Keep database credentials, LLM keys, publishing OAuth tokens, and session cookies out of logs and source control.

Run one API worker for the included process-local rate limiter (15 authentication writes and 120 other writes per source IP per minute). For multiple workers/replicas, enforce shared quotas at the ingress or replace the limiter with shared storage. Do not trust arbitrary client-supplied forwarded IP headers. Bound request sizes at the ingress. Configure request, connection, model-spend, and concurrency limits appropriate to your deployment.

Serve over TLS and set `COOKIE_SECURE=true`. Set `FRONTEND_ORIGINS` to exact trusted frontend origins, separated by commas. Build the frontend with the browser-reachable `NEXT_PUBLIC_API_URL`; this is a build-time value. Use the same hostname in local frontend/API URLs so SameSite cookies work; `localhost` and `127.0.0.1` are different sites. For hosted installations use a same-site API hostname or reverse proxy. Unrelated frontend/API sites are not supported by the current SameSite=Lax session policy.

`compose.yaml` is a localhost deployment example. Its database password must be URL-safe (otherwise use a separately encoded database URL). No model or publishing secrets are baked into its images. For production use your secret manager, private database networking, backups, and a TLS reverse proxy. Run migrations once before replicas start; do not run concurrent migrations.

## Health and telemetry

- `/health`: process liveness, no authentication required.
- `/ready`: database connectivity and presence of migrated application tables; returns 503 if unavailable.
- Requests emit JSON logs containing a generated request ID, route template, status, and duration. Bodies, cookies, emails, credentials, and raw provider responses are not logged.
- Organization audit logs record actor/resource/action in the same transaction as writes. API callers cannot edit audit records. This is application-level audit history, not a cryptographically tamper-proof external audit service.
- Run uvicorn with `--no-access-log` to avoid duplicate unstructured URL/query logs. Export stdout to your deployment's log collector and alert on error rate, latency, and database readiness.

## Recovery

Back up PostgreSQL and test restoring it. Sessions are revocable hashed tokens with 24-hour expiry; restarting the API preserves them. Periodically delete expired session rows through an operator maintenance task.

Publishing has durable claims. A worker crash can leave a job `sending`; a lost response can leave it `uncertain`. Check the provider before reconciliation. There is no automatic retry mechanism, and the API cannot silently reset these states.

## Current deployment boundaries

Registration is open and emails are not verified. Add controlled signup, email verification, password recovery, and MFA/SSO before wider commercial rollout. Self-service OAuth onboarding and refresh are follow-up work; the included adapter uses an operator-provisioned scoped token. Validate the supported LinkedIn API version and app permissions before enabling delivery.

The unit/integration suite uses provider mocks. A passing suite does not establish live provider access, research truth, or guaranteed customer acquisition. No production deployment or real publishing is performed by the implementation task.

## Rymu domain

For the intended production domain `rymu.ai`, a same-site API deployment can use `https://api.rymu.ai`: build with `NEXT_PUBLIC_API_URL=https://api.rymu.ai`, set `FRONTEND_ORIGINS=https://rymu.ai` (include `https://www.rymu.ai` only if it also serves the frontend), and set `COOKIE_SECURE=true`. Point the corresponding Namecheap DNS records at the DigitalOcean deployment and provision HTTPS for both hostnames before testing OAuth. Register callback URLs matching the existing backend routes. This documentation and app metadata do not create DNS records or certificates. Existing local Compose names and secrets remain unchanged.

For the connected interview → Facebook video path, follow [Growth journey provisioning](GROWTH_JOURNEY.md). Both API and worker require the shared private media volume, the same signing key, provider configuration and an explicitly provisioned organization. Publishing remains disabled until the server flag, Page permissions and an owner approval are present.

For the Rymu pilot, private footage, Stripe subscriptions and the DigitalOcean/Caddy production override, follow [PILOT_DEPLOYMENT.md](PILOT_DEPLOYMENT.md). Validate the [recommendation audit](RECOMMENDATION_AUDIT.md) before making growth or full-automation claims.
