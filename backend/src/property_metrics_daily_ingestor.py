"""
Property Metrics Daily Ingestor

Lightweight daily ingestion of property-level (site-wide) metrics.
This runs automatically as part of the main pipeline.

API Cost: ~26 API calls per day (one per property)
Data: Single day (today-2)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from src.db_persistence import DatabasePersistence


class PropertyMetricsDailyIngestor:
    """Handles daily incremental ingestion of property-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def ingest_property(self, property_data: Dict[str, Any], start_date: datetime.date, end_date: datetime.date) -> Dict[str, int]:
        """
        Fetch property metrics for a date range for a single property.
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
            start_date: Start of range
            end_date: End of range
        
        Returns:
            Dict with 'rows_fetched', 'rows_inserted', 'rows_updated'
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"[INGEST] Property Metrics: {base_domain} ({start_date} to {end_date})")
        
        # Build Search Analytics API request
        # dimensions=['date'] is CRITICAL for range ingestion to get daily rows
        request_body = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['date'], 
            'rowLimit': 25000
        }
        
        try:
            # Execute API call
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            print(f"  -> GSC returned {len(rows)} daily rows")
            
            if not rows:
                return {
                    'rows_fetched': 0,
                    'rows_inserted': 0,
                    'rows_updated': 0
                }
            
            total_inserted = 0
            total_updated = 0
            
            # Transform API response to database format
            property_metrics = []
            for row in rows:
                # keys[0] is the date string
                row_date = row['keys'][0]
                
                property_metrics.append({
                    'date': row_date,
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0.0),
                    'position': row.get('position', 0.0)
                })
            
            # Persist to database
            self.db.begin_transaction()
            counts = self.db.persist_property_metrics(property_id, property_metrics)
            self.db.commit_transaction()
            
            print(f"  -> Property metrics finish: {counts['inserted']} inserted, {counts['updated']} updated")
            
            return {
                'rows_fetched': len(rows),
                'rows_inserted': counts['inserted'],
                'rows_updated': counts['updated']
            }
        
        except Exception as e:
            self.db.rollback_transaction()
            print(f"  ✗ Property metrics error for {site_url}: {e}")
            raise
