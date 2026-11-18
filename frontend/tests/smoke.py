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
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ), "Mobile layout overflows"
        page.set_viewport_size({"width": 1440, "height": 1000})
        screenshot = Path(os.getenv("SMOKE_SCREENSHOT", "/tmp/founderos-dashboard.png"))
        page.screenshot(path=str(screenshot), full_page=True)
        assert not errors, errors
        browser.close()
        print(
            "Browser smoke passed: registration, project, research, plan, draft review, queue, metrics, reload, login, mobile layout"
        )


if __name__ == "__main__":
    main()
