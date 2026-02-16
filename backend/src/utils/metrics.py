from __future__ import annotations
"""
Centralized metrics utilities for GSC Quick View
"""

def safe_delta_pct(current: float, previous: float) -> float:
    """
    Unified delta logic:
    - previous > 0 → standard percentage delta
    - previous == 0 and current > 0 → 100.0
    - previous == 0 and current == 0 → 0.0
    """
    if previous > 0:
        return round(((current - previous) / previous) * 100, 2)
    elif current > 0:
        return 100.0
    else:
        return 0.0
