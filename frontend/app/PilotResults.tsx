"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "./api";
type Observation = {
  id: string;
  kind: string;
  channel: string;
  starts_on: string;
  ends_on: string;
  followers: number | null;
  inquiries: number | null;
  published: number;
  delivered: number;
  editing_minutes: number;
  source: string;
  cost_cents: number | null;
  revenue_cents: number | null;
  likely_authentic: number;
  suspicious: number;
  unknown: number;
  paid_promotion: boolean;
  renewed: boolean | null;
};
type Config = {
  revision: number;
  cohort: string;
  segment: string;
  primary_goal: string;
  starts_on: string;
  offer: string;
};
type Report = {
  config: Config | null;
  observations: Observation[];
  comparisons: {
    channel: string;
    follower_change: number | null;
    comparable: boolean;
  }[];
  note: string;
};
const today = () => new Date().toISOString().slice(0, 10);
export default function PilotResults({
  orgId,
  projectId,
  isOwner,
  canWrite,
}: {
  orgId: string;
  projectId: string;
  isOwner: boolean;
  canWrite: boolean;
}) {
  const root = `/v1/projects/${projectId}/pilot`;
  const [report, setReport] = useState<Report | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const [config, setConfig] = useState<Config>({
    revision: 0,
    cohort: "not_enrolled",
    segment: "other",
    primary_goal: "followers",
    starts_on: today(),
    offer: "",
  });
  const pending = useRef({ payload: "", id: "" });
  async function load() {
    const value = await api(root, orgId);
    setReport(value);
    if (value.config) setConfig(value.config);
  }
  useEffect(() => {
    let active = true;
    api(root, orgId)
      .then((value) => {
        if (active) {
          setReport(value);
          if (value.config) setConfig(value.config);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [orgId, projectId]);
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }
  function record(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const values: Record<string, unknown> = {
      kind: data.get("kind"),
      channel: data.get("channel"),
      starts_on: data.get("starts_on"),
      ends_on: data.get("ends_on"),
      attested: true,
      paid_promotion: data.get("paid_promotion") === "on",
      renewed:
        data.get("renewed") === "yes"
          ? true
          : data.get("renewed") === "no"
            ? false
            : null,
    };
    for (const name of ["followers", "inquiries", "paying_customers"])
      values[name] = data.get(name) === "" ? null : Number(data.get(name));
    for (const name of [
      "delivered",
      "published",
      "editing_minutes",
      "likely_authentic",
      "suspicious",
      "unknown",
    ])
      values[name] = Number(data.get(name) || 0);
    values.revenue_cents =
      data.get("revenue") === ""
        ? null
        : Math.round(Number(data.get("revenue")) * 100);
    values.cost_cents =
      data.get("cost") === ""
        ? null
        : Math.round(Number(data.get("cost")) * 100);
    const payload = JSON.stringify(values);
    if (pending.current.payload !== payload)
      pending.current = { payload, id: crypto.randomUUID() };
    void act(async () => {
      await api(root + "/observations", orgId, {
        ...values,
        external_id: pending.current.id,
      });
      pending.current = { payload: "", id: "" };
      setNotice("Observation saved as operator-reported evidence.");
    });
  }
  return (
    <section className="panel" aria-label="Pilot evidence">
      <span className="eyebrow">MEASURE WHAT CHANGED</span>
      <h2>Growth evidence</h2>
      <p>
        Compare a baseline with later results. Likes and followers are not
        verified sales.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {report?.comparisons.map((c) => (
        <p key={c.channel}>
          <strong>{c.channel}:</strong>{" "}
          {c.follower_change === null
            ? "No comparable follower totals yet"
            : `${c.follower_change >= 0 ? "+" : ""}${c.follower_change} followers`}{" "}
          {!c.comparable && "· Observation windows overlap"}
        </p>
      ))}
      {!report?.observations.length && <p>No baseline yet.</p>}
      {report && (
        <button
          className="secondary"
          onClick={() => {
            const url = URL.createObjectURL(
              new Blob([JSON.stringify(report, null, 2)], {
                type: "application/json",
              }),
            );
            const a = document.createElement("a");
            a.href = url;
            a.download = "rymu-pilot-evidence.json";
            a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
          }}
        >
          Export pilot evidence
        </button>
      )}
      <details>
        <summary>Pilot goal and group</summary>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await api(root + "/config", orgId, config);
              setNotice("Pilot settings saved.");
            });
          }}
        >
          <fieldset disabled={!isOwner || busy}>
            <div className="grid">
              <label>
                Focus
                <select
                  value={config.segment}
                  onChange={(e) =>
                    setConfig({ ...config, segment: e.target.value })
                  }
                >
                  <option value="coach">Coach or instructor</option>
                  <option value="creator">Personal creator</option>
                  <option value="founder">Business founder</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>
                Main outcome
                <select
                  value={config.primary_goal}
                  onChange={(e) =>
                    setConfig({ ...config, primary_goal: e.target.value })
                  }
                >
                  <option value="followers">Relevant followers</option>
                  <option value="inquiries">Qualified inquiries</option>
                  <option value="paying_customers">Paying customers</option>
                </select>
              </label>
              <label>
                Study group
                <select
                  value={config.cohort}
                  onChange={(e) =>
                    setConfig({ ...config, cohort: e.target.value })
                  }
                >
                  <option value="not_enrolled">Not enrolled</option>
                  <option value="immediate">Start now</option>
                  <option value="delayed">
                    Start later (comparison group)
                  </option>
                </select>
              </label>
              <label>
                Start date
                <input
                  type="date"
                  required
                  value={config.starts_on}
                  onChange={(e) =>
                    setConfig({ ...config, starts_on: e.target.value })
                  }
                />
              </label>
            </div>
            <label>
              Offer being tested (optional)
              <input
                maxLength={500}
                value={config.offer}
                onChange={(e) =>
                  setConfig({ ...config, offer: e.target.value })
                }
              />
            </label>
            <button>Save pilot settings</button>
          </fieldset>
        </form>
      </details>
      <details>
        <summary>Record a baseline or follow-up</summary>
        <form onSubmit={record}>
          <fieldset disabled={!canWrite || busy}>
            <div className="grid">
              <label>
                Observation
                <select name="kind" aria-label="Observation">
                  <option value="baseline">Baseline</option>
                  <option value="followup">Follow-up</option>
                </select>
              </label>
              <label>
                Channel
                <select name="channel">
                  <option>instagram</option>
                  <option>facebook</option>
                  <option>linkedin</option>
                  <option>tiktok</option>
                </select>
              </label>
              <label>
                Window starts
                <input name="starts_on" type="date" required max={today()} />
              </label>
              <label>
                Window ends
                <input name="ends_on" type="date" required max={today()} />
              </label>
            </div>
            <div className="grid">
              {[
                ["followers", "Follower total at window end"],
                ["inquiries", "Qualified inquiries in this window"],
                ["paying_customers", "New paying customers in this window"],
                ["delivered", "Posts delivered"],
                ["published", "Posts published"],
                ["editing_minutes", "Minutes spent editing"],
              ].map(([name, label]) => (
                <label key={name}>
                  {label}
                  <input
                    name={name}
                    type="number"
                    min={0}
                    max={
                      name === "followers"
                        ? 1000000000
                        : name === "editing_minutes"
                          ? 100000
                          : 1000
                    }
                  />
                </label>
              ))}
            </div>
            <small>
              Leave unknown follower, inquiry or customer counts blank. Use
              equal, non-overlapping windows for comparisons.
            </small>
            <label className="check">
              <input name="paid_promotion" type="checkbox" />
              Paid ads or boosted posts ran during this window.
            </label>
            <details>
              <summary>Audience sample, costs and renewal (optional)</summary>
              <p>
                Review a random sample where access permits. These judgments
                cannot certify that every follower is human.
              </p>
              <div className="grid">
                {[
                  ["likely_authentic", "Likely authentic accounts"],
                  ["suspicious", "Suspicious accounts"],
                  ["unknown", "Unknown accounts"],
                ].map(([name, label]) => (
                  <label key={name}>
                    {label}
                    <input type="number" name={name} min={0} max={1000} />
                  </label>
                ))}
                <label>
                  Revenue received (USD)
                  <input type="number" name="revenue" min={0} step="0.01" />
                </label>
                <label>
                  Total cost incurred (USD)
                  <input type="number" name="cost" min={0} step="0.01" />
                </label>
                <label>
                  Customer renewed?
                  <select name="renewed">
                    <option value="">Not known yet</option>
                    <option value="yes">Yes</option>
                    <option value="no">No</option>
                  </select>
                </label>
              </div>
            </details>
            <label className="check">
              <input type="checkbox" required />I checked these figures. They
              are self-reported, not independently verified.
            </label>
            <button>Save growth observation</button>
          </fieldset>
        </form>
      </details>
      {report?.observations.map((o) => (
        <article key={o.id} className="weekly-draft">
          <strong>
            {o.kind} · {o.channel} · {o.starts_on} – {o.ends_on}
          </strong>
          <p>
            {o.followers ?? "Unknown"} followers · {o.published}/{o.delivered}{" "}
            posts published · {o.editing_minutes} editing minutes ·{" "}
            {o.source.replaceAll("_", " ")}
          </p>
          <p>
            Audience sample: {o.likely_authentic} likely authentic /{" "}
            {o.suspicious} suspicious / {o.unknown} unknown
            {o.paid_promotion ? " · Paid promotion included" : ""}
          </p>
        </article>
      ))}
      <p>
        <small>{report?.note}</small>
      </p>
    </section>
  );
}
