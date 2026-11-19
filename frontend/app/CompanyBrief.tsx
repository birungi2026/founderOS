"use client";
import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
type Company = {
  problem: string;
  solution: string;
  target_customers: string;
  differentiator: string;
  competitors: string[];
  version: number;
};
export default function CompanyBrief({
  orgId,
  projectId,
  canWrite,
  personal = false,
}: {
  orgId: string;
  projectId: string;
  canWrite: boolean;
  personal?: boolean;
}) {
  const [profile, setProfile] = useState<Company | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api(`/v1/projects/${projectId}/company`, orgId)
      .then((p) => {
        if (active) setProfile(p);
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
    if (!profile) return;
    setBusy(true);
    setError("");
    try {
      const { version, ...fields } = profile;
      const result = await api(`/v1/projects/${projectId}/company`, orgId, {
        ...fields,
        competitors: fields.competitors.map((s) => s.trim()).filter(Boolean),
        expected_version: version,
      });
      setProfile(result);
      setNotice(
        "Company brief saved. The employee will research these facts and ask you to confirm its findings before using them in content.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="panel" open={profile ? !profile.problem : false}>
      <summary>
        {personal
          ? "Personal brand brief: niche, audience and peers"
          : "Company brief: problem, solution, audience and competitors"}
      </summary>
      <p>
        Give the employee the basics. Differentiation starts as your hypothesis;
        the research brief will show supporting evidence and unknowns.
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
      {profile && (
        <form onSubmit={save}>
          <fieldset disabled={busy || !canWrite}>
            <label>
              {personal
                ? "Audience challenge (optional)"
                : "Problem your company solves"}
              <textarea
                aria-label={
                  personal
                    ? "Audience challenge (optional)"
                    : "Problem your company solves"
                }
                minLength={personal ? 0 : 10}
                maxLength={2000}
                required={!personal}
                value={profile.problem}
                onChange={(e) =>
                  setProfile({ ...profile, problem: e.target.value })
                }
              />
            </label>
            <label>
              {personal ? "Your niche and expertise" : "Your solution"}
              <textarea
                aria-label={
                  personal ? "Your niche and expertise" : "Your solution"
                }
                minLength={10}
                maxLength={2000}
                required
                value={profile.solution}
                onChange={(e) =>
                  setProfile({ ...profile, solution: e.target.value })
                }
              />
            </label>
            <label>
              {personal ? "Target audience" : "Target customers"}
              <input
                minLength={3}
                maxLength={500}
                required
                value={profile.target_customers}
                onChange={(e) =>
                  setProfile({ ...profile, target_customers: e.target.value })
                }
              />
            </label>
            <label>
              {personal
                ? "What makes your perspective distinctive"
                : "Why customers might choose you"}
              <textarea
                aria-label={
                  personal
                    ? "What makes your perspective distinctive"
                    : "Why customers might choose you"
                }
                maxLength={1500}
                value={profile.differentiator}
                onChange={(e) =>
                  setProfile({ ...profile, differentiator: e.target.value })
                }
              />
            </label>
            <label>
              Competitor websites (optional, up to three, one per line)
              <textarea
                aria-label="Competitor websites"
                value={profile.competitors.join("\n")}
                onChange={(e) =>
                  setProfile({
                    ...profile,
                    competitors: e.target.value.split("\n"),
                  })
                }
              />
            </label>
            {canWrite && <button>Save company brief</button>}
          </fieldset>
        </form>
      )}
    </details>
  );
}
