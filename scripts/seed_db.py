"""
Seed the database with local KI text files, then run ingestion pipeline.
Usage: python scripts/seed_db.py
"""
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from scripts.fetch_local_ki import seed_local, DATASET_DIR

if __name__ == "__main__":
    seed_local(DATASET_DIR)
