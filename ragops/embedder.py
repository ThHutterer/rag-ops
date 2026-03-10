from typing import List
from sentence_transformers import SentenceTransformer
from ragops.config import EMBEDDING_MODEL

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed(text: str) -> List[float]:
    """Returns 384-dim embedding as list of floats for all-MiniLM-L6-v2."""
    model = _get_model()
    return model.encode(text).tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed for efficiency during ingestion. Returns list of 384-dim embeddings."""
    model = _get_model()
    return model.encode(texts).tolist()
