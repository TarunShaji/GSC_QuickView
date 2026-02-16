"""
GSC Quick View - Sequential Ingestion + Parallel Analysis
Multi-Account Aware
"""

from src.gsc_client import GSCClient, AuthError

from src.utils.urls import extract_base_domain
from src.db_persistence import DatabasePersistence, init_db_pool, close_db_pool
from src.property_metrics_daily_ingestor import PropertyMetricsDailyIngestor
from src.page_metrics_daily_ingestor import PageMetricsDailyIngestor
from src.device_metrics_daily_ingestor import DeviceMetricsDailyIngestor
from src.page_visibility_analyzer import PageVisibilityAnalyzer
from src.device_visibility_analyzer import DeviceVisibilityAnalyzer
from src.alert_detector import detect_alerts_for_all_properties
from datetime import datetime, timedelta
from src.config.date_windows import GSC_LAG_DAYS, INGESTION_WINDOW_DAYS, DAILY_INGEST_DAYS
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any


def log_step(account_id: str, message: str, level: str = "INFO"):
    """Log with timestamp and account context"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️ ",
        "PROGRESS": "⏳"
    }.get(level, "")
    print(f"[{timestamp}] [ACCOUNT: {account_id}] {prefix} {message}")


def check_bail_out(account_id: str, run_id: str, db: DatabasePersistence) -> bool:
    """
    Check if the run is still marked as active in the DB.
    Returns True if the thread should bail out.
    """
    if not db.is_run_active(account_id, run_id):
        log_step(account_id, f"Bailing out: Run {run_id} is no longer active (marked stale or stopped externally).", "WARNING")
        return True
    return False


def run_pipeline(account_id: str, run_id: Optional[str] = None):
    """
    Execute the full GSC analytics pipeline for a specific account.
    
    Args:
        account_id: UUID of the account
        run_id: Optional existing run ID (from API). If None, will create one.
    """
    log_step(account_id, "STARTING PIPELINE RUN", "INFO")
    
    db = DatabasePersistence()
    db.connect()
    
    try:
        # ========================================================================
        # SETUP & LOCKING
        # ========================================================================
        
        # If no run_id provided (e.g. CLI), create one
        if not run_id:
            try:
                run_id = db.start_pipeline_run(account_id)
            except RuntimeError as e:
                log_step(account_id, f"Pipeline block: {e}", "WARNING")
                return

        db.update_pipeline_state(account_id, run_id, current_step="Authenticating with Google")
        log_step(account_id, "SETUP", "INFO")
        
        try:
            client = GSCClient(db, account_id)
            log_step(account_id, "GSC authentication verified via DB tokens", "SUCCESS")
        except AuthError as e:
            db.update_pipeline_state(account_id, run_id, error=str(e), is_running=False)
            log_step(account_id, f"Authentication FAILED: {e}", "ERROR")
            return

        db.update_pipeline_state(account_id, run_id, current_step="Syncing properties")
        
        # Property sync
        log_step(account_id, "Fetching GSC properties...", "PROGRESS")
        all_properties = client.fetch_properties()
        filtered_properties = client.filter_properties(all_properties)
        
        # Group properties by base domain (inline logic replacing legacy PropertyGrouper)
        grouped_properties = {}
        for prop in filtered_properties:
            base_domain = extract_base_domain(prop.get('siteUrl', ''))
            if base_domain not in grouped_properties:
                grouped_properties[base_domain] = []
            grouped_properties[base_domain].append(prop)
        
        log_step(account_id, "Persisting websites and properties...", "PROGRESS")
        db.persist_grouped_properties(account_id, grouped_properties)
        
        # Fetch properties for this specific account
        db_properties = db.fetch_all_properties(account_id)
        log_step(account_id, f"Synced {len(db_properties)} properties", "SUCCESS")
        db.update_pipeline_state(account_id, run_id, current_step="Starting ingestion")

        # ========================================================================
        # PHASE 1: SEQUENTIAL INGESTION
        # ========================================================================
        
        log_step(account_id, "PHASE 1: INGESTION", "INFO")
        
        # Define date windows using canonical constants
        today = datetime.now().date()
        daily_end = today - timedelta(days=GSC_LAG_DAYS)
        daily_start = daily_end - timedelta(days=DAILY_INGEST_DAYS - 1)
        
        # Backfill covers the stabilization lag + the required historical buffer
        backfill_start = today - timedelta(days=INGESTION_WINDOW_DAYS)
        backfill_end = daily_end
        
        db.update_pipeline_state(
            account_id, run_id, 
            current_step="Ingesting metrics",
            progress_current=0,
            progress_total=len(db_properties)
        )
        
        property_ingestor = PropertyMetricsDailyIngestor(client.service, db)
        page_ingestor = PageMetricsDailyIngestor(client.service, db)
        device_ingestor = DeviceMetricsDailyIngestor(client.service, db)
        
        safe_properties = []
        
        for idx, prop in enumerate(db_properties, 1):
            site_url = prop['site_url']
            prop_id = prop['id']
            
            # 1. BAIL-OUT CHECK: Before processing each property
            if check_bail_out(account_id, run_id, db):
                return

            # Sub-step logging
            db.update_pipeline_state(
                account_id, run_id, 
                current_step=f"Processing [{idx}/{len(db_properties)}]: {site_url}",
                progress_current=idx-1
            )
            
            # Check if this specific property needs a bootstrap backfill
            # Redesigned check validates property, page, and device tables.
            needs_backfill = db.check_needs_backfill(account_id, prop_id)
            
            start_date = backfill_start if needs_backfill else daily_start
            end_date = daily_end
            
            mode_str = "BACKFILL" if needs_backfill else "DAILY"
            log_step(account_id, f"Property {idx}/{len(db_properties)}: {site_url} ({mode_str} mode)", "PROGRESS")
            
            try:
                # ATOMICITY RULE: All three must succeed for the property to be marked "safe"
                # Property aggregate metrics
                property_ingestor.ingest_property(prop, start_date, end_date)
                
                # Page-level metrics (with pagination)
                page_ingestor.ingest_property(prop, start_date, end_date)
                
                # Device-level metrics
                device_ingestor.ingest_property(prop, start_date, end_date)
                
                # If we reach here, this property is safe for analysis
                safe_properties.append(prop)
                log_step(account_id, f"Finished ingestion for {site_url}", "SUCCESS")
                
            except Exception as e:
                log_step(account_id, f"Ingestion FAILED for {site_url}: {e}", "ERROR")
                log_step(account_id, f"Property {site_url} will be skipped during analysis phase", "WARNING")
                continue
            
        log_step(account_id, f"Ingestion complete. {len(safe_properties)}/{len(db_properties)} properties safe for analysis", "SUCCESS")
        
        if not safe_properties:
            log_step(account_id, "No safe properties found. Ending pipeline early.", "WARNING")
            db.update_pipeline_state(
                account_id, run_id, 
                current_step="Pipeline finished (no properties ingested successfully)",
                is_running=False,
                completed_at=datetime.now()
            )
            return

        db.update_pipeline_state(
            account_id, run_id, 
            progress_current=len(db_properties)
        )

        # Update db_properties to only include the "safe" ones for subsequent phases
        db_properties = safe_properties

        # ========================================================================
        # PHASE 2: PARALLEL ANALYSIS (Compute Only)
        # ========================================================================
        
        log_step(account_id, "PHASE 2: ANALYSIS (Compute Only)", "INFO")
        
        # 2. BAIL-OUT CHECK: Before entering Parallel Analysis
        if check_bail_out(account_id, run_id, db):
            return

        db.update_pipeline_state(account_id, run_id, current_step="Running visibility analysis (Compute Only)")
        
        def analyze_page_visibility_task():
            db_local = DatabasePersistence()
            db_local.connect()
            try:
                analyzer = PageVisibilityAnalyzer(db_local)
                analyzer.analyze_all_properties(db_properties, account_id=account_id)
            finally:
                db_local.disconnect()
        
        def analyze_device_visibility_task():
            db_local = DatabasePersistence()
            db_local.connect()
            try:
                analyzer = DeviceVisibilityAnalyzer(db_local)
                analyzer.analyze_all_properties(db_properties, account_id=account_id)
            finally:
                db_local.disconnect()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(analyze_page_visibility_task),
                executor.submit(analyze_device_visibility_task)
            ]
            for future in as_completed(futures):
                future.result() # Raise if failed
        
        log_step(account_id, "Analysis complete", "SUCCESS")
        db.update_pipeline_state(
            account_id, run_id, 
            current_step="Detection alerts"
        )

        # ========================================================================
        # PHASE 3: ALERT DETECTION (Hardened Refactor)
        # ========================================================================
        
        log_step(account_id, "PHASE 3: ALERT DETECTION", "INFO")
        
        # 3. BAIL-OUT CHECK: Before Alert Detection
        if check_bail_out(account_id, run_id, db):
            return

        db.update_pipeline_state(account_id, run_id, current_step="Detecting alerts")
        
        triggered_count = detect_alerts_for_all_properties(db, account_id)
        
        log_step(account_id, f"Alert detection complete: {triggered_count} alerts triggered", "SUCCESS")

        # ========================================================================
        # COMPLETION
        # ========================================================================
        
        db.update_pipeline_state(
            account_id, run_id, 
            current_step="Pipeline finished",
            is_running=False,
            completed_at=datetime.now()
        )
        
        # Mark account as data initialized after successful completion
        db.mark_account_data_initialized(account_id)
        
        log_step(account_id, "PIPELINE COMPLETED SUCCESSFULLY", "SUCCESS")
        
    except Exception as e:
        log_step(account_id, f"FATAL ERROR in pipeline: {e}", "ERROR")
        try:
            # Atomic termination update
            db.update_pipeline_state(account_id, run_id, error=str(e), is_running=False, completed_at=datetime.now())
        except Exception as cleanup_err:
            log_step(account_id, f"Failed to mark pipeline as failed: {cleanup_err}", "WARNING")
        raise
    finally:
        db.disconnect()
        log_step(account_id, "PIPELINE THREAD EXITING", "INFO")


from src.settings import settings

def main():
    """CLI Entrypoint for testing - runs the first account found in DB"""
    # Initialize pool for CLI process using centralized settings
    init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=5)
    
    try:
        db = DatabasePersistence()
        db.connect()
        accounts = db.fetch_all_accounts()
        db.disconnect()
        
        if not accounts:
            print("❌ No accounts found in database. Please login via web first.")
            return
            
        account = accounts[0]
        print(f"🚀 Starting CLI test run for account: {account['google_email']}")
        run_pipeline(account['id'])
    finally:
        close_db_pool()


if __name__ == '__main__':
    main()
