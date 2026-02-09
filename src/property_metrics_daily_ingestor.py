"""
Property Metrics Daily Ingestor

Lightweight daily ingestion of property-level (site-wide) metrics.
This runs automatically as part of the main pipeline.

API Cost: ~26 API calls per day (one per property)
Data: Single day (today-2)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from db_persistence import DatabasePersistence


class PropertyMetricsDailyIngestor:
    """Handles daily incremental ingestion of property-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def ingest_property_single_day(self, property_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Fetch yesterday's property metrics (today - 2) for a single property
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
        
        Returns:
            Dict with 'rows_fetched', 'rows_inserted', 'rows_updated'
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        
        # Single day: today - 2 (GSC data stabilizes ~2 days later)
        target_date = datetime.now().date() - timedelta(days=2)
        
        # Build Search Analytics API request
        # NO dimensions = site-wide aggregate (one row per property)
        request_body = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'dimensions': [],  # Empty = site-wide aggregate
            'rowLimit': 25000
        }
        
        try:
            # Execute API call
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            
            if not rows:
                return {
                    'rows_fetched': 0,
                    'rows_inserted': 0,
                    'rows_updated': 0
                }
            
            # Site-wide aggregate returns exactly 1 row (no keys)
            row = rows[0]
            
            # Upsert to database
            # Note: property_daily_metrics table only has created_at, not updated_at
            self.db.cursor.execute("""
                INSERT INTO property_daily_metrics 
                    (property_id, date, clicks, impressions, ctr, position, created_at)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (property_id, date) 
                DO UPDATE SET
                    clicks = EXCLUDED.clicks,
                    impressions = EXCLUDED.impressions,
                    ctr = EXCLUDED.ctr,
                    position = EXCLUDED.position
                RETURNING (xmax = 0) AS inserted
            """, (
                property_id,
                target_date,
                row.get('clicks', 0),
                row.get('impressions', 0),
                row.get('ctr', 0.0),
                row.get('position', 0.0)
            ))

            
            result = self.db.cursor.fetchone()
            
            if result and result['inserted']:
                return {
                    'rows_fetched': 1,
                    'rows_inserted': 1,
                    'rows_updated': 0
                }
            else:
                return {
                    'rows_fetched': 1,
                    'rows_inserted': 0,
                    'rows_updated': 1
                }
        
        except Exception as e:
            print(f"  ✗ Error ingesting {site_url}: {e}")
            raise
    
    def ingest_all_properties(self, properties: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest single day for all properties
        
        Args:
            properties: List of property dicts from database
        
        Returns:
            Summary dict with totals
        """
        target_date = datetime.now().date() - timedelta(days=2)
        
        print("\n" + "="*80)
        print("PROPERTY DAILY METRICS INGESTION")
        print("="*80)
        print(f"Properties to process: {len(properties)}")
        print(f"Target date: {target_date}")
        print("="*80 + "\n")
        
        total_fetched = 0
        total_inserted = 0
        total_updated = 0
        properties_processed = 0
        
        # Begin transaction
        self.db.begin_transaction()
        
        try:
            for prop in properties:
                base_domain = prop['base_domain']
                
                result = self.ingest_property_single_day(prop)
                
                if result['rows_fetched'] > 0:
                    print(f"[PROPERTY] {base_domain}")
                    print(f"  Target date: {target_date}")
                    print(f"  ✓ API row fetched")
                    if result['rows_inserted'] > 0:
                        print(f"  ✓ Row inserted")
                    else:
                        print(f"  ↺ Row updated (GSC revision)")
                
                total_fetched += result['rows_fetched']
                total_inserted += result['rows_inserted']
                total_updated += result['rows_updated']
                properties_processed += 1
            
            # Commit transaction
            self.db.commit_transaction()
            
            # Print summary
            print("\n" + "="*80)
            print("PROPERTY DAILY INGESTION SUMMARY")
            print("="*80)
            print(f"✓ Properties processed: {properties_processed}")
            print(f"✓ Total rows fetched: {total_fetched:,}")
            print(f"✓ Total rows inserted: {total_inserted:,}")
            if total_updated > 0:
                print(f"↺ Total rows updated: {total_updated:,}")
            print("="*80 + "\n")
            
            return {
                'properties_processed': properties_processed,
                'rows_fetched': total_fetched,
                'rows_inserted': total_inserted,
                'rows_updated': total_updated
            }
        
        except Exception as e:
            print(f"\n[ERROR] Property daily ingestion failed: {e}")
            print("Rolling back transaction...")
            self.db.rollback_transaction()
            raise
