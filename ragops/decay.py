def compute_decay(days_since_modified: int, half_life_days: int = 180) -> float:
    """
    Exponential decay: 0.5 ** (days_since_modified / half_life_days)
    Returns 1.0 if days_since_modified <= 0.
    Note: Metaculus chunks must be locked at 1.0 by the CALLER (ingestion.py).
    """
    if days_since_modified <= 0:
        return 1.0
    return 0.5 ** (days_since_modified / half_life_days)
