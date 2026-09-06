# import argparse
# import json
# import re
# import time
# from pathlib import Path

# # ============================================================
# # CONFIG
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent

# PLAN_FILE = BASE_DIR / "data" / "plans" / "latest_plan.json"

# OUTPUT_DIR = BASE_DIR / "data" / "test_cases"

# OUTPUT_DIR.mkdir(
#     parents=True,
#     exist_ok=True,
# )


# # ============================================================
# # LOG
# # ============================================================


# def log(message):
#     print(
#         f"[TEST-GENERATOR] {message}",
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


# def normalize_field_type(value):

#     value = clean(value).lower()

#     mapping = {
#         "data": "Data",
#         "text": "Data",
#         "small text": "Data",
#         "long text": "Text",
#         "textarea": "Text",
#         "select": "Select",
#         "link": "Link",
#         "check": "Check",
#         "checkbox": "Check",
#         "date": "Date",
#         "datetime": "Datetime",
#         "datetime-local": "Datetime",
#         "float": "Float",
#         "int": "Int",
#         "integer": "Int",
#         "currency": "Currency",
#         "amount": "Currency",
#     }

#     return mapping.get(
#         value,
#         clean(value) or "Unknown",
#     )


# # ============================================================
# # LOAD PLAN
# # ============================================================


# def load_plan():

#     if not PLAN_FILE.exists():

#         raise FileNotFoundError(f"""
# Plan file not found:

# {PLAN_FILE}

# Run Planner first:

# python planner.py "Run regression test for Company Budget"
# """)

#     try:

#         return json.loads(PLAN_FILE.read_text(encoding="utf-8"))

#     except json.JSONDecodeError as exc:

#         raise RuntimeError(f"Invalid plan JSON: {exc}")


# # ============================================================
# # TEST CASE COUNTER
# # ============================================================


# class TestCaseCounter:

#     def __init__(self):

#         self.number = 0

#     def next(self):

#         self.number += 1

#         return f"TC-{self.number:04d}"


# # ============================================================
# # CREATE STRUCTURED TEST CASE
# # ============================================================


# def make_test_case(
#     counter,
#     doctype,
#     title,
#     category,
#     priority,
#     action,
#     steps,
#     expected,
#     fieldname=None,
#     fieldtype=None,
#     label=None,
#     option=None,
#     value=None,
#     source="knowledge",
# ):

#     return {
#         "id": counter.next(),
#         "doctype": doctype,
#         "title": title,
#         "category": category,
#         "priority": priority,
#         "source": source,
#         "field": {
#             "fieldname": fieldname,
#             "label": label,
#             "fieldtype": fieldtype,
#             "option": option,
#             "value": value,
#         },
#         "action": action,
#         "steps": steps,
#         "expected_result": expected,
#         "status": "not_executed",
#     }


# # ============================================================
# # BASIC DOCTYPE TESTS
# # ============================================================


# def generate_basic_tests(
#     counter,
#     doctype,
# ):

#     cases = []

#     # --------------------------------------------------------
#     # Open DocType
#     # --------------------------------------------------------

#     cases.append(
#         make_test_case(
#             counter=counter,
#             doctype=doctype,
#             title=f"Open {doctype}",
#             category="navigation",
#             priority="High",
#             action="open_doctype",
#             steps=[
#                 {
#                     "action": "open_doctype",
#                     "doctype": doctype,
#                 }
#             ],
#             expected=f"{doctype} page opens successfully.",
#         )
#     )

#     # --------------------------------------------------------
#     # Open New Document
#     # --------------------------------------------------------

#     cases.append(
#         make_test_case(
#             counter=counter,
#             doctype=doctype,
#             title=f"Open new {doctype} document",
#             category="navigation",
#             priority="High",
#             action="create_new_document",
#             steps=[
#                 {
#                     "action": "open_doctype",
#                     "doctype": doctype,
#                 },
#                 {
#                     "action": "click_add",
#                     "doctype": doctype,
#                     "target": f"Add {doctype}",
#                 },
#             ],
#             expected=(f"New {doctype} document form " "opens successfully."),
#         )
#     )

#     return cases


# # ============================================================
# # FIELD TESTS
# # ============================================================


# def generate_field_tests(
#     counter,
#     doctype,
#     fields,
# ):

#     cases = []

#     for field in fields:

#         if not isinstance(
#             field,
#             dict,
#         ):
#             continue

#         fieldname = clean(field.get("fieldname"))

#         if not fieldname:
#             continue

#         label = clean(field.get("label")) or fieldname

#         fieldtype = normalize_field_type(field.get("fieldtype"))

#         options = field.get(
#             "options",
#             [],
#         )

#         # ----------------------------------------------------
#         # Visibility
#         # ----------------------------------------------------

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=f"Verify {label} field is visible",
#                 category="field_validation",
#                 priority="Medium",
#                 action="verify_field_visible",
#                 steps=[
#                     {
#                         "action": "open_new_document",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "locate_field",
#                         "fieldname": fieldname,
#                         "label": label,
#                     },
#                 ],
#                 expected=(f"{label} field is visible " "and accessible."),
#                 fieldname=fieldname,
#                 fieldtype=fieldtype,
#                 label=label,
#             )
#         )

#         # ----------------------------------------------------
#         # Field Type
#         # ----------------------------------------------------

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=f"Verify {label} field type",
#                 category="field_validation",
#                 priority="Medium",
#                 action="verify_field_type",
#                 steps=[
#                     {
#                         "action": "open_new_document",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "locate_field",
#                         "fieldname": fieldname,
#                         "label": label,
#                     },
#                     {
#                         "action": "verify_field_type",
#                         "fieldname": fieldname,
#                         "expected_fieldtype": fieldtype,
#                     },
#                 ],
#                 expected=(f"{label} behaves as " f"a {fieldtype} field."),
#                 fieldname=fieldname,
#                 fieldtype=fieldtype,
#                 label=label,
#             )
#         )

#         # ----------------------------------------------------
#         # Select
#         # ----------------------------------------------------

#         if fieldtype.lower() == "select":

#             valid_options = []

#             for option in options:

#                 if isinstance(
#                     option,
#                     dict,
#                 ):

#                     option_value = clean(option.get("value") or option.get("text"))

#                 else:

#                     option_value = clean(option)

#                 if option_value:
#                     valid_options.append(option_value)

#             for option_value in valid_options:

#                 cases.append(
#                     make_test_case(
#                         counter=counter,
#                         doctype=doctype,
#                         title=(f"Verify {label} " f"option: {option_value}"),
#                         category="field_validation",
#                         priority="High",
#                         action="select_option",
#                         steps=[
#                             {
#                                 "action": "open_new_document",
#                                 "doctype": doctype,
#                             },
#                             {
#                                 "action": "select_option",
#                                 "fieldname": fieldname,
#                                 "label": label,
#                                 "option": option_value,
#                             },
#                         ],
#                         expected=(
#                             f"'{option_value}' can be "
#                             f"selected successfully "
#                             f"from {label}."
#                         ),
#                         fieldname=fieldname,
#                         fieldtype=fieldtype,
#                         label=label,
#                         option=option_value,
#                     )
#                 )

#         # ----------------------------------------------------
#         # Link Field
#         # ----------------------------------------------------

#         elif fieldtype.lower() == "link":

#             cases.append(
#                 make_test_case(
#                     counter=counter,
#                     doctype=doctype,
#                     title=f"Verify {label} Link field",
#                     category="link_validation",
#                     priority="High",
#                     action="select_link",
#                     steps=[
#                         {
#                             "action": "open_new_document",
#                             "doctype": doctype,
#                         },
#                         {
#                             "action": "locate_field",
#                             "fieldname": fieldname,
#                             "label": label,
#                         },
#                         {
#                             "action": "select_link",
#                             "fieldname": fieldname,
#                             "value": "<valid_link_value>",
#                         },
#                     ],
#                     expected=(f"{label} accepts and selects " "a valid linked record."),
#                     fieldname=fieldname,
#                     fieldtype=fieldtype,
#                     label=label,
#                 )
#             )

#         # ----------------------------------------------------
#         # Check / Checkbox
#         # ----------------------------------------------------

#         elif fieldtype.lower() == "check":

#             cases.append(
#                 make_test_case(
#                     counter=counter,
#                     doctype=doctype,
#                     title=f"Verify {label} checkbox",
#                     category="field_validation",
#                     priority="Medium",
#                     action="toggle_checkbox",
#                     steps=[
#                         {
#                             "action": "open_new_document",
#                             "doctype": doctype,
#                         },
#                         {
#                             "action": "toggle_checkbox",
#                             "fieldname": fieldname,
#                             "label": label,
#                             "value": True,
#                         },
#                     ],
#                     expected=(f"{label} checkbox can be " "checked successfully."),
#                     fieldname=fieldname,
#                     fieldtype=fieldtype,
#                     label=label,
#                     value=True,
#                 )
#             )

#         # ----------------------------------------------------
#         # Date
#         # ----------------------------------------------------

#         elif fieldtype.lower() == "date":

#             cases.append(
#                 make_test_case(
#                     counter=counter,
#                     doctype=doctype,
#                     title=f"Verify {label} date field",
#                     category="field_validation",
#                     priority="Medium",
#                     action="enter_value",
#                     steps=[
#                         {
#                             "action": "open_new_document",
#                             "doctype": doctype,
#                         },
#                         {
#                             "action": "fill_field",
#                             "fieldname": fieldname,
#                             "label": label,
#                             "value": "<valid_date>",
#                         },
#                     ],
#                     expected=(f"{label} accepts a valid " "date value."),
#                     fieldname=fieldname,
#                     fieldtype=fieldtype,
#                     label=label,
#                     value="<valid_date>",
#                 )
#             )

#         # ----------------------------------------------------
#         # Numeric
#         # ----------------------------------------------------

#         elif fieldtype.lower() in {
#             "float",
#             "int",
#             "currency",
#         }:

#             cases.append(
#                 make_test_case(
#                     counter=counter,
#                     doctype=doctype,
#                     title=f"Verify {label} numeric field",
#                     category="field_validation",
#                     priority="Medium",
#                     action="enter_value",
#                     steps=[
#                         {
#                             "action": "open_new_document",
#                             "doctype": doctype,
#                         },
#                         {
#                             "action": "fill_field",
#                             "fieldname": fieldname,
#                             "label": label,
#                             "value": "<valid_numeric_value>",
#                         },
#                     ],
#                     expected=(f"{label} accepts a valid " "numeric value."),
#                     fieldname=fieldname,
#                     fieldtype=fieldtype,
#                     label=label,
#                     value="<valid_numeric_value>",
#                 )
#             )

#     return cases


# # ============================================================
# # REQUIRED FIELD TESTS
# # ============================================================


# def generate_required_tests(
#     counter,
#     doctype,
#     fields,
# ):

#     cases = []

#     for field in fields:

#         if not isinstance(
#             field,
#             dict,
#         ):
#             continue

#         fieldname = clean(field.get("fieldname"))

#         if not fieldname:
#             continue

#         label = clean(field.get("label")) or fieldname

#         fieldtype = normalize_field_type(field.get("fieldtype"))

#         required = field.get(
#             "reqd",
#             False,
#         )

#         if not required:
#             continue

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=(f"Validate required " f"field: {label}"),
#                 category="negative_validation",
#                 priority="High",
#                 action="validate_required_field",
#                 steps=[
#                     {
#                         "action": "open_new_document",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "leave_field_empty",
#                         "fieldname": fieldname,
#                         "label": label,
#                     },
#                     {
#                         "action": "save_document",
#                         "doctype": doctype,
#                     },
#                 ],
#                 expected=(
#                     f"System should prevent saving " f"until {label} is provided."
#                 ),
#                 fieldname=fieldname,
#                 fieldtype=fieldtype,
#                 label=label,
#             )
#         )

#     return cases


# # ============================================================
# # BUTTON TESTS
# # ============================================================


# def generate_button_tests(
#     counter,
#     doctype,
#     buttons,
# ):

#     cases = []

#     ignored = {
#         "help",
#         "filter",
#         "list view",
#         "no new notifications",
#     }

#     for button in buttons:

#         if isinstance(
#             button,
#             dict,
#         ):

#             name = clean(button.get("text") or button.get("label"))

#         else:

#             name = clean(button)

#         if not name:
#             continue

#         if name.lower() in ignored:
#             continue

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=f"Verify button: {name}",
#                 category="button_validation",
#                 priority="Medium",
#                 action="click_button",
#                 steps=[
#                     {
#                         "action": "open_doctype",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "locate_button",
#                         "button": name,
#                     },
#                     {
#                         "action": "click_button",
#                         "button": name,
#                     },
#                 ],
#                 expected=(f"'{name}' button performs " "its expected action."),
#             )
#         )

#     return cases


# # ============================================================
# # TAB TESTS
# # ============================================================


# def generate_tab_tests(
#     counter,
#     doctype,
#     tabs,
# ):

#     cases = []

#     for tab in tabs:

#         if isinstance(
#             tab,
#             dict,
#         ):

#             name = clean(tab.get("label") or tab.get("text") or tab.get("name"))

#         else:

#             name = clean(tab)

#         if not name:
#             continue

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=f"Verify tab: {name}",
#                 category="ui_structure",
#                 priority="Medium",
#                 action="click_tab",
#                 steps=[
#                     {
#                         "action": "open_new_document",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "click_tab",
#                         "tab": name,
#                     },
#                 ],
#                 expected=(f"'{name}' tab opens and " "displays its content."),
#             )
#         )

#     return cases


# # ============================================================
# # SECTION TESTS
# # ============================================================


# def generate_section_tests(
#     counter,
#     doctype,
#     sections,
# ):

#     cases = []

#     for section in sections:

#         if isinstance(
#             section,
#             dict,
#         ):

#             name = clean(
#                 section.get("label") or section.get("text") or section.get("name")
#             )

#         else:

#             name = clean(section)

#         if not name:
#             continue

#         cases.append(
#             make_test_case(
#                 counter=counter,
#                 doctype=doctype,
#                 title=f"Verify section: {name}",
#                 category="ui_structure",
#                 priority="Low",
#                 action="verify_section",
#                 steps=[
#                     {
#                         "action": "open_new_document",
#                         "doctype": doctype,
#                     },
#                     {
#                         "action": "verify_section",
#                         "section": name,
#                     },
#                 ],
#                 expected=(f"'{name}' section is " "displayed correctly."),
#             )
#         )

#     return cases


# # ============================================================
# # DOCTYPE GENERATOR
# # ============================================================


# def generate_for_doctype(
#     counter,
#     plan,
# ):

#     knowledge = plan.get(
#         "knowledge",
#         {},
#     )

#     doctype = clean(plan.get("target"))

#     if not doctype:

#         doctype = clean(knowledge.get("doctype"))

#     fields = knowledge.get(
#         "fields",
#         [],
#     )

#     tabs = knowledge.get(
#         "tabs",
#         [],
#     )

#     sections = knowledge.get(
#         "sections",
#         [],
#     )

#     buttons = knowledge.get(
#         "buttons",
#         [],
#     )

#     cases = []

#     # --------------------------------------------------------
#     # Basic
#     # --------------------------------------------------------

#     cases.extend(
#         generate_basic_tests(
#             counter,
#             doctype,
#         )
#     )

#     # --------------------------------------------------------
#     # Fields
#     # --------------------------------------------------------

#     cases.extend(
#         generate_field_tests(
#             counter,
#             doctype,
#             fields,
#         )
#     )

#     # --------------------------------------------------------
#     # Required
#     # --------------------------------------------------------

#     cases.extend(
#         generate_required_tests(
#             counter,
#             doctype,
#             fields,
#         )
#     )

#     # --------------------------------------------------------
#     # Buttons
#     # --------------------------------------------------------

#     cases.extend(
#         generate_button_tests(
#             counter,
#             doctype,
#             buttons,
#         )
#     )

#     # --------------------------------------------------------
#     # Tabs
#     # --------------------------------------------------------

#     cases.extend(
#         generate_tab_tests(
#             counter,
#             doctype,
#             tabs,
#         )
#     )

#     # --------------------------------------------------------
#     # Sections
#     # --------------------------------------------------------

#     cases.extend(
#         generate_section_tests(
#             counter,
#             doctype,
#             sections,
#         )
#     )

#     return cases


# # ============================================================
# # MODULE GENERATOR
# # ============================================================


# def generate_for_module(
#     counter,
#     plan,
# ):

#     cases = []

#     doctypes = plan.get(
#         "doctypes",
#         [],
#     )

#     for doctype_plan in doctypes:

#         cases.extend(
#             generate_for_doctype(
#                 counter,
#                 doctype_plan,
#             )
#         )

#     return cases


# # ============================================================
# # GENERATE
# # ============================================================


# def generate():

#     plan_data = load_plan()

#     if plan_data.get("status") != "ready":

#         raise RuntimeError("Planner did not produce a ready plan.")

#     plan = plan_data.get(
#         "plan",
#         {},
#     )

#     target_type = plan.get("target_type")

#     counter = TestCaseCounter()

#     # --------------------------------------------------------
#     # DocType
#     # --------------------------------------------------------

#     if target_type == "doctype":

#         cases = generate_for_doctype(
#             counter,
#             plan,
#         )

#     # --------------------------------------------------------
#     # Module
#     # --------------------------------------------------------

#     elif target_type == "module":

#         cases = generate_for_module(
#             counter,
#             plan,
#         )

#     else:

#         raise RuntimeError(f"Unsupported target type: {target_type}")

#     return {
#         "knowledge_type": "erpnext_test_cases",
#         "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
#         "source_command": plan_data.get(
#             "command",
#             "",
#         ),
#         "target_type": target_type,
#         "target": plan.get(
#             "target",
#             "",
#         ),
#         "total_test_cases": len(cases),
#         "test_cases": cases,
#     }


# # ============================================================
# # SAVE
# # ============================================================


# def save_test_cases(data):

#     path = OUTPUT_DIR / "latest_test_cases.json"

#     path.write_text(
#         json.dumps(
#             data,
#             indent=2,
#             ensure_ascii=False,
#         ),
#         encoding="utf-8",
#     )

#     return path


# # ============================================================
# # MAIN
# # ============================================================


# def main():

#     parser = argparse.ArgumentParser(
#         description=("ERPNext Structured " "Test Case Generator")
#     )

#     parser.add_argument(
#         "--show",
#         action="store_true",
#         help="Print generated test cases.",
#     )

#     args = parser.parse_args()

#     log("======================================")

#     log("ERPNext STRUCTURED " "TEST CASE GENERATOR")

#     log("======================================")

#     data = generate()

#     path = save_test_cases(data)

#     log(f"Target: {data['target']}")

#     log(f"Target type: " f"{data['target_type']}")

#     log(f"Generated test cases: " f"{data['total_test_cases']}")

#     log(f"Saved: {path}")

#     if args.show:

#         print(
#             json.dumps(
#                 data,
#                 indent=2,
#                 ensure_ascii=False,
#             )
#         )

#     log("======================================")

#     log("TEST CASE GENERATION FINISHED")

#     log("======================================")


# if __name__ == "__main__":

#     main()


#======================================


import argparse
import json
import re
import time
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PLAN_FILE = BASE_DIR / "data" / "plans" / "latest_plan.json"

OUTPUT_DIR = BASE_DIR / "data" / "test_cases"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# LOG
# ============================================================


def log(message):
    print(
        f"[TEST-GENERATOR] {message}",
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


def normalize_field_type(value):

    value = clean(value).lower()

    mapping = {
        "data": "Data",
        "text": "Data",
        "small text": "Data",
        "long text": "Text",
        "textarea": "Text",
        "select": "Select",
        "link": "Link",
        "check": "Check",
        "checkbox": "Check",
        "date": "Date",
        "datetime": "Datetime",
        "datetime-local": "Datetime",
        "float": "Float",
        "int": "Int",
        "integer": "Int",
        "currency": "Currency",
        "amount": "Currency",
    }

    return mapping.get(
        value,
        clean(value) or "Unknown",
    )


# ============================================================
# LOAD PLAN
# ============================================================


def load_plan():

    if not PLAN_FILE.exists():

        raise FileNotFoundError(
            f"""
Plan file not found:

{PLAN_FILE}

Run Planner first:

python planner.py "Run regression test for Company Budget"
"""
        )

    try:

        return json.loads(
            PLAN_FILE.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            f"Invalid plan JSON: {exc}"
        )


# ============================================================
# TEST CASE COUNTER
# ============================================================


class TestCaseCounter:

    def __init__(self):

        self.number = 0

    def next(self):

        self.number += 1

        return f"TC-{self.number:04d}"


# ============================================================
# CREATE STRUCTURED TEST CASE
# ============================================================


def make_test_case(
    counter,
    doctype,
    title,
    category,
    priority,
    action,
    steps,
    expected,
    fieldname=None,
    fieldtype=None,
    label=None,
    option=None,
    value=None,
    source="knowledge",
):

    return {
        "id": counter.next(),
        "doctype": doctype,
        "title": title,
        "category": category,
        "priority": priority,
        "source": source,
        "field": {
            "fieldname": fieldname,
            "label": label,
            "fieldtype": fieldtype,
            "option": option,
            "value": value,
        },
        "action": action,
        "steps": steps,
        "expected_result": expected,
        "status": "not_executed",
    }


# ============================================================
# BASIC DOCTYPE TESTS
# ============================================================


def generate_basic_tests(
    counter,
    doctype,
):

    cases = []

    # --------------------------------------------------------
    # Open DocType
    # --------------------------------------------------------

    cases.append(
        make_test_case(
            counter=counter,
            doctype=doctype,
            title=f"Open {doctype}",
            category="navigation",
            priority="High",
            action="open_doctype",
            steps=[
                {
                    "action": "open_doctype",
                    "doctype": doctype,
                }
            ],
            expected=(
                f"{doctype} page opens successfully."
            ),
        )
    )

    # --------------------------------------------------------
    # Open New Document
    # --------------------------------------------------------

    cases.append(
        make_test_case(
            counter=counter,
            doctype=doctype,
            title=f"Open new {doctype} document",
            category="navigation",
            priority="High",
            action="create_new_document",
            steps=[
                {
                    "action": "open_doctype",
                    "doctype": doctype,
                },
                {
                    "action": "click_add",
                    "doctype": doctype,
                    "target": f"Add {doctype}",
                },
            ],
            expected=(
                f"New {doctype} document form "
                "opens successfully."
            ),
        )
    )

    return cases


# ============================================================
# FIELD TESTS
# ============================================================


def generate_field_tests(
    counter,
    doctype,
    fields,
):

    cases = []

    for field in fields:

        if not isinstance(
            field,
            dict,
        ):
            continue

        fieldname = clean(
            field.get("fieldname")
        )

        if not fieldname:
            continue

        label = (
            clean(field.get("label"))
            or fieldname
        )

        fieldtype = normalize_field_type(
            field.get("fieldtype")
        )

        options = field.get(
            "options",
            [],
        )

        # ----------------------------------------------------
        # Visibility
        # ----------------------------------------------------

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=(
                    f"Verify {label} "
                    "field is visible"
                ),
                category="field_validation",
                priority="Medium",
                action="verify_field_visible",
                steps=[
                    {
                        "action": "open_new_document",
                        "doctype": doctype,
                    },
                    {
                        "action": "locate_field",
                        "fieldname": fieldname,
                        "label": label,
                    },
                ],
                expected=(
                    f"{label} field is visible "
                    "and accessible."
                ),
                fieldname=fieldname,
                fieldtype=fieldtype,
                label=label,
            )
        )

        # ----------------------------------------------------
        # Field Type
        # ----------------------------------------------------

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=(
                    f"Verify {label} "
                    "field type"
                ),
                category="field_validation",
                priority="Medium",
                action="verify_field_type",
                steps=[
                    {
                        "action": "open_new_document",
                        "doctype": doctype,
                    },
                    {
                        "action": "locate_field",
                        "fieldname": fieldname,
                        "label": label,
                    },
                    {
                        "action": "verify_field_type",
                        "fieldname": fieldname,
                        "expected_fieldtype": fieldtype,
                    },
                ],
                expected=(
                    f"{label} behaves as "
                    f"a {fieldtype} field."
                ),
                fieldname=fieldname,
                fieldtype=fieldtype,
                label=label,
            )
        )

        # ----------------------------------------------------
        # Select
        # ----------------------------------------------------

        if fieldtype.lower() == "select":

            valid_options = []

            for option in options:

                if isinstance(
                    option,
                    dict,
                ):

                    option_value = clean(
                        option.get("value")
                        or option.get("text")
                    )

                else:

                    option_value = clean(
                        option
                    )

                if option_value:
                    valid_options.append(
                        option_value
                    )

            for option_value in valid_options:

                cases.append(
                    make_test_case(
                        counter=counter,
                        doctype=doctype,
                        title=(
                            f"Verify {label} "
                            f"option: {option_value}"
                        ),
                        category="field_validation",
                        priority="High",
                        action="select_option",
                        steps=[
                            {
                                "action": "open_new_document",
                                "doctype": doctype,
                            },
                            {
                                "action": "select_option",
                                "fieldname": fieldname,
                                "label": label,
                                "option": option_value,
                            },
                        ],
                        expected=(
                            f"'{option_value}' can be "
                            f"selected successfully "
                            f"from {label}."
                        ),
                        fieldname=fieldname,
                        fieldtype=fieldtype,
                        label=label,
                        option=option_value,
                    )
                )

        # ----------------------------------------------------
        # Link Field
        # ----------------------------------------------------

        elif fieldtype.lower() == "link":

            cases.append(
                make_test_case(
                    counter=counter,
                    doctype=doctype,
                    title=(
                        f"Verify {label} "
                        "Link field"
                    ),
                    category="link_validation",
                    priority="High",
                    action="select_link",
                    steps=[
                        {
                            "action": "open_new_document",
                            "doctype": doctype,
                        },
                        {
                            "action": "locate_field",
                            "fieldname": fieldname,
                            "label": label,
                        },
                        {
                            "action": "select_link",
                            "fieldname": fieldname,
                            "value": "<valid_link_value>",
                        },
                    ],
                    expected=(
                        f"{label} accepts and selects "
                        "a valid linked record."
                    ),
                    fieldname=fieldname,
                    fieldtype=fieldtype,
                    label=label,
                )
            )

        # ----------------------------------------------------
        # Check / Checkbox
        # ----------------------------------------------------

        elif fieldtype.lower() == "check":

            cases.append(
                make_test_case(
                    counter=counter,
                    doctype=doctype,
                    title=(
                        f"Verify {label} "
                        "checkbox"
                    ),
                    category="field_validation",
                    priority="Medium",
                    action="toggle_checkbox",
                    steps=[
                        {
                            "action": "open_new_document",
                            "doctype": doctype,
                        },
                        {
                            "action": "toggle_checkbox",
                            "fieldname": fieldname,
                            "label": label,
                            "value": True,
                        },
                    ],
                    expected=(
                        f"{label} checkbox can be "
                        "checked successfully."
                    ),
                    fieldname=fieldname,
                    fieldtype=fieldtype,
                    label=label,
                    value=True,
                )
            )

        # ----------------------------------------------------
        # Date
        # ----------------------------------------------------

        elif fieldtype.lower() == "date":

            cases.append(
                make_test_case(
                    counter=counter,
                    doctype=doctype,
                    title=(
                        f"Verify {label} "
                        "date field"
                    ),
                    category="field_validation",
                    priority="Medium",
                    action="enter_value",
                    steps=[
                        {
                            "action": "open_new_document",
                            "doctype": doctype,
                        },
                        {
                            "action": "fill_field",
                            "fieldname": fieldname,
                            "label": label,
                            "value": "<valid_date>",
                        },
                    ],
                    expected=(
                        f"{label} accepts a valid "
                        "date value."
                    ),
                    fieldname=fieldname,
                    fieldtype=fieldtype,
                    label=label,
                    value="<valid_date>",
                )
            )

        # ----------------------------------------------------
        # Numeric
        # ----------------------------------------------------

        elif fieldtype.lower() in {
            "float",
            "int",
            "currency",
        }:

            cases.append(
                make_test_case(
                    counter=counter,
                    doctype=doctype,
                    title=(
                        f"Verify {label} "
                        "numeric field"
                    ),
                    category="field_validation",
                    priority="Medium",
                    action="enter_value",
                    steps=[
                        {
                            "action": "open_new_document",
                            "doctype": doctype,
                        },
                        {
                            "action": "fill_field",
                            "fieldname": fieldname,
                            "label": label,
                            "value": "<valid_numeric_value>",
                        },
                    ],
                    expected=(
                        f"{label} accepts a valid "
                        "numeric value."
                    ),
                    fieldname=fieldname,
                    fieldtype=fieldtype,
                    label=label,
                    value="<valid_numeric_value>",
                )
            )

    return cases


# ============================================================
# REQUIRED FIELD TESTS
# ============================================================


def generate_required_tests(
    counter,
    doctype,
    fields,
):

    cases = []

    for field in fields:

        if not isinstance(
            field,
            dict,
        ):
            continue

        fieldname = clean(
            field.get("fieldname")
        )

        if not fieldname:
            continue

        label = (
            clean(field.get("label"))
            or fieldname
        )

        fieldtype = normalize_field_type(
            field.get("fieldtype")
        )

        required = field.get(
            "reqd",
            False,
        )

        if not required:
            continue

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=(
                    f"Validate required "
                    f"field: {label}"
                ),
                category="negative_validation",
                priority="High",
                action="validate_required_field",
                steps=[
                    {
                        "action": "open_new_document",
                        "doctype": doctype,
                    },
                    {
                        "action": "leave_field_empty",
                        "fieldname": fieldname,
                        "label": label,
                    },
                    {
                        "action": "save_document",
                        "doctype": doctype,
                    },
                ],
                expected=(
                    f"System should prevent saving "
                    f"until {label} is provided."
                ),
                fieldname=fieldname,
                fieldtype=fieldtype,
                label=label,
            )
        )

    return cases


# ============================================================
# SYSTEM / GLOBAL UI IGNORE
# ============================================================


def is_ignored_system_ui(name):
    """
    Return True when an element is a global/system UI
    element and should NOT generate a DocType test case.

    Examples:

        notification
        notifications
        no new notifications
        notification icon
        bell
        bell icon
    """

    normalized = clean(name).lower()

    if not normalized:
        return True

    # --------------------------------------------------------
    # Exact ignored names
    # --------------------------------------------------------

    ignored_exact = {
        "help",
        "filter",
        "list view",

        # Notification UI
        "notification",
        "notifications",
        "no new notifications",
        "notification icon",
        "bell",
        "bell icon",
    }

    if normalized in ignored_exact:
        return True

    # --------------------------------------------------------
    # Notification variations
    #
    # This also catches:
    #
    # Notifications
    # Notification Icon
    # No New Notifications
    # Bell
    # Bell Icon
    # Notifications (3)
    # --------------------------------------------------------

    notification_keywords = [
        "notification",
        "notifications",
        "no new notifications",
        "notification icon",
        "bell",
        "bell icon",
    ]

    for keyword in notification_keywords:

        if keyword in normalized:
            return True

    return False


# ============================================================
# BUTTON TESTS
# ============================================================


def generate_button_tests(
    counter,
    doctype,
    buttons,
):

    cases = []

    for button in buttons:

        if isinstance(
            button,
            dict,
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

        # ----------------------------------------------------
        # Ignore system/global UI
        # ----------------------------------------------------

        if is_ignored_system_ui(name):

            log(
                f"Skipping system UI element: {name}"
            )

            continue

        # ----------------------------------------------------
        # Generate actual button test case
        # ----------------------------------------------------

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=f"Verify button: {name}",
                category="button_validation",
                priority="Medium",
                action="click_button",
                steps=[
                    {
                        "action": "open_doctype",
                        "doctype": doctype,
                    },
                    {
                        "action": "locate_button",
                        "button": name,
                    },
                    {
                        "action": "click_button",
                        "button": name,
                    },
                ],
                expected=(
                    f"'{name}' button performs "
                    "its expected action."
                ),
            )
        )

    return cases


# ============================================================
# TAB TESTS
# ============================================================


def generate_tab_tests(
    counter,
    doctype,
    tabs,
):

    cases = []

    for tab in tabs:

        if isinstance(
            tab,
            dict,
        ):

            name = clean(
                tab.get("label")
                or tab.get("text")
                or tab.get("name")
            )

        else:

            name = clean(tab)

        if not name:
            continue

        # ----------------------------------------------------
        # Ignore global system UI if accidentally discovered
        # ----------------------------------------------------

        if is_ignored_system_ui(name):

            log(
                f"Skipping system UI tab: {name}"
            )

            continue

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=f"Verify tab: {name}",
                category="ui_structure",
                priority="Medium",
                action="click_tab",
                steps=[
                    {
                        "action": "open_new_document",
                        "doctype": doctype,
                    },
                    {
                        "action": "click_tab",
                        "tab": name,
                    },
                ],
                expected=(
                    f"'{name}' tab opens and "
                    "displays its content."
                ),
            )
        )

    return cases


# ============================================================
# SECTION TESTS
# ============================================================


def generate_section_tests(
    counter,
    doctype,
    sections,
):

    cases = []

    for section in sections:

        if isinstance(
            section,
            dict,
        ):

            name = clean(
                section.get("label")
                or section.get("text")
                or section.get("name")
            )

        else:

            name = clean(section)

        if not name:
            continue

        # ----------------------------------------------------
        # Ignore global system UI if accidentally discovered
        # ----------------------------------------------------

        if is_ignored_system_ui(name):

            log(
                f"Skipping system UI section: {name}"
            )

            continue

        cases.append(
            make_test_case(
                counter=counter,
                doctype=doctype,
                title=f"Verify section: {name}",
                category="ui_structure",
                priority="Low",
                action="verify_section",
                steps=[
                    {
                        "action": "open_new_document",
                        "doctype": doctype,
                    },
                    {
                        "action": "verify_section",
                        "section": name,
                    },
                ],
                expected=(
                    f"'{name}' section is "
                    "displayed correctly."
                ),
            )
        )

    return cases


# ============================================================
# DOCTYPE GENERATOR
# ============================================================


def generate_for_doctype(
    counter,
    plan,
):

    knowledge = plan.get(
        "knowledge",
        {},
    )

    doctype = clean(
        plan.get("target")
    )

    if not doctype:

        doctype = clean(
            knowledge.get("doctype")
        )

    fields = knowledge.get(
        "fields",
        [],
    )

    tabs = knowledge.get(
        "tabs",
        [],
    )

    sections = knowledge.get(
        "sections",
        [],
    )

    buttons = knowledge.get(
        "buttons",
        [],
    )

    cases = []

    # --------------------------------------------------------
    # Basic
    # --------------------------------------------------------

    cases.extend(
        generate_basic_tests(
            counter,
            doctype,
        )
    )

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------

    cases.extend(
        generate_field_tests(
            counter,
            doctype,
            fields,
        )
    )

    # --------------------------------------------------------
    # Required
    # --------------------------------------------------------

    cases.extend(
        generate_required_tests(
            counter,
            doctype,
            fields,
        )
    )

    # --------------------------------------------------------
    # Buttons
    # --------------------------------------------------------

    cases.extend(
        generate_button_tests(
            counter,
            doctype,
            buttons,
        )
    )

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    cases.extend(
        generate_tab_tests(
            counter,
            doctype,
            tabs,
        )
    )

    # --------------------------------------------------------
    # Sections
    # --------------------------------------------------------

    cases.extend(
        generate_section_tests(
            counter,
            doctype,
            sections,
        )
    )

    return cases


# ============================================================
# MODULE GENERATOR
# ============================================================


def generate_for_module(
    counter,
    plan,
):

    cases = []

    doctypes = plan.get(
        "doctypes",
        [],
    )

    for doctype_plan in doctypes:

        cases.extend(
            generate_for_doctype(
                counter,
                doctype_plan,
            )
        )

    return cases


# ============================================================
# GENERATE
# ============================================================


def generate():

    plan_data = load_plan()

    if plan_data.get("status") != "ready":

        raise RuntimeError(
            "Planner did not produce a ready plan."
        )

    plan = plan_data.get(
        "plan",
        {},
    )

    target_type = plan.get(
        "target_type"
    )

    counter = TestCaseCounter()

    # --------------------------------------------------------
    # DocType
    # --------------------------------------------------------

    if target_type == "doctype":

        cases = generate_for_doctype(
            counter,
            plan,
        )

    # --------------------------------------------------------
    # Module
    # --------------------------------------------------------

    elif target_type == "module":

        cases = generate_for_module(
            counter,
            plan,
        )

    else:

        raise RuntimeError(
            f"Unsupported target type: {target_type}"
        )

    return {
        "knowledge_type": "erpnext_test_cases",
        "generated_at": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "source_command": plan_data.get(
            "command",
            "",
        ),
        "target_type": target_type,
        "target": plan.get(
            "target",
            "",
        ),
        "total_test_cases": len(cases),
        "test_cases": cases,
    }


# ============================================================
# SAVE
# ============================================================


def save_test_cases(data):

    path = (
        OUTPUT_DIR
        / "latest_test_cases.json"
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


# ============================================================
# MAIN
# ============================================================


def main():

    parser = argparse.ArgumentParser(
        description=(
            "ERPNext Structured "
            "Test Case Generator"
        )
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Print generated test cases.",
    )

    args = parser.parse_args()

    log("======================================")

    log(
        "ERPNext STRUCTURED "
        "TEST CASE GENERATOR"
    )

    log("======================================")

    data = generate()

    path = save_test_cases(data)

    log(
        f"Target: {data['target']}"
    )

    log(
        f"Target type: "
        f"{data['target_type']}"
    )

    log(
        f"Generated test cases: "
        f"{data['total_test_cases']}"
    )

    log(
        f"Saved: {path}"
    )

    if args.show:

        print(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            )
        )

    log("======================================")

    log(
        "TEST CASE GENERATION FINISHED"
    )

    log("======================================")


# ============================================================
# ENTRY
# ============================================================


if __name__ == "__main__":

    main()
