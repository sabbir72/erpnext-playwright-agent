# import json
# import os
# import re
# import time
# from pathlib import Path
# from urllib.parse import urljoin, urlparse

# from dotenv import load_dotenv
# from playwright.sync_api import sync_playwright


# # ============================================================
# # CONFIG
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent

# load_dotenv(BASE_DIR / ".env")

# ERP_URL = os.getenv(
#     "ERPNEXT_URL",
#     "https://stage2-salma.altersense.net",
# ).rstrip("/")

# USERNAME = os.getenv("ERPNEXT_USER", "")
# PASSWORD = os.getenv("ERPNEXT_PASSWORD", "")

# HEADLESS = (
#     os.getenv("HEADLESS", "false").lower() == "true"
# )

# # Maximum number of pages to discover.
# # Increase later if required.
# MAX_PAGES = int(
#     os.getenv("DISCOVERY_MAX_PAGES", "100")
# )

# PAGE_TIMEOUT = int(
#     os.getenv("DISCOVERY_TIMEOUT", "30000")
# )

# WAIT_AFTER_NAVIGATION = int(
#     os.getenv("DISCOVERY_WAIT_MS", "1000")
# )

# DISCOVERY_DIR = (
#     BASE_DIR / "data" / "discovery"
# )

# SCREENSHOT_DIR = (
#     BASE_DIR / "data" / "screenshots"
# )

# DISCOVERY_DIR.mkdir(
#     parents=True,
#     exist_ok=True
# )

# SCREENSHOT_DIR.mkdir(
#     parents=True,
#     exist_ok=True
# )


# # ============================================================
# # SAFETY
# # ============================================================

# # These actions are NEVER executed by discovery.
# BLOCKED_ACTION_WORDS = {
#     "new",
#     "save",
#     "submit",
#     "delete",
#     "cancel",
#     "remove",
#     "discard",
#     "amend",
#     "update",
#     "insert",
#     "create",
#     "add",
# }


# # ============================================================
# # LOGGING
# # ============================================================

# def log(message):
#     print(
#         f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
#         f"{message}",
#         flush=True,
#     )


# # ============================================================
# # URL HELPERS
# # ============================================================

# def normalize_url(url):
#     """
#     Convert relative ERPNext URLs to absolute URLs.
#     """

#     if not url:
#         return None

#     url = url.strip()

#     if not url:
#         return None

#     absolute = urljoin(
#         ERP_URL + "/",
#         url,
#     )

#     parsed = urlparse(absolute)

#     # Only crawl our ERP domain.
#     base = urlparse(ERP_URL)

#     if parsed.netloc != base.netloc:
#         return None

#     # Remove fragments.
#     absolute = absolute.split("#")[0]

#     return absolute.rstrip("/")


# def is_safe_discovery_url(url):
#     """
#     Discovery only follows application navigation URLs.
#     """

#     url = normalize_url(url)

#     if not url:
#         return False

#     parsed = urlparse(url)

#     path = parsed.path.lower()

#     # Never crawl API endpoints.
#     if "/api/" in path:
#         return False

#     # Never crawl assets.
#     blocked_extensions = (
#         ".js",
#         ".css",
#         ".png",
#         ".jpg",
#         ".jpeg",
#         ".gif",
#         ".svg",
#         ".woff",
#         ".woff2",
#         ".ttf",
#         ".ico",
#     )

#     if path.endswith(blocked_extensions):
#         return False

#     return True


# # ============================================================
# # SAFE FILE NAME
# # ============================================================

# def safe_filename(value):

#     value = str(value or "").strip()

#     value = re.sub(
#         r"[^A-Za-z0-9_-]+",
#         "_",
#         value,
#     )

#     value = value.strip("_")

#     return value[:150] or "page"


# # ============================================================
# # SAVE JSON
# # ============================================================

# def save_json(path, data):

#     path.parent.mkdir(
#         parents=True,
#         exist_ok=True,
#     )

#     path.write_text(
#         json.dumps(
#             data,
#             indent=2,
#             ensure_ascii=False,
#         ),
#         encoding="utf-8",
#     )

#     log(
#         f"Discovery saved: {path}"
#     )


# # ============================================================
# # SAFE ELEMENT TEXT
# # ============================================================

# def element_text(element):

#     values = []

#     try:
#         values.append(
#             element.inner_text()
#         )
#     except Exception:
#         pass

#     for attr in (
#         "aria-label",
#         "title",
#         "placeholder",
#         "value",
#         "name",
#         "id",
#     ):

#         try:

#             value = element.get_attribute(
#                 attr
#             )

#             if value:
#                 values.append(value)

#         except Exception:
#             pass

#     text = " ".join(
#         str(x).strip()
#         for x in values
#         if x
#     )

#     return re.sub(
#         r"\s+",
#         " ",
#         text,
#     ).strip()


# # ============================================================
# # ELEMENT DESCRIPTION
# # ============================================================

# def describe_element(element):

#     try:

#         tag = element.evaluate(
#             "(el) => el.tagName.toLowerCase()"
#         )

#     except Exception:

#         tag = ""

#     data = {
#         "tag": tag,
#         "text": "",
#         "id": "",
#         "name": "",
#         "type": "",
#         "placeholder": "",
#         "aria_label": "",
#         "title": "",
#         "role": "",
#         "href": "",
#         "value": "",
#         "class": "",
#     }

#     attributes = {
#         "id": "id",
#         "name": "name",
#         "type": "type",
#         "placeholder": "placeholder",
#         "aria_label": "aria-label",
#         "title": "title",
#         "role": "role",
#         "href": "href",
#         "value": "value",
#         "class": "class",
#     }

#     for key, attr in attributes.items():

#         try:

#             data[key] = (
#                 element.get_attribute(attr)
#                 or ""
#             )

#         except Exception:
#             pass

#     data["text"] = element_text(
#         element
#     )[:300]

#     return data


# # ============================================================
# # VISIBLE ELEMENT DISCOVERY
# # ============================================================

# def discover_elements(page):

#     elements = []

#     selectors = """
#         button,
#         input,
#         textarea,
#         select,
#         a,
#         [role="button"],
#         [role="option"],
#         [role="tab"],
#         [role="menuitem"],
#         [role="link"],
#         [contenteditable="true"]
#     """

#     try:

#         locator = page.locator(
#             selectors
#         )

#         count = min(
#             locator.count(),
#             500,
#         )

#     except Exception:

#         return elements

#     for i in range(count):

#         element = locator.nth(i)

#         try:

#             if not element.is_visible():
#                 continue

#             elements.append(
#                 describe_element(
#                     element
#                 )
#             )

#         except Exception:
#             continue

#     return elements


# # ============================================================
# # LINKS
# # ============================================================

# def discover_links(page):

#     result = []

#     try:

#         links = page.locator("a")

#         count = min(
#             links.count(),
#             500,
#         )

#     except Exception:

#         return result

#     seen = set()

#     for i in range(count):

#         link = links.nth(i)

#         try:

#             if not link.is_visible():
#                 continue

#             text = (
#                 link.inner_text()
#                 or ""
#             ).strip()

#             href = (
#                 link.get_attribute("href")
#                 or ""
#             ).strip()

#             absolute = normalize_url(
#                 href
#             )

#             key = (
#                 text,
#                 absolute,
#             )

#             if key in seen:
#                 continue

#             seen.add(key)

#             result.append(
#                 {
#                     "text": text[:300],
#                     "href": href[:500],
#                     "absolute_url": absolute,
#                 }
#             )

#         except Exception:
#             continue

#     return result


# # ============================================================
# # BUTTONS / ACTIONS
# # ============================================================

# def discover_buttons(page):

#     result = []

#     try:

#         buttons = page.locator(
#             "button, [role='button']"
#         )

#         count = min(
#             buttons.count(),
#             300,
#         )

#     except Exception:

#         return result

#     seen = set()

#     for i in range(count):

#         button = buttons.nth(i)

#         try:

#             if not button.is_visible():
#                 continue

#             data = describe_element(
#                 button
#             )

#             text = (
#                 data["text"]
#                 or ""
#             ).strip()

#             if not text:
#                 continue

#             key = text.lower()

#             if key in seen:
#                 continue

#             seen.add(key)

#             # Mark dangerous actions but DON'T click.
#             normalized = key.lower()

#             blocked = any(
#                 word == normalized
#                 or word in normalized
#                 for word in BLOCKED_ACTION_WORDS
#             )

#             data["blocked_for_discovery"] = (
#                 blocked
#             )

#             result.append(data)

#         except Exception:
#             continue

#     return result


# # ============================================================
# # FORM FIELDS
# # ============================================================

# def discover_fields(page):

#     fields = []

#     selectors = """
#         input,
#         textarea,
#         select,
#         [contenteditable="true"]
#     """

#     try:

#         locator = page.locator(
#             selectors
#         )

#         count = min(
#             locator.count(),
#             500,
#         )

#     except Exception:

#         return fields

#     for i in range(count):

#         field = locator.nth(i)

#         try:

#             if not field.is_visible():
#                 continue

#             data = describe_element(
#                 field
#             )

#             data["required"] = False

#             try:

#                 data["required"] = (
#                     field.get_attribute(
#                         "required"
#                     )
#                     is not None
#                 )

#             except Exception:
#                 pass

#             fields.append(data)

#         except Exception:
#             continue

#     return fields


# # ============================================================
# # PAGE TEXT
# # ============================================================

# def discover_text(page):

#     try:

#         return (
#             page.locator("body")
#             .inner_text(
#                 timeout=5000
#             )
#             [:30000]
#         )

#     except Exception:

#         return ""


# # ============================================================
# # PAGE METADATA
# # ============================================================

# def discover_page(page):

#     data = {
#         "url": page.url,
#         "title": "",
#         "text": "",
#         "elements": [],
#         "links": [],
#         "buttons": [],
#         "fields": [],
#         "doctype": None,
#         "route": None,
#     }

#     try:

#         data["title"] = page.title()

#     except Exception:
#         pass

#     data["text"] = discover_text(
#         page
#     )

#     data["elements"] = (
#         discover_elements(page)
#     )

#     data["links"] = (
#         discover_links(page)
#     )

#     data["buttons"] = (
#         discover_buttons(page)
#     )

#     data["fields"] = (
#         discover_fields(page)
#     )

#     data["route"] = urlparse(
#         page.url
#     ).path

#     # --------------------------------------------------------
#     # Try to infer DocType from route
#     # --------------------------------------------------------

#     path = data["route"] or ""

#     match = re.search(
#         r"/app/([^/?#]+)",
#         path,
#     )

#     if match:

#         route_name = match.group(1)

#         data["doctype"] = (
#             route_name
#             .replace("-", " ")
#             .replace("_", " ")
#             .title()
#         )

#     return data


# # ============================================================
# # DISCOVER CURRENT PAGE
# # ============================================================

# def save_current_page(
#     page,
#     counter,
# ):

#     data = discover_page(page)

#     path = urlparse(
#         page.url
#     ).path

#     filename = safe_filename(
#         path.replace(
#             "/app/",
#             ""
#         ).replace(
#             "/",
#             "_"
#         )
#     )

#     if not filename:
#         filename = "page"

#     filename = (
#         f"{counter:04d}_{filename}"
#     )

#     json_path = (
#         DISCOVERY_DIR
#         / f"{filename}.json"
#     )

#     save_json(
#         json_path,
#         data,
#     )

#     # Screenshot.
#     screenshot_path = (
#         SCREENSHOT_DIR
#         / f"{filename}.png"
#     )

#     try:

#         page.screenshot(
#             path=str(
#                 screenshot_path
#             ),
#             full_page=True,
#         )

#     except Exception:
#         pass

#     return data


# # ============================================================
# # LOGIN
# # ============================================================

# def find_visible(
#     page,
#     selectors,
# ):

#     for selector in selectors:

#         try:

#             locator = page.locator(
#                 selector
#             )

#             count = locator.count()

#         except Exception:

#             continue

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if item.is_visible():
#                     return item

#             except Exception:
#                 continue

#     return None


# def login(page):

#     log("Checking login state...")

#     if "/app" in page.url:

#         log(
#             "Already logged in."
#         )

#         return True

#     if not USERNAME:

#         raise RuntimeError(
#             "ERPNEXT_USER is missing from .env"
#         )

#     if not PASSWORD:

#         raise RuntimeError(
#             "ERPNEXT_PASSWORD is missing from .env"
#         )

#     username = find_visible(
#         page,
#         [
#             "input[name='usr']",
#             "input[autocomplete='username']",
#             "input[name='login']",
#             "input[type='email']",
#         ],
#     )

#     if not username:

#         raise RuntimeError(
#             "Visible username field not found."
#         )

#     password = find_visible(
#         page,
#         [
#             "input[name='pwd']",
#             "input[name='password']",
#             "input[type='password']",
#         ],
#     )

#     if not password:

#         raise RuntimeError(
#             "Visible password field not found."
#         )

#     username.fill(
#         USERNAME
#     )

#     password.fill(
#         PASSWORD
#     )

#     log(
#         "Credentials filled."
#     )

#     login_button = find_visible(
#         page,
#         [
#             "button:has-text('Login')",
#             "button:has-text('Log in')",
#             "button:has-text('Sign in')",
#             "input[type='submit']",
#             "[role='button']:has-text('Login')",
#         ],
#     )

#     if not login_button:

#         raise RuntimeError(
#             "Login button not found."
#         )

#     login_button.click()

#     page.wait_for_timeout(
#         2000
#     )

#     # Wait for app navigation.
#     try:

#         page.wait_for_url(
#             re.compile(
#                 r".*/app.*"
#             ),
#             timeout=15000,
#         )

#     except Exception:
#         pass

#     log(
#         f"Login URL: {page.url}"
#     )

#     if "/app" not in page.url:

#         raise RuntimeError(
#             f"Login failed: {page.url}"
#         )

#     log(
#         "LOGIN SUCCESS"
#     )

#     return True


# # ============================================================
# # HOME URL
# # ============================================================

# def open_home(page):

#     # After login ERPNext normally already routes
#     # to /app or /app/home.

#     if "/app/home" not in page.url:

#         home_url = (
#             f"{ERP_URL}/app/home"
#         )

#         page.goto(
#             home_url,
#             wait_until="domcontentloaded",
#             timeout=PAGE_TIMEOUT,
#         )

#     page.wait_for_timeout(
#         WAIT_AFTER_NAVIGATION
#     )

#     log(
#         f"Home URL: {page.url}"
#     )


# # ============================================================
# # EXTRACT CRAWLABLE LINKS
# # ============================================================

# def extract_crawl_urls(
#     page,
#     page_data,
# ):

#     candidates = []

#     # --------------------------------------------------------
#     # Normal anchor links
#     # --------------------------------------------------------

#     for item in page_data["links"]:

#         url = item.get(
#             "absolute_url"
#         )

#         if url:
#             candidates.append(url)

#     # --------------------------------------------------------
#     # Some ERPNext UI elements use data-route
#     # --------------------------------------------------------

#     selectors = """
#         [data-route],
#         [data-link],
#         [data-href],
#         [href]
#     """

#     try:

#         locator = page.locator(
#             selectors
#         )

#         count = min(
#             locator.count(),
#             500,
#         )

#     except Exception:

#         count = 0

#     for i in range(count):

#         element = locator.nth(i)

#         try:

#             if not element.is_visible():
#                 continue

#             for attr in (
#                 "data-route",
#                 "data-link",
#                 "data-href",
#                 "href",
#             ):

#                 value = (
#                     element.get_attribute(
#                         attr
#                     )
#                     or ""
#                 )

#                 if not value:
#                     continue

#                 url = normalize_url(
#                     value
#                 )

#                 if url:
#                     candidates.append(url)

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Unique
#     # --------------------------------------------------------

#     result = []

#     seen = set()

#     for url in candidates:

#         if not is_safe_discovery_url(
#             url
#         ):
#             continue

#         if url in seen:
#             continue

#         seen.add(url)

#         result.append(url)

#     return result


# # ============================================================
# # CRAWL
# # ============================================================

# def crawl(page):

#     queue = []

#     visited = set()

#     discovery_index = []

#     # Start with Home.
#     home_url = normalize_url(
#         f"{ERP_URL}/app/home"
#     )

#     queue.append(home_url)

#     counter = 0

#     while queue and len(
#         visited
#     ) < MAX_PAGES:

#         url = queue.pop(0)

#         url = normalize_url(url)

#         if not url:
#             continue

#         if url in visited:
#             continue

#         visited.add(url)

#         log("")
#         log(
#             "--------------------------------------"
#         )

#         log(
#             f"CRAWL "
#             f"{len(visited)}/{MAX_PAGES}"
#         )

#         log(
#             f"URL: {url}"
#         )

#         log(
#             "--------------------------------------"
#         )

#         try:

#             # ------------------------------------------------
#             # Navigate
#             # ------------------------------------------------

#             if page.url != url:

#                 page.goto(
#                     url,
#                     wait_until="domcontentloaded",
#                     timeout=PAGE_TIMEOUT,
#                 )

#             page.wait_for_timeout(
#                 WAIT_AFTER_NAVIGATION
#             )

#             # ------------------------------------------------
#             # Session check
#             # ------------------------------------------------

#             if "/login" in page.url:

#                 log(
#                     "Session returned to login."
#                 )

#                 login(page)

#                 if page.url != url:

#                     page.goto(
#                         url,
#                         wait_until="domcontentloaded",
#                         timeout=PAGE_TIMEOUT,
#                     )

#                     page.wait_for_timeout(
#                         WAIT_AFTER_NAVIGATION
#                     )

#             # ------------------------------------------------
#             # Discover
#             # ------------------------------------------------

#             counter += 1

#             page_data = (
#                 save_current_page(
#                     page,
#                     counter,
#                 )
#             )

#             discovery_index.append(
#                 {
#                     "url": page.url,
#                     "title": page_data["title"],
#                     "doctype": page_data["doctype"],
#                     "route": page_data["route"],
#                     "file": (
#                         f"{counter:04d}_"
#                         f"{safe_filename(urlparse(page.url).path)}"
#                         ".json"
#                     ),
#                 }
#             )

#             # ------------------------------------------------
#             # Find next pages
#             # ------------------------------------------------

#             next_urls = (
#                 extract_crawl_urls(
#                     page,
#                     page_data,
#                 )
#             )

#             added = 0

#             for next_url in next_urls:

#                 if next_url in visited:
#                     continue

#                 if next_url in queue:
#                     continue

#                 queue.append(
#                     next_url
#                 )

#                 added += 1

#             log(
#                 f"New URLs queued: {added}"
#             )

#             log(
#                 f"Queue size: {len(queue)}"
#             )

#         except Exception as exc:

#             log(
#                 f"PAGE ERROR: {exc}"
#             )

#             error_file = (
#                 DISCOVERY_DIR
#                 / "crawl_errors.json"
#             )

#             existing = []

#             if error_file.exists():

#                 try:

#                     existing = json.loads(
#                         error_file.read_text(
#                             encoding="utf-8"
#                         )
#                     )

#                 except Exception:
#                     existing = []

#             existing.append(
#                 {
#                     "url": url,
#                     "error": str(exc),
#                     "time": time.strftime(
#                         "%Y-%m-%d %H:%M:%S"
#                     ),
#                 }
#             )

#             save_json(
#                 error_file,
#                 existing,
#             )

#             try:

#                 page.screenshot(
#                     path=str(
#                         SCREENSHOT_DIR
#                         / (
#                             "error_"
#                             + safe_filename(
#                                 urlparse(
#                                     url
#                                 ).path
#                             )
#                             + ".png"
#                         )
#                     ),
#                     full_page=True,
#                 )

#             except Exception:
#                 pass

#     # --------------------------------------------------------
#     # Crawl index
#     # --------------------------------------------------------

#     save_json(
#         DISCOVERY_DIR
#         / "crawl_index.json",
#         {
#             "erp_url": ERP_URL,
#             "started_at": time.strftime(
#                 "%Y-%m-%d %H:%M:%S"
#             ),
#             "pages_discovered": len(
#                 discovery_index
#             ),
#             "visited_urls": sorted(
#                 visited
#             ),
#             "pages": discovery_index,
#             "max_pages": MAX_PAGES,
#         },
#     )

#     return discovery_index


# # ============================================================
# # MAIN
# # ============================================================

# def main():

#     log(
#         "======================================"
#     )

#     log(
#         "ERPNext GENERIC DISCOVERY AGENT"
#     )

#     log(
#         "READ-ONLY MODE"
#     )

#     log(
#         "======================================"
#     )

#     log(
#         f"ERP URL: {ERP_URL}"
#     )

#     log(
#         f"MAX PAGES: {MAX_PAGES}"
#     )

#     with sync_playwright() as p:

#         browser = p.chromium.launch(
#             headless=HEADLESS,
#             slow_mo=20,
#         )

#         context = browser.new_context(
#             viewport={
#                 "width": 1440,
#                 "height": 900,
#             }
#         )

#         page = context.new_page()

#         try:

#             # ------------------------------------------------
#             # Open ERP
#             # ------------------------------------------------

#             log(
#                 f"Opening ERP: {ERP_URL}"
#             )

#             page.goto(
#                 ERP_URL,
#                 wait_until="domcontentloaded",
#                 timeout=PAGE_TIMEOUT,
#             )

#             log(
#                 f"Current URL: {page.url}"
#             )

#             # ------------------------------------------------
#             # Login
#             # ------------------------------------------------

#             login(page)

#             # ------------------------------------------------
#             # Home
#             # ------------------------------------------------

#             open_home(page)

#             # ------------------------------------------------
#             # Full crawl
#             # ------------------------------------------------

#             pages = crawl(page)

#             # ------------------------------------------------
#             # Final summary
#             # ------------------------------------------------

#             log("")
#             log(
#                 "======================================"
#             )

#             log(
#                 "DISCOVERY FINISHED"
#             )

#             log(
#                 f"Pages discovered: {len(pages)}"
#             )

#             log(
#                 f"Discovery directory: "
#                 f"{DISCOVERY_DIR}"
#             )

#             log(
#                 f"Screenshot directory: "
#                 f"{SCREENSHOT_DIR}"
#             )

#             log(
#                 "======================================"
#             )

#         except KeyboardInterrupt:

#             log(
#                 "Discovery interrupted by user."
#             )

#         except Exception as exc:

#             log(
#                 f"FATAL ERROR: {exc}"
#             )

#             try:

#                 page.screenshot(
#                     path=str(
#                         SCREENSHOT_DIR
#                         / "discovery_failure.png"
#                     ),
#                     full_page=True,
#                 )

#             except Exception:
#                 pass

#         finally:

#             try:
#                 context.close()
#             except Exception:
#                 pass

#             try:
#                 browser.close()
#             except Exception:
#                 pass


# if __name__ == "__main__":
#     main()


# =======================================================
# import argparse
# import json
# import os
# import re
# import time
# from pathlib import Path
# from urllib.parse import urljoin

# from dotenv import load_dotenv
# from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# # ============================================================
# # CONFIG
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent
# load_dotenv(BASE_DIR / ".env")

# ERP_URL = os.getenv(
#     "ERPNEXT_URL",
#     "https://stage2-salma.altersense.net",
# ).rstrip("/")

# USERNAME = os.getenv("ERPNEXT_USER", "")
# PASSWORD = os.getenv("ERPNEXT_PASSWORD", "")

# HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"

# TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "30000"))
# WAIT_MS = int(os.getenv("DISCOVERY_WAIT_MS", "1200"))

# DATA_DIR = BASE_DIR / "data"
# DISCOVERY_DIR = DATA_DIR / "discovery"
# SCREENSHOT_DIR = DATA_DIR / "screenshots"
# LOG_DIR = BASE_DIR / "logs"

# DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
# SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
# LOG_DIR.mkdir(parents=True, exist_ok=True)


# # ============================================================
# # ARGUMENTS
# # ============================================================

# def parse_args():

#     parser = argparse.ArgumentParser(
#         description="Generic ERPNext Knowledge Discovery Agent"
#     )

#     parser.add_argument(
#         "--module",
#         help="ERPNext module to discover"
#     )

#     parser.add_argument(
#         "--doctype",
#         help="Read only this DocType"
#     )

#     return parser.parse_args()


# # ============================================================
# # LOGGING
# # ============================================================

# def log(message):

#     print(
#         f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}",
#         flush=True,
#     )


# # ============================================================
# # NORMALIZATION
# # ============================================================

# def normalize_name(value):

#     if not value:
#         return ""

#     value = value.strip().lower()

#     value = re.sub(
#         r"\s+",
#         " ",
#         value
#     )

#     return value


# def slugify(value):

#     value = value.strip().lower()

#     value = value.replace("&", "and")

#     value = re.sub(
#         r"[^a-z0-9]+",
#         "-",
#         value
#     )

#     value = re.sub(
#         r"-+",
#         "-",
#         value
#     )

#     return value.strip("-")


# # ============================================================
# # SERIAL FILE NAME
# # ============================================================

# def next_serial_number():

#     highest = 0

#     for path in DISCOVERY_DIR.glob("*.json"):

#         match = re.match(
#             r"^(\d+)_",
#             path.name
#         )

#         if not match:
#             continue

#         try:

#             number = int(match.group(1))

#             highest = max(
#                 highest,
#                 number
#             )

#         except ValueError:
#             continue

#     return highest + 1


# def make_discovery_filename(name):

#     serial = next_serial_number()

#     slug = slugify(name)

#     if not slug:
#         slug = "unknown"

#     return f"{serial:04d}_{slug}.json"


# # ============================================================
# # EXISTING DISCOVERY INDEX
# # ============================================================

# def get_existing_discovery():

#     existing = {}

#     for path in DISCOVERY_DIR.glob("*.json"):

#         try:

#             data = json.loads(
#                 path.read_text(
#                     encoding="utf-8"
#                 )
#             )

#         except Exception:
#             continue

#         names = []

#         for key in (
#             "name",
#             "doctype",
#             "document",
#             "title",
#         ):

#             value = data.get(key)

#             if isinstance(value, str) and value.strip():

#                 names.append(value)

#         for name in names:

#             existing[
#                 normalize_name(name)
#             ] = path

#     return existing


# # ============================================================
# # SAVE DISCOVERY
# # ============================================================

# def save_discovery(name, data):

#     existing = get_existing_discovery()

#     key = normalize_name(name)

#     if key in existing:

#         log(
#             f"SKIP EXISTING: {name} "
#             f"-> {existing[key].name}"
#         )

#         return existing[key]

#     filename = make_discovery_filename(name)

#     path = DISCOVERY_DIR / filename

#     data["discovery_file"] = filename
#     data["discovered_at"] = time.strftime(
#         "%Y-%m-%d %H:%M:%S"
#     )

#     path.write_text(
#         json.dumps(
#             data,
#             indent=2,
#             ensure_ascii=False,
#         ),
#         encoding="utf-8",
#     )

#     log(
#         f"SAVED: {path}"
#     )

#     return path


# # ============================================================
# # ELEMENT INFO
# # ============================================================

# def element_info(element):

#     try:

#         tag = (
#             element.evaluate(
#                 "(el) => el.tagName.toLowerCase()"
#             )
#             or ""
#         )

#     except Exception:

#         tag = ""

#     def attr(name):

#         try:
#             return (
#                 element.get_attribute(name)
#                 or ""
#             )
#         except Exception:
#             return ""

#     try:

#         text = (
#             element.inner_text()
#             or ""
#         ).strip()

#     except Exception:

#         text = ""

#     return {
#         "tag": tag,
#         "text": text[:500],
#         "id": attr("id"),
#         "name": attr("name"),
#         "type": attr("type"),
#         "href": attr("href"),
#         "title": attr("title"),
#         "aria_label": attr("aria-label"),
#         "role": attr("role"),
#         "data_route": attr("data-route"),
#         "data_link": attr("data-link"),
#         "data_href": attr("data-href"),
#         "class": attr("class")[:500],
#     }


# # ============================================================
# # DISCOVER PAGE
# # ============================================================

# def discover_page(page):

#     result = {
#         "url": page.url,
#         "title": "",
#         "text": "",
#         "elements": [],
#         "links": [],
#         "inputs": [],
#         "buttons": [],
#         "tabs": [],
#     }

#     try:
#         result["title"] = page.title()
#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # BODY TEXT
#     # --------------------------------------------------------

#     try:

#         result["text"] = (
#             page.locator("body")
#             .inner_text(timeout=5000)
#         )[:50000]

#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # ELEMENTS
#     # --------------------------------------------------------

#     selectors = """
#         button,
#         input,
#         textarea,
#         select,
#         a,
#         [role="button"],
#         [role="link"],
#         [role="option"],
#         [role="tab"],
#         [role="menuitem"],
#         [contenteditable="true"]
#     """

#     locator = page.locator(selectors)

#     try:
#         count = min(
#             locator.count(),
#             2000
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         try:

#             element = locator.nth(i)

#             if not element.is_visible():
#                 continue

#             info = element_info(element)

#             result["elements"].append(info)

#             tag = info["tag"]
#             role = info["role"]

#             if tag == "a":

#                 result["links"].append(info)

#             elif tag == "input":

#                 result["inputs"].append(info)

#             elif tag == "button" or role == "button":

#                 result["buttons"].append(info)

#             if role == "tab":

#                 result["tabs"].append(info)

#         except Exception:
#             continue

#     return result


# # ============================================================
# # ABSOLUTE URL
# # ============================================================

# def absolute_url(value):

#     if not value:
#         return ""

#     if value.startswith("http://"):
#         return value

#     if value.startswith("https://"):
#         return value

#     return urljoin(
#         ERP_URL + "/",
#         value
#     )


# # ============================================================
# # UI TEXT FILTER
# # ============================================================

# IGNORED_NAMES = {
#     "home",
#     "help",
#     "settings",
#     "logout",
#     "log out",
#     "login",
#     "log in",
#     "sign in",
#     "search",
#     "new",
#     "edit",
#     "delete",
#     "save",
#     "cancel",
#     "close",
#     "refresh",
#     "back",
#     "next",
#     "previous",
#     "collapse",
#     "expand",
#     "dashboard",
#     "menu",
#     "more",
#     "actions",
#     "submit",
#     "yes",
#     "no",
#     "ok",
#     "clear",
# }


# def looks_like_document_name(text):

#     if not text:
#         return False

#     text = text.strip()

#     if len(text) < 2:
#         return False

#     if len(text) > 150:
#         return False

#     normalized = normalize_name(text)

#     if normalized in IGNORED_NAMES:
#         return False

#     # Obvious sentence / UI instruction
#     if normalized.startswith(
#         (
#             "click ",
#             "go to ",
#             "open ",
#             "select ",
#             "type ",
#             "begin typing",
#         )
#     ):
#         return False

#     # Pure number
#     if re.fullmatch(
#         r"[\d\s.,/-]+",
#         text
#     ):
#         return False

#     return True


# # ============================================================
# # FIND DOCUMENT CANDIDATES
# # ============================================================

# def discover_document_candidates(
#     page,
#     module_name
# ):

#     log(
#         f"Scanning visible documents "
#         f"inside module: {module_name}"
#     )

#     candidates = []
#     seen = set()

#     selectors = """
#         a,
#         button,
#         [role="button"],
#         [role="link"],
#         [role="menuitem"],
#         [data-route],
#         [data-link],
#         [data-href]
#     """

#     locator = page.locator(selectors)

#     try:

#         count = min(
#             locator.count(),
#             2000
#         )

#     except Exception:

#         count = 0

#     for i in range(count):

#         try:

#             element = locator.nth(i)

#             if not element.is_visible():
#                 continue

#             info = element_info(element)

#             text = (
#                 info.get("text")
#                 or info.get("aria_label")
#                 or info.get("title")
#             ).strip()

#             if not looks_like_document_name(text):
#                 continue

#             href = (
#                 info.get("href")
#                 or info.get("data_route")
#                 or info.get("data_link")
#                 or info.get("data_href")
#             )

#             href = absolute_url(href)

#             # ------------------------------------------------
#             # ERP internal routes only
#             # ------------------------------------------------

#             if href:

#                 if not href.startswith(
#                     ERP_URL
#                 ):

#                     continue

#             key = (
#                 normalize_name(text),
#                 href
#             )

#             if key in seen:
#                 continue

#             seen.add(key)

#             candidates.append({
#                 "name": text,
#                 "url": href,
#                 "element": info,
#             })

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Also inspect visible text blocks
#     # --------------------------------------------------------

#     text_selectors = """
#         .standard-sidebar-item,
#         .desk-sidebar-item,
#         .module-link,
#         .widget-head,
#         .widget-title,
#         .shortcut-widget-box,
#         .link-item,
#         .item-link
#     """

#     blocks = page.locator(text_selectors)

#     try:

#         count = min(
#             blocks.count(),
#             1000
#         )

#     except Exception:

#         count = 0

#     for i in range(count):

#         try:

#             block = blocks.nth(i)

#             if not block.is_visible():
#                 continue

#             text = (
#                 block.inner_text()
#                 or ""
#             ).strip()

#             if not looks_like_document_name(text):
#                 continue

#             key = (
#                 normalize_name(text),
#                 ""
#             )

#             if key in seen:
#                 continue

#             seen.add(key)

#             candidates.append({
#                 "name": text,
#                 "url": "",
#                 "element": {}
#             })

#         except Exception:
#             continue

#     log(
#         f"Document candidates found: "
#         f"{len(candidates)}"
#     )

#     for item in candidates:

#         log(
#             f"  DOCUMENT: {item['name']}"
#         )

#     return candidates


# # ============================================================
# # FIND VISIBLE TEXT ELEMENT
# # ============================================================

# def find_text_element(
#     page,
#     text
# ):

#     exact_selectors = [
#         f"text={text}",
#         f"a:text-is('{text}')",
#         f"button:text-is('{text}')",
#         f"[role='link']:text-is('{text}')",
#         f"[role='button']:text-is('{text}')",
#     ]

#     for selector in exact_selectors:

#         try:

#             locator = page.locator(
#                 selector
#             )

#             count = locator.count()

#             for i in range(count):

#                 item = locator.nth(i)

#                 if item.is_visible():

#                     return item

#         except Exception:
#             continue

#     return None


# # ============================================================
# # OPEN MODULE
# # ============================================================

# def open_module(
#     page,
#     module_name
# ):

#     log(
#         f"Finding module: {module_name}"
#     )

#     # --------------------------------------------------------
#     # Try direct ERPNext route first
#     # --------------------------------------------------------

#     route = slugify(module_name)

#     possible_url = (
#         f"{ERP_URL}/app/{route}"
#     )

#     try:

#         page.goto(
#             possible_url,
#             wait_until="domcontentloaded",
#             timeout=TIMEOUT
#         )

#         page.wait_for_timeout(
#             WAIT_MS
#         )

#         if "/app/" in page.url:

#             log(
#                 f"Module URL: {page.url}"
#             )

#             return True

#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # Search visible module name
#     # --------------------------------------------------------

#     element = find_text_element(
#         page,
#         module_name
#     )

#     if not element:

#         raise RuntimeError(
#             f"Module not found: "
#             f"{module_name}"
#         )

#     element.click()

#     page.wait_for_timeout(
#         WAIT_MS
#     )

#     log(
#         f"Module URL: {page.url}"
#     )

#     return True


# # ============================================================
# # OPEN HOME
# # ============================================================

# def open_home(page):

#     page.goto(
#         f"{ERP_URL}/app/home",
#         wait_until="domcontentloaded",
#         timeout=TIMEOUT
#     )

#     page.wait_for_timeout(
#         WAIT_MS
#     )

#     log(
#         f"Home URL: {page.url}"
#     )


# # ============================================================
# # LOGIN
# # ============================================================

# def login(page):

#     log("Checking login state...")

#     if "/app" in page.url:

#         log(
#             "Already logged in."
#         )

#         return True

#     if not USERNAME or not PASSWORD:

#         raise RuntimeError(
#             "ERPNEXT_USER / "
#             "ERPNEXT_PASSWORD missing "
#             "from .env"
#         )

#     # --------------------------------------------------------
#     # Username
#     # --------------------------------------------------------

#     username_selectors = [
#         "input[name='usr']",
#         "input[name='login']",
#         "input[name='username']",
#         "input[autocomplete='username']",
#         "input[type='email']",
#     ]

#     username = None

#     for selector in username_selectors:

#         locator = page.locator(
#             selector
#         )

#         try:
#             count = locator.count()
#         except Exception:
#             count = 0

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if item.is_visible():

#                     username = item
#                     break

#             except Exception:
#                 pass

#         if username:
#             break

#     if not username:

#         raise RuntimeError(
#             "Visible username field not found."
#         )

#     # --------------------------------------------------------
#     # Password
#     # --------------------------------------------------------

#     password_selectors = [
#         "input[name='pwd']",
#         "input[name='password']",
#         "input[type='password']",
#     ]

#     password = None

#     for selector in password_selectors:

#         locator = page.locator(
#             selector
#         )

#         try:
#             count = locator.count()
#         except Exception:
#             count = 0

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if item.is_visible():

#                     password = item
#                     break

#             except Exception:
#                 pass

#         if password:
#             break

#     if not password:

#         raise RuntimeError(
#             "Visible password field not found."
#         )

#     username.fill(
#         USERNAME
#     )

#     password.fill(
#         PASSWORD
#     )

#     log(
#         "Credentials filled."
#     )

#     # --------------------------------------------------------
#     # Login
#     # --------------------------------------------------------

#     login_button = None

#     buttons = page.locator(
#         "button, "
#         "input[type='submit'], "
#         "[role='button']"
#     )

#     try:
#         count = buttons.count()
#     except Exception:
#         count = 0

#     for i in range(count):

#         button = buttons.nth(i)

#         try:

#             if not button.is_visible():
#                 continue

#             text = " ".join(
#                 [
#                     button.inner_text() or "",
#                     button.get_attribute(
#                         "value"
#                     ) or "",
#                     button.get_attribute(
#                         "aria-label"
#                     ) or "",
#                 ]
#             ).strip().lower()

#             if (
#                 text == "login"
#                 or "login" in text
#                 or "log in" in text
#                 or "sign in" in text
#             ):

#                 login_button = button
#                 break

#         except Exception:
#             continue

#     if not login_button:

#         raise RuntimeError(
#             "Login button not found."
#         )

#     login_button.click()

#     try:

#         page.wait_for_url(
#             re.compile(
#                 r".*/app.*"
#             ),
#             timeout=10000
#         )

#     except PlaywrightTimeoutError:

#         page.wait_for_timeout(
#             2500
#         )

#     if "/app" not in page.url:

#         raise RuntimeError(
#             f"Login failed: {page.url}"
#         )

#     log(
#         f"LOGIN SUCCESS: {page.url}"
#     )

#     return True


# # ============================================================
# # READ ONE DOCUMENT
# # ============================================================

# def read_document(
#     page,
#     module_name,
#     document_name,
#     document_url=""
# ):

#     log(
#         "--------------------------------------"
#     )

#     log(
#         f"READ DOCUMENT: {document_name}"
#     )

#     # --------------------------------------------------------
#     # Existing check BEFORE opening
#     # --------------------------------------------------------

#     existing = get_existing_discovery()

#     key = normalize_name(
#         document_name
#     )

#     if key in existing:

#         log(
#             f"SKIP EXISTING: "
#             f"{document_name} -> "
#             f"{existing[key].name}"
#         )

#         return False

#     # --------------------------------------------------------
#     # Open
#     # --------------------------------------------------------

#     if document_url:

#         if not document_url.startswith(
#             ERP_URL
#         ):

#             log(
#                 f"SKIP external URL: "
#                 f"{document_url}"
#             )

#             return False

#         page.goto(
#             document_url,
#             wait_until="domcontentloaded",
#             timeout=TIMEOUT
#         )

#     else:

#         element = find_text_element(
#             page,
#             document_name
#         )

#         if not element:

#             log(
#                 f"Cannot open: "
#                 f"{document_name}"
#             )

#             return False

#         element.click()

#     page.wait_for_timeout(
#         WAIT_MS
#     )

#     # --------------------------------------------------------
#     # Read full visible page
#     # --------------------------------------------------------

#     data = discover_page(
#         page
#     )

#     data.update({
#         "name": document_name,
#         "doctype": document_name,
#         "module": module_name,
#         "knowledge_type": "doctype",
#         "source_url": page.url,
#     })

#     # --------------------------------------------------------
#     # Screenshot
#     # --------------------------------------------------------

#     screenshot_name = (
#         f"{slugify(document_name)}.png"
#     )

#     screenshot_path = (
#         SCREENSHOT_DIR
#         / screenshot_name
#     )

#     try:

#         page.screenshot(
#             path=str(
#                 screenshot_path
#             ),
#             full_page=True
#         )

#     except Exception:
#         pass

#     data["screenshot"] = str(
#         screenshot_path
#     )

#     # --------------------------------------------------------
#     # Save
#     # --------------------------------------------------------

#     path = save_discovery(
#         document_name,
#         data
#     )

#     log(
#         f"DOCUMENT COMPLETE: "
#         f"{document_name}"
#     )

#     return True


# # ============================================================
# # MODULE DISCOVERY
# # ============================================================

# def discover_module(
#     page,
#     module_name,
#     only_doctype=None
# ):

#     log(
#         "======================================"
#     )

#     log(
#         f"MODULE DISCOVERY: {module_name}"
#     )

#     log(
#         "======================================"
#     )

#     # --------------------------------------------------------
#     # Read module page itself
#     # --------------------------------------------------------

#     module_data = discover_page(
#         page
#     )

#     module_data.update({
#         "name": module_name,
#         "module": module_name,
#         "knowledge_type": "module",
#     })

#     save_discovery(
#         module_name,
#         module_data
#     )

#     # --------------------------------------------------------
#     # If exact DocType requested
#     # --------------------------------------------------------

#     if only_doctype:

#         log(
#             f"TARGET DOC ONLY: "
#             f"{only_doctype}"
#         )

#         read_document(
#             page,
#             module_name,
#             only_doctype
#         )

#         return

#     # --------------------------------------------------------
#     # Find ALL visible documents
#     # --------------------------------------------------------

#     candidates = (
#         discover_document_candidates(
#             page,
#             module_name
#         )
#     )

#     if not candidates:

#         log(
#             "No visible document candidates found."
#         )

#         return

#     # --------------------------------------------------------
#     # Read one by one
#     # --------------------------------------------------------

#     total = len(candidates)

#     completed = 0
#     skipped = 0
#     failed = 0

#     for index, item in enumerate(
#         candidates,
#         start=1
#     ):

#         name = item["name"]

#         log(
#             f"[{index}/{total}] "
#             f"{name}"
#         )

#         existing = get_existing_discovery()

#         if (
#             normalize_name(name)
#             in existing
#         ):

#             log(
#                 f"SKIP EXISTING: "
#                 f"{name}"
#             )

#             skipped += 1
#             continue

#         try:

#             success = read_document(
#                 page,
#                 module_name,
#                 name,
#                 item.get("url", "")
#             )

#             if success:

#                 completed += 1

#             else:

#                 failed += 1

#         except Exception as exc:

#             failed += 1

#             log(
#                 f"FAILED: "
#                 f"{name} -> {exc}"
#             )

#         # ----------------------------------------------------
#         # Return to module
#         # ----------------------------------------------------

#         try:

#             open_module(
#                 page,
#                 module_name
#             )

#         except Exception as exc:

#             log(
#                 f"Could not return to module: "
#                 f"{exc}"
#             )

#             break

#     # --------------------------------------------------------
#     # Summary
#     # --------------------------------------------------------

#     log(
#         "======================================"
#     )

#     log(
#         f"MODULE COMPLETE: {module_name}"
#     )

#     log(
#         f"Read: {completed}"
#     )

#     log(
#         f"Skipped: {skipped}"
#     )

#     log(
#         f"Failed: {failed}"
#     )

#     log(
#         "======================================"
#     )


# # ============================================================
# # MAIN
# # ============================================================

# def main():

#     args = parse_args()

#     if not args.module:

#         print(
#             "\nExample:\n"
#             '  python discovery_agent.py --module "Import"\n\n'
#             "Or:\n"
#             "  python discovery_agent.py "
#             '--module "Import" --doctype "Budget Head"\n'
#         )

#         return

#     log(
#         "======================================"
#     )

#     log(
#         "ERPNext KNOWLEDGE DISCOVERY AGENT"
#     )

#     log(
#         "======================================"
#     )

#     log(
#         f"Target Module: {args.module}"
#     )

#     if args.doctype:

#         log(
#             f"Target DocType: {args.doctype}"
#         )

#     with sync_playwright() as p:

#         browser = p.chromium.launch(
#             headless=HEADLESS,
#             slow_mo=20
#         )

#         context = browser.new_context(
#             viewport={
#                 "width": 1440,
#                 "height": 900,
#             }
#         )

#         page = context.new_page()

#         try:

#             # ------------------------------------------------
#             # OPEN ERP
#             # ------------------------------------------------

#             log(
#                 f"Opening ERP: {ERP_URL}"
#             )

#             page.goto(
#                 ERP_URL,
#                 wait_until="domcontentloaded",
#                 timeout=TIMEOUT
#             )

#             log(
#                 f"Current URL: {page.url}"
#             )

#             # ------------------------------------------------
#             # LOGIN
#             # ------------------------------------------------

#             login(page)

#             # ------------------------------------------------
#             # HOME
#             # ------------------------------------------------

#             log(
#                 "Opening Home / Desk..."
#             )

#             open_home(
#                 page
#             )

#             # ------------------------------------------------
#             # SCREENSHOT HOME
#             # ------------------------------------------------

#             try:

#                 page.screenshot(
#                     path=str(
#                         SCREENSHOT_DIR
#                         / "home.png"
#                     ),
#                     full_page=True
#                 )

#             except Exception:
#                 pass

#             # ------------------------------------------------
#             # MODULE
#             # ------------------------------------------------

#             open_module(
#                 page,

#                 args.module
#             )

#             # ------------------------------------------------
#             # DISCOVER
#             # ------------------------------------------------

#             discover_module(
#                 page,
#                 args.module,
#                 args.doctype
#             )

#         except Exception as exc:

#             log(
#                 f"FATAL ERROR: {exc}"
#             )

#             try:

#                 page.screenshot(
#                     path=str(
#                         SCREENSHOT_DIR
#                         / "discovery_failure.png"
#                     ),
#                     full_page=True
#                 )

#             except Exception:
#                 pass

#         finally:

#             context.close()
#             browser.close()

#     log(
#         "======================================"
#     )

#     log(
#         "DISCOVERY FINISHED"
#     )

#     log(
#         "======================================"
#     )


# if __name__ == "__main__":
#     main()


# ================================================
import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

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

TIMEOUT = int(os.getenv("DISCOVERY_TIMEOUT", "30000"))
WAIT_MS = int(os.getenv("DISCOVERY_WAIT_MS", "1500"))

DATA_DIR = BASE_DIR / "data"
DISCOVERY_DIR = DATA_DIR / "discovery"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
LOG_DIR = BASE_DIR / "logs"

DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# ARGUMENTS
# ============================================================


def parse_args():

    parser = argparse.ArgumentParser(
        description="Generic ERPNext Knowledge Discovery Agent"
    )

    parser.add_argument("--module", required=True, help="ERPNext module name")

    parser.add_argument("--doctype", required=False, help="Read only one DocType")

    return parser.parse_args()


# ============================================================
# LOG
# ============================================================


def log(message):

    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}",
        flush=True,
    )


# ============================================================
# TEXT HELPERS
# ============================================================


def normalize_name(value):

    if not value:
        return ""

    value = str(value).strip().lower()

    value = re.sub(r"\s+", " ", value)

    return value


def slugify(value):

    value = str(value).strip().lower()

    value = value.replace("&", "and")

    value = re.sub(r"[^a-z0-9]+", "-", value)

    value = re.sub(r"-+", "-", value)

    return value.strip("-")


def absolute_url(value):

    if not value:
        return ""

    if value.startswith("http://"):
        return value

    if value.startswith("https://"):
        return value

    return urljoin(ERP_URL + "/", value)


# ============================================================
# SERIAL FILE
# ============================================================


def next_serial_number():

    highest = 0

    for path in DISCOVERY_DIR.glob("*.json"):

        match = re.match(r"^(\d+)_", path.name)

        if match:

            try:
                highest = max(highest, int(match.group(1)))

            except ValueError:
                pass

    return highest + 1


def make_filename(name):

    serial = next_serial_number()

    slug = slugify(name)

    if not slug:
        slug = "unknown"

    return f"{serial:04d}_{slug}.json"


# ============================================================
# EXISTING KNOWLEDGE
# ============================================================


def get_existing_discovery():

    existing = {}

    for path in DISCOVERY_DIR.glob("*.json"):

        try:

            data = json.loads(path.read_text(encoding="utf-8"))

        except Exception:
            continue

        possible_names = []

        for key in (
            "name",
            "doctype",
            "document",
            "title",
        ):

            value = data.get(key)

            if isinstance(value, str):
                possible_names.append(value)

        for name in possible_names:

            normalized = normalize_name(name)

            if normalized:
                existing[normalized] = path

    return existing


def already_discovered(name):

    existing = get_existing_discovery()

    return normalize_name(name) in existing


# ============================================================
# SAVE
# ============================================================


def save_discovery(name, data):

    existing = get_existing_discovery()

    key = normalize_name(name)

    if key in existing:

        log(f"SKIP EXISTING: {name} " f"-> {existing[key].name}")

        return existing[key]

    filename = make_filename(name)

    path = DISCOVERY_DIR / filename

    data["discovery_file"] = filename

    data["discovered_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    log(f"SAVED: {path}")

    return path


# ============================================================
# ELEMENT INFO
# ============================================================


def element_info(element):

    def attr(name):

        try:
            return element.get_attribute(name) or ""
        except Exception:
            return ""

    try:

        tag = element.evaluate("(el) => el.tagName.toLowerCase()")

    except Exception:

        tag = ""

    try:

        text = (element.inner_text() or "").strip()

    except Exception:

        text = ""

    return {
        "tag": tag,
        "text": text[:500],
        "id": attr("id"),
        "name": attr("name"),
        "type": attr("type"),
        "href": attr("href"),
        "title": attr("title"),
        "aria_label": attr("aria-label"),
        "role": attr("role"),
        "data_route": attr("data-route"),
        "data_link": attr("data-link"),
        "data_href": attr("data-href"),
        "class": attr("class")[:500],
    }


# ============================================================
# FORM FIELD LABEL
# ============================================================


def get_field_label(page, element):

    # --------------------------------------------------------
    # 1. label[for=id]
    # --------------------------------------------------------

    try:

        element_id = element.get_attribute("id") or ""

        if element_id:

            label = page.locator(f"label[for='{element_id}']")

            if label.count() > 0:

                text = (label.first.inner_text() or "").strip()

                if text:
                    return text

    except Exception:
        pass

    # --------------------------------------------------------
    # 2. ERPNext control wrapper
    # --------------------------------------------------------

    selectors = [
        "xpath=ancestor::*[contains(@class,'frappe-control')][1]",
        "xpath=ancestor::*[contains(@class,'form-group')][1]",
        "xpath=ancestor::*[contains(@class,'field')][1]",
    ]

    for selector in selectors:

        try:

            parent = element.locator(selector)

            if parent.count() == 0:
                continue

            # Common ERPNext label classes
            labels = parent.locator(".control-label, " ".form-label, " "label")

            if labels.count() > 0:

                text = (labels.first.inner_text() or "").strip()

                if text:
                    return text

        except Exception:
            continue

    return ""


# ============================================================
# FIELD OPTIONS
# ============================================================


def get_select_options(element):

    options = []

    try:

        locator = element.locator("option")

        count = min(locator.count(), 200)

        for i in range(count):

            option = locator.nth(i)

            try:

                options.append(
                    {
                        "text": (option.inner_text() or "").strip(),
                        "value": (option.get_attribute("value") or ""),
                        "selected": (
                            option.is_checked()
                            if option.get_attribute("type") in ("checkbox", "radio")
                            else False
                        ),
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


# ============================================================
# DISCOVER FORM FIELDS
# ============================================================


def discover_form_fields(page):

    fields = []

    selectors = """
        input,
        textarea,
        select,
        [contenteditable="true"],
        [role="combobox"],
        [role="checkbox"],
        [role="radio"]
    """

    locator = page.locator(selectors)

    try:

        count = min(locator.count(), 3000)

    except Exception:

        count = 0

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            info = element_info(element)

            tag = info["tag"]

            # ------------------------------------------------
            # Value
            # ------------------------------------------------

            value = ""

            try:

                if tag in ("input", "textarea", "select"):

                    value = element.input_value()

            except Exception:
                pass

            # ------------------------------------------------
            # Checked
            # ------------------------------------------------

            checked = None

            try:

                if info["type"] in ("checkbox", "radio"):

                    checked = element.is_checked()

            except Exception:
                pass

            # ------------------------------------------------
            # Field
            # ------------------------------------------------

            field = {
                "label": get_field_label(page, element),
                "name": info["name"],
                "id": info["id"],
                "type": info["type"],
                "tag": info["tag"],
                "placeholder": info["placeholder"] if "placeholder" in info else "",
                "aria_label": info["aria_label"],
                "role": info["role"],
                "value": value,
                "checked": checked,
                "readonly": (element.get_attribute("readonly") is not None),
                "disabled": (
                    element.is_disabled()
                    if tag in ("input", "textarea", "select", "button")
                    else False
                ),
            }

            # ------------------------------------------------
            # Select options
            # ------------------------------------------------

            if tag == "select":

                field["options"] = get_select_options(element)

            fields.append(field)

        except Exception:
            continue

    return fields


# ============================================================
# BUTTON DISCOVERY
# ============================================================


def discover_buttons(page):

    buttons = []

    locator = page.locator("""
        button,
        [role="button"],
        input[type="button"],
        input[type="submit"]
        """)

    try:

        count = min(locator.count(), 1000)

    except Exception:

        count = 0

    seen = set()

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            info = element_info(element)

            text = (info["text"] or info["aria_label"] or info["title"]).strip()

            if not text:
                continue

            key = normalize_name(text)

            if key in seen:
                continue

            seen.add(key)

            buttons.append(
                {
                    "text": text,
                    "type": info["type"],
                    "id": info["id"],
                    "aria_label": info["aria_label"],
                    "title": info["title"],
                }
            )

        except Exception:
            continue

    return buttons


# ============================================================
# TABS
# ============================================================


def discover_tabs(page):

    tabs = []

    locator = page.locator("""
        [role="tab"],
        .form-tabs .nav-link,
        .nav-tabs .nav-link,
        .form-dashboard-section .section-head
        """)

    try:

        count = min(locator.count(), 500)

    except Exception:

        count = 0

    seen = set()

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            text = (element.inner_text() or "").strip()

            if not text:
                continue

            key = normalize_name(text)

            if key in seen:
                continue

            seen.add(key)

            tabs.append(text)

        except Exception:
            continue

    return tabs


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
        "inputs": [],
        "buttons": [],
        "tabs": [],
        "fields": [],
    }

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    try:

        data["title"] = page.title()

    except Exception:
        pass

    # --------------------------------------------------------
    # Body
    # --------------------------------------------------------

    try:

        data["text"] = (page.locator("body").inner_text(timeout=5000))[:60000]

    except Exception:
        pass

    # --------------------------------------------------------
    # Elements
    # --------------------------------------------------------

    locator = page.locator("""
        button,
        input,
        textarea,
        select,
        a,
        [role="button"],
        [role="link"],
        [role="option"],
        [role="tab"],
        [role="menuitem"],
        [contenteditable="true"]
        """)

    try:

        count = min(locator.count(), 3000)

    except Exception:

        count = 0

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            info = element_info(element)

            data["elements"].append(info)

            if info["tag"] == "a":
                data["links"].append(info)

            if info["tag"] == "input":
                data["inputs"].append(info)

            if info["tag"] == "button" or info["role"] == "button":
                data["buttons"].append(info)

        except Exception:
            continue

    # --------------------------------------------------------
    # Form fields
    # --------------------------------------------------------

    data["fields"] = discover_form_fields(page)

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    data["tabs"] = discover_tabs(page)

    return data


# ============================================================
# UI FILTER
# ============================================================

IGNORED_UI = {
    "home",
    "help",
    "settings",
    "logout",
    "log out",
    "login",
    "log in",
    "search",
    "new",
    "edit",
    "delete",
    "save",
    "cancel",
    "close",
    "refresh",
    "back",
    "next",
    "previous",
    "collapse",
    "expand",
    "dashboard",
    "menu",
    "more",
    "actions",
    "submit",
    "yes",
    "no",
    "ok",
    "clear",
}


def valid_candidate_name(text):

    if not text:
        return False

    text = text.strip()

    if len(text) < 2:
        return False

    if len(text) > 150:
        return False

    normalized = normalize_name(text)

    if normalized in IGNORED_UI:
        return False

    if normalized.startswith(
        (
            "click ",
            "go to ",
            "open ",
            "select ",
            "type ",
            "begin typing",
        )
    ):
        return False

    if re.fullmatch(r"[\d\s.,/-]+", text):
        return False

    return True


# ============================================================
# FIND "+ ADD <DOC>" BUTTONS
# ============================================================


def find_add_document_buttons(page):

    results = []

    locator = page.locator("""
        button,
        a,
        [role="button"],
        [role="link"]
        """)

    try:

        count = min(locator.count(), 2000)

    except Exception:

        count = 0

    seen = set()

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            info = element_info(element)

            text = (info["text"] or info["aria_label"] or info["title"] or "").strip()

            if not text:
                continue

            # ------------------------------------------------
            # Normalize:
            #
            # + Add Import LC
            # Add Import LC
            # +Add Import LC
            # ------------------------------------------------

            cleaned = re.sub(r"^\s*\+\s*", "", text).strip()

            match = re.match(r"^add\s+(.+)$", cleaned, re.IGNORECASE)

            if not match:
                continue

            document_name = match.group(1).strip()

            if not valid_candidate_name(document_name):
                continue

            key = normalize_name(document_name)

            if key in seen:
                continue

            seen.add(key)

            href = (
                info["href"]
                or info["data_route"]
                or info["data_link"]
                or info["data_href"]
            )

            results.append(
                {
                    "button_text": text,
                    "document_name": document_name,
                    "url": absolute_url(href),
                }
            )

        except Exception:
            continue

    return results


# ============================================================
# FIND NORMAL DOCUMENT LINKS
# ============================================================


def find_document_links(page):

    results = []

    locator = page.locator("""
        a,
        [role="link"],
        [data-route],
        [data-link],
        [data-href]
        """)

    try:

        count = min(locator.count(), 2000)

    except Exception:

        count = 0

    seen = set()

    for i in range(count):

        try:

            element = locator.nth(i)

            if not element.is_visible():
                continue

            info = element_info(element)

            text = (info["text"] or info["aria_label"] or info["title"] or "").strip()

            if not valid_candidate_name(text):
                continue

            href = (
                info["href"]
                or info["data_route"]
                or info["data_link"]
                or info["data_href"]
            )

            href = absolute_url(href)

            # Only internal links
            if href and not href.startswith(ERP_URL):
                continue

            key = (normalize_name(text), href)

            if key in seen:
                continue

            seen.add(key)

            results.append(
                {
                    "document_name": text,
                    "url": href,
                }
            )

        except Exception:
            continue

    return results


# ============================================================
# FIND EXACT TEXT ELEMENT
# ============================================================


def find_exact_text_element(page, text):

    selectors = [
        f"text={text}",
        f"a:text-is('{text}')",
        f"button:text-is('{text}')",
        f"[role='link']:text-is('{text}')",
        f"[role='button']:text-is('{text}')",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            for i in range(count):

                item = locator.nth(i)

                if item.is_visible():

                    return item

        except Exception:
            continue

    return None


# ============================================================
# OPEN DOCUMENT
# ============================================================


def open_document(page, document_name, document_url=""):

    log(f"Opening document: " f"{document_name}")

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    if document_url:

        if document_url.startswith(ERP_URL):

            try:

                page.goto(document_url, wait_until="domcontentloaded", timeout=TIMEOUT)

                page.wait_for_timeout(WAIT_MS)

                return True

            except Exception as exc:

                log(f"URL open failed: {exc}")

    # --------------------------------------------------------
    # Text click
    # --------------------------------------------------------

    element = find_exact_text_element(page, document_name)

    if not element:

        log(f"Document element not found: " f"{document_name}")

        return False

    try:

        element.click(timeout=10000)

        page.wait_for_timeout(WAIT_MS)

        return True

    except Exception as exc:

        log(f"Click failed: {exc}")

        return False


# ============================================================
# READ DOCUMENT FORM
# ============================================================


def read_document_form(page, module_name, document_name):

    log("======================================")

    log(f"READING DOC: {document_name}")

    log("======================================")

    # --------------------------------------------------------
    # Existing check
    # --------------------------------------------------------

    if already_discovered(document_name):

        log(f"SKIP EXISTING: " f"{document_name}")

        return "skipped"

    # --------------------------------------------------------
    # Wait for page
    # --------------------------------------------------------

    page.wait_for_timeout(WAIT_MS)

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------

    data = discover_page(page)

    data.update(
        {
            "name": document_name,
            "doctype": document_name,
            "module": module_name,
            "knowledge_type": "doctype",
            "source_url": page.url,
        }
    )

    # --------------------------------------------------------
    # Screenshot
    # --------------------------------------------------------

    screenshot = SCREENSHOT_DIR / f"{slugify(document_name)}.png"

    try:

        page.screenshot(path=str(screenshot), full_page=True)

        data["screenshot"] = str(screenshot)

    except Exception:
        pass

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_discovery(document_name, data)

    log(f"FIELDS FOUND: " f"{len(data['fields'])}")

    log(f"BUTTONS FOUND: " f"{len(data['buttons'])}")

    log(f"TABS FOUND: " f"{len(data['tabs'])}")

    return "success"


# ============================================================
# MODULE DISCOVERY
# ============================================================


def discover_module(page, module_name, only_doctype=None):

    log("======================================")

    log(f"MODULE: {module_name}")

    log("======================================")

    # --------------------------------------------------------
    # Save module page
    # --------------------------------------------------------

    module_data = discover_page(page)

    module_data.update(
        {
            "name": module_name,
            "module": module_name,
            "knowledge_type": "module",
        }
    )

    save_discovery(module_name, module_data)

    # --------------------------------------------------------
    # Specific DocType
    # --------------------------------------------------------

    if only_doctype:

        log(f"TARGET DOC: {only_doctype}")

        if already_discovered(only_doctype):

            log(f"SKIP EXISTING: " f"{only_doctype}")

            return

        opened = open_document(page, only_doctype)

        if opened:

            read_document_form(page, module_name, only_doctype)

        return

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # First priority = "+ Add <Doc Name>"
    # --------------------------------------------------------

    add_documents = find_add_document_buttons(page)

    log(f"+ Add documents found: " f"{len(add_documents)}")

    for item in add_documents:

        log(f"  + {item['document_name']}")

    # --------------------------------------------------------
    # Normal visible document links
    # --------------------------------------------------------

    normal_documents = find_document_links(page)

    # --------------------------------------------------------
    # Merge candidates
    # --------------------------------------------------------

    candidates = []

    seen = set()

    for item in add_documents:

        key = normalize_name(item["document_name"])

        if key in seen:
            continue

        seen.add(key)

        candidates.append(
            {
                "document_name": item["document_name"],
                "url": item.get("url", ""),
                "source": "add_button",
            }
        )

    for item in normal_documents:

        key = normalize_name(item["document_name"])

        if key in seen:
            continue

        seen.add(key)

        candidates.append(
            {
                "document_name": item["document_name"],
                "url": item.get("url", ""),
                "source": "visible_link",
            }
        )

    log(f"TOTAL DOCUMENT CANDIDATES: " f"{len(candidates)}")

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    success = 0
    skipped = 0
    failed = 0

    for index, item in enumerate(candidates, start=1):

        name = item["document_name"]

        log(f"[{index}/{len(candidates)}] " f"{name}")

        # ----------------------------------------------------
        # Existing
        # ----------------------------------------------------

        if already_discovered(name):

            log(f"SKIP EXISTING: {name}")

            skipped += 1

            continue

        # ----------------------------------------------------
        # Open
        # ----------------------------------------------------

        try:

            opened = open_document(page, name, item.get("url", ""))

            if not opened:

                failed += 1
                continue

            # ------------------------------------------------
            # Read actual form/page
            # ------------------------------------------------

            result = read_document_form(page, module_name, name)

            if result == "success":

                success += 1

            elif result == "skipped":

                skipped += 1

            else:

                failed += 1

        except Exception as exc:

            failed += 1

            log(f"FAILED: {name} -> {exc}")

        # ----------------------------------------------------
        # Return to module
        # ----------------------------------------------------

        try:

            open_home(page)

            open_module(page, module_name)

        except Exception as exc:

            log(f"Could not return to module: " f"{exc}")

            break

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    log("======================================")

    log(f"MODULE COMPLETE: {module_name}")

    log(f"SUCCESS: {success}")

    log(f"SKIPPED: {skipped}")

    log(f"FAILED: {failed}")

    log("======================================")


# ============================================================
# OPEN HOME
# ============================================================


def open_home(page):

    page.goto(f"{ERP_URL}/app/home", wait_until="domcontentloaded", timeout=TIMEOUT)

    page.wait_for_timeout(WAIT_MS)


# ============================================================
# OPEN MODULE
# ============================================================


def open_module(page, module_name):

    log(f"Opening module: " f"{module_name}")

    # --------------------------------------------------------
    # Try direct route
    # --------------------------------------------------------

    route = slugify(module_name)

    url = f"{ERP_URL}/app/{route}"

    try:

        page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)

        page.wait_for_timeout(WAIT_MS)

        if "/app/" in page.url and page.url.rstrip("/") != f"{ERP_URL}/app":

            log(f"Module URL: {page.url}")

            return True

    except Exception:
        pass

    # --------------------------------------------------------
    # Find module text
    # --------------------------------------------------------

    element = find_exact_text_element(page, module_name)

    if not element:

        raise RuntimeError(f"Module not found: " f"{module_name}")

    element.click()

    page.wait_for_timeout(WAIT_MS)

    log(f"Module URL: {page.url}")

    return True


# ============================================================
# LOGIN
# ============================================================


def login(page):

    log("Checking login state...")

    if "/app" in page.url:

        log("Already logged in.")

        return True

    if not USERNAME:

        raise RuntimeError("ERPNEXT_USER missing " "from .env")

    if not PASSWORD:

        raise RuntimeError("ERPNEXT_PASSWORD missing " "from .env")

    # --------------------------------------------------------
    # Username
    # --------------------------------------------------------

    username = None

    selectors = [
        "input[name='usr']",
        "input[name='login']",
        "input[name='username']",
        "input[autocomplete='username']",
        "input[type='email']",
    ]

    for selector in selectors:

        locator = page.locator(selector)

        try:
            count = locator.count()
        except Exception:
            count = 0

        for i in range(count):

            item = locator.nth(i)

            try:

                if item.is_visible():

                    username = item
                    break

            except Exception:
                continue

        if username:
            break

    if not username:

        raise RuntimeError("Visible username field not found.")

    # --------------------------------------------------------
    # Password
    # --------------------------------------------------------

    password = None

    selectors = [
        "input[name='pwd']",
        "input[name='password']",
        "input[type='password']",
    ]

    for selector in selectors:

        locator = page.locator(selector)

        try:
            count = locator.count()
        except Exception:
            count = 0

        for i in range(count):

            item = locator.nth(i)

            try:

                if item.is_visible():

                    password = item
                    break

            except Exception:
                continue

        if password:
            break

    if not password:

        raise RuntimeError("Visible password field not found.")

    username.fill(USERNAME)

    password.fill(PASSWORD)

    log("Credentials filled.")

    # --------------------------------------------------------
    # Login button
    # --------------------------------------------------------

    login_button = None

    buttons = page.locator("""
        button,
        input[type='submit'],
        [role='button']
        """)

    try:
        count = buttons.count()
    except Exception:
        count = 0

    for i in range(count):

        button = buttons.nth(i)

        try:

            if not button.is_visible():
                continue

            text = (
                " ".join(
                    [
                        button.inner_text() or "",
                        button.get_attribute("value") or "",
                        button.get_attribute("aria-label") or "",
                    ]
                )
                .strip()
                .lower()
            )

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

        raise RuntimeError("Login button not found.")

    login_button.click()

    try:

        page.wait_for_url(re.compile(r".*/app.*"), timeout=15000)

    except PlaywrightTimeoutError:

        page.wait_for_timeout(3000)

    if "/app" not in page.url:

        raise RuntimeError(f"Login failed: {page.url}")

    log(f"LOGIN SUCCESS: {page.url}")

    return True


# ============================================================
# MAIN
# ============================================================


def main():

    args = parse_args()

    log("======================================")

    log("ERPNext KNOWLEDGE DISCOVERY AGENT")

    log("======================================")

    log(f"Module: {args.module}")

    if args.doctype:

        log(f"DocType: {args.doctype}")

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=HEADLESS, slow_mo=20)

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        page = context.new_page()

        try:

            # ------------------------------------------------
            # ERP
            # ------------------------------------------------

            log(f"Opening ERP: {ERP_URL}")

            page.goto(ERP_URL, wait_until="domcontentloaded", timeout=TIMEOUT)

            log(f"Current URL: {page.url}")

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # HOME
            # ------------------------------------------------

            log("Opening Home / Desk...")

            open_home(page)

            log(f"Home URL: {page.url}")

            # ------------------------------------------------
            # Home screenshot
            # ------------------------------------------------

            try:

                page.screenshot(path=str(SCREENSHOT_DIR / "home.png"), full_page=True)

            except Exception:
                pass

            # ------------------------------------------------
            # MODULE
            # ------------------------------------------------

            open_module(page, args.module)

            # ------------------------------------------------
            # DISCOVERY
            # ------------------------------------------------

            discover_module(page, args.module, args.doctype)

        except Exception as exc:

            log(f"FATAL ERROR: {exc}")

            try:

                page.screenshot(
                    path=str(SCREENSHOT_DIR / "discovery_failure.png"), full_page=True
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
