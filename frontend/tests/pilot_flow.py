"""Real pilot evidence and local FFmpeg UI flow; no live external providers."""

import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import expect


def pilot_flow(page, section, require_drafts=False):
    section("Advanced tools")
    plan = page.get_by_role("region", name="Plan and usage", exact=True)
    expect(plan.get_by_role("heading", name="$59 per month", exact=True)).to_be_visible()
    expect(plan.get_by_role("button", name="Subscribe for $59/month", exact=True)).to_be_disabled()
    section("Customers")
    pilot = page.get_by_role("region", name="Pilot evidence", exact=True)
    pilot.get_by_text("Record a baseline or follow-up", exact=True).click()
    pilot.get_by_label("Window starts", exact=True).fill("2025-01-01")
    pilot.get_by_label("Window ends", exact=True).fill("2025-01-07")
    pilot.get_by_label("Follower total at window end", exact=True).fill("100")
    pilot.get_by_role("checkbox", name="I checked these figures.", exact=False).check()
    pilot.get_by_role("button", name="Save growth observation", exact=True).click()
    expect(pilot.get_by_text("Observation saved as operator-reported evidence.", exact=True)).to_be_visible()
    pilot.get_by_label("Observation", exact=True).select_option("followup")
    pilot.get_by_label("Window starts", exact=True).fill("2025-01-08")
    pilot.get_by_label("Window ends", exact=True).fill("2025-01-14")
    pilot.get_by_label("Follower total at window end", exact=True).fill("120")
    pilot.get_by_role("button", name="Save growth observation", exact=True).click()
    expect(pilot.get_by_text("+20 followers", exact=False)).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.set_viewport_size({"width": 1440, "height": 1000})
    section("3. Research & content")
    weekly = page.get_by_role("region", name="Weekly review", exact=True)
    if require_drafts:
        post = weekly.locator("article").filter(has=page.locator("textarea")).first
        text = post.locator("textarea")
        expect(text).to_be_visible()
        text.fill(text.input_value() + " Updated in weekly review.")
        post.get_by_role("button", name="Save post edit", exact=True).click()
        expect(weekly.get_by_text("Saved. Review the updated post before approval.", exact=True)).to_be_visible()
        post.get_by_role("button", name="Approve this draft", exact=True).click()
        expect(weekly.get_by_text("Draft approved. Publication still needs a separate approval.", exact=True)).to_be_visible()
    weekly.get_by_text("Make a clip from your own footage", exact=True).click()
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / "test.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x240:r=15:d=3", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", str(source)], check=True)
        weekly.get_by_label("Your footage", exact=True).set_input_files(str(source))
        weekly.get_by_role("button", name="Upload real footage", exact=True).click()
        expect(weekly.get_by_label("Start at (seconds)", exact=True)).to_be_visible()
        weekly.get_by_label("End at (seconds)", exact=True).fill("2")
        weekly.get_by_label("Post caption", exact=True).fill("A real clip for our weekly review.")
        weekly.get_by_label("On-screen captions (optional)", exact=True).fill("Hello from our real clip")
        weekly.get_by_role("button", name="Make vertical clip", exact=True).click()
        expect(weekly.get_by_role("button", name="Review and schedule this clip", exact=True)).to_be_visible(timeout=45000)
        page.route("https://api.rymu.test/**", lambda route: route.fulfill(response=route.fetch(url=route.request.url.replace("https://api.rymu.test", "http://localhost:8000"))))
        weekly.get_by_role("button", name="Review and schedule this clip", exact=True).click()
        journey = page.get_by_role("region", name="Create and schedule a video", exact=True)
        expect(journey.get_by_role("heading", name="Your finished video", exact=True)).to_be_visible()
        expect(journey.get_by_role("button", name="Approve and schedule this post", exact=True)).to_be_disabled()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path="/tmp/rymu-pilot-phone.png", full_page=True)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_function("() => document.querySelector('.growth-journey video')?.readyState >= 2", timeout=15000)
        page.unroute_all(behavior="wait")
    section("Overview")
