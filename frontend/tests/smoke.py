"""Browser smoke: run the API on localhost:8000 and frontend on localhost:3000 first."""

import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        executable = os.getenv("CHROMIUM_PATH")
        browser = p.chromium.launch(
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
            ],
            **({"executable_path": executable} if executable else {}),
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        email = f"browser-{uuid4().hex[:12]}@example.com"
        page.goto(os.getenv("FRONTEND_URL", "http://localhost:3000"))
        page.get_by_role("button", name="Create an account", exact=True).click()
        page.get_by_label("Email", exact=True).fill(email)
        page.get_by_label("Password", exact=True).fill("browser-fixture-password")
        page.get_by_label("Organization name").fill("Browser Test Workspace")
        page.get_by_role("button", name="Create account", exact=True).click()
        page.get_by_label("Product name").fill("Browser Growth Test")
        page.get_by_label("Company problem", exact=True).fill(
            "Small teams struggle to understand which messages turn interest into real customers."
        )
        page.get_by_label("What does it do?").fill(
            "Helps small teams measure useful customer outcomes."
        )
        page.get_by_label("Who is it for?").fill("Small software teams")
        page.get_by_role("button", name="Create project", exact=True).click()
        expect(
            page.get_by_role("heading", name="Browser Growth Test", exact=True)
        ).to_be_visible()
        expect(
            page.get_by_role("button", name="Complete company & founder", exact=True)
        ).to_be_visible()
        expect(page.get_by_label("HTTPS source URL")).not_to_be_visible()
        nav = page.get_by_role("navigation", name="Workspace sections", exact=True)

        def section(name):
            nav.get_by_role("button", name=name, exact=True).click()

        section("2. Social accounts")
        page.get_by_role("button", name="Try demo connection flow", exact=True).click()
        demo = page.get_by_role("region", name="Social connection demo", exact=True)
        demo.get_by_role(
            "button", name="Preview Instagram connection", exact=True
        ).click()
        page.get_by_role("button", name="Cancel demo connection", exact=True).click()
        expect(
            demo.get_by_text(
                "Demo connection cancelled. No access granted.", exact=True
            )
        ).to_be_visible()
        for provider in ["Instagram", "Facebook Pages"]:
            demo.get_by_role(
                "button", name=f"Preview {provider} connection", exact=True
            ).click()
            page.get_by_role("button", name="Approve demo access", exact=True).click()
            demo.get_by_role(
                "button", name=f"Retrieve {provider} sample data", exact=True
            ).click()
            expect(demo.get_by_text("Sample followers:", exact=True)).to_be_visible()
            demo.get_by_role(
                "button", name=f"Disconnect {provider} demo", exact=True
            ).click()
            expect(
                demo.get_by_text(
                    "Demo account disconnected. Its sample data was removed.",
                    exact=True,
                )
            ).to_be_visible()
        page.get_by_role("button", name="Hide demo connection flow", exact=True).click()
        section("Advanced tools")
        page.get_by_text("Optional sources and research evidence", exact=True).click()
        page.get_by_label("HTTPS source URL").fill("https://example.com/research")
        page.get_by_label("Source title").fill("Buyer interviews")
        page.get_by_label("Relevant excerpt").fill(
            "Small teams want clearer conversion metrics."
        )
        page.get_by_role("checkbox").check()
        page.get_by_role("button", name="Add research source").click()
        expect(page.get_by_role("link", name="Buyer interviews")).to_be_visible()
        page.get_by_role("button", name="Generate growth plan").click()
        expect(page.get_by_text("Generation: template.", exact=False)).to_be_visible()
        page.get_by_text("Standalone draft generator", exact=True).click()
        page.get_by_role("button", name="Prepare campaign drafts").click()
        section("3. Research & content")
        expect(page.get_by_role("button", name="Approve draft")).to_have_count(2)
        page.get_by_role("button", name="Approve draft").first.click()
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Queue approved draft").click()
        expect(
            page.get_by_text("Queued for a server-side connector.", exact=False)
        ).to_be_visible()
        section("Advanced tools")
        page.get_by_label("signups", exact=True).fill("4")
        page.get_by_label("paying customers", exact=True).fill("1")
        page.get_by_role("button", name="Record results", exact=True).click()
        section("Advanced tools")
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        page.reload()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        section("Advanced tools")
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        section("3. Research & content")
        expect(page.get_by_text("queued", exact=True)).to_be_visible()
        page.get_by_role("button", name="Sign out", exact=True).click()
        page.get_by_label("Email", exact=True).fill(email)
        page.get_by_label("Password", exact=True).fill("browser-fixture-password")
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        section("Advanced tools")
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        # Connected five-agent workflow shares one approved founder profile.
        section("1. Company & founder")
        interview = page.get_by_role(
            "region", name="Founder video interview", exact=True
        )
        interview.get_by_role(
            "button", name="Record founder interview", exact=True
        ).click()
        expect(
            interview.get_by_role("button", name="Stop recording", exact=True)
        ).to_be_visible()
        page.wait_for_function(
            """() => { const video = document.querySelector('video[aria-label="Live interview camera preview"]'); if (!video?.srcObject) return false; window.interviewTestTracks = video.srcObject.getTracks(); return window.interviewTestTracks.length === 2; }"""
        )
        section("2. Social accounts")
        page.wait_for_function(
            "() => window.interviewTestTracks.every(track => track.readyState === 'ended')"
        )
        section("1. Company & founder")
        expect(
            interview.get_by_label("Recorded founder interview", exact=True)
        ).to_be_visible()
        interview.get_by_role(
            "button", name="Delete local interview and reset demo", exact=True
        ).click()
        interview.get_by_role("button", name="Use sample interview", exact=True).click()
        interview.get_by_role(
            "button", name="Continue to review brief", exact=True
        ).click()
        interview.get_by_role(
            "button", name="Confirm brief and continue", exact=True
        ).click()
        expect(
            interview.get_by_role("button", name="Continue to HeyGen setup", exact=True)
        ).to_be_disabled()
        interview.get_by_role("checkbox").check()
        interview.get_by_role(
            "button", name="Continue to HeyGen setup", exact=True
        ).click()
        expect(
            interview.get_by_text(
                "Provider: HeyGen · Demo adapter · Not connected", exact=True
            )
        ).to_be_visible()
        interview.get_by_role(
            "button", name="Prepare placeholder sample", exact=True
        ).click()
        expect(
            interview.get_by_text(
                "No synthetic video or cloned audio has been generated.", exact=True
            )
        ).to_be_visible()
        interview.get_by_role("checkbox").check()
        expect(
            interview.get_by_text("Demo onboarding complete.", exact=False)
        ).to_be_visible()
        interview.get_by_role(
            "button", name="Delete local interview and reset demo", exact=True
        ).click()
        expect(
            interview.get_by_role("button", name="Continue to review brief", exact=True)
        ).to_be_disabled()
        page.get_by_label("Founder name", exact=True).fill("Ada Founder")
        page.get_by_label("Your founder story", exact=True).fill(
            "I started this company after helping small teams understand their customer conversion data."
        )
        page.get_by_label("Your expertise (one per line)", exact=True).fill(
            "Customer research\nProduct analytics"
        )
        page.get_by_label(
            "Content pillars (one per line, up to five)", exact=True
        ).fill("Founder lessons\nPractical growth")
        page.get_by_label("How should your content sound?", exact=True).fill(
            "Direct, practical and warm"
        )
        page.get_by_label("Your positioning", exact=True).fill(
            "We help small software teams learn which growth messages lead to useful conversations."
        )
        page.get_by_role("button", name="Save brand version", exact=True).click()
        page.get_by_role("button", name="Approve brand version 1", exact=True).click()
        section("3. Research & content")
        page.get_by_label("Research method", exact=True).select_option("manual")
        page.get_by_label("Content cadence", exact=True).select_option("weekly")
        page.get_by_role("button", name="Start growth workflow", exact=True).click()
        expect(page.get_by_text("Ready for your review", exact=True)).to_be_visible(
            timeout=45000
        )
        expect(
            page.get_by_role("button", name="Save new revision", exact=True)
        ).to_have_count(7)
        page.get_by_label("Content draft", exact=True).first.fill(
            "A founder-edited message about useful customer conversations and the lessons we learned."
        )
        page.get_by_role("button", name="Save new revision", exact=True).first.click()
        expect(page.get_by_text("pending · revision 2", exact=True)).to_be_visible()
        page.get_by_role("button", name="Research radar", exact=True).click()
        expect(
            page.get_by_text(
                "Explore Founder lessons with Small software teams", exact=True
            )
        ).to_be_visible()
        page.get_by_role("button", name="Video studio", exact=True).click()
        expect(
            page.get_by_role("button", name="Copy video script", exact=True)
        ).to_be_visible()
        page.get_by_role("button", name="Launch center", exact=True).click()
        expect(
            page.get_by_role("heading", name="Product launch checklist", exact=True)
        ).to_be_visible()
        task = page.locator(".launch-task input").first
        task.check()
        expect(task).to_be_checked()
        expect(
            page.get_by_role("button", name="Start growth workflow", exact=True)
        ).to_be_enabled()
        page.reload()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        section("1. Company & founder")
        expect(page.locator(".memory-status .tag")).to_have_text("Version 1 · approved")
        section("3. Research & content")
        expect(page.get_by_text("Ready for your review", exact=True)).to_be_visible()
        page.get_by_role("button", name="Launch center", exact=True).click()
        expect(page.locator(".launch-task input").first).to_be_checked()
        section("Customers")
        page.get_by_label("Customer or company name", exact=True).fill("First Customer")
        page.get_by_label("Customer company website", exact=True).fill(
            "https://first-customer.example"
        )
        page.get_by_role("button", name="Add potential customer", exact=True).click()
        page.get_by_label("Lead stage", exact=True).select_option("won")
        page.get_by_label(
            "I confirm this customer has actually paid.", exact=True
        ).check()
        page.get_by_role("button", name="Save lead progress", exact=True).click()
        expect(
            page.get_by_text(
                "49 more paying customers to reach the first milestone.", exact=True
            )
        ).to_be_visible()
        # Automatic research + approval checkpoint + configurable routine.
        section("4. Working routine")
        page.get_by_label("Content frequency", exact=True).select_option("daily")
        page.get_by_label("Posts per selected day", exact=True).fill("3")
        page.get_by_label(
            "Enable recurring research and draft generation", exact=True
        ).check()
        page.get_by_role("button", name="Save content routine", exact=True).click()
        expect(
            page.get_by_text(
                "Content routine enabled. Drafts will be prepared on your selected days.",
                exact=True,
            )
        ).to_be_visible()
        pid = page.get_by_label("Saved project").input_value()
        org = page.get_by_label("Organization", exact=True).input_value()
        page.wait_for_function(
            """async ({pid,org}) => {
          const response = await fetch('http://localhost:8000/v1/projects/' + pid + '/workflows', {credentials:'include',headers:{'X-Organization-ID':org}});
          const data = await response.json(); return data.runs?.some(run => run.status === 'research_review' && run.cadence === 'daily');
        }""",
            arg={"pid": pid, "org": org},
            timeout=45000,
        )
        section("3. Research & content")
        page.get_by_role("button", name="Refresh team activity", exact=True).click()
        review_option = (
            page.get_by_label("Campaign history")
            .locator("option")
            .filter(has_text="research_review")
            .first
        )
        expect(review_option).to_have_count(1, timeout=15000)
        page.get_by_label("Campaign history").select_option(
            review_option.get_attribute("value")
        )
        expect(
            page.get_by_role(
                "button", name="Confirm research and create content", exact=True
            )
        ).to_be_visible(timeout=15000)
        expect(
            page.get_by_text("Public buyer research", exact=True).first
        ).to_be_visible()
        page.get_by_role(
            "button", name="Confirm research and create content", exact=True
        ).click()
        expect(page.get_by_text("Ready for your review", exact=True)).to_be_visible(
            timeout=45000
        )
        page.get_by_role("button", name="Content calendar", exact=True).click()
        expect(
            page.get_by_role("button", name="Save new revision", exact=True)
        ).to_have_count(3)
        section("4. Working routine")
        page.get_by_label(
            "Enable recurring research and draft generation", exact=True
        ).uncheck()
        page.get_by_label("Content frequency", exact=True).select_option("monthly")
        page.get_by_label("Preparation day of month", exact=True).fill("5")
        page.get_by_role("button", name="Save content routine", exact=True).click()
        expect(
            page.get_by_text(
                "Routine paused; unfinished recurring jobs were cancelled.", exact=True
            )
        ).to_be_visible()
        page.reload()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        section("4. Working routine")
        expect(page.get_by_label("Content frequency", exact=True)).to_have_value(
            "monthly"
        )
        expect(page.get_by_label("Posts per selected day", exact=True)).to_have_value(
            "3"
        )
        expect(page.get_by_label("Preparation day of month", exact=True)).to_have_value(
            "5"
        )
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ), "Mobile layout overflows"
        page.set_viewport_size({"width": 1440, "height": 1000})
        screenshot = Path(os.getenv("SMOKE_SCREENSHOT", "/tmp/founderos-dashboard.png"))
        page.screenshot(path=str(screenshot), full_page=True)
        section("3. Research & content")
        page.locator(".command-center").screenshot(
            path="/tmp/founderos-command-center.png"
        )
        section("Overview")
        expect(
            page.get_by_role("heading", name="Your day at a glance", exact=True)
        ).to_be_visible()
        expect(
            page.get_by_label("Customer milestone progress", exact=True)
        ).to_be_visible()
        page.screenshot(path="/tmp/founderos-overview.png", full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ), "Overview overflows on mobile"
        page.screenshot(path="/tmp/founderos-overview-mobile.png", full_page=True)
        assert not errors, errors
        browser.close()
        print(
            "Browser smoke passed: accounts, brand and company setup, research confirmation, recurring routines, 50-customer funnel, calendar, video script, reload and mobile layout"
        )


if __name__ == "__main__":
    main()
