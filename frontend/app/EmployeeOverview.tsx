"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
import { goalLabels } from "./PersonalProgress";
import Icon from "./Icon";
import CreationChoices from "./CreationChoices";
export type WorkspaceView =
  | "journey"
  | "overview"
  | "profile"
  | "accounts"
  | "content"
  | "customers"
  | "routine"
  | "settings";
export const workspaceViews: [WorkspaceView, string][] = [
  ["overview", "Overview"],
  ["journey", "Your growth journey"],
  ["profile", "1. Company & founder"],
  ["accounts", "2. Social accounts"],
  ["content", "3. Research & content"],
  ["routine", "4. Working routine"],
  ["customers", "Customers"],
  ["settings", "Advanced tools"],
];
type Summary = {
  personal: boolean;
  metric: string;
  company: boolean;
  brand: boolean;
  accounts: number;
  runStatus: string;
  runGoal: string;
  routine: boolean;
  paid: number;
  target: number;
  leads: number;
  reviews: number;
  recent: {
    id: string;
    content: string;
    channel: string;
    status: string;
    generation?: { run_id?: string };
  }[];
  search: boolean;
  template: boolean;
};
export default function EmployeeOverview({
  orgId,
  projectId,
  navigate,
  refreshKey,
  create,
  projectName,
}: {
  orgId: string;
  projectId: string;
  navigate: (view: WorkspaceView) => void;
  refreshKey: number;
  create: (tab: string, runId?: string) => void;
  projectName: string;
}) {
  const [data, setData] = useState<Summary | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    let inFlight = false;
    async function load() {
      if (inFlight) return;
      inFlight = true;
      try {
        const [
          company,
          brand,
          social,
          runs,
          daily,
          customers,
          drafts,
          agents,
          project,
        ] = await Promise.all([
          api(`/v1/projects/${projectId}/company`, orgId),
          api(`/v1/projects/${projectId}/brand`, orgId),
          api(`/v1/projects/${projectId}/social`, orgId),
          api(`/v1/projects/${projectId}/workflows`, orgId),
          api(`/v1/projects/${projectId}/daily`, orgId),
          api(`/v1/projects/${projectId}/customers`, orgId),
          api(`/projects/${projectId}/drafts`, orgId),
          api("/v1/agents", orgId),
          api(`/projects/${projectId}`, orgId),
        ]);
        if (active) {
          setError("");
          setData({
            personal: project.mode === "personal",
            metric: goalLabels[project.personal_goal] || "Audience progress",
            company: project.mode === "personal" || !!company.problem,
            brand: brand.latest?.status === "approved",
            accounts: social.accounts.filter(
              (a: { status: string }) => a.status === "connected",
            ).length,
            runStatus: runs.runs[0]?.status || "",
            runGoal: runs.runs[0]?.goal || "",
            routine: !!daily.schedule?.enabled,
            paid:
              project.mode === "personal"
                ? project.personal_current || 0
                : customers.funnel.paying_customers,
            target:
              project.mode === "personal"
                ? project.personal_target
                : customers.funnel.target_customers,
            leads: customers.leads.filter(
              (l: { stage: string }) => !["won", "lost"].includes(l.stage),
            ).length,
            reviews: drafts.drafts.filter(
              (d: { status: string }) => d.status === "pending",
            ).length,
            recent: drafts.drafts.slice(0, 3),
            search: agents.research_configured,
            template: agents.generation_mode !== "llm",
          });
        }
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Unable to load employee status",
          );
      } finally {
        inFlight = false;
      }
    }
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [orgId, projectId, refreshKey]);
  if (error)
    return (
      <section className="panel" role="alert">
        <h2>We couldn’t load your employee’s status.</h2>
        <p>{error}</p>
        <p>
          Retrying automatically. You can still open your workspace sections.
        </p>
      </section>
    );
  if (!data)
    return (
      <section className="panel" role="status">
        Loading your employee’s progress…
      </section>
    );
  const reviewResearch = data.runStatus === "research_review";
  const working = ["queued", "running"].includes(data.runStatus);
  const next =
    !data.company || !data.brand
      ? {
          view: "profile" as const,
          title: data.personal
            ? "Introduce yourself and your personal brand"
            : "Introduce your company and yourself",
          text: data.personal
            ? "Share your niche, target audience, story and expertise, then approve your profile."
            : "Confirm the problem, solution and target customers, then save and approve your founder profile.",
          button: data.personal
            ? "Complete your personal profile"
            : "Complete company & founder",
        }
      : reviewResearch
        ? {
            view: "content" as const,
            title: "Your research needs confirmation",
            text: "Review what your employee learned before it uses that information to create content.",
            button: "Review research",
          }
        : data.reviews
          ? {
              view: "content" as const,
              title: `${data.reviews} drafts need your review`,
              text: "Review the content, make changes and approve the drafts you want to use.",
              button: "Review content",
            }
          : !data.runStatus
            ? {
                view: "content" as const,
                title: "Give your employee its first assignment",
                text: "Start research from your approved company and founder information. You’ll confirm the findings before content is created.",
                button: "Start first assignment",
              }
            : !data.routine
              ? {
                  view: "routine" as const,
                  title: "Choose when your employee prepares content",
                  text: "Set daily, weekly or monthly preparation. Publishing remains a separate approval.",
                  button: "Set working routine",
                }
              : {
                  view: "content" as const,
                  title: "Check your employee’s latest work",
                  text: "Open research, content drafts and the latest assignment status.",
                  button: "Open employee work",
                };
  const steps = [
    {
      title: data.personal ? "You & your brand" : "Company & founder",
      done: data.company && data.brand,
      view: "profile" as const,
      description: data.personal
        ? "Niche, audience, expertise and approved voice"
        : "Problem, audience, story and approved voice",
    },
    {
      title: "Social accounts",
      done: data.accounts > 0,
      view: "accounts" as const,
      description: "Connect an account or explore the demo",
    },
    {
      title: "First assignment",
      done: ["research_review", "needs_review", "research_ready"].includes(
        data.runStatus,
      ),
      view: "content" as const,
      description: "Research, confirm findings, then create content",
    },
    {
      title: "Working routine",
      done: data.routine,
      view: "routine" as const,
      description: "Choose content frequency and draft count",
    },
  ];
  const percentage = Math.min(100, Math.round((data.paid / data.target) * 100));
  const statusText = working
    ? "In progress"
    : reviewResearch
      ? "Needs confirmation"
      : data.runStatus === "failed"
        ? "Needs attention"
        : data.runStatus === "needs_review"
          ? "Ready for review"
          : data.runStatus === "research_ready"
            ? "Report ready"
            : "Ready for an assignment";
  return (
    <div className="employee-overview">
      <section className="rymu-welcome">
        <div>
          <span className="eyebrow">YOUR AI GROWTH EMPLOYEE</span>
          <h2>
            A bigger audience starts
            <br className="desktop-break" /> with your next good idea.
          </h2>
          <p>
            Make room for what you do best. Rymu helps with the research, the
            words and the plan.
          </p>
          <button onClick={() => create("research")}>
            Let’s get to work <Icon name="arrow" size={18} />
          </button>
        </div>
        <div className="welcome-collage" aria-hidden="true">
          <div className="collage-note">
            YOUR NEXT
            <br />
            <em>big thing.</em>
            <span>Starts with you ↗</span>
          </div>
          <div className="collage-orbit" />
          <img src="/rymu-mark.png" alt="" width="110" height="110" />
          <span className="collage-chip">Ideas → Content → Connections</span>
        </div>
      </section>
      <CreationChoices onChoose={create} />
      <div className="home-pulse" aria-label="Workspace snapshot">
        <button onClick={() => navigate("content")}>
          <Icon name="content" />
          <strong>{data.reviews}</strong>
          <span>drafts to review</span>
          <Icon name="arrow" size={16} />
        </button>
        <button onClick={() => navigate("accounts")}>
          <Icon name="accounts" />
          <strong>{data.accounts}</strong>
          <span>connected accounts</span>
          <Icon name="arrow" size={16} />
        </button>
        <button onClick={() => navigate("routine")}>
          <Icon name="routine" />
          <strong>{data.routine ? "On" : "Off"}</strong>
          <span>content routine</span>
          <Icon name="arrow" size={16} />
        </button>
      </div>
      <section className="recent-section" aria-label="Saved content">
        <div className="studio-section-heading">
          <div>
            <span className="eyebrow">{projectName}</span>
            <h2>Your content, all together</h2>
          </div>
          <button className="text-action" onClick={() => create("growth")}>
            Open library <Icon name="arrow" size={16} />
          </button>
        </div>
        {data.recent.length ? (
          <div className="recent-grid">
            {data.recent.map((draft) => (
              <button
                className="recent-draft"
                key={draft.id}
                data-campaign={draft.generation?.run_id}
                onClick={() => create("growth", draft.generation?.run_id)}
              >
                <span className="draft-platform">
                  {draft.channel}
                  <span>{draft.status.replaceAll("_", " ")}</span>
                </span>
                <p>{draft.content}</p>
                <span className="choice-link">
                  Review draft <Icon name="arrow" size={15} />
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="library-empty">
            <span className="empty-stack" aria-hidden="true">
              <Icon name="content" size={30} />
            </span>
            <div>
              <h3>Your first draft belongs here.</h3>
              <p>
                Introduce your brand, then let Rymu research and prepare your
                first content.
              </p>
            </div>
            <button className="secondary" onClick={() => navigate("profile")}>
              Set up my brand <Icon name="arrow" size={16} />
            </button>
          </div>
        )}
      </section>
      <div className="overview-grid">
        <section className="panel next-action">
          <div className="next-action-art" aria-hidden="true">
            <svg viewBox="0 0 180 180" fill="none">
              <circle cx="90" cy="90" r="72" />
              <circle cx="90" cy="90" r="48" />
              <path d="M18 90h144M90 18v144M40 140 140 40" />
              <circle cx="140" cy="40" r="6" />
            </svg>
          </div>
          <span className="eyebrow">
            <span className="eyebrow-dot" /> PICK UP WHERE YOU LEFT OFF
          </span>
          <h2>{next.title}</h2>
          <p>{next.text}</p>
          <button onClick={() => navigate(next.view)}>
            {next.button}
            <Icon name="arrow" size={18} />
          </button>
          <div className="next-action-foot">
            <Icon name="shield" size={14} /> Your employee prepares. You make
            the final call.
          </div>
        </section>
        <section className="panel goal-summary">
          <div className="panel-heading">
            <span className="eyebrow">YOUR GROWTH GOAL</span>
            <Icon name="target" size={18} />
          </div>
          <h3>{data.personal ? data.metric : "First paying customers"}</h3>
          <div className="goal-visual">
            <div className="goal-ring" aria-hidden="true">
              <svg viewBox="0 0 100 100">
                <circle className="goal-track" cx="50" cy="50" r="42" />
                <circle
                  className="goal-fill"
                  cx="50"
                  cy="50"
                  r="42"
                  strokeDasharray="263.9"
                  strokeDashoffset={263.9 * (1 - percentage / 100)}
                />
              </svg>
              <span>
                {percentage}
                <small>%</small>
              </span>
            </div>
            <div>
              <strong className="goal-value">
                {data.paid}
                <span> / {data.target}</span>
              </strong>
              <p>
                {data.personal ? data.metric.toLowerCase() : "paying customers"}
              </p>
            </div>
          </div>
          <progress
            className="accessible-progress"
            value={Math.min(data.paid, data.target)}
            max={data.target}
            aria-label={
              data.personal
                ? "Personal brand milestone progress"
                : "Customer milestone progress"
            }
          />
          <p className="metric-disclosure">
            <Icon name="info" size={14} />
            {data.personal
              ? "Self-reported progress. Automatic verification isn’t connected."
              : "Founder-confirmed purchases. Followers aren’t counted as customers."}
          </p>
          <button className="text-action" onClick={() => navigate("customers")}>
            {data.personal
              ? "View audience & opportunities"
              : "View customer pipeline"}
            <Icon name="arrow" size={16} />
          </button>
        </section>
      </div>
      <details className="home-more">
        <summary>Your employee setup & activity</summary>
        <div className="overview-lower-grid">
          <section className="panel readiness-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">A FEW STEPS. THEN YOU’RE READY.</span>
                <h2>Your launch checklist</h2>
              </div>
              <span className="count-pill">
                {steps.filter((s) => s.done).length} of {steps.length} ready
              </span>
            </div>
            <ol className="setup-steps">
              {steps.map((step, index) => (
                <li key={step.view}>
                  <span
                    className={
                      step.done ? "step-number complete" : "step-number"
                    }
                  >
                    {step.done ? (
                      <Icon name="check" size={15} />
                    ) : (
                      String(index + 1).padStart(2, "0")
                    )}
                  </span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.description}</p>
                  </div>
                  <button
                    className="step-action"
                    aria-label={`${step.done ? "Manage" : "Open"} ${step.title}`}
                    onClick={() => navigate(step.view)}
                  >
                    {step.done ? "Manage" : "Set up"}
                    <Icon name="arrow" size={15} />
                  </button>
                </li>
              ))}
            </ol>
          </section>
          <section className="panel employee-status">
            <div className="panel-heading">
              <span className="eyebrow">EMPLOYEE ACTIVITY</span>
              <Icon name="routine" size={18} />
            </div>
            <span
              className={`activity-badge ${working ? "is-working" : reviewResearch || data.runStatus === "failed" ? "needs-attention" : ""}`}
            >
              <span className="status-dot" />
              {statusText}
            </span>
            <h2>
              {working
                ? "Good work is in progress."
                : reviewResearch
                  ? "Your perspective comes next."
                  : data.runStatus === "failed"
                    ? "Let’s check the latest assignment."
                    : data.runStatus
                      ? "Your latest work, in one place."
                      : "Ready for your first assignment."}
            </h2>
            <p>
              {data.runGoal ||
                "Once your profile is approved, give your employee a focused growth assignment."}
            </p>
            <button className="text-action" onClick={() => navigate("content")}>
              View activity
              <Icon name="arrow" size={16} />
            </button>
            <div className="activity-note">
              <Icon name="shield" size={16} />
              <p>
                Research and drafts stay in review. This workflow does not
                publish automatically.
              </p>
            </div>
          </section>
        </div>
      </details>
      {(!data.search || data.template) && (
        <section className="capability-note">
          <Icon name="info" size={18} />
          <div>
            <h3>
              {data.template
                ? "Starter content mode"
                : "Research setup needs attention"}
            </h3>
            <p>
              {!data.search
                ? "Automatic research needs a configured search provider. "
                : ""}
              {data.template
                ? "Drafts currently use labeled templates. Connect a model provider for AI-written copy."
                : ""}{" "}
              Setup is managed by your workspace administrator.
            </p>
          </div>
        </section>
      )}
      <details className="workspace-footnote">
        <summary>What’s available in this workspace</summary>
        <p>
          Research, confirmation, drafts, social account connections and goal
          tracking are available. Interview capture and avatar onboarding
          include a labeled demo. Use Content studio for provider-backed
          interview processing, Tavus videos and approved Facebook Page
          scheduling. Administrator setup is required; other-channel publishing
          remains separate.
        </p>
      </details>
    </div>
  );
}
