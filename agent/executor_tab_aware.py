"""
ERPNext AI QA - Executor

Executes the current Planner JSON in one Playwright browser session.

Current safe scope:
- Login -> Home -> Global Search -> blank New DocType form
- Inspect every planned tab, section, field, button and link relation
- Scroll to off-screen controls before inspection
- Use data-fieldname first for field identity
- Skip ERPNext layout fields from business-field execution
- Block Save / Submit / Delete / Cancel / Amend / Payment / Create actions
- Never open an existing business record intentionally
- Never mutate business data

The Executor currently performs non-mutating inspection and field interaction
only when the plan explicitly provides a test value. The Planner currently
creates inspection steps, so this run is primarily a complete execution/health
check of the generated plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from playwright.sync_api import Locator, Page, sync_playwright, TimeoutError as PlaywrightTimeoutError

from navigator import (
    DEFAULT_TIMEOUT,
    assert_config,
    clean_doctype_name,
    is_system_ui,
    load_plan,
    navigate_plan,
    open_new_doctype,
    navigate_tabs,
    scroll_form_top_to_bottom,
)


FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = FILE_PATH.parents[1]
EXECUTION_DIR = PROJECT_ROOT / "data" / "executions"
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "screenshots"
EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")

ERP_URL = os.getenv(
    "ERPNEXT_URL",
    "https://stage2-salma.altersense.net",
).rstrip("/")
USERNAME = os.getenv("ERPNEXT_USER", "")
PASSWORD = os.getenv("ERPNEXT_PASSWORD", "")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"


# ============================================================
# SAFETY / CLASSIFICATION
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

LAYOUT_FIELD_TYPES = {
    "section break",
    "section_break",
    "column break",
    "column_break",
    "tab break",
    "tab_break",
    "html",
    "fold",
    "heading",
    "button",
    "image",
}

LAYOUT_FIELD_PATTERNS = (
    re.compile(r"(^|_)column_break($|_)", re.I),
    re.compile(r"(^|_)section(_break)?($|_)", re.I),
    re.compile(r"(^|_)tab(_break)?($|_)", re.I),
    re.compile(r"^__", re.I),
)

SYSTEM_UI_WORDS = {
    "notification",
    "notifications",
    "no new notifications",
    "bell",
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
    "new workspace",
    "create workspace",
    "add workspace",
}


def assert_executor_config() -> None:
    missing = []
    if not ERP_URL:
        missing.append("ERPNEXT_URL")
    if not USERNAME:
        missing.append("ERPNEXT_USER")
    if not PASSWORD:
        missing.append("ERPNEXT_PASSWORD")
    if missing:
        raise RuntimeError(
            "Missing required .env configuration: " + ", ".join(missing)
        )


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize(value: Any) -> str:
    return clean(value).lower()


def action_is_blocked(action: Any) -> bool:
    value = normalize(action)
    if value in BLOCKED_ACTIONS:
        return True
    return any(
        word in value
        for word in (
            "save",
            "submit",
            "delete",
            "cancel",
            "payment",
            "amend",
            "duplicate",
            "remove",
        )
    )


def is_layout_field(field: dict[str, Any]) -> bool:
    fieldname = clean(
        field.get("fieldname") or field.get("field_name")
    )
    fieldtype = normalize(
        field.get("fieldtype") or field.get("field_type")
    )

    if fieldtype in LAYOUT_FIELD_TYPES:
        return True

    return any(pattern.search(fieldname) for pattern in LAYOUT_FIELD_PATTERNS)


def is_system_value(value: Any) -> bool:
    text = normalize(value)
    if not text:
        return False
    if text in SYSTEM_UI_WORDS:
        return True
    return "notification" in text or text == "bell"


# ============================================================
# LOCATOR HELPERS
# ============================================================

def visible_locator(locator: Locator) -> Optional[Locator]:
    try:
        count = locator.count()
    except Exception:
        return None

    for index in range(count):
        try:
            candidate = locator.nth(index)
            if candidate.is_visible():
                return candidate
        except Exception:
            continue

    return None


def field_wrapper(page: Page, fieldname: str) -> Optional[Locator]:
    if not fieldname:
        return None

    locator = page.locator(f'[data-fieldname="{fieldname}"]')
    try:
        count = locator.count()
    except Exception:
        return None

    for index in range(count):
        try:
            candidate = locator.nth(index)
            return candidate
        except Exception:
            continue

    return None


def get_field_locator(page: Page, field: dict[str, Any]) -> Optional[Locator]:
    fieldname = clean(
        field.get("fieldname") or field.get("field_name")
    )
    label = clean(field.get("label"))

    if not fieldname:
        return None

    wrapper = field_wrapper(page, fieldname)
    if wrapper is not None:
        # Prefer a real control inside the exact ERPNext field wrapper.
        control = wrapper.locator(
            "input:not([type='hidden']), textarea, select, "
            "[contenteditable='true'], button"
        )

        visible_control = visible_locator(control)
        if visible_control is not None:
            return visible_control

        # Table/structural widgets may not expose a regular input. The wrapper
        # itself is still valid evidence that the field exists in the form.
        try:
            if wrapper.count() > 0:
                return wrapper
        except Exception:
            pass

    # Accessible label is a secondary fallback.
    if label:
        labeled = page.get_by_label(label, exact=True)
        fallback = visible_locator(labeled)
        if fallback is not None:
            return fallback

    return None


def ensure_form_context(
    page: Page,
    doctype: str,
    expected_url: str,
) -> None:
    """Make sure field/button inspection is happening on the blank New form."""
    current = page.url or ""

    route_ok = (
        "/app/" in current
        and (
            "new-" in current.lower()
            or "/new/" in current.lower()
        )
    )

    if expected_url and current != expected_url:
        route_ok = False

    if not route_ok:
        print(
            f"[EXECUTOR] Form context lost. Re-opening: New {doctype}"
        )
        open_new_doctype(page, doctype)

    if "/app/" not in page.url:
        raise RuntimeError(
            f"Could not reach ERPNext blank New {doctype} form."
        )


# ============================================================
# INSPECTION ACTIONS
# ============================================================

# ============================================================
# TAB-AWARE FIELD CONTEXT
# ============================================================

def open_planned_tab(page: Page, tab_name: str) -> bool:
    """Open the exact planned ERPNext form tab without touching business data."""
    tab_name = clean(tab_name)
    if not tab_name:
        return True

    candidates = [
        page.get_by_role("tab", name=tab_name, exact=True),
        page.locator(".form-tabs .nav-link").filter(
            has_text=re.compile(rf"^\s*{re.escape(tab_name)}\s*$", re.I)
        ),
        page.locator(".nav-tabs .nav-link").filter(
            has_text=re.compile(rf"^\s*{re.escape(tab_name)}\s*$", re.I)
        ),
        page.get_by_text(tab_name, exact=True),
    ]

    for candidate in candidates:
        found = first_visible(candidate)
        if found is None:
            continue
        try:
            found.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            found.click()
            page.wait_for_timeout(350)
            return True
        except Exception:
            continue

    return False


def field_exists_in_any_dom_state(page: Page, fieldname: str) -> bool:
    """Check field identity without opening existing records or mutating data."""
    if not fieldname:
        return False
    try:
        return page.locator(f'[data-fieldname="{fieldname}"]').count() > 0
    except Exception:
        return False


def ensure_field_tab(page: Page, field: dict[str, Any]) -> dict[str, Any]:
    """Move to the field's planned tab before trying its locator."""
    tab_name = clean(field.get("tab"))
    fieldname = clean(field.get("fieldname"))

    if not tab_name:
        return {"tab": "", "changed": False, "available": True}

    ok = open_planned_tab(page, tab_name)
    return {
        "tab": tab_name,
        "changed": bool(ok),
        "available": bool(ok),
        "field_in_dom_after_tab": field_exists_in_any_dom_state(page, fieldname),
    }


def inspect_field(page: Page, step: dict[str, Any]) -> dict[str, Any]:
    fieldname = clean(
        step.get("fieldname") or step.get("field_name")
    )
    label = clean(step.get("label") or fieldname)
    fieldtype = clean(
        step.get("fieldtype") or step.get("field_type")
    )

    result = {
        "order": step.get("order"),
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "action": "inspect_field",
        "status": "SKIPPED",
    }

    if is_system_value(fieldname) or is_system_value(label):
        result["reason"] = "system UI blocked"
        return result

    tab_context = ensure_field_tab(page, step)
    if tab_context["tab"]:
        result["tab"] = tab_context["tab"]
        result["tab_opened"] = tab_context["available"]

        if not tab_context["available"]:
            result["reason"] = f'planned tab not found: {tab_context["tab"]}'
            return result

    if is_layout_field(step):
        result["reason"] = "layout field excluded from business-field execution"
        result["category"] = "layout"
        return result

    locator = get_field_locator(page, step)

    if locator is None:
        result["reason"] = "field locator not found in current form DOM"
        return result

    try:
        # Bring the exact field into view when possible. The operation is
        # non-mutating and helps long Purchase Order forms.
        locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    try:
        result["located"] = True
        result["visible"] = locator.is_visible()
    except Exception:
        result["located"] = True
        result["visible"] = False

    # Planner currently provides inspection-only fields. Only perform an
    # actual fill/select/check when an explicit test_value/value is present.
    if "test_value" in step or "value" in step:
        value = step.get("test_value", step.get("value"))
        if value not in (None, ""):
            try:
                ft = normalize(fieldtype)

                if ft in {"check", "checkbox"}:
                    locator.set_checked(bool(value))
                elif ft in {"select", "selectbox"}:
                    locator.select_option(label=str(value))
                elif ft in {"link", "dynamic link"}:
                    locator.fill(str(value))
                else:
                    try:
                        locator.fill(str(value))
                    except Exception:
                        locator.click()
                        locator.type(str(value))

                result["execution"] = "value_applied"
            except Exception as exc:
                result["status"] = "FAILED"
                result["error"] = str(exc)
                return result

    result["status"] = "PASSED"
    result["reason"] = "field located/inspected"
    return result


def find_named_button(page: Page, name: str) -> Optional[Locator]:
    candidates = [
        page.get_by_role("button", name=name, exact=True),
        page.locator("button").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$", re.I)),
        page.get_by_text(name, exact=True),
    ]

    for locator in candidates:
        found = visible_locator(locator)
        if found is not None:
            return found

    return None


def inspect_button(page: Page, step: dict[str, Any]) -> dict[str, Any]:
    name = clean(
        step.get("button") or step.get("label") or step.get("name")
    )

    result = {
        "order": step.get("order"),
        "button": name,
        "action": "inspect_button",
        "status": "SKIPPED",
    }

    if not name:
        result["reason"] = "empty button name"
        return result

    if is_system_value(name):
        result["reason"] = "system UI blocked"
        return result

    if action_is_blocked(name):
        result["reason"] = "business mutation blocked"
        return result

    locator = find_named_button(page, name)
    if locator is None:
        result["reason"] = "button not found in current form DOM"
        return result

    try:
        locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    result["visible"] = locator.is_visible()
    result["status"] = "PASSED"
    result["reason"] = "button inspected without clicking"
    return result


def inspect_tab(page: Page, step: dict[str, Any]) -> dict[str, Any]:
    name = clean(step.get("tab") or step.get("label") or step.get("name"))

    result = {
        "order": step.get("order"),
        "tab": name,
        "action": "inspect_tab",
        "status": "SKIPPED",
    }

    if not name or is_system_value(name):
        result["reason"] = "system UI or empty tab"
        return result

    candidates = [
        page.get_by_role("tab", name=name, exact=True),
        page.locator(".form-tabs .nav-link").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$", re.I)),
        page.get_by_text(name, exact=True),
    ]

    locator = None
    for candidate in candidates:
        locator = visible_locator(candidate)
        if locator is not None:
            break

    if locator is None:
        result["reason"] = "tab not found"
        return result

    try:
        locator.click()
        page.wait_for_timeout(300)
        positions = scroll_form_top_to_bottom(page, pause_ms=150)
        result["scroll_positions"] = positions
        result["status"] = "PASSED"
        result["reason"] = "tab opened and form scanned"
    except Exception as exc:
        result["status"] = "FAILED"
        result["error"] = str(exc)

    return result


def inspect_section(page: Page, step: dict[str, Any]) -> dict[str, Any]:
    name = clean(step.get("section") or step.get("label") or step.get("name"))

    result = {
        "order": step.get("order"),
        "section": name,
        "action": "inspect_section",
        "status": "SKIPPED",
    }

    if not name or is_system_value(name):
        result["reason"] = "system UI or empty section"
        return result

    locators = [
        page.locator(".section-head, .collapse-label").filter(has_text=re.compile(rf"^\s*{re.escape(name)}\s*$", re.I)),
        page.get_by_text(name, exact=True),
    ]

    locator = None
    for candidate in locators:
        locator = visible_locator(candidate)
        if locator is not None:
            break

    if locator is None:
        result["reason"] = "section not found"
        return result

    try:
        locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    result["visible"] = locator.is_visible()
    result["status"] = "PASSED"
    result["reason"] = "section inspected without mutation"
    return result


def inspect_link_relation(page: Page, step: dict[str, Any]) -> dict[str, Any]:
    label = clean(step.get("label") or step.get("name"))

    result = {
        "order": step.get("order"),
        "label": label,
        "action": "inspect_link_relation",
        "status": "SKIPPED",
    }

    if not label or is_system_value(label):
        result["reason"] = "system UI or empty relation"
        return result

    # A relation label can appear as a field label, button, or connection link.
    candidates = [
        page.get_by_text(label, exact=True),
        page.get_by_label(label, exact=True),
        page.locator(f'[data-fieldname="{label}"]'),
    ]

    locator = None
    for candidate in candidates:
        try:
            count = candidate.count()
        except Exception:
            continue
        for index in range(count):
            try:
                current = candidate.nth(index)
                if current.is_visible():
                    locator = current
                    break
            except Exception:
                continue
        if locator is not None:
            break

    if locator is None:
        result["reason"] = "relation label not found in current form"
        return result

    try:
        locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    result["status"] = "PASSED"
    result["reason"] = "link relation inspected without clicking"
    return result


# ============================================================
# EXECUTE PLAN
# ============================================================

def execute_plan_steps(
    page: Page,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("Planner JSON does not contain a valid steps list.")

    results: list[dict[str, Any]] = []

    for step in steps:
        if not isinstance(step, dict):
            continue

        action = normalize(step.get("action"))

        if not action:
            continue

        # Navigation is executed by run_executor before this function.
        # We record it as completed rather than deferring it.
        if action in {
            "login",
            "open_home",
            "global_search",
            "open_blank_new_document",
        }:
            results.append(
                {
                    "order": step.get("order"),
                    "action": action,
                    "status": "PASSED",
                    "reason": "executed by Navigator before Executor steps",
                }
            )
            continue

        if action == "inspect_form_top_to_bottom":
            try:
                positions = scroll_form_top_to_bottom(page, pause_ms=150)
                results.append(
                    {
                        "order": step.get("order"),
                        "action": action,
                        "status": "PASSED",
                        "scroll_positions": positions,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "order": step.get("order"),
                        "action": action,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )
            continue

        if action == "inspect_tab":
            results.append(inspect_tab(page, step))
            continue

        if action == "inspect_section":
            results.append(inspect_section(page, step))
            continue

        if action == "inspect_field":
            results.append(inspect_field(page, step))
            continue

        if action == "inspect_button":
            results.append(inspect_button(page, step))
            continue

        if action == "inspect_link_relation":
            results.append(inspect_link_relation(page, step))
            continue

        if action_is_blocked(action):
            results.append(
                {
                    "order": step.get("order"),
                    "action": action,
                    "status": "BLOCKED",
                    "reason": "business mutation is blocked in safe executor",
                }
            )
            continue

        results.append(
            {
                "order": step.get("order"),
                "action": action,
                "status": "SKIPPED",
                "reason": "unsupported executor action",
            }
        )

    return results


# ============================================================
# MAIN RUNNER
# ============================================================

def run_executor(
    plan: dict[str, Any],
    headed: bool = False,
    slowmo: int = 0,
) -> dict[str, Any]:
    doctype = clean_doctype_name(
        plan.get("doctype") or plan.get("document_name") or ""
    )

    if not doctype:
        raise ValueError("Planner plan does not contain a DocType.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not headed,
            slow_mo=max(0, slowmo),
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        # 1) Navigator performs real navigation in THIS SAME browser session.
        navigation_result = navigate_plan(page, plan)
        expected_url = page.url

        # 2) If the navigator somehow landed outside the blank form, recover.
        ensure_form_context(
            page,
            doctype,
            expected_url,
        )

        # 3) Execute all planner inspection steps directly.
        execution_results = execute_plan_steps(
            page,
            plan,
        )

        # 4) Final evidence screenshot while still on the form.
        final_screenshot = SCREENSHOT_DIR / (
            f"executor_{re.sub(r'[^a-zA-Z0-9_-]+', '-', doctype)}.png"
        )
        try:
            page.screenshot(
                path=str(final_screenshot),
                full_page=True,
            )
        except Exception:
            final_screenshot = None

        # 5) Summarize real execution statuses.
        passed = sum(
            item.get("status") == "PASSED"
            for item in execution_results
        )
        failed = sum(
            item.get("status") == "FAILED"
            for item in execution_results
        )
        blocked = sum(
            item.get("status") == "BLOCKED"
            for item in execution_results
        )
        skipped = sum(
            item.get("status") == "SKIPPED"
            for item in execution_results
        )

        result = {
            "status": "EXECUTED",
            "doctype": doctype,
            "document_name": doctype,
            "search_name": f"New {doctype}",
            "action": "New",
            "navigation": navigation_result,
            "execution": {
                "mode": "non_mutating_inspection",
                "same_browser_session": True,
                "total_steps": len(execution_results),
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "skipped": skipped,
            },
            "results": execution_results,
            "existing_documents_skipped": True,
            "business_data_mutated": False,
            "save_clicked": False,
            "submit_clicked": False,
            "delete_clicked": False,
            "system_ui_blocked": True,
            "final_screenshot": (
                str(final_screenshot.relative_to(PROJECT_ROOT))
                if final_screenshot
                else ""
            ),
            "current_url": page.url,
        }

        browser.close()

    return result


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="ERPNext AI QA Executor - safe same-session Playwright execution"
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="Planner JSON path; defaults to data/plans/latest_plan.json",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window.",
    )
    parser.add_argument(
        "--slowmo",
        type=int,
        default=0,
        help="Playwright slow_mo milliseconds.",
    )
    args = parser.parse_args()

    try:
        assert_executor_config()
        assert_config()

        plan = load_plan(args.plan)
        result = run_executor(
            plan,
            headed=(True if args.headed else not HEADLESS),
            slowmo=args.slowmo,
        )

        output = EXECUTION_DIR / "latest_execution.json"
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"[EXECUTOR] Output: {output}")
        return 0

    except Exception as exc:
        print(f"[EXECUTOR] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
