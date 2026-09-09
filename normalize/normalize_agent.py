"""Normalize validated ERPNext Discovery JSON into AI-readable knowledge."""

from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
VALIDATION_DIR = BASE_DIR / "data" / "validation"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
NORMALIZED_DIR = KNOWLEDGE_DIR / "normalized"
BUSINESS_RULES_DIR = KNOWLEDGE_DIR / "business_rules"
WORKFLOWS_DIR = KNOWLEDGE_DIR / "workflows"
RELATIONSHIPS_DIR = KNOWLEDGE_DIR / "relationships"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def text(v: Any) -> str:
    return str(v or "").strip()


def norm(v: Any) -> str:
    return text(v).lower()


def slug(v: Any) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "-", norm(v))
    return re.sub(r"-+", "-", s).strip("-_") or "unknown"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return data


def validation_status(doctype: str) -> str:
    wanted = norm(doctype)
    exact = VALIDATION_DIR / f"{slug(doctype)}_validation.json"
    candidates = [exact] if exact.exists() else sorted(VALIDATION_DIR.glob("*.json"))
    for path in candidates:
        try:
            data = load_json(path)
        except Exception:
            continue
        if norm(data.get("doctype")) == wanted:
            return text(data.get("status")) or "UNKNOWN"
    return "NOT_VALIDATED"


def first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def normalize_field(field: Any) -> dict[str, Any]:
    if not isinstance(field, dict):
        return {
            "fieldname": "",
            "label": "",
            "fieldtype": "",
            "required": False,
            "options": None,
            "raw": field,
        }
    required = first(field, "required", "reqd", "mandatory")
    out = {
        "fieldname": text(first(field, "fieldname", "field_name", "name")),
        "label": text(first(field, "label", "title")),
        "fieldtype": text(first(field, "fieldtype", "field_type", "type")),
        "required": bool(required) if required is not None else False,
        "options": field.get("options"),
        "placeholder": field.get("placeholder"),
        "description": text(first(field, "description", "help_text", "help")),
    }
    for key in (
        "read_only",
        "hidden",
        "default",
        "depends_on",
        "mandatory_depends_on",
        "fetch_from",
        "fetch_if_empty",
        "allow_on_submit",
        "in_list_view",
        "in_standard_filter",
        "tab",
        "section",
    ):
        if key in field:
            out[key] = field[key]
    out["source_keys"] = sorted(field.keys())
    return out


def normalize_fields(items: Any) -> list[dict[str, Any]]:
    result, seen = [], set()
    for raw in items if isinstance(items, list) else []:
        item = normalize_field(raw)
        key = (norm(item.get("fieldname")), norm(item.get("label")))
        if key != ("", "") and key in seen:
            continue
        if key != ("", ""):
            seen.add(key)
        result.append(item)
    return result


def named_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": text(item)}
    out = {
        "name": text(
            first(item, "name", "title", "label", "text", "button", "section", "tab")
        )
    }
    for key in (
        "label",
        "text",
        "title",
        "fieldname",
        "fieldtype",
        "href",
        "route",
        "action",
        "type",
        "tab",
        "section",
        "target_doctype",
        "options",
        "required",
    ):
        if key in item:
            out[key] = item[key]
    out["source_keys"] = sorted(item.keys())
    return out


def normalize_collection(items: Any) -> list[dict[str, Any]]:
    result, seen = [], set()
    for raw in items if isinstance(items, list) else []:
        item = named_item(raw)
        name = norm(item.get("name"))
        if name and name in seen:
            continue
        if name:
            seen.add(name)
        result.append(item)
    return result


def links_from_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for field in fields:
        if norm(field.get("fieldtype")) == "link":
            target = text(field.get("options"))
            out.append(
                {
                    "source_field": field.get("fieldname"),
                    "source_label": field.get("label"),
                    "relationship_type": "Link",
                    "target_doctype": target,
                    "confirmed": bool(target),
                }
            )
    return out


def extract_explicit(
    data: dict[str, Any], keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    out = []
    for key in keys:
        value = data.get(key)
        if value:
            out.append({"source_key": key, "content": value, "confirmed": True})
    return out


def build(data: dict[str, Any], validation: str) -> dict[str, Any]:
    doctype = text(data.get("doctype"))
    fields = normalize_fields(data.get("fields"))
    return {
        "knowledge_version": "1.0",
        "normalized_at": now_iso(),
        "doctype": doctype,
        "source": {
            "discovery_file": data.get("_source_file", ""),
            "validation_status": validation,
        },
        "document": {
            "doctype": doctype,
            "fields": fields,
            "tabs": normalize_collection(data.get("tabs")),
            "sections": normalize_collection(data.get("sections")),
            "buttons": normalize_collection(data.get("buttons")),
            "links": normalize_collection(data.get("links")),
            "elements": normalize_collection(data.get("elements")),
        },
        "relationships": links_from_fields(fields),
        "business_rules": extract_explicit(
            data, ("business_rules", "rules", "formulas", "validation_rules")
        ),
        "workflows": extract_explicit(
            data, ("workflow", "workflow_states", "statuses", "workflow_rules")
        ),
        "qa_knowledge": {
            "existing_record_opened": bool(data.get("existing_record_opened", False)),
            "business_data_created": bool(data.get("business_data_created", False)),
            "business_data_saved": bool(data.get("business_data_saved", False)),
            "field_count": len(fields),
            "tab_count": len(normalize_collection(data.get("tabs"))),
            "section_count": len(normalize_collection(data.get("sections"))),
            "button_count": len(normalize_collection(data.get("buttons"))),
            "link_count": len(normalize_collection(data.get("links"))),
            "element_count": len(normalize_collection(data.get("elements"))),
        },
        "normalization_notes": [
            "Standardized field metadata into fixed keys.",
            "Removed duplicate entries within collections.",
            "Exposed Link fields as relationship candidates.",
            "Did not invent missing business rules or workflows.",
        ],
    }


def save(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return path


def normalize_file(path: Path, require_validation: bool = True) -> dict[str, Any]:
    data = load_json(path)
    data["_source_file"] = path.name
    doctype = text(data.get("doctype"))
    if not doctype:
        raise ValueError(f"DocType missing in {path.name}")
    status = validation_status(doctype)
    if require_validation and status not in {"VALID", "VALID_WITH_WARNINGS"}:
        raise ValueError(
            f"{doctype}: validation status is '{status}'. Run Validation Agent first."
        )

    document = build(data, status)
    normalized_path = save(NORMALIZED_DIR / f"{slug(doctype)}.json", document)

    relation_path = None
    if document["relationships"]:
        relation_path = save(
            RELATIONSHIPS_DIR / f"{slug(doctype)}.json",
            {
                "knowledge_type": "relationships",
                "knowledge_version": "1.0",
                "updated_at": now_iso(),
                "doctype": doctype,
                "relationships": document["relationships"],
            },
        )

    rule_path = None
    if document["business_rules"]:
        rule_path = save(
            BUSINESS_RULES_DIR / f"{slug(doctype)}.json",
            {
                "knowledge_type": "business_rules",
                "knowledge_version": "1.0",
                "updated_at": now_iso(),
                "doctype": doctype,
                "rules": document["business_rules"],
            },
        )

    workflow_path = None
    if document["workflows"]:
        workflow_path = save(
            WORKFLOWS_DIR / f"{slug(doctype)}.json",
            {
                "knowledge_type": "workflows",
                "knowledge_version": "1.0",
                "updated_at": now_iso(),
                "doctype": doctype,
                "workflows": document["workflows"],
            },
        )

    return {
        "doctype": doctype,
        "validation_status": status,
        "status": "NORMALIZED",
        "normalized_file": str(normalized_path.relative_to(BASE_DIR)),
        "relationship_file": (
            str(relation_path.relative_to(BASE_DIR)) if relation_path else None
        ),
        "business_rule_file": (
            str(rule_path.relative_to(BASE_DIR)) if rule_path else None
        ),
        "workflow_file": (
            str(workflow_path.relative_to(BASE_DIR)) if workflow_path else None
        ),
        "field_count": len(document["document"]["fields"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize ERPNext Discovery JSON into AI knowledge."
    )
    parser.add_argument("--file", help="Normalize one discovery JSON file")
    parser.add_argument(
        "--doctype", nargs="+", help="Normalize one or more DocTypes serially"
    )
    parser.add_argument(
        "--allow-unvalidated", action="store_true", help="Skip validation-status gate"
    )
    args = parser.parse_args()
    require_validation = not args.allow_unvalidated

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = BASE_DIR / path
        result = normalize_file(path, require_validation)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    target = {norm(x) for x in args.doctype} if args.doctype else None
    files = sorted(DISCOVERY_DIR.glob("*.json"))
    results = []
    for path in files:
        try:
            data = load_json(path)
            if target is not None and norm(data.get("doctype")) not in target:
                continue
            result = normalize_file(path, require_validation)
            results.append(result)
            print(
                f"[NORMALIZE] {result['doctype']}: {result['status']} -> {result['normalized_file']}"
            )
        except Exception as exc:
            if target is not None:
                print(f"[NORMALIZE] FAILED {path.name}: {exc}")
            else:
                print(f"[NORMALIZE] FAILED {path.name}: {exc}")

    if not args.file:
        print("\n=== NORMALIZE SUMMARY ===")
        print(f"Normalized: {sum(r.get('status') == 'NORMALIZED' for r in results)}")
        print(f"Failed: {len(files) - len(results) if target is None else 'see log'}")


if __name__ == "__main__":
    main()
