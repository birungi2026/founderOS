"use client";
import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";

type Lead = {
  id: string;
  name: string;
  website: string;
  stage: string;
  next_action: string;
  version: number;
};
type Funnel = {
  counts: Record<string, number>;
  paying_customers: number;
  target_customers: number;
  remaining: number;
};
type Schedule = {
  enabled: boolean;
  goal: string;
  hour: number;
  timezone: string;
  next_run: string;
  frequency: string;
  posts_per_day: number;
  weekday: number;
  month_day: number;
  last_error: string | null;
  last_run_id: string | null;
};
const stages = [
  ["identified", "Potential buyer"],
  ["contacted", "Contacted"],
  ["conversation", "Conversation"],
  ["trial", "Trial / demo"],
  ["won", "Paying customer"],
  ["lost", "Lost"],
];
const defaultGoal =
  "Convert qualified leads and followers into our first 50 paying customers.";
function LeadCard({
  lead,
  org,
  editable,
  refresh,
}: {
  lead: Lead;
  org: string;
  editable: boolean;
  refresh: () => Promise<void>;
}) {
  const [stage, setStage] = useState(lead.stage),
    [next, setNext] = useState(lead.next_action),
    [paid, setPaid] = useState(lead.stage === "won"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/v1/customers/${lead.id}`, org, {
        expected_version: lead.version,
        stage,
        next_action: next,
        paying_customer_confirmed: paid,
      });
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="lead-card">
      <h3>{lead.name}</h3>
      <a href={lead.website} target="_blank" rel="noreferrer">
        View company / source
      </a>
      <form onSubmit={save}>
        <fieldset disabled={busy || !editable}>
          <label>
            Lead stage
            <select
              aria-label="Lead stage"
              value={stage}
              onChange={(e) => setStage(e.target.value)}
            >
              {stages.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Next acquisition action
            <input
              minLength={3}
              maxLength={1000}
              required
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </label>
          {stage === "won" && (
            <label className="check">
              <input
                type="checkbox"
                required
                checked={paid}
                onChange={(e) => setPaid(e.target.checked)}
              />
              I confirm this customer has actually paid.
            </label>
          )}
          {editable && <button>Save lead progress</button>}
        </fieldset>
      </form>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </article>
  );
}
export default function DailyEmployee({
  orgId,
  projectId,
  canWrite,
  isOwner,
  refreshKey,
  section,
  goalText,
}: {
  orgId: string;
  projectId: string;
  canWrite: boolean;
  isOwner: boolean;
  refreshKey: number;
  section?: string;
  goalText?: string;
}) {
  const [leads, setLeads] = useState<Lead[]>([]),
    [funnel, setFunnel] = useState<Funnel | null>(null),
    [schedule, setSchedule] = useState<Schedule | null>(null),
    [available, setAvailable] = useState(false);
  const [goal, setGoal] = useState(goalText || defaultGoal),
    [enabled, setEnabled] = useState(false),
    [hour, setHour] = useState(9),
    [zone, setZone] = useState("UTC");
  const [frequency, setFrequency] = useState("daily"),
    [postsPerDay, setPostsPerDay] = useState(1),
    [weekday, setWeekday] = useState(0),
    [monthDay, setMonthDay] = useState(1);
  const [name, setName] = useState(""),
    [website, setWebsite] = useState(""),
    [nextAction, setNextAction] = useState(
      "Research their buying problem and prepare a relevant conversation opener.",
    );
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  async function refresh() {
    const result = await api(`/v1/projects/${projectId}/customers`, orgId);
    setLeads(result.leads);
    setFunnel(result.funnel);
  }
  useEffect(() => {
    let active = true;
    Promise.all([
      api(`/v1/projects/${projectId}/customers`, orgId),
      api(`/v1/projects/${projectId}/daily`, orgId),
    ])
      .then(([c, d]) => {
        if (!active) return;
        setLeads(c.leads);
        setFunnel(c.funnel);
        setSchedule(d.schedule);
        setAvailable(d.research_configured);
        if (d.schedule) {
          setEnabled(d.schedule.enabled);
          setGoal(d.schedule.goal);
          setHour(d.schedule.hour);
          setZone(d.schedule.timezone);
          setFrequency(d.schedule.frequency);
          setPostsPerDay(d.schedule.posts_per_day);
          setWeekday(d.schedule.weekday);
          setMonthDay(d.schedule.month_day);
        } else {
          setZone(Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [orgId, projectId, refreshKey]);
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
  function submit(e: FormEvent, fn: () => Promise<void>) {
    e.preventDefault();
    void action(fn);
  }
  return (
    <section className="panel conversion-center">
      <span className="eyebrow">THE BUSINESS OUTCOME</span>
      <h2>Your first {funnel?.target_customers || 50} paying customers.</h2>
      <p>
        The growth employee should turn relevant attention into conversations,
        trials and purchases. Followers and impressions stay separate from
        confirmed customers.
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
      {funnel && (
        <>
          <div className="customer-goal">
            <strong>
              {funnel.paying_customers}
              <span> / {funnel.target_customers}</span>
            </strong>
            <p>
              {funnel.remaining} more paying customers to reach the first
              milestone.
            </p>
          </div>
          <progress
            max={funnel.target_customers}
            value={Math.min(funnel.target_customers, funnel.paying_customers)}
            aria-label="Progress toward the paying-customer goal"
          />
          <div className="stats">
            {stages
              .filter(([s]) => s !== "lost")
              .map(([id, label]) => (
                <div key={id}>
                  <strong>{funnel.counts[id]}</strong>
                  <span>{label}</span>
                </div>
              ))}
          </div>
          <small>
            Customer counts are founder-confirmed records, not yet verified
            against a payment provider. A source or lead is never counted as a
            sale.
          </small>
        </>
      )}
      <details className="daily-settings" open={section === "routine"}>
        <summary>Content routine: daily, weekly or monthly</summary>
        <p>
          Set a routine once. The employee refreshes research and prepares your
          chosen number of drafts plus a video script on each selected day.
          Actual publishing needs a connected channel and separate approval.
        </p>
        <form
          onSubmit={(e) =>
            submit(e, async () => {
              const saved = await api(
                `/v1/projects/${projectId}/daily`,
                orgId,
                {
                  enabled,
                  goal,
                  hour,
                  timezone: zone,
                  frequency,
                  posts_per_day: postsPerDay,
                  weekday,
                  month_day: monthDay,
                },
              );
              setSchedule(saved);
              setNotice(
                enabled
                  ? "Content routine enabled. Drafts will be prepared on your selected days."
                  : "Routine paused; unfinished recurring jobs were cancelled.",
              );
            })
          }
        >
          <fieldset disabled={busy || !isOwner}>
            <label className="check">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
              />
              Enable recurring research and draft generation
            </label>
            <div className="grid">
              <label>
                Content frequency
                <select
                  aria-label="Content frequency"
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </label>
              <label>
                Posts per selected day
                <input
                  type="number"
                  min={1}
                  max={5}
                  required
                  value={postsPerDay}
                  onChange={(e) => setPostsPerDay(Number(e.target.value))}
                />
              </label>
            </div>
            {frequency === "weekly" && (
              <label>
                Preparation weekday
                <select
                  aria-label="Preparation weekday"
                  value={weekday}
                  onChange={(e) => setWeekday(Number(e.target.value))}
                >
                  {[
                    "Monday",
                    "Tuesday",
                    "Wednesday",
                    "Thursday",
                    "Friday",
                    "Saturday",
                    "Sunday",
                  ].map((name, index) => (
                    <option key={name} value={index}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {frequency === "monthly" && (
              <label>
                Preparation day of month
                <input
                  type="number"
                  min={1}
                  max={28}
                  required
                  value={monthDay}
                  onChange={(e) => setMonthDay(Number(e.target.value))}
                />
              </label>
            )}
            <label>
              Acquisition objective
              <textarea
                aria-label="Acquisition objective"
                minLength={10}
                maxLength={1000}
                required
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
              />
            </label>
            <div className="grid">
              <label>
                Preparation hour
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={hour}
                  required
                  onChange={(e) => setHour(Number(e.target.value))}
                />
              </label>
              <label>
                Your timezone
                <input
                  required
                  value={zone}
                  onChange={(e) => setZone(e.target.value)}
                />
              </label>
            </div>
            {!available && (
              <p>
                The workspace's search service is not connected yet. A server
                administrator must configure it before automatic research can
                run.
              </p>
            )}
            {isOwner && (
              <button disabled={enabled && !available}>
                Save content routine
              </button>
            )}
          </fieldset>
        </form>
        {!isOwner && (
          <small>An organization owner manages the daily routine.</small>
        )}
        {schedule && (
          <p>
            {schedule.enabled
              ? `Next preparation: ${new Date(schedule.next_run).toLocaleString()}`
              : "Recurring work is paused."}
            {schedule.last_error &&
              ` Setup needs attention: ${schedule.last_error.replaceAll("_", " ")}.`}
          </p>
        )}
        <small>
          Recurring work uses your organization's monthly workflow allowance. A
          paused or missed day is not backfilled with a burst of posts.
        </small>
      </details>
      <details open={section === "customers"}>
        <summary>Customer pipeline and next actions</summary>
        {canWrite && (
          <form
            onSubmit={(e) =>
              submit(e, async () => {
                await api(`/v1/projects/${projectId}/customers`, orgId, {
                  name,
                  website,
                  next_action: nextAction,
                });
                setName("");
                setWebsite("");
                await refresh();
              })
            }
          >
            <fieldset disabled={busy}>
              <div className="grid">
                <label>
                  Customer or company name
                  <input
                    required
                    minLength={2}
                    maxLength={200}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <label>
                  Customer company website
                  <input
                    type="url"
                    required
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                  />
                </label>
              </div>
              <label>
                First acquisition action
                <input
                  required
                  minLength={3}
                  maxLength={1000}
                  value={nextAction}
                  onChange={(e) => setNextAction(e.target.value)}
                />
              </label>
              <button>Add potential customer</button>
            </fieldset>
          </form>
        )}
        <div className="content-calendar">
          {leads.map((lead) => (
            <LeadCard
              key={lead.id + lead.version}
              lead={lead}
              org={orgId}
              editable={canWrite}
              refresh={refresh}
            />
          ))}
        </div>
        {leads.length === 0 && (
          <p>
            No customers are recorded yet. Research can suggest possible buyers;
            qualify them before counting them as leads or preparing individual
            outreach.
          </p>
        )}
      </details>
    </section>
  );
}
