"""
Canonical configuration for GSC date windows and analysis thresholds.
Centralizing these values ensures the ingestion pipeline guarantees 
the data required by the analyzers.
"""

# Analysis Requirements
ANALYSIS_WINDOW_DAYS = 14  # 7 days (current) vs 7 days (previous)
REQUIRED_HISTORY_DAYS = 14 # Threshold to trigger analysis (e.g. 14 distinct dates)

# GSC Stabilization & Lag
GSC_LAG_DAYS = 2  # GSC data stabilizes ~2 days later

# Ingestion Settings
BACKFILL_RANGE_DAYS = 28 # Safely cover the analysis window + buffers
SAFETY_BUFFER_DAYS = 7   # Extra buffer days during backfill

# Derived Windows
# (Used in main.py for ingestion triggers)
DAILY_INGEST_DAYS = 1 # How many days we normally ingest in a daily run
