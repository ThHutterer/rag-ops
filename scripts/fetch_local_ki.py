"""
Clears existing Supabase data and ingests local KI text files.

Source types and authority scores:
  ki_text     → 1.0  (authoritative, no decay)
  alt_ki_text → 0.8  (alternative version, decays normally)
  bad_ki_text → 0.3  (low-quality, decays normally)

Usage: python scripts/fetch_local_ki.py [--dataset-dir PATH] [--dry-run]
"""
import sys
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()

from ragops.config import get_supabase
from ragops.authority import compute_authority_score
from ragops.ingestion import ingest_document

DATASET_DIR = Path("/Users/thomas/Documents/code/n8n-template/rag_dataset")

FOLDER_CONFIG = {
    "ki_text": {
        "source_type": "ki_text",
        "review_status": "verified",
        "authority_score": 1.0,
    },
    "alt_ki_text": {
        "source_type": "alt_ki_text",
        "review_status": "published",
        "authority_score": 0.8,
    },
    "bad_ki_text": {
        "source_type": "bad_ki_text",
        "review_status": "draft",
        "authority_score": 0.3,
    },
}


def clear_database(sb):
    """Delete all rows from all tables (preserves schema and RLS)."""
    print("Clearing existing data...")
    # Order matters due to foreign key constraints
    sb.table("retrieval_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    sb.table("quarantine_queue").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    sb.table("chunks").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    sb.table("documents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print("  Done.\n")


def load_files(dataset_dir: Path) -> list[dict]:
    """
    Read all .txt files from the three folders.
    Skips files with ' 2' in the stem (macOS duplicate copies).
    Returns list of document dicts ready for insertion.
    """
    docs = []
    now = datetime.now(timezone.utc).isoformat()

    for folder_name, config in FOLDER_CONFIG.items():
        folder = dataset_dir / folder_name
        if not folder.exists():
            print(f"  WARNING: folder not found: {folder}")
            continue

        files = sorted(folder.glob("*.txt"))
        skipped = 0
        for f in files:
            # Skip macOS " 2" duplicates (e.g. "foo 2.txt")
            if " 2" in f.stem:
                skipped += 1
                continue

            content = f.read_text(encoding="utf-8", errors="replace").strip()
            if not content:
                continue

            # Derive a clean title from filename
            # e.g. "Configuring_a_Network_Printer_ki_text.txt" → "Configuring a Network Printer"
            stem = f.stem
            suffix = f"_{folder_name}"
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
            title = stem.replace("_", " ")

            docs.append(
                {
                    "title": title,
                    "content": content,
                    "source_type": config["source_type"],
                    "review_status": config["review_status"],
                    "authority_score": config["authority_score"],
                    "created_at": now,
                    "last_modified": now,
                    "url": None,
                    "author": None,
                }
            )

        print(f"  {folder_name}: {len([f for f in files if ' 2' not in f.stem])} files loaded, {skipped} duplicates skipped")

    return docs


def insert_documents(sb, docs: list[dict]) -> list[str]:
    """Insert documents into DB, return list of inserted IDs."""
    ids = []
    for doc in docs:
        result = sb.table("documents").insert(doc).execute()
        ids.append(result.data[0]["id"])
    return ids


def seed_local(dataset_dir: Path, dry_run: bool = False):
    sb = get_supabase()

    print("=" * 60)
    print("Phase 1: Clearing existing database...")
    print("=" * 60)
    if not dry_run:
        clear_database(sb)
    else:
        print("  [dry-run] skipped\n")

    print("=" * 60)
    print("Phase 2: Loading local KI files...")
    print("=" * 60)
    docs = load_files(dataset_dir)
    print(f"Total: {len(docs)} documents\n")

    if dry_run:
        print("[dry-run] Stopping before DB writes.")
        return

    print("=" * 60)
    print("Phase 3: Inserting documents...")
    print("=" * 60)
    doc_ids = insert_documents(sb, docs)
    print(f"  Inserted {len(doc_ids)} documents\n")

    print("=" * 60)
    print("Phase 4: Running ingestion pipeline (embed + conflict detection)...")
    print("=" * 60)
    total_chunks = 0
    total_conflicts = 0

    for i, (doc_id, doc) in enumerate(zip(doc_ids, docs)):
        label = f"[{i+1}/{len(doc_ids)}] [{doc['source_type']}] {doc['title'][:50]}"
        print(f"  {label}...")
        try:
            result = ingest_document(doc_id)
            total_chunks += result["chunks_created"]
            total_conflicts += result["conflicts_found"]
            if result["conflicts_found"] > 0:
                print(f"    ⚠ {result['conflicts_found']} conflict(s) detected")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\nSeed complete:")
    print(f"  Documents : {len(doc_ids)}")
    print(f"  Chunks    : {total_chunks}")
    print(f"  Conflicts : {total_conflicts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Load files but don't write to DB")
    args = parser.parse_args()
    seed_local(args.dataset_dir, dry_run=args.dry_run)
