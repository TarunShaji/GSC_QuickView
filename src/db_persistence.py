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

