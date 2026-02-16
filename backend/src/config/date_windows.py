# Analysis Requirements
ANALYSIS_WINDOW_DAYS = 14  # 7 days (current) vs 7 days (previous)
GSC_LAG_DAYS = 2           # GSC data stabilizes ~2 days later

# Derived Windows
INGESTION_WINDOW_DAYS = ANALYSIS_WINDOW_DAYS + GSC_LAG_DAYS  # Exactly 16 days
HALF_ANALYSIS_WINDOW = ANALYSIS_WINDOW_DAYS // 2             # 7 days

# Standard daily settings
DAILY_INGEST_DAYS = 1      # Normal daily run
