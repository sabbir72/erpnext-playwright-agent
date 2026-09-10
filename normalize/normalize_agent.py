"""
ERPNext AI QA - Normalize Agent

Purpose
-------
Normalize validated Discovery JSON files into a stable, AI-readable format.

Input:
    data/discovery/*.json

Validation dependency:
    The input JSON must indicate a PASSED validation status.
    Failed/invalid files are skipped.

Output:
    data/normalize/*.json

Important naming rule:
    - "doctype" must NOT start with "New "
    - "search_name" keeps "New <DocType>"
    - "action" remains "New"
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# ============================================================
# PATHS
# ============================================================

FILE_PATH = Path(__file__).resolve()
PROJECT_ROOT = FILE_PATH.parents[1]

DISCOVERY_DIR = PROJECT_ROOT / "data" / "discovery"
NORMALIZE_DIR = PROJECT_ROOT / "data" / "normalize"


# ============================================================
# TEXT HELPERS
# ============================================================


def clean_text(value: Any) -> str:
    """Normalize text to a clean single line."""
    if value is None:
        return ""

    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def clean_doctype_name(value: Any) -> str:
    """
    Remove only leading 'New ' from DocType.

    Examples:
        New Company Budget -> Company Budget
        Company Budget -> Company Budget
    """
    name = clean_text(value)

    return re.sub(
        r"^New\s+",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()


def build_search_name(
    doctype: str,
    existing: Any = None,
) -> str:
    """
    Build the required Global Search name.

    Example:
        Company Budget -> New Company Budget
    """

    existing_text = clean_text(existing)

    if existing_text:
        existing_clean = re.sub(
            r"^New\s+",
            "",
            existing_text,
            flags=re.IGNORECASE,
        )

        if existing_clean.lower() == doctype.lower():
            return f"New {doctype}"

    return f"New {doctype}"


# ============================================================
# DEDUPLICATION
# ============================================================


def unique_dict_list(
    items: Any,
    key: str = "fieldname",
) -> list[dict[str, Any]]:
    """
    Remove duplicate dictionaries while keeping
    the first occurrence.
    """

    if not isinstance(items, list):
        return []

    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in items:

        if not isinstance(item, dict):
            continue

        identity = clean_text(item.get(key)).lower()

        if identity:

            if identity in seen:
                continue

            seen.add(identity)

        output.append(item)

    return output


# ============================================================
# FIELD NORMALIZATION
# ============================================================


def clean_field(field: Any) -> dict[str, Any] | None:
    """Normalize one field object."""

    if not isinstance(field, dict):
        return None

    fieldname = clean_text(
        field.get("fieldname") or field.get("name") or field.get("field_name")
    )

    label = clean_text(field.get("label") or field.get("title"))

    fieldtype = clean_text(
        field.get("fieldtype") or field.get("type") or field.get("input_type")
    )

    if not fieldname and not label:
        return None

    result: dict[str, Any] = {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
    }

    # Preserve useful metadata when it exists.
    preserve_keys = [
        "reqd",
        "required",
        "mandatory",
        "read_only",
        "readonly",
        "hidden",
        "options",
        "default",
        "description",
        "placeholder",
        "depends_on",
        "mandatory_depends_on",
        "section",
        "tab",
    ]

    for key in preserve_keys:

        if key in field:
            result[key] = field[key]

    return result


def normalize_fields(value: Any) -> list[dict[str, Any]]:
    """Normalize and deduplicate fields."""

    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []

    for raw in value:

        field = clean_field(raw)

        if field is not None:
            normalized.append(field)

    return unique_dict_list(
        normalized,
        key="fieldname",
    )


# ============================================================
# GENERIC UI COLLECTION NORMALIZATION
# ============================================================


def normalize_named_list(
    value: Any,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """
    Normalize generic UI collections.

    Used for:
        tabs
        sections
        buttons
        links
    """

    if not isinstance(value, list):
        return []

    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in value:

        # ----------------------------------------------------
        # String
        # ----------------------------------------------------

        if isinstance(raw, str):

            name = clean_text(raw)

            if not name:
                continue

            item = {"name": name}

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

        elif isinstance(raw, dict):

            item = dict(raw)

            name = ""

            for key in keys:

                candidate = clean_text(item.get(key))

                if candidate:
                    name = candidate
                    break

            if not name:
                continue

            item["name"] = name

        else:
            continue

        # ----------------------------------------------------
        # Deduplicate
        # ----------------------------------------------------

        identity = clean_text(item.get("name")).lower()

        if identity in seen:
            continue

        seen.add(identity)

        output.append(item)

    return output


# ============================================================
# SOURCE METADATA
# ============================================================


def normalize_source_metadata(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Preserve useful high-level discovery metadata.
    """

    result: dict[str, Any] = {}

    metadata_keys = [
        "module",
        "workspace",
        "url",
        "route",
        "source_url",
        "source_route",
        "discovered_at",
        "read_mode",
        "blank_form",
        "is_new_form",
        "existing_record_opened",
    ]

    for key in metadata_keys:

        if key in data:
            result[key] = data[key]

    return result


# ============================================================
# VALIDATION STATUS
# ============================================================


def validation_is_passed(
    data: dict[str, Any],
) -> bool:
    """
    Detect PASSED validation status.

    Supports:

        validation_status: "PASSED"

        validation:
            {
                "status": "PASSED"
            }

        status: "PASSED"
    """

    candidates = [
        data.get("validation_status"),
        data.get("validation"),
        data.get("status"),
    ]

    for candidate in candidates:

        # ----------------------------------------------------
        # Dict
        # ----------------------------------------------------

        if isinstance(candidate, dict):

            status = clean_text(
                candidate.get("status") or candidate.get("validation_status")
            ).upper()

            if status == "PASSED":
                return True

        # ----------------------------------------------------
        # String
        # ----------------------------------------------------

        elif clean_text(candidate).upper() == "PASSED":

            return True

    return False


# ============================================================
# DOCUMENT NORMALIZATION
# ============================================================


def normalize_document(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize one Discovery JSON document.
    """

    raw_doctype = (
        data.get("doctype") or data.get("document_type") or data.get("name") or ""
    )

    doctype = clean_doctype_name(raw_doctype)

    search_name = build_search_name(
        doctype,
        data.get("search_name"),
    )

    # --------------------------------------------------------
    # Main normalized structure
    # --------------------------------------------------------

    normalized: dict[str, Any] = {
        "doctype": doctype,
        "search_name": search_name,
        "action": "New",
    }

    # --------------------------------------------------------
    # Source metadata
    # --------------------------------------------------------

    normalized.update(normalize_source_metadata(data))

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    normalized["fields"] = normalize_fields(
        data.get("fields") or data.get("form_fields") or []
    )

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    normalized["tabs"] = normalize_named_list(
        data.get("tabs") or [],
        (
            "name",
            "label",
            "title",
            "text",
        ),
    )

    # --------------------------------------------------------
    # Sections
    # --------------------------------------------------------

    normalized["sections"] = normalize_named_list(
        data.get("sections") or [],
        (
            "name",
            "label",
            "title",
            "text",
        ),
    )

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    normalized["buttons"] = normalize_named_list(
        data.get("buttons") or [],
        (
            "name",
            "label",
            "title",
            "text",
        ),
    )

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    normalized["links"] = normalize_named_list(
        data.get("links") or [],
        (
            "name",
            "label",
            "title",
            "text",
        ),
    )

    # --------------------------------------------------------
    # Other discovered information
    # --------------------------------------------------------

    preserve_data_keys = [
        "link_options",
        "child_tables",
        "visible_elements",
        "sections_and_tabs",
        "form_summary",
        "notes",
        "screenshots",
    ]

    for key in preserve_data_keys:

        if key in data:
            normalized[key] = data[key]

    # --------------------------------------------------------
    # Normalization status
    # --------------------------------------------------------

    normalized["normalization"] = {
        "status": "NORMALIZED",
        "doctype_cleaned": True,
        "search_name_preserved_as_new": True,
        "duplicates_removed": True,
    }

    return normalized


# ============================================================
# OUTPUT FILE NAME
# ============================================================


def output_filename(
    input_path: Path,
    data: dict[str, Any],
) -> str:
    """
    Generate normalized filename.

    Example:
        0001_new-company-budget.json
        ->
        0001_company-budget.json
    """

    stem = input_path.stem

    match = re.match(
        r"^(\d+)(?:[_-].*)?$",
        stem,
    )

    serial = ""

    if match:
        serial = match.group(1)

    doctype = clean_doctype_name(
        data.get("doctype")
        or data.get("document_type")
        or data.get("name")
        or input_path.stem
    )

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        doctype.lower(),
    ).strip("-")

    if not slug:
        slug = "document"

    if serial:
        return f"{serial}_{slug}.json"

    return f"{slug}.json"


# ============================================================
# NORMALIZE ONE FILE
# ============================================================


def normalize_file(
    input_path: Path,
) -> tuple[bool, str]:
    """
    Normalize one Discovery JSON file.
    """

    # --------------------------------------------------------
    # Read JSON
    # --------------------------------------------------------

    try:

        with input_path.open(
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

    except Exception as exc:

        return (
            False,
            f"JSON read failed: {exc}",
        )

    # --------------------------------------------------------
    # Root validation
    # --------------------------------------------------------

    if not isinstance(data, dict):

        return (
            False,
            "root JSON is not an object",
        )

    # --------------------------------------------------------
    # Validation Agent dependency
    # --------------------------------------------------------

    if not validation_is_passed(data):

        return (
            False,
            "validation status is not 'PASSED'. " "Run Validation Agent first.",
        )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    try:

        normalized = normalize_document(data)

        NORMALIZE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        out_path = NORMALIZE_DIR / output_filename(
            input_path,
            data,
        )

        with out_path.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                normalized,
                f,
                ensure_ascii=False,
                indent=2,
            )

        return (
            True,
            str(out_path),
        )

    except Exception as exc:

        return (
            False,
            f"normalization failed: {exc}",
        )


# ============================================================
# RUN ALL
# ============================================================


def run_all() -> int:
    """
    Normalize every Discovery JSON file.
    """

    # --------------------------------------------------------
    # Discovery directory
    # --------------------------------------------------------

    if not DISCOVERY_DIR.exists():

        print(
            "[NORMALIZE] No discovery directory found:",
            DISCOVERY_DIR,
        )

        return 1

    # --------------------------------------------------------
    # Find JSON files
    # --------------------------------------------------------

    files = sorted(DISCOVERY_DIR.glob("*.json"))

    if not files:

        print(
            "[NORMALIZE] No discovery JSON found in:",
            DISCOVERY_DIR,
        )

        return 1

    NORMALIZE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    passed = 0
    failed = 0

    # --------------------------------------------------------
    # Process files serially
    # --------------------------------------------------------

    for input_path in files:

        ok, message = normalize_file(input_path)

        if ok:

            passed += 1

            print(f"[NORMALIZE] PASSED " f"{input_path.name} -> {message}")

        else:

            failed += 1

            print(f"[NORMALIZE] FAILED " f"{input_path.name}: {message}")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("NORMALIZE SUMMARY")
    print("=" * 60)

    print(f"Total : {len(files)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Output: {NORMALIZE_DIR}")

    # Any failed file means non-zero result.
    return 0 if failed == 0 else 2


# ============================================================
# RUN ONE
# ============================================================


def run_one(
    filename: str,
) -> int:
    """
    Normalize one specific Discovery JSON.
    """

    input_path = Path(filename)

    if not input_path.is_absolute():

        input_path = DISCOVERY_DIR / input_path

    if not input_path.exists():

        print(
            "[NORMALIZE] File not found:",
            input_path,
        )

        return 1

    ok, message = normalize_file(input_path)

    if ok:

        print(f"[NORMALIZE] PASSED " f"{input_path.name} -> {message}")

        return 0

    print(f"[NORMALIZE] FAILED " f"{input_path.name}: {message}")

    return 2


# ============================================================
# CLI
# ============================================================


def main() -> int:

    parser = argparse.ArgumentParser(
        description=("Normalize validated " "ERPNext Discovery JSON files.")
    )

    parser.add_argument(
        "--file",
        help=("Normalize one Discovery " "JSON file."),
    )

    args = parser.parse_args()

    if args.file:

        return run_one(args.file)

    return run_all()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(main())
