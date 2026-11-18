"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "./api";

type BrandData = {
  founder_name: string;
  website_url: string | null;
  story: string;
  expertise: string[];
  voice: string;
  positioning: string;
  content_pillars: string[];
  proof_points: string[];
  avoid_topics: string[];
};
type Brand = {
  id: string;
  version: number;
  status: string;
  data: BrandData;
  created_at: string;
};
type Research = {
  opportunities: {
    angle: string;
    audience_fit: string;
    evidence_ids: string[];
    uncertainty: string;
  }[];
};
type Growth = { objective: string; experiment: string; success_metric: string };
type Video = {
  title: string;
  hook: string;
  scenes: {
    duration_seconds: number;
    narration: string;
    caption: string;
    visual: string;
  }[];
  call_to_action: string;
};
type Launch = { message: string };
type Step = {
  agent: string;
  artifact: Record<string, unknown>;
  generation_mode: string;
  usage: { model_calls: number; total_tokens?: number };
};
type Run = {
  id: string;
  status: string;
  progress: number;
  goal: string;
  generation_mode: string;
  error_code: string | null;
  brand_version?: number;
  steps?: Step[];
  sources?: { id: string; title: string; url: string; observed_at: string }[];
  performance_baseline?: { totals: Record<string, number> };
  tasks?: {
    id: string;
    title: string;
    phase: string;
    due_date: string;
    completed: boolean;
  }[];
};
type CalendarDraft = {
  id: string;
  content: string;
  status: string;
  channel: string;
  revision_hash: string;
  revision_number: number;
  generation: {
    run_id?: string;
    title?: string;
    planned_date?: string;
    hypothesis?: string;
  };
};
const agentNames = [
  ["personal_brand", "Personal Brand"],
  ["research", "Viral Research"],
  ["growth", "Founder Growth"],
  ["video", "Video Creator"],
  ["launch", "Product Launch"],
];
const emptyBrand: BrandData = {
  founder_name: "",
  website_url: null,
  story: "",
  expertise: [],
  voice: "",
  positioning: "",
  content_pillars: [],
  proof_points: [],
  avoid_topics: [],
};
const lines = (value: string) =>
  value
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
const dateAfter = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

function CalendarCard({
  draft,
  orgId,
  canWrite,
  changed,
}: {
  draft: CalendarDraft;
  orgId: string;
  canWrite: boolean;
  changed: () => Promise<void>;
}) {
  const [content, setContent] = useState(draft.content),
    [date, setDate] = useState(draft.generation.planned_date || ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/v1/content/${draft.id}/revisions`, orgId, {
        expected_hash: draft.revision_hash,
        content,
        planned_date: date,
      });
      await changed();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  const editable =
    canWrite && ["pending", "approved", "rejected"].includes(draft.status);
  return (
    <article className="calendar-card">
      <span className="eyebrow">
        {draft.generation.planned_date} / {draft.channel}
      </span>
      <h3>{draft.generation.title}</h3>
      <span className="tag">
        {draft.status} · revision {draft.revision_number}
      </span>
      <p>{draft.generation.hypothesis}</p>
      {editable ? (
        <form onSubmit={save}>
          <fieldset disabled={busy}>
            <label>
              Planned content date
              <input
                type="date"
                value={date}
                required
                onChange={(e) => setDate(e.target.value)}
              />
            </label>
            <label>
              Content draft
              <textarea
                minLength={10}
                maxLength={6000}
                required
                aria-label="Content draft"
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </label>
            <button>Save new revision</button>
            <small>
              Saving requires a fresh review. Planned dates do not schedule
              publishing.
            </small>
          </fieldset>
        </form>
      ) : (
        <p className="copy">{draft.content}</p>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </article>
  );
}

export default function GrowthTeam({
  orgId,
  projectId,
  canWrite,
  sourceCount,
  onComplete,
}: {
  orgId: string;
  projectId: string;
  canWrite: boolean;
  sourceCount: number;
  onComplete: () => Promise<void>;
}) {
  const [brand, setBrand] = useState<Brand | null>(null),
    [versions, setVersions] = useState<Brand[]>([]),
    [form, setForm] = useState<BrandData>(emptyBrand);
  const [runs, setRuns] = useState<Run[]>([]),
    [run, setRun] = useState<Run | null>(null),
    [drafts, setDrafts] = useState<CalendarDraft[]>([]);
  const [goal, setGoal] = useState(
      "Build a useful weekly content campaign and learn which messages resonate.",
    ),
    [weekStart, setWeekStart] = useState(dateAfter(0)),
    [launchDate, setLaunchDate] = useState(dateAfter(14));
  const [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [tab, setTab] = useState("growth"),
    [usage, setUsage] = useState({ workflow_runs: 0, limit: 20 }),
    [generationMode, setGenerationMode] = useState("");
  const completed = useRef(onComplete);
  completed.current = onComplete;
  const [historyVersion, setHistoryVersion] = useState("");
  const inspection = versions.find((v) => v.id === historyVersion);
  async function loadRun(id: string) {
    const r = await api(`/v1/workflows/${id}`, orgId);
    setRun(r);
    setDrafts(
      (await api(`/projects/${projectId}/drafts`, orgId)).drafts.filter(
        (d: CalendarDraft) => d.generation.run_id === id,
      ),
    );
  }
  useEffect(() => {
    let active = true;
    Promise.all([
      api(`/v1/projects/${projectId}/brand`, orgId),
      api(`/v1/projects/${projectId}/workflows`, orgId),
      api("/v1/usage", orgId),
      api("/v1/agents", orgId),
    ])
      .then(async ([b, w, u, a]) => {
        if (!active) return;
        setBrand(b.latest);
        setVersions(b.versions);
        setForm(b.latest?.data || emptyBrand);
        setRuns(w.runs);
        setUsage(u);
        setGenerationMode(a.generation_mode);
        if (w.runs[0]) {
          const r = await api(`/v1/workflows/${w.runs[0].id}`, orgId);
          const d = await api(`/projects/${projectId}/drafts`, orgId);
          if (active) {
            setRun(r);
            setDrafts(
              d.drafts.filter(
                (draft: CalendarDraft) => draft.generation.run_id === r.id,
              ),
            );
          }
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId, orgId]);
  useEffect(() => {
    if (!run || !["queued", "running"].includes(run.status)) return;
    let active = true,
      inFlight = false;
    const timer = window.setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const current = await api(`/v1/workflows/${run.id}`, orgId);
        if (!active) return;
        setRun(current);
        if (!["queued", "running"].includes(current.status)) {
          setRuns(
            (await api(`/v1/projects/${projectId}/workflows`, orgId)).runs,
          );
          if (current.status === "needs_review") {
            setDrafts(
              (await api(`/projects/${projectId}/drafts`, orgId)).drafts.filter(
                (d: CalendarDraft) => d.generation.run_id === current.id,
              ),
            );
            await completed.current();
          }
        }
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Could not refresh workflow",
          );
      } finally {
        inFlight = false;
      }
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [run?.id, run?.status, projectId, orgId]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  async function refreshBrand() {
    const b = await api(`/v1/projects/${projectId}/brand`, orgId);
    setBrand(b.latest);
    setVersions(b.versions);
    setForm(b.latest.data);
  }
  async function saveBrand(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      await api(`/v1/projects/${projectId}/brand`, orgId, {
        ...form,
        expertise: lines(form.expertise.join("\n")),
        content_pillars: lines(form.content_pillars.join("\n")),
        proof_points: lines(form.proof_points.join("\n")),
        avoid_topics: lines(form.avoid_topics.join("\n")),
        website_url: form.website_url || null,
        base_version_id: brand?.id || null,
      });
      await refreshBrand();
      setNotice(
        "Brand version saved. Review it, then approve it for the growth team.",
      );
    });
  }
  async function queue(e: FormEvent) {
    e.preventDefault();
    await action(async () => {
      const queued = await api(
        `/v1/projects/${projectId}/workflows`,
        orgId,
        { goal, week_start: weekStart, launch_date: launchDate },
        { "Idempotency-Key": crypto.randomUUID() },
      );
      await loadRun(queued.id);
      setRuns((await api(`/v1/projects/${projectId}/workflows`, orgId)).runs);
      setUsage(await api("/v1/usage", orgId));
    });
  }
  async function refreshContent() {
    if (run) await loadRun(run.id);
    await completed.current();
  }
  async function toggleTask(taskId: string, checked: boolean) {
    if (!run) return;
    const previous = run;
    setRun((current) =>
      current
        ? {
            ...current,
            tasks: current.tasks?.map((task) =>
              task.id === taskId ? { ...task, completed: checked } : task,
            ),
          }
        : current,
    );
    await action(async () => {
      try {
        await api(`/v1/launch-tasks/${taskId}`, orgId, { completed: checked });
        await loadRun(previous.id);
      } catch (error) {
        setRun(previous);
        throw error;
      }
    });
  }
  const activeRun = run && ["queued", "running"].includes(run.status);
  const artifact = (agent: string) =>
    run?.steps?.find((s) => s.agent === agent)?.artifact;
  const research = artifact("research") as Research | undefined,
    growth = artifact("growth") as Growth | undefined,
    video = artifact("video") as Video | undefined,
    launch = artifact("launch") as Launch | undefined;
  if (loading)
    return (
      <section className="panel">
        <p>Loading your founder workspace…</p>
      </section>
    );
  return (
    <div className="growth-team">
      <section className="panel brand-studio">
        <span className="eyebrow">PERSONAL BRAND STUDIO</span>
        <h2>Teach your growth team who you are.</h2>
        <p>
          Your story, expertise and voice become shared context for every agent.
          Website links are saved as references; no website import is performed.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        {brand && (
          <p className="memory-status">
            <span className="tag">
              Version {brand.version} · {brand.status}
            </span>{" "}
            {brand.status === "approved"
              ? "Ready for agent workflows"
              : "Needs your review before use"}
          </p>
        )}
        <form onSubmit={saveBrand}>
          <fieldset disabled={busy || !canWrite}>
            <div className="grid">
              <label>
                Founder name
                <input
                  required
                  minLength={2}
                  maxLength={100}
                  value={form.founder_name}
                  onChange={(e) =>
                    setForm({ ...form, founder_name: e.target.value })
                  }
                />
              </label>
              <label>
                Product website (optional)
                <input
                  type="url"
                  value={form.website_url || ""}
                  onChange={(e) =>
                    setForm({ ...form, website_url: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              Your founder story
              <textarea
                required
                minLength={20}
                maxLength={4000}
                placeholder="Why did you start? What have you personally learned?"
                aria-label="Your founder story"
                value={form.story}
                onChange={(e) => setForm({ ...form, story: e.target.value })}
              />
            </label>
            <div className="grid">
              <label>
                Your expertise (one per line)
                <textarea
                  required
                  aria-label="Your expertise (one per line)"
                  value={form.expertise.join("\n")}
                  onChange={(e) =>
                    setForm({ ...form, expertise: e.target.value.split("\n") })
                  }
                  onBlur={() =>
                    setForm((f) => ({
                      ...f,
                      expertise: lines(f.expertise.join("\n")),
                    }))
                  }
                />
              </label>
              <label>
                Content pillars (one per line, up to five)
                <textarea
                  required
                  aria-label="Content pillars (one per line, up to five)"
                  value={form.content_pillars.join("\n")}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      content_pillars: e.target.value.split("\n"),
                    })
                  }
                  onBlur={() =>
                    setForm((f) => ({
                      ...f,
                      content_pillars: lines(f.content_pillars.join("\n")),
                    }))
                  }
                />
              </label>
            </div>
            <label>
              How should your content sound?
              <input
                required
                minLength={3}
                maxLength={500}
                placeholder="Direct, practical, warm; use examples instead of jargon"
                value={form.voice}
                onChange={(e) => setForm({ ...form, voice: e.target.value })}
              />
            </label>
            <label>
              Your positioning
              <textarea
                required
                minLength={10}
                maxLength={1500}
                placeholder="Who do you help, with what problem, and why your approach?"
                aria-label="Your positioning"
                value={form.positioning}
                onChange={(e) =>
                  setForm({ ...form, positioning: e.target.value })
                }
              />
            </label>
            <div className="grid">
              <label>
                Proof points you can substantiate (optional, one per line)
                <textarea
                  aria-label="Proof points you can substantiate (optional, one per line)"
                  value={form.proof_points.join("\n")}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      proof_points: e.target.value.split("\n"),
                    })
                  }
                  onBlur={() =>
                    setForm((f) => ({
                      ...f,
                      proof_points: lines(f.proof_points.join("\n")),
                    }))
                  }
                />
              </label>
              <label>
                Topics or claims to avoid (optional, one per line)
                <textarea
                  aria-label="Topics or claims to avoid (optional, one per line)"
                  value={form.avoid_topics.join("\n")}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      avoid_topics: e.target.value.split("\n"),
                    })
                  }
                  onBlur={() =>
                    setForm((f) => ({
                      ...f,
                      avoid_topics: lines(f.avoid_topics.join("\n")),
                    }))
                  }
                />
              </label>
            </div>
            {canWrite && <button>Save brand version</button>}
          </fieldset>
        </form>
        {canWrite && brand?.status === "pending" && (
          <button
            disabled={busy}
            onClick={() =>
              action(async () => {
                await api(
                  `/v1/projects/${projectId}/brand/${brand.id}/approve`,
                  orgId,
                  {},
                );
                await refreshBrand();
                setNotice(
                  "This exact brand version is approved for agent workflows.",
                );
              })
            }
          >
            Approve brand version {brand.version}
          </button>
        )}
        {versions.length > 0 && (
          <details>
            <summary>Brand memory history</summary>
            <label>
              Inspect saved version
              <select
                value={historyVersion}
                onChange={(e) => setHistoryVersion(e.target.value)}
              >
                <option value="">Choose a version</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    Version {v.version} · {v.status}
                  </option>
                ))}
              </select>
            </label>
            {inspection && (
              <blockquote>
                <strong>
                  {inspection.data.founder_name} · {inspection.data.voice}
                </strong>
                <p>{inspection.data.story}</p>
                <p>{inspection.data.positioning}</p>
                <small>
                  Saved {new Date(inspection.created_at).toLocaleString()}.
                  Prior versions stay immutable.
                </small>
              </blockquote>
            )}
          </details>
        )}
      </section>
      <section className="panel command-center">
        <span className="eyebrow">YOUR COORDINATED AI GROWTH TEAM</span>
        <h2>One brief. Five connected agents.</h2>
        <p>
          The team shares your approved brand, supplied research and actual
          performance baseline. All content stays in review.
        </p>
        <div className="team-roster">
          {agentNames.map(([id, name]) => (
            <div
              key={id}
              className={artifact(id) ? "agent-card done" : "agent-card"}
            >
              <span>{artifact(id) ? "✓" : "○"}</span>
              <strong>{name}</strong>
              <small>
                {artifact(id) ? "Output saved" : "Ready to coordinate"}
              </small>
            </div>
          ))}
        </div>
        <p className="readiness">
          Brand: {brand?.status === "approved" ? "approved" : "needs approval"}{" "}
          · Research: {sourceCount} source{sourceCount === 1 ? "" : "s"} · Runs
          this month: {usage.workflow_runs}/{usage.limit}
        </p>
        <small>
          {generationMode === "llm"
            ? "AI mode: configured model provider. Outputs need your review."
            : "Template mode: tailored starter outputs; no live model or trend discovery."}
        </small>
        {canWrite && (
          <form onSubmit={queue}>
            <fieldset disabled={busy || !!activeRun}>
              <label>
                What should the team achieve?
                <textarea
                  required
                  minLength={10}
                  maxLength={1000}
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                />
              </label>
              <div className="grid">
                <label>
                  Content week starts
                  <input
                    type="date"
                    required
                    value={weekStart}
                    onChange={(e) => setWeekStart(e.target.value)}
                  />
                </label>
                <label>
                  Target launch date
                  <input
                    type="date"
                    required
                    value={launchDate}
                    onChange={(e) => setLaunchDate(e.target.value)}
                  />
                </label>
              </div>
              <button
                disabled={
                  brand?.status !== "approved" ||
                  sourceCount === 0 ||
                  usage.workflow_runs >= usage.limit
                }
              >
                Start growth workflow
              </button>
              <small>
                Add a research source in the Research section below before
                starting.
              </small>
            </fieldset>
          </form>
        )}
        {runs.length > 0 && (
          <label>
            Campaign history
            <select
              disabled={busy}
              value={run?.id || ""}
              onChange={(e) => action(() => loadRun(e.target.value))}
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.goal.slice(0, 60)} · {r.status}
                </option>
              ))}
            </select>
          </label>
        )}
        {run && (
          <div className="workflow-result">
            <div className="workflow-status">
              <strong role="status">
                {run.status === "needs_review"
                  ? "Ready for your review"
                  : run.status.replaceAll("_", " ")}
              </strong>
              <span>{run.progress}%</span>
            </div>
            <progress
              value={run.progress}
              max={100}
              aria-label="Growth workflow progress"
            />
            {run.status === "queued" && (
              <p>
                Your request is saved. The background worker will pick it up. If
                it stays queued, check that the worker service is running.
              </p>
            )}
            {run.status === "failed" && (
              <p className="error">
                The workflow stopped ({run.error_code}). No content was
                published. Check worker/provider configuration before starting a
                new run.
              </p>
            )}
            {canWrite && activeRun && (
              <button
                disabled={busy}
                className="secondary"
                onClick={() =>
                  action(async () => {
                    await api(`/v1/workflows/${run.id}/cancel`, orgId, {});
                    await loadRun(run.id);
                  })
                }
              >
                Cancel workflow
              </button>
            )}
            <small>
              Brand snapshot: version {run.brand_version || "—"} · Generation:{" "}
              {run.generation_mode}. Sources and performance are frozen for this
              run.
            </small>
            <nav className="team-tabs" aria-label="Agent outputs">
              {[
                ["growth", "Content calendar"],
                ["research", "Research radar"],
                ["video", "Video studio"],
                ["launch", "Launch center"],
              ].map(([id, label]) => (
                <button
                  type="button"
                  key={id}
                  aria-pressed={tab === id}
                  className={tab === id ? "" : "secondary"}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </nav>
            {tab === "research" &&
              (research ? (
                <div>
                  {research.opportunities.map((o, i) => (
                    <article key={i}>
                      <h3>{o.angle}</h3>
                      <p>{o.audience_fit}</p>
                      <small>{o.uncertainty}</small>
                      {o.evidence_ids.map((id) => {
                        const source = run.sources?.find((s) => s.id === id);
                        return (
                          source && (
                            <p key={id}>
                              <a
                                href={source.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {source.title}
                              </a>
                              <small>
                                Recorded{" "}
                                {new Date(
                                  source.observed_at,
                                ).toLocaleDateString()}{" "}
                                · operator-attested
                              </small>
                            </p>
                          )
                        );
                      })}
                    </article>
                  ))}
                </div>
              ) : (
                <p>
                  Research opportunities will appear after that agent finishes.
                </p>
              ))}
            {tab === "growth" &&
              (growth ? (
                <>
                  <h3>{growth.objective}</h3>
                  <p>{growth.experiment}</p>
                  <small>{growth.success_metric}</small>
                  {run.performance_baseline && (
                    <p>
                      Baseline: {run.performance_baseline.totals.leads} leads ·{" "}
                      {run.performance_baseline.totals.signups} signups ·{" "}
                      {run.performance_baseline.totals.paying_customers}{" "}
                      customers.
                    </p>
                  )}
                  <div className="content-calendar">
                    {drafts.map((d) => (
                      <CalendarCard
                        key={d.id + d.revision_hash}
                        draft={d}
                        orgId={orgId}
                        canWrite={canWrite}
                        changed={refreshContent}
                      />
                    ))}
                  </div>
                  <small>
                    Approve or reject these drafts in the campaign review
                    section below. Editing invalidates prior approval.
                  </small>
                </>
              ) : (
                <p>
                  Your seven-day calendar will appear when the workflow
                  completes.
                </p>
              ))}
            {tab === "video" &&
              (video ? (
                <>
                  <h3>{video.title}</h3>
                  <p>
                    <strong>Hook:</strong> {video.hook}
                  </p>
                  <small>
                    Script and storyboard only. MP4 rendering, media uploads,
                    voice and video publishing are not enabled in this
                    milestone.
                  </small>
                  {video.scenes.map((scene, i) => (
                    <article key={i}>
                      <strong>
                        Scene {i + 1} · {scene.duration_seconds}s
                      </strong>
                      <p>{scene.narration}</p>
                      <p>Caption: {scene.caption}</p>
                      <small>Visual direction: {scene.visual}</small>
                    </article>
                  ))}
                  <p>
                    <strong>Call to action:</strong> {video.call_to_action}
                  </p>
                  <button
                    className="secondary"
                    onClick={() =>
                      action(async () => {
                        await navigator.clipboard.writeText(
                          [
                            video.title,
                            video.hook,
                            ...video.scenes.map(
                              (s) =>
                                `${s.duration_seconds}s: ${s.narration}\nCaption: ${s.caption}\nVisual: ${s.visual}`,
                            ),
                            video.call_to_action,
                          ].join("\n\n"),
                        );
                        setNotice("Video script copied.");
                      })
                    }
                  >
                    Copy video script
                  </button>
                </>
              ) : (
                <p>
                  Your video script will appear after the Video Creator
                  finishes.
                </p>
              ))}
            {tab === "launch" &&
              (launch ? (
                <>
                  <h3>Product launch checklist</h3>
                  <p>{launch.message}</p>
                  {run.tasks?.map((task) => (
                    <label className="launch-task" key={task.id}>
                      <input
                        type="checkbox"
                        checked={task.completed}
                        disabled={busy || !canWrite}
                        onChange={(e) => toggleTask(task.id, e.target.checked)}
                      />
                      <span>
                        <strong>{task.title}</strong>
                        <small>
                          {task.due_date} · {task.phase.replaceAll("_", " ")}
                        </small>
                      </span>
                    </label>
                  ))}
                </>
              ) : (
                <p>
                  Launch tasks will appear after the full workflow completes.
                </p>
              ))}
          </div>
        )}
      </section>
    </div>
  );
}
