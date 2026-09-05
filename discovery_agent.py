import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

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

HEADLESS = (
    os.getenv("HEADLESS", "false").lower() == "true"
)

# Maximum number of pages to discover.
# Increase later if required.
MAX_PAGES = int(
    os.getenv("DISCOVERY_MAX_PAGES", "100")
)

PAGE_TIMEOUT = int(
    os.getenv("DISCOVERY_TIMEOUT", "30000")
)

WAIT_AFTER_NAVIGATION = int(
    os.getenv("DISCOVERY_WAIT_MS", "1000")
)

DISCOVERY_DIR = (
    BASE_DIR / "data" / "discovery"
)

SCREENSHOT_DIR = (
    BASE_DIR / "data" / "screenshots"
)

DISCOVERY_DIR.mkdir(
    parents=True,
    exist_ok=True
)

SCREENSHOT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SAFETY
# ============================================================

# These actions are NEVER executed by discovery.
BLOCKED_ACTION_WORDS = {
    "new",
    "save",
    "submit",
    "delete",
    "cancel",
    "remove",
    "discard",
    "amend",
    "update",
    "insert",
    "create",
    "add",
}


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{message}",
        flush=True,
    )


# ============================================================
# URL HELPERS
# ============================================================

def normalize_url(url):
    """
    Convert relative ERPNext URLs to absolute URLs.
    """

    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    absolute = urljoin(
        ERP_URL + "/",
        url,
    )

    parsed = urlparse(absolute)

    # Only crawl our ERP domain.
    base = urlparse(ERP_URL)

    if parsed.netloc != base.netloc:
        return None

    # Remove fragments.
    absolute = absolute.split("#")[0]

    return absolute.rstrip("/")


def is_safe_discovery_url(url):
    """
    Discovery only follows application navigation URLs.
    """

    url = normalize_url(url)

    if not url:
        return False

    parsed = urlparse(url)

    path = parsed.path.lower()

    # Never crawl API endpoints.
    if "/api/" in path:
        return False

    # Never crawl assets.
    blocked_extensions = (
        ".js",
        ".css",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".woff",
        ".woff2",
        ".ttf",
        ".ico",
    )

    if path.endswith(blocked_extensions):
        return False

    return True


# ============================================================
# SAFE FILE NAME
# ============================================================

def safe_filename(value):

    value = str(value or "").strip()

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value,
    )

    value = value.strip("_")

    return value[:150] or "page"


# ============================================================
# SAVE JSON
# ============================================================

def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
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
# SAFE ELEMENT TEXT
# ============================================================

def element_text(element):

    values = []

    try:
        values.append(
            element.inner_text()
        )
    except Exception:
        pass

    for attr in (
        "aria-label",
        "title",
        "placeholder",
        "value",
        "name",
        "id",
    ):

        try:

            value = element.get_attribute(
                attr
            )

            if value:
                values.append(value)

        except Exception:
            pass

    text = " ".join(
        str(x).strip()
        for x in values
        if x
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# ELEMENT DESCRIPTION
# ============================================================

def describe_element(element):

    try:

        tag = element.evaluate(
            "(el) => el.tagName.toLowerCase()"
        )

    except Exception:

        tag = ""

    data = {
        "tag": tag,
        "text": "",
        "id": "",
        "name": "",
        "type": "",
        "placeholder": "",
        "aria_label": "",
        "title": "",
        "role": "",
        "href": "",
        "value": "",
        "class": "",
    }

    attributes = {
        "id": "id",
        "name": "name",
        "type": "type",
        "placeholder": "placeholder",
        "aria_label": "aria-label",
        "title": "title",
        "role": "role",
        "href": "href",
        "value": "value",
        "class": "class",
    }

    for key, attr in attributes.items():

        try:

            data[key] = (
                element.get_attribute(attr)
                or ""
            )

        except Exception:
            pass

    data["text"] = element_text(
        element
    )[:300]

    return data


# ============================================================
# VISIBLE ELEMENT DISCOVERY
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
        [role="menuitem"],
        [role="link"],
        [contenteditable="true"]
    """

    try:

        locator = page.locator(
            selectors
        )

        count = min(
            locator.count(),
            500,
        )

    except Exception:

        return elements

    for i in range(count):

        element = locator.nth(i)

        try:

            if not element.is_visible():
                continue

            elements.append(
                describe_element(
                    element
                )
            )

        except Exception:
            continue

    return elements


# ============================================================
# LINKS
# ============================================================

def discover_links(page):

    result = []

    try:

        links = page.locator("a")

        count = min(
            links.count(),
            500,
        )

    except Exception:

        return result

    seen = set()

    for i in range(count):

        link = links.nth(i)

        try:

            if not link.is_visible():
                continue

            text = (
                link.inner_text()
                or ""
            ).strip()

            href = (
                link.get_attribute("href")
                or ""
            ).strip()

            absolute = normalize_url(
                href
            )

            key = (
                text,
                absolute,
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(
                {
                    "text": text[:300],
                    "href": href[:500],
                    "absolute_url": absolute,
                }
            )

        except Exception:
            continue

    return result


# ============================================================
# BUTTONS / ACTIONS
# ============================================================

def discover_buttons(page):

    result = []

    try:

        buttons = page.locator(
            "button, [role='button']"
        )

        count = min(
            buttons.count(),
            300,
        )

    except Exception:

        return result

    seen = set()

    for i in range(count):

        button = buttons.nth(i)

        try:

            if not button.is_visible():
                continue

            data = describe_element(
                button
            )

            text = (
                data["text"]
                or ""
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)

            # Mark dangerous actions but DON'T click.
            normalized = key.lower()

            blocked = any(
                word == normalized
                or word in normalized
                for word in BLOCKED_ACTION_WORDS
            )

            data["blocked_for_discovery"] = (
                blocked
            )

            result.append(data)

        except Exception:
            continue

    return result


# ============================================================
# FORM FIELDS
# ============================================================

def discover_fields(page):

    fields = []

    selectors = """
        input,
        textarea,
        select,
        [contenteditable="true"]
    """

    try:

        locator = page.locator(
            selectors
        )

        count = min(
            locator.count(),
            500,
        )

    except Exception:

        return fields

    for i in range(count):

        field = locator.nth(i)

        try:

            if not field.is_visible():
                continue

            data = describe_element(
                field
            )

            data["required"] = False

            try:

                data["required"] = (
                    field.get_attribute(
                        "required"
                    )
                    is not None
                )

            except Exception:
                pass

            fields.append(data)

        except Exception:
            continue

    return fields


# ============================================================
# PAGE TEXT
# ============================================================

def discover_text(page):

    try:

        return (
            page.locator("body")
            .inner_text(
                timeout=5000
            )
            [:30000]
        )

    except Exception:

        return ""


# ============================================================
# PAGE METADATA
# ============================================================

def discover_page(page):

    data = {
        "url": page.url,
        "title": "",
        "text": "",
        "elements": [],
        "links": [],
        "buttons": [],
        "fields": [],
        "doctype": None,
        "route": None,
    }

    try:

        data["title"] = page.title()

    except Exception:
        pass

    data["text"] = discover_text(
        page
    )

    data["elements"] = (
        discover_elements(page)
    )

    data["links"] = (
        discover_links(page)
    )

    data["buttons"] = (
        discover_buttons(page)
    )

    data["fields"] = (
        discover_fields(page)
    )

    data["route"] = urlparse(
        page.url
    ).path

    # --------------------------------------------------------
    # Try to infer DocType from route
    # --------------------------------------------------------

    path = data["route"] or ""

    match = re.search(
        r"/app/([^/?#]+)",
        path,
    )

    if match:

        route_name = match.group(1)

        data["doctype"] = (
            route_name
            .replace("-", " ")
            .replace("_", " ")
            .title()
        )

    return data


# ============================================================
# DISCOVER CURRENT PAGE
# ============================================================

def save_current_page(
    page,
    counter,
):

    data = discover_page(page)

    path = urlparse(
        page.url
    ).path

    filename = safe_filename(
        path.replace(
            "/app/",
            ""
        ).replace(
            "/",
            "_"
        )
    )

    if not filename:
        filename = "page"

    filename = (
        f"{counter:04d}_{filename}"
    )

    json_path = (
        DISCOVERY_DIR
        / f"{filename}.json"
    )

    save_json(
        json_path,
        data,
    )

    # Screenshot.
    screenshot_path = (
        SCREENSHOT_DIR
        / f"{filename}.png"
    )

    try:

        page.screenshot(
            path=str(
                screenshot_path
            ),
            full_page=True,
        )

    except Exception:
        pass

    return data


# ============================================================
# LOGIN
# ============================================================

def find_visible(
    page,
    selectors,
):

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            )

            count = locator.count()

        except Exception:

            continue

        for i in range(count):

            item = locator.nth(i)

            try:

                if item.is_visible():
                    return item

            except Exception:
                continue

    return None


def login(page):

    log("Checking login state...")

    if "/app" in page.url:

        log(
            "Already logged in."
        )

        return True

    if not USERNAME:

        raise RuntimeError(
            "ERPNEXT_USER is missing from .env"
        )

    if not PASSWORD:

        raise RuntimeError(
            "ERPNEXT_PASSWORD is missing from .env"
        )

    username = find_visible(
        page,
        [
            "input[name='usr']",
            "input[autocomplete='username']",
            "input[name='login']",
            "input[type='email']",
        ],
    )

    if not username:

        raise RuntimeError(
            "Visible username field not found."
        )

    password = find_visible(
        page,
        [
            "input[name='pwd']",
            "input[name='password']",
            "input[type='password']",
        ],
    )

    if not password:

        raise RuntimeError(
            "Visible password field not found."
        )

    username.fill(
        USERNAME
    )

    password.fill(
        PASSWORD
    )

    log(
        "Credentials filled."
    )

    login_button = find_visible(
        page,
        [
            "button:has-text('Login')",
            "button:has-text('Log in')",
            "button:has-text('Sign in')",
            "input[type='submit']",
            "[role='button']:has-text('Login')",
        ],
    )

    if not login_button:

        raise RuntimeError(
            "Login button not found."
        )

    login_button.click()

    page.wait_for_timeout(
        2000
    )

    # Wait for app navigation.
    try:

        page.wait_for_url(
            re.compile(
                r".*/app.*"
            ),
            timeout=15000,
        )

    except Exception:
        pass

    log(
        f"Login URL: {page.url}"
    )

    if "/app" not in page.url:

        raise RuntimeError(
            f"Login failed: {page.url}"
        )

    log(
        "LOGIN SUCCESS"
    )

    return True


# ============================================================
# HOME URL
# ============================================================

def open_home(page):

    # After login ERPNext normally already routes
    # to /app or /app/home.

    if "/app/home" not in page.url:

        home_url = (
            f"{ERP_URL}/app/home"
        )

        page.goto(
            home_url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

    page.wait_for_timeout(
        WAIT_AFTER_NAVIGATION
    )

    log(
        f"Home URL: {page.url}"
    )


# ============================================================
# EXTRACT CRAWLABLE LINKS
# ============================================================

def extract_crawl_urls(
    page,
    page_data,
):

    candidates = []

    # --------------------------------------------------------
    # Normal anchor links
    # --------------------------------------------------------

    for item in page_data["links"]:

        url = item.get(
            "absolute_url"
        )

        if url:
            candidates.append(url)

    # --------------------------------------------------------
    # Some ERPNext UI elements use data-route
    # --------------------------------------------------------

    selectors = """
        [data-route],
        [data-link],
        [data-href],
        [href]
    """

    try:

        locator = page.locator(
            selectors
        )

        count = min(
            locator.count(),
            500,
        )

    except Exception:

        count = 0

    for i in range(count):

        element = locator.nth(i)

        try:

            if not element.is_visible():
                continue

            for attr in (
                "data-route",
                "data-link",
                "data-href",
                "href",
            ):

                value = (
                    element.get_attribute(
                        attr
                    )
                    or ""
                )

                if not value:
                    continue

                url = normalize_url(
                    value
                )

                if url:
                    candidates.append(url)

        except Exception:
            continue

    # --------------------------------------------------------
    # Unique
    # --------------------------------------------------------

    result = []

    seen = set()

    for url in candidates:

        if not is_safe_discovery_url(
            url
        ):
            continue

        if url in seen:
            continue

        seen.add(url)

        result.append(url)

    return result


# ============================================================
# CRAWL
# ============================================================

def crawl(page):

    queue = []

    visited = set()

    discovery_index = []

    # Start with Home.
    home_url = normalize_url(
        f"{ERP_URL}/app/home"
    )

    queue.append(home_url)

    counter = 0

    while queue and len(
        visited
    ) < MAX_PAGES:

        url = queue.pop(0)

        url = normalize_url(url)

        if not url:
            continue

        if url in visited:
            continue

        visited.add(url)

        log("")
        log(
            "--------------------------------------"
        )

        log(
            f"CRAWL "
            f"{len(visited)}/{MAX_PAGES}"
        )

        log(
            f"URL: {url}"
        )

        log(
            "--------------------------------------"
        )

        try:

            # ------------------------------------------------
            # Navigate
            # ------------------------------------------------

            if page.url != url:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )

            page.wait_for_timeout(
                WAIT_AFTER_NAVIGATION
            )

            # ------------------------------------------------
            # Session check
            # ------------------------------------------------

            if "/login" in page.url:

                log(
                    "Session returned to login."
                )

                login(page)

                if page.url != url:

                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT,
                    )

                    page.wait_for_timeout(
                        WAIT_AFTER_NAVIGATION
                    )

            # ------------------------------------------------
            # Discover
            # ------------------------------------------------

            counter += 1

            page_data = (
                save_current_page(
                    page,
                    counter,
                )
            )

            discovery_index.append(
                {
                    "url": page.url,
                    "title": page_data["title"],
                    "doctype": page_data["doctype"],
                    "route": page_data["route"],
                    "file": (
                        f"{counter:04d}_"
                        f"{safe_filename(urlparse(page.url).path)}"
                        ".json"
                    ),
                }
            )

            # ------------------------------------------------
            # Find next pages
            # ------------------------------------------------

            next_urls = (
                extract_crawl_urls(
                    page,
                    page_data,
                )
            )

            added = 0

            for next_url in next_urls:

                if next_url in visited:
                    continue

                if next_url in queue:
                    continue

                queue.append(
                    next_url
                )

                added += 1

            log(
                f"New URLs queued: {added}"
            )

            log(
                f"Queue size: {len(queue)}"
            )

        except Exception as exc:

            log(
                f"PAGE ERROR: {exc}"
            )

            error_file = (
                DISCOVERY_DIR
                / "crawl_errors.json"
            )

            existing = []

            if error_file.exists():

                try:

                    existing = json.loads(
                        error_file.read_text(
                            encoding="utf-8"
                        )
                    )

                except Exception:
                    existing = []

            existing.append(
                {
                    "url": url,
                    "error": str(exc),
                    "time": time.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )

            save_json(
                error_file,
                existing,
            )

            try:

                page.screenshot(
                    path=str(
                        SCREENSHOT_DIR
                        / (
                            "error_"
                            + safe_filename(
                                urlparse(
                                    url
                                ).path
                            )
                            + ".png"
                        )
                    ),
                    full_page=True,
                )

            except Exception:
                pass

    # --------------------------------------------------------
    # Crawl index
    # --------------------------------------------------------

    save_json(
        DISCOVERY_DIR
        / "crawl_index.json",
        {
            "erp_url": ERP_URL,
            "started_at": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "pages_discovered": len(
                discovery_index
            ),
            "visited_urls": sorted(
                visited
            ),
            "pages": discovery_index,
            "max_pages": MAX_PAGES,
        },
    )

    return discovery_index


# ============================================================
# MAIN
# ============================================================

def main():

    log(
        "======================================"
    )

    log(
        "ERPNext GENERIC DISCOVERY AGENT"
    )

    log(
        "READ-ONLY MODE"
    )

    log(
        "======================================"
    )

    log(
        f"ERP URL: {ERP_URL}"
    )

    log(
        f"MAX PAGES: {MAX_PAGES}"
    )

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
            # Open ERP
            # ------------------------------------------------

            log(
                f"Opening ERP: {ERP_URL}"
            )

            page.goto(
                ERP_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT,
            )

            log(
                f"Current URL: {page.url}"
            )

            # ------------------------------------------------
            # Login
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # Home
            # ------------------------------------------------

            open_home(page)

            # ------------------------------------------------
            # Full crawl
            # ------------------------------------------------

            pages = crawl(page)

            # ------------------------------------------------
            # Final summary
            # ------------------------------------------------

            log("")
            log(
                "======================================"
            )

            log(
                "DISCOVERY FINISHED"
            )

            log(
                f"Pages discovered: {len(pages)}"
            )

            log(
                f"Discovery directory: "
                f"{DISCOVERY_DIR}"
            )

            log(
                f"Screenshot directory: "
                f"{SCREENSHOT_DIR}"
            )

            log(
                "======================================"
            )

        except KeyboardInterrupt:

            log(
                "Discovery interrupted by user."
            )

        except Exception as exc:

            log(
                f"FATAL ERROR: {exc}"
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

            try:
                context.close()
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()