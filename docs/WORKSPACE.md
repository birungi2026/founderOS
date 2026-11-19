# Founder-facing workspace

The signed-in workspace opens the latest saved company automatically and starts on Overview. The default screen shows one next action, paying-customer progress, employee activity and a four-step setup checklist. Its values come from project, founder profile, workflow, account, routine and customer APIs; missing status is shown as loading/error rather than invented progress. Overview refreshes while open and rechecks when the founder returns.

Navigation separates:

1. Company & founder: company problem, solution, target customers and differentiation, plus versioned founder story/voice approval.
2. Social accounts: real OAuth connections and a clearly labeled credential-free demo.
3. Research & content: start a coordinated assignment, confirm research, inspect the content calendar/video script/launch checklist, and review campaign drafts. Agent implementation details are collapsed.
4. Working routine: preparation frequency, count, timezone and pause/enable controls. Preparation is distinct from publishing.
5. Customers: purchase progress and lead next actions. Counts remain founder-confirmed.
6. Advanced tools: manual evidence, standalone plan/draft generators, manual results, export and organization access/audit. Creating another company also lives here once a company is selected.

Switching sections preserves in-progress form and draft state. Reloading returns to Overview and loads saved server data. New founders see company creation before the workspace. Existing tenant roles and approval/publishing rules remain enforced. A local interview recorder and HeyGen onboarding preview are available under Company & founder. They are clearly labeled as a demo: live interview processing, rendered avatars and unattended social publishing remain upcoming and do not appear as completed capabilities.

The browser smoke test covers navigation, hidden manual fields on Overview, both connection demos, saved founder approval, research confirmation/resumption, revision editing, lead purchase confirmation, routine persistence and mobile overflow.
