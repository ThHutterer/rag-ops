import os
import sys
import requests
from typing import List

sys.path.insert(0, ".")
from ragops.authority import compute_authority_score

METACULUS_API = "https://www.metaculus.com/api2/questions/"
PAGE_SIZE = 20


def _get_headers():
    token = os.getenv("METACULUS_TOKEN", "")
    headers = {"User-Agent": "rag-ops-portfolio/1.0", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers


def _parse_resolution(question: dict):
    res = question.get("resolution")
    if res is None:
        return None
    if isinstance(res, bool):
        return "YES" if res else "NO"
    if isinstance(res, (int, float)):
        return str(res)
    return str(res)


def _parse_question_content(q: dict) -> str:
    parts = []
    if q.get("description"):
        parts.append(q["description"])
    # question sub-object may contain description/resolution_criteria
    sub = q.get("question") or {}
    if isinstance(sub, dict):
        if sub.get("description"):
            parts.append(sub["description"])
        if sub.get("resolution_criteria"):
            parts.append(sub["resolution_criteria"])
    if not parts:
        parts.append(q.get("title", ""))
    return "\n\n".join(filter(None, parts))


def fetch_resolved_questions(limit: int = 100, dry_run: bool = False) -> List[dict]:
    """
    Fetches resolved questions from Metaculus API.
    If dry_run=True, returns data without inserting into DB.
    """
    from dotenv import load_dotenv
    load_dotenv()

    results = []
    url = METACULUS_API
    params = {"limit": PAGE_SIZE}
    headers = _get_headers()
    page = 1

    while url and len(results) < limit:
        print(f"Fetching page {page}...")
        try:
            if page == 1:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
            else:
                resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Error fetching page {page}: {e}")
            break

        questions = data.get("results", [])
        for q in questions:
            if len(results) >= limit:
                break

            # Filter for actually resolved questions (client-side)
            is_resolved = q.get("resolved") is True or str(q.get("resolved", "")).lower() == "true"
            actual_resolve = q.get("actual_resolve_time")
            if not is_resolved and not actual_resolve:
                continue

            content = _parse_question_content(q)
            resolution = _parse_resolution(q)

            row = {
                "title": q.get("title", "Untitled"),
                "content": content,
                "source_type": "metaculus",
                "author": q.get("author_username"),
                "created_at": q.get("created_at"),
                "last_modified": q.get("edited_at") or q.get("created_at"),
                "review_status": "resolved",
                "authority_score": compute_authority_score("metaculus", "resolved"),
                "url": f"https://www.metaculus.com/questions/{q.get('id', '')}/",
                "metaculus_question_id": int(q.get("id", 0)),
                "metaculus_resolution": resolution,
                "metaculus_resolution_date": actual_resolve,
            }
            results.append(row)

        url = data.get("next")
        page += 1

    print(f"Fetched {len(results)} resolved questions")

    if not dry_run and results:
        from ragops.config import get_supabase
        sb = get_supabase()
        inserted = 0
        for row in results:
            try:
                existing = sb.table("documents").select("id").eq(
                    "metaculus_question_id", row["metaculus_question_id"]
                ).execute()
                if existing.data:
                    sb.table("documents").update(row).eq(
                        "metaculus_question_id", row["metaculus_question_id"]
                    ).execute()
                else:
                    sb.table("documents").insert(row).execute()
                    inserted += 1
            except Exception as e:
                print(f"  Error inserting question {row.get('metaculus_question_id')}: {e}")
        print(f"Inserted {inserted} new questions")

    return results


if __name__ == "__main__":
    questions = fetch_resolved_questions(limit=100)
    print(f"Done. Total: {len(questions)}")
