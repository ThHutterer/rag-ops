from typing import List


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
    """
    Splits text into overlapping chunks by word count.
    chunk_size: number of words per chunk
    overlap: number of words to overlap between consecutive chunks
    Returns list of non-empty strings.
    """
    words = text.split()
    if len(words) <= chunk_size:
        stripped = text.strip()
        return [stripped] if stripped else []

    chunks = []
    step = chunk_size - overlap
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start += step

    return chunks
