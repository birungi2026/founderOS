"use client";
import { FormEvent, useEffect, useState } from "react";
import { API, api } from "./api";

type Draft = {
  id: string;
  content: string;
  channel: string;
  status: string;
  planned_date: string;
  revision_hash: string;
};
type Asset = {
  id: string;
  status: string;
  duration: number;
  video_url?: string;
  caption?: string;
  error?: string;
  journey_id?: string;
};
type Video = {
  id: string;
  status: string;
  caption: string;
  results?: { metrics: Record<string, number> };
  observed_at?: number;
};
export default function WeeklyWorkspace({
  orgId,
  projectId,
  canWrite,
  isOwner,
  reviewVideo,
  refreshKey,
}: {
  orgId: string;
  projectId: string;
  canWrite: boolean;
  isOwner: boolean;
  reviewVideo: (id: string) => void;
  refreshKey: number;
}) {
  const root = `/v1/projects/${projectId}`;
  const [week, setWeek] = useState<{
    start: string;
    end: string;
    drafts: Draft[];
    videos: Video[];
  } | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]),
    [selected, setSelected] = useState("");
  const [start, setStart] = useState(0),
    [end, setEnd] = useState(30),
    [caption, setCaption] = useState(""),
    [subtitles, setSubtitles] = useState("");
  const [transcribe, setTranscribe] = useState(false);
  const [file, setFile] = useState<File | null>(null),
    [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    const [w, a] = await Promise.all([
      api(root + "/week", orgId),
      api(root + "/assets", orgId),
    ]);
    setWeek(w);
    setAssets(a.assets);
  }
  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const [w, a] = await Promise.all([
          api(root + "/week", orgId),
          api(root + "/assets", orgId),
        ]);
        if (active) {
          setWeek(w);
          setAssets(a.assets);
        }
      } catch (e) {
        if (active)
          setError(e instanceof Error ? e.message : "Could not load this week");
      }
    }
    void poll();
    const timer = setInterval(poll, 10000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [orgId, projectId, refreshKey]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  const asset = assets.find((a) => a.id === selected);
  async function upload(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    await act(async () => {
      const response = await fetch(API + root + "/assets", {
        method: "POST",
        credentials: "include",
        headers: {
          "X-Organization-ID": orgId,
          "Content-Type":
            file.type ||
            (file.name.endsWith(".mp4") ? "video/mp4" : "video/webm"),
        },
        body: file,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Upload failed");
      setSelected(result.id);
      setStart(0);
      setEnd(Math.min(30, Math.floor(result.duration)));
      setNotice("Uploaded. Choose your clip range and captions.");
    });
  }
  return (
    <section className="panel weekly-workspace" aria-label="Weekly review">
      <span className="eyebrow">YOUR WEEKLY CONTENT</span>
      <h2>Review, then share.</h2>
      <p>
        {week ? `${week.start} – ${week.end}` : "Loading this week…"} · Approved
        drafts are not automatically published.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <button
        className="secondary"
        disabled={busy}
        onClick={() => void act(load)}
      >
        Refresh weekly review
      </button>
      <button
        className="secondary"
        disabled={!week?.drafts.length || busy}
        onClick={() =>
          void act(async () => {
            const response = await fetch(API + root + "/week/export", {
              credentials: "include",
              headers: { "X-Organization-ID": orgId },
            });
            if (!response.ok) throw new Error("Export failed");
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = url;
            link.download = "rymu-week.csv";
            link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          })
        }
      >
        Download this week
      </button>
      {!week?.drafts.length && (
        <p>
          No posts for this week yet. Start research below, then confirm the
          findings.
        </p>
      )}
      {week?.drafts.map((d) => (
        <article key={d.id} className="weekly-draft">
          <h3>
            {d.planned_date} · {d.channel}
          </h3>
          <p className="tag">{d.status}</p>
          <label>
            Post text
            <textarea
              aria-label={`Post text ${d.id}`}
              value={edits[d.id] ?? d.content}
              disabled={
                !canWrite ||
                busy ||
                !["pending", "approved", "rejected"].includes(d.status)
              }
              onChange={(e) => setEdits({ ...edits, [d.id]: e.target.value })}
              maxLength={6000}
            />
          </label>
          {canWrite && (
            <div className="journey-actions">
              <button
                className="secondary"
                disabled={
                  busy || edits[d.id] === undefined || edits[d.id] === d.content
                }
                onClick={() =>
                  void act(async () => {
                    await api(`/v1/content/${d.id}/revisions`, orgId, {
                      content: edits[d.id],
                      planned_date: d.planned_date,
                      expected_hash: d.revision_hash,
                    });
                    setEdits((current) => {
                      const next = { ...current };
                      delete next[d.id];
                      return next;
                    });
                    setNotice(
                      "Saved. Review the updated post before approval.",
                    );
                  })
                }
              >
                Save post edit
              </button>
              <button
                disabled={
                  busy ||
                  d.status !== "pending" ||
                  (edits[d.id] !== undefined && edits[d.id] !== d.content)
                }
                onClick={() =>
                  void act(async () => {
                    await api(
                      `/drafts/${d.id}/review?decision=approved&revision=${encodeURIComponent(d.revision_hash)}`,
                      orgId,
                      {},
                    );
                    setNotice(
                      "Draft approved. Publication still needs a separate approval.",
                    );
                  })
                }
              >
                Approve this draft
              </button>
            </div>
          )}
        </article>
      ))}
      <h3>Videos awaiting review and recent results</h3>
      {week?.videos.map((v) => (
        <article key={v.id} className="weekly-draft">
          <p>
            <strong>{v.status.replaceAll("_", " ")}</strong> · {v.caption}
          </p>
          {v.results && (
            <p>
              {Object.entries(v.results.metrics)
                .map(([name, value]) => `${name}: ${value}`)
                .join(" · ") || "Metrics unavailable"}
              {v.observed_at
                ? ` · Checked ${new Date(v.observed_at * 1000).toLocaleString()}`
                : ""}
            </p>
          )}
          <button className="secondary" onClick={() => reviewVideo(v.id)}>
            Review this video
          </button>
        </article>
      ))}
      <details>
        <summary>Make a clip from your own footage</summary>
        <p>
          Upload footage you have permission to use. Rymu trims your selected
          range into a vertical MP4. No avatar required.
        </p>
        <form onSubmit={upload}>
          <fieldset disabled={!isOwner || busy}>
            <label>
              Your footage
              <input
                type="file"
                accept="video/mp4,video/webm"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <small>MP4/WebM · up to 25 MB · 10 minutes maximum</small>
            <button>Upload real footage</button>
          </fieldset>
        </form>
        <label>
          Choose uploaded footage
          <select
            value={selected}
            onChange={(e) => {
              const item = assets.find((a) => a.id === e.target.value);
              setSelected(e.target.value);
              setStart(0);
              setEnd(Math.min(30, Math.floor(item?.duration || 30)));
            }}
          >
            <option value="">Choose footage</option>
            {assets.map((a) => (
              <option key={a.id} value={a.id}>
                {a.status} · {Math.round(a.duration)} seconds ·{" "}
                {a.id.slice(0, 8)}
              </option>
            ))}
          </select>
        </label>
        {asset?.status === "uploaded" && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void act(async () => {
                await api(root + `/assets/${asset.id}/render`, orgId, {
                  start,
                  end,
                  caption,
                  subtitles,
                  transcribe,
                });
                setNotice(
                  "Clip queued. Keep the worker running; the finished video will appear here.",
                );
              });
            }}
          >
            <fieldset disabled={!isOwner || busy}>
              <div className="grid">
                <label>
                  Start at (seconds)
                  <input
                    type="number"
                    min={0}
                    max={asset.duration - 1}
                    step="0.1"
                    value={start}
                    onChange={(e) => setStart(Number(e.target.value))}
                    required
                  />
                </label>
                <label>
                  End at (seconds)
                  <input
                    type="number"
                    min={start + 1}
                    max={Math.min(start + 120, asset.duration)}
                    step="0.1"
                    value={end}
                    onChange={(e) => setEnd(Number(e.target.value))}
                    required
                  />
                </label>
              </div>
              <label>
                Post caption
                <textarea
                  minLength={10}
                  maxLength={2000}
                  required
                  value={caption}
                  onChange={(e) => setCaption(e.target.value)}
                />
              </label>
              <label>
                On-screen captions (optional)
                <textarea
                  maxLength={4000}
                  value={subtitles}
                  onChange={(e) => setSubtitles(e.target.value)}
                />
              </label>
              <small>
                Manual captions are spaced across the clip; review their timing
                in the finished video.
              </small>
              <label className="check">
                <input
                  type="checkbox"
                  checked={transcribe}
                  onChange={(e) => setTranscribe(e.target.checked)}
                />
                Send this clip to OpenAI for automatic speech captions instead.
              </label>
              <button>Make vertical clip</button>
            </fieldset>
          </form>
        )}
        {asset?.error && <p role="alert">{asset.error}</p>}
        {asset?.status === "ready" && (
          <>
            <video
              controls
              playsInline
              src={asset.video_url}
              style={{ width: "100%", maxHeight: 420 }}
            />
            <a href={asset.video_url} target="_blank" rel="noreferrer">
              Open finished MP4
            </a>
            <button
              disabled={busy || !isOwner}
              onClick={() =>
                void act(async () => {
                  const result = await api(
                    root + `/assets/${asset.id}/use`,
                    orgId,
                    {},
                  );
                  reviewVideo(result.journey_id);
                })
              }
            >
              Review and schedule this clip
            </button>
          </>
        )}
        {asset && !["queued", "processing"].includes(asset.status) && (
          <button
            className="secondary"
            disabled={busy || !isOwner}
            onClick={() =>
              void act(async () => {
                await api(root + `/assets/${asset.id}/delete`, orgId, {});
                setSelected("");
              })
            }
          >
            Delete this footage and clip
          </button>
        )}
      </details>
    </section>
  );
}
