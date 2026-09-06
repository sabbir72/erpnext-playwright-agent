import json
import re
import time
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"

KNOWLEDGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

# UI elements that should NEVER become QA targets
IGNORED_UI_TERMS = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
    "bell",
    # "help",
    # "search",
    # "settings",
    # "filter",
    # "filters",
    # "load more",
    # "list view",
    "kanban",
    # "calendar",
    # "dashboard",
}


# ============================================================
# LOG
# ============================================================


def log(message):
    print(
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}",
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


def normalize_key(value):
    return clean(value).lower()


def is_ignored_ui(value):
    """
    Detect notification/search/help/settings type UI.
    """

    text = normalize_key(value)

    if not text:
        return True

    if text in IGNORED_UI_TERMS:
        return True

    # Notification variations
    notification_words = [
        "notification",
        "notifications",
        "no new notification",
        "no new notifications",
        "notification icon",
    ]

    for word in notification_words:
        if word in text:
            return True

    # Generic system controls
    generic_words = [
        "search",
        "help",
        "settings",
    ]

    for word in generic_words:
        if text == word:
            return True

    return False


def clean_options(options):
    """
    Normalize Select/Link options.
    """

    if not options:
        return []

    result = []
    seen = set()

    if not isinstance(options, list):
        options = [options]

    for option in options:

        if isinstance(option, dict):

            text = clean(
                option.get("text") or option.get("label") or option.get("value")
            )

            value = clean(
                option.get("value") or option.get("text") or option.get("label")
            )

        else:

            text = clean(option)
            value = text

        if not text:
            continue

        if is_ignored_ui(text):
            continue

        key = f"{text.lower()}::{value.lower()}"

        if key in seen:
            continue

        seen.add(key)

        result.append(
            {
                "text": text,
                "value": value,
            }
        )

    return result


def normalize_fieldtype(fieldtype):
    """
    Normalize field types so downstream Planner/Test Generator
    receives predictable values.
    """

    value = clean(fieldtype)

    if not value:
        return "Unknown"

    mapping = {
        "data": "Data",
        "text": "Text",
        "textarea": "Text",
        "small text": "Small Text",
        "long text": "Long Text",
        "select": "Select",
        "link": "Link",
        "dynamic link": "Dynamic Link",
        "date": "Date",
        "datetime": "Datetime",
        "datetime-local": "Datetime",
        "time": "Time",
        "check": "Check",
        "checkbox": "Check",
        "float": "Float",
        "number": "Float",
        "currency": "Currency",
        "int": "Int",
        "integer": "Int",
        "percent": "Percent",
        "email": "Data",
        "phone": "Data",
        "password": "Password",
        "attach": "Attach",
        "attach image": "Attach Image",
        "table": "Table",
        "table multiselect": "Table MultiSelect",
        "html": "HTML",
        "read only": "Read Only",
        "section break": "Section Break",
        "column break": "Column Break",
        "heading": "Heading",
    }

    return mapping.get(
        value.lower(),
        value,
    )


def normalize_required(field):
    """
    Support both:
        reqd
        required
        mandatory
    """

    value = field.get("reqd")

    if value is None:
        value = field.get("required")

    if value is None:
        value = field.get("mandatory")

    if isinstance(value, str):

        return value.lower() in {
            "true",
            "1",
            "yes",
            "required",
            "mandatory",
        }

    return bool(value)


def normalize_read_only(field):
    value = field.get("read_only")

    if value is None:
        value = field.get("readonly")

    if isinstance(value, str):

        return value.lower() in {
            "true",
            "1",
            "yes",
        }

    return bool(value)


def normalize_hidden(field):
    value = field.get("hidden")

    if isinstance(value, str):

        return value.lower() in {
            "true",
            "1",
            "yes",
        }

    return bool(value)


# ============================================================
# LOAD JSON
# ============================================================


def load_json(path):

    try:

        return json.loads(path.read_text(encoding="utf-8"))

    except Exception as exc:

        log(f"SKIP INVALID JSON: " f"{path.name} -> {exc}")

        return None


# ============================================================
# NORMALIZE FIELD
# ============================================================


def normalize_field(field):

    if not isinstance(
        field,
        dict,
    ):
        return None

    fieldname = clean(field.get("fieldname") or field.get("name"))

    if not fieldname:
        return None

    label = clean(field.get("label") or fieldname)

    fieldtype = normalize_fieldtype(field.get("fieldtype"))

    options = clean_options(
        field.get(
            "options",
            [],
        )
    )

    required = normalize_required(field)

    read_only = normalize_read_only(field)

    hidden = normalize_hidden(field)

    return {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "value": field.get(
            "value",
            "",
        ),
        "options": options,
        "required": required,
        "read_only": read_only,
        "hidden": hidden,
        "testable": not hidden,
    }


# ============================================================
# NORMALIZE FIELDS
# ============================================================


def normalize_fields(raw_fields):

    fields = []
    seen = set()

    if not isinstance(
        raw_fields,
        list,
    ):
        return fields

    for raw_field in raw_fields:

        field = normalize_field(raw_field)

        if not field:
            continue

        key = normalize_key(field["fieldname"])

        if key in seen:
            log(f"DUPLICATE FIELD SKIPPED: " f"{field['fieldname']}")
            continue

        seen.add(key)

        fields.append(field)

    return fields


# ============================================================
# NORMALIZE TABS
# ============================================================


def normalize_tabs(raw_tabs):

    tabs = []
    seen = set()

    if not isinstance(
        raw_tabs,
        list,
    ):
        return tabs

    for tab in raw_tabs:

        if isinstance(
            tab,
            dict,
        ):

            label = clean(tab.get("label") or tab.get("text") or tab.get("name"))

        else:

            label = clean(tab)

        if not label:
            continue

        if is_ignored_ui(label):
            continue

        key = label.lower()

        if key in seen:
            continue

        seen.add(key)

        tabs.append(
            {
                "label": label,
                "testable": True,
            }
        )

    return tabs


# ============================================================
# NORMALIZE SECTIONS
# ============================================================


def normalize_sections(raw_sections):

    sections = []
    seen = set()

    if not isinstance(
        raw_sections,
        list,
    ):
        return sections

    for section in raw_sections:

        if isinstance(
            section,
            dict,
        ):

            label = clean(
                section.get("label") or section.get("text") or section.get("name")
            )

        else:

            label = clean(section)

        if not label:
            continue

        if is_ignored_ui(label):
            continue

        key = label.lower()

        if key in seen:
            continue

        seen.add(key)

        sections.append(
            {
                "label": label,
                "testable": True,
            }
        )

    return sections


# ============================================================
# NORMALIZE BUTTONS
# ============================================================


def normalize_buttons(raw_buttons):

    buttons = []
    seen = set()

    if not isinstance(
        raw_buttons,
        list,
    ):
        return buttons

    for button in raw_buttons:

        if isinstance(
            button,
            dict,
        ):

            text = clean(
                button.get("text") or button.get("label") or button.get("name")
            )

            action = clean(button.get("action") or button.get("href") or "")

        else:

            text = clean(button)
            action = ""

        if not text:
            continue

        if is_ignored_ui(text):
            continue

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)

        buttons.append(
            {
                "text": text,
                "action": action,
                "testable": True,
            }
        )

    return buttons


# ============================================================
# NORMALIZE LINKS
# ============================================================


def normalize_links(raw_links):

    links = []
    seen = set()

    if not isinstance(
        raw_links,
        list,
    ):
        return links

    for link in raw_links:

        if not isinstance(
            link,
            dict,
        ):
            continue

        text = clean(link.get("text"))

        href = clean(link.get("href"))

        if is_ignored_ui(text):
            continue

        if not text and not href:
            continue

        key = f"{text.lower()}::{href.lower()}"

        if key in seen:
            continue

        seen.add(key)

        links.append(
            {
                "text": text,
                "href": href,
            }
        )

    return links


# ============================================================
# BUILD ACTIONS
# ============================================================


def build_actions(
    fields,
    buttons,
    tabs,
):

    actions = []

    # --------------------------------------------------------
    # Field actions
    # --------------------------------------------------------

    for field in fields:

        if not field.get("testable"):
            continue

        fieldname = field["fieldname"]
        fieldtype = field["fieldtype"]
        label = field["label"]

        actions.append(
            {
                "action": "verify_visible",
                "target": label,
                "fieldname": fieldname,
                "fieldtype": fieldtype,
            }
        )

        if field.get("required"):

            actions.append(
                {
                    "action": "validate_required",
                    "target": label,
                    "fieldname": fieldname,
                    "fieldtype": fieldtype,
                }
            )

        if fieldtype == "Select":

            for option in field.get(
                "options",
                [],
            ):

                actions.append(
                    {
                        "action": "select_option",
                        "target": label,
                        "fieldname": fieldname,
                        "fieldtype": fieldtype,
                        "option": option["value"],
                    }
                )

        elif fieldtype in {
            "Link",
            "Dynamic Link",
        }:

            actions.append(
                {
                    "action": "select_link",
                    "target": label,
                    "fieldname": fieldname,
                    "fieldtype": fieldtype,
                }
            )

    # --------------------------------------------------------
    # Button actions
    # --------------------------------------------------------

    for button in buttons:

        actions.append(
            {
                "action": "click",
                "target": button["text"],
                "button": button["text"],
            }
        )

    # --------------------------------------------------------
    # Tab actions
    # --------------------------------------------------------

    for tab in tabs:

        actions.append(
            {
                "action": "open_tab",
                "target": tab["label"],
            }
        )

    return actions


# ============================================================
# TEST HINTS
# ============================================================


def build_test_hints(
    fields,
    tabs,
    sections,
    buttons,
    actions,
):

    required_fields = [field["fieldname"] for field in fields if field.get("required")]

    select_fields = [
        field["fieldname"] for field in fields if field.get("fieldtype") == "Select"
    ]

    link_fields = [
        field["fieldname"]
        for field in fields
        if field.get("fieldtype")
        in {
            "Link",
            "Dynamic Link",
        }
    ]

    return {
        "field_count": len(fields),
        "required_field_count": len(required_fields),
        "required_fields": required_fields,
        "select_field_count": len(select_fields),
        "select_fields": select_fields,
        "link_field_count": len(link_fields),
        "link_fields": link_fields,
        "tab_count": len(tabs),
        "section_count": len(sections),
        "button_count": len(buttons),
        "action_count": len(actions),
        "has_tabs": bool(tabs),
        "has_sections": bool(sections),
        "has_buttons": bool(buttons),
    }


# ============================================================
# BUILD DOCTYPE KNOWLEDGE
# ============================================================


def build_doctype_knowledge(data):

    doctype = clean(data.get("doctype") or data.get("document_name"))

    if not doctype:
        return None

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    fields = normalize_fields(data.get("fields", []))

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    tabs = normalize_tabs(data.get("tabs", []))

    # --------------------------------------------------------
    # Sections
    # --------------------------------------------------------

    sections = normalize_sections(data.get("sections", []))

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    buttons = normalize_buttons(data.get("buttons", []))

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    links = normalize_links(data.get("links", []))

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

    actions = build_actions(
        fields,
        buttons,
        tabs,
    )

    # --------------------------------------------------------
    # Test hints
    # --------------------------------------------------------

    test_hints = build_test_hints(
        fields,
        tabs,
        sections,
        buttons,
        actions,
    )

    # --------------------------------------------------------
    # Knowledge
    # --------------------------------------------------------

    knowledge = {
        "knowledge_type": "erpnext_doctype",
        "doctype": doctype,
        "module": clean(data.get("module")),
        "source_file": "",
        "read_mode": data.get(
            "read_mode",
            "unknown",
        ),
        "url": data.get(
            "url",
            "",
        ),
        "title": data.get(
            "title",
            "",
        ),
        # ----------------------------------------------------
        # Structured document model
        # ----------------------------------------------------
        "structure": {
            "fields": fields,
            "tabs": tabs,
            "sections": sections,
            "buttons": buttons,
            "actions": actions,
        },
        # ----------------------------------------------------
        # Top-level compatibility
        # ----------------------------------------------------
        "fields": fields,
        "tabs": tabs,
        "sections": sections,
        "buttons": buttons,
        "actions": actions,
        # ----------------------------------------------------
        # Links
        # ----------------------------------------------------
        "links": links,
        # ----------------------------------------------------
        # Raw discovery information
        # ----------------------------------------------------
        "raw_text": clean(
            data.get(
                "text",
                "",
            )
        ),
        # ----------------------------------------------------
        # Test information
        # ----------------------------------------------------
        "test_hints": test_hints,
    }

    return knowledge


# ============================================================
# BUILD INDEX
# ============================================================


def build_index(documents):

    index = {
        "knowledge_type": "erpnext_knowledge_index",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_doctypes": len(documents),
        "doctypes": [],
        "modules": {},
    }

    for doc in documents:

        doctype = doc["doctype"]

        module = clean(doc.get("module"))

        entry = {
            "doctype": doctype,
            "module": module,
            "field_count": doc["test_hints"]["field_count"],
            "required_field_count": doc["test_hints"]["required_field_count"],
            "action_count": doc["test_hints"]["action_count"],
        }

        index["doctypes"].append(entry)

        if module:

            index["modules"].setdefault(module, [])

            index["modules"][module].append(doctype)

    return index


# ============================================================
# SAFE FILENAME
# ============================================================


def safe_filename(value):

    filename = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        clean(value).lower(),
    ).strip("-")

    return filename or "unknown"


# ============================================================
# MAIN BUILDER
# ============================================================


def main():

    log("======================================")

    log("ERPNext KNOWLEDGE BUILDER")

    log("======================================")

    log(f"Discovery directory: " f"{DISCOVERY_DIR}")

    # --------------------------------------------------------
    # Discovery files
    # --------------------------------------------------------

    files = sorted(DISCOVERY_DIR.glob("*.json"))

    if not files:

        log("No discovery JSON files found.")

        return

    log(f"Discovery files found: " f"{len(files)}")

    documents = []

    seen_doctypes = set()

    # --------------------------------------------------------
    # READ ALL DISCOVERY FILES
    # --------------------------------------------------------

    for path in files:

        log(f"Reading: {path.name}")

        data = load_json(path)

        if not data:
            continue

        knowledge = build_doctype_knowledge(data)

        if not knowledge:
            continue

        doctype = clean(knowledge["doctype"])

        key = doctype.lower()

        # ----------------------------------------------------
        # Duplicate DocType
        # ----------------------------------------------------

        if key in seen_doctypes:

            log(f"DUPLICATE DOCTYPE " f"SKIPPED: {doctype}")

            continue

        seen_doctypes.add(key)

        knowledge["source_file"] = path.name

        documents.append(knowledge)

        log(f"Loaded DocType: " f"{doctype}")

        log(f"  Fields: " f"{len(knowledge['fields'])}")

        log(f"  Required: " f"{knowledge['test_hints']['required_field_count']}")

        log(f"  Tabs: " f"{len(knowledge['tabs'])}")

        log(f"  Sections: " f"{len(knowledge['sections'])}")

        log(f"  Buttons: " f"{len(knowledge['buttons'])}")

        log(f"  Actions: " f"{len(knowledge['actions'])}")

    # --------------------------------------------------------
    # BUILD INDEX
    # --------------------------------------------------------

    index = build_index(documents)

    # --------------------------------------------------------
    # FULL KNOWLEDGE DB
    # --------------------------------------------------------

    knowledge_path = KNOWLEDGE_DIR / "erpnext_knowledge.json"

    knowledge_db = {
        "knowledge_type": "erpnext_knowledge_base",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_doctypes": len(documents),
        "documents": documents,
    }

    knowledge_path.write_text(
        json.dumps(
            knowledge_db,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    index_path = KNOWLEDGE_DIR / "index.json"

    index_path.write_text(
        json.dumps(
            index,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # INDIVIDUAL KNOWLEDGE
    # --------------------------------------------------------

    individual_dir = KNOWLEDGE_DIR / "doctypes"

    individual_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for doc in documents:

        filename = safe_filename(doc["doctype"]) + ".json"

        path = individual_dir / filename

        path.write_text(
            json.dumps(
                doc,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    log("======================================")

    log("KNOWLEDGE BUILD COMPLETED")

    log(f"Total DocTypes: " f"{len(documents)}")

    log(f"Knowledge DB: " f"{knowledge_path}")

    log(f"Index: " f"{index_path}")

    log(f"Individual knowledge: " f"{individual_dir}")

    log("======================================")


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()
