"""UI contract test. External provider outcomes are explicit fixtures, never live calls."""

import json
from datetime import UTC, datetime, timedelta

from playwright.sync_api import expect


def journey_flow(page, project_id):
    root = f"/v1/projects/{project_id}/journeys"
    state = None
    source = {
        "id": "fixture-source",
        "title": "Fixture audience research",
        "url": "https://example.com/research",
    }
    brief = {
        "founder_name": "Ada Founder",
        "story": "I help small teams keep their websites safe with clear practical guidance.",
        "expertise": ["Website security"],
        "voice": "Friendly and practical",
        "positioning": "Help small teams build safer websites.",
        "content_pillars": ["Practical security"],
        "problem": "Small teams need clearer security advice.",
        "solution": "Practical tools and guidance for website security.",
        "target_customers": "Small software teams",
        "differentiator": "Easy to understand",
    }
    calls = []

    def reply(route):
        nonlocal state
        request = route.request
        path = request.url.split("http://localhost:8000")[-1]
        if path.endswith("/social"):
            route.fulfill(
                json={
                    "accounts": [
                        {
                            "id": "fixture-page",
                            "provider": "facebook",
                            "name": "Fixture Founder Page",
                            "permissions": [
                                "pages_manage_posts",
                                "pages_read_engagement",
                            ],
                            "status": "connected",
                        }
                    ]
                }
            )
            return
        if request.method == "GET":
            result = (
                {
                    "capabilities": dict.fromkeys(
                        [
                            "workspace_enabled",
                            "transcription",
                            "model",
                            "research",
                            "video",
                            "training",
                            "publishing",
                        ],
                        True,
                    ),
                    "journeys": [state] if state else [],
                }
                if path == root
                else state
            )
            route.fulfill(json=result)
            return
        calls.append(path)
        if path.endswith("/interview?consent=yes"):
            assert request.post_data_buffer and request.headers["x-organization-id"]
            state = {
                "id": "fixture-journey",
                "created_at": "2026-11-19T12:00:00Z",
                "revision": 1,
                "status": "interview_review",
                "interview_available": True,
                "brief": brief,
                "transcript": "Explicit fixture interview transcript for browser testing.",
            }
        else:
            data = json.loads(request.post_data)
            assert data["revision"] == state["revision"]
            state = {**state, "revision": state["revision"] + 1}
            action = path.rsplit("/", 1)[-1]
            if action == "confirm-brand":
                assert data["brand"]["founder_name"] == "Ada Founder"
                state["status"] = "brand_confirmed"
            elif action == "research":
                state.update(
                    status="researching",
                    workflow={
                        "status": "research_review",
                        "research_review_hash": "a" * 64,
                        "sources": [source],
                        "steps": [
                            {
                                "agent": "research",
                                "artifact": {
                                    "company_understanding": "Small teams need practical security help.",
                                    "opportunities": [
                                        {
                                            "angle": "Explain a simple website security check",
                                            "audience_fit": "Useful to small teams",
                                            "uncertainty": "Test audience response",
                                            "evidence_ids": [source["id"]],
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                )
            elif action == "confirm-research":
                assert data["research_hash"] == "a" * 64
                state.update(
                    status="content_review",
                    workflow=None,
                    script="Here is one useful security check for your website. Start with your login settings and test them carefully.",
                    caption="A practical security check for small software teams.",
                    generation_mode="fixture",
                )
            elif action == "train":
                assert data["consent"] is True
                state["replica_id"] = "fixture-face"
            elif action == "render":
                state.update(
                    status="video_ready",
                    video_url="https://media.tavus.test/fixture.mp4",
                )
            elif action == "schedule":
                assert data["approve"] is True and data["account_id"] == "fixture-page"
                state.update(
                    status="scheduled",
                    publication={
                        "publish_at": datetime.fromisoformat(
                            data["publish_at"]
                        ).timestamp()
                    },
                )
            else:
                raise AssertionError("Unexpected UI write: " + action)
        route.fulfill(json=state)

    patterns = ["**" + root + "**", f"**/v1/projects/{project_id}/social"]
    for pattern in patterns:
        page.route(pattern, reply)
    page.route(
        "https://media.tavus.test/**",
        lambda route: route.fulfill(
            status=200,
            content_type="video/mp4",
            body=b"fixture-video-not-a-real-provider-render",
        ),
    )
    try:
        page.get_by_role("navigation", name="Workspace sections").get_by_role(
            "button", name="Your growth journey", exact=True
        ).click()
        guide = page.get_by_role("region", name="How your growth journey works")
        expect(guide).to_be_visible()
        expect(guide.locator("button, input, textarea, select, form")).to_have_count(0)
        page.get_by_role("navigation", name="Workspace sections").get_by_role(
            "button", name="Content studio", exact=True
        ).click()
        page.get_by_text("Create a video from your interview", exact=True).click()
        region = page.get_by_role("region", name="Create and schedule a video", exact=True)
        expect(
            region.get_by_role(
                "button", name="Upload interview and prepare my brief", exact=True
            )
        ).to_be_disabled()
        page.evaluate("""() => {
          window.__journeyTracks = [];
          const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
          navigator.mediaDevices.getUserMedia = async (...args) => {
            const stream = await original(...args);
            window.__journeyTracks = stream.getTracks();
            return stream;
          };
        }""")
        region.get_by_role("button", name="Record my interview", exact=True).click()
        expect(
            region.get_by_role("button", name="Stop interview recording", exact=True)
        ).to_be_visible()
        page.wait_for_timeout(1200)
        region.get_by_role(
            "button", name="Stop interview recording", exact=True
        ).click()
        expect(region.get_by_text("Ready to upload:", exact=False)).to_be_visible()
        assert page.evaluate(
            "window.__journeyTracks.every(track => track.readyState === 'ended')"
        )
        expect(
            region.get_by_label("Interview video", exact=True)
        ).not_to_have_attribute("required", "")
        region.get_by_label(
            "I agree to send this interview for transcription and a draft brand brief.",
            exact=True,
        ).check()
        region.get_by_role(
            "button", name="Upload interview and prepare my brief", exact=True
        ).click()
        expect(
            region.get_by_role(
                "heading", name="2. Check and confirm your brand", exact=True
            )
        ).to_be_visible()
        region.get_by_role("button", name="Confirm my brand", exact=True).click()
        region.get_by_role(
            "button", name="Start automatic research", exact=True
        ).click()
        expect(
            region.get_by_text("Why it fits: Useful to small teams", exact=True)
        ).to_be_visible()
        region.get_by_role(
            "button", name="Confirm research and prepare content", exact=True
        ).click()
        region.get_by_label(
            "This is my likeness and voice. I authorize Tavus to use this recording to create my video replica.",
            exact=True,
        ).check()
        region.get_by_role("button", name="Create my Tavus replica", exact=True).click()
        region.get_by_role(
            "button", name="Generate my video with Tavus", exact=True
        ).click()
        expect(
            region.get_by_role(
                "button", name="Approve and schedule this post", exact=True
            )
        ).to_be_disabled()
        region.get_by_label("Facebook Page", exact=True).select_option("fixture-page")
        when = (datetime.now(UTC) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M")
        region.get_by_label("When should this video be posted?", exact=True).fill(when)
        region.get_by_label(
            "I watched the video and approve this caption, Page and posting time.",
            exact=True,
        ).check()
        region.get_by_role(
            "button", name="Approve and schedule this post", exact=True
        ).click()
        expect(
            region.get_by_role("button", name="Cancel scheduled post", exact=True)
        ).to_be_visible()
        state.update(
            status="measured",
            observed_at=datetime.now(UTC).timestamp(),
            results={
                "processing_status": "ready",
                "metrics": {"likes": 3, "comments": 1},
                "permalink": "https://facebook.com/fixture",
            },
        )
        region.get_by_role("button", name="Refresh journey status", exact=True).click()
        expect(
            region.get_by_role("heading", name="6. Measured results", exact=True)
        ).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
            "Journey overflows on phone"
        )
        page.screenshot(path="/tmp/rymu-journey-phone.png", full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        assert len(calls) == 7
    finally:
        for pattern in patterns:
            page.unroute(pattern, reply)
        page.unroute("https://media.tavus.test/**")
        page.get_by_role("navigation", name="Workspace sections").get_by_role(
            "button", name="Home", exact=True
        ).click()
