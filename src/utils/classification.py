"""
Classification Logic Utility

Standardizes metrics classification across all analyzers and the database.
"""

def classify_delta(delta_pct: float, threshold: float = 40.0) -> str:
    """
    Classifies a percentage change into canonical buckets.
    
    Returns:
        'significant_drop', 'significant_gain', or 'flat'
    """
    if delta_pct <= -threshold:
        return 'significant_drop'
    elif delta_pct >= threshold:
        return 'significant_gain'
    else:
        return 'flat'
