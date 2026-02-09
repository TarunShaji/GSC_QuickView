"""
Page Metrics Daily Ingestor

Lightweight daily ingestion of page-level metrics (single day only).
This runs automatically as part of the main pipeline.

API Cost: ~26 API calls per day (one per property)
Data: Single day (today-2)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from db_persistence import DatabasePersistence


class PageMetricsDailyIngestor:
    """Handles daily incremental ingestion of page-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def ingest_property_single_day(self, property_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Fetch yesterday's page metrics (today - 2) for a single property
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
        
        Returns:
            Dict with 'rows_fetched', 'rows_processed'
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        
        # Single day: today - 2 (GSC data stabilizes ~2 days later)
        target_date = datetime.now().date() - timedelta(days=2)
        
        # Build Search Analytics API request
        request_body = {
            'startDate': target_date.strftime('%Y-%m-%d'),
            'endDate': target_date.strftime('%Y-%m-%d'),
            'dimensions': ['page', 'date'],
            'rowLimit': 25000  # GSC max
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
                    'rows_processed': 0
                }

            
            # Transform API response to database format
            page_metrics = []
            for row in rows:
                keys = row.get('keys', [])
                if len(keys) != 2:
                    continue  # Skip malformed rows
                
                page_url = keys[0]
                date_str = keys[1]
                
                page_metrics.append({
                    'page_url': page_url,
                    'date': date_str,
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0.0),
                    'position': row.get('position', 0.0)
                })
            
            # Persist to database (no progress logging for daily - small dataset)
            counts = self.db.persist_page_metrics(property_id, page_metrics, show_progress=False)
            
            return {
                'rows_fetched': len(rows),
                'rows_processed': counts['rows_processed']
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
        print("DAILY PAGE METRICS INGESTION")
        print("="*80)
        print(f"Properties to process: {len(properties)}")
        print(f"Target date: {target_date}")
        print("="*80 + "\n")
        
        total_fetched = 0
        total_processed = 0
        properties_processed = 0
        
        # Begin transaction
        self.db.begin_transaction()
        
        try:
            for prop in properties:
                base_domain = prop['base_domain']
                
                result = self.ingest_property_single_day(prop)
                
                if result['rows_fetched'] > 0:
                    print(f"[PROPERTY] {base_domain}")
                    print(f"  ✓ {result['rows_fetched']:,} page rows fetched")
                    print(f"  ✓ {result['rows_processed']:,} rows processed")
                
                total_fetched += result['rows_fetched']
                total_processed += result['rows_processed']
                properties_processed += 1
            
            # Commit transaction
            self.db.commit_transaction()
            
            # Print summary
            print("\n" + "="*80)
            print("DAILY INGESTION SUMMARY")
            print("="*80)
            print(f"✓ Properties processed: {properties_processed}")
            print(f"✓ Total rows fetched: {total_fetched:,}")
            print(f"✓ Total rows processed: {total_processed:,}")
            print("="*80 + "\n")
            
            return {
                'properties_processed': properties_processed,
                'rows_fetched': total_fetched,
                'rows_processed': total_processed
            }
        
        except Exception as e:
            print(f"\n[ERROR] Daily ingestion failed: {e}")
            print("Rolling back transaction...")
            self.db.rollback_transaction()
            raise
