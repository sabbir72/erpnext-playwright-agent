import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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

KNOWLEDGE_DIR = BASE_DIR / "knowledge" / "doctypes"
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
SCREENSHOT_DIR = BASE_DIR / "data" / "screenshots"

KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
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
# SAFE NAME
# ============================================================

def safe_name(value):
    return re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        value.strip(),
    ).strip("_").lower()


# ============================================================
# FIND VISIBLE ELEMENT
# ============================================================

def first_visible(page, selectors):

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(count):

                item = locator.nth(i)

                try:

                    if item.is_visible():
                        return item

                except Exception:
                    continue

        except Exception:
            continue

    return None


# ============================================================
# LOGIN
# ============================================================

def login(page):

    log("Checking login state...")

    if "/app" in page.url:
        log("Already logged in.")
        return

    username = first_visible(
        page,
        [
            "input[name='usr']",
            "input[autocomplete='username']",
            "input[name='login']",
            "input[type='email']",
        ],
    )

    password = first_visible(
        page,
        [
            "input[name='pwd']",
            "input[name='password']",
            "input[type='password']",
        ],
    )

    if not username:
        raise RuntimeError(
            "Visible username field not found."
        )

    if not password:
        raise RuntimeError(
            "Visible password field not found."
        )

    if not USERNAME or not PASSWORD:
        raise RuntimeError(
            "ERPNEXT_USER / ERPNEXT_PASSWORD missing from .env"
        )

    username.fill(USERNAME)
    password.fill(PASSWORD)

    log("Credentials filled.")

    login_button = first_visible(
        page,
        [
            "button:has-text('Login')",
            "button:has-text('Log In')",
            "button:has-text('Sign In')",
            "input[type='submit']",
        ],
    )

    if not login_button:
        raise RuntimeError(
            "Visible Login button not found."
        )

    login_button.click()

    page.wait_for_timeout(1500)

    if "/app" not in page.url:
        raise RuntimeError(
            f"Login failed. Current URL: {page.url}"
        )

    log(
        f"LOGIN SUCCESS: {page.url}"
    )


# ============================================================
# PAGE ELEMENT DISCOVERY
# ============================================================

def discover_elements(page):

    result = []

    selector = """
        input,
        textarea,
        select,
        button,
        a,
        [role="button"],
        [role="tab"],
        [role="option"],
        [contenteditable="true"]
    """

    try:
        locator = page.locator(selector)
        count = min(locator.count(), 500)
    except Exception:
        return result

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

                "class": (
                    element.get_attribute("class")
                    or ""
                ),

                "value": (
                    element.get_attribute("value")
                    or ""
                ),
            }

            result.append(item)

        except Exception:
            continue

    return result


# ============================================================
# LABEL DISCOVERY
# ============================================================

def discover_labels(page):

    labels = []

    selectors = [
        "label",
        ".frappe-control .control-label",
        ".form-group .control-label",
        "[class*='label']",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)
            count = min(locator.count(), 500)

            for i in range(count):

                element = locator.nth(i)

                try:

                    if not element.is_visible():
                        continue

                    text = (
                        element.inner_text() or ""
                    ).strip()

                    if text and text not in labels:
                        labels.append(text[:200])

                except Exception:
                    continue

        except Exception:
            continue

    return labels


# ============================================================
# BUTTON DISCOVERY
# ============================================================

def discover_buttons(page):

    buttons = []

    locator = page.locator(
        "button, [role='button'], input[type='button'], input[type='submit']"
    )

    try:
        count = min(locator.count(), 300)
    except Exception:
        count = 0

    for i in range(count):

        button = locator.nth(i)

        try:

            if not button.is_visible():
                continue

            text = " ".join(
                [
                    button.inner_text() or "",
                    button.get_attribute("value") or "",
                    button.get_attribute("aria-label") or "",
                    button.get_attribute("title") or "",
                ]
            ).strip()

            if text:
                buttons.append(text[:200])

        except Exception:
            continue

    return list(dict.fromkeys(buttons))


# ============================================================
# PAGE SNAPSHOT
# ============================================================

def snapshot(page, doctype):

    data = {
        "doctype": doctype,
        "url": page.url,
        "title": "",
        "page_text": "",
        "labels": [],
        "buttons": [],
        "elements": [],
        "captured_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }

    try:
        data["title"] = page.title()
    except Exception:
        pass

    try:
        data["page_text"] = (
            page.locator("body")
            .inner_text(timeout=5000)
        )[:30000]
    except Exception:
        pass

    data["labels"] = discover_labels(page)
    data["buttons"] = discover_buttons(page)
    data["elements"] = discover_elements(page)

    return data


# ============================================================
# SEARCH DOCTYPE
# ============================================================

def search_doctype(page, doctype):

    log(
        f"Searching for Doctype: {doctype}"
    )

    # --------------------------------------------------------
    # Go Home
    # --------------------------------------------------------

    page.goto(
        f"{ERP_URL}/app/home",
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(1000)

    log(
        f"Home: {page.url}"
    )

    # --------------------------------------------------------
    # Possible ERPNext global search inputs
    # --------------------------------------------------------

    search_selectors = [
        "input[placeholder*='Search']",
        "input[placeholder*='search']",
        "input[placeholder*='typing']",
        "input[aria-label*='Search']",
        "input[data-original-title*='Search']",
        ".awesomplete input",
        ".navbar-search input",
        "input[type='search']",
    ]

    search = first_visible(
        page,
        search_selectors,
    )

    # --------------------------------------------------------
    # If not directly visible, inspect buttons/links
    # --------------------------------------------------------

    if not search:

        log(
            "Search input not immediately visible."
        )

        candidates = [
            "button:has-text('Search')",
            "[role='button']:has-text('Search')",
            "a:has-text('Search')",
        ]

        search_button = first_visible(
            page,
            candidates,
        )

        if search_button:

            try:
                search_button.click()
                page.wait_for_timeout(500)
            except Exception:
                pass

            search = first_visible(
                page,
                search_selectors,
            )

    if not search:

        # Last attempt: inspect page for input fields
        inputs = page.locator("input")

        try:

            count = min(inputs.count(), 100)

            for i in range(count):

                item = inputs.nth(i)

                if not item.is_visible():
                    continue

                placeholder = (
                    item.get_attribute("placeholder")
                    or ""
                ).lower()

                aria = (
                    item.get_attribute("aria-label")
                    or ""
                ).lower()

                if (
                    "search" in placeholder
                    or "search" in aria
                    or "typing" in placeholder
                ):
                    search = item
                    break

        except Exception:
            pass

    if not search:

        raise RuntimeError(
            "Could not find visible ERPNext Search input."
        )

    log("Search input found.")

    search.fill(doctype)

    page.wait_for_timeout(1500)

    # --------------------------------------------------------
    # Save screenshot of results
    # --------------------------------------------------------

    page.screenshot(
        path=str(
            SCREENSHOT_DIR
            / f"{safe_name(doctype)}_search.png"
        ),
        full_page=True,
    )

    log(
        "Search results screenshot saved."
    )

    # --------------------------------------------------------
    # Read results
    # --------------------------------------------------------

    text = ""

    try:
        text = (
            page.locator("body")
            .inner_text(timeout=5000)
        )
    except Exception:
        pass

    if doctype.lower() not in text.lower():

        log(
            "Warning: Doctype text not detected yet."
        )

    else:

        log(
            f"'{doctype}' appears in page."
        )

    return text


# ============================================================
# OPEN DOCTYPE WITHOUT NEW/SAVE
# ============================================================

def open_doctype(page, doctype):

    log(
        f"Looking for '{doctype}' search result..."
    )

    # IMPORTANT:
    # We only click an exact matching search result.
    # We NEVER click New here.

    candidates = [
        page.get_by_text(
            doctype,
            exact=True,
        ),

        page.get_by_role(
            "option",
            name=doctype,
            exact=True,
        ),
    ]

    for candidate in candidates:

        try:

            count = candidate.count()

            for i in range(count):

                item = candidate.nth(i)

                if not item.is_visible():
                    continue

                log(
                    f"Found visible result: {doctype}"
                )

                item.click()

                page.wait_for_timeout(1200)

                log(
                    f"After result click: {page.url}"
                )

                return True

        except Exception:
            continue

    # --------------------------------------------------------
    # Text-based fallback
    # --------------------------------------------------------

    locator = page.locator(
        f"text={doctype}"
    )

    try:

        count = locator.count()

        for i in range(count):

            item = locator.nth(i)

            if item.is_visible():

                item.click()

                page.wait_for_timeout(1200)

                log(
                    f"Opened result: {page.url}"
                )

                return True

    except Exception:
        pass

    log(
        f"Could not automatically open {doctype}."
    )

    return False


# ============================================================
# SAVE KNOWLEDGE
# ============================================================

def save_knowledge(doctype, data):

    path = (
        KNOWLEDGE_DIR
        / f"{safe_name(doctype)}.json"
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
        f"Knowledge saved: {path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    doctype = " ".join(
        sys.argv[1:]
    ).strip()

    if not doctype:

        doctype = input(
            "Doctype to discover: "
        ).strip()

    if not doctype:

        print("No Doctype supplied.")
        return

    log("======================================")
    log("ERP DOCTYPE DISCOVERY AGENT")
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

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            search_text = search_doctype(
                page,
                doctype,
            )

            # ------------------------------------------------
            # TRY OPEN
            # ------------------------------------------------

            opened = open_doctype(
                page,
                doctype,
            )

            # ------------------------------------------------
            # If opened, discover page
            # ------------------------------------------------

            if opened:

                page.wait_for_timeout(1000)

                data = snapshot(
                    page,
                    doctype,
                )

                data["search_text"] = search_text
                data["opened"] = True

                screenshot_path = (
                    SCREENSHOT_DIR
                    / f"{safe_name(doctype)}.png"
                )

                page.screenshot(
                    path=str(screenshot_path),
                    full_page=True,
                )

                data["screenshot"] = str(
                    screenshot_path
                )

                save_knowledge(
                    doctype,
                    data,
                )

                log(
                    f"Elements discovered: "
                    f"{len(data['elements'])}"
                )

                log(
                    f"Labels discovered: "
                    f"{len(data['labels'])}"
                )

                log(
                    f"Buttons discovered: "
                    f"{len(data['buttons'])}"
                )

            else:

                # Save search results even if opening failed

                data = {
                    "doctype": doctype,
                    "opened": False,
                    "url": page.url,
                    "search_text": search_text,
                    "elements": discover_elements(page),
                    "labels": discover_labels(page),
                    "buttons": discover_buttons(page),
                }

                save_knowledge(
                    doctype,
                    data,
                )

            log("Discovery completed.")

        except Exception as exc:

            log(
                f"FATAL ERROR: {exc}"
            )

            try:

                page.screenshot(
                    path=str(
                        SCREENSHOT_DIR
                        / f"{safe_name(doctype)}_failure.png"
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