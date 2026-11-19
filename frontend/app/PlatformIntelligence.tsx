"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
type Guidance = {
  platform: string;
  source_url: string;
  signal: string;
  experiment: string;
  success_metric: string;
  uncertainty: string;
  curated_reviewed_on: string;
  published_on: string | null;
  account_data: {
    name: string;
    observed_at?: number;
    recent_posts: number;
    followers_count?: number;
    limitations?: string;
  }[];
};
export default function PlatformIntelligence({
  orgId,
  projectId,
}: {
  orgId: string;
  projectId: string;
}) {
  const [items, setItems] = useState<Guidance[]>([]),
    [selected, setSelected] = useState("instagram"),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api(`/v1/projects/${projectId}/platform-intelligence`, orgId)
      .then((p) => {
        if (active) setItems(p.platforms);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [orgId, projectId]);
  const item = items.find((p) => p.platform === selected);
  return (
    <details className="panel">
      <summary>Platform growth intelligence</summary>
      <h2>Study the platforms. Test what works.</h2>
      <p>
        Published guidance and account observations help your employee propose
        experiments. Private ranking weights are unknown. New automatic research
        runs check for public updates; findings need your confirmation before
        content creation.
      </p>
      <button
        type="button"
        className="secondary"
        onClick={() => {
          setError("");
          api(`/v1/projects/${projectId}/platform-intelligence`, orgId)
            .then((p) => setItems(p.platforms))
            .catch((e) => setError(e.message));
        }}
      >
        Refresh platform evidence
      </button>
      {error && <p role="alert">{error}</p>}
      <nav className="team-tabs" aria-label="Platform guidance">
        {items.map((p) => (
          <button
            type="button"
            aria-pressed={selected === p.platform}
            key={p.platform}
            onClick={() => setSelected(p.platform)}
          >
            {p.platform === "linkedin"
              ? "LinkedIn"
              : p.platform === "tiktok"
                ? "TikTok"
                : p.platform === "instagram"
                  ? "Instagram"
                  : "Facebook"}
          </button>
        ))}
      </nav>
      {item && (
        <article>
          <h3>What the platform has published</h3>
          <p>{item.signal}</p>
          <a href={item.source_url} target="_blank" rel="noreferrer">
            Official platform guidance
          </a>
          <p>
            <small>
              Curated review: {item.curated_reviewed_on}. This is not a live
              algorithm measurement.
            </small>
          </p>
          <h3>Experiment to consider</h3>
          <p>{item.experiment}</p>
          <h3>What to measure</h3>
          <p>{item.success_metric}</p>
          <h3>Available account evidence</h3>
          {!item.account_data.length ? (
            <p>
              No active connected account snapshot. These suggestions are not
              personalized performance findings.
            </p>
          ) : (
            item.account_data.map((a, i) => (
              <div key={i}>
                <p>
                  {a.name}:{" "}
                  {a.observed_at
                    ? `Retrieved ${new Date(a.observed_at * 1000).toLocaleString()} · ${a.recent_posts} recent posts`
                    : "Connected; no data retrieved yet"}{" "}
                  · Followers: {a.followers_count ?? "Unavailable"}
                </p>
                {a.limitations && <small>{a.limitations}</small>}
              </div>
            ))
          )}
          <p>{item.uncertainty}</p>
        </article>
      )}
    </details>
  );
}
