"""Fast standalone browser acceptance for the new pilot screens."""
import os
from uuid import uuid4
from playwright.sync_api import expect, sync_playwright
from pilot_flow import pilot_flow

with sync_playwright() as p:
    browser = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM_PATH"]} if os.getenv("CHROMIUM_PATH") else {}))
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    response = page.request.post("http://localhost:8000/auth/register", data={"email": f"pilot-{uuid4().hex[:10]}@example.com", "password": "long-fixture-password"})
    assert response.status == 201, response.text()
    response = page.request.post("http://localhost:8000/projects", data={"product_name": "Pilot acceptance", "description": "Useful personal coaching content", "problem": "People need practical ideas for training", "audience": "People exploring fitness", "goal_customers": 50})
    assert response.status == 201, response.text()
    page.goto("http://localhost:3000")
    expect(page.get_by_role("combobox", name="Saved project", exact=True)).to_have_value(response.json()["id"], timeout=20000)
    def section(name):
        aliases = {"Advanced tools": "Settings", "Customers": "Results", "3. Research & content": "Content studio", "Overview": "Home"}
        page.get_by_role("navigation", name="Workspace sections", exact=True).get_by_role("button", name=aliases.get(name, name), exact=True).click()
    pilot_flow(page, section)
    browser.close()
    print("Pilot browser acceptance passed")
