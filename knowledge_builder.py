#!/usr/bin/env python3

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def log(message):
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    )


def safe_name(value, fallback="unknown"):
    value = str(value or "").strip()
    value = re.sub(r"[^\w\s.-]", "", value)
    value = re.sub(r"\s+", "_", value)

    return value[:120] or fallback


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


def get_value(data, *keys, default=None):
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return default


def normalize_field(field):
    return {
        "label": get_value(
            field,
            "label",
            "text",
            "name",
            "fieldname"
        ),

        "fieldname": get_value(
            field,
            "fieldname",
            "name"
        ),

        "type": get_value(
            field,
            "fieldtype",
            "type",
            "element_type"
        ),

        "mandatory": bool(
            get_value(
                field,
                "mandatory",
                "required",
                "reqd",
                default=False
            )
        ),

        "options": get_value(
            field,
            "options",
            "values"
        ),

        "placeholder": get_value(
            field,
            "placeholder"
        ),

        "default": get_value(
            field,
            "default",
            "default_value"
        ),

        "readonly": bool(
            get_value(
                field,
                "readonly",
                "read_only",
                default=False
            )
        ),

        "hidden": bool(
            get_value(
                field,
                "hidden",
                default=False
            )
        ),

        "link_doctype": get_value(
            field,
            "link_doctype",
            "options_doctype",
            "related_doctype",
            "reference"
        )
    }


def collect_fields(data):
    found = []

    def walk(value):

        if isinstance(value, dict):

            for key in (
                "fields",
                "form_fields",
                "visible_fields",
                "inputs"
            ):

                items = value.get(key)

                if isinstance(items, list):

                    for item in items:

                        if isinstance(item, dict):
                            found.append(item)

            for child in value.values():
                walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    walk(data)

    result = []
    seen = set()

    for field in found:

        normalized = normalize_field(field)

        key = (
            normalized.get("fieldname"),
            normalized.get("label"),
            normalized.get("type")
        )

        if key in seen:
            continue

        if not any(key):
            continue

        seen.add(key)
        result.append(normalized)

    return result


def collect_items(data, keys):

    found = []

    def walk(value):

        if isinstance(value, dict):

            for key in keys:

                item = value.get(key)

                if isinstance(item, list):
                    found.extend(item)

                elif item not in (None, ""):
                    found.append(item)

            for child in value.values():
                walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    walk(data)

    result = []
    seen = set()

    for item in found:

        if isinstance(item, (dict, list)):
            marker = json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=False
            )
        else:
            marker = str(item)

        if marker in seen:
            continue

        seen.add(marker)
        result.append(item)

    return result


def infer_doctype(data, filename):

    if isinstance(data, dict):

        value = get_value(
            data,
            "doctype",
            "doc_type",
            "document_type"
        )

        if value:
            return str(value)

        title = data.get("title")

        if isinstance(title, str) and title.strip():
            return title.strip()

    name = filename.replace(
        "_discovery",
        ""
    )

    name = name.replace(
        "_",
        " "
    )

    return name.title()


def build_doctype(data, source):

    doctype = infer_doctype(
        data,
        source.stem
    )

    fields = collect_fields(data)

    buttons = collect_items(
        data,
        (
            "buttons",
            "actions",
            "available_actions",
            "page_actions"
        )
    )

    links = collect_items(
        data,
        (
            "links",
            "related_links",
            "related_doctypes",
            "link_fields"
        )
    )

    workflows = collect_items(
        data,
        (
            "workflows",
            "workflow",
            "statuses",
            "status_options"
        )
    )

    routes = collect_items(
        data,
        (
            "url",
            "route",
            "href",
            "path"
        )
    )

    mandatory_fields = [
        field
        for field in fields
        if field.get("mandatory")
    ]

    link_fields = [
        field
        for field in fields
        if (
            str(field.get("type") or "").lower()
            in {
                "link",
                "link field",
                "reference"
            }
            or field.get("link_doctype")
        )
    ]

    return {
        "doctype": doctype,

        "source_file": str(source),

        "discovered_at":
            datetime.now(timezone.utc).isoformat(),

        "fields": fields,

        "mandatory_fields":
            mandatory_fields,

        "link_fields":
            link_fields,

        "buttons":
            buttons,

        "links":
            links,

        "workflows":
            workflows,

        "routes":
            routes
    }


def main():

    parser = argparse.ArgumentParser(
        description="Build ERPNext knowledge from discovery JSON"
    )

    parser.add_argument(
        "--input",
        default="data/discovery"
    )

    parser.add_argument(
        "--output",
        default="knowledge"
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():

        raise SystemExit(
            f"Discovery directory not found: {input_dir}"
        )

    files = sorted(
        input_dir.rglob("*.json")
    )

    if not files:

        raise SystemExit(
            f"No JSON files found in {input_dir}"
        )

    log(
        f"Found {len(files)} discovery file(s)"
    )

    doctypes = {}

    modules = set()

    routes = set()

    workflows = set()

    field_types = Counter()

    failed = []

    for source in files:

        log(
            f"Reading: {source}"
        )

        try:

            data = load_json(source)

            if isinstance(data, dict):

                for key in (
                    "module",
                    "module_name",
                    "workspace",
                    "workspace_name"
                ):

                    value = data.get(key)

                    if value:
                        modules.add(
                            str(value)
                        )

            knowledge = build_doctype(
                data,
                source
            )

            name = knowledge["doctype"]

            existing = doctypes.get(name)

            if (
                existing is None
                or len(json.dumps(knowledge))
                > len(json.dumps(existing))
            ):

                doctypes[name] = knowledge

            for route in knowledge["routes"]:
                routes.add(str(route))

            for workflow in knowledge["workflows"]:

                if isinstance(
                    workflow,
                    str
                ):
                    workflows.add(workflow)

                else:
                    workflows.add(
                        json.dumps(
                            workflow,
                            ensure_ascii=False
                        )
                    )

            for field in knowledge["fields"]:

                field_type = (
                    field.get("type")
                    or "unknown"
                )

                field_types[
                    str(field_type)
                ] += 1

        except Exception as exc:

            failed.append(
                {
                    "file": str(source),
                    "error": str(exc)
                }
            )

            log(
                f"WARNING: {source}: {exc}"
            )

    # ----------------------------------------
    # Individual DocType knowledge
    # ----------------------------------------

    for name, knowledge in sorted(
        doctypes.items()
    ):

        filename = (
            safe_name(name)
            + ".json"
        )

        save_json(
            output_dir
            / "doctypes"
            / filename,
            knowledge
        )

    # ----------------------------------------
    # DocType index
    # ----------------------------------------

    doctype_index = []

    for name, knowledge in sorted(
        doctypes.items()
    ):

        doctype_index.append(
            {
                "doctype": name,

                "field_count":
                    len(knowledge["fields"]),

                "mandatory_field_count":
                    len(
                        knowledge[
                            "mandatory_fields"
                        ]
                    ),

                "link_field_count":
                    len(
                        knowledge[
                            "link_fields"
                        ]
                    ),

                "buttons":
                    knowledge["buttons"],

                "routes":
                    knowledge["routes"]
            }
        )

    save_json(
        output_dir
        / "doctypes"
        / "index.json",
        doctype_index
    )

    # ----------------------------------------
    # Summary
    # ----------------------------------------

    summary = {

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source_directory":
            str(input_dir),

        "source_files":
            len(files),

        "doctypes":
            len(doctypes),

        "modules":
            sorted(modules),

        "routes":
            sorted(routes),

        "workflows":
            sorted(workflows),

        "field_types":
            dict(field_types),

        "failed_files":
            failed
    }

    save_json(
        output_dir
        / "knowledge_summary.json",
        summary
    )

    # ----------------------------------------
    # Global index
    # ----------------------------------------

    save_json(
        output_dir
        / "index.json",
        {
            "generated_at":
                summary["generated_at"],

            "doctypes":
                sorted(doctypes.keys()),

            "modules":
                sorted(modules),

            "paths": {
                "doctypes":
                    "doctypes/",

                "summary":
                    "knowledge_summary.json"
            }
        }
    )

    # ----------------------------------------
    # Final output
    # ----------------------------------------

    log("")
    log("======================================")
    log("KNOWLEDGE BUILD FINISHED")
    log("======================================")

    log(
        f"Discovery files : {len(files)}"
    )

    log(
        f"DocTypes        : {len(doctypes)}"
    )

    log(
        f"Modules         : {len(modules)}"
    )

    log(
        f"Field types     : {dict(field_types)}"
    )

    log(
        f"Failed files    : {len(failed)}"
    )

    log(
        f"Knowledge path  : {output_dir.resolve()}"
    )

    log("======================================")


if __name__ == "__main__":
    main()