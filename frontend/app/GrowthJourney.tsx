"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { API, api } from "./api";
import JourneyResearch from "./JourneyResearch";
import JourneyRecorder from "./JourneyRecorder";

type Brief = {
  founder_name: string;
  story: string;
  expertise: string[];
  voice: string;
  positioning: string;
  content_pillars: string[];
  problem: string;
  solution: string;
  target_customers: string;
  differentiator: string;
};
type Journey = {
  created_at: string;
  interview_available?: boolean;
  can_reuse_replica?: boolean;
  trained_at?: number;
  id: string;
  status: string;
  revision: number;
  error_code?: string;
  transcript?: string;
  brief?: Brief;
  script?: string;
  caption?: string;
  replica_id?: string;
  video_url?: string;
  generation_mode?: string;
  observed_at?: number;
  results?: {
    processing_status: string;
    permalink?: string;
    metrics: Record<string, number>;
  };
  publication?: { publish_at: number };
  workflow?: {
    status: string;
    research_review_hash: string;
    sources: { id: string; title: string; url: string; excerpt?: string }[];
    steps: { agent: string; artifact: Record<string, unknown> }[];
  };
};
const labels: Record<string, string> = {
  interview_uploaded: "Interview saved. Waiting to transcribe.",
  transcribing: "Listening to your interview…",
  interview_review: "Check what Rymu learned about you.",
  brand_confirmed: "Your brand is confirmed. Ready for research.",
  researching: "Research and content preparation are in progress.",
  checking_research: "Checking the research…",
  content_review: "Review your script and caption.",
  training_queued: "Your Tavus training request is queued.",
  training_request: "Submitting training to Tavus…",
  training: "Tavus is learning your appearance and voice.",
  checking_training: "Checking Tavus training…",
  render_queued: "Your video is queued for generation.",
  render_request: "Requesting your video from Tavus…",
  rendering: "Tavus is making your video.",
  checking_video: "Checking your video…",
  video_ready: "Watch your video before approving it.",
  scheduled: "Approved and scheduled.",
  publishing: "Sending your approved video to Facebook…",
  posted: "Facebook accepted the upload. Processing may still be in progress.",
  measuring: "Checking Facebook processing and engagement…",
  measured: "Your latest Facebook results are available.",
  uncertain:
    "A provider request could not be confirmed. Do not submit it again until an administrator checks the provider dashboard.",
  failed:
    "This journey stopped. Review the setup and provider status before starting again.",
  access_revoked:
    "This journey stopped because account access or publishing permission is unavailable.",
  missed:
    "The posting time was missed by more than an hour. Nothing was posted automatically.",
};
const reviewFields: [keyof Brief, string][] = [
  ["founder_name", "Your name"],
  ["story", "Your story"],
  ["expertise", "What do you know well?"],
  ["voice", "How should Rymu write your posts?"],
  ["positioning", "Who do you help, and how?"],
  ["content_pillars", "What topics should Rymu post about?"],
  ["problem", "What problem do you solve?"],
  ["solution", "How do you solve it?"],
  ["target_customers", "Who is it for?"],
  ["differentiator", "What makes your approach different?"],
];
const setupLabels: Record<string, string> = {
  workspace_enabled: "Workspace activation",
  transcription: "Interview transcription",
  model: "AI writing",
  research: "Web research",
  video: "Tavus video",
  training: "Secure training link",
  publishing: "Facebook publishing",
};
const split = (value: string) =>
  value
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
export default function GrowthJourney({
  orgId,
  projectId,
  isOwner,
}: {
  orgId: string;
  projectId: string;
  isOwner: boolean;
}) {
  const [journeys, setJourneys] = useState<Journey[]>([]),
    [journey, setJourney] = useState<Journey | null>(null);
  const [capabilities, setCapabilities] = useState<Record<string, boolean>>({}),
    [accounts, setAccounts] = useState<
      {
        id: string;
        name: string;
        permissions: string[];
        provider: string;
        status: string;
      }[]
    >([]);
  const [file, setFile] = useState<File | null>(null),
    [consent, setConsent] = useState(false),
    [cloneConsent, setCloneConsent] = useState(false),
    [approve, setApprove] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({}),
    [brandBase, setBrandBase] = useState<string | null>(null),
    [companyVersion, setCompanyVersion] = useState(0);
  const [script, setScript] = useState(""),
    [caption, setCaption] = useState(""),
    [goal, setGoal] = useState(
      "Find the right audience and turn useful content into qualified customer conversations.",
    );
  const [account, setAccount] = useState(""),
    [when, setWhen] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false);
  const [hasBrand, setHasBrand] = useState(false),
    [replicaSource, setReplicaSource] = useState("");
  const [contextReady, setContextReady] = useState(false);
  const [capturing, setCapturing] = useState(false),
    [previewUrl, setPreviewUrl] = useState("");
  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  const selected = useRef(""),
    initialized = useRef(""),
    contentInitialized = useRef("");
  const root = `/v1/projects/${projectId}/journeys`;
  async function refresh() {
    const list = await api(root, orgId);
    setJourneys(list.journeys);
    setHasBrand(!!list.has_approved_brand);
    setCapabilities(list.capabilities);
    const id = selected.current || list.journeys[0]?.id;
    if (id) {
      selected.current = id;
      const detail = await api(root + "/" + id, orgId);
      if (selected.current === id) setJourney(detail);
    }
    setLoaded(true);
  }
  useEffect(() => {
    let active = true,
      inFlight = false;
    const load = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        if (active) await refresh();
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Could not load your journey",
          );
      } finally {
        inFlight = false;
      }
    };
    void load();
    void Promise.all([
      api(`/v1/projects/${projectId}/social`, orgId),
      api(`/v1/projects/${projectId}/brand`, orgId),
      api(`/v1/projects/${projectId}/company`, orgId),
    ])
      .then(([social, brand, company]) => {
        if (active) {
          setAccounts(social.accounts);
          setBrandBase(brand.latest?.id || null);
          setCompanyVersion(company.version || 0);
        }
      })
      .catch(() => {
        if (active)
          setError(
            "Could not load account and brand setup. Refresh this page before continuing.",
          );
      });
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [orgId, projectId]);
  useEffect(() => {
    if (
      journey?.brief &&
      journey.status === "interview_review" &&
      initialized.current !== journey.id
    ) {
      setDraft(
        Object.fromEntries(
          Object.entries(journey.brief).map(([key, value]) => [
            key,
            Array.isArray(value) ? value.join("\n") : value,
          ]),
        ),
      );
      initialized.current = journey.id;
      setContextReady(false);
      void Promise.all([
        api(`/v1/projects/${projectId}/brand`, orgId),
        api(`/v1/projects/${projectId}/company`, orgId),
      ])
        .then(([brand, company]) => {
          setBrandBase(brand.latest?.id || null);
          setCompanyVersion(company.version || 0);
          setContextReady(true);
        })
        .catch(() =>
          setError(
            "Could not load your current brand. Refresh before confirming.",
          ),
        );
    }
    if (
      journey?.script &&
      ["content_review", "video_ready"].includes(journey.status) &&
      contentInitialized.current !== journey.id
    ) {
      setScript(journey.script);
      setCaption(journey.caption || "");
      contentInitialized.current = journey.id;
    }
  }, [journey]);
  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
      await refresh();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Something went wrong. Refresh and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  function post(path: string, values: Record<string, unknown> = {}) {
    return api(root + "/" + journey!.id + "/" + path, orgId, {
      revision: journey!.revision,
      ...values,
    });
  }
  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !consent) return;
    await action(async () => {
      if (file.size > 25 * 1024 * 1024)
        throw new Error("Choose a video no larger than 25 MB.");
      const response = await fetch(API + root + "/interview?consent=yes", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": file.type.split(";")[0],
          "X-Organization-ID": orgId,
        },
        body: file,
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          result.detail || "Upload failed. Your file is still on your device.",
        );
      selected.current = result.id;
      setCloneConsent(false);
      setApprove(false);
      setConsent(false);
      initialized.current = "";
      contentInitialized.current = "";
      setFile(null);
    });
  }
  const wf = journey?.workflow;
  const captionDirty =
    script !== journey?.script || caption !== journey?.caption;
  return (
    <section
      className="panel growth-journey"
      aria-label="Create and schedule a video"
    >
      <span className="eyebrow">FROM YOUR STORY TO YOUR NEXT CUSTOMER</span>
      <h2>Create and schedule a video</h2>
      <p>Interview → brand → research → video → approval → results.</p>
      <p>Schedule Facebook Page videos here. Provider setup is required.</p>
      {!isOwner && (
        <p>
          Only owners can upload, confirm or schedule. You have view access.
        </p>
      )}
      {!loaded && <p role="status">Loading your journey…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {Object.values(capabilities).some((value) => !value) && (
        <details className="journey-setup">
          <summary>Provider setup needed</summary>
          {Object.entries(capabilities).map(([name, ready]) => (
            <p key={name}>
              {setupLabels[name] || name}:{" "}
              {ready ? "Ready" : "Needs administrator setup"}
            </p>
          ))}
        </details>
      )}
      <details open={!journey}>
        <summary>1. Record or upload your interview</summary>
        <p>
          Share your story, audience, offer and topics. Speak in your natural
          style.
        </p>
        <p>
          MP4 or WebM, up to 25 MB. Uploading sends your video to transcription
          and AI providers with your consent.
        </p>
        <JourneyRecorder
          disabled={busy || !isOwner}
          onReady={setFile}
          onActive={setCapturing}
        />
        {file && (
          <p role="status">
            Ready to upload: {file.name} ({(file.size / 1024 / 1024).toFixed(1)}{" "}
            MB)
          </p>
        )}
        {previewUrl && (
          <video
            controls
            playsInline
            preload="metadata"
            src={previewUrl}
            style={{ width: "100%", maxHeight: 320 }}
          />
        )}
        <form onSubmit={upload}>
          <fieldset disabled={busy || !isOwner}>
            <label>
              Interview video
              <input
                type="file"
                accept="video/mp4,video/webm"
                capture="user"
                disabled={capturing}
                required={!file}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                required
              />
              I agree to send this interview for transcription and a draft brand
              brief.
            </label>
            <button
              disabled={
                !file ||
                capturing ||
                !consent ||
                !capabilities.workspace_enabled ||
                !capabilities.transcription ||
                !capabilities.model
              }
            >
              {busy ? "Uploading…" : "Upload interview and prepare my brief"}
            </button>
          </fieldset>
        </form>
      </details>
      {hasBrand && (
        <button
          className="secondary"
          disabled={busy || !isOwner || !capabilities.workspace_enabled}
          onClick={() =>
            void action(async () => {
              const row = await api(root + "/from-brand", orgId, {});
              selected.current = row.id;
              initialized.current = "";
              contentInitialized.current = "";
              setCloneConsent(false);
              setApprove(false);
              setReplicaSource("");
            })
          }
        >
          Create another post with my confirmed brand
        </button>
      )}
      {!!journeys.length && (
        <label>
          Saved journeys
          <select
            value={journey?.id || ""}
            onChange={(e) => {
              selected.current = e.target.value;
              initialized.current = "";
              contentInitialized.current = "";
              setApprove(false);
              setCloneConsent(false);
              void action(refresh);
            }}
          >
            {journeys.map((row) => (
              <option key={row.id} value={row.id}>
                {new Date(row.created_at).toLocaleString()} ·{" "}
                {row.status.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </label>
      )}
      {journey && (
        <>
          <p className="notice" role="status">
            {labels[journey.status] || journey.status.replaceAll("_", " ")}
          </p>
          {journey.error_code && (
            <p className="error">{journey.error_code.replaceAll("_", " ")}</p>
          )}
          {journey.status === "interview_review" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  const brand = {
                    founder_name: draft.founder_name,
                    story: draft.story,
                    expertise: split(draft.expertise || ""),
                    voice: draft.voice,
                    positioning: draft.positioning,
                    content_pillars: split(draft.content_pillars || ""),
                    proof_points: [],
                    avoid_topics: [],
                    base_version_id: brandBase,
                  };
                  await post("confirm-brand", {
                    brand,
                    company: {
                      problem: draft.problem,
                      solution: draft.solution,
                      target_customers: draft.target_customers,
                      differentiator: draft.differentiator || "",
                      competitors: [],
                      expected_version: companyVersion,
                    },
                  });
                });
              }}
            >
              <h3>2. Check and confirm your brand</h3>
              <details>
                <summary>Read your interview transcript</summary>
                <p className="journey-transcript">{journey.transcript}</p>
              </details>
              <p>
                Check the details before confirming. Rymu uses this approved
                brand; it does not infer personality or accent from your face.
              </p>
              <fieldset disabled={busy || !isOwner}>
                {reviewFields.map(([key, label]) => (
                  <label key={key}>
                    {label}
                    {(key === "expertise" || key === "content_pillars") &&
                      " (one per line)"}
                    <textarea
                      value={draft[key] || ""}
                      required={!["differentiator", "problem"].includes(key)}
                      onChange={(e) =>
                        setDraft({ ...draft, [key]: e.target.value })
                      }
                    />
                  </label>
                ))}
                <button disabled={!contextReady}>Confirm my brand</button>
              </fieldset>
            </form>
          )}
          {journey.status === "brand_confirmed" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(() => post("research", { goal }));
              }}
            >
              <h3>3. Let Rymu research</h3>
              <label>
                What should this content help you achieve?
                <textarea
                  required
                  minLength={10}
                  maxLength={1000}
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                />
              </label>
              <button
                disabled={
                  busy ||
                  !isOwner ||
                  !capabilities.research ||
                  !capabilities.workspace_enabled
                }
              >
                Start automatic research
              </button>
            </form>
          )}
          {wf?.status === "research_review" && (
            <div>
              <h3>Confirm what Rymu found</h3>
              <p>
                Check the sources, audience fit and uncertainties before Rymu
                writes the content.
              </p>
              {wf.sources.map((source) => (
                <p key={source.id}>
                  <a href={source.url} target="_blank" rel="noreferrer">
                    {source.title}
                  </a>
                </p>
              ))}
              {wf.steps
                .filter((step) => step.agent === "research")
                .map((step) => (
                  <JourneyResearch
                    key={step.agent}
                    artifact={step.artifact}
                    sources={wf.sources}
                  />
                ))}
              <button
                disabled={busy || !isOwner}
                onClick={() =>
                  void action(() =>
                    post("confirm-research", {
                      research_hash: wf.research_review_hash,
                    }),
                  )
                }
              >
                Confirm research and prepare content
              </button>
            </div>
          )}
          {["content_review", "video_ready"].includes(journey.status) && (
            <div>
              <h3>4. Review your content</h3>
              <p>
                Generation: {journey.generation_mode}. Review every claim before
                making or posting the video.
              </p>
              <fieldset disabled={busy || !isOwner}>
                <label>
                  Video script
                  <textarea
                    minLength={20}
                    maxLength={1200}
                    value={script}
                    onChange={(e) => {
                      setScript(e.target.value);
                      setApprove(false);
                    }}
                  />
                </label>
                <label>
                  Post caption
                  <textarea
                    minLength={10}
                    maxLength={2000}
                    value={caption}
                    onChange={(e) => {
                      setCaption(e.target.value);
                      setApprove(false);
                    }}
                  />
                </label>
                <button
                  className="secondary"
                  disabled={!captionDirty}
                  onClick={() =>
                    void action(() => post("content", { script, caption }))
                  }
                >
                  Save content changes
                </button>
                {journey.status === "content_review" && !journey.replica_id && (
                  <>
                    <p>
                      Paid Tavus training needs at least 30 seconds of
                      continuous 1080p video, a visible face and clear speech.
                      Provider consent and footage rules apply.
                    </p>
                    <label className="check">
                      <input
                        type="checkbox"
                        checked={cloneConsent}
                        onChange={(e) => setCloneConsent(e.target.checked)}
                      />
                      {replicaSource
                        ? "This is my existing likeness and voice. I authorize its use in this video."
                        : "This is my likeness and voice. I authorize Tavus to use this recording to create my video replica."}
                    </label>
                    {!!journeys.filter(
                      (item) =>
                        item.can_reuse_replica && item.id !== journey.id,
                    ).length && (
                      <>
                        <label>
                          Or use your existing Tavus replica
                          <select
                            aria-label="Existing Tavus replica"
                            value={replicaSource}
                            onChange={(e) => {
                              setReplicaSource(e.target.value);
                              setCloneConsent(false);
                            }}
                          >
                            <option value="">
                              Choose your earlier training
                            </option>
                            {journeys
                              .filter(
                                (item) =>
                                  item.can_reuse_replica &&
                                  item.id !== journey.id,
                              )
                              .map((item) => (
                                <option key={item.id} value={item.id}>
                                  {new Date(item.created_at).toLocaleString()}
                                </option>
                              ))}
                          </select>
                        </label>
                        <button
                          disabled={!replicaSource || !cloneConsent}
                          onClick={() =>
                            void action(() =>
                              post("reuse-replica", {
                                source_journey_id: replicaSource,
                                consent: true,
                              }),
                            )
                          }
                        >
                          Use my existing replica for this video
                        </button>
                      </>
                    )}
                    <button
                      disabled={
                        !cloneConsent ||
                        captionDirty ||
                        !capabilities.video ||
                        !capabilities.training ||
                        !!replicaSource ||
                        !journey.interview_available ||
                        !capabilities.workspace_enabled
                      }
                      onClick={() =>
                        void action(() =>
                          post("train", { consent: cloneConsent }),
                        )
                      }
                    >
                      Create my Tavus replica
                    </button>
                  </>
                )}
                {journey.status === "content_review" && journey.replica_id && (
                  <button
                    disabled={
                      captionDirty ||
                      !capabilities.video ||
                      !capabilities.workspace_enabled
                    }
                    onClick={() => void action(() => post("render"))}
                  >
                    Generate my video with Tavus
                  </button>
                )}
              </fieldset>
            </div>
          )}
          {journey.video_url && (
            <div>
              <h3>Your finished video</h3>
              <video
                controls
                preload="metadata"
                src={journey.video_url}
                style={{ width: "100%", maxHeight: 480 }}
              />
              <a href={journey.video_url} target="_blank" rel="noreferrer">
                Open video file
              </a>
            </div>
          )}
          {journey.status === "video_ready" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(() =>
                  post("schedule", {
                    account_id: account,
                    publish_at: new Date(when).toISOString(),
                    approve,
                  }),
                );
              }}
            >
              <h3>5. Approve and schedule</h3>
              <p>Approve this video, caption, Page and time before posting.</p>
              <fieldset disabled={busy || !isOwner}>
                <label>
                  Facebook Page
                  <select
                    aria-label="Facebook Page"
                    required
                    value={account}
                    onChange={(e) => {
                      setAccount(e.target.value);
                      setApprove(false);
                    }}
                  >
                    <option value="">Choose a connected Page</option>
                    {accounts
                      .filter(
                        (a) =>
                          a.provider === "facebook" &&
                          a.status === "connected" &&
                          a.permissions.includes("pages_manage_posts"),
                      )
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  When should this video be posted?
                  <input
                    type="datetime-local"
                    required
                    value={when}
                    onChange={(e) => {
                      setWhen(e.target.value);
                      setApprove(false);
                    }}
                  />
                </label>
                <p>
                  Your device timezone:{" "}
                  {Intl.DateTimeFormat().resolvedOptions().timeZone}. Choose at
                  least one minute from now.
                </p>
                <label className="check">
                  <input
                    type="checkbox"
                    required
                    checked={approve}
                    onChange={(e) => setApprove(e.target.checked)}
                  />
                  I watched the video and approve this caption, Page and posting
                  time.
                </label>
                <button
                  disabled={
                    !approve ||
                    !when ||
                    !account ||
                    captionDirty ||
                    !capabilities.publishing ||
                    !capabilities.workspace_enabled
                  }
                >
                  Approve and schedule this post
                </button>
              </fieldset>
            </form>
          )}
          {journey.status === "scheduled" && (
            <div>
              <p>
                Posting time:{" "}
                {new Date(
                  journey.publication!.publish_at * 1000,
                ).toLocaleString()}
                .
              </p>
              <button
                className="secondary"
                disabled={busy || !isOwner}
                onClick={() => {
                  setApprove(false);
                  void action(() => post("cancel"));
                }}
              >
                Cancel scheduled post
              </button>
            </div>
          )}
          {journey.interview_available &&
            [
              "interview_review",
              "brand_confirmed",
              "content_review",
              "video_ready",
              "failed",
              "uncertain",
              "posted",
              "measured",
              "access_revoked",
              "missed",
            ].includes(journey.status) && (
              <details>
                <summary>Remove the stored interview</summary>
                <p>
                  Permanently deletes your Rymu recording and transcript. Your
                  approved brand and Tavus assets remain.
                </p>
                <button
                  className="secondary"
                  disabled={busy || !isOwner}
                  onClick={() => void action(() => post("delete-interview"))}
                >
                  Delete stored interview and transcript
                </button>
              </details>
            )}
          {journey.results && (
            <div>
              <h3>6. Measured results</h3>
              <p>
                Facebook processing: {journey.results.processing_status}.
                Observed{" "}
                {new Date((journey.observed_at || 0) * 1000).toLocaleString()}.
              </p>
              {Object.entries(journey.results.metrics).map(
                ([metric, value]) => (
                  <p key={metric}>
                    {metric}: <strong>{value}</strong>
                  </p>
                ),
              )}
              {!Object.keys(journey.results.metrics).length && (
                <p>
                  Facebook has not returned engagement counts. Missing metrics
                  are not counted as zero.
                </p>
              )}
              {journey.results.permalink && (
                <a
                  href={journey.results.permalink}
                  target="_blank"
                  rel="noreferrer"
                >
                  View on Facebook
                </a>
              )}
              <p>
                Latest engagement counts. Leads and customers are tracked
                separately in Results.
              </p>
            </div>
          )}
        </>
      )}
      <button
        className="secondary"
        disabled={busy}
        onClick={() => void action(refresh)}
      >
        Refresh journey status
      </button>
    </section>
  );
}
