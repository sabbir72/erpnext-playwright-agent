from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.sync_api import (
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# ============================================================
# PATHS / ENV
# ============================================================

FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = FILE_PATH.parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
PLAN_DIR = PROJECT_ROOT / "data" / "plans"

load_dotenv(ENV_PATH)

BASE_URL = (
    os.getenv("BASE_URL")
    or os.getenv("ERPNext_BASE_URL")
    or os.getenv("SITE_URL")
    or ""
).rstrip("/")
ERP_USERNAME = (
    os.getenv("ERP_USERNAME")
    or os.getenv("ERP_USERNAME01")
    or os.getenv("USERNAME")
    or ""
)
ERP_PASSWORD = (
    os.getenv("ERP_PASSWORD")
    or os.getenv("ERP_PASSWORD01")
    or os.getenv("PASSWORD")
    or ""
)
DEFAULT_TIMEOUT = int(os.getenv("PLAYWRIGHT_TIMEOUT", "15000"))

SYSTEM_UI_KEYWORDS = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
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


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_doctype_name(value: Any) -> str:
    return re.sub(r"^New\s+", "", clean_text(value), flags=re.IGNORECASE).strip()


def build_search_name(doctype: str) -> str:
    doctype = clean_doctype_name(doctype)
    return f"New {doctype}" if doctype else ""


def is_system_ui(value: Any) -> bool:
    text = clean_text(value).lower()
    return bool(text) and (
        text in SYSTEM_UI_KEYWORDS or "notification" in text or text == "bell"
    )


def load_plan(plan_path: Optional[str] = None) -> dict[str, Any]:
    path = Path(plan_path) if plan_path else PLAN_DIR / "latest_plan.json"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Plan not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid plan JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Plan root must be a JSON object.")
    return data


def assert_config() -> None:
    missing = [
        name
        for name, value in (
            ("BASE_URL", BASE_URL),
            ("ERP_USERNAME", ERP_USERNAME),
            ("ERP_PASSWORD", ERP_PASSWORD),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required .env configuration: " + ", ".join(missing))


def assert_safe_target(doctype: str) -> None:
    doctype = clean_doctype_name(doctype)
    if not doctype:
        raise ValueError("DocType is empty.")
    if is_system_ui(doctype):
        raise ValueError(f"Blocked system UI target: {doctype}")


def current_route(page: Page) -> str:
    return urlparse(page.url).path.rstrip("/")


def is_login_page(page: Page) -> bool:
    return "/login" in current_route(page).lower() or "login" in page.url.lower()


def first_visible(locators: list[Locator]) -> Optional[Locator]:
    for locator in locators:
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(count):
            try:
                candidate = locator.nth(index)
                if candidate.is_visible():
                    return candidate
            except Exception:
                continue
    return None


def login(page: Page) -> None:
    if not is_login_page(page):
        return

    user_input = first_visible(
        [
            page.get_by_label("Username"),
            page.get_by_label("Email"),
            page.get_by_placeholder(re.compile("username|email", re.I)),
            page.locator('input[type="text"]'),
            page.locator('input[type="email"]'),
        ]
    )
    password_input = first_visible(
        [
            page.get_by_label("Password"),
            page.get_by_placeholder(re.compile("password", re.I)),
            page.locator('input[type="password"]'),
        ]
    )
    if user_input is None or password_input is None:
        raise RuntimeError("Could not find ERPNext login fields.")

    user_input.fill(ERP_USERNAME)
    password_input.fill(ERP_PASSWORD)

    login_button = first_visible(
        [
            page.get_by_role("button", name=re.compile(r"^log\s*in$", re.I)),
            page.get_by_role("button", name=re.compile(r"sign\s*in", re.I)),
            page.get_by_text(re.compile(r"^log\s*in$", re.I), exact=True),
            page.locator('button[type="submit"]'),
        ]
    )
    if login_button is None:
        raise RuntimeError("Could not find ERPNext Login button.")

    login_button.click()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeoutError:
        pass


def open_home(page: Page) -> None:
    target = f"{BASE_URL}/app/home"
    if not page.url.startswith(target):
        page.goto(target, wait_until="domcontentloaded")
    if is_login_page(page):
        login(page)
    try:
        page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeoutError:
        pass


def get_global_search(page: Page) -> Optional[Locator]:
    candidates = [
        page.locator('input[placeholder*="Search" i]'),
        page.locator('input[aria-label*="Search" i]'),
        page.locator('input[type="search"]'),
        page.locator('input[data-gramm="false"]'),
    ]
    return first_visible(candidates)


def search_global(page: Page, search_name: str) -> None:
    search_box = get_global_search(page)
    if search_box is None:
        raise RuntimeError("ERPNext Global Search input not found.")
    search_box.fill(clean_text(search_name))
    page.wait_for_timeout(500)


def get_search_results(page: Page) -> list[Locator]:
    results: list[Locator] = []
    for selector in [
        '[role="option"]',
        ".awesomplete li",
        ".search-result",
        ".search-dialog .list-item",
        ".dropdown-menu .dropdown-item",
    ]:
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(count):
            try:
                item = locator.nth(index)
                if item.is_visible():
                    results.append(item)
            except Exception:
                continue
    return results


def result_text(locator: Locator) -> str:
    try:
        return clean_text(locator.inner_text())
    except Exception:
        return ""


def result_matches_doctype(locator: Locator, doctype: str) -> bool:
    text = result_text(locator)
    target = clean_doctype_name(doctype)
    if not text:
        return False
    return bool(re.fullmatch(rf"(?:New\s+)?{re.escape(target)}", text, flags=re.I))


def click_search_result(page: Page, doctype: str) -> bool:
    for item in get_search_results(page):
        text = result_text(item)
        if is_system_ui(text):
            continue
        if result_matches_doctype(item, doctype):
            try:
                item.click()
                return True
            except Exception:
                continue

    for locator in [
        page.get_by_text(build_search_name(doctype), exact=True),
        page.get_by_text(clean_doctype_name(doctype), exact=True),
    ]:
        try:
            if locator.is_visible():
                locator.click()
                return True
        except Exception:
            continue
    return False


def has_new_form_markers(page: Page, doctype: str) -> bool:
    name = clean_doctype_name(doctype)
    markers = [
        page.get_by_text(re.compile(rf"^New\s+{re.escape(name)}$", re.I)),
        page.get_by_text(name, exact=True),
        page.locator(".form-page"),
        page.locator(".form-layout"),
    ]
    return any(
        (lambda l: l.is_visible())(x) for x in markers if _safe_locator_visible(x)
    )


def _safe_locator_visible(locator: Locator) -> bool:
    try:
        return locator.is_visible()
    except Exception:
        return False


def wait_for_blank_new_form(page: Page, doctype: str) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(500)
    if not has_new_form_markers(page, doctype):
        try:
            page.locator(".form-page, .form-layout").first.wait_for(
                state="visible", timeout=DEFAULT_TIMEOUT
            )
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                f"Blank New form for '{clean_doctype_name(doctype)}' was not verified."
            ) from exc


def open_new_doctype(page: Page, doctype: str) -> None:
    doctype = clean_doctype_name(doctype)
    assert_safe_target(doctype)
    open_home(page)
    search_global(page, build_search_name(doctype))
    if not click_search_result(page, doctype):
        raise RuntimeError(
            f'Could not find exact Global Search result for "{build_search_name(doctype)}".'
        )
    wait_for_blank_new_form(page, doctype)


def navigate_tabs(page: Page, plan: dict[str, Any]) -> list[str]:
    visited: list[str] = []
    planned_tabs = plan.get("tabs", [])
    if not isinstance(planned_tabs, list):
        return visited

    for item in planned_tabs:
        if not isinstance(item, dict):
            continue
        name = clean_text(
            item.get("tab") or item.get("name") or item.get("label") or ""
        )
        if not name or is_system_ui(name):
            continue

        clicked = False
        role_tab = page.get_by_role("tab", name=name, exact=True)
        if _safe_locator_visible(role_tab):
            try:
                role_tab.click()
                clicked = True
            except Exception:
                pass

        if not clicked:
            fallback = page.get_by_text(name, exact=True)
            if _safe_locator_visible(fallback):
                try:
                    fallback.click()
                    clicked = True
                except Exception:
                    pass

        if clicked:
            visited.append(name)
            page.wait_for_timeout(250)

    return visited


def scroll_form_top_to_bottom(page: Page, pause_ms: int = 250) -> int:
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(pause_ms)
    positions = 1
    previous_y = -1

    while True:
        result = page.evaluate("""
            () => {
                const before = window.scrollY;
                const viewport = window.innerHeight || 800;
                const maxY = Math.max(0, document.documentElement.scrollHeight - viewport);
                const nextY = Math.min(maxY, before + Math.max(300, viewport * 0.85));
                window.scrollTo(0, nextY);
                return {before, after: window.scrollY, maxY};
            }
        """)
        current_y = int(result.get("after", 0))
        max_y = int(result.get("maxY", 0))
        if current_y == previous_y:
            break
        previous_y = current_y
        positions += 1
        page.wait_for_timeout(pause_ms)
        if current_y >= max_y:
            break

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(pause_ms)
    return positions


def navigate_plan(page: Page, plan: dict[str, Any]) -> dict[str, Any]:
    doctype = clean_doctype_name(plan.get("doctype") or plan.get("document_name") or "")
    if not doctype:
        raise ValueError("Planner plan does not contain a DocType.")
    assert_safe_target(doctype)

    expected_search = build_search_name(doctype)
    actual_search = clean_text(plan.get("search_name"))
    if actual_search and actual_search.casefold() != expected_search.casefold():
        raise ValueError(
            f'Planner search_name mismatch: expected "{expected_search}", got "{actual_search}".'
        )

    open_new_doctype(page, doctype)
    tabs_visited = navigate_tabs(page, plan)
    scroll_positions = scroll_form_top_to_bottom(page)

    return {
        "status": "NAVIGATED",
        "doctype": doctype,
        "document_name": doctype,
        "search_name": expected_search,
        "action": "New",
        "current_url": page.url,
        "tabs_visited": tabs_visited,
        "scroll_positions": scroll_positions,
        "existing_documents_skipped": True,
        "business_data_mutated": False,
        "system_ui_blocked": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ERPNext AI QA Navigator - navigation only."
    )
    parser.add_argument(
        "--plan", default=str(PLAN_DIR / "latest_plan.json"), help="Planner JSON path."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Run browser in headed mode."
    )
    parser.add_argument(
        "--slowmo", type=int, default=0, help="Playwright slow_mo in milliseconds."
    )
    args = parser.parse_args()

    try:
        assert_config()
        plan = load_plan(args.plan)
        doctype = clean_doctype_name(
            plan.get("doctype") or plan.get("document_name") or ""
        )
        assert_safe_target(doctype)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=not args.headed, slow_mo=max(0, args.slowmo)
            )
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT)
            result = navigate_plan(page, plan)
            print("=" * 60)
            print("NAVIGATOR RESULT")
            print("=" * 60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            browser.close()
        return 0
    except Exception as exc:
        print(f"[NAVIGATOR] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
