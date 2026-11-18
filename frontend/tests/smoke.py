"""Browser smoke: run the API on localhost:8000 and frontend on localhost:3000 first."""

import os
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def main():
    with sync_playwright() as p:
        executable = os.getenv("CHROMIUM_PATH")
        browser = p.chromium.launch(
            **({"executable_path": executable} if executable else {})
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
        page.get_by_label("What does it do?").fill(
            "Helps small teams measure useful customer outcomes."
        )
        page.get_by_label("Who is it for?").fill("Small software teams")
        page.get_by_role("button", name="Create project", exact=True).click()
        expect(
            page.get_by_role("heading", name="Browser Growth Test", exact=True)
        ).to_be_visible()
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
        page.get_by_role("button", name="Prepare campaign drafts").click()
        expect(page.get_by_role("button", name="Approve draft")).to_have_count(2)
        page.get_by_role("button", name="Approve draft").first.click()
        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Queue approved draft").click()
        expect(
            page.get_by_text("Queued for a server-side connector.", exact=False)
        ).to_be_visible()
        page.get_by_label("signups", exact=True).fill("4")
        page.get_by_label("paying customers", exact=True).fill("1")
        page.get_by_role("button", name="Record results", exact=True).click()
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        page.reload()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        expect(page.get_by_text("queued", exact=True)).to_be_visible()
        page.get_by_role("button", name="Sign out", exact=True).click()
        page.get_by_label("Email", exact=True).fill(email)
        page.get_by_label("Password", exact=True).fill("browser-fixture-password")
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_label("Saved project").select_option(label="Browser Growth Test")
        expect(page.get_by_text("25%", exact=True)).to_be_visible()
        # Connected five-agent workflow shares one approved founder profile.
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
        expect(page.locator(".memory-status .tag")).to_have_text("Version 1 · approved")
        expect(page.get_by_text("Ready for your review", exact=True)).to_be_visible()
        page.get_by_role("button", name="Launch center", exact=True).click()
        expect(page.locator(".launch-task input").first).to_be_checked()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ), "Mobile layout overflows"
        page.set_viewport_size({"width": 1440, "height": 1000})
        screenshot = Path(os.getenv("SMOKE_SCREENSHOT", "/tmp/founderos-dashboard.png"))
        page.screenshot(path=str(screenshot), full_page=True)
        page.locator(".command-center").screenshot(
            path="/tmp/founderos-command-center.png"
        )
        assert not errors, errors
        browser.close()
        print(
            "Browser smoke passed: accounts, legacy workflow, brand approval, five-agent run, seven-day calendar edit, video script, persistent launch checklist, reload, mobile layout"
        )


if __name__ == "__main__":
    main()
