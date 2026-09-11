"""
ERPNext AI QA - Analyzer

Reads Executor output and produces a stable analysis report for Orchestrator.

Input:
    data/executions/latest_execution.json

Output:
    data/reports/latest_analysis.json

Analyzer never opens ERPNext and never performs browser actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
EXECUTION_DIR = BASE_DIR / "data" / "executions"
REPORT_DIR = BASE_DIR / "data" / "reports"

EXECUTION_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================


def clean(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Execution file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid execution JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Execution JSON root must be an object.")

    return data


# ============================================================
# CLASSIFICATION
# ============================================================


def classify_result(execution: dict[str, Any]) -> str:
    results = execution.get("results", [])
    if not isinstance(results, list):
        results = []

    statuses = {
        clean(item.get("status")).upper() for item in results if isinstance(item, dict)
    }

    if "FAILED" in statuses:
        return "FAIL"

    if not results:
        return "PARTIAL"

    has_passed = "PASSED" in statuses
    has_blocked = "BLOCKED" in statuses
    has_deferred = "DEFERRED_TO_NAVIGATOR" in statuses

    if has_blocked and not has_passed and not has_deferred:
        return "BLOCKED"

    if has_blocked or has_deferred:
        return "PARTIAL"

    return "PASS"


# ============================================================
# RESULT BREAKDOWN
# ============================================================


def analyze_results(execution: dict[str, Any]) -> dict[str, Any]:
    results = execution.get("results", [])
    if not isinstance(results, list):
        results = []

    groups = {
        "passed": [],
        "failed": [],
        "blocked": [],
        "deferred": [],
        "skipped": [],
    }

    for item in results:
        if not isinstance(item, dict):
            continue

        status = clean(item.get("status")).upper()

        if status == "PASSED":
            groups["passed"].append(item)
        elif status == "FAILED":
            groups["failed"].append(item)
        elif status == "BLOCKED":
            groups["blocked"].append(item)
        elif status == "DEFERRED_TO_NAVIGATOR":
            groups["deferred"].append(item)
        elif status == "SKIPPED":
            groups["skipped"].append(item)

    groups["counts"] = {
        "total": len(results),
        "passed": len(groups["passed"]),
        "failed": len(groups["failed"]),
        "blocked": len(groups["blocked"]),
        "deferred": len(groups["deferred"]),
        "skipped": len(groups["skipped"]),
    }

    return groups


# ============================================================
# FAILURES
# ============================================================


def build_failures(groups: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []

    for item in groups.get("failed", []):
        failures.append(
            {
                "type": "execution_failure",
                "fieldname": clean(item.get("fieldname")),
                "label": clean(item.get("label") or item.get("button")),
                "fieldtype": clean(item.get("fieldtype")),
                "action": clean(item.get("action")),
                "error": clean(item.get("error")) or "Unknown execution error",
            }
        )

    return failures


# ============================================================
# BLOCKED ACTIONS
# ============================================================


def build_blocked_actions(groups: dict[str, Any]) -> list[dict[str, Any]]:
    blocked = []

    for item in groups.get("blocked", []):
        blocked.append(
            {
                "action": clean(item.get("action")),
                "reason": clean(item.get("reason"))
                or "Business mutation intentionally blocked",
            }
        )

    return blocked


# ============================================================
# DEFERRED ACTIONS
# ============================================================


def build_deferred_actions(groups: dict[str, Any]) -> list[dict[str, Any]]:
    deferred = []

    for item in groups.get("deferred", []):
        deferred.append(
            {
                "action": clean(item.get("action")),
                "owner": "Navigator",
                "reason": "Navigation action is handled by navigator.py",
            }
        )

    return deferred


# ============================================================
# RECOMMENDATION
# ============================================================


def recommendation(status: str, counts: dict[str, int]) -> str:
    if status == "PASS":
        return "Safe Executor actions completed without execution failures."

    if status == "FAIL":
        return (
            "Execution failure detected. Check failed fields/buttons, "
            "locator strategy and screenshots before retrying."
        )

    if status == "BLOCKED":
        return (
            "Only unsafe business mutations were requested and they were "
            "intentionally blocked. No mutation was executed."
        )

    if counts.get("deferred", 0) and counts.get("blocked", 0):
        return (
            "Partial result: navigation was deferred to Navigator and "
            "unsafe business mutations were blocked."
        )

    if counts.get("deferred", 0):
        return "Partial result: navigation actions were deferred to Navigator."

    if counts.get("blocked", 0):
        return "Partial result: one or more business mutations were blocked."

    return "Partial execution; review individual action results."


# ============================================================
# SCREENSHOT EVIDENCE
# ============================================================


def screenshot_evidence(doctype: str) -> list[str]:
    screenshot_dir = BASE_DIR / "data" / "screenshots"

    if not screenshot_dir.exists():
        return []

    target = clean(doctype).lower().replace(" ", "-")
    output = []

    for path in sorted(screenshot_dir.iterdir()):
        if not path.is_file():
            continue
        if target and target in path.stem.lower():
            output.append(str(path))

    return output[:20]


# ============================================================
# REPORT
# ============================================================


def build_report(execution: dict[str, Any]) -> dict[str, Any]:
    doctype = clean(execution.get("doctype") or execution.get("document_name"))
    status = classify_result(execution)
    groups = analyze_results(execution)
    counts = groups["counts"]

    return {
        "analysis_version": "1.0",
        "status": status,
        "doctype": doctype,
        "document_name": doctype,
        "search_name": clean(execution.get("search_name")),
        "execution_status": clean(execution.get("status")).upper(),
        "current_url": clean(execution.get("current_url")),
        "safety": {
            "existing_documents_skipped": bool(
                execution.get("existing_documents_skipped", True)
            ),
            "business_data_mutated": bool(
                execution.get("business_data_mutated", False)
            ),
            "blocked_business_mutations": bool(
                execution.get("blocked_business_mutations", True)
            ),
            "system_ui_blocked": bool(execution.get("system_ui_blocked", True)),
        },
        "summary": counts,
        "failures": build_failures(groups),
        "blocked_actions": build_blocked_actions(groups),
        "deferred_actions": build_deferred_actions(groups),
        "skipped_actions": groups["skipped"],
        "evidence": {
            "screenshots": screenshot_evidence(doctype),
        },
        "recommendation": recommendation(status, counts),
    }


# ============================================================
# SAVE
# ============================================================


def save_report(report: dict[str, Any]) -> Path:
    output = REPORT_DIR / "latest_analysis.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


# ============================================================
# CLI
# ============================================================


def main() -> int:
    parser = argparse.ArgumentParser(description="ERPNext AI QA Analyzer")
    parser.add_argument(
        "--file",
        default="latest_execution.json",
        help="Execution JSON filename or path.",
    )
    args = parser.parse_args()

    try:
        execution_path = Path(args.file)
        if not execution_path.is_absolute():
            execution_path = EXECUTION_DIR / execution_path

        execution = load_json(execution_path)
        report = build_report(execution)
        output = save_report(report)

        print("=" * 60)
        print("ANALYZER RESULT")
        print("=" * 60)
        print(f"Status   : {report['status']}")
        print(f"DocType  : {report['doctype']}")
        print(f"Passed   : {report['summary']['passed']}")
        print(f"Failed   : {report['summary']['failed']}")
        print(f"Blocked  : {report['summary']['blocked']}")
        print(f"Deferred : {report['summary']['deferred']}")
        print(f"Output   : {output}")

        return 0

    except Exception as exc:
        print(f"[ANALYZER] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
