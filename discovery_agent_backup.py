
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ERP_URL = os.getenv(
    "ERPNEXT_URL",
    "https://stage2-salma.altersense.net",
).rstrip("/")

USERNAME = os.getenv("ERPNEXT_USER", "")
PASSWORD = os.getenv("ERPNEXT_PASSWORD", "")

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
SCREENSHOT_DIR = BASE_DIR / "data" / "screenshots"

DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# LOG
# ============================================================

def log(message):
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}",
        flush=True,
    )


# ============================================================
# VISIBLE ELEMENTS
# ============================================================

def discover_elements(page):

    elements = []

    selectors = """
        button,
        input,
        textarea,
        select,
        a,
        [role="button"],
        [role="option"],
        [role="tab"],
        [contenteditable="true"]
    """

    locator = page.locator(selectors)

    try:
        count = min(locator.count(), 300)
    except Exception:
        count = 0

    for i in range(count):

        element = locator.nth(i)

        try:

            if not element.is_visible():
                continue

            tag = element.evaluate(
                "(el) => el.tagName.toLowerCase()"
            )

            item = {
                "tag": tag,
                "text": (
                    element.inner_text() or ""
                ).strip()[:200],

                "id": (
                    element.get_attribute("id")
                    or ""
                ),

                "name": (
                    element.get_attribute("name")
                    or ""
                ),

                "type": (
                    element.get_attribute("type")
                    or ""
                ),

                "placeholder": (
                    element.get_attribute("placeholder")
                    or ""
                ),

                "aria_label": (
                    element.get_attribute("aria-label")
                    or ""
                ),

                "title": (
                    element.get_attribute("title")
                    or ""
                ),

                "role": (
                    element.get_attribute("role")
                    or ""
                ),

                "value": (
                    element.get_attribute("value")
                    or ""
                ),
            }

            elements.append(item)

        except Exception:
            continue

    return elements


# ============================================================
# PAGE DISCOVERY
# ============================================================

def discover_page(page):

    data = {
        "url": page.url,
        "title": "",
        "text": "",
        "elements": [],
        "links": [],
    }

    try:
        data["title"] = page.title()
    except Exception:
        pass

    try:

        data["text"] = (
            page.locator("body")
            .inner_text(timeout=5000)
            [:20000]
        )

    except Exception:
        pass

    data["elements"] = discover_elements(page)

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    try:

        links = page.locator("a")

        count = min(
            links.count(),
            200,
        )

        for i in range(count):

            link = links.nth(i)

            try:

                if not link.is_visible():
                    continue

                text = (
                    link.inner_text() or ""
                ).strip()

                href = (
                    link.get_attribute("href")
                    or ""
                )

                if text or href:

                    data["links"].append(
                        {
                            "text": text[:200],
                            "href": href[:500],
                        }
                    )

            except Exception:
                continue

    except Exception:
        pass

    return data


# ============================================================
# SAVE DISCOVERY
# ============================================================

def save_discovery(name, data):

    safe_name = re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        name,
    )

    path = (
        DISCOVERY_DIR
        / f"{safe_name}.json"
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    log(
        f"Discovery saved: {path}"
    )


# ============================================================
# LOGIN
# ============================================================

def login(page):

    log("Checking login state...")

    if "/app" in page.url:

        log("Already logged in.")

        return True

    # --------------------------------------------------------
    # Username
    # --------------------------------------------------------

    username_selectors = [
        "input[name='usr']",
        "input[autocomplete='username']",
        "input[name='login']",
        "input[type='email']",
    ]

    username = None

    for selector in username_selectors:

        locator = page.locator(selector)

        for i in range(locator.count()):

            item = locator.nth(i)

            try:

                if item.is_visible():

                    username = item
                    break

            except Exception:
                pass

        if username:
            break

    if not username:

        raise RuntimeError(
            "Visible username field not found."
        )

    # --------------------------------------------------------
    # Password
    # --------------------------------------------------------

    password_selectors = [
        "input[name='pwd']",
        "input[name='password']",
        "input[type='password']",
    ]

    password = None

    for selector in password_selectors:

        locator = page.locator(selector)

        for i in range(locator.count()):

            item = locator.nth(i)

            try:

                if item.is_visible():

                    password = item
                    break

            except Exception:
                pass

        if password:
            break

    if not password:

        raise RuntimeError(
            "Visible password field not found."
        )

    username.fill(USERNAME)

    password.fill(PASSWORD)

    log("Credentials filled.")

    # --------------------------------------------------------
    # Login button
    # --------------------------------------------------------

    buttons = page.locator(
        "button, input[type='submit'], [role='button']"
    )

    login_button = None

    for i in range(buttons.count()):

        button = buttons.nth(i)

        try:

            if not button.is_visible():
                continue

            text = " ".join(
                [
                    button.inner_text() or "",
                    button.get_attribute("value") or "",
                    button.get_attribute("aria-label") or "",
                ]
            ).strip().lower()

            if (
                text == "login"
                or "login" in text
                or "log in" in text
                or "sign in" in text
            ):

                login_button = button
                break

        except Exception:
            continue

    if not login_button:

        raise RuntimeError(
            "Login button not found."
        )

    login_button.click()

    page.wait_for_timeout(1500)

    log(
        f"Login URL: {page.url}"
    )

    if "/app" not in page.url:

        raise RuntimeError(
            "Login may have failed."
        )

    log("LOGIN SUCCESS")

    return True


# ============================================================
# MAIN DISCOVERY
# ============================================================

def main():

    log("======================================")
    log("ERP DISCOVERY AGENT")
    log("======================================")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS,
            slow_mo=20,
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        page = context.new_page()

        try:

            # ------------------------------------------------
            # OPEN ERP
            # ------------------------------------------------

            log(
                f"Opening ERP: {ERP_URL}"
            )

            page.goto(
                ERP_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            log(
                f"Current URL: {page.url}"
            )

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # HOME
            # ------------------------------------------------

            page.goto(
                f"{ERP_URL}/app/home",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(1000)

            log(
                f"Home URL: {page.url}"
            )

            # ------------------------------------------------
            # DISCOVER HOME
            # ------------------------------------------------

            home_data = discover_page(page)

            save_discovery(
                "home",
                home_data,
            )

            # ------------------------------------------------
            # SCREENSHOT
            # ------------------------------------------------

            screenshot = (
                SCREENSHOT_DIR
                / "home_discovery.png"
            )

            page.screenshot(
                path=str(screenshot),
                full_page=True,
            )

            log(
                f"Screenshot: {screenshot}"
            )

            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            log(
                f"Visible elements: "
                f"{len(home_data['elements'])}"
            )

            log(
                f"Links discovered: "
                f"{len(home_data['links'])}"
            )

            log(
                "Discovery completed."
            )

        except Exception as exc:

            log(
                f"ERROR: {exc}"
            )

            try:

                page.screenshot(
                    path=str(
                        SCREENSHOT_DIR
                        / "discovery_failure.png"
                    ),
                    full_page=True,
                )

            except Exception:
                pass

        finally:

            context.close()
            browser.close()

    log("======================================")
    log("DISCOVERY FINISHED")
    log("======================================")


if __name__ == "__main__":
    main()
