"""
ERPNext AI QA - Executor

Purpose
-------
Execute safe actions from Planner output using Playwright.

Default behavior:
    - inspect
    - fill
    - select
    - check

Blocked business actions:
    - save
    - submit
    - delete
    - cancel
    - amend
    - payment / commit actions

.env keys MUST match discovery_agent.py:
    ERPNEXT_URL
    ERPNEXT_USER
    ERPNEXT_PASSWORD
    HEADLESS
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

PLAN_DIR = BASE_DIR / "data" / "plans"
EXECUTION_DIR = BASE_DIR / "data" / "executions"

EXECUTION_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

# ============================================================
# SAME .ENV AS DISCOVERY AGENT
# ============================================================

load_dotenv(BASE_DIR / ".env")

DEFAULT_TIMEOUT = int(
    os.getenv(
        "PLAYWRIGHT_TIMEOUT",
        "15000",
    )
)

ERP_URL = os.getenv(
    "ERPNEXT_URL",
    "https://stage2-salma.altersense.net",
).rstrip("/")

USERNAME = os.getenv(
    "ERPNEXT_USER",
    "",
)

PASSWORD = os.getenv(
    "ERPNEXT_PASSWORD",
    "",
)

HEADLESS = (
    os.getenv(
        "HEADLESS",
        "false",
    ).lower()
    == "true"
)


# ============================================================
# SAFETY
# ============================================================

BLOCKED_ACTIONS = {
    "save",
    "submit",
    "delete",
    "cancel",
    "cancel_document",
    "amend",
    "make_payment",
    "submit_payment",
    "create",
    "insert",
    "remove",
    "duplicate",
}

SYSTEM_UI = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
    "bell",
    "help",
    "filter",
    "filters",
    "settings",
    "search",
    "list view",
    "kanban",
    "calendar",
    "dashboard",
    "load more",
    "new workspace",
    "create workspace",
    "add workspace",
}


# ============================================================
# TEXT
# ============================================================


def clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def clean_doctype(value: Any) -> str:
    """
    Main DocType never includes 'New'.

    New Contract -> Contract
    Contract     -> Contract
    """
    return re.sub(
        r"^New\s+",
        "",
        clean(value),
        flags=re.IGNORECASE,
    ).strip()


def build_search_name(
    doctype: str,
) -> str:
    return f"New {clean_doctype(doctype)}"


def is_system_ui(
    value: Any,
) -> bool:
    text = clean(value).lower()

    return text in SYSTEM_UI or "notification" in text or text == "bell"


# ============================================================
# CONFIG VALIDATION
# ============================================================


def validate_config() -> None:
    """
    Validate the SAME .env configuration used by discovery_agent.py.

    Password is never printed.
    """

    missing = []

    if not ERP_URL:
        missing.append("ERPNEXT_URL")

    if not USERNAME:
        missing.append("ERPNEXT_USER")

    if not PASSWORD:
        missing.append("ERPNEXT_PASSWORD")

    if missing:
        raise RuntimeError("Missing required .env configuration: " + ", ".join(missing))


# ============================================================
# PLAN
# ============================================================


def load_plan(
    path_arg: Optional[str],
) -> dict[str, Any]:

    path = Path(path_arg) if path_arg else PLAN_DIR / "latest_plan.json"

    if not path.is_absolute():
        path = BASE_DIR / path

    if not path.exists():
        raise FileNotFoundError(f"Plan not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Plan JSON root must be an object")

    return data


# ============================================================
# LOCATOR
# ============================================================


def first_visible(
    locators: list[Locator],
) -> Optional[Locator]:

    for locator in locators:

        try:
            count = locator.count()
        except Exception:
            continue

        for i in range(count):

            try:
                item = locator.nth(i)

                if item.is_visible():
                    return item

            except Exception:
                continue

    return None


# ============================================================
# LOGIN
# ============================================================


def login(
    page: Page,
) -> None:

    # Already logged in.
    if "/app" in page.url.lower():
        return

    # --------------------------------------------------------
    # USERNAME
    # Same selectors as discovery_agent.py
    # --------------------------------------------------------

    user = first_visible(
        [
            page.locator("input[name='usr']"),
            page.locator("input[autocomplete='username']"),
            page.locator("input[name='login']"),
            page.get_by_label(
                re.compile(
                    "username|email",
                    re.I,
                )
            ),
            page.get_by_placeholder(
                re.compile(
                    "username|email",
                    re.I,
                )
            ),
            page.locator('input[type="email"]'),
            page.locator('input[type="text"]'),
        ]
    )

    # --------------------------------------------------------
    # PASSWORD
    # Same selectors as discovery_agent.py
    # --------------------------------------------------------

    password = first_visible(
        [
            page.locator("input[name='pwd']"),
            page.locator("input[name='password']"),
            page.get_by_label(
                re.compile(
                    "password",
                    re.I,
                )
            ),
            page.get_by_placeholder(
                re.compile(
                    "password",
                    re.I,
                )
            ),
            page.locator('input[type="password"]'),
        ]
    )

    if not user:
        raise RuntimeError("Visible username field not found.")

    if not password:
        raise RuntimeError("Visible password field not found.")

    user.fill(USERNAME)

    page.wait_for_timeout(500)

    password.fill(PASSWORD)

    # --------------------------------------------------------
    # LOGIN BUTTON
    # --------------------------------------------------------

    login_button = first_visible(
        [
            page.get_by_role(
                "button",
                name=re.compile(
                    r"log.?in|sign.?in",
                    re.I,
                ),
            ),
            page.locator('button[type="submit"]'),
            page.locator('input[type="submit"]'),
        ]
    )

    if not login_button:
        raise RuntimeError("Login button not found.")

    login_button.click()

    try:
        page.wait_for_url(
            re.compile(r"/app"),
            timeout=DEFAULT_TIMEOUT,
        )
    except PlaywrightTimeoutError:
        try:
            page.wait_for_load_state(
                "domcontentloaded",
                timeout=DEFAULT_TIMEOUT,
            )
        except PlaywrightTimeoutError:
            pass

    page.wait_for_timeout(1000)

    if "/app" not in page.url.lower():
        raise RuntimeError(f"Login failed. Current URL: {page.url}")


# ============================================================
# HOME
# ============================================================


def open_home(
    page: Page,
) -> None:

    page.goto(
        f"{ERP_URL}/app/home",
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.wait_for_timeout(1000)

    if "/login" in page.url.lower():
        login(page)

    if "/app" not in page.url.lower():
        raise RuntimeError(f"Home could not be opened: {page.url}")


# ============================================================
# GLOBAL SEARCH
# ============================================================


def get_global_search(
    page: Page,
) -> Optional[Locator]:

    candidates = [
        page.locator("input[placeholder*='Search or type a command']"),
        page.locator("input[placeholder*='Search or type']"),
        page.locator("input[aria-label*='Search']"),
        page.locator(".search-bar input"),
        page.locator(".navbar-search input"),
        page.locator("input[placeholder='Search']"),
    ]

    return first_visible(candidates)


# ============================================================
# SEARCH RESULT
# ============================================================


def is_exact_search_result(
    text: str,
    doctype: str,
) -> bool:

    text = clean(text)
    target = clean_doctype(doctype)

    if not text or not target:
        return False

    if text.casefold() == target.casefold():
        return True

    if text.casefold() == build_search_name(target).casefold():
        return True

    return bool(
        re.fullmatch(
            rf"New\s+{re.escape(target)}|{re.escape(target)}",
            text,
            flags=re.IGNORECASE,
        )
    )


def search_doctype(
    page: Page,
    doctype: str,
) -> bool:

    doctype = clean_doctype(doctype)

    if not doctype:
        raise ValueError("DocType is empty.")

    if is_system_ui(doctype):
        raise RuntimeError(f"Blocked system UI target: {doctype}")

    open_home(page)

    search_box = get_global_search(page)

    if not search_box:
        raise RuntimeError("Global Search input not found.")

    search_name = build_search_name(doctype)

    search_box.click()

    search_box.fill(search_name)

    page.wait_for_timeout(1000)

    selectors = [
        ".search-result",
        ".awesomplete li",
        "[role='option']",
        ".dropdown-menu a",
        ".dropdown-menu button",
        "a[href*='/app/']",
    ]

    for selector in selectors:

        locator = page.locator(selector)

        try:
            count = min(
                locator.count(),
                500,
            )
        except Exception:
            continue

        for i in range(count):

            item = locator.nth(i)

            try:

                if not item.is_visible():
                    continue

                text = clean(
                    " ".join(
                        [
                            item.inner_text() or "",
                            item.get_attribute("aria-label") or "",
                            item.get_attribute("title") or "",
                        ]
                    )
                )

                if not text:
                    continue

                if is_system_ui(text):
                    continue

                if not is_exact_search_result(
                    text,
                    doctype,
                ):
                    continue

                item.click()

                page.wait_for_timeout(1200)

                return True

            except Exception:
                continue

    return False


# ============================================================
# NEW FORM
# ============================================================


def is_blank_new_form(
    page: Page,
    doctype: str,
) -> bool:

    target = clean_doctype(doctype)

    route = page.url.lower()

    if "new-" in route or "/new/" in route:
        return True

    try:
        body = clean(page.locator("body").inner_text(timeout=5000)).lower()
    except Exception:
        body = ""

    if target.lower() not in body:
        return False

    try:
        has_fields = page.locator("[data-fieldname]").count() > 0
    except Exception:
        has_fields = False

    return has_fields or "save" in body or "submit" in body


# ============================================================
# NEW BUTTON
# ============================================================


def find_new_button(
    page: Page,
) -> Optional[Locator]:

    candidates = page.locator("button, a, [role='button']")

    try:
        count = min(
            candidates.count(),
            1000,
        )
    except Exception:
        return None

    for i in range(count):

        item = candidates.nth(i)

        try:

            if not item.is_visible():
                continue

            text = clean(
                " ".join(
                    [
                        item.inner_text() or "",
                        item.get_attribute("aria-label") or "",
                        item.get_attribute("title") or "",
                    ]
                )
            )

            if text.casefold() != "new":
                continue

            if is_system_ui(text):
                continue

            return item

        except Exception:
            continue

    return None


def open_new_form(
    page: Page,
    doctype: str,
) -> None:

    if is_blank_new_form(
        page,
        doctype,
    ):
        return

    button = find_new_button(page)

    if not button:
        raise RuntimeError(f"New button not found for {doctype}")

    button.click()

    page.wait_for_timeout(1200)

    if not is_blank_new_form(
        page,
        doctype,
    ):
        raise RuntimeError(f"Blank New form could not be verified for {doctype}")


# ============================================================
# FIELD LOCATOR
# ============================================================


def get_field_locator(
    page: Page,
    field: dict[str, Any],
) -> Optional[Locator]:

    fieldname = clean(field.get("fieldname"))

    label = clean(field.get("label"))

    if is_system_ui(fieldname) or is_system_ui(label):
        return None

    candidates: list[Locator] = []

    # ERPNext fieldname first.
    if fieldname:

        candidates.extend(
            [
                page.locator(f'[data-fieldname="{fieldname}"] input'),
                page.locator(f'[data-fieldname="{fieldname}"] textarea'),
                page.locator(f'[data-fieldname="{fieldname}"] select'),
                page.locator(
                    f'[data-fieldname="{fieldname}"] ' f'[contenteditable="true"]'
                ),
                page.locator(f'[data-fieldname="{fieldname}"]'),
            ]
        )

    # Label fallback.
    if label:

        candidates.extend(
            [
                page.get_by_label(
                    label,
                    exact=True,
                ),
            ]
        )

    return first_visible(candidates)


# ============================================================
# BOOLEAN
# ============================================================


def normalize_bool(
    value: Any,
) -> bool:

    if isinstance(value, bool):
        return value

    return clean(value).lower() in {
        "true",
        "1",
        "yes",
        "y",
        "checked",
        "on",
    }


# ============================================================
# EXECUTE FIELD
# ============================================================


def execute_field(
    page: Page,
    field: dict[str, Any],
) -> dict[str, Any]:

    fieldname = clean(field.get("fieldname"))

    label = clean(field.get("label")) or fieldname

    value = field.get(
        "value",
        field.get("test_value"),
    )

    fieldtype = clean(field.get("fieldtype")).lower()

    result = {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "action": "inspect",
        "status": "SKIPPED",
    }

    if is_system_ui(fieldname) or is_system_ui(label):
        result["reason"] = "system UI blocked"
        return result

    locator = get_field_locator(
        page,
        field,
    )

    if locator is None:
        result["reason"] = "field locator not found"
        return result

    try:

        # ----------------------------------------------------
        # CHECKBOX
        # ----------------------------------------------------

        if fieldtype in {
            "check",
            "checkbox",
            "radio",
        }:

            if value is not None:

                locator.set_checked(normalize_bool(value))

                result["action"] = "set_checked"

            else:
                result["action"] = "inspect"

        # ----------------------------------------------------
        # SELECT
        # ----------------------------------------------------

        elif fieldtype in {
            "select",
            "selectbox",
        }:

            if value not in (
                None,
                "",
            ):

                locator.select_option(label=str(value))

                result["action"] = "select_option"

            else:
                result["action"] = "inspect"

        # ----------------------------------------------------
        # TEXT / DATE / NUMBER
        # ----------------------------------------------------

        elif fieldtype in {
            "date",
            "datetime",
            "time",
            "int",
            "integer",
            "float",
            "decimal",
            "currency",
            "percent",
            "data",
            "small text",
            "text",
            "textarea",
            "long text",
            "text editor",
            "code",
        }:

            if value not in (
                None,
                "",
            ):

                try:
                    locator.fill(str(value))

                except Exception:

                    locator.click()

                    locator.press_sequentially(str(value))

                result["action"] = "fill"

            else:
                result["action"] = "inspect"

        # ----------------------------------------------------
        # UNKNOWN / LINK
        # ----------------------------------------------------

        else:
            result["action"] = "inspect"

        result["status"] = "PASSED"

    except Exception as exc:

        result["status"] = "FAILED"
        result["error"] = str(exc)

    return result


# ============================================================
# BUTTON
# ============================================================


def execute_button(
    page: Page,
    button: dict[str, Any],
) -> dict[str, Any]:

    name = clean(button.get("button") or button.get("label") or button.get("name"))

    result = {
        "button": name,
        "action": "inspect",
        "status": "SKIPPED",
    }

    if not name:
        result["reason"] = "empty button"
        return result

    if is_system_ui(name):
        result["reason"] = "system UI blocked"
        return result

    lowered = name.lower()

    if lowered in BLOCKED_ACTIONS or any(
        word in lowered
        for word in (
            "save",
            "submit",
            "delete",
            "cancel",
            "amend",
        )
    ):

        result["reason"] = "business mutation blocked"
        return result

    try:

        locator = page.get_by_role(
            "button",
            name=name,
            exact=True,
        )

        locator.scroll_into_view_if_needed()

        result["visible"] = locator.is_visible()

        result["status"] = "PASSED"

    except Exception as exc:

        result["status"] = "FAILED"
        result["error"] = str(exc)

    return result


# ============================================================
# EXECUTE PLAN
# ============================================================


def execute_plan(
    page: Page,
    plan: dict[str, Any],
) -> dict[str, Any]:

    doctype = clean_doctype(plan.get("doctype") or plan.get("document_name"))

    steps = (
        plan.get("steps", [])
        if isinstance(
            plan.get("steps", []),
            list,
        )
        else []
    )

    if not doctype:
        raise ValueError("Plan does not contain doctype")

    results = []

    for step in steps:

        if not isinstance(
            step,
            dict,
        ):
            continue

        action = clean(step.get("action")).lower()

        # ----------------------------------------------------
        # HARD BLOCK
        # ----------------------------------------------------

        if action in BLOCKED_ACTIONS:

            results.append(
                {
                    "action": action,
                    "status": "BLOCKED",
                    "reason": ("business mutation " "not allowed"),
                }
            )

            continue

        # ----------------------------------------------------
        # NAVIGATION
        # ----------------------------------------------------
        # Navigator owns browser navigation.
        # ----------------------------------------------------

        if action in {
            "login",
            "open_home",
            "global_search",
            "open_blank_new_document",
            "inspect_form_top_to_bottom",
            "inspect_tab",
            "inspect_section",
            "inspect_link_relation",
        }:

            results.append(
                {
                    "action": action,
                    "status": ("DEFERRED_TO_NAVIGATOR"),
                }
            )

            continue

        # ----------------------------------------------------
        # FIELD
        # ----------------------------------------------------

        if action == "inspect_field":

            results.append(
                execute_field(
                    page,
                    step,
                )
            )

            continue

        # ----------------------------------------------------
        # BUTTON
        # ----------------------------------------------------

        if action == "inspect_button":

            results.append(
                execute_button(
                    page,
                    step,
                )
            )

            continue

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        results.append(
            {
                "action": (action or "unknown"),
                "status": "SKIPPED",
                "reason": ("unsupported executor action"),
            }
        )

    passed = sum(item.get("status") == "PASSED" for item in results)

    failed = sum(item.get("status") == "FAILED" for item in results)

    blocked = sum(item.get("status") == "BLOCKED" for item in results)

    return {
        "status": "EXECUTED",
        "doctype": doctype,
        "document_name": doctype,
        "search_name": build_search_name(doctype),
        "action": "New",
        "existing_documents_skipped": True,
        "business_data_mutated": False,
        "blocked_business_mutations": True,
        "system_ui_blocked": True,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
        },
        "results": results,
        "current_url": page.url,
    }


# ============================================================
# MAIN
# ============================================================


def main() -> int:

    parser = argparse.ArgumentParser(description=("ERPNext AI QA Executor"))

    parser.add_argument(
        "--plan",
        default=str(PLAN_DIR / "latest_plan.json"),
        help="Planner JSON path.",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
        help="Force visible browser.",
    )

    args = parser.parse_args()

    try:

        # ----------------------------------------------------
        # CONFIG
        # ----------------------------------------------------

        validate_config()

        print(f"[EXECUTOR] ERP: {ERP_URL}")

        print("[EXECUTOR] USER: configured")

        print("[EXECUTOR] PASSWORD: configured")

        browser_headless = HEADLESS if not args.headed else False

        print(f"[EXECUTOR] HEADLESS: " f"{browser_headless}")

        # ----------------------------------------------------
        # PLAN
        # ----------------------------------------------------

        plan = load_plan(args.plan)

        doctype = clean_doctype(plan.get("doctype") or plan.get("document_name") or "")

        if not doctype:
            raise RuntimeError("Planner output has no DocType.")

        if is_system_ui(doctype):
            raise RuntimeError(f"Blocked system UI DocType: {doctype}")

        # ----------------------------------------------------
        # PLAYWRIGHT
        # ----------------------------------------------------

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=browser_headless)

            context = browser.new_context(
                viewport={
                    "width": 1440,
                    "height": 900,
                }
            )

            page = context.new_page()

            page.set_default_timeout(DEFAULT_TIMEOUT)

            # ------------------------------------------------
            # OPEN ERP
            # ------------------------------------------------

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
            # HOME
            # ------------------------------------------------

            open_home(page)

            # ------------------------------------------------
            # EXECUTE SAFE PLAN ACTIONS
            # ------------------------------------------------

            result = execute_plan(
                page,
                plan,
            )

            # ------------------------------------------------
            # SAVE RESULT
            # ------------------------------------------------

            output = EXECUTION_DIR / "latest_execution.json"

            output.write_text(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            print(f"[EXECUTOR] Output: {output}")

            context.close()
            browser.close()

        return 0

    except Exception as exc:

        print(f"[EXECUTOR] FAILED: {exc}")

        return 1


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    raise SystemExit(main())
