SOURCE_TYPE_SCORES = {
    "metaculus": 1.0,
    "ki_text": 1.0,
    "alt_ki_text": 0.8,
    "bad_ki_text": 0.3,
    "arxiv_paper": 0.75,
    "news_article": 0.5,
}

REVIEW_STATUS_MULTIPLIER = {
    "resolved": 1.0,
    "verified": 1.0,
    "published": 0.85,
    "preprint": 0.7,
    "draft": 1.0,  # bad_ki_text uses draft; score comes entirely from source type
}

# Source types whose decay_score is locked at 1.0 permanently
NO_DECAY_SOURCE_TYPES = {"metaculus", "ki_text"}


def compute_authority_score(source_type: str, review_status: str) -> float:
    """
    Returns float 0.0–1.0.
    Formula: SOURCE_TYPE_SCORES[source_type] * REVIEW_STATUS_MULTIPLIER[review_status]
    """
    base = SOURCE_TYPE_SCORES.get(source_type, 0.3)
    multiplier = REVIEW_STATUS_MULTIPLIER.get(review_status, 0.8)
    return max(0.0, min(1.0, base * multiplier))
