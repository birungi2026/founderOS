# Rymu content studio design

Rymu replaces the FounderOS product identity. The chosen growth-partner symbol lives at `frontend/public/rymu-mark.png`; the wordmark is live text. Brand targets are indigo `#302399`, coral `#F47C73` and warm white `#FAF8F5`. Generated PNG pixels may vary slightly. System fonts avoid external font-service dependencies.

## Product structure

Home prioritizes creation: three illustrated entry points open video scripts, social-post calendars and research outputs in the existing coordinated workflow. Illustrations are decorative CSS artwork, not fake generated assets or playable videos. Saved content previews come from stored drafts; no sample engagement or fabricated revenue appears. Setup and employee activity are available in a disclosure, alongside real goal progress and the next required action.

A white desktop sidebar contains Home, Brand profile/Your brand, Social accounts, Content studio, Content plan, Results and Settings. The compact header shows the active project. Below 820px a persistent bottom bar provides Home, Create, Plan, Results and More. More and the header menu reveal account/project selectors and secondary navigation. The menu is a disclosure, not a focus-trapping modal. Safe-area padding keeps controls above phone system UI.

Horizontal creation cards use contained scrolling and scroll snapping on narrow phones. Forms use 16px inputs, buttons have at least 44px targets, keyboard focus remains visible and reduced-motion preferences disable decorative transforms. Desktop and phone use the same permission checks and saved state.

## Reference and boundaries

Zeely's [public project guide](https://zeely.ai/blog/setting-up-your-first-zeely-project/) and [mobile video guide](https://help.zeely.ai/en/articles/11003687-how-to-create-a-talking-head-video) informed the short setup, visual creation choices, persistent mobile navigation and saved-content concept. Rymu retains its own identity, artwork, copy and founder-research approval flow. No access to Zeely's private customer dashboard is implied.

Research confirmation and content approvals remain required. Video output is a script; interview/provider onboarding remains a labeled preview. This redesign does not implement Tavus rendering, automatic publishing, billing or an App Store release. Signup remains email/password plus a business/personal-brand choice, with automatic workspace names and the existing 12-character password requirement.

## Deployment

The intended public brand domain is `rymu.ai`; metadata and favicon use Rymu. DNS is not configured by this change. Existing API identifiers, database names, Docker service names and environment-variable names remain compatible. The runtime image now copies `public` so the logo is available in Docker deployments.
