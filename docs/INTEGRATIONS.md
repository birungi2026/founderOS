# Integration contracts

## Authentication and organization selection

`POST /auth/register` accepts `{email, password, organization_name}`; passwords must be 12–128 characters. `POST /auth/login` accepts `{email, password}`. Both set an HttpOnly, SameSite=Lax session cookie with a 24-hour expiry. `POST /auth/logout` revokes the current token. Use `GET /auth/me` to retrieve organizations.

Send `X-Organization-ID` on every organization-scoped call. If omitted, the backend selects one of the user's memberships. Integrations should always specify it. An organization header never grants access; membership and role are checked on the server.

Owners can grant registered users `editor` or `viewer` membership via `POST /organization/members`. Viewers have read-only access. Editors manage projects, research, drafts and analytics. Only owners manage membership, see audit logs, and queue publications.

## CRM event ingestion

Use an editor account in the intended organization, sign in server-side, and retain its session cookie securely. No public unauthenticated tracking endpoint is exposed. A CRM bridge maps source events to:

```http
POST /projects/{project_id}/events
Content-Type: application/json
X-Organization-ID: organization-uuid
Cookie: founderos_session=server-side-session

{"external_id":"crm:signup:12345","kind":"signup","channel":"linkedin","campaign":"launch-2026"}
```

Supported kinds: `impression`, `lead`, `signup`, `paying_customer`. A unique `(project_id, external_id)` prevents duplicate increments. Exact replay returns `duplicate: true`; conflicting reuse returns 409. A concurrent uniqueness collision returns 409 and can be retried with the same payload. Authenticate again after session expiry; do not blindly retry other 4xx errors.

Channel and campaign are supplied by the integration; FounderOS does not infer attribution. Manual metric entries and event counts are additive. Do not submit the same outcome through both paths. CSV export provides channel totals, not personal lead information.

## Research and model generation

`POST /projects/{id}/sources` accepts `url` (HTTPS), `title`, `excerpt`, and `permission_confirmed: true`. URLs are stored, not fetched. This avoids server-side URL retrieval and preserves the distinction between operator attestation and independent verification. The latest 20 source excerpts enter the model context. The model returns steps, campaign drafts, and `citation_ids`; unknown IDs reject the entire generation.

An LLM can still make unsupported statements despite valid IDs. Operators must review content. No API key is returned in any API response or included in frontend bundles.

## Explicit publishing lifecycle

1. Generate a draft (`pending`).
2. Editor or owner approves or rejects it. Only pending drafts can be reviewed.
3. Owner explicitly queues an approved draft using `POST /drafts/{id}/publish` with `{"confirm":true}`.
4. The database snapshots the approved content and channel. Only one publication exists per draft.
5. A server operator explicitly delivers that one queued LinkedIn job with the command below.

Queueing is not delivery. The API does not run a publishing worker automatically. `GET /projects/{id}/publications` returns job status and provider reference. Outreach drafts have no sending adapter, recipient discovery, or bulk delivery.

### LinkedIn OAuth connector

Provision `LINKEDIN_CONNECTOR_JSON` in the backend secret manager with `organization_id`, `channel: "linkedin"`, `author` (a LinkedIn URN), `access_token`, and `api_version` (a supported YYYYMM LinkedIn API version). Obtain the token through your approved LinkedIn developer app with the applicable member or organization publishing scope. This release does not implement the OAuth browser handshake or token refresh. Never store this JSON in Git or pass tokens as command arguments.

```bash
cd backend
python -m app.publishing --organization ORGANIZATION_UUID --publication PUBLICATION_UUID --deliver
```

The connector is bound to one organization and channel and posts only to `https://api.linkedin.com/rest/posts`. Redirects are not followed. The approving user must still be an owner. Claims are atomic and committed before network I/O, so duplicate workers cannot publish the same job twice.

A confirmed 201 marks `sent`; a 4xx rejection marks `failed`; ambiguous responses/timeouts mark `uncertain`. A crash after claiming may leave `sending`. Neither `sending`, `uncertain`, nor `failed` jobs are automatically retried. Reconcile the provider's actual state before any manual repair. This favors avoiding duplicates and does not promise exactly-once delivery across network failures.

Tests use mocked transport. No live provider call is required to run the test suite.
