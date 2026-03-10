SOURCE_TYPE_SCORES = {
    "metaculus": 1.0,
    "arxiv_paper": 0.75,
    "news_article": 0.5,
}

REVIEW_STATUS_MULTIPLIER = {
    "resolved": 1.0,
    "published": 0.85,
    "preprint": 0.7,
}


def compute_authority_score(source_type: str, review_status: str) -> float:
    """
    Returns float 0.0–1.0.
    Formula: SOURCE_TYPE_SCORES[source_type] * REVIEW_STATUS_MULTIPLIER[review_status]
    """
    base = SOURCE_TYPE_SCORES.get(source_type, 0.3)
    multiplier = REVIEW_STATUS_MULTIPLIER.get(review_status, 0.8)
    return max(0.0, min(1.0, base * multiplier))
