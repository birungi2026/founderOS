# Social account access

This increment connects Instagram professional accounts (Business/Creator) and Facebook Pages using the founder's own OAuth authorization. It reads profile follower totals and up to 25 recent posts. It does not grant access to arbitrary private accounts, personal Facebook profiles, follower identities, DMs or public publishing. LinkedIn and TikTok connections remain separate work.

Owners initiate connections, retrieve account data and disconnect. Organization members can view account summaries. A successful connection grants only `instagram_business_basic` or `pages_show_list,pages_read_engagement`. Facebook connects up to 100 Pages returned by Meta for the grant; use Meta's granular Page selection to limit access. More than 100 Pages and paginated historical media are not imported.

## Server setup

1. Create and configure the applicable Meta app products: Instagram API with Instagram Login and/or Facebook Login with Pages access. These may use different App IDs/secrets. For Instagram, register the founder/test account and complete the account's tester authorization. Production access for unrelated founders requires Meta review/Advanced Access and any required business verification.
2. Register exact OAuth redirect URIs matching the root `.env` values, including the actual API port (e.g. 8001 if 8000 is occupied). Public deployments require HTTPS, secure login cookies, privacy policy and provider-required data deletion/deauthorization configuration before launch. The founder must return in the same signed-in browser session.
3. Generate a Fernet key using the backend environment: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Store it as `SOCIAL_TOKEN_ENCRYPTION_KEY` in `.env`/your secret manager. Keep it stable across redeploys and replicas and back it up securely. Losing or replacing it requires founders to reconnect. Never put it or provider secrets in `NEXT_PUBLIC_*` variables.
4. Set `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_REDIRECT_URI`, and/or the corresponding `FACEBOOK_*` values. The default callback paths are `/v1/social/instagram/callback` and `/v1/social/facebook/callback`. `META_GRAPH_VERSION` defaults to `v25.0`; select a supported version configured for your app.
5. Rebuild: `docker compose up -d --build`. Open a project → Connected social accounts → Connect → authorize on Meta → Return to FounderOS → Refresh connected accounts → Retrieve account data.

Saved account snapshots are included in newly queued agent contexts as untrusted evidence. They are not payment proof or a guarantee of reach. Retrieval is currently explicit via the account panel; unattended refresh, insight time series, token renewal and expiry notifications are follow-up work. Expired/invalid credentials require reconnection. Failed retrieval preserves the previous timestamped snapshot rather than claiming fresh data.

Disconnect immediately removes the local token and current snapshot, stopping future access through this connection. To revoke the provider grant itself, use Instagram/Facebook's app permissions settings. Existing workflow context snapshots remain in campaign history. Provider-initiated revocation/deletion webhooks must be added before a public launch; current code fails closed on invalid provider requests but cannot proactively detect those events.

## Security and verification

OAuth state is random, hashed, short-lived, bound to the founder session/user/project/provider, checked against current owner membership and consumed atomically before token exchange. Tokens are encrypted at rest and never returned to the frontend or sent to the model. Fixed provider hosts, bounded responses, timeouts and disabled redirects prevent following arbitrary paging URLs. Operator reverse-proxy/APM logs must redact callback query strings and provider request URLs containing credentials.

Automated tests mock Meta endpoints. They verify grant/callback handling, replay/session isolation, encrypted storage, sanitized snapshots, tenant isolation and disconnect. Live provider authorization cannot be verified without the deployment's Meta app configuration and a real eligible account.

Official references: [Instagram business login](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login/business-login), [Instagram API capabilities](https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-instagram-login), [Facebook Page enumeration](https://developers.facebook.com/docs/graph-api/reference/user/accounts/).

## Preview without credentials

Open a project → Connected social accounts → **Try demo connection flow**. Preview Instagram or Facebook Pages, approve or cancel simulated read-only access, retrieve sample followers/posts and disconnect. No API credentials or encryption key are needed for this preview. All demo state stays in the current UI session, resets on reload/project switch, and never enters real account records, agent context or analytics. The real connection buttons still require valid Meta configuration; placeholder strings are not live credentials.
