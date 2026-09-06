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

# DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
# SCREENSHOT_DIR = BASE_DIR / "data" / "screenshots"

# DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
# SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# # ============================================================
# # LOG
# # ============================================================


# def log(message):
#     print(
#         f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}",
#         flush=True,
#     )


# # ============================================================
# # TEXT HELPERS
# # ============================================================


# def clean_text(value):
#     if value is None:
#         return ""

#     return re.sub(
#         r"\s+",
#         " ",
#         str(value),
#     ).strip()


# def slugify(value):
#     value = clean_text(value).lower()

#     value = re.sub(
#         r"[^a-z0-9]+",
#         "-",
#         value,
#     )

#     value = value.strip("-")

#     return value or "unknown"


# # ============================================================
# # DISCOVERY FILE MANAGEMENT
# # ============================================================


# def existing_discovery_doctypes():
#     """
#     Read all existing discovery JSON files and return
#     their known DocType names.
#     """

#     discovered = set()

#     for path in DISCOVERY_DIR.glob("*.json"):

#         try:

#             data = json.loads(path.read_text(encoding="utf-8"))

#             doctype = clean_text(data.get("doctype") or data.get("document_name") or "")

#             if doctype:
#                 discovered.add(doctype.lower())

#         except Exception:
#             continue

#     return discovered


# def next_serial_number():
#     """
#     Find next serial number from existing files.

#     Example:

#     0001_company-budget.json
#     0002_import-lc.json

#     next = 0003
#     """

#     maximum = 0

#     pattern = re.compile(r"^(\d+)_")

#     for path in DISCOVERY_DIR.glob("*.json"):

#         match = pattern.match(path.name)

#         if not match:
#             continue

#         try:
#             number = int(match.group(1))

#             maximum = max(
#                 maximum,
#                 number,
#             )

#         except ValueError:
#             continue

#     return maximum + 1


# def discovery_file_for_doctype(doctype):
#     """
#     Find existing JSON for a DocType.

#     Primary check:
#     - JSON content

#     Secondary check:
#     - filename slug
#     """

#     target = clean_text(doctype).lower()
#     target_slug = slugify(doctype)

#     for path in DISCOVERY_DIR.glob("*.json"):

#         # Filename check
#         filename = path.stem

#         match = re.match(
#             r"^\d+_(.+)$",
#             filename,
#         )

#         if match:

#             if match.group(1).lower() == target_slug:
#                 return path

#         # Content check
#         try:

#             data = json.loads(path.read_text(encoding="utf-8"))

#             stored = clean_text(
#                 data.get("doctype") or data.get("document_name") or ""
#             ).lower()

#             if stored == target:
#                 return path

#         except Exception:
#             pass

#     return None


# def save_discovery(data):
#     """
#     Save discovery using:

#     0001_company-budget.json
#     0002_import-lc.json
#     """

#     doctype = clean_text(data.get("doctype") or data.get("document_name") or "unknown")

#     existing = discovery_file_for_doctype(doctype)

#     if existing:

#         log(f"SKIP SAVE: already exists -> " f"{existing.name}")

#         return existing

#     serial = next_serial_number()

#     filename = f"{serial:04d}_" f"{slugify(doctype)}.json"

#     path = DISCOVERY_DIR / filename

#     path.write_text(
#         json.dumps(
#             data,
#             indent=2,
#             ensure_ascii=False,
#         ),
#         encoding="utf-8",
#     )

#     log(f"Knowledge saved: {path}")

#     return path


# # ============================================================
# # VISIBLE ELEMENTS
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
#         [role="combobox"],
#         [contenteditable="true"]
#     """

#     locator = page.locator(selectors)

#     try:
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

#             tag = element.evaluate("(el) => el.tagName.toLowerCase()")

#             item = {
#                 "tag": tag,
#                 "text": clean_text(element.inner_text())[:300],
#                 "id": (element.get_attribute("id") or ""),
#                 "name": (element.get_attribute("name") or ""),
#                 "type": (element.get_attribute("type") or ""),
#                 "placeholder": (element.get_attribute("placeholder") or ""),
#                 "aria_label": (element.get_attribute("aria-label") or ""),
#                 "title": (element.get_attribute("title") or ""),
#                 "role": (element.get_attribute("role") or ""),
#                 "value": (element.get_attribute("value") or ""),
#                 "data_fieldname": (element.get_attribute("data-fieldname") or ""),
#                 "class": (element.get_attribute("class") or "")[:500],
#             }

#             elements.append(item)

#         except Exception:
#             continue

#     return elements


# # ============================================================
# # FIELD DISCOVERY
# # ============================================================


# def discover_form_fields(page):

#     fields = []

#     # --------------------------------------------------------
#     # ERPNext field wrappers
#     # --------------------------------------------------------

#     wrappers = page.locator("""
#         .frappe-control,
#         .form-group,
#         [data-fieldname]
#         """)

#     try:
#         count = min(
#             wrappers.count(),
#             500,
#         )

#     except Exception:
#         count = 0

#     seen = set()

#     for i in range(count):

#         wrapper = wrappers.nth(i)

#         try:

#             if not wrapper.is_visible():
#                 continue

#             fieldname = wrapper.get_attribute("data-fieldname") or ""

#             # Try child data-fieldname
#             if not fieldname:

#                 child = wrapper.locator("[data-fieldname]")

#                 if child.count() > 0:

#                     fieldname = child.first.get_attribute("data-fieldname") or ""

#             if not fieldname:
#                 continue

#             fieldname = clean_text(fieldname)

#             if fieldname in seen:
#                 continue

#             seen.add(fieldname)

#             # ------------------------------------------------
#             # Label
#             # ------------------------------------------------

#             label = ""

#             try:

#                 label_locator = wrapper.locator(".control-label, label")

#                 if label_locator.count() > 0:

#                     label = clean_text(label_locator.first.inner_text())

#             except Exception:
#                 pass

#             if not label:
#                 label = fieldname

#             # ------------------------------------------------
#             # Input
#             # ------------------------------------------------

#             input_locator = wrapper.locator(
#                 "input, textarea, select, [contenteditable='true']"
#             )

#             value = ""

#             fieldtype = "unknown"

#             options = []

#             if input_locator.count() > 0:

#                 control = input_locator.first

#                 try:

#                     tag = control.evaluate("(el) => el.tagName.toLowerCase()")

#                 except Exception:
#                     tag = ""

#                 try:

#                     control_type = (control.get_attribute("type") or "").lower()

#                 except Exception:
#                     control_type = ""

#                 # ------------------------------------------------
#                 # Field type
#                 # ------------------------------------------------

#                 if tag == "select":

#                     fieldtype = "Select"

#                 elif control_type == "checkbox":

#                     fieldtype = "Check"

#                 elif control_type == "date":

#                     fieldtype = "Date"

#                 elif control_type == "datetime-local":

#                     fieldtype = "Datetime"

#                 elif control_type == "number":

#                     fieldtype = "Float"

#                 elif control_type == "email":

#                     fieldtype = "Data"

#                 else:

#                     # ERPNext Link field
#                     try:

#                         has_link_class = "link-field" in (
#                             wrapper.get_attribute("class") or ""
#                         )

#                     except Exception:
#                         has_link_class = False

#                     if has_link_class:
#                         fieldtype = "Link"
#                     else:
#                         fieldtype = "Data"

#                 # ------------------------------------------------
#                 # Value
#                 # ------------------------------------------------

#                 try:

#                     if tag == "textarea":

#                         value = control.input_value() or ""

#                     elif tag == "select":

#                         value = control.input_value() or ""

#                     elif control_type == "checkbox":

#                         value = control.is_checked()

#                     else:

#                         value = control.input_value() or ""

#                 except Exception:
#                     pass

#                 # ------------------------------------------------
#                 # Select options
#                 # ------------------------------------------------

#                 if tag == "select":

#                     try:

#                         option_locator = control.locator("option")

#                         option_count = min(
#                             option_locator.count(),
#                             200,
#                         )

#                         for j in range(option_count):

#                             option = option_locator.nth(j)

#                             try:

#                                 options.append(
#                                     {
#                                         "text": clean_text(option.inner_text()),
#                                         "value": (option.get_attribute("value") or ""),
#                                     }
#                                 )

#                             except Exception:
#                                 continue

#                     except Exception:
#                         pass

#                 # ------------------------------------------------
#                 # Link / autocomplete options
#                 # ------------------------------------------------

#                 if fieldtype == "Link":

#                     options.extend(
#                         discover_link_options(
#                             page,
#                             wrapper,
#                         )
#                     )

#             fields.append(
#                 {
#                     "fieldname": fieldname,
#                     "label": label,
#                     "fieldtype": fieldtype,
#                     "value": value,
#                     "options": options,
#                 }
#             )

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Fallback: direct data-fieldname elements
#     # --------------------------------------------------------

#     if not fields:

#         direct = page.locator("[data-fieldname]")

#         try:
#             count = min(
#                 direct.count(),
#                 500,
#             )
#         except Exception:
#             count = 0

#         for i in range(count):

#             element = direct.nth(i)

#             try:

#                 if not element.is_visible():
#                     continue

#                 fieldname = clean_text(element.get_attribute("data-fieldname") or "")

#                 if not fieldname:
#                     continue

#                 if fieldname in seen:
#                     continue

#                 seen.add(fieldname)

#                 fields.append(
#                     {
#                         "fieldname": fieldname,
#                         "label": fieldname,
#                         "fieldtype": "unknown",
#                         "value": "",
#                         "options": [],
#                     }
#                 )

#             except Exception:
#                 continue

#     return fields


# def discover_link_options(page, wrapper):
#     """
#     Read currently visible autocomplete options for a Link field.
#     Does not type anything into the field.
#     """

#     options = []

#     try:

#         candidates = page.locator("""
#             .awesomplete li,
#             .awesomplete ul li,
#             .ac-option,
#             .link-option,
#             [role="option"]
#             """)

#         count = min(
#             candidates.count(),
#             100,
#         )

#         for i in range(count):

#             option = candidates.nth(i)

#             try:

#                 if not option.is_visible():
#                     continue

#                 text = clean_text(option.inner_text())

#                 if text:

#                     options.append(
#                         {
#                             "text": text,
#                             "value": text,
#                         }
#                     )

#             except Exception:
#                 continue

#     except Exception:
#         pass

#     return options


# # ============================================================
# # TABS
# # ============================================================


# def discover_tabs(page):

#     tabs = []

#     selectors = [
#         "[role='tab']",
#         ".form-tabs .nav-link",
#         ".form-tabs a",
#         ".nav-tabs .nav-link",
#     ]

#     seen = set()

#     for selector in selectors:

#         locator = page.locator(selector)

#         try:
#             count = min(
#                 locator.count(),
#                 100,
#             )
#         except Exception:
#             count = 0

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if not item.is_visible():
#                     continue

#                 text = clean_text(item.inner_text())

#                 if text and text not in seen:

#                     seen.add(text)
#                     tabs.append(text)

#             except Exception:
#                 continue

#     return tabs


# # ============================================================
# # SECTIONS
# # ============================================================


# def discover_sections(page):

#     sections = []

#     selectors = [
#         ".section-head",
#         ".form-section .section-head",
#         ".form-dashboard-section .section-head",
#         ".collapse-label",
#     ]

#     seen = set()

#     for selector in selectors:

#         locator = page.locator(selector)

#         try:
#             count = min(
#                 locator.count(),
#                 200,
#             )
#         except Exception:
#             count = 0

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if not item.is_visible():
#                     continue

#                 text = clean_text(item.inner_text())

#                 if text and text not in seen:

#                     seen.add(text)
#                     sections.append(text)

#             except Exception:
#                 continue

#     return sections


# # ============================================================
# # BUTTONS
# # ============================================================


# def discover_buttons(page):

#     buttons = []

#     locator = page.locator("""
#         button,
#         [role="button"],
#         input[type="button"],
#         input[type="submit"]
#         """)

#     seen = set()

#     try:
#         count = min(
#             locator.count(),
#             300,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         button = locator.nth(i)

#         try:

#             if not button.is_visible():
#                 continue

#             text = clean_text(button.inner_text())

#             if not text:

#                 text = clean_text(
#                     button.get_attribute("aria-label")
#                     or button.get_attribute("title")
#                     or button.get_attribute("value")
#                     or ""
#                 )

#             if text and text not in seen:

#                 seen.add(text)
#                 buttons.append(text)

#         except Exception:
#             continue

#     return buttons


# # ============================================================
# # LINKS
# # ============================================================


# def discover_links(page):

#     links = []

#     locator = page.locator("a")

#     try:
#         count = min(
#             locator.count(),
#             500,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         link = locator.nth(i)

#         try:

#             if not link.is_visible():
#                 continue

#             text = clean_text(link.inner_text())

#             href = link.get_attribute("href") or ""

#             if text or href:

#                 links.append(
#                     {
#                         "text": text[:300],
#                         "href": href[:500],
#                     }
#                 )

#         except Exception:
#             continue

#     return links


# # ============================================================
# # PAGE DISCOVERY
# # ============================================================


# def discover_page(page, doctype="", read_mode="unknown"):

#     data = {
#         "knowledge_type": "erpnext_doctype",
#         "module": "",
#         "doctype": doctype,
#         "document_name": doctype,
#         "read_mode": read_mode,
#         "existing_documents_skipped": True,
#         "url": page.url,
#         "title": "",
#         "text": "",
#         "fields": [],
#         "tabs": [],
#         "sections": [],
#         "buttons": [],
#         "links": [],
#         "elements": [],
#     }

#     try:

#         data["title"] = page.title()

#     except Exception:
#         pass

#     try:

#         data["text"] = clean_text(page.locator("body").inner_text(timeout=10000))[
#             :30000
#         ]

#     except Exception:
#         pass

#     data["fields"] = discover_form_fields(page)

#     data["tabs"] = discover_tabs(page)

#     data["sections"] = discover_sections(page)

#     data["buttons"] = discover_buttons(page)

#     data["links"] = discover_links(page)

#     data["elements"] = discover_elements(page)

#     return data


# # ============================================================
# # LOGIN
# # ============================================================


# def find_visible_locator(
#     page,
#     selectors,
# ):
#     for selector in selectors:

#         locator = page.locator(selector)

#         try:
#             count = locator.count()
#         except Exception:
#             count = 0

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

#         log("Already logged in.")

#         return True

#     # --------------------------------------------------------
#     # Username
#     # --------------------------------------------------------

#     username = find_visible_locator(
#         page,
#         [
#             "input[name='usr']",
#             "input[autocomplete='username']",
#             "input[name='login']",
#             "input[type='email']",
#             "input[type='text']",
#         ],
#     )

#     if not username:

#         raise RuntimeError("Visible username field not found.")

#     # --------------------------------------------------------
#     # Password
#     # --------------------------------------------------------

#     password = find_visible_locator(
#         page,
#         [
#             "input[name='pwd']",
#             "input[name='password']",
#             "input[type='password']",
#         ],
#     )

#     if not password:

#         raise RuntimeError("Visible password field not found.")

#     username.fill(USERNAME)

#     password.fill(PASSWORD)

#     log("Credentials filled.")

#     # --------------------------------------------------------
#     # Login button
#     # --------------------------------------------------------

#     login_button = None

#     buttons = page.locator("""
#         button,
#         input[type='submit'],
#         [role='button']
#         """)

#     try:
#         count = buttons.count()
#     except Exception:
#         count = 0

#     for i in range(count):

#         button = buttons.nth(i)

#         try:

#             if not button.is_visible():
#                 continue

#             text = clean_text(
#                 " ".join(
#                     [
#                         button.inner_text() or "",
#                         button.get_attribute("value") or "",
#                         button.get_attribute("aria-label") or "",
#                     ]
#                 )
#             ).lower()

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

#         raise RuntimeError("Login button not found.")

#     login_button.click()

#     try:

#         page.wait_for_url(
#             re.compile(r"/app"),
#             timeout=15000,
#         )

#     except PlaywrightTimeoutError:

#         page.wait_for_timeout(3000)

#     log(f"Login URL: {page.url}")

#     if "/app" not in page.url:

#         raise RuntimeError("Login failed.")

#     log("LOGIN SUCCESS")

#     return True


# # ============================================================
# # HOME
# # ============================================================


# def open_home(page):

#     log("Opening Home / Desk...")

#     page.goto(
#         f"{ERP_URL}/app/home",
#         wait_until="domcontentloaded",
#         timeout=30000,
#     )

#     page.wait_for_timeout(1500)

#     log(f"Home URL: {page.url}")


# # ============================================================
# # MODULE NAVIGATION
# # ============================================================


# def normalize_route(text):
#     return slugify(text)


# def find_module(page, module_name):

#     target = clean_text(module_name).lower()

#     log(f"Finding module: {module_name}")

#     # --------------------------------------------------------
#     # First: visible text
#     # --------------------------------------------------------

#     candidates = page.get_by_text(
#         module_name,
#         exact=True,
#     )

#     try:
#         count = candidates.count()
#     except Exception:
#         count = 0

#     for i in range(count):

#         item = candidates.nth(i)

#         try:

#             if item.is_visible():
#                 return item

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Second: links/buttons containing text
#     # --------------------------------------------------------

#     candidates = page.locator("""
#         a,
#         button,
#         [role="button"],
#         .module-link,
#         .desk-sidebar-item
#         """)

#     try:
#         count = min(
#             candidates.count(),
#             500,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         item = candidates.nth(i)

#         try:

#             if not item.is_visible():
#                 continue

#             text = clean_text(item.inner_text()).lower()

#             if text == target:

#                 return item

#         except Exception:
#             continue

#     return None


# def open_module(page, module_name):

#     item = find_module(
#         page,
#         module_name,
#     )

#     if not item:

#         raise RuntimeError(f"Module not found: {module_name}")

#     log(f"Opening module: {module_name}")

#     item.click()

#     page.wait_for_timeout(1500)

#     log(f"Module URL: {page.url}")


# # ============================================================
# # DOC TYPE DETECTION
# # ============================================================


# def is_probable_record_name(text):
#     """
#     Existing ERPNext records often look like:

#     BUDGET-00000025
#     SAL-ORD-2026-00001
#     INV-00001

#     We don't want to treat those as DocTypes.
#     """

#     text = clean_text(text)

#     if not text:
#         return False

#     patterns = [
#         r"^[A-Z]{2,}[-_]\d{3,}",
#         r"^[A-Z0-9]+-\d{4,}$",
#         r"^\d+$",
#     ]

#     return any(
#         re.match(
#             pattern,
#             text,
#         )
#         for pattern in patterns
#     )


# def clean_doctype_candidate(text):

#     text = clean_text(text)

#     if not text:
#         return ""

#     if is_probable_record_name(text):
#         return ""

#     bad = {
#         "list view",
#         "kanban",
#         "calendar",
#         "report",
#         "dashboard",
#         "filter",
#         "filters",
#         "load more",
#         "help",
#         "settings",
#         "search",
#         "actions",
#         "add",
#     }

#     if text.lower() in bad:
#         return ""

#     # Avoid very long UI sentences
#     if len(text) > 100:
#         return ""

#     return text


# # ============================================================
# # MODULE DOC DISCOVERY
# # ============================================================


# def discover_module_docs(page):
#     """
#     Discover visible DocType entries inside a module.

#     Important:
#     We do NOT depend on "Quick Access".

#     We inspect visible links/buttons/cards and also
#     href patterns such as /app/<route>.
#     """

#     docs = []

#     seen = set()

#     def add_candidate(
#         text,
#         href="",
#     ):

#         text = clean_doctype_candidate(text)

#         if not text:
#             return

#         key = text.lower()

#         if key in seen:
#             return

#         seen.add(key)

#         docs.append(
#             {
#                 "doctype": text,
#                 "href": href,
#             }
#         )

#     # --------------------------------------------------------
#     # 1. Visible links
#     # --------------------------------------------------------

#     links = page.locator("a")

#     try:
#         count = min(
#             links.count(),
#             1000,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         link = links.nth(i)

#         try:

#             if not link.is_visible():
#                 continue

#             text = clean_text(link.inner_text())

#             href = link.get_attribute("href") or ""

#             # Only likely ERP routes
#             if href.startswith("/app/") or "/app/" in href:

#                 add_candidate(
#                     text,
#                     href,
#                 )

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # 2. Visible buttons/cards
#     # --------------------------------------------------------

#     clickable = page.locator("""
#         button,
#         [role="button"],
#         .module-card,
#         .desk-card,
#         .link-card,
#         .widget
#         """)

#     try:
#         count = min(
#             clickable.count(),
#             1000,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         item = clickable.nth(i)

#         try:

#             if not item.is_visible():
#                 continue

#             text = clean_text(item.inner_text())

#             href = item.get_attribute("href") or ""

#             add_candidate(
#                 text,
#                 href,
#             )

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # 3. Look for "Add <DocType>" buttons
#     # --------------------------------------------------------

#     buttons = page.locator("""
#         button,
#         [role="button"],
#         a
#         """)

#     try:
#         count = min(
#             buttons.count(),
#             1000,
#         )
#     except Exception:
#         count = 0

#     add_pattern = re.compile(
#         r"^\+?\s*add\s+(.+)$",
#         re.I,
#     )

#     for i in range(count):

#         item = buttons.nth(i)

#         try:

#             if not item.is_visible():
#                 continue

#             text = clean_text(item.inner_text())

#             match = add_pattern.match(text)

#             if match:

#                 candidate = clean_doctype_candidate(match.group(1))

#                 if candidate:

#                     add_candidate(
#                         candidate,
#                         "",
#                     )

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # 4. Remove obvious non-Doc entries
#     # --------------------------------------------------------

#     filtered = []

#     for item in docs:

#         text = item["doctype"]

#         lower = text.lower()

#         if lower in {
#             "home",
#             "import",
#             "accounting",
#             "inventory",
#             "assets",
#             "production",
#             "quality",
#             "planning",
#             "support",
#             "crm",
#             "settings",
#         }:
#             continue

#         filtered.append(item)

#     return filtered


# # ============================================================
# # FIND DOCTYPE LIST PAGE
# # ============================================================


# def find_doctype_route(
#     page,
#     doctype,
# ):
#     """
#     Try to find a link that points to this DocType.
#     """

#     target = clean_text(doctype).lower()

#     links = page.locator("a")

#     try:
#         count = min(
#             links.count(),
#             1000,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         link = links.nth(i)

#         try:

#             if not link.is_visible():
#                 continue

#             text = clean_text(link.inner_text()).lower()

#             href = link.get_attribute("href") or ""

#             if text == target or target in text:

#                 if href:

#                     return urljoin(
#                         ERP_URL + "/",
#                         href,
#                     )

#         except Exception:
#             continue

#     return None


# def guess_doctype_route(doctype):

#     return f"{ERP_URL}/app/" f"{slugify(doctype)}"


# # ============================================================
# # OPEN DOCTYPE LIST
# # ============================================================


# def open_doctype_list(
#     page,
#     doctype,
# ):

#     log(f"Opening DocType list: {doctype}")

#     route = find_doctype_route(
#         page,
#         doctype,
#     )

#     if not route:

#         route = guess_doctype_route(doctype)

#     log(f"DocType route: {route}")

#     page.goto(
#         route,
#         wait_until="domcontentloaded",
#         timeout=30000,
#     )

#     page.wait_for_timeout(1200)

#     return page.url


# # ============================================================
# # ADD NEW DOCUMENT
# # ============================================================


# def find_add_button(
#     page,
#     doctype,
# ):

#     target = clean_text(doctype).lower()

#     expected = [
#         f"add {target}",
#         f"+ add {target}",
#         f"new {target}",
#     ]

#     # --------------------------------------------------------
#     # Exact text
#     # --------------------------------------------------------

#     candidates = page.locator("""
#         button,
#         a,
#         [role="button"]
#         """)

#     try:
#         count = min(
#             candidates.count(),
#             1000,
#         )
#     except Exception:
#         count = 0

#     for i in range(count):

#         item = candidates.nth(i)

#         try:

#             if not item.is_visible():
#                 continue

#             text = clean_text(
#                 " ".join(
#                     [
#                         item.inner_text() or "",
#                         item.get_attribute("aria-label") or "",
#                         item.get_attribute("title") or "",
#                     ]
#                 )
#             ).lower()

#             if text in expected:

#                 return item

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Contains "Add <DocType>"
#     # --------------------------------------------------------

#     for i in range(count):

#         item = candidates.nth(i)

#         try:

#             if not item.is_visible():
#                 continue

#             text = clean_text(item.inner_text()).lower()

#             if "add" in text and target in text:

#                 return item

#         except Exception:
#             continue

#     # --------------------------------------------------------
#     # Generic Add button on DocType list
#     # --------------------------------------------------------

#     generic = [
#         "button:has-text('Add')",
#         "button:has-text('New')",
#         "a:has-text('Add')",
#         "[role='button']:has-text('Add')",
#     ]

#     for selector in generic:

#         locator = page.locator(selector)

#         try:
#             count = locator.count()
#         except Exception:
#             count = 0

#         for i in range(count):

#             item = locator.nth(i)

#             try:

#                 if item.is_visible():

#                     return item

#             except Exception:
#                 continue

#     return None


# def click_add_new_document(
#     page,
#     doctype,
# ):

#     log(f"Looking for + Add {doctype}")

#     add_button = find_add_button(
#         page,
#         doctype,
#     )

#     if not add_button:

#         raise RuntimeError(f"+ Add {doctype} button not found.")

#     log(f"Clicking + Add {doctype}")

#     before_url = page.url

#     add_button.click()

#     try:

#         page.wait_for_url(
#             re.compile(r"/app/"),
#             timeout=10000,
#         )

#     except PlaywrightTimeoutError:
#         pass

#     page.wait_for_timeout(1500)

#     after_url = page.url

#     log(f"New document URL: {after_url}")

#     # --------------------------------------------------------
#     # Verify we are not still on list
#     # --------------------------------------------------------

#     if after_url == before_url:

#         # Maybe route did not change immediately.
#         page.wait_for_timeout(1500)

#     return page.url


# # ============================================================
# # VERIFY NEW DOCUMENT
# # ============================================================


# def verify_new_document(
#     page,
#     doctype,
# ):

#     url = page.url.lower()

#     # Common new route:
#     # /app/<route>/new-<doctype>
#     # /app/<doctype>/new-<doctype>

#     has_new = "new-" in url or "/new/" in url

#     # Look at page text
#     try:

#         body_text = clean_text(page.locator("body").inner_text(timeout=5000)).lower()

#     except Exception:
#         body_text = ""

#     title = clean_text(doctype).lower()

#     indicators = [
#         f"new {title}",
#         f"new-{slugify(doctype)}",
#         "save",
#         "submit",
#     ]

#     text_indicator = any(item in body_text for item in indicators)

#     if has_new or text_indicator:

#         log(f"New document confirmed: {doctype}")

#         return True

#     # --------------------------------------------------------
#     # Check form fields
#     # --------------------------------------------------------

#     fields = page.locator("[data-fieldname]")

#     try:

#         if fields.count() > 0:

#             log(f"Form detected for: {doctype}")

#             return True

#     except Exception:
#         pass

#     return False


# # ============================================================
# # DISCOVER ONE DOCTYPE
# # ============================================================


# def discover_doctype(
#     page,
#     doctype,
#     module_name="",
# ):

#     doctype = clean_text(doctype)

#     if not doctype:
#         return None

#     # --------------------------------------------------------
#     # Existing JSON validation
#     # --------------------------------------------------------

#     existing = discovery_file_for_doctype(doctype)

#     if existing:

#         log(f"SKIP: {doctype} " f"already discovered -> " f"{existing.name}")

#         return existing

#     log("--------------------------------------")

#     log(f"DISCOVERING DOCTYPE: {doctype}")

#     log("--------------------------------------")

#     # --------------------------------------------------------
#     # Open list
#     # --------------------------------------------------------

#     open_doctype_list(
#         page,
#         doctype,
#     )

#     # --------------------------------------------------------
#     # Screenshot list
#     # --------------------------------------------------------

#     list_screenshot = SCREENSHOT_DIR / f"{slugify(doctype)}_list.png"

#     try:

#         page.screenshot(
#             path=str(list_screenshot),
#             full_page=True,
#         )

#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # Click + Add
#     # --------------------------------------------------------

#     click_add_new_document(
#         page,
#         doctype,
#     )

#     # --------------------------------------------------------
#     # Verify
#     # --------------------------------------------------------

#     if not verify_new_document(
#         page,
#         doctype,
#     ):

#         raise RuntimeError(f"Could not confirm new document " f"for {doctype}")

#     # --------------------------------------------------------
#     # Read form
#     # --------------------------------------------------------

#     page.wait_for_timeout(1000)

#     log(f"Reading all fields: {doctype}")

#     data = discover_page(
#         page,
#         doctype=doctype,
#         read_mode="blank_new_document",
#     )

#     data["module"] = module_name

#     # --------------------------------------------------------
#     # Save screenshot
#     # --------------------------------------------------------

#     screenshot = SCREENSHOT_DIR / f"{slugify(doctype)}_new.png"

#     try:

#         page.screenshot(
#             path=str(screenshot),
#             full_page=True,
#         )

#         log(f"Screenshot saved: {screenshot}")

#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # Save JSON
#     # --------------------------------------------------------

#     saved = save_discovery(data)

#     log(f"Fields discovered: " f"{len(data['fields'])}")

#     log(f"Tabs discovered: " f"{len(data['tabs'])}")

#     log(f"Sections discovered: " f"{len(data['sections'])}")

#     log(f"Buttons discovered: " f"{len(data['buttons'])}")

#     log(f"COMPLETED: {doctype}")

#     return saved


# # ============================================================
# # MODULE DISCOVERY
# # ============================================================


# def discover_module(
#     page,
#     module_name,
# ):

#     log("======================================")

#     log(f"FULL MODULE DISCOVERY: {module_name}")

#     log("======================================")

#     # --------------------------------------------------------
#     # Open module
#     # --------------------------------------------------------

#     open_home(page)

#     open_module(
#         page,
#         module_name,
#     )

#     page.wait_for_timeout(1000)

#     # --------------------------------------------------------
#     # Screenshot module
#     # --------------------------------------------------------

#     module_screenshot = SCREENSHOT_DIR / f"module_{slugify(module_name)}.png"

#     try:

#         page.screenshot(
#             path=str(module_screenshot),
#             full_page=True,
#         )

#     except Exception:
#         pass

#     # --------------------------------------------------------
#     # Find visible DocTypes
#     # --------------------------------------------------------

#     docs = discover_module_docs(page)

#     log(f"Visible document candidates: " f"{len(docs)}")

#     for index, item in enumerate(
#         docs,
#         start=1,
#     ):

#         log(f"{index}. " f"{item['doctype']}")

#     if not docs:

#         log("No visible DocTypes detected.")

#         return

#     # --------------------------------------------------------
#     # Process one by one
#     # --------------------------------------------------------

#     success = 0
#     skipped = 0
#     failed = 0

#     for index, item in enumerate(
#         docs,
#         start=1,
#     ):

#         doctype = item["doctype"]

#         log("======================================")

#         log(f"MODULE DOC {index}/{len(docs)}: " f"{doctype}")

#         log("======================================")

#         # Existing check before opening
#         existing = discovery_file_for_doctype(doctype)

#         if existing:

#             log(f"SKIP EXISTING: {doctype} " f"-> {existing.name}")

#             skipped += 1

#             continue

#         try:

#             discover_doctype(
#                 page,
#                 doctype,
#                 module_name=module_name,
#             )

#             success += 1

#         except Exception as exc:

#             failed += 1

#             log(f"FAILED: {doctype}")

#             log(f"Reason: {exc}")

#             # ------------------------------------------------
#             # Failure screenshot
#             # ------------------------------------------------

#             try:

#                 path = SCREENSHOT_DIR / f"failure_{slugify(doctype)}.png"

#                 page.screenshot(
#                     path=str(path),
#                     full_page=True,
#                 )

#             except Exception:
#                 pass

#             # ------------------------------------------------
#             # Return to module and continue
#             # ------------------------------------------------

#             try:

#                 open_home(page)

#                 open_module(
#                     page,
#                     module_name,
#                 )

#                 page.wait_for_timeout(1000)

#             except Exception as recovery_error:

#                 log(f"Recovery failed: " f"{recovery_error}")

#     # --------------------------------------------------------
#     # Summary
#     # --------------------------------------------------------

#     log("======================================")

#     log(f"MODULE DISCOVERY FINISHED: " f"{module_name}")

#     log(f"SUCCESS: {success}")

#     log(f"SKIPPED: {skipped}")

#     log(f"FAILED: {failed}")

#     log("Agent will now STOP.")

#     log("======================================")


# # ============================================================
# # SINGLE DOCTYPE DISCOVERY
# # ============================================================


# def discover_single_doctype(
#     page,
#     doctype,
# ):

#     log("======================================")

#     log(f"SINGLE DOCTYPE DISCOVERY: {doctype}")

#     log("======================================")

#     existing = discovery_file_for_doctype(doctype)

#     if existing:

#         log(f"ALREADY EXISTS: {existing}")

#         log("Nothing to do.")

#         return

#     discover_doctype(
#         page,
#         doctype,
#         module_name="",
#     )

#     log("======================================")

#     log(f"DOC TYPE DISCOVERY FINISHED: " f"{doctype}")

#     log("Agent will now STOP.")

#     log("======================================")


# # ============================================================
# # ARGUMENTS
# # ============================================================


# def parse_args():

#     parser = argparse.ArgumentParser(description=("ERPNext Knowledge Discovery Agent"))

#     parser.add_argument(
#         "--module",
#         required=False,
#         help=("Discover all visible DocTypes " "inside the module."),
#     )

#     parser.add_argument(
#         "--doctype",
#         required=False,
#         help=("Discover only this DocType."),
#     )

#     args = parser.parse_args()

#     if not args.module and not args.doctype:

#         parser.error("Give either --module or --doctype.")

#     if args.module and args.doctype:

#         log("Both --module and --doctype supplied.")

#         log("Priority: specific --doctype.")

#         args.module = None

#     return args


# # ============================================================
# # MAIN
# # ============================================================


# def main():

#     args = parse_args()

#     log("======================================")

#     log("ERPNext KNOWLEDGE DISCOVERY AGENT")

#     log("======================================")

#     log(f"ERP: {ERP_URL}")

#     if args.module:

#         log(f"MODE: MODULE")

#         log(f"MODULE: {args.module}")

#     else:

#         log(f"MODE: SINGLE DOCTYPE")

#         log(f"DOCTYPE: {args.doctype}")

#     with sync_playwright() as p:

#         browser = p.chromium.launch(
#             headless=HEADLESS,
#             slow_mo=30,
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

#             log(f"Opening ERP: {ERP_URL}")

#             page.goto(
#                 ERP_URL,
#                 wait_until="domcontentloaded",
#                 timeout=30000,
#             )

#             log(f"Current URL: {page.url}")

#             # ------------------------------------------------
#             # LOGIN
#             # ------------------------------------------------

#             login(page)

#             # ------------------------------------------------
#             # HOME
#             # ------------------------------------------------

#             open_home(page)

#             # ------------------------------------------------
#             # MODE
#             # ------------------------------------------------

#             if args.doctype:

#                 discover_single_doctype(
#                     page,
#                     args.doctype,
#                 )

#             elif args.module:

#                 discover_module(
#                     page,
#                     args.module,
#                 )

#         except Exception as exc:

#             log(f"FATAL ERROR: {exc}")

#             try:

#                 failure = SCREENSHOT_DIR / "discovery_failure.png"

#                 page.screenshot(
#                     path=str(failure),
#                     full_page=True,
#                 )

#                 log(f"Failure screenshot: " f"{failure}")

#             except Exception:
#                 pass

#         finally:

#             context.close()
#             browser.close()

#     log("======================================")

#     log("DISCOVERY FINISHED")

#     log("======================================")


# # ============================================================
# # ENTRY
# # ============================================================

# if __name__ == "__main__":
#     main()


# =========================================
import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

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

DISCOVERY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SCREENSHOT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

# ============================================================
# TIMING
# ============================================================

WAIT_SHORT = 500
WAIT_MEDIUM = 1000
WAIT_LONG = 1500

# ============================================================
# NOTIFICATION / SYSTEM UI
# ============================================================

NOTIFICATION_KEYWORDS = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
    "bell",
}

SYSTEM_UI_KEYWORDS = {
    "help",
    "filter",
    "filters",
    "search",
    "settings",
    "list view",
    "kanban",
    "calendar",
    "dashboard",
    "load more",
    "no new notifications",
    "notification",
    "notifications",
    "notification icon",
    "bell",
}

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


def clean_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def normalize_text(value):
    return clean_text(value).lower()


def slugify(value):
    value = normalize_text(value)

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    value = value.strip("-")

    return value or "unknown"


# ============================================================
# NOTIFICATION DETECTION
# ============================================================


def is_notification_element(
    text="",
    aria_label="",
    title="",
    value="",
    class_name="",
    id_value="",
):
    """
    Detect ERPNext notification / bell related UI.

    Important:
    These elements must NEVER become business actions.
    """

    values = [
        normalize_text(text),
        normalize_text(aria_label),
        normalize_text(title),
        normalize_text(value),
        normalize_text(class_name),
        normalize_text(id_value),
    ]

    for value_item in values:

        if not value_item:
            continue

        # Exact match
        if value_item in NOTIFICATION_KEYWORDS:
            return True

        # Notification text
        if "notification" in value_item:
            return True

        # Bell
        if value_item == "bell":
            return True

        # Notification + number
        if re.search(
            r"\bnotifications?\b.*\d+",
            value_item,
        ):
            return True

        # Number + notification
        if re.search(
            r"\d+.*\bnotifications?\b",
            value_item,
        ):
            return True

        # Notification related class/id
        if (
            "notification" in value_item
            or "navbar-notifications" in value_item
            or "notifications-icon" in value_item
        ):
            return True

    return False


def is_system_ui(
    text="",
    aria_label="",
    title="",
):
    """
    Detect generic system/browser/UI elements
    which should not become business test actions.
    """

    values = [
        normalize_text(text),
        normalize_text(aria_label),
        normalize_text(title),
    ]

    for value_item in values:

        if not value_item:
            continue

        if value_item in SYSTEM_UI_KEYWORDS:
            return True

        if is_notification_element(
            text=value_item,
        ):
            return True

    return False


# ============================================================
# JSON HELPERS
# ============================================================


def load_json(path):

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )

    except Exception as exc:

        log(f"SKIP INVALID JSON: " f"{path.name} -> {exc}")

        return None


# ============================================================
# DISCOVERY FILE MANAGEMENT
# ============================================================


def existing_discovery_doctypes():
    """
    Read existing discovery files and return
    known DocType names.
    """

    discovered = set()

    for path in DISCOVERY_DIR.glob("*.json"):

        data = load_json(path)

        if not data:
            continue

        doctype = clean_text(data.get("doctype") or data.get("document_name") or "")

        if doctype:
            discovered.add(doctype.lower())

    return discovered


def next_serial_number():
    """
    Find next serial number.

    Example:
        0001_company-budget.json
        0002_import-lc.json

    Next:
        0003
    """

    maximum = 0

    pattern = re.compile(r"^(\d+)_")

    for path in DISCOVERY_DIR.glob("*.json"):

        match = pattern.match(path.name)

        if not match:
            continue

        try:

            number = int(match.group(1))

            maximum = max(
                maximum,
                number,
            )

        except ValueError:
            continue

    return maximum + 1


def discovery_file_for_doctype(doctype):
    """
    Find existing discovery JSON
    for a DocType.
    """

    target = normalize_text(doctype)

    target_slug = slugify(doctype)

    for path in DISCOVERY_DIR.glob("*.json"):

        # ----------------------------------------------------
        # Filename check
        # ----------------------------------------------------

        filename = path.stem

        match = re.match(
            r"^\d+_(.+)$",
            filename,
        )

        if match:

            if match.group(1).lower() == target_slug:
                return path

        # ----------------------------------------------------
        # Content check
        # ----------------------------------------------------

        data = load_json(path)

        if not data:
            continue

        stored = normalize_text(data.get("doctype") or data.get("document_name") or "")

        if stored == target:
            return path

    return None


def save_discovery(data):
    """
    Save discovery JSON using:

        0001_company-budget.json
        0002_import-lc.json
    """

    doctype = clean_text(data.get("doctype") or data.get("document_name") or "unknown")

    existing = discovery_file_for_doctype(doctype)

    if existing:

        log(f"SKIP SAVE: already exists -> " f"{existing.name}")

        return existing

    serial = next_serial_number()

    filename = f"{serial:04d}_" f"{slugify(doctype)}.json"

    path = DISCOVERY_DIR / filename

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    log(f"Discovery saved: {path}")

    return path


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
        [role="combobox"],
        [contenteditable="true"]
    """

    locator = page.locator(selectors)

    try:
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

            tag = element.evaluate("(el) => el.tagName.toLowerCase()")

            text = clean_text(element.inner_text())

            aria_label = clean_text(element.get_attribute("aria-label") or "")

            title = clean_text(element.get_attribute("title") or "")

            class_name = element.get_attribute("class") or ""

            id_value = element.get_attribute("id") or ""

            # ------------------------------------------------
            # NEVER DISCOVER NOTIFICATION UI
            # ------------------------------------------------

            if is_notification_element(
                text=text,
                aria_label=aria_label,
                title=title,
                class_name=class_name,
                id_value=id_value,
            ):
                continue

            elements.append(
                {
                    "tag": tag,
                    "text": text[:300],
                    "id": id_value,
                    "name": (element.get_attribute("name") or ""),
                    "type": (element.get_attribute("type") or ""),
                    "placeholder": (element.get_attribute("placeholder") or ""),
                    "aria_label": aria_label,
                    "title": title,
                    "role": (element.get_attribute("role") or ""),
                    "value": (element.get_attribute("value") or ""),
                    "data_fieldname": (element.get_attribute("data-fieldname") or ""),
                    "class": class_name[:500],
                    "system_ui": is_system_ui(
                        text=text,
                        aria_label=aria_label,
                        title=title,
                    ),
                }
            )

        except Exception:
            continue

    return elements


# ============================================================
# FIELD DISCOVERY
# ============================================================


def discover_form_fields(page):

    fields = []

    wrappers = page.locator("""
        .frappe-control,
        .form-group,
        [data-fieldname]
        """)

    try:
        count = min(
            wrappers.count(),
            500,
        )
    except Exception:
        count = 0

    seen = set()

    for i in range(count):

        wrapper = wrappers.nth(i)

        try:

            if not wrapper.is_visible():
                continue

            fieldname = wrapper.get_attribute("data-fieldname") or ""

            if not fieldname:

                child = wrapper.locator("[data-fieldname]")

                if child.count() > 0:

                    fieldname = child.first.get_attribute("data-fieldname") or ""

            fieldname = clean_text(fieldname)

            if not fieldname:
                continue

            if fieldname in seen:
                continue

            seen.add(fieldname)

            # ------------------------------------------------
            # LABEL
            # ------------------------------------------------

            label = ""

            try:

                label_locator = wrapper.locator(".control-label, label")

                if label_locator.count() > 0:

                    label = clean_text(label_locator.first.inner_text())

            except Exception:
                pass

            if not label:
                label = fieldname

            # ------------------------------------------------
            # REQUIRED
            # ------------------------------------------------

            required = False

            try:

                required = bool(wrapper.locator(".reqd").count())

            except Exception:
                required = False

            # ------------------------------------------------
            # CONTROL
            # ------------------------------------------------

            input_locator = wrapper.locator("""
                input,
                textarea,
                select,
                [contenteditable='true']
                """)

            value = ""

            fieldtype = "unknown"

            options = []

            placeholder = ""

            control_type = ""

            if input_locator.count() > 0:

                control = input_locator.first

                try:

                    tag = control.evaluate("(el) => el.tagName.toLowerCase()")

                except Exception:
                    tag = ""

                control_type = (control.get_attribute("type") or "").lower()

                placeholder = control.get_attribute("placeholder") or ""

                # ------------------------------------------------
                # FIELD TYPE
                # ------------------------------------------------

                if tag == "select":

                    fieldtype = "Select"

                elif control_type == "checkbox":

                    fieldtype = "Check"

                elif control_type == "date":

                    fieldtype = "Date"

                elif control_type == "datetime-local":

                    fieldtype = "Datetime"

                elif control_type == "number":

                    fieldtype = "Float"

                elif control_type == "email":

                    fieldtype = "Data"

                else:

                    wrapper_class = (wrapper.get_attribute("class") or "").lower()

                    if "link-field" in wrapper_class:

                        fieldtype = "Link"

                    elif "date-field" in wrapper_class:

                        fieldtype = "Date"

                    elif "currency" in wrapper_class:

                        fieldtype = "Currency"

                    elif "percent" in wrapper_class:

                        fieldtype = "Percent"

                    else:

                        fieldtype = "Data"

                # ------------------------------------------------
                # VALUE
                # ------------------------------------------------

                try:

                    if tag == "textarea":

                        value = control.input_value() or ""

                    elif tag == "select":

                        value = control.input_value() or ""

                    elif control_type == "checkbox":

                        value = control.is_checked()

                    else:

                        value = control.input_value() or ""

                except Exception:
                    pass

                # ------------------------------------------------
                # SELECT OPTIONS
                # ------------------------------------------------

                if tag == "select":

                    try:

                        option_locator = control.locator("option")

                        option_count = min(
                            option_locator.count(),
                            200,
                        )

                        for j in range(option_count):

                            option = option_locator.nth(j)

                            try:

                                option_text = clean_text(option.inner_text())

                                option_value = option.get_attribute("value") or ""

                                if option_text or option_value:

                                    options.append(
                                        {
                                            "text": option_text,
                                            "value": option_value,
                                        }
                                    )

                            except Exception:
                                continue

                    except Exception:
                        pass

                # ------------------------------------------------
                # LINK OPTIONS
                # ------------------------------------------------

                if fieldtype == "Link":

                    options.extend(
                        discover_link_options(
                            page,
                            wrapper,
                        )
                    )

            # ------------------------------------------------
            # ACTIONS
            # ------------------------------------------------

            actions = []

            if fieldtype in {
                "Data",
                "Float",
                "Currency",
                "Percent",
            }:

                actions.extend(
                    [
                        "fill",
                        "clear",
                    ]
                )

            elif fieldtype == "Select":

                actions.extend(
                    [
                        "select",
                    ]
                )

            elif fieldtype == "Check":

                actions.extend(
                    [
                        "check",
                        "uncheck",
                    ]
                )

            elif fieldtype == "Link":

                actions.extend(
                    [
                        "select_link",
                    ]
                )

            elif fieldtype in {
                "Date",
                "Datetime",
            }:

                actions.extend(
                    [
                        "fill",
                        "clear",
                    ]
                )

            fields.append(
                {
                    "fieldname": fieldname,
                    "label": label,
                    "fieldtype": fieldtype,
                    "value": value,
                    "required": required,
                    "placeholder": placeholder,
                    "options": options,
                    "actions": actions,
                }
            )

        except Exception:
            continue

    # ========================================================
    # FALLBACK
    # ========================================================

    if not fields:

        direct = page.locator("[data-fieldname]")

        try:
            count = min(
                direct.count(),
                500,
            )
        except Exception:
            count = 0

        for i in range(count):

            element = direct.nth(i)

            try:

                if not element.is_visible():
                    continue

                fieldname = clean_text(element.get_attribute("data-fieldname") or "")

                if not fieldname:
                    continue

                if fieldname in seen:
                    continue

                seen.add(fieldname)

                fields.append(
                    {
                        "fieldname": fieldname,
                        "label": fieldname,
                        "fieldtype": "unknown",
                        "value": "",
                        "required": False,
                        "placeholder": "",
                        "options": [],
                        "actions": [],
                    }
                )

            except Exception:
                continue

    return fields


# ============================================================
# LINK OPTIONS
# ============================================================


def discover_link_options(
    page,
    wrapper,
):
    """
    Read currently visible autocomplete
    options without typing into the field.
    """

    options = []

    try:

        candidates = page.locator("""
            .awesomplete li,
            .awesomplete ul li,
            .ac-option,
            .link-option,
            [role="option"]
            """)

        count = min(
            candidates.count(),
            100,
        )

        seen = set()

        for i in range(count):

            option = candidates.nth(i)

            try:

                if not option.is_visible():
                    continue

                text = clean_text(option.inner_text())

                if not text:
                    continue

                if is_notification_element(text=text):
                    continue

                key = text.lower()

                if key in seen:
                    continue

                seen.add(key)

                options.append(
                    {
                        "text": text,
                        "value": text,
                    }
                )

            except Exception:
                continue

    except Exception:
        pass

    return options


# ============================================================
# TABS
# ============================================================


def discover_tabs(page):

    tabs = []

    selectors = [
        "[role='tab']",
        ".form-tabs .nav-link",
        ".form-tabs a",
        ".nav-tabs .nav-link",
    ]

    seen = set()

    for selector in selectors:

        locator = page.locator(selector)

        try:
            count = min(
                locator.count(),
                100,
            )
        except Exception:
            count = 0

        for i in range(count):

            item = locator.nth(i)

            try:

                if not item.is_visible():
                    continue

                text = clean_text(item.inner_text())

                if not text:
                    continue

                if is_system_ui(text=text):
                    continue

                if text not in seen:

                    seen.add(text)

                    tabs.append(text)

            except Exception:
                continue

    return tabs


# ============================================================
# SECTIONS
# ============================================================


def discover_sections(page):

    sections = []

    selectors = [
        ".section-head",
        ".form-section .section-head",
        ".form-dashboard-section .section-head",
        ".collapse-label",
    ]

    seen = set()

    for selector in selectors:

        locator = page.locator(selector)

        try:
            count = min(
                locator.count(),
                200,
            )
        except Exception:
            count = 0

        for i in range(count):

            item = locator.nth(i)

            try:

                if not item.is_visible():
                    continue

                text = clean_text(item.inner_text())

                if not text:
                    continue

                if is_system_ui(text=text):
                    continue

                if text not in seen:

                    seen.add(text)

                    sections.append(text)

            except Exception:
                continue

    return sections


# ============================================================
# BUTTONS
# ============================================================


def discover_buttons(page):

    buttons = []

    locator = page.locator("""
        button,
        [role="button"],
        input[type="button"],
        input[type="submit"]
        """)

    seen = set()

    try:
        count = min(
            locator.count(),
            300,
        )
    except Exception:
        count = 0

    for i in range(count):

        button = locator.nth(i)

        try:

            if not button.is_visible():
                continue

            text = clean_text(button.inner_text())

            aria_label = clean_text(button.get_attribute("aria-label") or "")

            title = clean_text(button.get_attribute("title") or "")

            value = clean_text(button.get_attribute("value") or "")

            class_name = button.get_attribute("class") or ""

            id_value = button.get_attribute("id") or ""

            # =================================================
            # IMPORTANT:
            # NEVER include notification button
            # =================================================

            if is_notification_element(
                text=text,
                aria_label=aria_label,
                title=title,
                value=value,
                class_name=class_name,
                id_value=id_value,
            ):

                log(
                    "IGNORED SYSTEM UI: "
                    f"notification -> "
                    f"{text or aria_label or title}"
                )

                continue

            # Generic system controls
            if is_system_ui(
                text=text,
                aria_label=aria_label,
                title=title,
            ):
                continue

            if not text:

                text = aria_label or title or value

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)

            buttons.append(
                {
                    "text": text,
                    "aria_label": aria_label,
                    "title": title,
                    "role": (button.get_attribute("role") or "button"),
                    "action": "click",
                }
            )

        except Exception:
            continue

    return buttons


# ============================================================
# LINKS
# ============================================================


def discover_links(page):

    links = []

    locator = page.locator("a")

    seen = set()

    try:
        count = min(
            locator.count(),
            500,
        )
    except Exception:
        count = 0

    for i in range(count):

        link = locator.nth(i)

        try:

            if not link.is_visible():
                continue

            text = clean_text(link.inner_text())

            aria_label = clean_text(link.get_attribute("aria-label") or "")

            title = clean_text(link.get_attribute("title") or "")

            href = link.get_attribute("href") or ""

            class_name = link.get_attribute("class") or ""

            id_value = link.get_attribute("id") or ""

            # =================================================
            # NEVER DISCOVER NOTIFICATION LINK
            # =================================================

            if is_notification_element(
                text=text,
                aria_label=aria_label,
                title=title,
                class_name=class_name,
                id_value=id_value,
            ):
                continue

            if not text and not href:
                continue

            key = f"{text.lower()}|" f"{href.lower()}"

            if key in seen:
                continue

            seen.add(key)

            links.append(
                {
                    "text": text[:300],
                    "href": href[:500],
                    "aria_label": aria_label,
                    "title": title,
                }
            )

        except Exception:
            continue

    return links


# ============================================================
# PAGE DISCOVERY
# ============================================================


def discover_page(
    page,
    doctype="",
    read_mode="unknown",
):

    data = {
        "knowledge_type": "erpnext_doctype",
        "module": "",
        "doctype": doctype,
        "document_name": doctype,
        "read_mode": read_mode,
        "existing_documents_skipped": True,
        "url": page.url,
        "title": "",
        "text": "",
        "fields": [],
        "tabs": [],
        "sections": [],
        "buttons": [],
        "links": [],
        "elements": [],
        "system_ui_rules": {
            "notification_detected": True,
            "notification_click_allowed": False,
            "notification_keywords": sorted(NOTIFICATION_KEYWORDS),
        },
    }

    try:
        data["title"] = page.title()

    except Exception:
        pass

    try:

        data["text"] = clean_text(page.locator("body").inner_text(timeout=10000))[
            :30000
        ]

    except Exception:
        pass

    data["fields"] = discover_form_fields(page)

    data["tabs"] = discover_tabs(page)

    data["sections"] = discover_sections(page)

    data["buttons"] = discover_buttons(page)

    data["links"] = discover_links(page)

    data["elements"] = discover_elements(page)

    return data


# ============================================================
# FIND VISIBLE LOCATOR
# ============================================================


def find_visible_locator(
    page,
    selectors,
):

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
                    return item

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

        return True

    # --------------------------------------------------------
    # USERNAME
    # --------------------------------------------------------

    username = find_visible_locator(
        page,
        [
            "input[name='usr']",
            "input[autocomplete='username']",
            "input[name='login']",
            "input[type='email']",
            "input[type='text']",
        ],
    )

    if not username:

        raise RuntimeError("Visible username field not found.")

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    password = find_visible_locator(
        page,
        [
            "input[name='pwd']",
            "input[name='password']",
            "input[type='password']",
        ],
    )

    if not password:

        raise RuntimeError("Visible password field not found.")

    username.fill(USERNAME)

    page.wait_for_timeout(WAIT_SHORT)

    password.fill(PASSWORD)

    log("Credentials filled.")

    # --------------------------------------------------------
    # LOGIN BUTTON
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

            text = clean_text(
                " ".join(
                    [
                        button.inner_text() or "",
                        button.get_attribute("value") or "",
                        button.get_attribute("aria-label") or "",
                    ]
                )
            ).lower()

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

        page.wait_for_url(
            re.compile(r"/app"),
            timeout=15000,
        )

    except PlaywrightTimeoutError:

        page.wait_for_timeout(WAIT_LONG)

    log(f"Login URL: {page.url}")

    if "/app" not in page.url:

        raise RuntimeError("Login failed.")

    log("LOGIN SUCCESS")

    return True


# ============================================================
# HOME
# ============================================================


def open_home(page):

    log("Opening Home / Desk...")

    page.goto(
        f"{ERP_URL}/app/home",
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(WAIT_LONG)

    log(f"Home URL: {page.url}")


# ============================================================
# MODULE NAVIGATION
# ============================================================


def find_module(
    page,
    module_name,
):

    target = normalize_text(module_name)

    log(f"Finding module: {module_name}")

    # --------------------------------------------------------
    # EXACT TEXT
    # --------------------------------------------------------

    candidates = page.get_by_text(
        module_name,
        exact=True,
    )

    try:
        count = candidates.count()
    except Exception:
        count = 0

    for i in range(count):

        item = candidates.nth(i)

        try:

            if item.is_visible():

                return item

        except Exception:
            continue

    # --------------------------------------------------------
    # CLICKABLE
    # --------------------------------------------------------

    candidates = page.locator("""
        a,
        button,
        [role="button"],
        .module-link,
        .desk-sidebar-item
        """)

    try:
        count = min(
            candidates.count(),
            500,
        )
    except Exception:
        count = 0

    for i in range(count):

        item = candidates.nth(i)

        try:

            if not item.is_visible():
                continue

            text = normalize_text(item.inner_text())

            if text == target:
                return item

        except Exception:
            continue

    return None


def open_module(
    page,
    module_name,
):

    item = find_module(
        page,
        module_name,
    )

    if not item:

        raise RuntimeError(f"Module not found: " f"{module_name}")

    log(f"Opening module: {module_name}")

    item.click()

    page.wait_for_timeout(WAIT_LONG)

    log(f"Module URL: {page.url}")


# ============================================================
# DOCTYPE DETECTION
# ============================================================


def is_probable_record_name(text):

    text = clean_text(text)

    if not text:
        return False

    patterns = [
        r"^[A-Z]{2,}[-_]\d{3,}",
        r"^[A-Z0-9]+-\d{4,}$",
        r"^\d+$",
    ]

    return any(
        re.match(
            pattern,
            text,
        )
        for pattern in patterns
    )


def clean_doctype_candidate(text):

    text = clean_text(text)

    if not text:
        return ""

    if is_probable_record_name(text):
        return ""

    if is_system_ui(text=text):
        return ""

    if text.lower() in {
        "home",
        "import",
        "accounting",
        "inventory",
        "assets",
        "production",
        "quality",
        "planning",
        "support",
        "crm",
        "settings",
        "add",
    }:
        return ""

    if len(text) > 100:
        return ""

    return text


# ============================================================
# MODULE DOC DISCOVERY
# ============================================================


def discover_module_docs(page):

    docs = []

    seen = set()

    def add_candidate(
        text,
        href="",
    ):

        text = clean_doctype_candidate(text)

        if not text:
            return

        key = text.lower()

        if key in seen:
            return

        seen.add(key)

        docs.append(
            {
                "doctype": text,
                "href": href,
            }
        )

    # --------------------------------------------------------
    # VISIBLE LINKS
    # --------------------------------------------------------

    links = page.locator("a")

    try:
        count = min(
            links.count(),
            1000,
        )
    except Exception:
        count = 0

    for i in range(count):

        link = links.nth(i)

        try:

            if not link.is_visible():
                continue

            text = clean_text(link.inner_text())

            href = link.get_attribute("href") or ""

            if href.startswith("/app/") or "/app/" in href:

                add_candidate(
                    text,
                    href,
                )

        except Exception:
            continue

    # --------------------------------------------------------
    # BUTTONS / CARDS
    # --------------------------------------------------------

    clickable = page.locator("""
        button,
        [role="button"],
        .module-card,
        .desk-card,
        .link-card,
        .widget
        """)

    try:
        count = min(
            clickable.count(),
            1000,
        )
    except Exception:
        count = 0

    for i in range(count):

        item = clickable.nth(i)

        try:

            if not item.is_visible():
                continue

            text = clean_text(item.inner_text())

            if is_notification_element(
                text=text,
                aria_label=(item.get_attribute("aria-label") or ""),
                title=(item.get_attribute("title") or ""),
            ):
                continue

            href = item.get_attribute("href") or ""

            add_candidate(
                text,
                href,
            )

        except Exception:
            continue

    # --------------------------------------------------------
    # ADD DOCTYPE BUTTONS
    # --------------------------------------------------------

    buttons = page.locator("""
        button,
        [role="button"],
        a
        """)

    try:
        count = min(
            buttons.count(),
            1000,
        )
    except Exception:
        count = 0

    # Correct regex
    add_pattern = re.compile(
        r"^\+?\s*add\s+(.+)$",
        re.I,
    )

    for i in range(count):

        item = buttons.nth(i)

        try:

            if not item.is_visible():
                continue

            text = clean_text(item.inner_text())

            if is_notification_element(
                text=text,
                aria_label=(item.get_attribute("aria-label") or ""),
                title=(item.get_attribute("title") or ""),
            ):
                continue

            match = add_pattern.match(text)

            if match:

                candidate = clean_doctype_candidate(match.group(1))

                if candidate:

                    add_candidate(
                        candidate,
                        "",
                    )

        except Exception:
            continue

    return docs


# ============================================================
# FIND DOCTYPE ROUTE
# ============================================================


def find_doctype_route(
    page,
    doctype,
):

    target = normalize_text(doctype)

    links = page.locator("a")

    try:
        count = min(
            links.count(),
            1000,
        )
    except Exception:
        count = 0

    for i in range(count):

        link = links.nth(i)

        try:

            if not link.is_visible():
                continue

            text = normalize_text(link.inner_text())

            href = link.get_attribute("href") or ""

            if is_notification_element(
                text=text,
                aria_label=(link.get_attribute("aria-label") or ""),
                title=(link.get_attribute("title") or ""),
            ):
                continue

            if text == target or target in text:

                if href:

                    return urljoin(
                        ERP_URL + "/",
                        href,
                    )

        except Exception:
            continue

    return None


def guess_doctype_route(doctype):

    return f"{ERP_URL}/app/" f"{slugify(doctype)}"


# ============================================================
# OPEN DOCTYPE LIST
# ============================================================


def open_doctype_list(
    page,
    doctype,
):

    log(f"Opening DocType list: " f"{doctype}")

    route = find_doctype_route(
        page,
        doctype,
    )

    if not route:

        route = guess_doctype_route(doctype)

    log(f"DocType route: {route}")

    page.goto(
        route,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(WAIT_LONG)

    return page.url


# ============================================================
# FIND ADD BUTTON
# ============================================================


def find_add_button(
    page,
    doctype,
):

    target = normalize_text(doctype)

    expected = {
        f"add {target}",
        f"+ add {target}",
        f"new {target}",
    }

    candidates = page.locator("""
        button,
        a,
        [role="button"]
        """)

    try:
        count = min(
            candidates.count(),
            1000,
        )
    except Exception:
        count = 0

    # --------------------------------------------------------
    # Exact
    # --------------------------------------------------------

    for i in range(count):

        item = candidates.nth(i)

        try:

            if not item.is_visible():
                continue

            text = clean_text(
                " ".join(
                    [
                        item.inner_text() or "",
                        item.get_attribute("aria-label") or "",
                        item.get_attribute("title") or "",
                    ]
                )
            ).lower()

            if is_notification_element(text=text):
                continue

            if text in expected:
                return item

        except Exception:
            continue

    # --------------------------------------------------------
    # Contains
    # --------------------------------------------------------

    for i in range(count):

        item = candidates.nth(i)

        try:

            if not item.is_visible():
                continue

            text = normalize_text(item.inner_text())

            if is_notification_element(text=text):
                continue

            if "add" in text and target in text:
                return item

        except Exception:
            continue

    # --------------------------------------------------------
    # Generic add
    # --------------------------------------------------------

    generic_selectors = [
        "button:has-text('Add')",
        "button:has-text('New')",
        "a:has-text('Add')",
        "[role='button']:has-text('Add')",
    ]

    for selector in generic_selectors:

        locator = page.locator(selector)

        try:
            count = locator.count()
        except Exception:
            count = 0

        for i in range(count):

            item = locator.nth(i)

            try:

                if not item.is_visible():
                    continue

                text = clean_text(item.inner_text())

                if is_notification_element(text=text):
                    continue

                return item

            except Exception:
                continue

    return None


# ============================================================
# CLICK ADD NEW DOCUMENT
# ============================================================


def click_add_new_document(
    page,
    doctype,
):

    log(f"Looking for + Add {doctype}")

    add_button = find_add_button(
        page,
        doctype,
    )

    if not add_button:

        raise RuntimeError(f"+ Add {doctype} " f"button not found.")

    log(f"Clicking + Add {doctype}")

    before_url = page.url

    add_button.click()

    try:

        page.wait_for_url(
            re.compile(r"/app/"),
            timeout=10000,
        )

    except PlaywrightTimeoutError:
        pass

    page.wait_for_timeout(WAIT_LONG)

    after_url = page.url

    log(f"New document URL: " f"{after_url}")

    if after_url == before_url:

        page.wait_for_timeout(WAIT_LONG)

    return page.url


# ============================================================
# VERIFY NEW DOCUMENT
# ============================================================


def verify_new_document(
    page,
    doctype,
):

    url = page.url.lower()

    has_new = "new-" in url or "/new/" in url

    try:

        body_text = clean_text(page.locator("body").inner_text(timeout=5000)).lower()

    except Exception:

        body_text = ""

    title = normalize_text(doctype)

    indicators = [
        f"new {title}",
        f"new-{slugify(doctype)}",
        "save",
        "submit",
    ]

    text_indicator = any(item in body_text for item in indicators)

    if has_new or text_indicator:

        log(f"New document confirmed: " f"{doctype}")

        return True

    # --------------------------------------------------------
    # Form fields
    # --------------------------------------------------------

    fields = page.locator("[data-fieldname]")

    try:

        if fields.count() > 0:

            log(f"Form detected for: " f"{doctype}")

            return True

    except Exception:
        pass

    return False


# ============================================================
# DISCOVER ONE DOCTYPE
# ============================================================


def discover_doctype(
    page,
    doctype,
    module_name="",
):

    doctype = clean_text(doctype)

    if not doctype:
        return None

    # --------------------------------------------------------
    # Existing JSON validation
    # --------------------------------------------------------

    existing = discovery_file_for_doctype(doctype)

    if existing:

        log(f"SKIP: {doctype} " f"already discovered -> " f"{existing.name}")

        return existing

    log("--------------------------------------")

    log(f"DISCOVERING DOCTYPE: " f"{doctype}")

    log("--------------------------------------")

    # --------------------------------------------------------
    # Open list
    # --------------------------------------------------------

    open_doctype_list(
        page,
        doctype,
    )

    # --------------------------------------------------------
    # Screenshot list
    # --------------------------------------------------------

    list_screenshot = SCREENSHOT_DIR / f"{slugify(doctype)}_list.png"

    try:

        page.screenshot(
            path=str(list_screenshot),
            full_page=True,
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # Add new
    # --------------------------------------------------------

    click_add_new_document(
        page,
        doctype,
    )

    # --------------------------------------------------------
    # Verify
    # --------------------------------------------------------

    if not verify_new_document(
        page,
        doctype,
    ):

        raise RuntimeError(f"Could not confirm " f"new document for " f"{doctype}")

    # --------------------------------------------------------
    # Read form
    # --------------------------------------------------------

    page.wait_for_timeout(WAIT_MEDIUM)

    log(f"Reading all fields: " f"{doctype}")

    data = discover_page(
        page,
        doctype=doctype,
        read_mode="blank_new_document",
    )

    data["module"] = module_name

    # --------------------------------------------------------
    # Save screenshot
    # --------------------------------------------------------

    screenshot = SCREENSHOT_DIR / f"{slugify(doctype)}_new.png"

    try:

        page.screenshot(
            path=str(screenshot),
            full_page=True,
        )

        log(f"Screenshot saved: " f"{screenshot}")

    except Exception:
        pass

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    saved = save_discovery(data)

    log(f"Fields discovered: " f"{len(data['fields'])}")

    log(f"Tabs discovered: " f"{len(data['tabs'])}")

    log(f"Sections discovered: " f"{len(data['sections'])}")

    log(f"Buttons discovered: " f"{len(data['buttons'])}")

    log(f"Elements discovered: " f"{len(data['elements'])}")

    log(f"COMPLETED: {doctype}")

    return saved


# ============================================================
# MODULE DISCOVERY
# ============================================================


def discover_module(
    page,
    module_name,
):

    log("======================================")

    log(f"FULL MODULE DISCOVERY: " f"{module_name}")

    log("======================================")

    # --------------------------------------------------------
    # Open module
    # --------------------------------------------------------

    open_home(page)

    open_module(
        page,
        module_name,
    )

    page.wait_for_timeout(WAIT_MEDIUM)

    # --------------------------------------------------------
    # Screenshot
    # --------------------------------------------------------

    module_screenshot = SCREENSHOT_DIR / f"module_{slugify(module_name)}.png"

    try:

        page.screenshot(
            path=str(module_screenshot),
            full_page=True,
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # Discover DocTypes
    # --------------------------------------------------------

    docs = discover_module_docs(page)

    log(f"Visible document candidates: " f"{len(docs)}")

    for index, item in enumerate(
        docs,
        start=1,
    ):

        log(f"{index}. " f"{item['doctype']}")

    if not docs:

        log("No visible DocTypes detected.")

        return

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    success = 0
    skipped = 0
    failed = 0

    for index, item in enumerate(
        docs,
        start=1,
    ):

        doctype = item["doctype"]

        log("======================================")

        log(f"MODULE DOC " f"{index}/{len(docs)}: " f"{doctype}")

        log("======================================")

        existing = discovery_file_for_doctype(doctype)

        if existing:

            log(f"SKIP EXISTING: " f"{doctype} -> " f"{existing.name}")

            skipped += 1

            continue

        try:

            discover_doctype(
                page,
                doctype,
                module_name=module_name,
            )

            success += 1

        except Exception as exc:

            failed += 1

            log(f"FAILED: {doctype}")

            log(f"Reason: {exc}")

            # ------------------------------------------------
            # Failure screenshot
            # ------------------------------------------------

            try:

                path = SCREENSHOT_DIR / f"failure_{slugify(doctype)}.png"

                page.screenshot(
                    path=str(path),
                    full_page=True,
                )

            except Exception:
                pass

            # ------------------------------------------------
            # Recovery
            # ------------------------------------------------

            try:

                open_home(page)

                open_module(
                    page,
                    module_name,
                )

                page.wait_for_timeout(WAIT_MEDIUM)

            except Exception as recovery_error:

                log(f"Recovery failed: " f"{recovery_error}")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    log("======================================")

    log(f"MODULE DISCOVERY FINISHED: " f"{module_name}")

    log(f"SUCCESS: {success}")

    log(f"SKIPPED: {skipped}")

    log(f"FAILED: {failed}")

    log("Agent will now STOP.")

    log("======================================")


# ============================================================
# SINGLE DOCTYPE DISCOVERY
# ============================================================


def discover_single_doctype(
    page,
    doctype,
):

    log("======================================")

    log(f"SINGLE DOCTYPE DISCOVERY: " f"{doctype}")

    log("======================================")

    existing = discovery_file_for_doctype(doctype)

    if existing:

        log(f"ALREADY EXISTS: " f"{existing}")

        log("Nothing to do.")

        return

    discover_doctype(
        page,
        doctype,
        module_name="",
    )

    log("======================================")

    log(f"DOC TYPE DISCOVERY FINISHED: " f"{doctype}")

    log("Agent will now STOP.")

    log("======================================")


# ============================================================
# ARGUMENTS
# ============================================================


def parse_args():

    parser = argparse.ArgumentParser(
        description=("ERPNext Knowledge " "Discovery Agent")
    )

    parser.add_argument(
        "--module",
        required=False,
        help=("Discover all visible " "DocTypes inside module."),
    )

    parser.add_argument(
        "--doctype",
        required=False,
        help=("Discover only this DocType."),
    )

    args = parser.parse_args()

    if not args.module and not args.doctype:

        parser.error("Give either " "--module or " "--doctype.")

    if args.module and args.doctype:

        log("Both --module and " "--doctype supplied.")

        log("Priority: specific " "--doctype.")

        args.module = None

    return args


# ============================================================
# MAIN
# ============================================================


def main():

    args = parse_args()

    log("======================================")

    log("ERPNext KNOWLEDGE " "DISCOVERY AGENT")

    log("======================================")

    log(f"ERP: {ERP_URL}")

    if args.module:

        log("MODE: MODULE")

        log(f"MODULE: {args.module}")

    else:

        log("MODE: SINGLE DOCTYPE")

        log(f"DOCTYPE: {args.doctype}")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS,
            slow_mo=30,
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

            log(f"Opening ERP: {ERP_URL}")

            page.goto(
                ERP_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            log(f"Current URL: {page.url}")

            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            login(page)

            # ------------------------------------------------
            # HOME
            # ------------------------------------------------

            open_home(page)

            # ------------------------------------------------
            # MODE
            # ------------------------------------------------

            if args.doctype:

                discover_single_doctype(
                    page,
                    args.doctype,
                )

            elif args.module:

                discover_module(
                    page,
                    args.module,
                )

        except Exception as exc:

            log(f"FATAL ERROR: {exc}")

            try:

                failure = SCREENSHOT_DIR / "discovery_failure.png"

                page.screenshot(
                    path=str(failure),
                    full_page=True,
                )

                log(f"Failure screenshot: " f"{failure}")

            except Exception:
                pass

        finally:

            context.close()

            browser.close()

    log("======================================")

    log("DISCOVERY FINISHED")

    log("======================================")


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()
