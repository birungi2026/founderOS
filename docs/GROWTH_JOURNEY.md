# Connected growth journey

The **Your growth journey** navigation item and Home action connect one full path: a private interview, transcription and editable brief, explicit brand confirmation, automatic web research and its confirmation checkpoint, a finished Tavus video, owner-approved scheduling to a Facebook Page, and observed Facebook results. This is the first supported publishing path; it does not add Instagram, TikTok or LinkedIn publishing. Existing tools and labeled demos remain separate.

## What runs

The API persists `GrowthJourney` rows and private MP4/WebM recordings. The existing worker now advances both research workflows and journeys. API and worker must share the media volume. No additional message broker is required. A recorded interview stays local until the founder explicitly agrees to upload for transcription; a separate action authorizes Tavus likeness/voice training. Training and rendering may incur provider charges.

Transcription uses OpenAI's multipart audio transcription API. A configured compatible language model extracts an editable brief from explicit transcript facts; unknown facts stay blank. No facial-personality or accent inference is performed. Confirming the review creates and approves a new versioned brand and company brief, with optimistic version checks. Research uses the existing Brave integration and stops for source/fact confirmation before the existing agents create the script and caption.

Tavus training uses `POST /v2/faces` with `model_name=phoenix-4`. The resulting `face_id` is passed as `replica_id` to the documented video-generation endpoint; Tavus documents these as the same resource. The founder reviews the returned downloadable video, edits the caption if needed, and explicitly approves the exact video ID, caption, Facebook Page and posting time. Script edits discard the old video reference and require a new render. Caption edits require another approval. Scheduled content cannot be edited without cancellation.

Rymu posts the approved video when its worker reaches the due time. A fresh Tavus download URL is fetched for the approved video ID at delivery, since signed asset URLs can expire. Facebook upload acceptance is labeled separately from completed video processing. Measurements are the latest returned likes/comments and processing status, with observation time and an available permalink. Missing counts stay missing. Refreshes replace snapshots rather than add totals. Leads, purchases and causal attribution are not inferred from engagement; the existing customer tracker remains separate.

## Provisioning

Configure the existing `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `GENERATION_MODE=llm` and `BRAVE_SEARCH_API_KEY`, plus:

- `TRANSCRIPTION_API_KEY` and optional `TRANSCRIPTION_MODEL` (default `gpt-4o-mini-transcribe`).
- `TAVUS_API_KEY` with face training and recorded-video generation enabled for the account.
- `PUBLIC_API_URL`, a reachable HTTPS API origin such as `https://api.rymu.ai`.
- `JOURNEY_MEDIA_SIGNING_KEY`, a random secret of at least 32 characters. Signed training links expire after 24 hours, are scoped to one recording and require recorded clone consent. Treat the links as temporary bearer credentials; redact query strings in ingress/proxy logs.
- `JOURNEY_ENABLED_ORGANIZATIONS`, a comma-separated allowlist of organization IDs from `/auth/me`. This keeps public signup from automatically enabling paid provider jobs before billing/entitlements exist. `*` is only appropriate for isolated tests or explicitly controlled deployments.
- `JOURNEY_PUBLISHING_ENABLED=true` only when live delivery is intended. This also adds `pages_manage_posts` to newly requested Facebook OAuth permissions. Existing connections need reauthorization for that scope; read-only connections are never silently upgraded.
- Existing Facebook app credentials, exact callback URI and `SOCIAL_TOKEN_ENCRYPTION_KEY`. The founder must connect an eligible Facebook Page with `pages_manage_posts` and `pages_read_engagement`. App Review/access requirements remain Meta's responsibility to approve.

Compose mounts `journey-media` at `/app/media` in API and worker. Include that volume in backups. Standalone deployments must set `JOURNEY_MEDIA_DIR` to a shared private persistent directory; the development fallback is `/tmp/rymu-media`. Do not expose the directory as a static website.

Limits default to 30 processed interviews, one trained replica and ten render submissions per organization per UTC calendar month, plus three lifetime render attempts per journey. They are conservative operator limits, not implemented subscription/billing entitlements or generated-minute quotas. They reserve attempts rather than refund uncertain provider requests. Configure them deliberately after measuring costs. Recordings are limited to 25 MB, and no more than 30 stored interview files per project. Local deletion frees file storage but preserves the row for quota/audit history. It removes the recording/transcript from Rymu, not approved brand information or Tavus's remote face/video resources. Remote deletion/retention must be managed with Tavus under the account agreement.

## Failure handling

All mutations require an owner and project/organization access. State/revision checks reject stale decisions. Durable SQL claims precede provider writes. Charged training/render requests and publishing are not automatically replayed after an uncertain response or worker crash. An administrator must inspect Tavus/Meta before any deliberate replacement request. Training uses a journey-specific name for reconciliation. Interrupted read-only polls can resume; failed polls do not fabricate successful metrics. Provider/token/prompt bodies are not persisted in public error messages.

Disconnecting an account, token expiry, removing publishing permission, disabling delivery, removing an approving owner or disabling a provisioned organization prevents a queued post from being delivered. Cancellation competes atomically with the worker claim; once delivery is in progress cancellation is refused. A post more than one hour late is marked missed, rather than sent in a catch-up burst. Scheduling supports an explicit device-local datetime converted to an absolute UTC timestamp, one minute to 30 days ahead. Posting requires the worker to stay running and is not an exact-second delivery SLA.

## Verification and current limits

Tests exercise the real database, approval checkpoints, automatic research workflow, durable job processing, rendering states, scheduled publishing and measurement replacement with deterministic external-provider fixtures. Separate HTTP contract tests check transcription, model, Tavus and Meta request/response shapes; browser tests cover the connected screens and disabled approval gates with explicit fixtures. Those tests do not establish live provider account eligibility, footage quality, API app approval, playback quality, accent fidelity or actual reach/customers.

A live acceptance run still requires provisioned keys, an HTTPS API reachable by Tavus, compliant founder footage and an authorized Facebook Page. Use a test Page first, approve one video for a future time, verify the real provider IDs/permalink, and compare observed engagement with Meta. No live external video or social post is sent by the automated test suite. An interview may need rerecording to meet Tavus's 1080p/30-second footage requirements; a browser/device's recording support is not proof of provider acceptance. Automatic editing, burned-in captions, background footage, other-channel delivery, billing and automatic purchase attribution are outside this first journey.

## Provider contracts

- [OpenAI transcription guide](https://platform.openai.com/docs/guides/speech-to-text)
- [Tavus Create Face](https://docs.tavus.io/api-reference/faces/create-face)
- [Tavus Generate Video](https://docs.tavus.io/api-reference/video-request/create-video)
- [Tavus Get Video](https://docs.tavus.io/api-reference/video-request/get-video)
- [Meta Page videos](https://developers.facebook.com/docs/graph-api/reference/page/videos/)
