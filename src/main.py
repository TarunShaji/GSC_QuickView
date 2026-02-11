"""
GSC Quick View - Sequential Ingestion + Parallel Analysis
Multi-Account Aware
"""

from gsc_client import GSCClient, AuthError
from property_grouper import PropertyGrouper
from db_persistence import DatabasePersistence
from property_metrics_daily_ingestor import PropertyMetricsDailyIngestor
from page_metrics_daily_ingestor import PageMetricsDailyIngestor
from device_metrics_daily_ingestor import DeviceMetricsDailyIngestor
from page_visibility_analyzer import PageVisibilityAnalyzer
from device_visibility_analyzer import DeviceVisibilityAnalyzer
from datetime import datetime, timedelta
from config.date_windows import GSC_LAG_DAYS, BACKFILL_RANGE_DAYS, DAILY_INGEST_DAYS
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


def run_pipeline(account_id: str):
    """
    Execute the full GSC analytics pipeline for a specific account.
    
    Args:
        account_id: UUID of the account
    """
    log_step(account_id, "STARTING PIPELINE RUN", "INFO")
    
    db = DatabasePersistence()
    db.connect()
    
    run_id = None
    
    try:
        # ========================================================================
        # PHASE 0: SETUP & LOCKING
        # ========================================================================
        
        # This implements the FOR UPDATE lock to ensure one run per account
        try:
            run_id = db.start_pipeline_run(account_id)
        except RuntimeError as e:
            log_step(account_id, f"Pipeline block: {e}", "WARNING")
            return

        db.update_pipeline_state(account_id, run_id, phase="setup", current_step="Authenticating with Google")
        log_step(account_id, "PHASE 0: SETUP", "INFO")
        
        try:
            client = GSCClient(db, account_id)
            log_step(account_id, "GSC authentication verified via DB tokens", "SUCCESS")
        except AuthError as e:
            db.update_pipeline_state(account_id, run_id, phase="failed", error=str(e), is_running=False)
            log_step(account_id, f"Authentication FAILED: {e}", "ERROR")
            return

        db.update_pipeline_state(account_id, run_id, completed_steps=["auth_check"], current_step="Syncing properties")
        
        # Property sync
        log_step(account_id, "Fetching GSC properties...", "PROGRESS")
        all_properties = client.fetch_properties()
        filtered_properties = client.filter_properties(all_properties)
        
        grouper = PropertyGrouper()
        grouped_properties = grouper.group_properties(filtered_properties)
        
        log_step(account_id, "Persisting websites and properties...", "PROGRESS")
        db.persist_grouped_properties(account_id, grouped_properties)
        
        # Fetch properties for this specific account
        db_properties = db.fetch_all_properties(account_id)
        log_step(account_id, f"Synced {len(db_properties)} properties", "SUCCESS")
        db.update_pipeline_state(account_id, run_id, completed_steps=["auth_check", "properties_sync"])

        # ========================================================================
        # PHASE 1: SEQUENTIAL INGESTION
        # ========================================================================
        
        log_step(account_id, "PHASE 1: INGESTION", "INFO")
        
        # Define date windows using canonical constants
        today = datetime.now().date()
        daily_end = today - timedelta(days=GSC_LAG_DAYS)
        daily_start = daily_end - timedelta(days=DAILY_INGEST_DAYS - 1)
        
        # Backfill covers the stabilization lag + the required historical buffer
        backfill_start = today - timedelta(days=BACKFILL_RANGE_DAYS + GSC_LAG_DAYS)
        backfill_end = daily_end
        
        db.update_pipeline_state(
            account_id, run_id, 
            phase="ingestion", 
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
            end_date = backfill_end
            
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
                phase="completed", 
                current_step="Pipeline finished (no properties ingested successfully)",
                is_running=False,
                completed_at=datetime.now()
            )
            return

        db.update_pipeline_state(
            account_id, run_id, 
            completed_steps=["auth_check", "properties_sync", "ingestion"],
            progress_current=len(db_properties)
        )

        # Update db_properties to only include the "safe" ones for subsequent phases
        db_properties = safe_properties

        # ========================================================================
        # PHASE 2: PARALLEL ANALYSIS (Account Scoped)
        # ========================================================================
        
        log_step(account_id, "PHASE 2: ANALYSIS", "INFO")
        db.update_pipeline_state(account_id, run_id, phase="analysis", current_step="Running visibility analysis")
        
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
            completed_steps=["auth_check", "properties_sync", "ingestion", "analysis"]
        )

        # ========================================================================
        # PHASE 3: ALERT DETECTION
        # ========================================================================
        
        log_step(account_id, "PHASE 3: ALERT DETECTION", "INFO")
        db.update_pipeline_state(account_id, run_id, phase="alerting", current_step="Detecting alerts")
        
        try:
            import alert_detector
            triggered_count = alert_detector.detect_alerts_for_all_properties(db, account_id=account_id)
            log_step(account_id, f"Alert detection complete ({triggered_count} triggered)", "SUCCESS")
        except Exception as e:
            log_step(account_id, f"Alert detection non-critical error: {e}", "WARNING")

        # ========================================================================
        # COMPLETION
        # ========================================================================
        
        db.update_pipeline_state(
            account_id, run_id, 
            phase="completed", 
            current_step="Pipeline finished",
            is_running=False,
            completed_at=datetime.now()
        )
        log_step(account_id, "PIPELINE COMPLETED SUCCESSFULLY", "SUCCESS")
        
    except Exception as e:
        log_step(account_id, f"PIPELINE CRITICAL FAILURE: {e}", "ERROR")
        if run_id:
            db.update_pipeline_state(account_id, run_id, phase="failed", error=str(e), is_running=False)
        raise
    finally:
        db.disconnect()


def main():
    """CLI Entrypoint for testing - runs the first account found in DB"""
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


if __name__ == '__main__':
    main()
