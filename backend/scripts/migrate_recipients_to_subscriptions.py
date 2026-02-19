"""
Migration Script: Migrate Alert Recipients to Property-Level Subscriptions

This is a one-time migration script that must be run BEFORE deploying the
new alert dispatcher. It copies all existing account-level alert_recipients
into alert_subscriptions for every property in their account.

This preserves current alert behavior for all existing users.

Usage:
    cd /Users/tarunshaji/GSC_QuickView/backend
    python -m scripts.migrate_recipients_to_subscriptions

    Or for a dry-run (no DB writes):
    python -m scripts.migrate_recipients_to_subscriptions --dry-run
"""
from __future__ import annotations

import sys
import os
import argparse
from typing import List, Dict, Any

# Ensure backend src is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_persistence import DatabasePersistence, init_db_pool, close_db_pool
from src.settings import settings


def log(msg: str) -> None:
    print(f"[MIGRATE] {msg}")


def migrate(db: DatabasePersistence, dry_run: bool = False) -> None:
    """
    For every existing alert_recipient, subscribe them to all current
    properties for that account.
    """
    if dry_run:
        log("DRY RUN — no database writes will occur.")

    accounts = db.fetch_all_accounts()
    if not accounts:
        log("No accounts found. Nothing to migrate.")
        return

    total_inserted = 0
    total_skipped = 0

    for acc in accounts:
        account_id = acc['id']
        account_email = acc.get('google_email', account_id)

        recipients = db.fetch_alert_recipients(account_id)
        if not recipients:
            log(f"Account {account_email}: No recipients — skipping.")
            continue

        properties = db.fetch_all_properties(account_id)
        if not properties:
            log(f"Account {account_email}: No properties — skipping.")
            continue

        log(f"Account {account_email}: {len(recipients)} recipient(s) × {len(properties)} propert(ies)")

        for email in recipients:
            for prop in properties:
                property_id = prop['id']
                site_url = prop.get('site_url', property_id)

                if dry_run:
                    log(f"  [DRY RUN] Would subscribe {email} → {site_url}")
                    total_inserted += 1
                else:
                    try:
                        db.add_alert_subscription(account_id, email, property_id)
                        log(f"  ✅ Subscribed {email} → {site_url}")
                        total_inserted += 1
                    except Exception as e:
                        # ON CONFLICT DO NOTHING handles duplicates in the DB method,
                        # but catch any unexpected error here.
                        log(f"  ⚠️  Skipped {email} → {site_url}: {e}")
                        total_skipped += 1

    log("=" * 60)
    log(f"Migration complete: {total_inserted} subscription(s) created, {total_skipped} skipped.")
    if dry_run:
        log("DRY RUN complete — no changes written.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate alert recipients to property-level subscriptions.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to DB.")
    args = parser.parse_args()

    db = None
    try:
        init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=3)
        db = DatabasePersistence()
        db.connect()
        log("Database connection established.")
        migrate(db, dry_run=args.dry_run)
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        if db:
            db.disconnect()
        close_db_pool()
        log("Database connection closed.")


if __name__ == "__main__":
    main()
