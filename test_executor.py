import argparse
import json
import os
import re
import time
from pathlib import Path

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

# Wait configuration
ACTION_WAIT = float(os.getenv("ACTION_WAIT", "1.0"))

RETRY_COUNT = int(os.getenv("RETRY_COUNT", "3"))

RETRY_WAIT = float(os.getenv("RETRY_WAIT", "1.5"))

PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT", "30000"))

# Files
TEST_CASE_FILE = BASE_DIR / "data" / "test_cases" / "latest_test_cases.json"

REPORT_DIR = BASE_DIR / "data" / "execution_reports"

SCREENSHOT_DIR = BASE_DIR / "data" / "execution_screenshots"

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SCREENSHOT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOG
# ============================================================


def log(message):
    print(
        f"[EXECUTOR] {message}",
        flush=True,
    )


def tc_log(tc_id, message):
    print(
        f"[{tc_id}] {message}",
        flush=True,
    )


# ============================================================
# HELPERS
# ============================================================


def clean(value):

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def slugify(value):

    value = clean(value).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value,
    )

    return value.strip("-") or "unknown"


def wait_after_action():

    time.sleep(ACTION_WAIT)


# ============================================================
# LOAD TEST CASES
# ============================================================


def load_test_cases():

    if not TEST_CASE_FILE.exists():

        raise FileNotFoundError(f"""
Test case file not found:

{TEST_CASE_FILE}

Run:

python test_case_generator.py
""")

    try:

        data = json.loads(TEST_CASE_FILE.read_text(encoding="utf-8"))

    except json.JSONDecodeError as exc:

        raise RuntimeError(f"Invalid test case JSON: {exc}")

    cases = data.get("test_cases", [])

    if not isinstance(
        cases,
        list,
    ):

        raise RuntimeError("test_cases must be a list.")

    return data, cases


# ============================================================
# LOGIN
# ============================================================


def find_visible_locator(
    page,
    selectors,
):

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

        except Exception:

            continue

        for index in range(count):

            item = locator.nth(index)

            try:

                if item.is_visible():

                    return item

            except Exception:

                continue

    return None


def login(page):

    log("Checking login state...")

    if "/app" in page.url:

        log("Already logged in.")

        return True

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

        raise RuntimeError("Username field not found.")

    password = find_visible_locator(
        page,
        [
            "input[name='pwd']",
            "input[name='password']",
            "input[type='password']",
        ],
    )

    if not password:

        raise RuntimeError("Password field not found.")

    username.fill(USERNAME)

    wait_after_action()

    password.fill(PASSWORD)

    wait_after_action()

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

    for index in range(count):

        button = buttons.nth(index)

        try:

            if not button.is_visible():

                continue

            text = clean(
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

        page.wait_for_timeout(3000)

    if "/app" not in page.url:

        raise RuntimeError("Login failed.")

    log(f"LOGIN SUCCESS: {page.url}")

    return True


# ============================================================
# OPEN ERP
# ============================================================


def open_erp(page):

    log(f"Opening ERP: {ERP_URL}")

    page.goto(
        ERP_URL,
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT,
    )

    page.wait_for_timeout(2000)

    login(page)


# ============================================================
# SAFE WAIT
# ============================================================


def safe_wait():

    time.sleep(ACTION_WAIT)


# ============================================================
# NOTIFICATION DETECTION
# ============================================================


def is_notification_element(element):

    try:

        text = clean(
            " ".join(
                [
                    element.inner_text() or "",
                    element.get_attribute("aria-label") or "",
                    element.get_attribute("title") or "",
                    element.get_attribute("class") or "",
                ]
            )
        ).lower()

    except Exception:

        return False

    notification_words = [
        "notification",
        "notifications",
        "notify",
        "bell",
        "alert",
    ]

    return any(word in text for word in notification_words)


def detect_notification(page):
    """
    Notification icon থাকলে শুধু detect করবে।
    কখনো click করবে না।
    """

    selectors = [
        "[aria-label*='notification' i]",
        "[title*='notification' i]",
        "[class*='notification' i]",
        "[class*='navbar-notification' i]",
        ".notifications-icon",
        ".navbar-notification",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = min(
                locator.count(),
                20,
            )

        except Exception:

            continue

        for index in range(count):

            element = locator.nth(index)

            try:

                if element.is_visible():

                    log("Notification detected " "(NOT CLICKED)")

                    return True

            except Exception:

                continue

    # Generic fallback
    try:

        elements = page.locator("""
            button,
            a,
            [role='button']
            """)

        count = min(
            elements.count(),
            300,
        )

        for index in range(count):

            element = elements.nth(index)

            try:

                if not element.is_visible():

                    continue

                if is_notification_element(element):

                    log("Notification detected " "(NOT CLICKED)")

                    return True

            except Exception:

                continue

    except Exception:

        pass

    return False


# ============================================================
# ELEMENT SEARCH
# ============================================================


def find_by_text(
    page,
    text,
):

    text = clean(text)

    if not text:

        return None

    # Exact text
    selectors = [
        f"text={text}",
        f"button:has-text('{text}')",
        f"a:has-text('{text}')",
        f"[role='button']:has-text('{text}')",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = min(
                locator.count(),
                100,
            )

        except Exception:

            continue

        for index in range(count):

            element = locator.nth(index)

            try:

                if element.is_visible():

                    return element

            except Exception:

                continue

    return None


def find_field(
    page,
    fieldname,
    label=None,
):

    fieldname = clean(fieldname)

    label = clean(label)

    selectors = []

    if fieldname:

        selectors.extend(
            [
                f"[data-fieldname='{fieldname}'] input",
                f"[data-fieldname='{fieldname}'] textarea",
                f"[data-fieldname='{fieldname}'] select",
                f"[data-fieldname='{fieldname}'] [contenteditable='true']",
                f"[data-fieldname='{fieldname}']",
            ]
        )

    if label:

        selectors.extend(
            [
                f"input[aria-label='{label}']",
                f"input[placeholder='{label}']",
                f"textarea[aria-label='{label}']",
            ]
        )

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = min(
                locator.count(),
                50,
            )

        except Exception:

            continue

        for index in range(count):

            element = locator.nth(index)

            try:

                if element.is_visible():

                    return element

            except Exception:

                continue

    return None


# ============================================================
# RETRY ELEMENT
# ============================================================


def retry_find(
    finder,
    description,
):

    for attempt in range(
        1,
        RETRY_COUNT + 1,
    ):

        log(f"Searching: {description} " f"(attempt {attempt}/{RETRY_COUNT})")

        try:

            element = finder()

            if element:

                return element

        except Exception:

            pass

        time.sleep(RETRY_WAIT)

    return None


# ============================================================
# CLICK ELEMENT
# ============================================================


def safe_click(
    page,
    element,
    description,
):

    if not element:

        raise RuntimeError(f"Element not found: {description}")

    # --------------------------------------------------------
    # NEVER CLICK NOTIFICATION
    # --------------------------------------------------------

    if is_notification_element(element):

        log(f"SKIP CLICK: notification " f"element detected -> {description}")

        return "notification_skipped"

    try:

        element.scroll_into_view_if_needed()

    except Exception:

        pass

    safe_wait()

    element.click(timeout=10000)

    safe_wait()

    return "clicked"


# ============================================================
# FIELD VALUE
# ============================================================


def fill_field(
    page,
    field,
    value,
):

    fieldname = clean(field.get("fieldname"))

    label = clean(field.get("label"))

    fieldtype = clean(field.get("fieldtype")).lower()

    element = retry_find(
        lambda: find_field(
            page,
            fieldname,
            label,
        ),
        f"field {label or fieldname}",
    )

    if not element:

        raise RuntimeError(f"Field not found: " f"{label or fieldname}")

    # Check
    if fieldtype in (
        "check",
        "checkbox",
    ):

        desired = str(value).lower() in (
            "true",
            "1",
            "yes",
            "checked",
        )

        current = element.is_checked()

        if current != desired:

            element.check(timeout=10000)

        safe_wait()

        return

    # Select
    if fieldtype == "select":

        element.select_option(str(value))

        safe_wait()

        return

    # Normal input
    element.fill(str(value))

    safe_wait()


# ============================================================
# SELECT OPTION
# ============================================================


def select_option(
    page,
    fieldname,
    label,
    option,
):

    option = clean(option)

    if not option:

        raise RuntimeError("Option is empty.")

    element = retry_find(
        lambda: find_field(
            page,
            fieldname,
            label,
        ),
        f"field {label or fieldname}",
    )

    if not element:

        raise RuntimeError(f"Field not found: " f"{label or fieldname}")

    # Native select
    try:

        tag = element.evaluate("(el) => el.tagName.toLowerCase()")

    except Exception:

        tag = ""

    if tag == "select":

        element.select_option(label=option)

        safe_wait()

        return

    # Click field
    safe_click(
        page,
        element,
        label or fieldname,
    )

    # Search dropdown option
    option_element = retry_find(
        lambda: find_by_text(
            page,
            option,
        ),
        f"option {option}",
    )

    if not option_element:

        raise RuntimeError(f"Option not found: {option}")

    safe_click(
        page,
        option_element,
        option,
    )


# ============================================================
# ACTION EXECUTION
# ============================================================


def execute_action(
    page,
    tc,
    step,
    step_index,
    total_steps,
):

    tc_id = tc.get("id", "UNKNOWN")

    step_text = clean(step)

    tc_log(tc_id, f"Action {step_index}/{total_steps}: " f"{step_text}")

    lower = step_text.lower()

    # --------------------------------------------------------
    # Notification
    # --------------------------------------------------------

    detect_notification(page)

    if "notification" in lower:

        log("Notification-related action " "detected -> NEVER CLICK")

        return {
            "status": "skipped",
            "reason": "Notification must not be clicked.",
        }

    # --------------------------------------------------------
    # OPEN
    # --------------------------------------------------------

    if lower.startswith("open "):

        target = clean(step_text[5:])

        if target.lower().startswith("new "):

            target = target[4:]

        # Existing URL?
        if target.startswith("http://") or target.startswith("https://"):

            page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT,
            )

            safe_wait()

            return {"status": "passed"}

        # Search visible text
        element = retry_find(
            lambda: find_by_text(
                page,
                target,
            ),
            f"Open {target}",
        )

        if element:

            safe_click(
                page,
                element,
                target,
            )

            return {"status": "passed"}

        # ERPNext route fallback
        route = slugify(target)

        url = f"{ERP_URL}/app/{route}"

        log(f"Route fallback: {url}")

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        safe_wait()

        return {"status": "passed"}

    # --------------------------------------------------------
    # CLICK
    # --------------------------------------------------------

    if lower.startswith("click ") or "click " in lower:

        match = re.search(
            r"click\s+['\"]?(.+?)['\"]?$",
            step_text,
            re.I,
        )

        target = (
            match.group(1)
            if match
            else step_text.replace(
                "click",
                "",
                1,
            )
        )

        target = clean(target).strip("'\"")

        if "notification" in target.lower() or "bell" in target.lower():

            log(f"Notification click blocked: " f"{target}")

            return {
                "status": "skipped",
                "reason": "Notification click blocked.",
            }

        element = retry_find(
            lambda: find_by_text(
                page,
                target,
            ),
            f"click {target}",
        )

        if not element:

            raise RuntimeError(f"Click target not found: " f"{target}")

        result = safe_click(
            page,
            element,
            target,
        )

        return {"status": ("skipped" if result == "notification_skipped" else "passed")}

    # --------------------------------------------------------
    # LOCATE
    # --------------------------------------------------------

    if lower.startswith("locate "):

        target = clean(step_text[7:])

        element = retry_find(
            lambda: find_by_text(
                page,
                target,
            ),
            f"locate {target}",
        )

        if not element:

            raise RuntimeError(f"Element not found: " f"{target}")

        return {"status": "passed"}

    # --------------------------------------------------------
    # SELECT
    # --------------------------------------------------------

    if lower.startswith("select ") and " from " not in lower:

        # Example:
        # Select 'Monthly'
        match = re.search(
            r"select\s+['\"](.+?)['\"]",
            step_text,
            re.I,
        )

        if match:

            option = clean(match.group(1))

            # Try currently open dropdown
            element = retry_find(
                lambda: find_by_text(
                    page,
                    option,
                ),
                f"select {option}",
            )

            if not element:

                raise RuntimeError(f"Option not found: " f"{option}")

            safe_click(
                page,
                element,
                option,
            )

            return {"status": "passed"}

    # --------------------------------------------------------
    # ENTER / TYPE
    # --------------------------------------------------------

    if (
        lower.startswith("enter ")
        or lower.startswith("type ")
        or lower.startswith("fill ")
    ):

        # Generic fallback
        match = re.search(
            r"(?:enter|type|fill)\s+['\"](.+?)['\"]",
            step_text,
            re.I,
        )

        if match:

            value = match.group(1)

            fields = tc.get("fieldname")

            label = tc.get("field_label")

            if fields:

                field = {
                    "fieldname": fields,
                    "label": label,
                    "fieldtype": tc.get(
                        "fieldtype",
                        "Data",
                    ),
                }

                fill_field(
                    page,
                    field,
                    value,
                )

                return {"status": "passed"}

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if lower == "save" or "save the document" in lower or "attempt to save" in lower:

        element = retry_find(
            lambda: find_by_text(
                page,
                "Save",
            ),
            "Save button",
        )

        if not element:

            raise RuntimeError("Save button not found.")

        safe_click(
            page,
            element,
            "Save",
        )

        return {"status": "passed"}

    # --------------------------------------------------------
    # SUBMIT
    # --------------------------------------------------------

    if lower == "submit" or "submit the document" in lower:

        element = retry_find(
            lambda: find_by_text(
                page,
                "Submit",
            ),
            "Submit button",
        )

        if not element:

            raise RuntimeError("Submit button not found.")

        safe_click(
            page,
            element,
            "Submit",
        )

        return {"status": "passed"}

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    log(f"Generic action: {step_text}")

    # Give UI time even when action is
    # not directly executable yet.
    safe_wait()

    return {
        "status": "skipped",
        "reason": "No direct executor mapped for this action.",
    }


# ============================================================
# EXECUTE SINGLE TC
# ============================================================


def execute_test_case(
    page,
    tc,
):

    tc_id = clean(tc.get("id"))

    title = clean(tc.get("title"))

    doctype = clean(tc.get("doctype"))

    steps = tc.get("steps", [])

    if not isinstance(
        steps,
        list,
    ):

        steps = []

    tc_log(tc_id, "========================================")

    tc_log(tc_id, f"START: {title}")

    tc_log(tc_id, f"DocType: {doctype}")

    tc_log(tc_id, f"Steps: {len(steps)}")

    result = {
        "id": tc_id,
        "doctype": doctype,
        "title": title,
        "category": tc.get("category"),
        "priority": tc.get("priority"),
        "status": "FAIL",
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "actions": [],
        "error": None,
    }

    if not steps:

        result["status"] = "SKIP"

        result["error"] = "No steps available."

        tc_log(tc_id, "RESULT: SKIP")

        return result

    for index, step in enumerate(
        steps,
        start=1,
    ):

        action_result = {
            "step": index,
            "description": clean(step),
            "status": "FAIL",
        }

        try:

            output = execute_action(
                page,
                tc,
                step,
                index,
                len(steps),
            )

            action_result.update(output)

            status = output.get("status")

            if status == "passed":

                tc_log(tc_id, f"✓ PASS ACTION {index}")

            elif status == "skipped":

                tc_log(tc_id, f"⚠ SKIPPED ACTION {index}")

            else:

                tc_log(tc_id, f"⚠ ACTION {index}: " f"{status}")

        except Exception as exc:

            action_result["status"] = "failed"

            action_result["error"] = str(exc)

            result["error"] = str(exc)

            tc_log(tc_id, f"✗ FAIL ACTION {index}: " f"{exc}")

            # Screenshot
            try:

                screenshot = SCREENSHOT_DIR / f"{tc_id}_action_{index}.png"

                page.screenshot(
                    path=str(screenshot),
                    full_page=True,
                )

                action_result["screenshot"] = str(screenshot)

            except Exception:

                pass

            result["actions"].append(action_result)

            # TC fail
            result["status"] = "FAIL"

            result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            tc_log(tc_id, "RESULT: FAIL")

            tc_log(tc_id, "========================================")

            return result

        result["actions"].append(action_result)

    # If all executable actions did not fail
    result["status"] = "PASS"

    result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    tc_log(tc_id, "RESULT: PASS")

    tc_log(tc_id, "========================================")

    return result


# ============================================================
# FILTER TEST CASES
# ============================================================


def select_test_cases(
    cases,
    tc_ids=None,
    run_all=False,
):

    if run_all:

        return cases

    if not tc_ids:

        raise RuntimeError("Use either --all or --tc TC-0001.")

    requested = {clean(tc_id).upper() for tc_id in tc_ids}

    selected = []

    for tc in cases:

        tc_id = clean(tc.get("id")).upper()

        if tc_id in requested:

            selected.append(tc)

    missing = requested - {clean(tc.get("id")).upper() for tc in selected}

    if missing:

        raise RuntimeError("TC not found: " + ", ".join(sorted(missing)))

    return selected


# ============================================================
# SAVE REPORT
# ============================================================


def save_report(
    source_data,
    selected_cases,
    results,
    mode,
):

    passed = sum(1 for result in results if result["status"] == "PASS")

    failed = sum(1 for result in results if result["status"] == "FAIL")

    skipped = sum(1 for result in results if result["status"] == "SKIP")

    report = {
        "knowledge_type": "erpnext_test_execution_report",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_command": source_data.get(
            "source_command",
            "",
        ),
        "target": source_data.get(
            "target",
            "",
        ),
        "execution_mode": mode,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }

    filename = f"execution_" f"{time.strftime('%Y%m%d_%H%M%S')}.json"

    path = REPORT_DIR / filename

    path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Latest report
    latest = REPORT_DIR / "latest_execution_report.json"

    latest.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path, report


# ============================================================
# PRINT SUMMARY
# ============================================================


def print_summary(report):

    print()
    print("========================================")

    print("EXECUTION SUMMARY")

    print("========================================")

    print(f"Total   : {report['total']}")

    print(f"PASS    : {report['passed']}")

    print(f"FAIL    : {report['failed']}")

    print(f"SKIPPED : {report['skipped']}")

    print("========================================")


# ============================================================
# MAIN EXECUTION
# ============================================================


def run(
    selected_cases,
    mode,
    source_data,
):

    log("========================================")

    log("ERPNext TEST EXECUTOR")

    log("========================================")

    log(f"Mode: {mode}")

    log(f"Test cases selected: " f"{len(selected_cases)}")

    results = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS,
            slow_mo=100,
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 900,
            }
        )

        page = context.new_page()

        page.set_default_timeout(PAGE_TIMEOUT)

        try:

            open_erp(page)

            for index, tc in enumerate(
                selected_cases,
                start=1,
            ):

                tc_id = clean(tc.get("id"))

                log("----------------------------------------")

                log(f"RUNNING TC " f"{index}/{len(selected_cases)} " f"-> {tc_id}")

                log(f"Title: " f"{clean(tc.get('title'))}")

                try:

                    result = execute_test_case(
                        page,
                        tc,
                    )

                except Exception as exc:

                    result = {
                        "id": tc_id,
                        "doctype": tc.get("doctype"),
                        "title": tc.get("title"),
                        "status": "FAIL",
                        "error": str(exc),
                    }

                    log(f"{tc_id} FATAL TC ERROR: " f"{exc}")

                results.append(result)

                # --------------------------------------------
                # Recovery for next TC
                # --------------------------------------------

                try:

                    page.goto(
                        f"{ERP_URL}/app/home",
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT,
                    )

                    page.wait_for_timeout(1500)

                except Exception as recovery_error:

                    log(f"Recovery warning: " f"{recovery_error}")

            report_path, report = save_report(
                source_data,
                selected_cases,
                results,
                mode,
            )

        finally:

            context.close()

            browser.close()

    print_summary(report)

    log(f"Report saved: {report_path}")

    return report


# ============================================================
# SHOW TEST CASES
# ============================================================


def show_cases(cases):

    print()
    print("========================================")

    print("AVAILABLE TEST CASES")

    print("========================================")

    for tc in cases:

        print(
            f"{clean(tc.get('id'))} | "
            f"{clean(tc.get('doctype'))} | "
            f"{clean(tc.get('title'))}"
        )

    print("========================================")

    print(f"Total: {len(cases)}")


# ============================================================
# ARGUMENTS
# ============================================================


def parse_args():

    parser = argparse.ArgumentParser(
        description=("ERPNext Playwright " "Test Executor")
    )

    group = parser.add_mutually_exclusive_group(required=False)

    group.add_argument(
        "--all",
        action="store_true",
        help="Execute all test cases.",
    )

    group.add_argument(
        "--tc",
        nargs="+",
        help=("Execute specific test case IDs. " "Example: --tc TC-0001 TC-0005"),
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Show available test cases.",
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================


def main():

    args = parse_args()

    source_data, cases = load_test_cases()

    # --------------------------------------------------------
    # SHOW
    # --------------------------------------------------------

    if args.show:

        show_cases(cases)

        # If only --show, stop.
        if not args.all and not args.tc:

            return

    # --------------------------------------------------------
    # Default
    # --------------------------------------------------------

    if not args.all and not args.tc:

        print("""
No execution mode selected.

Use:

python test_executor.py --all

or:

python test_executor.py --tc TC-0001

or:

python test_executor.py --tc TC-0001 TC-0005
""")

        return

    # --------------------------------------------------------
    # Select
    # --------------------------------------------------------

    selected = select_test_cases(
        cases,
        tc_ids=args.tc,
        run_all=args.all,
    )

    if args.all:

        mode = "ALL"

    else:

        mode = "SPECIFIC"

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    run(
        selected,
        mode,
        source_data,
    )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":

    main()
