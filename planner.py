# import argparse
# import json
# import re
# import time
# from pathlib import Path

# # ============================================================
# # CONFIG
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent

# DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
# PLAN_DIR = BASE_DIR / "data" / "plans"

# PLAN_DIR.mkdir(
#     parents=True,
#     exist_ok=True,
# )

# PLAN_FILE = PLAN_DIR / "latest_plan.json"


# # ============================================================
# # LOG
# # ============================================================


# def log(message):
#     print(
#         f"[PLANNER] {message}",
#         flush=True,
#     )


# # ============================================================
# # HELPERS
# # ============================================================


# def clean(value):
#     if value is None:
#         return ""

#     return re.sub(
#         r"\s+",
#         " ",
#         str(value),
#     ).strip()


# def slugify(value):
#     value = clean(value).lower()

#     value = re.sub(
#         r"[^a-z0-9]+",
#         "-",
#         value,
#     )

#     return value.strip("-")


# def normalize(value):
#     return clean(value).lower()


# # ============================================================
# # DISCOVERY FILES
# # ============================================================


# def get_discovery_files():
#     """
#     Return all discovery JSON files.

#     Example:

#     data/discovery/
#         0001_company-budget.json
#         0002_budget-head.json
#         0003_import-lc.json
#     """

#     if not DISCOVERY_DIR.exists():
#         raise FileNotFoundError(f"Discovery directory not found:\n{DISCOVERY_DIR}")

#     files = list(DISCOVERY_DIR.glob("*.json"))

#     # Serial order
#     files.sort(key=lambda path: path.name.lower())

#     return files


# # ============================================================
# # LOAD ONE DISCOVERY FILE
# # ============================================================


# def load_discovery_file(path):
#     """
#     Load one discovery JSON safely.
#     """

#     try:
#         data = json.loads(path.read_text(encoding="utf-8"))

#     except json.JSONDecodeError as exc:
#         log(f"Invalid JSON skipped: " f"{path.name} -> {exc}")
#         return None

#     except Exception as exc:
#         log(f"Could not read: " f"{path.name} -> {exc}")
#         return None

#     if not isinstance(data, dict):
#         log(f"Invalid discovery structure skipped: " f"{path.name}")
#         return None

#     return data


# # ============================================================
# # LOAD ALL DISCOVERY
# # ============================================================


# def load_discovery():
#     """
#     Load every discovery JSON.

#     IMPORTANT:
#     Broken/invalid files are skipped.
#     """

#     documents = []

#     files = get_discovery_files()

#     log(f"Discovery files found: {len(files)}")

#     for path in files:

#         data = load_discovery_file(path)

#         if not data:
#             continue

#         doctype = clean(data.get("doctype") or data.get("document_name") or "")

#         if not doctype:
#             log(f"SKIP: no DocType -> {path.name}")
#             continue

#         # Store actual source filename
#         data["source_file"] = path.name

#         # Store absolute source path
#         data["source_path"] = str(path)

#         # Normalize module
#         data["module"] = clean(data.get("module", ""))

#         documents.append(data)

#         log(f"Loaded: {doctype} " f"-> {path.name}")

#     return documents


# # ============================================================
# # FIND DOCTYPE
# # ============================================================


# def find_doctype(
#     documents,
#     target,
# ):
#     """
#     Find DocType by:

#     1. Exact name
#     2. Filename slug
#     3. Partial name
#     """

#     target = clean(target)

#     if not target:
#         return None

#     target_normalized = normalize(target)
#     target_slug = slugify(target)

#     # --------------------------------------------------------
#     # Exact DocType
#     # --------------------------------------------------------

#     for doc in documents:

#         doctype = clean(doc.get("doctype") or doc.get("document_name") or "")

#         if normalize(doctype) == target_normalized:
#             return doc

#     # --------------------------------------------------------
#     # Filename
#     # --------------------------------------------------------

#     for doc in documents:

#         source_file = clean(doc.get("source_file", ""))

#         if not source_file:
#             continue

#         stem = Path(source_file).stem

#         match = re.match(
#             r"^\d+_(.+)$",
#             stem,
#         )

#         if not match:
#             continue

#         file_slug = match.group(1)

#         if file_slug.lower() == target_slug:
#             return doc

#     # --------------------------------------------------------
#     # Partial match
#     # --------------------------------------------------------

#     matches = []

#     for doc in documents:

#         doctype = clean(doc.get("doctype") or doc.get("document_name") or "")

#         if not doctype:
#             continue

#         current = normalize(doctype)

#         if target_normalized in current or current in target_normalized:
#             matches.append(doc)

#     if len(matches) == 1:
#         return matches[0]

#     return None


# # ============================================================
# # FIND MODULE
# # ============================================================


# def find_module(
#     documents,
#     module_name,
# ):
#     """
#     Find every discovered DocType
#     belonging to a module.
#     """

#     target = normalize(module_name)

#     if not target:
#         return []

#     matches = []

#     # --------------------------------------------------------
#     # Exact module
#     # --------------------------------------------------------

#     for doc in documents:

#         module = normalize(doc.get("module", ""))

#         if module == target:
#             matches.append(doc)

#     if matches:
#         return matches

#     # --------------------------------------------------------
#     # Partial module
#     # --------------------------------------------------------

#     for doc in documents:

#         module = normalize(doc.get("module", ""))

#         if not module:
#             continue

#         if target in module or module in target:
#             matches.append(doc)

#     return matches


# # ============================================================
# # AVAILABLE DOCTYPES
# # ============================================================


# def available_doctypes(documents):

#     result = []

#     for doc in documents:

#         name = clean(doc.get("doctype") or doc.get("document_name") or "")

#         if name:
#             result.append(name)

#     return result


# # ============================================================
# # AVAILABLE MODULES
# # ============================================================


# def available_modules(documents):

#     modules = []

#     for doc in documents:

#         module = clean(doc.get("module", ""))

#         if module and module not in modules:
#             modules.append(module)

#     return sorted(modules, key=lambda value: value.lower())


# # ============================================================
# # DETECT TASK TYPE
# # ============================================================


# def detect_task_type(command):

#     text = normalize(command)

#     # --------------------------------------------------------
#     # Regression
#     # --------------------------------------------------------

#     if any(
#         word in text
#         for word in [
#             "regression",
#             "regression test",
#         ]
#     ):
#         return "regression_test"

#     # --------------------------------------------------------
#     # Generate test cases
#     # --------------------------------------------------------

#     if any(
#         word in text
#         for word in [
#             "generate test",
#             "generate test case",
#             "generate test cases",
#             "test case",
#             "test cases",
#         ]
#     ):
#         return "generate_test_cases"

#     # --------------------------------------------------------
#     # Functional testing
#     # --------------------------------------------------------

#     if any(
#         word in text
#         for word in [
#             "test",
#             "testing",
#             "execute",
#             "run",
#             "verify",
#             "validate",
#         ]
#     ):
#         return "functional_test"

#     # --------------------------------------------------------
#     # Discovery
#     # --------------------------------------------------------

#     if any(
#         word in text
#         for word in [
#             "discover",
#             "read",
#             "scan",
#         ]
#     ):
#         return "discovery"

#     return "unknown"


# # ============================================================
# # DETECT EXPLICIT DOCTYPE
# # ============================================================


# def detect_doctype_from_command(
#     command,
#     documents,
# ):
#     """
#     Detect the most likely DocType
#     from natural language command.

#     Longest names first prevents:

#     "Budget"

#     from matching before:

#     "Company Budget"
#     """

#     text = normalize(command)

#     candidates = []

#     for doc in documents:

#         doctype = clean(doc.get("doctype") or doc.get("document_name") or "")

#         if doctype:
#             candidates.append(doctype)

#     # Longest first
#     candidates.sort(
#         key=len,
#         reverse=True,
#     )

#     for doctype in candidates:

#         if normalize(doctype) in text:
#             return doctype

#     return None


# # ============================================================
# # DETECT MODULE
# # ============================================================


# def detect_module_from_command(
#     command,
#     documents,
# ):
#     """
#     Detect module from natural language.
#     """

#     text = normalize(command)

#     modules = available_modules(documents)

#     modules.sort(
#         key=len,
#         reverse=True,
#     )

#     for module in modules:

#         if normalize(module) in text:
#             return module

#     return None


# # ============================================================
# # DETECT TARGET
# # ============================================================


# def detect_target(
#     command,
#     documents,
# ):
#     """
#     Priority:

#     1. Explicit/known DocType
#     2. Module
#     3. Unknown
#     """

#     # --------------------------------------------------------
#     # DocType
#     # --------------------------------------------------------

#     doctype = detect_doctype_from_command(
#         command,
#         documents,
#     )

#     if doctype:

#         knowledge = find_doctype(
#             documents,
#             doctype,
#         )

#         if knowledge:

#             return {
#                 "target_type": "doctype",
#                 "target": doctype,
#                 "knowledge": knowledge,
#             }

#     # --------------------------------------------------------
#     # Module
#     # --------------------------------------------------------

#     module = detect_module_from_command(
#         command,
#         documents,
#     )

#     if module:

#         module_docs = find_module(
#             documents,
#             module,
#         )

#         return {
#             "target_type": "module",
#             "target": module,
#             "knowledge": module_docs,
#         }

#     # --------------------------------------------------------
#     # Unknown
#     # --------------------------------------------------------

#     return {
#         "target_type": "unknown",
#         "target": "",
#         "knowledge": [],
#     }


# # ============================================================
# # NORMALIZE DISCOVERY STRUCTURE
# # ============================================================


# def get_structure(doc):
#     """
#     Discovery Agent currently stores:

#         fields
#         tabs
#         sections
#         buttons

#     directly at root.

#     Older discovery files may have
#     a structure object.

#     Support both.
#     """

#     structure = doc.get("structure", {})

#     if not isinstance(
#         structure,
#         dict,
#     ):
#         structure = {}

#     fields = doc.get("fields")

#     if not isinstance(
#         fields,
#         list,
#     ):
#         fields = structure.get("fields", [])

#     tabs = doc.get("tabs")

#     if not isinstance(
#         tabs,
#         list,
#     ):
#         tabs = structure.get("tabs", [])

#     sections = doc.get("sections")

#     if not isinstance(
#         sections,
#         list,
#     ):
#         sections = structure.get("sections", [])

#     buttons = doc.get("buttons")

#     if not isinstance(
#         buttons,
#         list,
#     ):
#         buttons = structure.get("buttons", [])

#     return (
#         fields,
#         tabs,
#         sections,
#         buttons,
#     )


# # ============================================================
# # FIELD NORMALIZATION
# # ============================================================


# def normalize_fields(fields):

#     result = []

#     if not isinstance(
#         fields,
#         list,
#     ):
#         return result

#     for field in fields:

#         if not isinstance(
#             field,
#             dict,
#         ):
#             continue

#         fieldname = clean(field.get("fieldname", ""))

#         if not fieldname:
#             continue

#         normalized = {
#             "fieldname": fieldname,
#             "label": clean(field.get("label") or fieldname),
#             "fieldtype": clean(field.get("fieldtype", "")),
#             "value": field.get("value", ""),
#             "options": field.get("options", []),
#         }

#         # Preserve extra metadata
#         for key in [
#             "reqd",
#             "read_only",
#             "hidden",
#             "depends_on",
#             "mandatory",
#             "description",
#         ]:

#             if key in field:
#                 normalized[key] = field[key]

#         result.append(normalized)

#     return result


# # ============================================================
# # STRUCTURE NORMALIZATION
# # ============================================================


# def normalize_names(values):

#     result = []

#     if not isinstance(
#         values,
#         list,
#     ):
#         return result

#     for item in values:

#         if isinstance(
#             item,
#             dict,
#         ):

#             value = clean(
#                 item.get("label") or item.get("text") or item.get("name") or ""
#             )

#         else:

#             value = clean(item)

#         if value:
#             result.append(value)

#     return result


# # ============================================================
# # BUTTON NORMALIZATION
# # ============================================================


# def normalize_buttons(buttons):

#     result = []

#     if not isinstance(
#         buttons,
#         list,
#     ):
#         return result

#     for button in buttons:

#         if isinstance(
#             button,
#             dict,
#         ):

#             name = clean(
#                 button.get("text") or button.get("label") or button.get("name") or ""
#             )

#         else:

#             name = clean(button)

#         if name:
#             result.append(name)

#     return result


# # ============================================================
# # BUILD DOCTYPE PLAN
# # ============================================================


# def build_doctype_plan(
#     task_type,
#     doc,
# ):
#     """
#     Convert one discovery JSON
#     into an execution-ready plan.
#     """

#     doctype = clean(doc.get("doctype") or doc.get("document_name") or "")

#     (
#         raw_fields,
#         raw_tabs,
#         raw_sections,
#         raw_buttons,
#     ) = get_structure(doc)

#     fields = normalize_fields(raw_fields)

#     tabs = normalize_names(raw_tabs)

#     sections = normalize_names(raw_sections)

#     buttons = normalize_buttons(raw_buttons)

#     return {
#         "task_type": task_type,
#         "target_type": "doctype",
#         "target": doctype,
#         "source_file": doc.get("source_file", ""),
#         "source_path": doc.get("source_path", ""),
#         "execution": {
#             "open_doctype": True,
#             "open_list_view": True,
#             "click_add_new": True,
#             "open_blank_document": True,
#             "read_all_fields": True,
#             "read_tabs": bool(tabs),
#             "read_sections": bool(sections),
#             "read_buttons": bool(buttons),
#             "test_all_fields": bool(fields),
#             "test_buttons": bool(buttons),
#             "test_tabs": bool(tabs),
#             "test_sections": bool(sections),
#             "save_document": False,
#             "submit_document": False,
#             "delete_document": False,
#         },
#         "navigation": {
#             "url": doc.get("url", ""),
#             "doctype": doctype,
#             "open_method": "list_then_add",
#             "add_button": f"Add {doctype}",
#         },
#         "knowledge": {
#             "doctype": doctype,
#             "module": clean(doc.get("module", "")),
#             "field_count": len(fields),
#             "fields": fields,
#             "tab_count": len(tabs),
#             "tabs": tabs,
#             "section_count": len(sections),
#             "sections": sections,
#             "button_count": len(buttons),
#             "buttons": buttons,
#             "url": doc.get("url", ""),
#             "title": doc.get("title", ""),
#             "read_mode": doc.get("read_mode", ""),
#             "existing_documents_skipped": doc.get("existing_documents_skipped", True),
#             "discovery_file": doc.get("source_file", ""),
#         },
#         "next_step": "generate_test_cases",
#     }


# # ============================================================
# # BUILD MODULE PLAN
# # ============================================================


# def build_module_plan(
#     task_type,
#     module_name,
#     docs,
# ):
#     """
#     Build a plan for ALL discovered
#     DocTypes in the selected module.
#     """

#     targets = []

#     for doc in docs:

#         doctype = clean(doc.get("doctype") or doc.get("document_name") or "")

#         if not doctype:
#             continue

#         targets.append(
#             build_doctype_plan(
#                 task_type,
#                 doc,
#             )
#         )

#     return {
#         "task_type": task_type,
#         "target_type": "module",
#         "target": module_name,
#         "execution": {
#             "process_all_doctypes": True,
#             "skip_existing_discovery": True,
#             "skip_missing_knowledge": True,
#             "continue_on_failure": True,
#             "open_each_doctype": True,
#             "click_add_new_for_each": True,
#             "read_all_fields": True,
#         },
#         "doctype_count": len(targets),
#         "doctypes": targets,
#         "next_step": "generate_test_cases",
#     }


# # ============================================================
# # CREATE PLAN
# # ============================================================


# def create_plan(
#     command,
# ):
#     """
#     Main planning engine.
#     """

#     documents = load_discovery()

#     if not documents:

#         raise RuntimeError(
#             "No valid discovery JSON files found.\n\n" f"Directory:\n{DISCOVERY_DIR}"
#         )

#     task_type = detect_task_type(command)

#     target = detect_target(
#         command,
#         documents,
#     )

#     # --------------------------------------------------------
#     # UNKNOWN
#     # --------------------------------------------------------

#     if target["target_type"] == "unknown":

#         return {
#             "status": "needs_clarification",
#             "command": command,
#             "task_type": task_type,
#             "target_type": "unknown",
#             "message": ("Could not identify a known " "ERPNext DocType or Module."),
#             "available_doctypes": available_doctypes(documents),
#             "available_modules": available_modules(documents),
#             "next_step": "ask_user",
#         }

#     # --------------------------------------------------------
#     # DOCTYPE
#     # --------------------------------------------------------

#     if target["target_type"] == "doctype":

#         plan = build_doctype_plan(
#             task_type,
#             target["knowledge"],
#         )

#         return {
#             "status": "ready",
#             "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "command": command,
#             "source": "data/discovery",
#             "plan": plan,
#         }

#     # --------------------------------------------------------
#     # MODULE
#     # --------------------------------------------------------

#     if target["target_type"] == "module":

#         plan = build_module_plan(
#             task_type,
#             target["target"],
#             target["knowledge"],
#         )

#         return {
#             "status": "ready",
#             "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#             "command": command,
#             "source": "data/discovery",
#             "plan": plan,
#         }

#     return {
#         "status": "error",
#         "message": "Unknown planner state.",
#     }


# # ============================================================
# # SAVE PLAN
# # ============================================================


# def save_plan(plan):

#     PLAN_FILE.write_text(
#         json.dumps(
#             plan,
#             indent=2,
#             ensure_ascii=False,
#         ),
#         encoding="utf-8",
#     )

#     log(f"Plan saved: {PLAN_FILE}")

#     return PLAN_FILE


# # ============================================================
# # PRINT SUMMARY
# # ============================================================


# def print_summary(plan):

#     if plan.get("status") != "ready":

#         log(f"Status: {plan.get('status')}")

#         return

#     data = plan.get("plan", {})

#     target_type = data.get("target_type")

#     target = data.get("target", "")

#     log(f"Target type: {target_type}")

#     log(f"Target: {target}")

#     if target_type == "doctype":

#         knowledge = data.get("knowledge", {})

#         log(f"Fields: " f"{knowledge.get('field_count', 0)}")

#         log(f"Tabs: " f"{knowledge.get('tab_count', 0)}")

#         log(f"Sections: " f"{knowledge.get('section_count', 0)}")

#         log(f"Buttons: " f"{knowledge.get('button_count', 0)}")

#         log(f"Source: " f"{data.get('source_file', '')}")

#     elif target_type == "module":

#         doctypes = data.get("doctypes", [])

#         log(f"DocTypes: " f"{len(doctypes)}")

#         for index, item in enumerate(
#             doctypes,
#             start=1,
#         ):

#             log(
#                 f"{index}. "
#                 f"{item.get('target', '')} "
#                 f"-> "
#                 f"{item.get('source_file', '')}"
#             )


# # ============================================================
# # ARGUMENTS
# # ============================================================


# def parse_args():

#     parser = argparse.ArgumentParser(description=("ERPNext AI QA Planner"))

#     # --------------------------------------------------------
#     # Natural language command
#     # --------------------------------------------------------

#     parser.add_argument(
#         "command",
#         nargs="*",
#         help=("Natural language QA command"),
#     )

#     # --------------------------------------------------------
#     # Direct DocType
#     # --------------------------------------------------------

#     parser.add_argument(
#         "--doctype",
#         required=False,
#         help=("Plan only this DocType."),
#     )

#     # --------------------------------------------------------
#     # Direct Module
#     # --------------------------------------------------------

#     parser.add_argument(
#         "--module",
#         required=False,
#         help=("Plan all discovered DocTypes " "inside this module."),
#     )

#     args = parser.parse_args()

#     # --------------------------------------------------------
#     # Direct options have priority
#     # --------------------------------------------------------

#     if args.doctype:

#         command = f"Generate test cases for " f"{args.doctype}"

#         return command

#     if args.module:

#         command = f"Generate test cases for " f"{args.module} module"

#         return command

#     # --------------------------------------------------------
#     # Natural language
#     # --------------------------------------------------------

#     if args.command:

#         return " ".join(args.command)

#     parser.error("Give a command, " "--doctype or --module.")


# # ============================================================
# # MAIN
# # ============================================================


# def main():

#     command = parse_args()

#     log("======================================")

#     log("ERPNext QA PLANNER")

#     log("======================================")

#     log(f"Command: {command}")

#     try:

#         plan = create_plan(command)

#         save_plan(plan)

#         print_summary(plan)

#         print(
#             json.dumps(
#                 plan,
#                 indent=2,
#                 ensure_ascii=False,
#             )
#         )

#     except Exception as exc:

#         log(f"ERROR: {exc}")

#         raise

#     log("======================================")

#     log("PLANNER FINISHED")

#     log("======================================")


# # ============================================================
# # ENTRY
# # ============================================================

# if __name__ == "__main__":
#     main()


#==========================


import argparse
import json
import re
import time
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
PLAN_DIR = BASE_DIR / "data" / "plans"

PLAN_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PLAN_FILE = PLAN_DIR / "latest_plan.json"


# ============================================================
# LOG
# ============================================================

def log(message):
    print(
        f"[PLANNER] {message}",
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

    return value.strip("-")


def normalize(value):
    return clean(value).lower()


# ============================================================
# NOTIFICATION KEYWORDS
# ============================================================

NOTIFICATION_KEYWORDS = {
    "notification",
    "notifications",
    "no new notifications",
    "notification icon",
    "bell",
}


def is_notification_item(value):
    """
    Identify notification-related UI items.

    These items are kept in Planner knowledge so that
    Test Case Generator / Executor can skip clicking them.
    """

    text = normalize(value)

    if not text:
        return False

    return text in NOTIFICATION_KEYWORDS


# ============================================================
# DISCOVERY FILES
# ============================================================

def get_discovery_files():

    if not DISCOVERY_DIR.exists():

        raise FileNotFoundError(
            f"Discovery directory not found:\n{DISCOVERY_DIR}"
        )

    files = list(
        DISCOVERY_DIR.glob("*.json")
    )

    files.sort(
        key=lambda path: path.name.lower()
    )

    return files


# ============================================================
# LOAD ONE DISCOVERY FILE
# ============================================================

def load_discovery_file(path):

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        log(
            f"Invalid JSON skipped: "
            f"{path.name} -> {exc}"
        )

        return None

    except Exception as exc:

        log(
            f"Could not read: "
            f"{path.name} -> {exc}"
        )

        return None

    if not isinstance(data, dict):

        log(
            f"Invalid discovery structure "
            f"skipped: {path.name}"
        )

        return None

    return data


# ============================================================
# LOAD ALL DISCOVERY
# ============================================================

def load_discovery():

    documents = []

    files = get_discovery_files()

    log(
        f"Discovery files found: "
        f"{len(files)}"
    )

    for path in files:

        data = load_discovery_file(path)

        if not data:
            continue

        doctype = clean(
            data.get("doctype")
            or data.get("document_name")
            or ""
        )

        if not doctype:

            log(
                f"SKIP: no DocType -> "
                f"{path.name}"
            )

            continue

        data["source_file"] = path.name

        data["source_path"] = str(path)

        data["module"] = clean(
            data.get("module", "")
        )

        documents.append(data)

        log(
            f"Loaded: {doctype} "
            f"-> {path.name}"
        )

    return documents


# ============================================================
# FIND DOCTYPE
# ============================================================

def find_doctype(
    documents,
    target,
):

    target = clean(target)

    if not target:
        return None

    target_normalized = normalize(target)

    target_slug = slugify(target)

    for doc in documents:

        doctype = clean(
            doc.get("doctype")
            or doc.get("document_name")
            or ""
        )

        if normalize(doctype) == target_normalized:

            return doc

    for doc in documents:

        source_file = clean(
            doc.get("source_file", "")
        )

        if not source_file:
            continue

        stem = Path(
            source_file
        ).stem

        match = re.match(
            r"^\d+_(.+)$",
            stem,
        )

        if not match:
            continue

        file_slug = match.group(1)

        if file_slug.lower() == target_slug:

            return doc

    matches = []

    for doc in documents:

        doctype = clean(
            doc.get("doctype")
            or doc.get("document_name")
            or ""
        )

        if not doctype:
            continue

        current = normalize(doctype)

        if (
            target_normalized in current
            or current in target_normalized
        ):

            matches.append(doc)

    if len(matches) == 1:

        return matches[0]

    return None


# ============================================================
# FIND MODULE
# ============================================================

def find_module(
    documents,
    module_name,
):

    target = normalize(module_name)

    if not target:
        return []

    matches = []

    for doc in documents:

        module = normalize(
            doc.get("module", "")
        )

        if module == target:

            matches.append(doc)

    if matches:
        return matches

    for doc in documents:

        module = normalize(
            doc.get("module", "")
        )

        if not module:
            continue

        if (
            target in module
            or module in target
        ):

            matches.append(doc)

    return matches


# ============================================================
# AVAILABLE DOCTYPES
# ============================================================

def available_doctypes(documents):

    result = []

    for doc in documents:

        name = clean(
            doc.get("doctype")
            or doc.get("document_name")
            or ""
        )

        if name:
            result.append(name)

    return result


# ============================================================
# AVAILABLE MODULES
# ============================================================

def available_modules(documents):

    modules = []

    for doc in documents:

        module = clean(
            doc.get("module", "")
        )

        if (
            module
            and module not in modules
        ):

            modules.append(module)

    return sorted(
        modules,
        key=lambda value: value.lower()
    )


# ============================================================
# DETECT TASK TYPE
# ============================================================

def detect_task_type(command):

    text = normalize(command)

    if any(
        word in text
        for word in [
            "regression",
            "regression test",
        ]
    ):

        return "regression_test"

    if any(
        word in text
        for word in [
            "generate test",
            "generate test case",
            "generate test cases",
            "test case",
            "test cases",
        ]
    ):

        return "generate_test_cases"

    if any(
        word in text
        for word in [
            "test",
            "testing",
            "execute",
            "run",
            "verify",
            "validate",
        ]
    ):

        return "functional_test"

    if any(
        word in text
        for word in [
            "discover",
            "read",
            "scan",
        ]
    ):

        return "discovery"

    return "unknown"


# ============================================================
# DETECT EXPLICIT DOCTYPE
# ============================================================

def detect_doctype_from_command(
    command,
    documents,
):

    text = normalize(command)

    candidates = []

    for doc in documents:

        doctype = clean(
            doc.get("doctype")
            or doc.get("document_name")
            or ""
        )

        if doctype:

            candidates.append(doctype)

    candidates.sort(
        key=len,
        reverse=True
    )

    for doctype in candidates:

        if normalize(doctype) in text:

            return doctype

    return None


# ============================================================
# DETECT MODULE
# ============================================================

def detect_module_from_command(
    command,
    documents,
):

    text = normalize(command)

    modules = available_modules(
        documents
    )

    modules.sort(
        key=len,
        reverse=True
    )

    for module in modules:

        if normalize(module) in text:

            return module

    return None


# ============================================================
# DETECT TARGET
# ============================================================

def detect_target(
    command,
    documents,
):

    doctype = detect_doctype_from_command(
        command,
        documents,
    )

    if doctype:

        knowledge = find_doctype(
            documents,
            doctype,
        )

        if knowledge:

            return {
                "target_type": "doctype",
                "target": doctype,
                "knowledge": knowledge,
            }

    module = detect_module_from_command(
        command,
        documents,
    )

    if module:

        module_docs = find_module(
            documents,
            module,
        )

        return {
            "target_type": "module",
            "target": module,
            "knowledge": module_docs,
        }

    return {
        "target_type": "unknown",
        "target": "",
        "knowledge": [],
    }


# ============================================================
# NORMALIZE DISCOVERY STRUCTURE
# ============================================================

def get_structure(doc):

    structure = doc.get(
        "structure",
        {}
    )

    if not isinstance(
        structure,
        dict
    ):

        structure = {}

    fields = doc.get("fields")

    if not isinstance(
        fields,
        list
    ):

        fields = structure.get(
            "fields",
            []
        )

    tabs = doc.get("tabs")

    if not isinstance(
        tabs,
        list
    ):

        tabs = structure.get(
            "tabs",
            []
        )

    sections = doc.get("sections")

    if not isinstance(
        sections,
        list
    ):

        sections = structure.get(
            "sections",
            []
        )

    buttons = doc.get("buttons")

    if not isinstance(
        buttons,
        list
    ):

        buttons = structure.get(
            "buttons",
            []
        )

    return (
        fields,
        tabs,
        sections,
        buttons,
    )


# ============================================================
# FIELD NORMALIZATION
# ============================================================

def normalize_fields(fields):

    result = []

    if not isinstance(
        fields,
        list
    ):

        return result

    for field in fields:

        if not isinstance(
            field,
            dict
        ):

            continue

        fieldname = clean(
            field.get(
                "fieldname",
                ""
            )
        )

        if not fieldname:
            continue

        normalized = {
            "fieldname": fieldname,
            "label": clean(
                field.get(
                    "label"
                )
                or fieldname
            ),
            "fieldtype": clean(
                field.get(
                    "fieldtype",
                    ""
                )
            ),
            "value": field.get(
                "value",
                ""
            ),
            "options": field.get(
                "options",
                []
            ),
        }

        for key in [
            "reqd",
            "read_only",
            "hidden",
            "depends_on",
            "mandatory",
            "description",
        ]:

            if key in field:

                normalized[key] = field[key]

        result.append(normalized)

    return result


# ============================================================
# STRUCTURE NORMALIZATION
# ============================================================

def normalize_names(values):

    result = []

    if not isinstance(
        values,
        list
    ):

        return result

    for item in values:

        if isinstance(
            item,
            dict
        ):

            value = clean(
                item.get("label")
                or item.get("text")
                or item.get("name")
                or ""
            )

        else:

            value = clean(item)

        if value:

            result.append(value)

    return result


# ============================================================
# BUTTON NORMALIZATION
# ============================================================

def normalize_buttons(buttons):

    result = []

    if not isinstance(
        buttons,
        list
    ):

        return result

    for button in buttons:

        if isinstance(
            button,
            dict
        ):

            name = clean(
                button.get("text")
                or button.get("label")
                or button.get("name")
                or ""
            )

        else:

            name = clean(button)

        if not name:
            continue

        result.append(
            {
                "name": name,
                "notification": is_notification_item(
                    name
                ),
                "action": (
                    "skip"
                    if is_notification_item(name)
                    else "click"
                ),
            }
        )

    return result


# ============================================================
# BUILD DOCTYPE PLAN
# ============================================================

def build_doctype_plan(
    task_type,
    doc,
):

    doctype = clean(
        doc.get("doctype")
        or doc.get("document_name")
        or ""
    )

    (
        raw_fields,
        raw_tabs,
        raw_sections,
        raw_buttons,
    ) = get_structure(doc)

    fields = normalize_fields(
        raw_fields
    )

    tabs = normalize_names(
        raw_tabs
    )

    sections = normalize_names(
        raw_sections
    )

    buttons = normalize_buttons(
        raw_buttons
    )

    return {
        "task_type": task_type,
        "target_type": "doctype",
        "target": doctype,
        "source_file": doc.get(
            "source_file",
            ""
        ),
        "source_path": doc.get(
            "source_path",
            ""
        ),
        "execution": {
            "open_doctype": True,
            "open_list_view": True,
            "click_add_new": True,
            "open_blank_document": True,
            "read_all_fields": True,
            "read_tabs": bool(tabs),
            "read_sections": bool(sections),
            "read_buttons": bool(buttons),
            "test_all_fields": bool(fields),
            "test_buttons": bool(buttons),
            "test_tabs": bool(tabs),
            "test_sections": bool(sections),
            "save_document": False,
            "submit_document": False,
            "delete_document": False,
        },
        "navigation": {
            "url": doc.get(
                "url",
                ""
            ),
            "doctype": doctype,
            "open_method": "list_then_add",
            "add_button": f"Add {doctype}",
        },
        "knowledge": {
            "doctype": doctype,
            "module": clean(
                doc.get(
                    "module",
                    ""
                )
            ),
            "field_count": len(fields),
            "fields": fields,
            "tab_count": len(tabs),
            "tabs": tabs,
            "section_count": len(sections),
            "sections": sections,
            "button_count": len(buttons),
            "buttons": buttons,
            "notification_keywords": sorted(
                NOTIFICATION_KEYWORDS
            ),
            "url": doc.get(
                "url",
                ""
            ),
            "title": doc.get(
                "title",
                ""
            ),
            "read_mode": doc.get(
                "read_mode",
                ""
            ),
            "existing_documents_skipped": doc.get(
                "existing_documents_skipped",
                True,
            ),
            "discovery_file": doc.get(
                "source_file",
                ""
            ),
        },
        "next_step": "generate_test_cases",
    }


# ============================================================
# BUILD MODULE PLAN
# ============================================================

def build_module_plan(
    task_type,
    module_name,
    docs,
):

    targets = []

    for doc in docs:

        doctype = clean(
            doc.get("doctype")
            or doc.get("document_name")
            or ""
        )

        if not doctype:
            continue

        targets.append(
            build_doctype_plan(
                task_type,
                doc,
            )
        )

    return {
        "task_type": task_type,
        "target_type": "module",
        "target": module_name,
        "execution": {
            "process_all_doctypes": True,
            "skip_existing_discovery": True,
            "skip_missing_knowledge": True,
            "continue_on_failure": True,
            "open_each_doctype": True,
            "click_add_new_for_each": True,
            "read_all_fields": True,
        },
        "doctype_count": len(targets),
        "doctypes": targets,
        "next_step": "generate_test_cases",
    }


# ============================================================
# CREATE PLAN
# ============================================================

def create_plan(command):

    documents = load_discovery()

    if not documents:

        raise RuntimeError(
            "No valid discovery JSON files found.\n\n"
            f"Directory:\n{DISCOVERY_DIR}"
        )

    task_type = detect_task_type(
        command
    )

    target = detect_target(
        command,
        documents,
    )

    if target["target_type"] == "unknown":

        return {
            "status": "needs_clarification",
            "command": command,
            "task_type": task_type,
            "target_type": "unknown",
            "message": (
                "Could not identify a known "
                "ERPNext DocType or Module."
            ),
            "available_doctypes": available_doctypes(
                documents
            ),
            "available_modules": available_modules(
                documents
            ),
            "next_step": "ask_user",
        }

    if target["target_type"] == "doctype":

        plan = build_doctype_plan(
            task_type,
            target["knowledge"],
        )

        return {
            "status": "ready",
            "generated_at": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "command": command,
            "source": "data/discovery",
            "plan": plan,
        }

    if target["target_type"] == "module":

        plan = build_module_plan(
            task_type,
            target["target"],
            target["knowledge"],
        )

        return {
            "status": "ready",
            "generated_at": time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "command": command,
            "source": "data/discovery",
            "plan": plan,
        }

    return {
        "status": "error",
        "message": "Unknown planner state.",
    }


# ============================================================
# SAVE PLAN
# ============================================================

def save_plan(plan):

    PLAN_FILE.write_text(
        json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    log(
        f"Plan saved: {PLAN_FILE}"
    )

    return PLAN_FILE


# ============================================================
# PRINT SUMMARY
# ============================================================

def print_summary(plan):

    if plan.get("status") != "ready":

        log(
            f"Status: "
            f"{plan.get('status')}"
        )

        return

    data = plan.get(
        "plan",
        {}
    )

    target_type = data.get(
        "target_type"
    )

    target = data.get(
        "target",
        ""
    )

    log(
        f"Target type: "
        f"{target_type}"
    )

    log(
        f"Target: "
        f"{target}"
    )

    if target_type == "doctype":

        knowledge = data.get(
            "knowledge",
            {}
        )

        log(
            f"Fields: "
            f"{knowledge.get('field_count', 0)}"
        )

        log(
            f"Tabs: "
            f"{knowledge.get('tab_count', 0)}"
        )

        log(
            f"Sections: "
            f"{knowledge.get('section_count', 0)}"
        )

        log(
            f"Buttons: "
            f"{knowledge.get('button_count', 0)}"
        )

        log(
            f"Source: "
            f"{data.get('source_file', '')}"
        )

    elif target_type == "module":

        doctypes = data.get(
            "doctypes",
            []
        )

        log(
            f"DocTypes: "
            f"{len(doctypes)}"
        )

        for index, item in enumerate(
            doctypes,
            start=1,
        ):

            log(
                f"{index}. "
                f"{item.get('target', '')} "
                f"-> "
                f"{item.get('source_file', '')}"
            )


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "ERPNext AI QA Planner"
        )
    )

    parser.add_argument(
        "command",
        nargs="*",
        help=(
            "Natural language QA command"
        ),
    )

    parser.add_argument(
        "--doctype",
        required=False,
        help=(
            "Plan only this DocType."
        ),
    )

    parser.add_argument(
        "--module",
        required=False,
        help=(
            "Plan all discovered DocTypes "
            "inside this module."
        ),
    )

    args = parser.parse_args()

    if args.doctype:

        return (
            f"Generate test cases for "
            f"{args.doctype}"
        )

    if args.module:

        return (
            f"Generate test cases for "
            f"{args.module} module"
        )

    if args.command:

        return " ".join(
            args.command
        )

    parser.error(
        "Give a command, "
        "--doctype or --module."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    command = parse_args()

    log(
        "======================================"
    )

    log(
        "ERPNext QA PLANNER"
    )

    log(
        "======================================"
    )

    log(
        f"Command: {command}"
    )

    try:

        plan = create_plan(
            command
        )

        save_plan(
            plan
        )

        print_summary(
            plan
        )

        print(
            json.dumps(
                plan,
                indent=2,
                ensure_ascii=False,
            )
        )

    except Exception as exc:

        log(
            f"ERROR: {exc}"
        )

        raise

    log(
        "======================================"
    )

    log(
        "PLANNER FINISHED"
    )

    log(
        "======================================"
    )


# ============================================================
# ENTRY
# ============================================================

if __name__ == "__main__":
    main()

