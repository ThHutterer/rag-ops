import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

CONFLICT_SIMILARITY_THRESHOLD = float(os.getenv("CONFLICT_SIMILARITY_THRESHOLD", "0.88"))
DECAY_HALF_LIFE_DAYS = int(os.getenv("DECAY_HALF_LIFE_DAYS", "180"))


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgrespass90"),
    )
