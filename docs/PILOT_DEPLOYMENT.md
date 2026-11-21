# Deploy the controlled Rymu pilot

## Server and DNS

Use a supported Ubuntu DigitalOcean Droplet with Docker and Compose >= 2.24.4. Size after measuring real workloads; FFmpeg runs CPU jobs one at a time per worker. A small paid pilot is not a promise that one host can support arbitrary scale. At Namecheap, point A records for `@`, `www` and `api` at the server. Remove stale AAAA records unless IPv6 is configured. Allow inbound 80/443 and restrict SSH. PostgreSQL, API and web have no public host ports in the production override.

Caddy issues TLS for rymu.ai, www.rymu.ai and api.rymu.ai. Set TLS_EMAIL to your administrator email. Do not enable access logging of signed media query strings. Media endpoints use temporary bearer links and no-store responses; do not cache them at a CDN.

## Environment

Preserve the existing POSTGRES_PASSWORD and database volume. Add:

```dotenv
TLS_EMAIL=you@example.com
FRONTEND_ORIGINS=https://rymu.ai
COOKIE_SECURE=true
NEXT_PUBLIC_API_URL=https://api.rymu.ai
PUBLIC_API_URL=https://api.rymu.ai
APP_PUBLIC_URL=https://rymu.ai
GENERATION_MODE=llm
# LLM_MODEL / LLM_API_KEY / BRAVE_SEARCH_API_KEY / TRANSCRIPTION_API_KEY
# TAVUS_API_KEY only when training/rendering will be used
# JOURNEY_MEDIA_SIGNING_KEY: random secret at least 32 characters
JOURNEY_ENABLED_ORGANIZATIONS=approved-organization-id
JOURNEY_PUBLISHING_ENABLED=false
INSTAGRAM_PUBLISHING_ENABLED=false
BILLING_ENFORCED=false
PLAN_VIDEO_SECONDS=900
PLAN_FOOTAGE_SECONDS=1800
PLAN_RESEARCH_RUNS=20
```

Use the existing official OAuth setup. Instagram uses Instagram Login and requires instagram_business_basic plus instagram_business_content_publish and instagram_business_manage_insights for the full publishing/insight path. Existing read connections must reauthorize. Confirm the supported permissions/API version in Meta's dashboard; professional accounts and appropriate app access/review are required. Missing insights remain unavailable, not zero. Turn delivery flags on only after reviewing a real test post. Likeness/voice training remains separately consented and operator-provisioned: add approved organization IDs to TAVUS_TRAINING_ORGANIZATIONS only after confirming vendor capacity and setup costs. It is empty by default, independently of the general journey allowlist; buying the base subscription cannot enable clone training on its own.

## Billing

Create a Stripe recurring monthly USD price for $59. Set STRIPE_SECRET_KEY, STRIPE_PRICE_ID and STRIPE_WEBHOOK_SECRET server-side. Configure the customer portal for cancellation/payment management and a webhook at https://api.rymu.ai/v1/billing/webhook subscribing to customer.subscription.created, updated and deleted. Checkout retries reuse a durable pending-session key and an open session; completed sessions wait for webhook confirmation rather than starting another subscription. The endpoint verifies the signature and retrieves canonical subscription state from Stripe; a return URL never grants access. Start with Stripe test mode. Check signed events, retry/deduplication, same-second/out-of-order events, successful payment, past_due, cancellation at period end and a new subscription after cancellation before enabling BILLING_ENFORCED=true.

Limits are per organization and UTC calendar month, not subscription anniversary. They do not roll over. Each avatar render reserves a conservative script budget (minimum 30 seconds; maximum of word and character estimates, rounded up to six seconds); rerenders are new reservations. This is not exact provider invoice settlement. Failed/uncertain requests keep their reservation. Footage edits reserve the selected actual clip length. Research workflow requests reserve one unit, including recurring runs. Separate operator attempt caps still apply. No paid top-up or unlimited option is offered. Confirm provider commercial/face-capacity terms before selling personal-clone access.

## Build and start

```bash
git pull --ff-only origin main
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build --force-recreate
docker compose -f compose.yaml -f compose.production.yaml ps -a
docker compose -f compose.yaml -f compose.production.yaml logs --tail=80 migrate api worker web proxy
```

The migrate container must exit 0; API/web/worker must become healthy. Worker health checks a local loop heartbeat. Configure external uptime/health alerts; Docker health status alone does not notify the operator or prove a real provider transaction works. Install the provider keys and allowlist only pilot organizations. Keep generation and delivery disabled for public free signups until entitlements and provider budgets are deliberately provisioned.

## Backups and restoration

Run `./scripts/backup.sh /secure/backup-directory` from the repository. It briefly stops API/worker writers, produces a custom-format PostgreSQL dump and a media tar archive, then starts writers in an EXIT trap. The first run may build the API image; build before a scheduled backup window. The dump and archive are private; copy them encrypted off the Droplet. Keep the encryption/signing keys and environment securely backed up separately. Set retention and failure alerts in your own backup scheduler; a backup on the same disk is not disaster recovery.

Before launch, rehearse restoration into an isolated server: stop writers; restore the dump with pg_restore into a fresh founderos database, restore the matching archive into the private journey-media volume with UID 10001 ownership, restore the matching secrets, run migrations, and verify login, recordings, a test clip and scheduled-job status. Never run a restore over production without a reviewed backup and maintenance window. Scheduled external jobs from restored databases may already have been sent: disable publishing flags and reconcile provider IDs before re-enabling them.

## Website conversions

An owner can create/rotate a server conversion key in Results → Track website referrals and conversions. Send from a trusted backend after checking your own purchase/lead event. Never embed the key in browser JavaScript. A stable customer ID for the first paid conversion prevents counting each renewal/order as a new customer. Rotating a key immediately invalidates the old key.

```python
import os
import httpx

# Run after your own payment provider confirms a genuine first paid customer.
httpx.post(
    "https://api.rymu.ai/v1/conversions",
    headers={"X-Rymu-Conversion-Key": os.environ["RYMU_CONVERSION_KEY"]},
    json={
        "project_id": os.environ["RYMU_PROJECT_ID"],
        "external_id": "first-paid-customer:your-stable-customer-id",
        "kind": "paying_customer",
        "channel": "instagram",
        "campaign": "coach_pilot",
    },
    timeout=20,
).raise_for_status()
```

Retries use exactly the same ID/body. Changed data with an old ID is rejected. These events are server-reported; Rymu does not independently verify the payment, refunds, or cross-device attribution. Do not count Rymu's own subscription webhook as a founder's customer purchase. Avoid double-entering a manual sale and a server event. UTM links supply referral tags, not proof of causation.

## Live acceptance still required

Follow RECOMMENDATION_AUDIT.md. Run actual footage upload/caption/render/playback on a physical phone and desktop, a permitted Tavus training/render job, a scheduled approved Instagram Reel and Facebook Page video, source/metric comparison in the native apps, and Stripe test checkout/cancellation. Automated tests use external provider fixtures. A paid customer interview, social growth or renewal cannot be manufactured by a passing test.

Primary integration references: https://developers.facebook.com/docs/instagram-platform/ · https://docs.stripe.com/webhooks · https://docs.stripe.com/billing/subscriptions/webhooks · https://docs.tavus.io/ · https://platform.openai.com/docs/guides/speech-to-text
