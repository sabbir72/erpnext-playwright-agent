import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

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
    "new workspace",
    "create workspace",
    "add workspace",
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


def is_workspace_ui(text="", aria_label="", title=""):
    """
    Detect Workspace creation/navigation UI.

    "New Workspace" is a UI action, not the business DocType
    the discovery agent should click while discovering documents.
    """

    values = [
        normalize_text(text),
        normalize_text(aria_label),
        normalize_text(title),
    ]

    workspace_ui_patterns = {
        "new workspace",
        "create workspace",
        "add workspace",
    }

    for value in values:
        if value in workspace_ui_patterns:
            return True

        if re.search(r"\bnew\s+workspace\b", value):
            return True

        if re.search(r"\b(create|add)\s+workspace\b", value):
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

        if is_workspace_ui(text=value_item):
            return True

        if is_notification_element(
            text=value_item,
        ):
            return True

    return False


# ============================================================
# DOCTYPE NAME CLEANING
# ============================================================


def clean_doctype_name(name: str) -> str:
    """
    Keep ``New`` as a UI action, never as part of the DocType name.

    Examples:
        New Contract -> Contract
        New Product  -> Product
        Contract     -> Contract
    """
    name = clean_text(name)
    if name.lower().startswith("new "):
        return clean_text(name[4:])
    return name


def build_doctype_search_name(doctype: str) -> str:
    """Return the Global Search term: ``New <main DocType>``."""
    main_name = clean_doctype_name(doctype)
    return f"New {main_name}" if main_name else ""


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
    Persist the observed ERPNext DocType as the AI knowledge source.

    IMPORTANT:
        Discovery JSON is the actual output of this agent. It must be written
        even when the form contains zero fields, because a zero-field result is
        still useful evidence that the page was reached and inspected.

        Existing valid discovery files are not overwritten.
    """
    doctype = clean_doctype_name(
        data.get("doctype") or data.get("document_name") or "unknown"
    )

    existing = discovery_file_for_doctype(doctype)
    if existing:
        log(f"SKIP SAVE: already exists -> {existing.name}")
        return existing

    serial = next_serial_number()
    filename = f"{serial:04d}_{slugify(doctype)}.json"
    path = DISCOVERY_DIR / filename

    # Add a deterministic summary so the future AI/RAG layer can retrieve
    # document structure without first counting every array in the JSON.
    data.setdefault("discovery_summary", {})
    data["discovery_summary"].update({
        "doctype": doctype,
        "field_count": len(data.get("fields", [])),
        "tab_count": len(data.get("tabs", [])),
        "section_count": len(data.get("sections", [])),
        "button_count": len(data.get("buttons", [])),
        "link_count": len(data.get("links", [])),
        "element_count": len(data.get("elements", [])),
        "discovery_status": "completed",
    })

    # Write atomically so a partial JSON can never become the knowledge base
    # source if the process is interrupted during serialization.
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp_path.replace(path)

    log(f"Discovery saved: {path}")
    log(
        "DISCOVERY RECORD: "
        f"{doctype} | fields={len(data.get('fields', []))} | "
        f"tabs={len(data.get('tabs', []))} | "
        f"sections={len(data.get('sections', []))}"
    )
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
                    # Selector hints are stored as knowledge, not executed.
                    # The future test planner can use these to build Playwright actions.
                    "locator_hints": {
                        "fieldname": f"[data-fieldname=\"{fieldname}\"]",
                        "name": fieldname,
                        "label": label,
                    },
                    "testability": {
                        "can_fill": "fill" in actions,
                        "can_select": "select" in actions or "select_link" in actions,
                        "can_check": "check" in actions,
                        "can_clear": "clear" in actions,
                    },
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


def _safe_attr(element, name):
    try:
        return clean_text(element.get_attribute(name) or "")
    except Exception:
        return ""


def _field_snapshot_key(field):
    return (
        normalize_text(field.get("fieldname", "")),
        normalize_text(field.get("tab", "")),
    )


def _merge_fields(existing, incoming):
    """Merge field discoveries without losing tab/section context."""
    merged = list(existing)
    index = {_field_snapshot_key(item): i for i, item in enumerate(merged)}

    for field in incoming:
        key = _field_snapshot_key(field)
        if key not in index:
            index[key] = len(merged)
            merged.append(field)
            continue

        current = merged[index[key]]
        # Prefer the richer observation while preserving the first stable data.
        for k, value in field.items():
            if value not in ("", None, [], {}) and current.get(k) in ("", None, [], {}):
                current[k] = value

    return merged



def scroll_form_and_collect(page, active_tab=""):
    """
    Read the current blank ERPNext form from top to bottom.

    Long forms can render controls only after scrolling. This helper reads
    every viewport position, merges unique fields by fieldname, and returns
    the combined snapshot. It never fills or saves business data.
    """
    collected = {
        "fields": [],
        "sections": [],
        "buttons": [],
        "links": [],
        "elements": [],
    }
    seen_fields=set(); seen_sections=set(); seen_buttons=set(); seen_links=set(); seen_elements=set()

    def key(item, *names):
        if not isinstance(item, dict):
            return normalize_text(item)
        for n in names:
            v=normalize_text(item.get(n))
            if v:
                return v
        return repr(item)

    def merge(snapshot):
        for f in snapshot.get("fields", []):
            k=key(f,"fieldname","label")
            if k not in seen_fields:
                seen_fields.add(k); collected["fields"].append(f)
        for x in snapshot.get("sections", []):
            k=key(x,"name","label","text","title")
            if k not in seen_sections:
                seen_sections.add(k); collected["sections"].append(x)
        for x in snapshot.get("buttons", []):
            k=key(x,"text","label","title","action")
            if k not in seen_buttons:
                seen_buttons.add(k); collected["buttons"].append(x)
        for x in snapshot.get("links", []):
            k=key(x,"text","href","title")
            if k not in seen_links:
                seen_links.add(k); collected["links"].append(x)
        for x in snapshot.get("elements", []):
            k=key(x,"tag","id","data_fieldname","name","text","aria_label")
            if k not in seen_elements:
                seen_elements.add(k); collected["elements"].append(x)

    def reset_top():
        try:
            page.evaluate("""() => { const e=document.scrollingElement||document.documentElement; e.scrollTo(0,0); }""")
        except Exception:
            pass
        page.wait_for_timeout(WAIT_SHORT)

    reset_top()
    merge(_collect_current_form_snapshot(page, active_tab=active_tab))

    # Prefer the page's main document scroller. If ERPNext has an inner
    # scrolling form, also scan that container after the document scan.
    targets=[]
    try:
        metrics=page.evaluate("""() => { const e=document.scrollingElement||document.documentElement; return {scrollHeight:e.scrollHeight, clientHeight:e.clientHeight}; }""")
        if metrics.get("scrollHeight",0) > metrics.get("clientHeight",0) + 10:
            targets.append(("document", None, metrics))
    except Exception:
        pass

    for sel in [".layout-main-section", ".form-layout", ".page-container"]:
        loc=page.locator(sel)
        try:
            n=min(loc.count(),10)
        except Exception:
            n=0
        for i in range(n):
            el=loc.nth(i)
            try:
                if not el.is_visible(): continue
                m=el.evaluate("""e => ({scrollHeight:e.scrollHeight, clientHeight:e.clientHeight})""")
                if m.get("scrollHeight",0)>m.get("clientHeight",0)+10:
                    targets.append(("element", el, m))
            except Exception:
                continue

    for kind, target, initial in targets[:3]:
        last=-1; stable=0
        for _ in range(100):
            try:
                if kind=="document":
                    m=page.evaluate("""() => { const e=document.scrollingElement||document.documentElement; return {top:e.scrollTop, height:e.scrollHeight, viewport:e.clientHeight}; }""")
                else:
                    m=target.evaluate("""e => ({top:e.scrollTop, height:e.scrollHeight, viewport:e.clientHeight})""")
                top=m.get("top",0); maximum=max(0,m.get("height",0)-m.get("viewport",0))
                if top==last: stable+=1
                else: stable=0; last=top

                if kind=="document":
                    page.evaluate("""y => { const e=document.scrollingElement||document.documentElement; e.scrollTo(0,y); }""", maximum if top>=maximum-5 else min(maximum,top+max(300,int(m.get("viewport",700)*0.75))))
                else:
                    next_top=maximum if top>=maximum-5 else min(maximum,top+max(300,int(m.get("viewport",700)*0.75)))
                    target.evaluate("""(e,y)=>e.scrollTo(0,y)""", next_top)
                page.wait_for_timeout(WAIT_SHORT)
                merge(_collect_current_form_snapshot(page, active_tab=active_tab))

                if top>=maximum-5 and stable>=1:
                    break
            except Exception as exc:
                log(f"FORM SCROLL READ WARNING: {exc}")
                break

        try:
            if kind=="document":
                page.evaluate("""() => { const e=document.scrollingElement||document.documentElement; e.scrollTo(0,0); }""")
            else:
                target.evaluate("e=>e.scrollTo(0,0)")
            page.wait_for_timeout(WAIT_SHORT)
        except Exception:
            pass

    return collected


def _collect_current_form_snapshot(page, active_tab=""):
    """
    Read one currently visible form state.

    This is deliberately separated from navigation so the future AI layer can
    distinguish "what was observed" from "how we moved to it".
    """
    fields = discover_form_fields(page)
    for field in fields:
        field["tab"] = active_tab

    return {
        "fields": fields,
        "sections": discover_sections(page),
        "buttons": discover_buttons(page),
        "links": discover_links(page),
        "elements": discover_elements(page),
    }


def discover_all_form_tabs(page):
    """
    Inspect every visible ERPNext form tab one-by-one.

    A single blank document can contain fields hidden behind tabs. Reading only
    the initially active tab would create incomplete AI knowledge. Therefore we
    click only genuine form-tab controls, collect the current tab's fields and
    sections, then continue to the next tab.

    We never click generic buttons, Notification/Bell, Search, Filter,
    Workspace or business records here.
    """
    tab_selectors = [
        "[role='tab']",
        ".form-tabs .nav-link",
        ".form-tabs a",
        ".nav-tabs .nav-link",
    ]

    tabs = []
    seen = set()

    for selector in tab_selectors:
        locator = page.locator(selector)
        try:
            count = min(locator.count(), 100)
        except Exception:
            count = 0

        for i in range(count):
            item = locator.nth(i)
            try:
                if not item.is_visible():
                    continue
                text = clean_text(item.inner_text())
                if not text or is_system_ui(text=text):
                    continue
                key = normalize_text(text)
                if key in seen:
                    continue
                seen.add(key)
                tabs.append({"label": text, "index": len(tabs)})
            except Exception:
                continue
        if tabs:
            break

    # No tabs means the form itself is the only view.
    if not tabs:
        snapshot = scroll_form_and_collect(page, active_tab="")
        return [], snapshot

    all_fields = []
    all_sections = []
    all_buttons = []
    all_links = []
    all_elements = []
    tab_observations = []

    for tab_index, tab_info in enumerate(tabs):
        label = tab_info["label"]

        # Re-query on every iteration because clicking a tab can re-render DOM.
        current = None
        for selector in tab_selectors:
            locator = page.locator(selector)
            try:
                count = min(locator.count(), 100)
            except Exception:
                count = 0
            for i in range(count):
                item = locator.nth(i)
                try:
                    if item.is_visible() and normalize_text(item.inner_text()) == normalize_text(label):
                        current = item
                        break
                except Exception:
                    continue
            if current:
                break

        if current and tab_index > 0:
            try:
                current.click()
                page.wait_for_timeout(WAIT_SHORT)
            except Exception as exc:
                log(f"TAB CLICK SKIPPED: {label} -> {exc}")

        snapshot = scroll_form_and_collect(page, active_tab=label)
        all_fields = _merge_fields(all_fields, snapshot["fields"])

        for collection_name, target in (
            ("sections", all_sections),
            ("buttons", all_buttons),
            ("links", all_links),
            ("elements", all_elements),
        ):
            for value in snapshot[collection_name]:
                if value not in target:
                    target.append(value)

        tab_observations.append({
            "label": label,
            "index": tab_index,
            "read": bool(snapshot["fields"] or snapshot["sections"]),
            "field_count": len(snapshot["fields"]),
        })

    return tab_observations, {
        "fields": all_fields,
        "sections": all_sections,
        "buttons": all_buttons,
        "links": all_links,
        "elements": all_elements,
    }


def discover_page(
    page,
    doctype="",
    read_mode="unknown",
):
    """
    Build the AI-oriented knowledge record for a blank ERPNext document.

    Important design rule:
        discovery_agent.py observes and records; it does not create business
        data. Existing records are never opened and no field is filled.
    """
    data = {
        "knowledge_type": "erpnext_doctype",
        "schema_version": "2.1",
        "module": "",
        "doctype": clean_doctype_name(doctype),
        "document_name": clean_doctype_name(doctype),
        "search_name": build_doctype_search_name(doctype),
        "action": "New",
        "read_mode": read_mode,
        "existing_documents_skipped": True,
        "url": page.url,
        "route": urlparse(page.url).path if page.url else "",
        "title": "",
        "text": "",
        "fields": [],
        "tabs": [],
        "tab_observations": [],
        "sections": [],
        "buttons": [],
        "links": [],
        "elements": [],
        "navigation": {
            "source": "blank_new_document",
            "record_access_allowed": False,
            "business_data_mutation": False,
        },
        "system_ui_rules": {
            "notification_detected": True,
            "notification_click_allowed": False,
            "notification_keywords": sorted(NOTIFICATION_KEYWORDS),
            "workspace_click_allowed": False,
            "generic_system_actions_allowed": False,
        },
    }

    try:
        data["title"] = page.title()
    except Exception:
        pass

    try:
        data["text"] = clean_text(page.locator("body").inner_text(timeout=10000))[:50000]
    except Exception:
        pass

    tab_observations, snapshot = discover_all_form_tabs(page)
    data["tab_observations"] = tab_observations
    data["tabs"] = [item["label"] for item in tab_observations]
    data["fields"] = snapshot["fields"]
    data["sections"] = snapshot["sections"]
    data["buttons"] = snapshot["buttons"]
    data["links"] = snapshot["links"]
    data["elements"] = snapshot["elements"]

    # Knowledge classification for the future AI QA planner. This does not
    # execute tests; it records what can potentially be tested later.
    data["qa_knowledge"] = {
        "form_read": True,
        "business_data_created": False,
        "business_data_saved": False,
        "existing_record_opened": False,
        "field_actions": sorted({
            action
            for field in data["fields"]
            for action in field.get("actions", [])
        }),
        "business_buttons": [
            button.get("text", "")
            for button in data["buttons"]
            if button.get("text")
        ],
        "validation_candidates": [
            {
                "fieldname": field.get("fieldname", ""),
                "required": bool(field.get("required")),
                "fieldtype": field.get("fieldtype", "unknown"),
            }
            for field in data["fields"]
        ],
    }

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


def strip_workspace_counter(text):
    """
    ERPNext workspace cards commonly display a DocType with a record
    counter, for example:
        Purchase Order 118
        LC Application 64
        Contract. 46

    The counter is UI information, not part of the DocType name.
    """
    text = clean_text(text)

    if not text:
        return ""

    # Only strip a trailing numeric counter when there is a clear
    # separator/space before it. This avoids changing names such as
    # "Level 2" unnecessarily when they are not workspace counters.
    text = re.sub(r"\s+[\-–—.]?\s*\d+$", "", text).strip()

    return text.rstrip(". ")


def clean_doctype_candidate(text):

    text = clean_text(text)

    if not text:
        return ""

    # Remove workspace record counters such as "46" from
    # "Contract. 46" / "Purchase Order 118".
    text = strip_workspace_counter(text)

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
# ACTUAL ERPNext DOCTYPE VALIDATION
# ============================================================


def is_doctype_list_route(href):
    """
    A business DocType list route is normally:
        /app/<doctype-slug>

    We reject:
        /app/<doctype>/<record>
        /app/workspace
        /app/search
        /app/settings
        /app/home
    """
    if not href:
        return False

    try:
        route = urljoin(ERP_URL + "/", href)
        parsed = urlparse(route)
        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) != 2 or parts[0].lower() != "app":
            return False

        slug = normalize_text(parts[1])

        blocked = {
            "home",
            "search",
            "settings",
            "workspace",
            "notifications",
            "notification",
            "list",
            "kanban",
            "calendar",
        }

        if slug in blocked:
            return False

        return True
    except Exception:
        return False


def validate_doctype_list_page(page, doctype):
    """
    Validate an opened ERPNext list page by its visible UI.

    IMPORTANT:
    We do NOT call the Frappe metadata endpoint here because the
    deployed site previously returned HTTP 404 for that endpoint.

    A candidate is accepted only when the opened page looks like the
    requested DocType list page. We look for the DocType title and/or
    a target-specific New/Add action.

    This function never clicks Notification, Bell, Workspace, Search,
    Filter, or any other system UI.
    """
    target = normalize_text(doctype)

    if not target:
        return False

    if is_system_ui(text=doctype) or is_notification_element(text=doctype):
        return False

    try:
        body = clean_text(
            page.locator("body").inner_text(timeout=5000)
        )
    except Exception:
        body = ""

    body_normalized = normalize_text(body)

    # UI can show "Purchase Order" in title/body.
    title_match = target in body_normalized

    # Look for a real target-specific New/Add action.
    new_match = False
    buttons = page.locator("button, a, [role='button']")

    try:
        count = min(buttons.count(), 500)
    except Exception:
        count = 0

    expected = {
        f"new {target}",
        f"add {target}",
        f"+ add {target}",
    }

    for i in range(count):
        item = buttons.nth(i)

        try:
            if not item.is_visible():
                continue

            text = clean_text(
                " ".join([
                    item.inner_text() or "",
                    item.get_attribute("aria-label") or "",
                    item.get_attribute("title") or "",
                ])
            )

            if not text:
                continue

            if is_notification_element(text=text):
                continue

            if is_workspace_ui(text=text):
                continue

            if normalize_text(text) in expected:
                new_match = True
                break
        except Exception:
            continue

    # ERPNext often uses a generic "New" button on a validated list page.
    # It is safe ONLY here because the current route/page has already been
    # validated as the requested DocType; "New Workspace" is explicitly excluded.
    if not new_match and title_match:
        for i in range(count):
            item = buttons.nth(i)
            try:
                if not item.is_visible():
                    continue
                text = clean_text(" ".join([
                    item.inner_text() or "",
                    item.get_attribute("aria-label") or "",
                    item.get_attribute("title") or "",
                ]))
                if normalize_text(text) in {"new", "+ new", "add"} and not is_workspace_ui(text=text):
                    new_match = True
                    break
            except Exception:
                continue

    if title_match or new_match:
        log(f"VALID ACTUAL DOCTYPE LIST: {doctype}")
        return True

    log(f"SKIP NON-DOCTYPE PAGE: {doctype}")
    return False


def validate_actual_doctype(page, doctype, href=""):
    """
    Candidate gate used by module discovery.

    No metadata API is used.
    No generic New button is clicked.
    No notification/bell/workspace UI is clicked.

    For module candidates we only accept a clean /app/<doctype> route.
    The final confirmation happens when that route is opened and its
    list page is inspected.
    """
    doctype = clean_doctype_candidate(doctype)

    if not doctype:
        return False

    if is_system_ui(text=doctype):
        log(f"SKIP NON-DOCTYPE SYSTEM UI: {doctype}")
        return False

    if is_notification_element(text=doctype):
        log(f"SKIP NOTIFICATION UI: {doctype}")
        return False

    if is_workspace_ui(text=doctype):
        log(f"SKIP WORKSPACE UI: {doctype}")
        return False

    if is_probable_record_name(doctype):
        log(f"SKIP RECORD NAME: {doctype}")
        return False

    if href and not is_doctype_list_route(href):
        log(f"SKIP INVALID DOCTYPE ROUTE: {doctype} -> {href}")
        return False

    # A href is preferred. Without one, this candidate will be handled by
    # the safe guessed route only when the caller explicitly needs it.
    if href:
        return True

    return bool(guess_doctype_route(doctype))


# ============================================================
# MODULE DOC DISCOVERY
# ============================================================


def _extract_route_from_clickable(item):
    """Read an ERPNext navigation route from href/data attributes when present."""
    for attr in (
        "href",
        "data-route",
        "data-href",
        "data-link",
        "data-path",
    ):
        value = _safe_attr(item, attr)
        if value:
            return value

    # Some Desk cards keep navigation inside an onclick handler.
    onclick = _safe_attr(item, "onclick")
    if onclick:
        match = re.search(r"(?:/app/[a-z0-9\-_/]+)", onclick, re.I)
        if match:
            return match.group(0)

    return ""


def _module_content_scope(page):
    """
    Return the most likely right-side module content container.

    ERPNext themes differ, so this is intentionally a selector list rather
    than one hard-coded class. If no scope is found, page-level scanning is
    used as a fallback and system/sidebar links are filtered later.
    """
    selectors = [
        ".workspace-container",
        ".workspace-page",
        ".layout-main-section",
        ".page-container",
        "main",
        "[role='main']",
    ]
    for selector in selectors:
        locator = page.locator(selector)
        try:
            for i in range(min(locator.count(), 20)):
                item = locator.nth(i)
                if item.is_visible():
                    return item
        except Exception:
            continue
    return page.locator("body")


def discover_module_docs(page):
    """Discover business DocTypes visible in the opened module workspace.

    ERPNext workspace cards may expose a real /app/<slug> href, or may be
    rendered as DIV/cards with only text and a record count. We support both.
    Candidates are NOT clicked here; discover_doctype() later uses Global Search
    by exact DocType name for every document.
    """
    docs = []
    seen = set()
    scope = _module_content_scope(page)

    def add_candidate(raw_text, href="", source="module_right_side"):
        raw_text = clean_text(raw_text)
        if not raw_text:
            return

        # Work line-by-line because a card can contain title + count + extra text.
        lines = [clean_text(x) for x in raw_text.splitlines() if clean_text(x)]
        if not lines:
            lines = [raw_text]

        for line in lines:
            candidate = clean_doctype_candidate(line)
            if not candidate:
                continue

            candidate = clean_doctype_name(candidate)
            low = normalize_text(candidate)

            if is_notification_element(text=candidate) or is_workspace_ui(text=candidate):
                continue
            if low in {"commercial", "library & setup", "import", "reports", "report",
                       "search", "filter", "settings", "dashboard", "list view",
                       "kanban", "calendar", "load more", "new", "add"}:
                continue

            if href and not is_doctype_list_route(href):
                href = ""

            key = low
            if not key or key in seen:
                continue

            seen.add(key)
            docs.append({
                "doctype": candidate,
                "href": href,
                "source": source,
            })
            log(
                f"MODULE DOCTYPE FOUND: {candidate}"
                + (f" -> {href}" if href else "")
            )
            return

    # 1) Cards/links/buttons with route information.
    clickables = scope.locator(
        "a, button, [role='button'], .module-card, .desk-card, .link-card, "
        ".widget, .shortcut, .number-card, .workspace-link"
    )
    try:
        count = min(clickables.count(), 2500)
    except Exception:
        count = 0

    for i in range(count):
        item = clickables.nth(i)
        try:
            if not item.is_visible():
                continue
            text_value = clean_text(item.inner_text())
            aria = _safe_attr(item, "aria-label")
            title = _safe_attr(item, "title")
            href = _extract_route_from_clickable(item)
            add_candidate(
                text_value or aria or title,
                href=href,
                source="module_right_side_clickable",
            )
        except Exception:
            continue

    # 2) Cards without href/data-route.
    fallback_selectors = [
        ".workspace-container .shortcut",
        ".workspace-container .widget",
        ".workspace-container .number-card",
        ".workspace-container .module-card",
        ".workspace-container .link-card",
        ".workspace-page .shortcut",
        ".workspace-page .widget",
        ".workspace-page .number-card",
        ".workspace-page .module-card",
        ".workspace-page .link-card",
        ".layout-main-section .shortcut",
        ".layout-main-section .widget",
        ".layout-main-section .number-card",
        ".layout-main-section .module-card",
        ".layout-main-section .link-card",
    ]

    for selector in fallback_selectors:
        locator = scope.locator(selector)
        try:
            count = min(locator.count(), 2500)
        except Exception:
            count = 0

        for i in range(count):
            item = locator.nth(i)
            try:
                if not item.is_visible():
                    continue
                text_value = clean_text(item.inner_text())
                data_doctype = _safe_attr(item, "data-doctype")
                href = _extract_route_from_clickable(item)
                add_candidate(
                    data_doctype or text_value,
                    href=href,
                    source="module_right_side_card",
                )
            except Exception:
                continue

    # 3) Final text fallback. Workspace entries in the user's example look like
    # "Contract 46", "Purchase Order 118", etc. Their trailing count is removed
    # by clean_doctype_candidate(). This fallback is only used for lines with a
    # trailing number, reducing false positives from workspace headings.
    try:
        body = scope.inner_text()
    except Exception:
        body = ""

    for line in [clean_text(x) for x in body.splitlines() if clean_text(x)]:
        if re.search(r"\s+\d+$", line):
            add_candidate(line, source="module_right_side_text")

    log(f"Module DocType candidates collected: {len(docs)}")
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
# GLOBAL SEARCH -> DOCTYPE
# ============================================================


def find_global_search_box(page):
    """
    Find ERPNext's global search box without treating it as a
    business DocType/action. The search box is navigation only.
    """

    selectors = [
        "input[placeholder*='Search or type a command']",
        "input[placeholder*='Search or type']",
        "input[aria-label*='Search']",
        "input[data-original-title*='Search']",
        ".search-bar input",
        ".navbar-search input",
        "input[placeholder='Search']",
    ]

    return find_visible_locator(page, selectors)


def search_doctype_from_home(page, doctype):
    """
    Search ERPNext Global Search using ``New <DocType>``.

    Main DocType is always kept clean in memory and in discovery JSON.
    Example: ``Contract`` -> search ``New Contract``.
    """
    main_doctype = clean_doctype_name(doctype)
    if not main_doctype:
        return None

    if is_system_ui(text=main_doctype) or is_notification_element(text=main_doctype):
        log(f"BLOCKED SEARCH TARGET (SYSTEM UI): {main_doctype}")
        return None

    open_home(page)
    search_box = find_global_search_box(page)
    if not search_box:
        log("Global search box not found.")
        return None

    search_name = build_doctype_search_name(main_doctype)
    target_main = normalize_text(main_doctype)
    target_search = normalize_text(search_name)

    log(f"GLOBAL SEARCH: {search_name}")
    log(f"MAIN DOCTYPE: {main_doctype}")

    try:
        search_box.click()
        search_box.fill(search_name)
        page.wait_for_timeout(WAIT_MEDIUM)
    except Exception as exc:
        log(f"Global search interaction failed: {exc}")
        return None

    result_selectors = [
        ".search-result",
        ".awesomplete li",
        "[role='option']",
        ".dropdown-menu a",
        ".dropdown-menu button",
        "a[href*='/app/']",
    ]

    for selector in result_selectors:
        locator = page.locator(selector)
        try:
            count = min(locator.count(), 500)
        except Exception:
            count = 0

        for i in range(count):
            item = locator.nth(i)
            try:
                if not item.is_visible():
                    continue

                raw_text = clean_text(" ".join([
                    item.inner_text() or "",
                    item.get_attribute("aria-label") or "",
                    item.get_attribute("title") or "",
                ]))
                href = item.get_attribute("href") or ""

                if not raw_text:
                    continue
                if is_notification_element(text=raw_text):
                    continue
                if is_workspace_ui(text=raw_text):
                    continue

                # The search UI may show either "New Contract" or just
                # "Contract". Both are accepted after stripping the UI word.
                result_main = normalize_text(clean_doctype_name(raw_text))
                result_exact = normalize_text(raw_text)

                if result_main != target_main and result_exact != target_search:
                    continue

                if href and not is_doctype_list_route(href):
                    continue

                log(f"EXACT SEARCH RESULT FOUND: {search_name} -> {raw_text}")
                item.click()
                page.wait_for_timeout(WAIT_LONG)

                # Some ERPNext deployments open the blank New form directly.
                if is_blank_new_document(page, main_doctype):
                    log(f"BLANK NEW FORM OPENED DIRECTLY: {main_doctype}")
                    return page.url

                if "/app/" not in page.url and href:
                    route = urljoin(ERP_URL + "/", href)
                    if not is_doctype_list_route(route):
                        log(f"SKIP UNSAFE SEARCH ROUTE: {route}")
                        return None
                    page.goto(route, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(WAIT_LONG)

                if "/app/" in page.url and validate_doctype_list_page(page, main_doctype):
                    log(f"DOCTYPE LIST OPENED: {main_doctype} -> {page.url}")
                    return page.url

            except Exception:
                continue

    log(f"EXACT SEARCH RESULT NOT FOUND: {search_name}")
    return None


def open_doctype_list_by_route(page, doctype, href=""):
    """
    Safe route fallback.

    Only /app/<doctype> is allowed.
    No record route, workspace, search, settings or notification route
    can be opened here.
    """
    if href:
        route = urljoin(ERP_URL + "/", href)
    else:
        route = guess_doctype_route(doctype)

    if not is_doctype_list_route(route):
        raise RuntimeError(
            f"Unsafe DocType route: {doctype} -> {route}"
        )

    log(f"SAFE DOCTYPE ROUTE: {route}")

    response = page.goto(
        route,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(WAIT_LONG)

    if response is not None and response.status >= 400:
        raise RuntimeError(
            f"DocType route returned HTTP {response.status}: {route}"
        )

    if not validate_doctype_list_page(page, doctype):
        raise RuntimeError(
            f"Route is not a confirmed DocType list: {doctype}"
        )

    return page.url


# ============================================================
# OPEN DOCTYPE LIST
# ============================================================


def open_doctype_list(page, doctype, href=""):
    """
    Open the requested DocType ONLY through ERPNext Global Search.

    Required discovery flow for EVERY DocType:
        Home -> Global Search -> exact DocType name -> DocType List
        -> New <DocType> / New -> blank New Document -> read all fields.

    ``href`` is intentionally ignored here. Even when a module scanner
    finds a DocType route, the actual DocType is still searched by name
    from the global Search option so every discovery follows one consistent
    navigation path.
    """
    doctype = clean_doctype_name(doctype)
    log(f"SEARCHING DOCTYPE: {build_doctype_search_name(doctype)}")
    log(f"MAIN DOCTYPE: {doctype}")

    # IMPORTANT: do not use the module-collected href as a shortcut.
    # Every DocType must be searched from ERPNext Home by its own name.
    result = search_doctype_from_home(page, doctype)

    if not result:
        raise RuntimeError(
            f"DocType could not be opened from Global Search: {doctype}"
        )

    return result


# ============================================================
# FIND ADD BUTTON
# ============================================================


def find_add_button(
    page,
    doctype,
):
    """
    Find ONLY the New action for the currently validated DocType.

    The business-document action is intentionally expressed as:
        New <DocType>

    ERPNext may render the same action visually as just ``New``. That
    generic ``New`` is accepted only after the current page has already
    been validated as the requested DocType list.

    IMPORTANT:
        ``Add``, ``+ Add`` and unrelated generic Add actions are never used.
    """
    target = normalize_text(doctype)
    candidates = page.locator("button, a, [role='button']")

    try:
        count = min(candidates.count(), 1000)
    except Exception:
        count = 0

    # 1) Preferred: exact "New" action for the already validated DocType.
    # IMPORTANT: never build "New <DocType>" here because the DocType name
    # itself may already start with "New" (for example "New Company Budget").
    for i in range(count):
        item = candidates.nth(i)
        try:
            if not item.is_visible():
                continue

            text = clean_text(" ".join([
                item.inner_text() or "",
                item.get_attribute("aria-label") or "",
                item.get_attribute("title") or "",
            ]))
            normalized = normalize_text(text)

            if (
                not normalized
                or is_notification_element(text=text)
                or is_workspace_ui(text=text)
            ):
                continue

            if normalized == "new":
                return item
        except Exception:
            continue

    # 2) ERPNext commonly renders the button simply as "New".
    # Accept it ONLY on the already validated target DocType list page.
    if not is_doctype_list_route(page.url):
        return None

    try:
        body = normalize_text(page.locator("body").inner_text(timeout=5000))
    except Exception:
        body = ""

    if target not in body:
        return None

    for i in range(count):
        item = candidates.nth(i)
        try:
            if not item.is_visible():
                continue

            text = clean_text(" ".join([
                item.inner_text() or "",
                item.get_attribute("aria-label") or "",
                item.get_attribute("title") or "",
            ]))
            normalized = normalize_text(text)

            if normalized == "new":
                if is_notification_element(text=text) or is_workspace_ui(text=text):
                    continue
                return item
        except Exception:
            continue

    return None


def is_blank_new_document(page, doctype=""):
    """Return True when ERPNext has already opened a blank New Document."""
    try:
        url = page.url or ""
    except Exception:
        url = ""

    route = urlparse(url).path.lower()
    if "new-" in route or "/new/" in route:
        return True

    try:
        body = normalize_text(page.locator("body").inner_text(timeout=5000))
    except Exception:
        body = ""

    target = normalize_text(doctype)
    if target and target in body:
        # A form with data-fieldname plus Save/Submit is strong evidence that
        # this is the blank document form, even when the route is customized.
        try:
            has_fields = page.locator("[data-fieldname]").count() > 0
        except Exception:
            has_fields = False
        has_save = "save" in body or "submit" in body
        if has_fields and has_save:
            return True

    return False


# ============================================================
# CLICK ADD NEW DOCUMENT
# ============================================================


def click_add_new_document(
    page,
    doctype,
):
    """
    Open a blank document without creating business data.

    Search results on some ERPNext deployments can open the blank New form
    directly. In that case there is no reason to search for another New button.
    Otherwise, on a validated list page, click ONLY the DocType's New action.
    """
    if is_blank_new_document(page, doctype):
        log(f"Blank New Document already opened: {page.url}")
        return page.url

    log("Looking for New")
    add_button = find_add_button(
        page,
        doctype,
    )

    if not add_button:
        raise RuntimeError("New button not found for validated DocType list.")

    log("Clicking New")
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
    log(f"New document URL: {after_url}")

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
    href="",
):

    doctype = clean_doctype_name(doctype)

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
        href=href,
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
    # Discovery notes / implementation comments
    # --------------------------------------------------------
    # These notes make it clear later where each automation rule
    # was applied while reading the ERPNext form.
    data["discovery_notes"] = {
        "navigation": (
            "Login -> ERPNext Home -> Global Search using 'New <DocType>' -> DocType List "
            "or blank New Document -> read all fields -> store main DocType without 'New'"
        ),
        "doctype_validation": (
            "DocType is accepted from a clean /app/<doctype> list route and the opened list page is UI-validated; no metadata API dependency."
        ),
        "record_rule": (
            "Existing business documents are not opened for discovery; "
            "only the blank New Document form is inspected."
        ),
        "system_ui_rule": (
            "Notification, Bell, Search, Filter, Settings, Workspace and "
            "other system UI are ignored and never treated as DocTypes."
        ),
        "field_rule": (
            "Visible form fields are read for fieldname, label, fieldtype, "
            "required state, placeholder/options and available actions."
        ),
        "tab_section_rule": (
            "Every visible form tab is opened and read one-by-one; fields are stored with tab context, and sections are collected from each tab."
        ),
        "scroll_rule": (
            "Each form tab is scanned from top to bottom in multiple scroll positions so long forms and lazy-rendered fields are not missed."
        ),
        "blank_form_rule": (
            "The agent reads the blank New Document without filling or saving business data."
        ),
        "ai_knowledge_rule": (
            "The JSON is an observation record for future AI retrieval/planning, not a test execution result."
        ),
    }

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

            # ------------------------------------------------
            # 1) Take this DocType name from the module list.
            # 2) Go Home -> Global Search and search this exact DocType name.
            # 3) Open the search result -> DocType List -> New <DocType>/New.
            # 4) Open the blank document and read the complete form.
            # 5) Return to Home -> same Module before processing next DocType.
            # ------------------------------------------------
            discover_doctype(
                page,
                doctype,
                module_name=module_name,
                href=item.get("href", ""),
            )

            success += 1

        except Exception as exc:

            failed += 1

            log(f"FAILED: {doctype}")
            log(f"Reason: {exc}")

            try:
                path = SCREENSHOT_DIR / f"failure_{slugify(doctype)}.png"
                page.screenshot(
                    path=str(path),
                    full_page=True,
                )
            except Exception:
                pass

        finally:
            # ------------------------------------------------
            # ALWAYS RETURN TO THE MODULE BEFORE NEXT DOC.
            # This is the core requested sequence:
            #   Module -> Doc A -> New -> Read -> Back -> Doc B ...
            # ------------------------------------------------
            try:
                open_home(page)
                open_module(page, module_name)
                page.wait_for_timeout(WAIT_MEDIUM)
                log(f"BACK TO MODULE: {module_name}")
            except Exception as recovery_error:
                log(f"Recovery failed: {recovery_error}")

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

    doctype = clean_doctype_name(doctype)

    log("======================================")

    log(f"SINGLE DOCTYPE DISCOVERY: " f"{doctype}")

    log("======================================")

    if is_system_ui(text=doctype) or is_notification_element(text=doctype):
        log(f"BLOCKED SYSTEM UI TARGET: {doctype}")
        return

    # Direct DocType mode always starts from Home -> Search.
    open_home(page)

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
        nargs="+",
        required=False,
        help=(
            "Discover one or more DocTypes serially. "
            "Each name is searched from Global Search, opened, read, and stored as JSON."
        ),
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

                # ------------------------------------------------
                # MULTIPLE DOCTYPE MODE
                # ------------------------------------------------
                # The user can provide several DocType names in one run.
                # They are processed strictly in the given order:
                #
                #   Home -> Search Doc A -> Open -> New -> Read -> JSON
                #        -> Home -> Search Doc B -> Open -> New -> Read -> JSON
                #        -> ...
                #
                # Each DocType gets its own discovery JSON record.
                # No existing business record is opened or saved.
                total = len(args.doctype)
                success = 0
                skipped = 0
                failed = 0

                log("======================================")
                log(f"SERIAL DOCTYPE DISCOVERY: {total} DOCUMENTS")
                log("======================================")

                for index, doctype in enumerate(args.doctype, start=1):
                    doctype = clean_doctype_name(doctype)

                    log("--------------------------------------")
                    log(f"DOCTYPE {index}/{total}: {doctype}")
                    log("--------------------------------------")

                    if not doctype:
                        log("SKIP: Empty DocType name")
                        skipped += 1
                        continue

                    if is_system_ui(text=doctype) or is_notification_element(text=doctype):
                        log(f"SKIP SYSTEM UI TARGET: {doctype}")
                        skipped += 1
                        continue

                    try:
                        existing = discovery_file_for_doctype(doctype)
                        if existing:
                            log(f"SKIP EXISTING: {doctype} -> {existing.name}")
                            skipped += 1
                            continue

                        # Always restart from Home before every DocType so the
                        # search/open sequence is deterministic and isolated.
                        open_home(page)

                        discover_doctype(
                            page,
                            doctype,
                            module_name="",
                        )

                        success += 1
                        log(f"SERIAL DISCOVERY SUCCESS: {doctype}")

                    except Exception as exc:
                        failed += 1
                        log(f"SERIAL DISCOVERY FAILED: {doctype}")
                        log(f"Reason: {exc}")

                        try:
                            path = SCREENSHOT_DIR / f"failure_{slugify(doctype)}.png"
                            page.screenshot(path=str(path), full_page=True)
                            log(f"Failure screenshot: {path}")
                        except Exception:
                            pass

                    finally:
                        # After each document, return to Home before searching
                        # the next name. This prevents the next search from
                        # starting inside the previous DocType form.
                        try:
                            open_home(page)
                            log(f"READY FOR NEXT DOCTYPE: {index + 1}/{total}")
                        except Exception as recovery_error:
                            log(f"Home recovery failed: {recovery_error}")

                log("======================================")
                log("SERIAL DOCTYPE DISCOVERY FINISHED")
                log(f"SUCCESS: {success}")
                log(f"SKIPPED: {skipped}")
                log(f"FAILED: {failed}")
                log("======================================")

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
