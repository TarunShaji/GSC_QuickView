"""
Device Metrics Daily Ingestor

Lightweight daily ingestion of device-level metrics (single day only).
This runs automatically as part of the main pipeline.

API Cost: ~26 API calls per day (one per property)
Data: Single day (today-2)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from db_persistence import DatabasePersistence


class DeviceMetricsDailyIngestor:
    """Handles daily incremental ingestion of device-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def ingest_property(self, property_data: Dict[str, Any], start_date: datetime.date, end_date: datetime.date) -> Dict[str, int]:
        """
        Fetch device metrics for a date range for a single property.
        
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
        
        print(f"[INGEST] Device Metrics: {base_domain} ({start_date} to {end_date})")
        
        # Build Search Analytics API request
        request_body = {
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'dimensions': ['device', 'date'],
            'rowLimit': 25000
        }
        
        try:
            # Execute API call
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            print(f"  -> GSC returned {len(rows)} device-date rows")
            
            if not rows:
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
                    continue
                
                device = keys[0].lower() # Normalize to lowercase
                date_str = keys[1]
                
                device_metrics.append({
                    'device': device,
                    'date': date_str,
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0.0),
                    'position': row.get('position', 0.0)
                })

            # Persist to database
            self.db.begin_transaction()
            counts = self.db.persist_device_metrics(property_id, device_metrics)
            self.db.commit_transaction()
            
            print(f"  -> Device metrics finish: {counts['inserted']} inserted, {counts['updated']} updated")
            
            return {
                'rows_fetched': len(rows),
                'rows_inserted': counts['inserted'],
                'rows_updated': counts['updated']
            }
        
        except Exception as e:
            self.db.rollback_transaction()
            print(f"  ✗ Device metrics error for {site_url}: {e}")
            raise
