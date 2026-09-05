import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

def test_erpnext_is_reachable():
    url = os.getenv("ERPNEXT_URL", "http://localhost:8000")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        assert response is not None
        assert response.ok or response.status in {401, 403}
        browser.close()
