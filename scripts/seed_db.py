"""
Seed the database with Metaculus questions and RSS articles, then run ingestion pipeline.
Usage: python scripts/seed_db.py [--limit N]
"""
import sys
import argparse

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from scripts.fetch_metaculus import fetch_resolved_questions
from scripts.fetch_news_rss import fetch_articles
from ragops.config import get_supabase
from ragops.ingestion import ingest_document


def seed(limit: int = 100):
    sb = get_supabase()
    print("=" * 60)
    print("Phase 1: Fetching Metaculus questions...")
    print("=" * 60)
    questions = fetch_resolved_questions(limit=limit)
    print(f"Metaculus: {len(questions)} questions fetched\n")

    print("=" * 60)
    print("Phase 2: Fetching RSS articles...")
    print("=" * 60)
    articles = fetch_articles()
    print(f"RSS: {len(articles)} articles fetched\n")

    print("=" * 60)
    print("Phase 3: Running ingestion pipeline...")
    print("=" * 60)

    # Get all documents that don't have chunks yet (or re-ingest all)
    all_docs = sb.table("documents").select("id, title, source_type").execute()
    docs = all_docs.data or []
    print(f"Found {len(docs)} documents to ingest")

    total_chunks = 0
    total_conflicts = 0

    for i, doc in enumerate(docs):
        print(f"  [{i+1}/{len(docs)}] Ingesting: {doc['title'][:60]}...")
        try:
            result = ingest_document(doc["id"])
            total_chunks += result["chunks_created"]
            total_conflicts += result["conflicts_found"]
            if result["conflicts_found"] > 0:
                print(f"    ⚠ {result['conflicts_found']} conflict(s) detected")
        except Exception as e:
            print(f"    Error ingesting {doc['id']}: {e}")

    print(f"\nSeed complete:")
    print(f"  Documents: {len(docs)}")
    print(f"  Chunks created: {total_chunks}")
    print(f"  Conflicts found: {total_conflicts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Max Metaculus questions to fetch")
    args = parser.parse_args()
    seed(limit=args.limit)
