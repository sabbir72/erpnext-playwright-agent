"""
ERPNext AI QA - Validation Agent

Purpose:
    Validate Discovery Agent JSON files before they enter the AI knowledge base.

Pipeline position:
    Discovery -> Validation -> Normalize -> Store -> Retrieve -> Plan -> Execute -> Analyze

This agent validates STRUCTURE and COMPLETENESS.
It does not execute business tests and does not produce Pass/Fail test results.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
VALIDATION_DIR = BASE_DIR / "data" / "validation"

REQUIRED_TOP_LEVEL_KEYS = {
    "doctype",
    "fields",
    "tabs",
    "sections",
    "buttons",
    "links",
    "elements",
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
    "notification",
    "notifications",
    "notification icon",
    "bell",
    "new workspace",
    "create workspace",
    "add workspace",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def is_system_ui(value: Any) -> bool:
    text = normalize_text(value)
    return text in SYSTEM_UI_KEYWORDS or any(
        keyword in text for keyword in SYSTEM_UI_KEYWORDS
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Discovery JSON root must be an object")

    return data


def validate_required_structure(data: dict[str, Any]) -> list[str]:
    errors = []

    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(data.keys()))
    if missing:
        errors.append(f"Missing top-level keys: {', '.join(missing)}")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key in data and not isinstance(data[key], list):
            errors.append(f"'{key}' must be a list")

    if not str(data.get("doctype", "")).strip():
        errors.append("DocType name is empty")

    return errors


def get_name(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in (
        "fieldname",
        "field_name",
        "name",
        "label",
        "button",
        "text",
        "title",
        "doctype",
    ):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def find_duplicates(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []

    for item in items:
        name = normalize_text(get_name(item))
        if not name:
            continue
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)

    return duplicates


def validate_fields(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    fields = data.get("fields", [])

    duplicates = find_duplicates(fields)
    if duplicates:
        warnings.append("Duplicate field entries: " + ", ".join(sorted(duplicates)))

    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            errors.append(f"Field #{index + 1} is not an object")
            continue

        fieldname = str(field.get("fieldname") or field.get("field_name") or "").strip()
        label = str(field.get("label") or "").strip()

        if not fieldname and not label:
            errors.append(f"Field #{index + 1} has no fieldname or label")

        if not fieldname:
            warnings.append(
                f"Field #{index + 1} ({label or 'unknown'}) has no fieldname"
            )

        if not label:
            warnings.append(f"Field {fieldname or index + 1} has no label")

        field_type = field.get("fieldtype") or field.get("field_type")
        if not field_type:
            warnings.append(
                f"Field {fieldname or label or index + 1} has no field type"
            )

        # AI knowledge needs enough information to identify interactive fields.
        if field_type and normalize_text(field_type) in {
            "select",
            "link",
            "table",
            "multiselect",
        }:
            if field_type == "Select" and not field.get("options"):
                warnings.append(f"Select field '{fieldname or label}' has no options")

    return errors, warnings


def validate_collection(
    data: dict[str, Any],
    key: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    items = data.get(key, [])

    duplicates = find_duplicates(items)
    if duplicates:
        warnings.append(f"Duplicate {key}: " + ", ".join(sorted(duplicates)))

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{key} #{index + 1} is not an object")
            continue

        name = get_name(item)
        if not name:
            warnings.append(f"{key} #{index + 1} has no identifiable name/text")

        if is_system_ui(name):
            warnings.append(f"System UI may have been captured in {key}: '{name}'")

    return errors, warnings


def validate_relationships(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    for field in data.get("fields", []):
        if not isinstance(field, dict):
            continue

        field_type = normalize_text(field.get("fieldtype") or field.get("field_type"))

        if field_type == "link":
            options = field.get("options")
            if not options:
                warnings.append(
                    f"Link field '{get_name(field)}' has no linked DocType/options"
                )

    return warnings


def validate_business_data_safety(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    if data.get("existing_record_opened") is True:
        warnings.append(
            "Discovery metadata says an existing business record was opened"
        )

    if data.get("business_data_created") is True:
        warnings.append("Discovery metadata says business data was created")

    if data.get("business_data_saved") is True:
        warnings.append("Discovery metadata says business data was saved")

    return warnings


def calculate_completeness(data: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "doctype_present": bool(str(data.get("doctype", "")).strip()),
        "fields_present": isinstance(data.get("fields"), list),
        "tabs_present": isinstance(data.get("tabs"), list),
        "sections_present": isinstance(data.get("sections"), list),
        "buttons_present": isinstance(data.get("buttons"), list),
        "links_present": isinstance(data.get("links"), list),
        "elements_present": isinstance(data.get("elements"), list),
    }

    passed = sum(checks.values())
    total = len(checks)

    return {
        "checks": checks,
        "score": round((passed / total) * 100, 2) if total else 0,
        "passed": passed,
        "total": total,
    }


def validate_discovery_file(path: Path) -> dict[str, Any]:
    started = now_iso()

    result: dict[str, Any] = {
        "validation_version": "1.0",
        "source_file": path.name,
        "validated_at": started,
        "doctype": "",
        "status": "FAILED",
        "errors": [],
        "warnings": [],
        "summary": {},
    }

    try:
        data = load_json(path)
    except json.JSONDecodeError as exc:
        result["errors"].append(f"Invalid JSON: {exc}")
        return result
    except Exception as exc:
        result["errors"].append(f"Could not read file: {exc}")
        return result

    result["doctype"] = str(data.get("doctype", "")).strip()

    result["errors"].extend(validate_required_structure(data))

    field_errors, field_warnings = validate_fields(data)
    result["errors"].extend(field_errors)
    result["warnings"].extend(field_warnings)

    for key in ("tabs", "sections", "buttons", "links", "elements"):
        errors, warnings = validate_collection(data, key)
        result["errors"].extend(errors)
        result["warnings"].extend(warnings)

    result["warnings"].extend(validate_relationships(data))
    result["warnings"].extend(validate_business_data_safety(data))

    result["summary"] = {
        "doctype": result["doctype"],
        "field_count": (
            len(data.get("fields", [])) if isinstance(data.get("fields"), list) else 0
        ),
        "tab_count": (
            len(data.get("tabs", [])) if isinstance(data.get("tabs"), list) else 0
        ),
        "section_count": (
            len(data.get("sections", []))
            if isinstance(data.get("sections"), list)
            else 0
        ),
        "button_count": (
            len(data.get("buttons", [])) if isinstance(data.get("buttons"), list) else 0
        ),
        "link_count": (
            len(data.get("links", [])) if isinstance(data.get("links"), list) else 0
        ),
        "element_count": (
            len(data.get("elements", []))
            if isinstance(data.get("elements"), list)
            else 0
        ),
        "completeness": calculate_completeness(data),
    }

    if result["errors"]:
        result["status"] = "FAILED"
    elif result["warnings"]:
        result["status"] = "VALID_WITH_WARNINGS"
    else:
        result["status"] = "VALID"

    return result


def save_validation(result: dict[str, Any]) -> Path:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    doctype = normalize_text(result.get("doctype")).replace(" ", "-")
    doctype = (
        "".join(char for char in doctype if char.isalnum() or char in "-_") or "unknown"
    )

    output = VALIDATION_DIR / f"{doctype}_validation.json"
    temp = output.with_suffix(".json.tmp")

    with temp.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    temp.replace(output)
    return output


def run(discovery_dir: Path = DISCOVERY_DIR) -> list[dict[str, Any]]:
    discovery_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(discovery_dir.glob("*.json"))

    results = []

    for path in files:
        result = validate_discovery_file(path)
        output = save_validation(result)
        result["validation_file"] = str(output.relative_to(BASE_DIR))
        results.append(result)

        print(
            f"[VALIDATION] {result.get('doctype') or path.name}: " f"{result['status']}"
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate ERPNext Discovery JSON files."
    )
    parser.add_argument(
        "--file",
        help="Validate one discovery JSON file.",
    )
    parser.add_argument(
        "--doctype",
        nargs="+",
        help="Validate discovery JSON for one or more DocTypes.",
    )
    args = parser.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = BASE_DIR / path
        result = validate_discovery_file(path)
        output = save_validation(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Saved: {output}")
        return

    if args.doctype:
        wanted = {normalize_text(name) for name in args.doctype}
        files = sorted(DISCOVERY_DIR.glob("*.json"))
        matched = [
            p for p in files if normalize_text(load_json(p).get("doctype")) in wanted
        ]

        if not matched:
            raise SystemExit("No matching discovery JSON found.")

        for path in matched:
            result = validate_discovery_file(path)
            output = save_validation(result)
            print(
                f"[VALIDATION] {result.get('doctype')}: "
                f"{result['status']} -> {output}"
            )
        return

    results = run()

    valid = sum(r["status"] == "VALID" for r in results)
    warning = sum(r["status"] == "VALID_WITH_WARNINGS" for r in results)
    failed = sum(r["status"] == "FAILED" for r in results)

    print("\n=== VALIDATION SUMMARY ===")
    print(f"Total: {len(results)}")
    print(f"Valid: {valid}")
    print(f"Valid with warnings: {warning}")
    print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
