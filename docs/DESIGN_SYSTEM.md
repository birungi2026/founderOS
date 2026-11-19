# FounderOS dashboard design

The product uses a persistent navy sidebar, neutral workspace surfaces, restrained mint accents and a system font stack that needs no external font service. The FounderOS mark and line icons are original inline SVG/CSS, keeping the UI deterministic and lightweight. The existing functional components share the same buttons, inputs, panels, tabs, notices and content-card styles.

## Information hierarchy

- Sidebar: workspace/project selectors and Overview, Brand profile (Your brand for individuals), Social accounts, Content studio, Working routine, Customers/Audience & opportunities and Workspace settings.
- Header: location, actual workspace type and sign-out action. Account initials and organization role use signed-in user data.
- Overview: real draft-review count, active account count, saved routine state and approved profile status; a primary next action; goal progress; readiness checklist; latest assignment state.
- Goal rings are calculated from stored goal progress. They never imply historical growth or fabricate a time series. Purchases remain founder-confirmed, personal-brand totals remain self-reported, and missing account metrics stay unknown.
- Configuration limitations are quieter contextual notices. Interview/avatar demos, template generation and unavailable publishing features remain labeled. There are no fabricated customer logos, security certifications, revenue charts, testimonials or simulated activity presented as live data.

## Interaction and accessibility

At 820px and below, the sidebar becomes a collapsible navigation area with an expanded-state button. It is not a modal and does not trap focus. Navigation buttons use their visible labels as accessible names and mark the active section. Switching sections scrolls the content to the top while preserving component/form state. Keyboard focus is visible, icons are decorative, and reduced-motion preferences disable transitions. Native progress elements accompany the decorative goal rings for assistive technology.

The browser regression covers both business and personal-brand flows, mobile navigation, all four social demos, research confirmation, draft editing, interview capture teardown, customer/progress updates and routine persistence. Desktop and mobile screenshots are inspected for layout and overflow.
