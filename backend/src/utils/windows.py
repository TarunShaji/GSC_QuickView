from __future__ import annotations
"""
Centralized window logic for GSC metrics.
Handles date anchoring, split/aggregation, and canonical windows for consistent analysis.
"""

from datetime import date, timedelta
from typing import Dict, List, Any, Tuple
from src.config.date_windows import ANALYSIS_WINDOW_DAYS, HALF_ANALYSIS_WINDOW

def get_most_recent_date(rows: List[Dict[str, Any]]) -> date:
    """Find the most recent date in a list of metric rows."""
    if not rows:
        return date.today()
    return max(row['date'] for row in rows)

def split_rows_by_window(rows: List[Dict[str, Any]], most_recent_date: date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split a list of metric rows into 'last_7' and 'prev_7' windows 
    based on the canonical HALF_ANALYSIS_WINDOW.
    """
    last_window = []
    prev_window = []
    
    window_size = HALF_ANALYSIS_WINDOW
    total_window = ANALYSIS_WINDOW_DAYS
    
    for row in rows:
        row_date = row['date']
        days_ago = (most_recent_date - row_date).days
        
        # Last window (e.g. 0-6 days ago)
        if 0 <= days_ago < window_size:
            last_window.append(row)
        # Previous window (e.g. 7-13 days ago)
        elif window_size <= days_ago < total_window:
            prev_window.append(row)
            
    return last_window, prev_window

def aggregate_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate clicks, impressions, and position for a window of rows.
    Computes CTR and Avg Position correctly.
    """
    clicks = 0
    impressions = 0
    position_sum = 0.0
    position_days = 0
    days_with_data = len(set(row['date'] for row in rows))
    
    for row in rows:
        clicks += row.get('clicks', 0) or 0
        impressions += row.get('impressions', 0) or 0
        if row.get('position') is not None:
            position_sum += float(row['position'])
            position_days += 1
            
    ctr = (clicks / impressions) if impressions > 0 else 0.0
    avg_position = (position_sum / position_days) if position_days > 0 else 0.0
    
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "avg_position": avg_position,
        "days_with_data": days_with_data
    }
