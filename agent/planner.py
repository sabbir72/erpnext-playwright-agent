#!/usr/bin/env python3
"""
ERPNext AI QA - Planner Agent

Purpose:
- Read normalized Discovery knowledge from data/normalize/.
- Fall back to data/discovery/ when normalized knowledge is unavailable.
- Convert a QA task into a structured execution plan.
- Keep real DocType names clean; use "New <DocType>" only for Global Search.
- Exclude ERPNext system UI from business plans.
- Do not perform any browser action. Navigator/Executor handle execution later.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
NORMALIZE_DIR = BASE_DIR / "data" / "normalize"
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
PLAN_DIR = BASE_DIR / "data" / "plans"

SYSTEM_UI_KEYWORDS = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
    "bell",
    "help",
    "filter",
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


def clean_doctype_name(name: Any) -> str:
    """Return the real DocType name without the Global Search 'New' prefix."""
    value = str(name or "").strip()
    return re.sub(r"^New\s+", "", value, flags=re.IGNORECASE).strip()


def build_search_name(doctype: str) -> str:
    """Global Search uses 'New <DocType>'; knowledge keeps '<DocType>'."""
    doctype = clean_doctype_name(doctype)
    return f"New {doctype}" if doctype else ""


def is_system_ui(value: Any) -> bool:
    """True when a value belongs to ERPNext/system UI and not business UI."""
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(keyword in text for keyword in SYSTEM_UI_KEYWORDS)


def load_json_files(folder: Path) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []

    if not folder.exists():
        return documents

    for path in sorted(folder.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[PLANNER] SKIP {path.name}: {exc}")
            continue

        if isinstance(data, dict):
            data["_source_file"] = path.name
            documents.append(data)

    return documents


def load_knowledge() -> List[Dict[str, Any]]:
    """Prefer normalized data, otherwise use discovery data as a safe fallback."""
    normalized = load_json_files(NORMALIZE_DIR)
    if normalized:
        print(f"[PLANNER] Loaded {len(normalized)} normalized file(s).")
        return normalized

    discovery = load_json_files(DISCOVERY_DIR)
    if discovery:
        print(
            f"[PLANNER] Normalize data not found. "
            f"Loaded {len(discovery)} discovery file(s) as fallback."
        )
        return discovery

    print("[PLANNER] No normalize/discovery JSON found.")
    return []


def get_doctype(document: Dict[str, Any]) -> str:
    return clean_doctype_name(
        document.get("doctype")
        or document.get("document_name")
        or document.get("name")
        or ""
    )


def list_items(document: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = document.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def first_text(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def detect_task_type(task: str) -> str:
    text = (task or "").lower()

    if any(word in text for word in ("regression", "regress")):
        return "regression"
    if any(
        word in text
        for word in ("create test case", "generate test case", "test cases")
    ):
        return "test_case_generation"
    if any(word in text for word in ("discover", "discovery", "inspect")):
        return "discovery"
    if any(
        word in text for word in ("create", "new document", "new record", "open form")
    ):
        return "create"
    if any(
        word in text for word in ("functional", "validate", "verify", "check", "test")
    ):
        return "functional_test"
    return "general"


def select_doctype(
    knowledge: List[Dict[str, Any]],
    requested_doctype: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not knowledge:
        return None

    if not requested_doctype:
        return knowledge[0]

    requested = clean_doctype_name(requested_doctype).casefold()

    for document in knowledge:
        current = get_doctype(document).casefold()
        if current == requested:
            return document

    return None


def build_fields(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()

    for field in list_items(document, "fields"):
        fieldname = first_text(field, "fieldname", "name")
        label = first_text(field, "label", "title") or fieldname

        if not fieldname and not label:
            continue
        if is_system_ui(fieldname) or is_system_ui(label):
            continue

        key = (fieldname or label).casefold()
        if key in seen:
            continue
        seen.add(key)

        result.append(
            {
                "fieldname": fieldname,
                "label": label,
                "fieldtype": first_text(field, "fieldtype", "type"),
                "required": bool(field.get("required", False)),
                "options": field.get("options", ""),
                "placeholder": field.get("placeholder", ""),
                "action": "inspect_or_fill",
            }
        )

    return result


def build_tabs(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()

    for tab in list_items(document, "tabs"):
        label = first_text(tab, "label", "title", "name")
        if not label or is_system_ui(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append({"tab": label, "action": "open_and_inspect"})

    return result


def build_sections(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()

    for section in list_items(document, "sections"):
        label = first_text(section, "label", "title", "name")
        if not label or is_system_ui(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append({"section": label, "action": "inspect"})

    return result


def build_buttons(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()

    for button in list_items(document, "buttons"):
        label = first_text(button, "label", "text", "name")
        if not label or is_system_ui(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "button": label,
                "action": "inspect",
                "safe_action_required": True,
            }
        )

    return result


def build_links(document: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()

    for link in list_items(document, "links"):
        label = first_text(link, "label", "doctype", "name")
        if not label or is_system_ui(label):
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append({"label": label, "action": "inspect_relation"})

    return result


def build_plan(document: Dict[str, Any], task: str) -> Dict[str, Any]:
    doctype = get_doctype(document)
    search_name = build_search_name(doctype)
    task_type = detect_task_type(task)

    fields = build_fields(document)
    tabs = build_tabs(document)
    sections = build_sections(document)
    buttons = build_buttons(document)
    links = build_links(document)

    steps: List[Dict[str, Any]] = [
        {
            "order": 1,
            "action": "login",
            "description": "Login using configured credentials.",
        },
        {
            "order": 2,
            "action": "open_home",
            "description": "Open ERPNext Home.",
        },
        {
            "order": 3,
            "action": "global_search",
            "search_text": search_name,
            "description": f'Search Global Search for "{search_name}".',
        },
        {
            "order": 4,
            "action": "open_blank_new_document",
            "doctype": doctype,
            "description": f"Open the blank New form for {doctype}.",
        },
        {
            "order": 5,
            "action": "inspect_form_top_to_bottom",
            "description": "Inspect the full blank form by scrolling through every viewport.",
        },
    ]

    order = 6

    for tab in tabs:
        steps.append(
            {
                "order": order,
                "action": "inspect_tab",
                "tab": tab["tab"],
                "description": f'Open and inspect tab "{tab["tab"]}".',
            }
        )
        order += 1

    for section in sections:
        steps.append(
            {
                "order": order,
                "action": "inspect_section",
                "section": section["section"],
            }
        )
        order += 1

    for field in fields:
        steps.append(
            {
                "order": order,
                "action": "inspect_field",
                "fieldname": field["fieldname"],
                "label": field["label"],
                "fieldtype": field["fieldtype"],
                "required": field["required"],
            }
        )
        order += 1

    for button in buttons:
        steps.append(
            {
                "order": order,
                "action": "inspect_button",
                "button": button["button"],
                "safe_action_required": True,
            }
        )
        order += 1

    for link in links:
        steps.append(
            {
                "order": order,
                "action": "inspect_link_relation",
                "label": link["label"],
            }
        )
        order += 1

    return {
        "plan_version": "1.0",
        "task": task,
        "task_type": task_type,
        "doctype": doctype,
        "document_name": doctype,
        "search_name": search_name,
        "action": "New",
        "source_file": document.get("_source_file", ""),
        "safety": {
            "existing_documents_skipped": True,
            "blank_new_document_only": True,
            "do_not_save_without_task": True,
            "do_not_submit_without_task": True,
            "do_not_delete": True,
            "system_ui_excluded": True,
        },
        "steps": steps,
        "fields": fields,
        "tabs": tabs,
        "sections": sections,
        "buttons": buttons,
        "links": links,
    }


def save_plan(plan: Dict[str, Any], filename: str = "latest_plan.json") -> Path:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PLAN_DIR / filename
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(plan, file, ensure_ascii=False, indent=2)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an ERPNext QA execution plan from normalized Discovery knowledge."
    )
    parser.add_argument(
        "--task", required=True, help="Task, e.g. 'Create Contract flow test'"
    )
    parser.add_argument("--doctype", help="Specific DocType, e.g. 'Contract'")
    args = parser.parse_args()

    knowledge = load_knowledge()
    document = select_doctype(knowledge, args.doctype)

    if not document:
        requested = clean_doctype_name(args.doctype or "")
        message = "[PLANNER] No matching DocType found."
        if requested:
            message += f" Requested: {requested}"
        print(message)
        return

    plan = build_plan(document, args.task)
    output = save_plan(plan)

    print(f"[PLANNER] DocType : {plan['doctype']}")
    print(f"[PLANNER] Search  : {plan['search_name']}")
    print(f"[PLANNER] Task    : {plan['task_type']}")
    print(f"[PLANNER] Steps   : {len(plan['steps'])}")
    print(f"[PLANNER] Output  : {output}")


if __name__ == "__main__":
    main()
