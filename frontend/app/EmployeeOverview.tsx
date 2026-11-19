"use client";
import { useEffect, useState } from "react";
import { api } from "./api";
import { goalLabels } from "./PersonalProgress";
export type WorkspaceView =
  | "overview"
  | "profile"
  | "accounts"
  | "content"
  | "customers"
  | "routine"
  | "settings";
export const workspaceViews: [WorkspaceView, string][] = [
  ["overview", "Overview"],
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
  search: boolean;
  template: boolean;
};
export default function EmployeeOverview({
  orgId,
  projectId,
  navigate,
  refreshKey,
}: {
  orgId: string;
  projectId: string;
  navigate: (view: WorkspaceView) => void;
  refreshKey: number;
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
  return (
    <div className="employee-overview">
      <div className="overview-grid">
        <section className="panel next-action">
          <span className="eyebrow">YOUR NEXT STEP</span>
          <h2>{next.title}</h2>
          <p>{next.text}</p>
          <button onClick={() => navigate(next.view)}>
            {next.button} <span aria-hidden="true">→</span>
          </button>
        </section>
        <section className="panel goal-summary">
          <span className="eyebrow">
            {data.personal ? data.metric : "PAYING CUSTOMERS"}
          </span>
          <h2>
            {data.paid}
            <span> / {data.target}</span>
          </h2>
          <progress
            value={Math.min(data.paid, data.target)}
            max={data.target}
            aria-label={
              data.personal
                ? "Personal brand milestone progress"
                : "Customer milestone progress"
            }
          />
          <p>
            {data.personal
              ? "Build a relevant audience and meaningful opportunities."
              : `${data.leads} potential customers in your pipeline`}
          </p>
          <small>
            {data.personal
              ? "Self-reported total. Automatic goal verification is not connected."
              : "Founder-confirmed purchases. Followers don’t count as sales."}
          </small>
          <button className="secondary" onClick={() => navigate("customers")}>
            {data.personal
              ? "View audience & opportunities"
              : "View customer pipeline"}
          </button>
        </section>
      </div>
      <section className="panel employee-status">
        <div>
          <span className="eyebrow">EMPLOYEE STATUS</span>
          <h2>
            {working
              ? "Your employee is working"
              : reviewResearch
                ? "Waiting for your research confirmation"
                : data.runStatus === "failed"
                  ? "The latest assignment needs attention"
                  : data.runStatus === "research_ready"
                    ? "A monitoring report is ready"
                    : data.runStatus === "needs_review"
                      ? "Content is ready for review"
                      : data.routine
                        ? "Routine enabled"
                        : "Ready when you are"}
          </h2>
          <p>
            {working
              ? "Research and preparation are in progress. No content is published by this assignment."
              : "Your decisions and your employee’s outputs stay together in Research & content."}
          </p>
        </div>
        <button className="secondary" onClick={() => navigate("content")}>
          View activity
        </button>
      </section>
      <section className="panel">
        <span className="eyebrow">GET YOUR EMPLOYEE READY</span>
        <h2>One setup. A clear path to useful work.</h2>
        <ol className="setup-steps">
          {steps.map((step, index) => (
            <li key={step.view}>
              <span
                className={step.done ? "step-number complete" : "step-number"}
              >
                {step.done ? "✓" : index + 1}
              </span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
                <small>
                  {step.done
                    ? "Ready"
                    : step.view === "accounts"
                      ? "Optional for the first research run"
                      : "Needs setup"}
                </small>
              </div>
              <button className="secondary" onClick={() => navigate(step.view)}>
                {step.done ? "Manage" : "Open"}
              </button>
            </li>
          ))}
        </ol>
      </section>
      {(!data.search || data.template) && (
        <section className="capability-note">
          <h3>
            {data.template
              ? "You’re using starter content"
              : "Research setup needs attention"}
          </h3>
          <p>
            {!data.search
              ? "Automatic research needs a search provider key. Optional source notes are available under Advanced tools. "
              : ""}
            {data.template
              ? "AI copy generation needs a configured model provider. Starter templates are labeled in the workspace."
              : ""}
          </p>
        </section>
      )}
      <p className="workspace-footnote">
        Available now: research, confirmation, drafts and customer tracking.
        Live interview processing, avatar video rendering and automatic social
        publishing are still upcoming.
      </p>
    </div>
  );
}
