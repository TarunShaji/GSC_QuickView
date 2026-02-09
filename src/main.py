"""
GSC Quick View - Sequential Ingestion + Parallel Analysis

This script:
1. Authenticates with Google Search Console API
2. Fetches all accessible properties
3. Filters to Owner/Full User only
4. Groups properties by base domain
5. Persists websites and properties to Supabase
6. Ingests daily metrics (property/page/device) SEQUENTIALLY
7. Analyzes visibility (page/device) in PARALLEL
8. Persists analysis results to database

Architecture:
- Phase 0 (Sequential): Auth + Property Sync
- Phase 1 (Sequential): Property/Page/Device Ingestion (GSC API - NOT thread-safe)
- Phase 2 (Parallel): Page/Device Analysis (DB-only - thread-safe)

CRITICAL: GSC API client is NOT thread-safe. Parallel API calls cause SSL errors.
"""

from gsc_client import GSCClient
from property_grouper import PropertyGrouper
from db_persistence import DatabasePersistence
from property_metrics_daily_ingestor import PropertyMetricsDailyIngestor
from page_metrics_daily_ingestor import PageMetricsDailyIngestor
from device_metrics_daily_ingestor import DeviceMetricsDailyIngestor
from page_visibility_analyzer import PageVisibilityAnalyzer
from device_visibility_analyzer import DeviceVisibilityAnalyzer
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


# Global pipeline state for frontend polling
PIPELINE_LOCK = Lock()
PIPELINE_STATE = {
    "is_running": False,
    "phase": "idle",  # idle | ingestion | analysis | completed | failed
    "current_step": None,  # Current step description
    "progress": {"current": 0, "total": 0},  # Progress tracking
    "completed_steps": [],
    "error": None,
    "started_at": None
}


def update_pipeline_state(**kwargs):
    """Thread-safe update of PIPELINE_STATE"""
    with PIPELINE_LOCK:
        for key, value in kwargs.items():
            PIPELINE_STATE[key] = value


def log_step(message, level="INFO"):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️ ",
        "PROGRESS": "⏳"
    }.get(level, "")
    print(f"[{timestamp}] {prefix} {message}")


def run_pipeline():
    """
    Execute the full GSC analytics pipeline.
    
    IMPORTANT: This function assumes GSC authentication already exists.
    
    Architecture:
    - Phase 0 (Sequential): Auth check + Property sync
    - Phase 1 (Sequential): Property/Page/Device ingestion (GSC API calls)
    - Phase 2 (Parallel): Page/Device analysis (DB-only operations)
    
    Returns:
        None
    
    Raises:
        RuntimeError: If GSC authentication does not exist
        Exception: Any error during pipeline execution
    """
    log_step("GSC QUICK VIEW - SEQUENTIAL INGESTION + PARALLEL ANALYSIS", "INFO")
    print("="*80 + "\n")
    
    db = None
    
    try:
        # Initialize pipeline state
        update_pipeline_state(
            is_running=True,
            phase="idle",
            current_step=None,
            progress={"current": 0, "total": 0},
            completed_steps=[],
            error=None,
            started_at=datetime.now().isoformat()
        )
        
        # ========================================================================
        # PHASE 0: SEQUENTIAL SETUP
        # ========================================================================
        
        update_pipeline_state(phase="setup", current_step="Checking GSC authentication")
        log_step("PHASE 0: SETUP", "INFO")
        log_step("Checking Google Search Console authentication...", "PROGRESS")
        
        client = GSCClient()
        
        # Verify authentication exists
        if not client.is_authenticated():
            raise RuntimeError(
                "GSC not authenticated. Please run authentication first.\n"
                "From CLI: Authentication will be handled automatically.\n"
                "From API: Call POST /auth/login before running the pipeline."
            )
        
        # Load existing credentials and build service
        client.authenticate()
        log_step("GSC authentication successful", "SUCCESS")
        update_pipeline_state(completed_steps=["auth_check"])
        
        # Property sync
        update_pipeline_state(current_step="Fetching GSC properties")
        log_step("Fetching GSC properties...", "PROGRESS")
        all_properties = client.fetch_properties()
        
        log_step("Filtering properties (Owner/Full User only)...", "PROGRESS")
        filtered_properties = client.filter_properties(all_properties)
        
        log_step("Grouping properties by base domain...", "PROGRESS")
        grouper = PropertyGrouper()
        grouped_properties = grouper.group_properties(filtered_properties)
        log_step(f"Grouped into {len(grouped_properties)} websites", "SUCCESS")
        
        log_step("Connecting to database...", "PROGRESS")
        db = DatabasePersistence()
        db.connect()
        log_step("Database connected", "SUCCESS")
        
        log_step("Persisting websites and properties...", "PROGRESS")
        counts = db.persist_grouped_properties(grouped_properties)
        log_step(f"Persisted {counts['websites']} websites, {counts['properties']} properties", "SUCCESS")
        
        log_step("Fetching properties from database...", "PROGRESS")
        db_properties = db.fetch_all_properties()
        log_step(f"Retrieved {len(db_properties)} properties", "SUCCESS")
        update_pipeline_state(completed_steps=PIPELINE_STATE["completed_steps"] + ["properties_sync"])
        
        # ========================================================================
        # PHASE 1: SEQUENTIAL INGESTION (GSC API - NOT THREAD-SAFE)
        # ========================================================================
        
        print("\n" + "="*80)
        log_step("PHASE 1: SEQUENTIAL INGESTION (GSC API calls)", "INFO")
        log_step("⚠️  GSC API client is NOT thread-safe - running sequentially", "WARNING")
        print("="*80 + "\n")
        
        update_pipeline_state(
            phase="ingestion",
            current_step="Ingesting metrics from GSC API",
            progress={"current": 0, "total": len(db_properties) * 3}
        )
        
        # Create ingestors (shared GSC client)
        property_ingestor = PropertyMetricsDailyIngestor(client.service, db)
        page_ingestor = PageMetricsDailyIngestor(client.service, db)
        device_ingestor = DeviceMetricsDailyIngestor(client.service, db)
        
        total_properties = len(db_properties)
        current_progress = 0
        
        # Sequential ingestion for each property
        for idx, prop in enumerate(db_properties, 1):
            site_url = prop['site_url']
            
            # Property metrics
            log_step(f"[{idx}/{total_properties}] Property metrics: {site_url}", "PROGRESS")
            update_pipeline_state(
                current_step=f"Property metrics [{idx}/{total_properties}]: {site_url}",
                progress={"current": current_progress, "total": total_properties * 3}
            )
            property_ingestor.ingest_property_single_day(prop)
            current_progress += 1
            
            # Page metrics
            log_step(f"[{idx}/{total_properties}] Page metrics: {site_url}", "PROGRESS")
            update_pipeline_state(
                current_step=f"Page metrics [{idx}/{total_properties}]: {site_url}",
                progress={"current": current_progress, "total": total_properties * 3}
            )
            page_ingestor.ingest_property_single_day(prop)
            current_progress += 1
            
            # Device metrics
            log_step(f"[{idx}/{total_properties}] Device metrics: {site_url}", "PROGRESS")
            update_pipeline_state(
                current_step=f"Device metrics [{idx}/{total_properties}]: {site_url}",
                progress={"current": current_progress, "total": total_properties * 3}
            )
            device_ingestor.ingest_property_single_day(prop)
            current_progress += 1
        
        log_step("All ingestion complete", "SUCCESS")
        update_pipeline_state(
            completed_steps=PIPELINE_STATE["completed_steps"] + ["ingestion"],
            progress={"current": total_properties * 3, "total": total_properties * 3}
        )
        
        # ========================================================================
        # PHASE 2: PARALLEL ANALYSIS (DB-ONLY - THREAD-SAFE)
        # ========================================================================
        
        print("\n" + "="*80)
        log_step("PHASE 2: PARALLEL ANALYSIS (DB-only operations)", "INFO")
        log_step("✅ Database operations are thread-safe - running in parallel", "SUCCESS")
        print("="*80 + "\n")
        
        update_pipeline_state(
            phase="analysis",
            current_step="Running parallel visibility analysis"
        )
        
        def analyze_page_visibility():
            """Task: Analyze page visibility and persist to DB"""
            db_local = DatabasePersistence()
            db_local.connect()
            try:
                log_step("Starting page visibility analysis...", "PROGRESS")
                analyzer = PageVisibilityAnalyzer(db_local)
                analyzer.analyze_all_properties(db_properties)
                log_step("Page visibility analysis complete", "SUCCESS")
            finally:
                db_local.disconnect()
        
        def analyze_device_visibility():
            """Task: Analyze device visibility and persist to DB"""
            db_local = DatabasePersistence()
            db_local.connect()
            try:
                log_step("Starting device visibility analysis...", "PROGRESS")
                analyzer = DeviceVisibilityAnalyzer(db_local)
                analyzer.analyze_all_properties(db_properties)
                log_step("Device visibility analysis complete", "SUCCESS")
            finally:
                db_local.disconnect()
        
        # Execute Phase 2 tasks in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(analyze_page_visibility): "page_visibility",
                executor.submit(analyze_device_visibility): "device_visibility"
            }
            
            # Wait for all tasks and fail-fast on error
            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    future.result()  # Raises if task failed
                    update_pipeline_state(
                        completed_steps=PIPELINE_STATE["completed_steps"] + [task_name]
                    )
                except Exception as e:
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    raise RuntimeError(f"Phase 2 failed during {task_name}: {e}") from e
        
        log_step("All analysis complete", "SUCCESS")
        update_pipeline_state(current_step="Pipeline completed", phase="completed")
        
        print("\n" + "="*80)
        log_step("PIPELINE COMPLETED SUCCESSFULLY", "SUCCESS")
        print("="*80 + "\n")
    
    except Exception as e:
        log_step(f"PIPELINE FAILED: {e}", "ERROR")
        update_pipeline_state(error=str(e), phase="failed")
        raise
    
    finally:
        # Always close database connection
        if db:
            db.disconnect()
        
        # Reset running state
        update_pipeline_state(is_running=False)


def main():
    """
    CLI entrypoint for the pipeline.
    
    This function is called when running: python main.py
    
    Behavior:
    1. Checks if GSC authentication exists
    2. If not authenticated, runs OAuth flow
    3. Then executes the full pipeline
    """
    # Check authentication status
    client = GSCClient()
    
    if not client.is_authenticated():
        print("\n" + "="*80)
        print("AUTHENTICATION REQUIRED")
        print("="*80)
        print("Google Search Console is not authenticated.")
        print("Starting OAuth flow...\n")
        
        # Run OAuth flow (will open browser)
        client.authenticate()
        
        print("\n✅ Authentication successful!")
        print("="*80 + "\n")
    
    # Run the pipeline (assumes authentication exists)
    run_pipeline()


if __name__ == '__main__':
    main()
