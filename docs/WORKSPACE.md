# Rymu workspace

The signed-in workspace opens the latest saved company automatically and starts on Home. The default screen shows visual creation choices, recent saved drafts, a next action and real goal progress; setup and employee activity are tucked into a disclosure. Its values come from project, founder profile, workflow, account, routine and customer APIs; missing status is shown as loading/error rather than invented progress. Home refreshes while open and rechecks when the founder returns.

Navigation separates:

1. Brand profile (Your brand for personal workspaces): company problem, solution, target customers and differentiation, plus versioned founder story/voice approval.
2. Social accounts: real OAuth connections and a clearly labeled credential-free demo.
3. Content studio: start a coordinated assignment, confirm research, inspect the content calendar/video script/launch checklist, and review campaign drafts. Agent implementation details are collapsed.
4. Content plan: preparation frequency, count, timezone and pause/enable controls. Preparation is distinct from publishing.
5. Results: purchase progress and lead next actions. Counts remain founder-confirmed.
6. Settings: manual evidence, standalone plan/draft generators, manual results, export and organization access/audit. Creating another company also lives here once a company is selected.

Switching sections preserves in-progress form and draft state. Reloading returns to Home and loads saved server data. New founders see company creation before the workspace. Existing tenant roles and approval/publishing rules remain enforced. A local interview recorder and HeyGen onboarding preview are available under Brand profile (Your brand for personal workspaces). They are clearly labeled as a demo: live interview processing, rendered avatars and unattended social publishing remain upcoming and do not appear as completed capabilities.

The browser smoke test covers navigation, hidden manual fields on Overview, both connection demos, saved founder approval, research confirmation/resumption, revision editing, lead purchase confirmation, routine persistence and mobile overflow.

On phones a bottom bar provides Home, Create, Plan, Results and More. More reveals brand, account and workspace controls. The content cards open the corresponding output tab in the coordinated employee workspace; they do not bypass brand approval or research confirmation.
