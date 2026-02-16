from __future__ import annotations
"""
Page Metrics Daily Ingestor

Lightweight daily ingestion of page-level metrics (single day only).
This runs automatically as part of the main pipeline.

API Cost: ~26 API calls per day (one per property)
Data: Single day (today-2)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any
from src.db_persistence import DatabasePersistence


class PageMetricsDailyIngestor:
    """Handles daily incremental ingestion of page-level metrics"""
    
    def __init__(self, gsc_service, db: DatabasePersistence):
        self.service = gsc_service
        self.db = db
    
    def ingest_property(self, property_data: Dict[str, Any], start_date: datetime.date, end_date: datetime.date) -> Dict[str, int]:
        """
        Fetch page metrics for a date range for a single property with pagination.
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
            start_date: Start of range
            end_date: End of range
        
        Returns:
            Dict with 'rows_fetched', 'rows_processed'
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"[INGEST] Page Metrics: {base_domain} ({start_date} to {end_date})")
        
        total_fetched = 0
        total_processed = 0
        start_row = 0
        row_limit = 25000
        
        try:
            while True:
                # Build Search Analytics API request with pagination
                request_body = {
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d'),
                    'dimensions': ['page', 'date'],
                    'rowLimit': row_limit,
                    'startRow': start_row
                }
                
                # Execute API call
                response = self.service.searchanalytics().query(
                    siteUrl=site_url,
                    body=request_body
                ).execute()
                
                rows = response.get('rows', [])
                batch_size = len(rows)
                total_fetched += batch_size
                
                print(f"  -> Fetched batch: {batch_size} rows (total: {total_fetched})")
                
                if not rows:
                    break
                
                # Transform API response to database format
                page_metrics = []
                for row in rows:
                    keys = row.get('keys', [])
                    if len(keys) != 2:
                        continue
                    
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
                
                # Persist batch to database
                # Start transaction for this batch
                self.db.begin_transaction()
                counts = self.db.persist_page_metrics(property_id, page_metrics, show_progress=False)
                self.db.commit_transaction()
                
                total_processed += counts['rows_processed']
                
                # Pagination logic: if we got exactly row_limit, there might be more
                if batch_size < row_limit:
                    break
                
                start_row += row_limit
            
            print(f"  -> Page metrics finish: {total_fetched} fetched, {total_processed} processed")
            return {
                'rows_fetched': total_fetched,
                'rows_processed': total_processed
            }
        
        except Exception as e:
            self.db.rollback_transaction()
            print(f"  ✗ Page metrics error for {site_url}: {e}")
            raise
