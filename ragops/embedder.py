import os
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def embed(text: str) -> List[float]:
    """Returns 1536-dim embedding using text-embedding-3-small (matches n8n)."""
    response = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def embed_batch(texts: List[str]) -> List[List[float]]:
    response = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [d.embedding for d in sorted(response.data, key=lambda x: x.index)]
