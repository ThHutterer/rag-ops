import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

CONFLICT_SIMILARITY_THRESHOLD = float(os.getenv("CONFLICT_SIMILARITY_THRESHOLD", "0.88"))
DECAY_HALF_LIFE_DAYS = int(os.getenv("DECAY_HALF_LIFE_DAYS", "180"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


def get_supabase() -> Client:
    """Returns a configured Supabase client using SUPABASE_URL and SUPABASE_KEY from env."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(url, key)
