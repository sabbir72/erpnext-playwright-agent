import argparse
import json
import re
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = (
    Path(__file__).resolve().parents[1]
    if (Path(__file__).resolve().parents[1] / "data").exists()
    else Path(__file__).resolve().parent
)
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
VALIDATION_DIR = BASE_DIR / "data" / "validation"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

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
    "notification",
    "notifications",
    "notification icon",
    "bell",
    "new workspace",
}

# ============================================================
# HELPERS
# ============================================================


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize(value):
    return clean_text(value).lower()


def slugify(value):
    value = normalize(value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "unknown"


def clean_doctype_name(value):
    value = clean_text(value)
    if value.lower().startswith("new "):
        return value[4:].strip()
    return value


def add_issue(result, message, severity="ERROR"):
    result["issues"].append({"severity": severity, "message": message})


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)


def expected_filename(path, doctype):
    match = re.match(r"^(\d+)_", path.stem)
    if not match:
        return False
    return f"{match.group(1)}_{slugify(doctype)}.json" == path.name


# ============================================================
# FIELD VALIDATION
# ============================================================


def validate_fields(data, result):
    fields = data.get("fields")
    if not isinstance(fields, list):
        add_issue(result, "fields must be a list")
        return

    seen = set()
    for index, field in enumerate(fields, start=1):
        if not isinstance(field, dict):
            add_issue(result, f"fields[{index}] is not an object")
            continue

        fieldname = clean_text(field.get("fieldname"))
        label = clean_text(field.get("label"))
        fieldtype = clean_text(field.get("fieldtype"))

        if not fieldname:
            add_issue(result, f"fields[{index}] missing fieldname")
        elif fieldname in seen:
            add_issue(result, f"duplicate fieldname: {fieldname}")
        else:
            seen.add(fieldname)

        if not label:
            add_issue(result, f"field '{fieldname or index}' missing label", "WARNING")

        if not fieldtype or fieldtype.lower() == "unknown":
            add_issue(
                result, f"field '{fieldname or index}' has unknown fieldtype", "WARNING"
            )


# ============================================================
# UI VALIDATION
# ============================================================


def is_system_ui(value):
    value = normalize(value)
    if not value:
        return False
    return value in SYSTEM_UI_KEYWORDS or "notification" in value or value == "bell"


def validate_buttons(data, result):
    buttons = data.get("buttons")
    if not isinstance(buttons, list):
        add_issue(result, "buttons must be a list", "WARNING")
        return

    for index, button in enumerate(buttons, start=1):
        if not isinstance(button, dict):
            add_issue(result, f"buttons[{index}] is not an object", "WARNING")
            continue
        text = clean_text(
            button.get("text") or button.get("label") or button.get("title")
        )
        if is_system_ui(text):
            add_issue(result, f"system UI detected in buttons: '{text}'", "WARNING")


def validate_elements(data, result):
    elements = data.get("elements")
    if not isinstance(elements, list):
        add_issue(result, "elements must be a list", "WARNING")
        return

    for index, element in enumerate(elements, start=1):
        if not isinstance(element, dict):
            add_issue(result, f"elements[{index}] is not an object", "WARNING")
            continue
        text = clean_text(element.get("text"))
        aria = clean_text(element.get("aria_label"))
        title = clean_text(element.get("title"))
        if any(is_system_ui(value) for value in (text, aria, title)):
            # System UI may be intentionally captured as metadata. This is not a hard failure.
            continue


# ============================================================
# DOCUMENT VALIDATION
# ============================================================


def validate_document(path, data):
    result = {
        "file": path.name,
        "status": "PASSED",
        "doctype": clean_text(data.get("doctype")),
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "issues": [],
    }

    required_keys = [
        "knowledge_type",
        "module",
        "doctype",
        "document_name",
        "search_name",
        "action",
        "read_mode",
        "existing_documents_skipped",
        "url",
        "fields",
        "tabs",
        "sections",
        "buttons",
        "links",
        "elements",
    ]

    for key in required_keys:
        if key not in data:
            add_issue(result, f"missing top-level key: {key}")

    doctype = clean_doctype_name(data.get("doctype"))
    document_name = clean_doctype_name(data.get("document_name"))
    search_name = clean_text(data.get("search_name"))
    action = clean_text(data.get("action"))
    read_mode = clean_text(data.get("read_mode"))

    if not doctype:
        add_issue(result, "doctype is empty")
    if not document_name:
        add_issue(result, "document_name is empty")
    if normalize(doctype) != normalize(document_name):
        add_issue(
            result, f"doctype/document_name mismatch: '{doctype}' vs '{document_name}'"
        )
    if doctype.lower().startswith("new "):
        add_issue(result, "doctype must NOT contain leading 'New'")
    if document_name.lower().startswith("new "):
        add_issue(result, "document_name must NOT contain leading 'New'")

    expected_search = f"New {doctype}" if doctype else ""
    if normalize(search_name) != normalize(expected_search):
        add_issue(
            result,
            f"search_name mismatch: expected '{expected_search}', got '{search_name}'",
        )
    if normalize(action) != "new":
        add_issue(result, f"action must be 'New', got '{action}'")
    if read_mode and read_mode != "blank_new_document":
        add_issue(
            result, f"read_mode should be 'blank_new_document', got '{read_mode}'"
        )
    if data.get("existing_documents_skipped") is not True:
        add_issue(result, "existing_documents_skipped must be true")

    if expected_filename(path, doctype):
        pass
    else:
        add_issue(
            result,
            f"filename does not match clean doctype: expected serial_{slugify(doctype)}.json",
            "WARNING",
        )

    validate_fields(data, result)
    validate_buttons(data, result)
    validate_elements(data, result)

    system_rules = data.get("system_ui_rules")
    if isinstance(system_rules, dict):
        if system_rules.get("notification_click_allowed") is True:
            add_issue(result, "notification_click_allowed must be false")

    result["status"] = (
        "FAILED"
        if any(i["severity"] == "ERROR" for i in result["issues"])
        else "PASSED"
    )
    return result


# ============================================================
# SAVE REPORT
# ============================================================


def save_result(result):
    path = VALIDATION_DIR / result["file"]
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def validate_all():
    files = sorted(DISCOVERY_DIR.glob("*.json"))
    summary = {
        "validation_type": "erpnext_discovery_validation",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "discovery_dir": str(DISCOVERY_DIR),
        "total": len(files),
        "passed": 0,
        "failed": 0,
        "warning_only": 0,
        "invalid_json": 0,
        "results": [],
    }

    if not files:
        print(f"[VALIDATION] No discovery JSON found in: {DISCOVERY_DIR}")
        return summary

    for path in files:
        raw = load_json(path)
        if isinstance(raw, tuple) and raw[0] is None:
            _, error = raw
            result = {
                "file": path.name,
                "status": "FAILED",
                "doctype": "",
                "checked_at": datetime.now().isoformat(timespec="seconds"),
                "issues": [{"severity": "ERROR", "message": f"Invalid JSON: {error}"}],
            }
            summary["invalid_json"] += 1
        else:
            data, error = raw if isinstance(raw, tuple) else (raw, None)
            result = validate_document(path, data or {})

        save_result(result)
        summary["results"].append(result)

        if result["status"] == "PASSED":
            summary["passed"] += 1
            if any(i["severity"] == "WARNING" for i in result["issues"]):
                summary["warning_only"] += 1
            print(f"[VALIDATION] PASSED  {path.name}")
        else:
            summary["failed"] += 1
            print(f"[VALIDATION] FAILED  {path.name}")
            for issue in result["issues"]:
                print(f"    [{issue['severity']}] {issue['message']}")

    summary_path = VALIDATION_DIR / "validation_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n============================================================")
    print("VALIDATION SUMMARY")
    print("============================================================")
    print(f"Total   : {summary['total']}")
    print(f"Passed  : {summary['passed']}")
    print(f"Failed  : {summary['failed']}")
    print(f"Warnings: {summary['warning_only']}")
    print(f"Report  : {summary_path}")

    return summary


def validate_one(filename):
    path = DISCOVERY_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Discovery file not found: {path}")

    raw = load_json(path)
    data, error = raw if isinstance(raw, tuple) else (raw, None)
    if data is None:
        result = {
            "file": path.name,
            "status": "FAILED",
            "doctype": "",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "issues": [{"severity": "ERROR", "message": f"Invalid JSON: {error}"}],
        }
    else:
        result = validate_document(path, data)

    output = save_result(result)
    print(f"[VALIDATION] {result['status']} {path.name}")
    for issue in result["issues"]:
        print(f"    [{issue['severity']}] {issue['message']}")
    print(f"Report: {output}")
    return result


# ============================================================
# CLI
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Validate ERPNext Discovery JSON files"
    )
    parser.add_argument("--file", help="Validate one discovery JSON filename")
    args = parser.parse_args()

    if args.file:
        result = validate_one(args.file)
        raise SystemExit(0 if result["status"] == "PASSED" else 1)

    summary = validate_all()
    raise SystemExit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
