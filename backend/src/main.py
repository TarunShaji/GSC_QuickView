from __future__ import annotations
"""
GSC Radar - Sequential Ingestion + Parallel Analysis
Multi-Account Aware

CONNECTION DESIGN:
  Each operation acquires a connection from the pool, uses it, and immediately
  returns it. The pipeline thread does NOT hold a connection for its full duration.
  This is required because Supabase session-mode pool size = 15 and pipelines
  can run for 30+ minutes.
"""

from contextlib import contextmanager
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


@contextmanager
def db_scope():
    """
    Context manager: borrow a pool connection, yield DatabasePersistence,
    return the connection when the with-block exits (even on exception).

    Usage:
        with db_scope() as db:
            db.some_method(...)
        # connection is now back in the pool
    """
    db = DatabasePersistence()
    db.connect()
    try:
        yield db
    finally:
        db.disconnect()


def check_bail_out(account_id: str, run_id: str) -> bool:
    """
    Check if the run is still marked as active in the DB.
    Acquires and immediately releases a connection for this single check.
    """
    with db_scope() as db:
        if not db.is_run_active(account_id, run_id):
            log_step(account_id, f"Bailing out: Run {run_id} is no longer active.", "WARNING")
            return True
    return False


def run_pipeline(account_id: str, run_id: Optional[str] = None):
    """
    Execute the full GSC analytics pipeline for a specific account.

    Connection strategy: acquire → use → release for each discrete operation.
    The pipeline thread holds ZERO connections between operations, so no
    connection is held for the full pipeline duration.

    Args:
        account_id: UUID of the account
        run_id:     Optional existing run ID (from API). If None, will create one.
    """
    log_step(account_id, "STARTING PIPELINE RUN", "INFO")

    try:
        # ====================================================================
        # SETUP & LOCKING (short-lived connection)
        # ====================================================================

        with db_scope() as db:
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

            grouped_properties = {}
            for prop in filtered_properties:
                base_domain = extract_base_domain(prop.get('siteUrl', ''))
                if base_domain not in grouped_properties:
                    grouped_properties[base_domain] = []
                grouped_properties[base_domain].append(prop)

            log_step(account_id, "Persisting websites and properties...", "PROGRESS")
            db.persist_grouped_properties(account_id, grouped_properties)

            db_properties = db.fetch_all_properties(account_id)
            log_step(account_id, f"Synced {len(db_properties)} properties", "SUCCESS")

            db.update_pipeline_state(
                account_id, run_id,
                current_step="Starting ingestion",
                progress_current=0,
                progress_total=len(db_properties)
            )
        # ← connection returned to pool here

        # ====================================================================
        # PHASE 1: SEQUENTIAL INGESTION
        # Each property is processed with its own short-lived connection scope.
        # ====================================================================

        log_step(account_id, "PHASE 1: INGESTION", "INFO")

        today = datetime.now().date()
        daily_end = today - timedelta(days=GSC_LAG_DAYS)
        daily_start = daily_end - timedelta(days=DAILY_INGEST_DAYS - 1)
        backfill_start = today - timedelta(days=INGESTION_WINDOW_DAYS)

        safe_properties = []

        for idx, prop in enumerate(db_properties, 1):
            site_url = prop['site_url']
            prop_id = prop['id']

            # Bail-out check — acquires and releases its own connection
            if check_bail_out(account_id, run_id):
                return

            with db_scope() as db:
                db.update_pipeline_state(
                    account_id, run_id,
                    current_step=f"Processing [{idx}/{len(db_properties)}]: {site_url}",
                    progress_current=idx - 1
                )
                needs_backfill = db.check_needs_backfill(account_id, prop_id)

            start_date = backfill_start if needs_backfill else daily_start
            mode_str = "BACKFILL" if needs_backfill else "DAILY"
            log_step(account_id, f"Property {idx}/{len(db_properties)}: {site_url} ({mode_str} mode)", "PROGRESS")

            try:
                # Ingestors hold db for the duration of their work then we release.
                # Each ingestor call is sequential, so only 1 connection at a time.
                with db_scope() as db:
                    property_ingestor = PropertyMetricsDailyIngestor(client.service, db)
                    page_ingestor = PageMetricsDailyIngestor(client.service, db)
                    device_ingestor = DeviceMetricsDailyIngestor(client.service, db)

                    property_ingestor.ingest_property(prop, start_date, daily_end)
                    page_ingestor.ingest_property(prop, start_date, daily_end)
                    device_ingestor.ingest_property(prop, start_date, daily_end)

                safe_properties.append(prop)
                log_step(account_id, f"Finished ingestion for {site_url}", "SUCCESS")

            except Exception as e:
                log_step(account_id, f"Ingestion FAILED for {site_url}: {e}", "ERROR")
                log_step(account_id, f"Property {site_url} will be skipped during analysis phase", "WARNING")
                continue

        log_step(account_id, f"Ingestion complete. {len(safe_properties)}/{len(db_properties)} properties safe for analysis", "SUCCESS")

        if not safe_properties:
            log_step(account_id, "No safe properties found. Ending pipeline early.", "WARNING")
            with db_scope() as db:
                db.update_pipeline_state(
                    account_id, run_id,
                    current_step="Pipeline finished (no properties ingested successfully)",
                    is_running=False,
                    completed_at=datetime.now()
                )
            return

        with db_scope() as db:
            db.update_pipeline_state(account_id, run_id, progress_current=len(db_properties))

        db_properties = safe_properties

        # ====================================================================
        # PHASE 2: SEQUENTIAL ANALYSIS
        # Previously parallelised with 2 separate connections. Now sequential
        # with a single shared connection — saves 1 connection per pipeline run
        # and avoids the risk of running out of pool slots during heavy load.
        # ====================================================================

        log_step(account_id, "PHASE 2: ANALYSIS", "INFO")

        if check_bail_out(account_id, run_id):
            return

        with db_scope() as db:
            db.update_pipeline_state(account_id, run_id, current_step="Running visibility analysis")

            analyzer_page = PageVisibilityAnalyzer(db)
            analyzer_page.analyze_all_properties(db_properties, account_id=account_id)

            analyzer_device = DeviceVisibilityAnalyzer(db)
            analyzer_device.analyze_all_properties(db_properties, account_id=account_id)
        # ← connection returned to pool here

        log_step(account_id, "Analysis complete", "SUCCESS")

        # ====================================================================
        # PHASE 3: ALERT DETECTION
        # ====================================================================

        log_step(account_id, "PHASE 3: ALERT DETECTION", "INFO")

        if check_bail_out(account_id, run_id):
            return

        with db_scope() as db:
            db.update_pipeline_state(account_id, run_id, current_step="Detecting alerts")
            triggered_count = detect_alerts_for_all_properties(db, account_id)
        # ← connection returned to pool here

        log_step(account_id, f"Alert detection complete: {triggered_count} alerts triggered", "SUCCESS")

        # ====================================================================
        # COMPLETION
        # ====================================================================

        with db_scope() as db:
            db.update_pipeline_state(
                account_id, run_id,
                current_step="Pipeline finished",
                is_running=False,
                completed_at=datetime.now()
            )
            db.mark_account_data_initialized(account_id)

        log_step(account_id, "PIPELINE COMPLETED SUCCESSFULLY", "SUCCESS")

    except Exception as e:
        log_step(account_id, f"FATAL ERROR in pipeline: {e}", "ERROR")
        try:
            with db_scope() as db:
                db.update_pipeline_state(
                    account_id, run_id,
                    error=str(e),
                    is_running=False,
                    completed_at=datetime.now()
                )
        except Exception as cleanup_err:
            log_step(account_id, f"Failed to mark pipeline as failed: {cleanup_err}", "WARNING")
        raise
    finally:
        log_step(account_id, "PIPELINE THREAD EXITING", "INFO")


from src.settings import settings

def main():
    """CLI Entrypoint for testing - runs the first account found in DB"""
    init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=5)

    try:
        with db_scope() as db:
            accounts = db.fetch_all_accounts()

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
