"use client";
import { FormEvent, useEffect, useState } from "react";
import { API, api } from "./api";
import GrowthTeam from "./GrowthTeam";
import Icon from "./Icon";
import DailyEmployee from "./DailyEmployee";
import CompanyBrief from "./CompanyBrief";
import FounderInterview from "./FounderInterview";
import PersonalProgress from "./PersonalProgress";
import SocialAccounts from "./SocialAccounts";
import PlatformIntelligence from "./PlatformIntelligence";
import EmployeeOverview, {
  WorkspaceView,
  workspaceViews,
} from "./EmployeeOverview";
type Org = { id: string; name: string; role: string };
type Identity = {
  email: string;
  organizations: Org[];
  onboarding_mode?: "business" | "personal";
};
type Strategy = {
  steps: string[];
  generation_mode: string;
  citations: { id: string; url: string; title: string }[];
};
type Project = {
  id: string;
  product_name: string;
  strategy?: Strategy;
  mode?: string;
  personal_goal?: string;
  personal_target?: number;
};
type Draft = {
  id: string;
  channel: string;
  content: string;
  status: string;
  generation: { mode: string };
  revision_hash: string;
};
type Source = { id: string; url: string; title: string; excerpt: string };
type Analytics = {
  totals: Record<string, number>;
  channels: Record<string, Record<string, number>>;
};
export default function Home() {
  const [identity, setIdentity] = useState<Identity | null>(null),
    [booting, setBooting] = useState(true),
    [register, setRegister] = useState(true);
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [orgId, setOrgId] = useState(""),
    [projects, setProjects] = useState<Project[]>([]),
    [projectId, setProjectId] = useState("");
  const [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [audience, setAudience] = useState(""),
    [goal, setGoal] = useState(50);
  const [strategy, setStrategy] = useState<Strategy | null>(null),
    [drafts, setDrafts] = useState<Draft[]>([]),
    [sources, setSources] = useState<Source[]>([]);
  const [sourceUrl, setSourceUrl] = useState(""),
    [sourceTitle, setSourceTitle] = useState(""),
    [excerpt, setExcerpt] = useState(""),
    [permission, setPermission] = useState(false);
  const [analytics, setAnalytics] = useState<Analytics | null>(null),
    [channel, setChannel] = useState("manual");
  const [counts, setCounts] = useState({
    impressions: 0,
    leads: 0,
    signups: 0,
    paying_customers: 0,
  });
  const [problem, setProblem] = useState("");
  const [projectMode, setProjectMode] = useState("business"),
    [personalGoal, setPersonalGoal] = useState("followers"),
    [personalTarget, setPersonalTarget] = useState(1000);
  const activeProject = projects.find((p) => p.id === projectId);
  const personal = activeProject?.mode === "personal";
  const goalText = personal
    ? `Build a relevant audience and reach ${activeProject?.personal_target || 1000} ${(activeProject?.personal_goal || "followers").replaceAll("_", " ")}.`
    : "Convert qualified leads and followers into our first 50 paying customers.";
  const [pipelineRefresh, setPipelineRefresh] = useState(0);
  const [view, setView] = useState<WorkspaceView>("overview");
  const [navOpen, setNavOpen] = useState(false);
  const viewNames: Record<string, string> = {
    overview: "Overview",
    profile: personal ? "Your brand" : "Brand profile",
    accounts: "Social accounts",
    content: "Content studio",
    routine: "Working routine",
    customers: personal ? "Audience & opportunities" : "Customers",
    settings: "Workspace settings",
  };
  useEffect(() => {
    setView("overview");
  }, [projectId, orgId]);
  useEffect(() => {
    if (projectId) window.scrollTo({ top: 0, behavior: "auto" });
  }, [view, projectId]);
  const [memberEmail, setMemberEmail] = useState(""),
    [memberRole, setMemberRole] = useState("viewer");
  const [audit, setAudit] = useState<
    { id: string; action: string; created_at: string }[]
  >([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const role = identity?.organizations.find((o) => o.id === orgId)?.role,
    canWrite = role === "owner" || role === "editor";
  useEffect(() => {
    api("/auth/me")
      .then((me) => {
        setIdentity(me);
        setProjectMode(me.onboarding_mode || "business");
        setOrgId(me.organizations[0]?.id || "");
      })
      .catch(() => {})
      .finally(() => setBooting(false));
  }, []);
  useEffect(() => {
    let active = true;
    setProjects([]);
    setProjectId("");
    setAudit([]);
    if (orgId)
      api("/projects", orgId)
        .then((r) => {
          if (active) {
            setProjects(r.projects);
            setProjectId(r.projects[0]?.id || "");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [orgId]);
  useEffect(() => {
    let active = true;
    setDrafts([]);
    setSources([]);
    setStrategy(null);
    setAnalytics(null);
    if (projectId)
      Promise.all([
        api(`/projects/${projectId}`, orgId),
        api(`/projects/${projectId}/drafts`, orgId),
        api(`/projects/${projectId}/sources`, orgId),
        api(`/projects/${projectId}/analytics`, orgId),
      ])
        .then(([p, d, s, a]) => {
          if (active) {
            setStrategy(p.strategy || null);
            setDrafts(d.drafts);
            setSources(s.sources);
            setAnalytics(a);
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [projectId, orgId]);
  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent, action: () => Promise<void>) {
    e.preventDefault();
    void run(action);
  }
  async function authenticate() {
    try {
      await api(register ? "/auth/register" : "/auth/login", "", {
        email,
        password,
        ...(register ? { onboarding_mode: projectMode } : {}),
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : "";
      throw new Error(
        message === "Account already exists"
          ? "This email already has an account. Choose Sign in below."
          : message === "Invalid email or password"
            ? "That email and password don’t match. Please try again."
            : message === "Failed to fetch"
              ? "We couldn’t connect. Check your connection and try again."
              : message || "We couldn’t create your account. Please try again.",
      );
    }
    const me = await api("/auth/me");
    setIdentity(me);
    setProjectMode(me.onboarding_mode || "business");
    setOrgId(me.organizations[0]?.id || "");
    setPassword("");
    setShowPassword(false);
  }
  async function logout() {
    await api("/auth/logout", "", {});
    setIdentity(null);
    setRegister(false);
    setShowPassword(false);
    setOrgId("");
    setProjects([]);
    setProjectId("");
  }
  async function create() {
    const p = await api("/projects", orgId, {
      mode: projectMode,
      personal_goal: personalGoal,
      personal_target: personalTarget,
      product_name: name,
      description,
      problem: projectMode === "personal" ? "" : problem,
      audience,
      goal_customers: goal,
    });
    setProjects((old) => [p, ...old]);
    setProjectId(p.id);
    setNotice("Project saved.");
  }
  async function plan() {
    setStrategy(await api(`/projects/${projectId}/strategy`, orgId, {}));
  }
  async function generate() {
    await api(`/projects/${projectId}/drafts`, orgId, {});
    setDrafts((await api(`/projects/${projectId}/drafts`, orgId)).drafts);
  }
  async function review(id: string, decision: string) {
    const current = drafts.find((d) => d.id === id);
    const d = await api(
      `/drafts/${id}/review?decision=${decision}&revision=${current?.revision_hash || ""}`,
      orgId,
      {},
    );
    setDrafts((old) => old.map((x) => (x.id === id ? d : x)));
  }
  async function publish(id: string) {
    if (
      !window.confirm(
        "Queue this exact approved draft for a publishing connector? This does not send it now.",
      )
    )
      return;
    const r = await api(`/drafts/${id}/publish`, orgId, { confirm: true });
    setDrafts((old) =>
      old.map((x) => (x.id === id ? { ...x, status: "queued" } : x)),
    );
    setNotice(r.note);
  }
  async function addSource() {
    await api(`/projects/${projectId}/sources`, orgId, {
      url: sourceUrl,
      title: sourceTitle,
      excerpt,
      permission_confirmed: permission,
    });
    setSources((await api(`/projects/${projectId}/sources`, orgId)).sources);
    setSourceUrl("");
    setSourceTitle("");
    setExcerpt("");
    setPermission(false);
  }
  async function record() {
    await api(`/projects/${projectId}/metrics`, orgId, { channel, ...counts });
    setAnalytics(await api(`/projects/${projectId}/analytics`, orgId));
    setNotice("Metrics saved. Do not record these outcomes again as events.");
  }
  async function download() {
    const r = await fetch(`${API}/projects/${projectId}/analytics.csv`, {
      credentials: "include",
      headers: { "X-Organization-ID": orgId },
    });
    if (!r.ok) throw new Error("Export failed");
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "founderos-analytics.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <main
      className={
        identity
          ? `app-shell ${projectId ? "employee-workspace" : ""}`
          : "auth-shell"
      }
    >
      {identity && (
        <aside
          className={`app-sidebar ${navOpen ? "is-open" : ""}`}
          aria-label="Main navigation"
        >
          <div className="sidebar-brand">
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                setView("overview");
                setNavOpen(false);
              }}
              aria-label="FounderOS overview"
            >
              <span className="brand-mark" aria-hidden="true">
                F<span />
              </span>
              Founder<span className="brand-light">OS</span>
            </a>
            <button
              type="button"
              className="mobile-nav-toggle"
              aria-label={navOpen ? "Close navigation" : "Open navigation"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen(!navOpen)}
            >
              <Icon name="menu" />
            </button>
          </div>
          <div className="sidebar-body">
            <span className="sidebar-caption">YOUR WORKSPACE</span>
            <fieldset disabled={busy}>
              {" "}
              <section className="workspace">
                <label>
                  {personal ? "Workspace" : "Organization"}
                  <select
                    aria-label="Organization"
                    value={orgId}
                    onChange={(e) => setOrgId(e.target.value)}
                  >
                    {identity.organizations.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name} · {o.role}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Saved project
                  <select
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">Select a project</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.product_name}
                      </option>
                    ))}
                  </select>
                </label>
              </section>
            </fieldset>
            {projectId ? (
              <nav className="workspace-nav" aria-label="Workspace sections">
                {workspaceViews.map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    aria-current={view === id ? "page" : undefined}
                    aria-label={viewNames[id]}
                    onClick={() => {
                      setView(id);
                      setNavOpen(false);
                    }}
                  >
                    <Icon name={id} />
                    <span>{viewNames[id]}</span>
                    {view === id && (
                      <span className="nav-active-dot" aria-hidden="true" />
                    )}
                  </button>
                ))}
              </nav>
            ) : (
              <p className="sidebar-empty">
                Create a workspace to get started.
              </p>
            )}
            <div className="sidebar-trust">
              <Icon name="shield" />
              <div>
                <strong>You stay in control</strong>
                <p>Review the research. Approve the content.</p>
              </div>
            </div>
            <div className="sidebar-person">
              <span className="user-avatar">
                {identity.email.slice(0, 2).toUpperCase()}
              </span>
              <div>
                <strong>{identity.email.split("@")[0]}</strong>
                <span>{role || "Workspace member"}</span>
              </div>
            </div>
          </div>
        </aside>
      )}
      <div className="main-stage">
        <header className="app-topbar">
          {identity ? (
            <div className="topbar-breadcrumb">
              <span>Workspace</span>
              <span aria-hidden="true">/</span>
              <strong>{projectId ? viewNames[view] : "Get started"}</strong>
            </div>
          ) : (
            <a className="auth-brand" href="/">
              FounderOS
            </a>
          )}
          {identity && (
            <div className="topbar-mode">
              <span className="status-dot" />{" "}
              {personal ? "Personal brand" : "Business workspace"}
            </div>
          )}
          {identity && (
            <button disabled={busy} onClick={() => run(logout)}>
              <Icon name="logout" size={16} /> Sign out
            </button>
          )}
        </header>
        <h1 className={identity ? "workspace-headline" : ""}>
          {identity ? (
            "Your growth employee."
          ) : (
            <>{register ? "Your growth starts here." : "Welcome back."}</>
          )}
        </h1>
        <p className="intro" hidden={!!identity && !!projectId}>
          {identity
            ? "You’re in. Tell us a little about what you want to grow."
            : projectMode === "personal"
              ? "Share what you know. Reach people who care."
              : "Get help with research and content. Keep control of what gets shared."}
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
        {booting ? (
          <p>Restoring your workspace…</p>
        ) : !identity ? (
          <section className="panel auth simple-auth">
            <span className="eyebrow">
              {register ? "LET’S GET STARTED" : "WELCOME BACK"}
            </span>
            <h2>{register ? "Create your account" : "Sign in"}</h2>
            <p className="auth-subtitle">
              {register
                ? "Just your email and a password. You can add the details later."
                : "Pick up where you left off."}
            </p>
            <form onSubmit={(e) => submit(e, authenticate)}>
              <fieldset disabled={busy}>
                <label>
                  Email
                  <input
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    autoCapitalize="none"
                    spellCheck={false}
                    placeholder="you@example.com"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
                <label>
                  Password
                  <div className="password-control">
                    <input
                      aria-label="Password"
                      type={showPassword ? "text" : "password"}
                      autoComplete={
                        register ? "new-password" : "current-password"
                      }
                      minLength={12}
                      maxLength={128}
                      required
                      value={password}
                      aria-describedby={register ? "password-hint" : undefined}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </label>
                {register && (
                  <p id="password-hint" className="form-hint">
                    Use at least 12 characters. A few words together work well.
                  </p>
                )}
                {register && (
                  <fieldset className="signup-choice">
                    <legend>What would you like to grow?</legend>
                    {[
                      {
                        value: "business",
                        title: "My business",
                        text: "Find customers for what I’m building.",
                      },
                      {
                        value: "personal",
                        title: "My personal brand",
                        text: "Grow my audience and find opportunities.",
                      },
                    ].map((choice) => (
                      <label
                        key={choice.value}
                        className={
                          projectMode === choice.value ? "selected" : ""
                        }
                      >
                        <input
                          type="radio"
                          name="signup-goal"
                          aria-label={choice.title}
                          value={choice.value}
                          checked={projectMode === choice.value}
                          onChange={() => setProjectMode(choice.value)}
                        />
                        <span>
                          <strong>{choice.title}</strong>
                          <small>{choice.text}</small>
                        </span>
                      </label>
                    ))}
                  </fieldset>
                )}
                <button className="auth-primary" type="submit">
                  {busy
                    ? register
                      ? "Creating your account…"
                      : "Signing you in…"
                    : register
                      ? "Create account"
                      : "Sign in"}
                  <Icon name="arrow" size={17} />
                </button>
                <p className="auth-switch">
                  {register ? "Already have an account?" : "New here?"}{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setRegister(!register);
                      setShowPassword(false);
                      setError("");
                    }}
                  >
                    {register ? "Sign in" : "Create an account"}
                  </button>
                </p>
              </fieldset>
            </form>
            {register && (
              <p className="auth-reassurance">
                <Icon name="shield" size={15} />
                You can connect your social accounts when you’re ready.
              </p>
            )}
          </section>
        ) : (
          <fieldset disabled={busy}>
            {canWrite && (!projectId || view === "settings") && (
              <details className="panel" open={!projectId}>
                <summary>
                  {projectId
                    ? "Create another growth workspace"
                    : projectMode === "personal"
                      ? "Start here: introduce your personal brand"
                      : "Start here: tell us about your company"}
                </summary>
                <form onSubmit={(e) => submit(e, create)}>
                  <label>
                    Workspace purpose
                    <select
                      aria-label="Workspace purpose"
                      value={projectMode}
                      onChange={(e) => setProjectMode(e.target.value)}
                    >
                      <option value="business">Grow my business</option>
                      <option value="personal">Build my personal brand</option>
                    </select>
                  </label>
                  <label>
                    {projectMode === "personal"
                      ? "Your name or brand"
                      : "Product name"}
                    <input
                      required
                      minLength={2}
                      maxLength={100}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </label>
                  {projectMode !== "personal" && (
                    <label>
                      Company problem
                      <textarea
                        aria-label="Company problem"
                        required
                        minLength={10}
                        maxLength={2000}
                        value={problem}
                        onChange={(e) => setProblem(e.target.value)}
                      />
                    </label>
                  )}
                  <label>
                    {projectMode === "personal"
                      ? "Your niche and expertise"
                      : "What does it do?"}
                    <textarea
                      required
                      minLength={10}
                      maxLength={2000}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                    />
                  </label>
                  <div className="grid">
                    <label>
                      {projectMode === "personal"
                        ? "Who do you want to reach?"
                        : "Who is it for?"}
                      <input
                        required
                        minLength={3}
                        maxLength={500}
                        value={audience}
                        onChange={(e) => setAudience(e.target.value)}
                      />
                    </label>
                    {projectMode === "personal" ? (
                      <>
                        <label>
                          Your personal brand goal
                          <select
                            aria-label="Personal brand outcome"
                            value={personalGoal}
                            onChange={(e) => setPersonalGoal(e.target.value)}
                          >
                            <option value="followers">
                              Relevant followers
                            </option>
                            <option value="newsletter_subscribers">
                              Newsletter subscribers
                            </option>
                            <option value="inquiries">
                              Qualified inquiries / opportunities
                            </option>
                          </select>
                        </label>
                        <label>
                          Personal brand target
                          <input
                            type="number"
                            min={1}
                            max={10000000}
                            required
                            value={personalTarget}
                            onChange={(e) =>
                              setPersonalTarget(Number(e.target.value))
                            }
                          />
                        </label>
                      </>
                    ) : (
                      <label>
                        Customer goal
                        <input
                          type="number"
                          min={1}
                          max={10000}
                          required
                          value={goal}
                          onChange={(e) => setGoal(Number(e.target.value))}
                        />
                      </label>
                    )}
                  </div>
                  <button>Create project</button>
                </form>
              </details>
            )}
            {projectId && (
              <>
                <div className="section-title">
                  <span>
                    {personal ? "YOUR PERSONAL BRAND" : "YOUR COMPANY"}
                  </span>
                  <h2>
                    {projects.find((p) => p.id === projectId)?.product_name}
                  </h2>
                </div>
                <section className="view-description" aria-live="polite">
                  <h2>
                    {view === "overview"
                      ? "Your day at a glance"
                      : personal && view === "customers"
                        ? "Audience & opportunities"
                        : personal && view === "profile"
                          ? "You & your brand"
                          : workspaceViews
                              .find(([id]) => id === view)?.[1]
                              .replace(/^\d\. /, "")}
                  </h2>
                  <p>
                    {
                      {
                        overview:
                          "One next step, current activity and progress toward your goal.",
                        profile: personal
                          ? "Share your niche, audience, expertise and voice. A company or paid offer is optional."
                          : "Confirm your business context and teach your employee your story and voice.",
                        accounts:
                          "Grant account access, or try the sample connection flow without API keys.",
                        content:
                          "Start an assignment, confirm the research and review the resulting drafts.",
                        customers: personal
                          ? "Track audience growth, subscribers or qualified opportunities against your chosen goal."
                          : "Track real buyer conversations and confirmed purchases.",
                        routine:
                          "Choose how often your employee prepares content. This does not enable automatic publishing.",
                        settings:
                          "Optional manual sources, standalone tools, metric entry and team administration.",
                      }[view]
                    }
                  </p>
                </section>
                {view === "overview" && (
                  <div>
                    <EmployeeOverview
                      key={orgId + projectId + view}
                      orgId={orgId}
                      projectId={projectId}
                      navigate={setView}
                      refreshKey={pipelineRefresh}
                    />
                  </div>
                )}
                {view === "profile" && (
                  <div className="journey-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setView("accounts")}
                    >
                      Next: connect social accounts →
                    </button>
                    <p>
                      Save and approve your{" "}
                      {personal ? "personal brand" : "founder"} profile below
                      before starting an assignment.
                    </p>
                  </div>
                )}
                {view === "accounts" && (
                  <div className="journey-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setView("content")}
                    >
                      Next: research & content →
                    </button>
                    <p>
                      You can skip connecting accounts while you explore the
                      demo.
                    </p>
                  </div>
                )}
                <div hidden={view !== "accounts"}>
                  <SocialAccounts
                    key={"social" + orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                    isOwner={role === "owner"}
                  />
                </div>
                <div
                  hidden={
                    (view !== "customers" && view !== "routine") ||
                    (personal && view === "customers")
                  }
                  data-employee-view={view}
                >
                  <DailyEmployee
                    key={"daily" + orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                    canWrite={canWrite}
                    isOwner={role === "owner"}
                    refreshKey={pipelineRefresh}
                    section={view}
                    goalText={goalText}
                  />
                </div>
                {personal && view === "customers" && (
                  <PersonalProgress
                    key={orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                    canWrite={canWrite}
                  />
                )}
                <div hidden={view !== "profile"}>
                  <FounderInterview
                    key={"interview" + orgId + projectId}
                    canWrite={canWrite}
                    active={view === "profile"}
                    personal={personal}
                  />
                  <CompanyBrief
                    personal={personal}
                    key={"company" + orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                    canWrite={canWrite}
                  />
                </div>
                <div hidden={view !== "content"}>
                  <PlatformIntelligence
                    key={"platforms" + orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                  />
                </div>
                <div
                  hidden={view !== "profile" && view !== "content"}
                  data-team-view={view}
                >
                  <GrowthTeam
                    key={orgId + projectId}
                    orgId={orgId}
                    projectId={projectId}
                    canWrite={canWrite}
                    sourceCount={sources.length}
                    goalText={goalText}
                    personal={personal}
                    isOwner={role === "owner"}
                    onComplete={async () => {
                      setDrafts(
                        (await api(`/projects/${projectId}/drafts`, orgId))
                          .drafts,
                      );
                      setSources(
                        (await api(`/projects/${projectId}/sources`, orgId))
                          .sources,
                      );
                      setPipelineRefresh((value) => value + 1);
                    }}
                  />
                </div>
                <div hidden={view !== "settings"}>
                  <details className="panel">
                    <summary>Optional sources and research evidence</summary>
                    <p>
                      The growth employee collects search evidence automatically
                      when the search service is connected. You can optionally
                      add your own research here. Search excerpts and supplied
                      notes are evidence to assess, not independently verified
                      facts.
                    </p>
                    {sources.map((s) => (
                      <article key={s.id}>
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title}
                        </a>
                        <p>{s.excerpt}</p>
                      </article>
                    ))}
                    {canWrite && (
                      <form onSubmit={(e) => submit(e, addSource)}>
                        <label>
                          HTTPS source URL
                          <input
                            type="url"
                            required
                            value={sourceUrl}
                            onChange={(e) => setSourceUrl(e.target.value)}
                          />
                        </label>
                        <label>
                          Source title
                          <input
                            minLength={2}
                            maxLength={200}
                            required
                            value={sourceTitle}
                            onChange={(e) => setSourceTitle(e.target.value)}
                          />
                        </label>
                        <label>
                          Relevant excerpt
                          <textarea
                            minLength={10}
                            maxLength={4000}
                            required
                            value={excerpt}
                            onChange={(e) => setExcerpt(e.target.value)}
                          />
                        </label>
                        <label className="check">
                          <input
                            type="checkbox"
                            required
                            checked={permission}
                            onChange={(e) => setPermission(e.target.checked)}
                          />
                          I reviewed this source and have permission to use the
                          excerpt.
                        </label>
                        <button>Add research source</button>
                      </form>
                    )}
                  </details>
                  <section className="panel">
                    <span className="eyebrow">OPTIONAL / QUICK PLAN</span>
                    <h2>Quick growth plan.</h2>
                    <p>
                      This standalone tool uses product details. Use the
                      coordinated team above for a brand-aware weekly campaign.
                    </p>
                    {canWrite && (
                      <button onClick={() => run(plan)}>
                        Generate growth plan
                      </button>
                    )}
                    {strategy && (
                      <>
                        <small>
                          Generation: {strategy.generation_mode}.
                          Recommendations require your judgment.
                        </small>
                        <ol>
                          {strategy.steps.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ol>
                        {strategy.citations.map((s) => (
                          <a
                            className="citation"
                            key={s.id}
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {s.title}
                          </a>
                        ))}
                      </>
                    )}
                  </section>
                </div>
                <div hidden={view !== "content"}>
                  <section className="panel">
                    <span className="eyebrow">CAMPAIGN APPROVAL INBOX</span>
                    <h2>Review your campaign content.</h2>
                    {!drafts.length && (
                      <p>
                        No drafts yet. Start a growth workflow above to prepare
                        content using your approved founder profile.
                      </p>
                    )}
                    <p>
                      Review approves a draft. Owners can then explicitly queue
                      it. No messages are automatically sent.
                    </p>
                    {drafts.map((d) => (
                      <article key={d.id}>
                        <div className="draft-heading">
                          <strong>{d.channel.toUpperCase()}</strong>
                          <span className="tag">{d.status}</span>
                        </div>
                        <p className="copy">{d.content}</p>
                        <small>Generation: {d.generation.mode}</small>
                        {canWrite && d.status === "pending" && (
                          <div>
                            <button
                              onClick={() =>
                                run(() => review(d.id, "approved"))
                              }
                            >
                              Approve draft
                            </button>
                            <button
                              className="secondary"
                              onClick={() =>
                                run(() => review(d.id, "rejected"))
                              }
                            >
                              Reject
                            </button>
                          </div>
                        )}
                        {role === "owner" && d.status === "approved" && (
                          <button onClick={() => run(() => publish(d.id))}>
                            Queue approved draft
                          </button>
                        )}
                      </article>
                    ))}
                  </section>
                </div>
                <div hidden={view !== "settings"}>
                  <details className="panel">
                    <summary>Standalone draft generator</summary>
                    <p>
                      This optional tool uses the quick plan instead of the
                      coordinated employee workflow.
                    </p>
                    {canWrite && (
                      <button onClick={() => run(generate)}>
                        Prepare campaign drafts
                      </button>
                    )}
                  </details>
                  <section className="panel">
                    <span className="eyebrow">MANUAL RESULTS</span>
                    <h2>Track outcomes, not guesses.</h2>
                    <p>
                      Record incremental results once. API events are added to
                      these totals.
                    </p>
                    {canWrite && (
                      <form onSubmit={(e) => submit(e, record)}>
                        <label>
                          Channel
                          <input
                            minLength={2}
                            maxLength={100}
                            required
                            value={channel}
                            onChange={(e) => setChannel(e.target.value)}
                          />
                        </label>
                        <div className="grid">
                          {Object.entries(counts).map(([key, value]) => (
                            <label key={key}>
                              {key.replaceAll("_", " ")}
                              <input
                                type="number"
                                min={0}
                                required
                                value={value}
                                onChange={(e) =>
                                  setCounts((old) => ({
                                    ...old,
                                    [key]: Number(e.target.value),
                                  }))
                                }
                              />
                            </label>
                          ))}
                        </div>
                        <button>Record results</button>
                      </form>
                    )}
                    <button
                      className="secondary"
                      onClick={() =>
                        run(async () =>
                          setAnalytics(
                            await api(
                              `/projects/${projectId}/analytics`,
                              orgId,
                            ),
                          ),
                        )
                      }
                    >
                      Refresh analytics
                    </button>
                    <button className="secondary" onClick={() => run(download)}>
                      Export CSV
                    </button>
                    {analytics && (
                      <>
                        <div className="stats">
                          {Object.entries(analytics.totals).map(
                            ([key, value]) => (
                              <div key={key}>
                                <strong>
                                  {value}
                                  {key.endsWith("rate") ? "%" : ""}
                                </strong>
                                <span>{key.replaceAll("_", " ")}</span>
                              </div>
                            ),
                          )}
                        </div>
                        <div className="table-wrap">
                          <table>
                            <caption>Results by channel</caption>
                            <thead>
                              <tr>
                                <th>Channel</th>
                                <th>Impressions</th>
                                <th>Leads</th>
                                <th>Signups</th>
                                <th>Customers</th>
                              </tr>
                            </thead>
                            <tbody>
                              {Object.entries(analytics.channels).map(
                                ([c, n]) => (
                                  <tr key={c}>
                                    <td>{c}</td>
                                    <td>{n.impressions}</td>
                                    <td>{n.leads}</td>
                                    <td>{n.signups}</td>
                                    <td>{n.paying_customers}</td>
                                  </tr>
                                ),
                              )}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </section>
                </div>
              </>
            )}
            {role === "owner" && (!projectId || view === "settings") && (
              <details className="panel">
                <summary>Organization access and audit</summary>
                <p>Add an existing registered user to this organization.</p>
                <form
                  onSubmit={(e) =>
                    submit(e, async () => {
                      await api("/organization/members", orgId, {
                        email: memberEmail,
                        role: memberRole,
                      });
                      setNotice("Organization access updated.");
                    })
                  }
                >
                  <label>
                    Member email
                    <input
                      type="email"
                      required
                      value={memberEmail}
                      onChange={(e) => setMemberEmail(e.target.value)}
                    />
                  </label>
                  <label>
                    Role
                    <select
                      value={memberRole}
                      onChange={(e) => setMemberRole(e.target.value)}
                    >
                      <option value="viewer">Viewer</option>
                      <option value="editor">Editor</option>
                    </select>
                  </label>
                  <button>Save member access</button>
                </form>
                <button
                  className="secondary"
                  onClick={() =>
                    run(async () =>
                      setAudit(
                        (await api("/organization/audit", orgId)).events,
                      ),
                    )
                  }
                >
                  Load audit log
                </button>
                <ul>
                  {audit.map((a) => (
                    <li key={a.id}>
                      {new Date(a.created_at).toLocaleString()} · {a.action}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {busy && <p role="status">Saving your changes…</p>}
          </fieldset>
        )}
        <footer className="app-footer">
          <span>© FounderOS</span>
          <span>
            <Icon name="shield" size={14} /> Approval-based workflows · Your
            results, honestly measured.
          </span>
        </footer>
      </div>
    </main>
  );
}
