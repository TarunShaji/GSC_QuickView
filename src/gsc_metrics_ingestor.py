"""
Google Search Console Metrics Ingestor
Fetches daily Search Analytics metrics and persists to database
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError


class GSCMetricsIngestor:
    """Handles fetching and persisting Search Analytics metrics"""
    
    def __init__(self, gsc_service, db_persistence):
        """
        Initialize metrics ingestor
        
        Args:
            gsc_service: Authenticated Google Search Console API service
            db_persistence: DatabasePersistence instance
        """
        self.service = gsc_service
        self.db = db_persistence
    
    def calculate_date_range(self) -> tuple[str, str]:
        """
        Calculate safe date range for metrics fetching
        
        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        
        Logic:
            - startDate = today - 32 days
            - endDate = today - 2 days
            - Guarantees ≥14 complete days (avoids incomplete data)
        """
        today = datetime.now().date()
        start_date = today - timedelta(days=32)
        end_date = today - timedelta(days=2)
        
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    
    def fetch_property_metrics(
        self, 
        site_url: str, 
        start_date: str, 
        end_date: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch Search Analytics metrics for a single property
        
        Args:
            site_url: GSC property URL (exact identifier)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of metric rows, or None if API call fails
        
        API Request Shape:
        {
          "startDate": "YYYY-MM-DD",
          "endDate": "YYYY-MM-DD",
          "dimensions": ["date"],
          "rowLimit": 25000
        }
        
        Response Shape:
        {
          "rows": [
            {
              "keys": ["YYYY-MM-DD"],
              "clicks": number,
              "impressions": number,
              "ctr": number,
              "position": number
            }
          ]
        }
        """
        try:
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['date'],
                'rowLimit': 25000
            }
            
            response = self.service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()
            
            rows = response.get('rows', [])
            return rows
        
        except HttpError as e:
            print(f"[ERROR] API call failed for {site_url}: {e}")
            return None
        
        except Exception as e:
            print(f"[ERROR] Unexpected error fetching metrics for {site_url}: {e}")
            return None
    
    def persist_metrics(
        self, 
        property_id: str, 
        metrics_rows: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Persist metrics rows to database
        
        Args:
            property_id: UUID of the property
            metrics_rows: List of metric rows from GSC API
        
        Returns:
            Dictionary with counts: {'inserted': int, 'skipped': int}
        """
        inserted_count = 0
        skipped_count = 0
        
        for row in metrics_rows:
            # Extract data from API response
            date_str = row['keys'][0]  # YYYY-MM-DD
            clicks = row.get('clicks', 0)
            impressions = row.get('impressions', 0)
            ctr = row.get('ctr', 0.0)
            position = row.get('position', 0.0)
            
            try:
                # Attempt insert with ON CONFLICT DO NOTHING
                self.db.cursor.execute("""
                    INSERT INTO property_daily_metrics 
                    (property_id, date, clicks, impressions, ctr, position, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (property_id, date) DO NOTHING
                    RETURNING id
                """, (property_id, date_str, clicks, impressions, ctr, position))
                
                result = self.db.cursor.fetchone()
                
                if result:
                    # New insert
                    inserted_count += 1
                else:
                    # Already exists
                    skipped_count += 1
            
            except Exception as e:
                print(f"[ERROR] Failed to insert metric for property {property_id}, date {date_str}: {e}")
                raise RuntimeError(f"Database error inserting metric: {e}") from e
        
        return {'inserted': inserted_count, 'skipped': skipped_count}
    
    def ingest_all_properties(self, properties: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest metrics for all properties
        
        Args:
            properties: List of property dictionaries from database
                       Each must have: id, site_url, base_domain
        
        Returns:
            Dictionary with summary counts
        """
        start_date, end_date = self.calculate_date_range()
        
        print("\n" + "="*80)
        print("PHASE 3: SEARCH ANALYTICS INGESTION")
        print("="*80)
        print(f"Date range: {start_date} → {end_date}")
        print(f"Properties to process: {len(properties)}")
        print("="*80 + "\n")
        
        total_properties_processed = 0
        total_properties_failed = 0
        total_rows_inserted = 0
        total_rows_skipped = 0
        
        try:
            # Begin transaction for metrics ingestion
            self.db.begin_transaction()
            
            for prop in properties:
                property_id = prop['id']
                site_url = prop['site_url']
                base_domain = prop.get('base_domain', site_url)  # For display
                
                print(f"[PROPERTY] {base_domain}")
                print(f"  Site URL: {site_url}")
                print(f"  Date range: {start_date} → {end_date}")
                
                # Fetch metrics from GSC API
                metrics_rows = self.fetch_property_metrics(site_url, start_date, end_date)
                
                if metrics_rows is None:
                    # API call failed
                    print(f"  ✗ API call failed (skipping property)\n")
                    total_properties_failed += 1
                    continue
                
                if len(metrics_rows) == 0:
                    # No data returned
                    print(f"  [INFO] 0 rows fetched (no data in date range)\n")
                    total_properties_processed += 1
                    continue
                
                print(f"  ✓ {len(metrics_rows)} rows fetched")
                
                # Persist to database
                try:
                    counts = self.persist_metrics(property_id, metrics_rows)
                    print(f"  ✓ {counts['inserted']} rows inserted")
                    if counts['skipped'] > 0:
                        print(f"  ↺ {counts['skipped']} rows skipped (already exist)")
                    print()
                    
                    total_rows_inserted += counts['inserted']
                    total_rows_skipped += counts['skipped']
                    total_properties_processed += 1
                
                except Exception as e:
                    print(f"  ✗ Database error: {e}")
                    raise  # Re-raise to trigger transaction rollback
            
            # Commit transaction after all metrics are inserted
            self.db.commit_transaction()
            
        except Exception as e:
            print(f"\n[ERROR] Critical error during metrics ingestion: {e}")
            print("[DB] Rolling back metrics transaction...")
            self.db.rollback_transaction()
            raise RuntimeError(f"Metrics ingestion failed: {e}") from e
        
        # Print summary
        print("="*80)
        print("INGESTION SUMMARY")
        print("="*80)
        print(f"✓ Properties processed: {total_properties_processed}")
        if total_properties_failed > 0:
            print(f"✗ Properties failed: {total_properties_failed}")
        print(f"✓ Metric rows inserted: {total_rows_inserted}")
        if total_rows_skipped > 0:
            print(f"↺ Metric rows skipped: {total_rows_skipped}")
        print("="*80 + "\n")
        
        return {
            'properties_processed': total_properties_processed,
            'properties_failed': total_properties_failed,
            'rows_inserted': total_rows_inserted,
            'rows_skipped': total_rows_skipped
        }
