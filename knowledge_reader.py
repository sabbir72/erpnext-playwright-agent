import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge" / "doctypes"


def normalize(text):
    return " ".join(text.lower().split())


def load_knowledge(doctype):
    path = KNOWLEDGE_DIR / (
        doctype.strip().lower().replace(" ", "_") + ".json"
    )

    if not path.exists():
        return None

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def search_knowledge(query):
    query = normalize(query)
    results = []

    for path in KNOWLEDGE_DIR.glob("*.json"):

        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )
        except Exception:
            continue

        searchable = normalize(
            json.dumps(
                data,
                ensure_ascii=False
            )
        )

        score = 0

        for word in query.split():
            if word in searchable:
                score += 1

        if score:
            results.append(
                {
                    "score": score,
                    "doctype": data.get(
                        "doctype",
                        path.stem
                    ),
                    "data": data,
                }
            )

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results


if __name__ == "__main__":

    query = input(
        "Search ERP knowledge: "
    ).strip()

    results = search_knowledge(query)

    if not results:
        print("No knowledge found.")
    else:

        for item in results[:5]:

            print(
                f"\n=== {item['doctype']} "
                f"(score={item['score']}) ==="
            )

            print(
                json.dumps(
                    item["data"],
                    indent=2,
                    ensure_ascii=False
                )[:5000]
            )