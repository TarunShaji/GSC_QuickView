"""
Database Persistence Layer
Handles insertion of websites and properties and metrics into Supabase
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()


class DatabasePersistence:
    """Handles database operations for websites and properties"""

    def __init__(self):
        self.db_url = os.getenv('SUPABASE_DB_URL')
        if not self.db_url:
            raise ValueError(
                "SUPABASE_DB_URL not found in environment variables. "
                "Please add it to /src/.env file."
            )
        self.connection = None
        self.cursor = None
    
    def connect(self) -> None:
        """
        Establish database connection
        Raises explicit error if connection fails
        """
        try:
            print("[DB] Connecting to Supabase...")
            self.connection = psycopg2.connect(self.db_url)
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            print("[DB] ✓ Connected successfully")
        except psycopg2.Error as e:
            print(f"[DB] ✗ Connection failed: {e}")
            raise RuntimeError(f"Database connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            print("[DB] Connection closed")
    
    def begin_transaction(self) -> None:
        """Begin a database transaction"""
        if not self.connection:
            raise RuntimeError("Must connect to database before starting transaction")
        print("[DB] Starting transaction...")
    
    def commit_transaction(self) -> None:
        """Commit the current transaction"""
        if self.connection:
            self.connection.commit()
            print("[DB] ✓ Transaction committed")

    def rollback_transaction(self) -> None:
        """Rollback the current transaction"""
        if self.connection:
            self.connection.rollback()
            print("[DB] ✗ Transaction rolled back")
    
    def insert_website(self, base_domain: str) -> Optional[str]:
        """
        Insert a website into the database
        Uses ON CONFLICT DO NOTHING for idempotency
        
        Args:
            base_domain: The base domain (e.g., 'example.com')
        
        Returns:
            UUID of the website (existing or newly inserted)
        """
        try:
            # Attempt insert with ON CONFLICT DO NOTHING
            self.cursor.execute("""
                INSERT INTO websites (base_domain, display_name, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (base_domain) DO NOTHING
                RETURNING id
            """, (base_domain, base_domain))
            
            result = self.cursor.fetchone()
            
            if result:
                # New insert
                website_id = result['id']
                print(f"[INSERT] Website: {base_domain} (id: {website_id})")
                return website_id
            else:
                # Already exists, fetch existing ID
                self.cursor.execute("""
                    SELECT id FROM websites WHERE base_domain = %s
                """, (base_domain,))
                result = self.cursor.fetchone()
                
                if result:
                    website_id = result['id']
                    print(f"[SKIP]   Website already exists: {base_domain} (id: {website_id})")
                    return website_id
                else:
                    raise RuntimeError(f"Failed to retrieve website ID for {base_domain}")
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to insert website '{base_domain}': {e}")
            raise RuntimeError(f"Database error inserting website: {e}") from e
    
    def insert_property(
        self, 
        website_id: str, 
        site_url: str, 
        property_type: str, 
        permission_level: str
    ) -> Optional[str]:
        """
        Insert a property into the database
        Uses ON CONFLICT DO NOTHING for idempotency
        
        Args:
            website_id: UUID of the parent website
            site_url: Full GSC property URL
            property_type: "sc_domain" or "url_prefix"
            permission_level: GSC permission level
        
        Returns:
            UUID of the property (existing or newly inserted)
        """
        try:
            # Attempt insert with ON CONFLICT DO NOTHING
            self.cursor.execute("""
                INSERT INTO properties (website_id, site_url, property_type, permission_level, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (site_url) DO NOTHING
                RETURNING id
            """, (website_id, site_url, property_type, permission_level))
            
            result = self.cursor.fetchone()
            
            if result:
                # New insert
                property_id = result['id']
                print(f"[INSERT] Property: {site_url} (type: {property_type}, permission: {permission_level})")
                return property_id
            else:
                # Already exists
                self.cursor.execute("""
                    SELECT id FROM properties WHERE site_url = %s
                """, (site_url,))
                result = self.cursor.fetchone()
                
                if result:
                    property_id = result['id']
                    print(f"[SKIP]   Property already exists: {site_url}")
                    return property_id
                else:
                    raise RuntimeError(f"Failed to retrieve property ID for {site_url}")
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to insert property '{site_url}': {e}")
            raise RuntimeError(f"Database error inserting property: {e}") from e
    
    def persist_grouped_properties(self, grouped_properties: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """
        Persist all grouped properties to database
        
        Args:
            grouped_properties: Dictionary mapping base_domain -> list of properties
        
        Returns:
            Dictionary with counts: {'websites': int, 'properties': int}
        """
        websites_inserted = 0
        websites_skipped = 0
        properties_inserted = 0
        properties_skipped = 0
        
        try:
            self.begin_transaction()
            
            print("\n" + "="*80)
            print("PERSISTING TO DATABASE")
            print("="*80 + "\n")
            
            # Sort by base domain for consistent output
            for base_domain in sorted(grouped_properties.keys()):
                properties = grouped_properties[base_domain]
                
                # Insert website
                print(f"\nProcessing website: {base_domain}")
                website_id = self.insert_website(base_domain)
                
                if not website_id:
                    raise RuntimeError(f"Failed to get website_id for {base_domain}")
                
                # Track if this was a new insert or skip
                # (We can infer from the log output, but for stats we'll count)
                
                # Insert properties for this website
                for prop in properties:
                    site_url = prop.get('siteUrl', '')
                    permission_level = prop.get('permissionLevel', '')
                    
                    # Determine property type
                    if site_url.startswith('sc-domain:'):
                        property_type = 'sc_domain'
                    else:
                        property_type = 'url_prefix'
                    
                    property_id = self.insert_property(
                        website_id=website_id,
                        site_url=site_url,
                        property_type=property_type,
                        permission_level=permission_level
                    )
                    
                    if not property_id:
                        raise RuntimeError(f"Failed to get property_id for {site_url}")
            
            # Commit transaction
            self.commit_transaction()
            
            # Get final counts from database
            self.cursor.execute("SELECT COUNT(*) as count FROM websites")
            total_websites = self.cursor.fetchone()['count']
            
            self.cursor.execute("SELECT COUNT(*) as count FROM properties")
            total_properties = self.cursor.fetchone()['count']
            
            print("\n" + "="*80)
            print("PERSISTENCE SUMMARY")
            print("="*80)
            print(f"✓ Total websites in database: {total_websites}")
            print(f"✓ Total properties in database: {total_properties}")
            print("="*80 + "\n")
            
            return {
                'websites': total_websites,
                'properties': total_properties
            }
        
        except Exception as e:
            print(f"\n[ERROR] Critical error during persistence: {e}")
            print("[DB] Rolling back transaction...")
            self.rollback_transaction()
            raise RuntimeError(f"Persistence failed: {e}") from e
    
    def fetch_all_properties(self) -> List[Dict[str, Any]]:
        """
        Fetch all properties from database with their base domains
        
        Returns:
            List of dictionaries with: id, site_url, base_domain, property_type, permission_level
        """
        try:
            self.cursor.execute("""
                SELECT 
                    p.id,
                    p.site_url,
                    p.property_type,
                    p.permission_level,
                    w.base_domain
                FROM properties p
                JOIN websites w ON p.website_id = w.id
                ORDER BY w.base_domain, p.site_url
            """)
            
            properties = self.cursor.fetchall()
            return [dict(prop) for prop in properties]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch properties: {e}")
            raise RuntimeError(f"Database error fetching properties: {e}") from e
    
    # ========================================
    # PHASE 5: PAGE METRICS PERSISTENCE
    # ========================================
    
    def persist_page_metrics(self, property_id: str, page_metrics: List[Dict[str, Any]], 
                            show_progress: bool = False) -> Dict[str, int]:
        """
        Insert or update page metrics for a property using batch inserts
        Uses ON CONFLICT DO UPDATE to handle GSC data revisions
        
        Args:
            property_id: UUID of the property
            page_metrics: List of dicts with keys: page_url, date, clicks, impressions, ctr, position
            show_progress: If True, log progress every 500 rows (for backfill)
        
        Returns:
            Dictionary with total rows processed
        """
        if not page_metrics:
            return {'rows_processed': 0}
        
        total_rows = len(page_metrics)
        batch_size = 500
        
        try:
            # Prepare SQL for batch insert
            insert_sql = """
                INSERT INTO page_daily_metrics 
                    (property_id, page_url, date, clicks, impressions, ctr, position, created_at, updated_at)
                VALUES 
                    (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (property_id, page_url, date) 
                DO UPDATE SET
                    clicks = EXCLUDED.clicks,
                    impressions = EXCLUDED.impressions,
                    ctr = EXCLUDED.ctr,
                    position = EXCLUDED.position,
                    updated_at = NOW()
            """
            
            # Process in batches
            for i in range(0, total_rows, batch_size):
                batch = page_metrics[i:i + batch_size]
                
                # Prepare batch data
                batch_data = [
                    (
                        property_id,
                        metric['page_url'],
                        metric['date'],
                        metric['clicks'],
                        metric['impressions'],
                        metric['ctr'],
                        metric['position']
                    )
                    for metric in batch
                ]
                
                # Execute batch insert
                execute_batch(self.cursor, insert_sql, batch_data, page_size=batch_size)
                
                # Log progress if requested
                if show_progress:
                    rows_processed = min(i + batch_size, total_rows)
                    print(f"  Inserted {rows_processed:,} / {total_rows:,} rows...")
            
            return {
                'rows_processed': total_rows
            }
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to persist page metrics: {e}")
            raise RuntimeError(f"Database error persisting page metrics: {e}") from e
            print(f"[ERROR] Failed to persist page metrics: {e}")
            raise RuntimeError(f"Database error persisting page metrics: {e}") from e
    
    def fetch_page_metrics_last_14_days(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all page metrics for the last 14 days for a property
        Used for visibility analysis
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with: page_url, date, clicks, impressions, ctr, position
        """
        try:
            self.cursor.execute("""
                SELECT 
                    page_url,
                    date,
                    clicks,
                    impressions,
                    ctr,
                    position
                FROM page_daily_metrics
                WHERE property_id = %s
                  AND date >= CURRENT_DATE - INTERVAL '14 days'
                ORDER BY date DESC, page_url
            """, (property_id,))
            
            metrics = self.cursor.fetchall()
            return [dict(metric) for metric in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch page metrics: {e}")
            raise RuntimeError(f"Database error fetching page metrics: {e}") from e
    
    def get_page_metrics_count(self, property_id: str) -> int:
        """
        Get total count of page metric rows for a property
        Used to detect if backfill is needed
        
        Args:
            property_id: UUID of the property
        
        Returns:
            Total number of page-date rows
        """
        try:
            self.cursor.execute("""
                SELECT COUNT(*) as count
                FROM page_daily_metrics
                WHERE property_id = %s
            """, (property_id,))
            
            result = self.cursor.fetchone()
            return result['count'] if result else 0
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to count page metrics: {e}")
            raise RuntimeError(f"Database error counting page metrics: {e}") from e
    
    # ========================================
    # PHASE 6: DEVICE METRICS PERSISTENCE
    # ========================================
    
    def persist_device_metrics(self, property_id: str, device_metrics: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Insert or update device metrics for a property
        Uses ON CONFLICT DO UPDATE to handle GSC data revisions
        
        Args:
            property_id: UUID of the property
            device_metrics: List of dicts with keys: device, date, clicks, impressions, ctr, position
        
        Returns:
            Dictionary with counts: {'inserted': N, 'updated': M}
        """
        if not device_metrics:
            return {'inserted': 0, 'updated': 0}
        
        inserted_count = 0
        updated_count = 0
        
        try:
            for metric in device_metrics:
                # Insert with ON CONFLICT DO UPDATE
                self.cursor.execute("""
                    INSERT INTO device_daily_metrics 
                        (property_id, device, date, clicks, impressions, ctr, position, created_at, updated_at)
                    VALUES 
                        (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (property_id, device, date) 
                    DO UPDATE SET
                        clicks = EXCLUDED.clicks,
                        impressions = EXCLUDED.impressions,
                        ctr = EXCLUDED.ctr,
                        position = EXCLUDED.position,
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS inserted
                """, (
                    property_id,
                    metric['device'],
                    metric['date'],
                    metric['clicks'],
                    metric['impressions'],
                    metric['ctr'],
                    metric['position']
                ))
                
                result = self.cursor.fetchone()
                if result and result['inserted']:
                    inserted_count += 1
                else:
                    updated_count += 1
            
            return {
                'inserted': inserted_count,
                'updated': updated_count
            }
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to persist device metrics: {e}")
            raise RuntimeError(f"Database error persisting device metrics: {e}") from e
    
    def fetch_device_metrics_last_14_days(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch last 14 days of device metrics for a property
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with device, date, clicks, impressions, ctr, position
        """
        try:
            # Fetch last 14 days (max 42 rows: 14 days * 3 devices)
            self.cursor.execute("""
                SELECT 
                    device,
                    date,
                    clicks,
                    impressions,
                    ctr,
                    position
                FROM device_daily_metrics
                WHERE property_id = %s
                ORDER BY date DESC
                LIMIT 42
            """, (property_id,))
            
            metrics = self.cursor.fetchall()
            return [dict(metric) for metric in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch device metrics: {e}")
            raise RuntimeError(f"Database error fetching device metrics: {e}") from e


    def persist_page_visibility_analysis(self, property_id: str, analysis_results: dict) -> int:
        """
        Persist page visibility analysis to page_visibility_analysis table.
        
        Strategy:
        - Delete existing records for property_id (idempotent)
        - Batch insert new records
        - Return count of inserted rows
        
        Args:
            property_id: UUID of the property
            analysis_results: Dictionary with keys: 'new_pages', 'lost_pages', 
                            'significant_drops', 'significant_gains'
                            Each value is a list of page dicts
        
        Returns:
            Total number of rows inserted
        
        Schema:
            - property_id (uuid)
            - category (text): 'new' | 'lost' | 'drop' | 'gain'
            - page_url (text)
            - impressions_last_7 (int4)
            - impressions_prev_7 (int4)
            - delta (int4)
            - delta_pct (numeric)
            - created_at (timestamptz)
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            # Delete existing records for this property (idempotent)
            self.cursor.execute("""
                DELETE FROM page_visibility_analysis
                WHERE property_id = %s
            """, (property_id,))
            
            # Prepare batch insert data
            rows_to_insert = []
            
            # Process each category
            category_mapping = {
                'new_pages': 'new',
                'lost_pages': 'lost',
                'significant_drops': 'drop',
                'significant_gains': 'gain'
            }
            
            for result_key, category in category_mapping.items():
                pages = analysis_results.get(result_key, [])
                for page in pages:
                    rows_to_insert.append((
                        property_id,
                        category,
                        page.get('page_url'),
                        page.get('impressions_last_7', 0),
                        page.get('impressions_prev_7', 0),
                        page.get('delta', 0),
                        page.get('delta_pct', 0.0)
                    ))
            
            # Batch insert
            if rows_to_insert:
                execute_batch(
                    self.cursor,
                    """
                    INSERT INTO page_visibility_analysis 
                        (property_id, category, page_url, impressions_last_7, 
                         impressions_prev_7, delta, delta_pct, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    rows_to_insert,
                    page_size=100
                )
            
            self.connection.commit()
            
            print(f"✓ Persisted {len(rows_to_insert)} page visibility records for property {property_id}")
            return len(rows_to_insert)
        
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to persist page visibility analysis: {e}")
            raise RuntimeError(f"Database error persisting page visibility: {e}") from e


    def persist_device_visibility_analysis(self, property_id: str, analysis_results: dict) -> int:
        """
        Persist device visibility to device_visibility_analysis table.
        
        Strategy:
        - Delete existing records for property_id (idempotent)
        - Batch insert new records
        - Return count of inserted rows
        
        Args:
            property_id: UUID of the property
            analysis_results: Dictionary with device keys ('mobile', 'desktop', 'tablet')
                            Each value is a dict with analysis data
        
        Returns:
            Total number of rows inserted
        
        Schema:
            - property_id (uuid)
            - device (text): 'mobile' | 'desktop' | 'tablet'
            - last_7_impressions (int4)
            - prev_7_impressions (int4)
            - delta (int4)
            - delta_pct (numeric)
            - classification (text): 'significant_drop' | 'significant_gain' | 'flat'
            - created_at (timestamptz)
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            # Delete existing records for this property (idempotent)
            self.cursor.execute("""
                DELETE FROM device_visibility_analysis
                WHERE property_id = %s
            """, (property_id,))
            
            # Prepare batch insert data
            rows_to_insert = []
            
            # Process each device
            for device in ['mobile', 'desktop', 'tablet']:
                device_data = analysis_results.get(device, {})
                if device_data:  # Only insert if device has data
                    rows_to_insert.append((
                        property_id,
                        device,
                        device_data.get('last_7_impressions', 0),
                        device_data.get('prev_7_impressions', 0),
                        device_data.get('delta', 0),
                        device_data.get('delta_pct', 0.0),
                        device_data.get('classification', 'flat')
                    ))
            
            # Batch insert
            if rows_to_insert:
                execute_batch(
                    self.cursor,
                    """
                    INSERT INTO device_visibility_analysis 
                        (property_id, device, last_7_impressions, prev_7_impressions,
                         delta, delta_pct, classification, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    rows_to_insert,
                    page_size=100
                )
            
            self.connection.commit()
            
            print(f"✓ Persisted {len(rows_to_insert)} device visibility records for property {property_id}")
            return len(rows_to_insert)
        
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to persist device visibility analysis: {e}")
            raise RuntimeError(f"Database error persisting device visibility: {e}") from e


    # =========================================================================
    # DATA EXPLORATION METHODS (Frontend APIs)
    # =========================================================================

    def fetch_all_websites(self) -> List[Dict[str, Any]]:
        """
        Fetch all websites from database.
        
        Returns:
            List of dicts with: id, base_domain, created_at, property_count
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    w.id,
                    w.base_domain,
                    w.created_at,
                    COUNT(p.id) as property_count
                FROM websites w
                LEFT JOIN properties p ON w.id = p.website_id
                GROUP BY w.id, w.base_domain, w.created_at
                ORDER BY w.base_domain
            """)
            
            websites = self.cursor.fetchall()
            return [dict(row) for row in websites]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch websites: {e}")
            raise RuntimeError(f"Database error fetching websites: {e}") from e


    def fetch_properties_by_website(self, website_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all properties for a specific website.
        
        Args:
            website_id: UUID of the website
        
        Returns:
            List of dicts with: id, site_url, property_type, permission_level, created_at
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    id,
                    site_url,
                    property_type,
                    permission_level,
                    created_at
                FROM properties
                WHERE website_id = %s
                ORDER BY site_url
            """, (website_id,))
            
            properties = self.cursor.fetchall()
            return [dict(row) for row in properties]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch properties: {e}")
            raise RuntimeError(f"Database error fetching properties: {e}") from e


    def fetch_property_daily_metrics_for_overview(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch last 14 days of property metrics for 7v7 computation.
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with: date, clicks, impressions, ctr, position
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    date,
                    clicks,
                    impressions,
                    ctr,
                    position
                FROM property_daily_metrics
                WHERE property_id = %s
                ORDER BY date DESC
                LIMIT 14
            """, (property_id,))
            
            metrics = self.cursor.fetchall()
            return [dict(row) for row in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch property metrics: {e}")
            raise RuntimeError(f"Database error fetching property metrics: {e}") from e


    def fetch_page_visibility_analysis(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch page visibility analysis for a property.
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with: category, page_url, impressions_last_7, 
                               impressions_prev_7, delta, delta_pct
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    category,
                    page_url,
                    impressions_last_7,
                    impressions_prev_7,
                    delta,
                    delta_pct,
                    created_at
                FROM page_visibility_analysis
                WHERE property_id = %s
                ORDER BY category, delta DESC
            """, (property_id,))
            
            analysis = self.cursor.fetchall()
            return [dict(row) for row in analysis]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch page visibility: {e}")
            raise RuntimeError(f"Database error fetching page visibility: {e}") from e


    def fetch_device_visibility_analysis(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch device visibility analysis for a property.
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with: device, last_7_impressions, prev_7_impressions,
                               delta, delta_pct, classification
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    device,
                    last_7_impressions,
                    prev_7_impressions,
                    delta,
                    delta_pct,
                    classification,
                    created_at
                FROM device_visibility_analysis
                WHERE property_id = %s
                ORDER BY device
            """, (property_id,))
            
            analysis = self.cursor.fetchall()
            return [dict(row) for row in analysis]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch device visibility: {e}")
            raise RuntimeError(f"Database error fetching device visibility: {e}") from e


    # =========================================================================
    # ALERT METHODS (Email Alerting)
    # =========================================================================

    def insert_alert(
        self, 
        property_id: str, 
        alert_type: str,
        prev_7_impressions: int,
        last_7_impressions: int,
        delta_pct: float
    ) -> str:
        """
        Insert an alert into the alerts table.
        
        Args:
            property_id: UUID of the property
            alert_type: Type of alert (e.g., 'impression_drop')
            prev_7_impressions: Previous 7-day impressions
            last_7_impressions: Last 7-day impressions
            delta_pct: Percentage change
        
        Returns:
            UUID of the inserted alert
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                INSERT INTO alerts 
                    (property_id, alert_type, prev_7_impressions, last_7_impressions, 
                     delta_pct, triggered_at, email_sent)
                VALUES (%s, %s, %s, %s, %s, NOW(), false)
                RETURNING id
            """, (property_id, alert_type, prev_7_impressions, last_7_impressions, delta_pct))
            
            result = self.cursor.fetchone()
            self.connection.commit()
            
            return result['id']
        
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to insert alert: {e}")
            raise RuntimeError(f"Database error inserting alert: {e}") from e


    def fetch_alert_recipients(self) -> List[str]:
        """
        Fetch all alert recipients from alert_recipients table.
        
        Returns:
            List of email addresses
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT email
                FROM alert_recipients
                ORDER BY created_at
            """)
            
            recipients = self.cursor.fetchall()
            return [row['email'] for row in recipients]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch alert recipients: {e}")
            raise RuntimeError(f"Database error fetching alert recipients: {e}") from e


    def mark_alert_email_sent(self, alert_id: str) -> None:
        """
        Mark an alert as email sent.
        
        Args:
            alert_id: UUID of the alert
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                UPDATE alerts
                SET email_sent = true
                WHERE id = %s
            """, (alert_id,))
            
            self.connection.commit()
        
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to mark alert email sent: {e}")
            raise RuntimeError(f"Database error marking alert email sent: {e}") from e


    def fetch_alert_details(self, alert_id: str) -> Dict[str, Any]:
        """
        Fetch alert details including property URL.
        
        Args:
            alert_id: UUID of the alert
        
        Returns:
            Dict with: alert_id, property_id, site_url, alert_type, 
                      prev_7_impressions, last_7_impressions, delta_pct
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    a.id as alert_id,
                    a.property_id,
                    p.site_url,
                    a.alert_type,
                    a.prev_7_impressions,
                    a.last_7_impressions,
                    a.delta_pct,
                    a.triggered_at
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                WHERE a.id = %s
            """, (alert_id,))
            
            result = self.cursor.fetchone()
            
            if not result:
                raise RuntimeError(f"Alert not found: {alert_id}")
            
            return dict(result)
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch alert details: {e}")
            raise RuntimeError(f"Database error fetching alert details: {e}") from e


    def fetch_property_url(self, property_id: str) -> str:
        """
        Fetch site_url for a property.
        
        Args:
            property_id: UUID of the property
        
        Returns:
            Site URL string
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT site_url
                FROM properties
                WHERE id = %s
            """, (property_id,))
            
            result = self.cursor.fetchone()
            
            if not result:
                raise RuntimeError(f"Property not found: {property_id}")
            
            return result['site_url']
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch property URL: {e}")
            raise RuntimeError(f"Database error fetching property URL: {e}") from e


    def fetch_pending_alerts(self) -> List[Dict[str, Any]]:
        """
        Fetch all alerts where email_sent = false.
        
        Used by alert dispatcher to send pending emails.
        
        Returns:
            List of alert dicts with: id, property_id, site_url, alert_type,
                                     prev_7_impressions, last_7_impressions, delta_pct
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    a.id,
                    a.property_id,
                    a.alert_type,
                    a.prev_7_impressions,
                    a.last_7_impressions,
                    a.delta_pct,
                    a.triggered_at,
                    p.site_url
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                WHERE a.email_sent = false
                ORDER BY a.triggered_at ASC
            """)
            
            alerts = self.cursor.fetchall()
            return [dict(row) for row in alerts]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch pending alerts: {e}")
            raise RuntimeError(f"Database error fetching pending alerts: {e}") from e


    def fetch_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch recent alerts for frontend display.
        
        Args:
            limit: Maximum number of alerts to return
        
        Returns:
            List of alert dicts with: id, property_id, site_url, alert_type,
                                     prev_7_impressions, last_7_impressions, delta_pct,
                                     triggered_at, email_sent
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    a.id,
                    a.property_id,
                    a.alert_type,
                    a.prev_7_impressions,
                    a.last_7_impressions,
                    a.delta_pct,
                    a.triggered_at,
                    a.email_sent,
                    p.site_url
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                ORDER BY a.triggered_at DESC
                LIMIT %s
            """, (limit,))
            
            alerts = self.cursor.fetchall()
            return [dict(row) for row in alerts]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch recent alerts: {e}")
            raise RuntimeError(f"Database error fetching recent alerts: {e}") from e

