"""
Populate retrieval_log with simulated queries for demo realism.
Usage: python scripts/simulate_retrievals.py
"""
import sys
import random
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")
from ragops.config import get_supabase

SAMPLE_QUERIES = [
    "Will AI surpass human performance on coding benchmarks?",
    "What is the current state of large language models?",
    "Climate change predictions for 2030",
    "Autonomous vehicles regulatory landscape",
    "Nuclear fusion commercial viability",
    "mRNA vaccine technology development",
    "Quantum computing practical applications",
    "AI safety research progress",
    "Renewable energy cost trends",
    "Protein folding and drug discovery",
    "Social media regulation outcomes",
    "Cryptocurrency adoption by institutions",
    "Remote work productivity research",
    "Gene therapy clinical trials",
    "Space launch cost reduction",
]

FEEDBACKS = [None, None, None, "good", "good", "bad"]  # weighted


def simulate_retrievals(n: int = 50):
    sb = get_supabase()

    # Get all chunk IDs
    chunks_result = sb.table("chunks").select("id").execute()
    chunk_ids = [c["id"] for c in (chunks_result.data or [])]

    if not chunk_ids:
        print("No chunks found. Run seed_db.py first.")
        return

    print(f"Simulating {n} retrieval log entries...")
    inserted = 0

    for i in range(n):
        query = random.choice(SAMPLE_QUERIES)
        # Simulate 3-5 retrieved chunks
        k = random.randint(3, 5)
        retrieved_chunks = random.sample(chunk_ids, min(k, len(chunk_ids)))
        feedback = random.choice(FEEDBACKS)

        # Spread over last 30 days
        days_ago = random.randint(0, 30)
        retrieved_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

        row = {
            "query": query,
            "chunk_ids": retrieved_chunks,
            "retrieved_at": retrieved_at,
            "feedback": feedback,
        }

        try:
            sb.table("retrieval_log").insert(row).execute()
            inserted += 1
        except Exception as e:
            print(f"  Error inserting log entry: {e}")

    print(f"Inserted {inserted} retrieval log entries.")


if __name__ == "__main__":
    simulate_retrievals(50)
