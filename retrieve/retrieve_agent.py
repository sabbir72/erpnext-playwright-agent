"""
ERPNext AI QA - Retrieve Agent

Purpose:
    Retrieve relevant, already-stored ERPNext knowledge for an AI planner.

Pipeline position:
    Discovery -> Validation -> Normalize -> Store -> Retrieve -> Plan

Design:
    - Deterministic local retrieval; no internet and no invented facts.
    - Searches normalized knowledge first, then dedicated knowledge categories.
    - Uses an exact main DocType filter when supplied.
    - Scores query matches transparently.
    - Returns a compact AI-readable context.
    - Saves retrieval results under data/retrieval/.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# retrieve/retrieve_agent.py -> project root
BASE_DIR = Path(__file__).resolve().parents[1]

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
NORMALIZED_DIR = KNOWLEDGE_DIR / "normalized"
BUSINESS_RULES_DIR = KNOWLEDGE_DIR / "business_rules"
WORKFLOWS_DIR = KNOWLEDGE_DIR / "workflows"
RELATIONSHIPS_DIR = KNOWLEDGE_DIR / "relationships"
TEST_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "test_knowledge"

# Raw discovery is only a fallback when structured knowledge is unavailable.
DISCOVERY_DIR = BASE_DIR / "data" / "discovery"
RETRIEVAL_DIR = BASE_DIR / "data" / "retrieval"
RETRIEVAL_DIR.mkdir(parents=True, exist_ok=True)

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for",
    "from", "how", "is", "it", "of", "on", "or", "the", "to", "what",
    "which", "with", "in", "me", "show", "give", "tell", "about", "does",
    "do", "this", "that", "document", "details", "information",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_text(value: Any) -> str:
    return clean_text(value).lower()


def clean_doctype_name(value: Any) -> str:
    """
    Main DocType name rule:
        New Contract -> Contract
        Contract      -> Contract

    'New' is a Search/UI word, not part of the main knowledge identity.
    """
    name = clean_text(value)
    if name.lower().startswith("new "):
        return name[4:].strip()
    return name


def tokenize(value: Any) -> list[str]:
    words = re.findall(r"[a-z0-9_]+", normalize_text(value))
    return [word for word in words if word not in STOP_WORDS]


def safe_slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", normalize_text(value)).strip("-_")
    return slug or "query"


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def extract_doctype(data: dict[str, Any]) -> str:
    document = data.get("document")
    candidates = [
        data.get("doctype"),
        data.get("document_name"),
        document.get("doctype") if isinstance(document, dict) else None,
    ]
    for value in candidates:
        name = clean_doctype_name(value)
        if name:
            return name
    return ""


def knowledge_type(path: Path, data: dict[str, Any]) -> str:
    explicit = clean_text(data.get("knowledge_type"))
    if explicit:
        return explicit
    return path.parent.name or "knowledge"


def iter_knowledge_files() -> list[Path]:
    """
    Prefer structured knowledge.
    Raw discovery JSON is used only when no structured knowledge JSON exists.
    """
    files: list[Path] = []
    for directory in (
        NORMALIZED_DIR,
        BUSINESS_RULES_DIR,
        WORKFLOWS_DIR,
        RELATIONSHIPS_DIR,
        TEST_KNOWLEDGE_DIR,
    ):
        files.extend(directory.glob("*.json"))

    if files:
        return sorted(set(files))

    return sorted(DISCOVERY_DIR.glob("*.json"))


def flatten_text(value: Any, limit: int = 30000) -> str:
    """Turn nested JSON into searchable text without modifying source data."""
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(" ".join(parts)) >= limit:
            return
        if item is None:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                parts.append(str(key))
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        else:
            parts.append(str(item))

    walk(value)
    return clean_text(" ".join(parts))[:limit]


def get_fields(data: dict[str, Any]) -> list[dict[str, Any]]:
    document = data.get("document")
    if isinstance(document, dict) and isinstance(document.get("fields"), list):
        return [x for x in document["fields"] if isinstance(x, dict)]
    if isinstance(data.get("fields"), list):
        return [x for x in data["fields"] if isinstance(x, dict)]
    return []


def field_relevance(field: dict[str, Any], query_tokens: set[str]) -> float:
    values = " ".join(
        clean_text(field.get(key, ""))
        for key in (
            "fieldname", "label", "fieldtype", "options", "description",
            "tab", "section", "depends_on", "mandatory_depends_on",
        )
    )
    field_tokens = set(tokenize(values))
    return float(len(query_tokens & field_tokens))


def compact_field(field: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "fieldname", "label", "fieldtype", "required", "options",
        "placeholder", "description", "read_only", "hidden", "default",
        "depends_on", "mandatory_depends_on", "fetch_from", "allow_on_submit",
        "tab", "section", "actions", "locator_hints", "testability",
    )
    return {key: field[key] for key in allowed if key in field}


def compact_content(data: dict[str, Any], query_tokens: set[str]) -> dict[str, Any]:
    """Return useful structured context, prioritizing fields matching the query."""
    document = data.get("document")
    source = document if isinstance(document, dict) else data

    fields = get_fields(data)
    ranked_fields = sorted(
        fields,
        key=lambda item: field_relevance(item, query_tokens),
        reverse=True,
    )

    # Keep all fields for field/schema queries; cap only when there are many.
    field_limit = 200
    selected_fields = ranked_fields[:field_limit]

    result: dict[str, Any] = {
        "doctype": extract_doctype(data),
        "fields": [compact_field(item) for item in selected_fields],
        "tabs": source.get("tabs", []) if isinstance(source.get("tabs", []), list) else [],
        "sections": source.get("sections", []) if isinstance(source.get("sections", []), list) else [],
        "buttons": source.get("buttons", []) if isinstance(source.get("buttons", []), list) else [],
        "links": source.get("links", []) if isinstance(source.get("links", []), list) else [],
        "elements": source.get("elements", []) if isinstance(source.get("elements", []), list) else [],
    }

    for key in ("relationships", "business_rules", "workflows", "qa_knowledge"):
        if key in data and data[key]:
            result[key] = data[key]

    return result


def score_file(query: str, data: dict[str, Any]) -> tuple[float, list[str]]:
    """Transparent lexical ranking; no generated or inferred facts."""
    query_text = normalize_text(query)
    query_tokens = set(tokenize(query))
    if not query_tokens and not query_text:
        return 0.0, []

    doctype = normalize_text(extract_doctype(data))
    blob = normalize_text(flatten_text(data))
    score = 0.0
    reasons: list[str] = []

    if query_text and query_text in blob:
        score += 10.0
        reasons.append("exact_phrase")

    if doctype and doctype in query_text:
        score += 8.0
        reasons.append("doctype_match")

    field_blob = normalize_text(
        " ".join(
            f"{field.get('fieldname', '')} {field.get('label', '')} "
            f"{field.get('fieldtype', '')} {field.get('options', '')}"
            for field in get_fields(data)
        )
    )

    for token in query_tokens:
        if token in doctype.split():
            score += 8.0
            reasons.append(f"doctype_token:{token}")
        elif token in field_blob:
            score += 4.0
            reasons.append(f"field:{token}")
        elif token in blob:
            score += 1.0
            reasons.append(f"content:{token}")

    return score, sorted(set(reasons))


def retrieve(
    query: str,
    doctype: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    query = clean_text(query)
    doctype = clean_doctype_name(doctype) if doctype else None
    query_tokens = set(tokenize(query))

    candidates: list[dict[str, Any]] = []

    for path in iter_knowledge_files():
        data = load_json(path)
        if not data:
            continue

        actual_doctype = extract_doctype(data)
        if doctype and normalize_text(actual_doctype) != normalize_text(doctype):
            continue

        score, reasons = score_file(query, data)
        if score <= 0:
            continue

        candidates.append({
            "score": round(score, 3),
            "source_file": str(path.relative_to(BASE_DIR)),
            "knowledge_type": knowledge_type(path, data),
            "doctype": actual_doctype,
            "reasons": reasons,
            "context": compact_content(data, query_tokens),
        })

    candidates.sort(
        key=lambda item: (-item["score"], item["doctype"], item["source_file"])
    )

    results = candidates[:max(1, min(top_k, 20))]

    return {
        "retrieval_version": "1.0",
        "retrieved_at": now_iso(),
        "query": query,
        "doctype_filter": doctype,
        "result_count": len(results),
        "results": results,
    }


def save_result(result: dict[str, Any]) -> Path:
    base = result.get("doctype_filter") or result.get("query") or "query"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = RETRIEVAL_DIR / f"{safe_slug(base)}_{timestamp}.json"
    temp = output.with_suffix(".json.tmp")

    temp.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(output)
    return output


def print_result(result: dict[str, Any]) -> None:
    print("\n=== RETRIEVAL RESULT ===")
    print(f"Query: {result['query']}")
    print(f"DocType filter: {result['doctype_filter'] or 'None'}")
    print(f"Results: {result['result_count']}")

    for index, item in enumerate(result["results"], start=1):
        print(
            f"\n{index}. {item['doctype'] or 'Unknown'} | "
            f"score={item['score']} | {item['knowledge_type']}"
        )
        print(f"   Source: {item['source_file']}")
        if item["reasons"]:
            print("   Match: " + ", ".join(item["reasons"][:10]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retrieve ERPNext AI QA knowledge."
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language retrieval query.",
    )
    parser.add_argument(
        "--doctype",
        help="Optional exact main DocType filter. Use 'Contract', not 'New Contract'.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Maximum number of results (1-20).",
    )
    args = parser.parse_args()

    result = retrieve(
        query=args.query,
        doctype=args.doctype,
        top_k=args.top_k,
    )
    output = save_result(result)
    print_result(result)
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
