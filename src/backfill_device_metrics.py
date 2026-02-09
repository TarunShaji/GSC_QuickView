"""
Device Metrics Backfill (ONE-TIME ONLY)

This script performs initial historical backfill of device-level metrics from GSC.
Run this ONCE manually, then use daily ingestion for ongoing updates.

Usage:
    cd src
    python backfill_device_metrics.py

API Cost: ~26 API calls (one per property)
Data Range: Last 15 days (today-17 to today-2)
"""

import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from gsc_client import GSCClient
from db_persistence import DatabasePersistence


class DeviceMetricsBackfill:
    """Handles one-time backfill of device-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def backfill_property(self, property_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Fetch 15 days of device-level metrics for a single property
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
        
        Returns:
            Dict with 'rows_fetched', 'rows_inserted', 'rows_updated'
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"\n[PROPERTY] {base_domain}")
        print(f"  Site URL: {site_url}")
        
        # Calculate date range (15 days, ending 2 days ago)
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=15)  # 15 days total
        
        print(f"  Date range: {start_date} → {end_date}")
        
        # Build Search Analytics API request
        request_body = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['device', 'date'],
            'rowLimit': 25000  # GSC max (though we expect ~45 rows)
        }
        
        try:
            # Execute API call
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            print(f"  ✓ {len(rows):,} device-date rows fetched from API")
            
            if not rows:
                print(f"  ⚠ No data available for this property")
                return {
                    'rows_fetched': 0,
                    'rows_inserted': 0,
                    'rows_updated': 0
                }
            
            # Transform API response to database format
            device_metrics = []
            for row in rows:
                keys = row.get('keys', [])
                if len(keys) != 2:
                    continue  # Skip malformed rows
                
                # CRITICAL: GSC returns device in UPPERCASE (MOBILE, DESKTOP, TABLET)
                # Database constraint requires lowercase (mobile, desktop, tablet)
                device = keys[0].lower()  # Normalize to lowercase
                date_str = keys[1]
                
                device_metrics.append({
                    'device': device,
                    'date': date_str,
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0.0),
                    'position': row.get('position', 0.0)
                })
            
            print(f"\n  Processing {len(device_metrics)} rows:")
            # Show first few rows for visibility
            for i, metric in enumerate(device_metrics[:5]):
                print(f"    → device={metric['device']}, date={metric['date']}, impressions={metric['impressions']:,}")
            if len(device_metrics) > 5:
                print(f"    ... and {len(device_metrics) - 5} more rows")
            
            # Begin transaction for this property
            self.db.begin_transaction()
            
            try:
                # Persist to database
                print(f"\n  [DB] Persisting {len(device_metrics)} rows...")
                counts = self.db.persist_device_metrics(property_id, device_metrics)
                
                # Commit transaction for this property
                self.db.commit_transaction()
                
                print(f"  [DB] ✓ Transaction committed")
                print(f"  ✓ Inserted {counts['inserted']} / {len(device_metrics)} rows")
                if counts['updated'] > 0:
                    print(f"  ↺ Updated {counts['updated']} rows (GSC revisions)")

                
                return {
                    'rows_fetched': len(rows),
                    'rows_inserted': counts['inserted'],
                    'rows_updated': counts['updated']
                }
            
            except Exception as e:
                # Rollback this property's transaction
                self.db.rollback_transaction()
                print(f"  ✗ Database error, transaction rolled back: {e}")
                raise
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            raise
    
    def backfill_all_properties(self, properties: List[Dict[str, Any]]) -> None:
        """
        Backfill all properties and print summary
        
        Args:
            properties: List of property dicts from database
        """
        print("\n" + "="*80)
        print("DEVICE METRICS BACKFILL (ONE-TIME)")
        print("="*80)
        print(f"Properties to backfill: {len(properties)}")
        
        # Calculate date range for display
        end_date = datetime.now().date() - timedelta(days=2)
        start_date = end_date - timedelta(days=15)
        print(f"Date range: {start_date} → {end_date}")
        print("="*80)
        
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        properties_processed = 0
        properties_failed = 0
        
        # No global transaction - each property commits independently
        
        for prop in properties:
            try:
                result = self.backfill_property(prop)
                total_fetched += result['rows_fetched']
                total_inserted += result['rows_inserted']
                total_updated += result['rows_updated']
                properties_processed += 1
            except Exception as e:
                properties_failed += 1
                print(f"  [WARNING] Skipping property due to error (continuing with others)")
        
        # Print summary
        print("\n" + "="*80)
        print("BACKFILL SUMMARY")
        print("="*80)
        print(f"✓ Properties processed: {properties_processed}")
        if properties_failed > 0:
            print(f"✗ Properties failed: {properties_failed}")
        print(f"✓ Total rows fetched: {total_fetched:,}")
        print(f"✓ Total rows inserted: {total_inserted:,}")
        if total_updated > 0:
            print(f"↺ Total rows updated: {total_updated:,}")
        print("="*80 + "\n")


def main():
    """Main entry point for backfill script"""
    print("\n" + "="*80)
    print("GSC QUICK VIEW - DEVICE METRICS BACKFILL")
    print("="*80 + "\n")
    
    db = None
    
    try:
        # Step 1: Authenticate with GSC
        print("Step 1: Authenticating with Google Search Console API...")
        client = GSCClient()
        client.authenticate()
        print()
        
        # Step 2: Connect to database
        print("Step 2: Connecting to database...")
        db = DatabasePersistence()
        db.connect()
        print()
        
        # Step 3: Fetch all properties
        print("Step 3: Fetching properties from database...")
        properties = db.fetch_all_properties()
        print(f"✓ Retrieved {len(properties)} properties\n")
        
        # Step 4: Run backfill
        print("Step 4: Starting backfill...")
        backfill = DeviceMetricsBackfill(client.service, db)
        backfill.backfill_all_properties(properties)
        
        print("✓ Backfill complete\n")
    
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        print("Exiting with error.\n")
        sys.exit(1)
    
    finally:
        if db:
            db.disconnect()


if __name__ == '__main__':
    main()
