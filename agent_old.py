
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# BASE / ENV
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


ERPNEXT_URL = os.getenv(
    "ERPNEXT_URL",
    "https://stage2-salma.altersense.net",
).rstrip("/")


ERPNEXT_USER = os.getenv(
    "ERPNEXT_USER",
    "",
)


ERPNEXT_PASSWORD = os.getenv(
    "ERPNEXT_PASSWORD",
    "",
)


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
).rstrip("/")


MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5-coder:7b",
)


HEADLESS = (
    os.getenv(
        "HEADLESS",
        "false",
    ).lower()
    == "true"
)


SLOW_MO = int(
    os.getenv(
        "SLOW_MO",
        "20",
    )
)


MAX_STEPS = int(
    os.getenv(
        "MAX_STEPS",
        "40",
    )
)


AI_TIMEOUT = int(
    os.getenv(
        "AI_TIMEOUT",
        "120",
    )
)


# ============================================================
# ARTIFACTS
# ============================================================

ARTIFACTS = BASE_DIR / "artifacts"

SCREENSHOTS = ARTIFACTS / "screenshots"

ARTIFACTS.mkdir(
    exist_ok=True
)

SCREENSHOTS.mkdir(
    exist_ok=True
)

LOG_FILE = (
    ARTIFACTS
    / "execution.log"
)

REPORT_FILE = (
    ARTIFACTS
    / "test-results.json"
)


# ============================================================
# LOG
# ============================================================

def log(message):

    line = (
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
        f"{message}"
    )

    print(
        line,
        flush=True,
    )

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as f:

        f.write(
            line + "\n"
        )


# ============================================================
# URL
# ============================================================

def absolute_url(url):

    if not url:
        return ERPNEXT_URL

    url = str(url).strip()

    if url.startswith(
        "http://"
    ) or url.startswith(
        "https://"
    ):

        return url

    return urljoin(
        ERPNEXT_URL + "/",
        url.lstrip("/"),
    )


# ============================================================
# VISIBILITY
# ============================================================

def is_visible_enabled(element):

    try:

        return (
            element.is_visible()
            and element.is_enabled()
        )

    except Exception:

        return False


def first_visible(locator):

    try:

        count = locator.count()

        for i in range(count):

            element = locator.nth(i)

            if is_visible_enabled(
                element
            ):

                return element

    except Exception:

        pass

    return None


# ============================================================
# LOGIN STATE
# ============================================================

def is_logged_in(page):

    try:

        current_url = page.url.lower()

        if "/app" in current_url:

            return True

    except Exception:

        pass

    try:

        body = page.locator(
            "body"
        ).inner_text(
            timeout=2000
        ).lower()

        login_words = [
            "forgot password",
            "login to",
            "sign in",
        ]

        if any(
            word in body
            for word in login_words
        ):

            return False

        desk_words = [
            "home",
            "accounting",
            "inventory",
            "settings",
            "crm",
        ]

        return any(
            word in body
            for word in desk_words
        )

    except Exception:

        return False


# ============================================================
# LOGIN ELEMENTS
# ============================================================

def find_username(page):

    selectors = [

        "input[name='usr']",

        "input[autocomplete='username']",

        "input[name='login']",

        "input[type='email']",

        "input[name='email']",

    ]

    for selector in selectors:

        try:

            element = first_visible(
                page.locator(selector)
            )

            if element:

                return element

        except Exception:

            continue

    return None


def find_password(page):

    selectors = [

        "input[name='pwd']",

        "input[name='password']",

        "input[type='password']",

        "input[autocomplete='current-password']",

    ]

    for selector in selectors:

        try:

            element = first_visible(
                page.locator(selector)
            )

            if element:

                return element

        except Exception:

            continue

    return None


def find_login_button(page):

    selectors = [

        "button",

        "input[type='submit']",

        "[role='button']",

    ]

    for selector in selectors:

        try:

            locator = page.locator(
                selector
            )

            count = locator.count()

            for i in range(count):

                element = locator.nth(i)

                if not is_visible_enabled(
                    element
                ):

                    continue

                text_parts = [

                    element.inner_text() or "",

                    element.get_attribute(
                        "value"
                    ) or "",

                    element.get_attribute(
                        "aria-label"
                    ) or "",

                    element.get_attribute(
                        "title"
                    ) or "",

                ]

                text = " ".join(
                    text_parts
                ).strip().lower()

                if (
                    text == "login"
                    or "login" in text
                    or "log in" in text
                    or "sign in" in text
                ):

                    return element

        except Exception:

            continue

    return None


# ============================================================
# LOGIN
# ============================================================

def perform_login(page):

    if is_logged_in(page):

        log(
            "LOGIN: Already logged in."
        )

        return "LOGIN_ALREADY_ACTIVE"

    if not ERPNEXT_USER:

        raise RuntimeError(
            "ERPNEXT_USER is missing from .env"
        )

    if not ERPNEXT_PASSWORD:

        raise RuntimeError(
            "ERPNEXT_PASSWORD is missing from .env"
        )

    log(
        "Finding visible username field..."
    )

    username = find_username(
        page
    )

    if not username:

        raise RuntimeError(
            "Username field not found."
        )

    log(
        "Finding visible password field..."
    )

    password = find_password(
        page
    )

    if not password:

        raise RuntimeError(
            "Password field not found."
        )

    username.fill(
        ERPNEXT_USER,
        timeout=10000,
    )

    password.fill(
        ERPNEXT_PASSWORD,
        timeout=10000,
    )

    log(
        "Credentials filled locally."
    )

    login_button = find_login_button(
        page
    )

    if not login_button:

        raise RuntimeError(
            "Login button not found."
        )

    log(
        "Clicking visible Login button..."
    )

    login_button.click(
        timeout=10000
    )

    try:

        page.wait_for_url(
            re.compile(
                r".*/app.*"
            ),
            timeout=20000,
        )

    except PlaywrightTimeoutError:

        pass

    page.wait_for_timeout(
        1000
    )

    if not is_logged_in(page):

        raise RuntimeError(
            "Login failed. "
            f"Current URL: {page.url}"
        )

    log(
        "Login completed. "
        f"Current URL: {page.url}"
    )

    return "LOGIN_SUCCESS"


# ============================================================
# PAGE OBSERVATION
# ============================================================

def page_state(page):

    result = {

        "url": page.url,

        "title": "",

        "logged_in": is_logged_in(
            page
        ),

        "body_text": "",

        "interactive_elements": [],

    }

    try:

        result["title"] = page.title()

    except Exception:

        pass

    try:

        result["body_text"] = (
            page.locator(
                "body"
            )
            .inner_text(
                timeout=3000
            )
            [:16000]
        )

    except Exception:

        result["body_text"] = ""

    selector = (
        "button,"
        "input,"
        "textarea,"
        "select,"
        "a,"
        "[role='button'],"
        "[role='option'],"
        "[role='tab'],"
        "[contenteditable='true']"
    )

    try:

        locator = page.locator(
            selector
        )

        count = min(
            locator.count(),
            200,
        )

        for i in range(count):

            element = locator.nth(i)

            try:

                if not element.is_visible():

                    continue

                tag = element.evaluate(
                    "(el) => el.tagName.toLowerCase()"
                )

                text = (
                    element.inner_text()
                    or ""
                ).strip()

                aria = (
                    element.get_attribute(
                        "aria-label"
                    )
                    or ""
                )

                name = (
                    element.get_attribute(
                        "name"
                    )
                    or ""
                )

                placeholder = (
                    element.get_attribute(
                        "placeholder"
                    )
                    or ""
                )

                element_id = (
                    element.get_attribute(
                        "id"
                    )
                    or ""
                )

                title = (
                    element.get_attribute(
                        "title"
                    )
                    or ""
                )

                role = (
                    element.get_attribute(
                        "role"
                    )
                    or ""
                )

                value = (
                    element.get_attribute(
                        "value"
                    )
                    or ""
                )

                result[
                    "interactive_elements"
                ].append(

                    {
                        "tag": tag,

                        "text": text[:120],

                        "aria": aria[:120],

                        "name": name,

                        "placeholder":
                            placeholder[:120],

                        "id": element_id,

                        "title": title[:120],

                        "role": role,

                        "value": value[:120],
                    }
                )

            except Exception:

                continue

    except Exception:

        pass

    return result


# ============================================================
# AI PROMPT
# ============================================================

SYSTEM_PROMPT = r"""
You are a GENERAL ERPNext QA BROWSER AGENT.

You control an ERPNext browser through Playwright.

Your job is to execute the user's task.

IMPORTANT:
Return EXACTLY ONE action at a time.

NEVER return a multi-step plan.

NEVER return:
{
    "steps": [...]
}

Return only ONE JSON object.

============================================================
ALLOWED ACTIONS
============================================================

Navigate:

{
    "action": "goto",
    "url": "/app/home"
}

Click:

{
    "action": "click",
    "target": "Search"
}

Fill:

{
    "action": "fill",
    "target": "Search",
    "text": "Budget Head"
}

Press:

{
    "action": "press",
    "target": "Search",
    "key": "Enter"
}

Select:

{
    "action": "select",
    "target": "Company",
    "value": "ABC"
}

Check:

{
    "action": "check",
    "target": "Is Active"
}

Uncheck:

{
    "action": "uncheck",
    "target": "Is Active"
}

Wait:

{
    "action": "wait",
    "ms": 1000
}

Read:

{
    "action": "read_page"
}

Screenshot:

{
    "action": "screenshot",
    "name": "step"
}

Finish:

{
    "action": "done",
    "result": "Task completed."
}

============================================================
IMPORTANT TARGET RULE
============================================================

Use the CURRENT BROWSER STATE.

Prefer:

1. Visible text
2. Accessible label
3. aria-label
4. Placeholder
5. name
6. id
7. Stable CSS selector

Do not invent selectors.

Do not use coordinates.

If you cannot identify an element:

return:

{
    "action": "read_page"
}

============================================================
LOGIN
============================================================

Python handles login.

If logged_in is true:

NEVER return:

{
    "action": "login"
}

NEVER click Login.

NEVER navigate to /login.

Continue the user's actual task.

============================================================
ACTION MEMORY
============================================================

The browser state contains recent actions.

If an action already succeeded:

DO NOT repeat it.

If the same action failed:

do not blindly repeat it.

Try a better target or read the page.

============================================================
SAFETY
============================================================

Never delete.

Never cancel.

Never approve.

Never submit.

Never post.

Never modify financial data.

Unless the user explicitly requests that exact operation.

Do not perform unrelated actions.

============================================================
STOP CONDITION
============================================================

The user may explicitly say:

"stop there"

"stop"

"do not continue"

"do not open"

"do not save"

When that point is reached:

return:

{
    "action": "done",
    "result": "Reached requested stopping point."
}

============================================================
CURRENT TASK
============================================================

{task}

============================================================
CURRENT BROWSER STATE
============================================================

{state}
"""


# ============================================================
# ASK OLLAMA
# ============================================================

def ask_ollama(
    task,
    state,
    recent_actions,
):

    prompt = SYSTEM_PROMPT

    prompt = prompt.replace(
        "{task}",
        task,
    )

    enriched_state = {
        **state,

        "recent_actions":
            recent_actions[-8:],
    }

    prompt = prompt.replace(
        "{state}",
        json.dumps(
            enriched_state,
            ensure_ascii=False,
        ),
    )

    started = time.time()

    response = requests.post(

        f"{OLLAMA_URL}/api/chat",

        json={

            "model": MODEL,

            "messages": [

                {
                    "role": "system",

                    "content":
                        "Return exactly ONE "
                        "valid JSON action. "
                        "No markdown. "
                        "No explanation.",
                },

                {
                    "role": "user",

                    "content": prompt,
                },
            ],

            "stream": False,

            "format": "json",

            "options": {

                "temperature": 0,

                "num_ctx": 8192,
            },
        },

        timeout=AI_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    content = data[
        "message"
    ][
        "content"
    ]

    elapsed = (
        time.time()
        - started
    )

    log(
        f"QWEN RESPONSE TIME: "
        f"{elapsed:.2f}s"
    )

    log(
        "QWEN ACTION: "
        + content
    )

    return parse_action(
        content
    )


# ============================================================
# PARSE ACTION
# ============================================================

def parse_action(raw):

    raw = raw.strip()

    raw = re.sub(
        r"```(?:json)?",
        "",
        raw,
        flags=re.IGNORECASE,
    )

    raw = raw.replace(
        "```",
        "",
    ).strip()

    try:

        data = json.loads(
            raw
        )

    except json.JSONDecodeError:

        start = raw.find(
            "{"
        )

        end = raw.rfind(
            "}"
        )

        if (
            start == -1
            or end == -1
        ):

            raise ValueError(
                "Invalid Qwen JSON:\n"
                + raw
            )

        data = json.loads(
            raw[
                start:end + 1
            ]
        )

    if not isinstance(
        data,
        dict,
    ):

        raise ValueError(
            "Qwen response is not "
            "a JSON object."
        )

    # --------------------------------------------------------
    # VERY IMPORTANT:
    # Reject old multi-step plans
    # --------------------------------------------------------

    if isinstance(
        data.get("steps"),
        list,
    ):

        raise ValueError(
            "Qwen returned a multi-step "
            "plan. Only ONE action is allowed."
        )

    action = data.get(
        "action"
    )

    if not action:

        raise ValueError(
            "Qwen returned no action."
        )

    return data


# ============================================================
# TARGET RESOLVER
# ============================================================

def resolve_target(
    page,
    target,
):

    target = str(
        target or ""
    ).strip()

    if not target:

        return None

    # --------------------------------------------------------
    # CSS selector
    # --------------------------------------------------------

    looks_like_css = (

        target.startswith("#")

        or target.startswith(".")

        or target.startswith("[")

        or "input[" in target

        or "button[" in target

        or "textarea[" in target

        or "select[" in target

        or ":has-text" in target
    )

    if looks_like_css:

        try:

            element = first_visible(
                page.locator(
                    target
                )
            )

            if element:

                return element

        except Exception:

            pass

    # --------------------------------------------------------
    # LABEL
    # --------------------------------------------------------

    try:

        locator = page.get_by_label(
            target,
            exact=True,
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    # --------------------------------------------------------
    # PLACEHOLDER
    # --------------------------------------------------------

    try:

        locator = (
            page.get_by_placeholder(
                target,
                exact=True,
            )
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    # --------------------------------------------------------
    # ROLE BUTTON
    # --------------------------------------------------------

    try:

        locator = page.get_by_role(
            "button",
            name=target,
            exact=True,
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    # --------------------------------------------------------
    # ROLE LINK
    # --------------------------------------------------------

    try:

        locator = page.get_by_role(
            "link",
            name=target,
            exact=True,
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    # --------------------------------------------------------
    # EXACT TEXT
    # --------------------------------------------------------

    try:

        locator = page.get_by_text(
            target,
            exact=True,
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    # --------------------------------------------------------
    # PARTIAL TEXT
    # --------------------------------------------------------

    try:

        locator = page.get_by_text(
            target
        )

        element = first_visible(
            locator
        )

        if element:

            return element

    except Exception:

        pass

    return None


# ============================================================
# EXECUTE ACTION
# ============================================================

def execute_action(
    page,
    action,
):

    name = str(
        action.get(
            "action",
            "",
        )
    ).lower().strip()

    target = (
        action.get("target")
        or action.get("selector")
    )

    # ========================================================
    # LOGIN
    # ========================================================

    if name == "login":

        if is_logged_in(page):

            return (
                "LOGIN_BLOCKED: "
                "Already logged in."
            )

        return perform_login(
            page
        )

    # ========================================================
    # GOTO
    # ========================================================

    if name == "goto":

        url = absolute_url(
            action.get("url")
        )

        if (
            "/login" in url.lower()
            and is_logged_in(page)
        ):

            return (
                "GOTO_BLOCKED: "
                "Already logged in. "
                "Cannot navigate to /login."
            )

        page.goto(

            url,

            wait_until="domcontentloaded",

            timeout=30000,
        )

        page.wait_for_timeout(
            500
        )

        return (
            "GOTO_SUCCESS: "
            + page.url
        )

    # ========================================================
    # READ
    # ========================================================

    if name in (
        "read_page",
        "observe",
    ):

        return json.dumps(
            page_state(page),
            ensure_ascii=False,
        )

    # ========================================================
    # CLICK
    # ========================================================

    if name == "click":

        # Never click Login after successful login.
        if (
            is_logged_in(page)
            and str(target).strip().lower()
            in (
                "login",
                "log in",
                "sign in",
            )
        ):

            return (
                "CLICK_BLOCKED: "
                "Already logged in. "
                "Login button will not be clicked."
            )

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "CLICK_FAILED: "
                + str(target)
            )

        element.click(
            timeout=10000
        )

        page.wait_for_timeout(
            500
        )

        return (
            "CLICK_SUCCESS: "
            + str(target)
        )

    # ========================================================
    # FILL
    # ========================================================

    if name == "fill":

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "FILL_FAILED: "
                + str(target)
            )

        text = str(
            action.get(
                "text",
                "",
            )
        )

        element.fill(
            text,
            timeout=10000,
        )

        return (
            "FILL_SUCCESS: "
            + str(target)
        )

    # ========================================================
    # PRESS
    # ========================================================

    if name == "press":

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "PRESS_FAILED: "
                + str(target)
            )

        key = str(
            action.get(
                "key",
                "Enter",
            )
        )

        element.press(
            key,
            timeout=10000,
        )

        page.wait_for_timeout(
            500
        )

        return (
            "PRESS_SUCCESS: "
            + key
        )

    # ========================================================
    # SELECT
    # ========================================================

    if name == "select":

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "SELECT_FAILED: "
                + str(target)
            )

        value = str(
            action.get(
                "value",
                "",
            )
        )

        element.select_option(
            value,
            timeout=10000,
        )

        return (
            "SELECT_SUCCESS: "
            + value
        )

    # ========================================================
    # CHECK
    # ========================================================

    if name == "check":

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "CHECK_FAILED: "
                + str(target)
            )

        element.check(
            timeout=10000
        )

        return (
            "CHECK_SUCCESS: "
            + str(target)
        )

    # ========================================================
    # UNCHECK
    # ========================================================

    if name == "uncheck":

        element = resolve_target(
            page,
            target,
        )

        if not element:

            return (
                "UNCHECK_FAILED: "
                + str(target)
            )

        element.uncheck(
            timeout=10000
        )

        return (
            "UNCHECK_SUCCESS: "
            + str(target)
        )

    # ========================================================
    # WAIT
    # ========================================================

    if name == "wait":

        ms = int(
            action.get(
                "ms",
                1000,
            )
        )

        ms = max(
            100,
            min(
                ms,
                10000,
            ),
        )

        page.wait_for_timeout(
            ms
        )

        return (
            f"WAIT_SUCCESS: {ms}ms"
        )

    # ========================================================
    # SCREENSHOT
    # ========================================================

    if name == "screenshot":

        filename = re.sub(
            r"[^A-Za-z0-9_-]",
            "_",
            str(
                action.get(
                    "name",
                    "step",
                )
            ),
        )

        path = (
            SCREENSHOTS
            / f"{filename}.png"
        )

        page.screenshot(
            path=str(path),
            full_page=True,
        )

        return (
            "SCREENSHOT_SAVED: "
            + str(path)
        )

    # ========================================================
    # DONE
    # ========================================================

    if name == "done":

        return (
            "__DONE__"
            + str(
                action.get(
                    "result",
                    "Task completed.",
                )
            )
        )

    return (
        "UNKNOWN_ACTION: "
        + name
    )


# ============================================================
# MAIN
# ============================================================

def main():

    task = input(
        "QA task for ERPNext: "
    ).strip()

    if not task:

        print(
            "No task supplied."
        )

        return

    LOG_FILE.write_text(
        "",
        encoding="utf-8",
    )

    report = {

        "task": task,

        "status": "error",

        "model": MODEL,

        "steps": [],
    }

    browser = None
    context = None
    page = None

    recent_actions = []

    try:

        with sync_playwright() as p:

            log(
                "======================================"
            )

            log(
                f"Opening ERPNext: {ERPNEXT_URL}"
            )

            browser = p.chromium.launch(

                headless=HEADLESS,

                slow_mo=SLOW_MO,
            )

            context = browser.new_context(

                viewport={
                    "width": 1440,
                    "height": 900,
                }
            )

            page = context.new_page()

            page.goto(

                ERPNEXT_URL,

                wait_until="domcontentloaded",

                timeout=30000,
            )

            log(
                f"Current URL: {page.url}"
            )

            # =================================================
            # MAIN LOOP
            # =================================================

            for step_no in range(
                1,
                MAX_STEPS + 1,
            ):

                log(
                    f"========== STEP {step_no} =========="
                )

                state = page_state(
                    page
                )

                # ------------------------------------------------
                # LOGIN IS ALWAYS HANDLED LOCALLY
                # ------------------------------------------------

                if not is_logged_in(
                    page
                ):

                    if (
                        "login" in task.lower()
                        or "log in" in task.lower()
                        or "sign in" in task.lower()
                    ):

                        action = {
                            "action": "login"
                        }

                    else:

                        # If user did not explicitly ask
                        # for login but the ERPNext session
                        # requires login, login is still needed
                        # to perform the requested task.

                        action = {
                            "action": "login"
                        }

                        log(
                            "Login required. "
                            "Handling login locally."
                        )

                else:

                    state[
                        "login_status"
                    ] = "ALREADY_LOGGED_IN"

                    # ------------------------------------------------
                    # ASK QWEN FOR EXACTLY ONE ACTION
                    # ------------------------------------------------

                    try:

                        action = ask_ollama(

                            task,

                            state,

                            recent_actions,
                        )

                    except Exception as exc:

                        log(
                            "AI ERROR: "
                            + str(exc)
                        )

                        # Give the model another chance
                        # after reading the page.

                        action = {
                            "action": "read_page"
                        }

                # =================================================
                # SAFETY: LOGIN REPEAT BLOCK
                # =================================================

                if (
                    action.get("action")
                    == "login"
                    and is_logged_in(page)
                ):

                    log(
                        "BLOCKED repeated login."
                    )

                    action = {
                        "action": "read_page"
                    }

                # =================================================
                # SAFETY: /login BLOCK
                # =================================================

                if (
                    action.get("action")
                    == "goto"
                    and "/login"
                    in str(
                        action.get(
                            "url",
                            "",
                        )
                    ).lower()
                    and is_logged_in(page)
                ):

                    log(
                        "BLOCKED navigation to /login."
                    )

                    action = {
                        "action": "read_page"
                    }

                # =================================================
                # DUPLICATE ACTION DETECTION
                # =================================================

                signature = json.dumps(
                    action,
                    sort_keys=True,
                    ensure_ascii=False,
                )

                if (
                    len(recent_actions) >= 2
                    and signature
                    == recent_actions[-1]
                    and signature
                    == recent_actions[-2]
                ):

                    log(
                        "DUPLICATE ACTION DETECTED."
                    )

                    log(
                        "Forcing fresh page observation."
                    )

                    action = {
                        "action": "read_page"
                    }

                    signature = json.dumps(
                        action,
                        sort_keys=True,
                        ensure_ascii=False,
                    )

                # =================================================
                # EXECUTE
                # =================================================

                log(
                    "ACTION: "
                    + json.dumps(
                        action,
                        ensure_ascii=False,
                    )
                )

                started = time.time()

                try:

                    result = execute_action(

                        page,

                        action,
                    )

                except Exception as exc:

                    result = (
                        "ACTION_ERROR: "
                        + str(exc)
                    )

                duration = (
                    time.time()
                    - started
                )

                log(
                    "RESULT: "
                    + result[:3000]
                )

                log(
                    f"STEP TIME: "
                    f"{duration:.2f}s"
                )

                recent_actions.append(
                    signature
                )

                # Keep history small.
                recent_actions = (
                    recent_actions[-8:]
                )

                report[
                    "steps"
                ].append(

                    {
                        "step": step_no,

                        "action": action,

                        "result": result,

                        "url": page.url,

                        "duration":
                            round(
                                duration,
                                2,
                            ),
                    }
                )

                # =================================================
                # DONE
                # =================================================

                if result.startswith(
                    "__DONE__"
                ):

                    report[
                        "status"
                    ] = "passed"

                    log(
                        "TASK COMPLETED: "
                        + result.replace(
                            "__DONE__",
                            "",
                        )
                    )

                    break

                # =================================================
                # ACTION ERROR
                # =================================================

                if result.startswith(
                    "ACTION_ERROR"
                ):

                    log(
                        "Action error."
                    )

                    log(
                        "Agent will observe "
                        "the page again."
                    )

            else:

                report[
                    "status"
                ] = "max_steps_reached"

                log(
                    "MAX STEPS REACHED."
                )

    except KeyboardInterrupt:

        report[
            "status"
        ] = "stopped"

        log(
            "Stopped by user."
        )

    except Exception as exc:

        report[
            "status"
        ] = "error"

        log(
            "FATAL ERROR: "
            + str(exc)
        )

        try:

            if page:

                page.screenshot(

                    path=str(
                        SCREENSHOTS
                        / "failure.png"
                    ),

                    full_page=True,
                )

                log(
                    "Failure screenshot: "
                    + str(
                        SCREENSHOTS
                        / "failure.png"
                    )
                )

        except Exception:

            pass

    finally:

        try:

            if context:

                context.close()

        except Exception:

            pass

        try:

            if browser:

                browser.close()

        except Exception:

            pass

        REPORT_FILE.write_text(

            json.dumps(
                report,
                indent=2,
                ensure_ascii=False,
            ),

            encoding="utf-8",
        )

    print(
        "\n======================================"
    )

    print(
        f"STATUS: {report['status']}"
    )

    print(
        f"STEPS: {len(report['steps'])}"
    )

    print(
        f"REPORT: {REPORT_FILE}"
    )

    print(
        f"SCREENSHOTS: {SCREENSHOTS}"
    )

    print(
        f"LOG: {LOG_FILE}"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":

    main()

