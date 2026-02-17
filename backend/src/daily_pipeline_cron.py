from __future__ import annotations
"""
GSC Radar - Daily Pipeline Cron Service
Orchestrates sequential ingestion for all accounts in the database.
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import run_pipeline
from src.db_persistence import DatabasePersistence, init_db_pool, close_db_pool
from src.settings import settings

def log_cron(message: str, level: str = "INFO"):
    """Structured logging for cron orchestration."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️ ",
        "PROGRESS": "⏳"
    }.get(level, "")
    print(f"[{timestamp}] [CRON-PIPELINE] {prefix} {message}")

def main():
    log_cron("Starting Daily Pipeline Cron Orchestrator...")
    
    # Initialize DB Pool
    init_db_pool(settings.DATABASE_URL)
    
    db = DatabasePersistence()
    db.connect()
    
    success_count = 0
    skipped_count = 0
    failed_count = 0
    
    try:
        log_cron("Fetching all accounts from database...")
        accounts = db.fetch_all_accounts()
        log_cron(f"Found {len(accounts)} accounts to process.")
        
        for account in accounts:
            account_id = account['id']
            email = account['google_email']
            
            log_cron(f"Processing account: {email} ({account_id})", "PROGRESS")
            
            try:
                # 1. Attempt to start a run (this handles the lock)
                run_id = db.start_pipeline_run(account_id)
                log_cron(f"Lock acquired for {email}. Starting pipeline (run_id: {run_id})...", "SUCCESS")
                
                # 2. Execute the full pipeline
                # run_pipeline internally handles its own DB connection but uses the global pool
                run_pipeline(account_id, run_id)
                
                log_cron(f"Successfully completed pipeline for {email}.", "SUCCESS")
                success_count += 1
                
            except RuntimeError as e:
                # This usually means a pipeline is already running (locking error)
                if "already running" in str(e).lower():
                    log_cron(f"SKIPPING {email}: Pipeline already active.", "WARNING")
                    skipped_count += 1
                else:
                    log_cron(f"FAILED {email} (RuntimeError): {e}", "ERROR")
                    failed_count += 1
            except Exception as e:
                log_cron(f"CRITICAL FAILURE for {email}: {e}", "ERROR")
                failed_count += 1
                
    except Exception as e:
        log_cron(f"Fatal orchestrator error: {e}", "ERROR")
        sys.exit(1)
    finally:
        db.disconnect()
        close_db_pool()
        
    # Summary Report
    log_cron("="*50)
    log_cron("DAILY CRON SUMMARY")
    log_cron(f"Total Accounts: {len(accounts)}")
    log_cron(f"✅ Success:     {success_count}")
    log_cron(f"⚠️  Skipped:     {skipped_count}")
    log_cron(f"❌ Failed:      {failed_count}")
    log_cron("="*50)
    
    # Exit Codes:
    # 0 = All Success or mixture (if no failures/skips, but usually means 'finished')
    # 1 = At least one actual failure
    # 2 = No failures, but some skipped
    
    if failed_count > 0:
        log_cron("Cron finished with ERRORS.", "ERROR")
        sys.exit(1)
    elif skipped_count > 0:
        log_cron("Cron finished with some SKIPPED accounts.", "WARNING")
        sys.exit(2)
    else:
        log_cron("Cron finished SUCCESSFULLY.", "SUCCESS")
        sys.exit(0)

if __name__ == "__main__":
    main()
