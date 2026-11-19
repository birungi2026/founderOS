"use client";
import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
export const goalLabels: Record<string, string> = {
  followers: "Relevant followers",
  newsletter_subscribers: "Newsletter subscribers",
  inquiries: "Qualified inquiries",
};
export default function PersonalProgress({
  orgId,
  projectId,
  canWrite,
}: {
  orgId: string;
  projectId: string;
  canWrite: boolean;
}) {
  const [project, setProject] = useState<{
      personal_current?: number;
      personal_target: number;
      personal_goal: string;
      personal_progress_version?: number;
    } | null>(null),
    [current, setCurrent] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    let active = true;
    api(`/projects/${projectId}`, orgId)
      .then((p) => {
        if (active) {
          setProject(p);
          setCurrent(p.personal_current || 0);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [orgId, projectId]);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const p = await api(`/projects/${projectId}/personal-progress`, orgId, {
        current,
        expected_version: project?.personal_progress_version || 0,
      });
      setProject(p);
      setNotice(
        "Progress saved. This is a self-reported total, not an automatically verified platform metric.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Progress could not be saved");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <span className="eyebrow">YOUR PERSONAL BRAND GOAL</span>
      <h2>
        {project
          ? goalLabels[project.personal_goal]
          : "Audience & opportunities"}
      </h2>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {project && (
        <>
          <div className="customer-goal">
            <strong>
              {project.personal_current || 0}
              <span> / {project.personal_target}</span>
            </strong>
          </div>
          <progress
            aria-label="Personal brand goal progress"
            max={project.personal_target}
            value={Math.min(
              project.personal_current || 0,
              project.personal_target,
            )}
          />
          <p>
            Measure the people and opportunities relevant to your niche.
            Follower growth does not imply revenue.
          </p>
          <form onSubmit={save}>
            <fieldset disabled={!canWrite || busy}>
              <label>
                Current total (self-reported)
                <input
                  type="number"
                  min={0}
                  max={100000000}
                  required
                  value={current}
                  onChange={(e) => setCurrent(Number(e.target.value))}
                />
              </label>
              <button>Save personal brand progress</button>
            </fieldset>
          </form>
          <small>
            Enter the current total, not an increment. Connected account data is
            separate until automated goal attribution is implemented.
          </small>
        </>
      )}
    </section>
  );
}
