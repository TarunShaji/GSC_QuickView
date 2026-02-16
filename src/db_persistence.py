import os
import psycopg2
import threading
from psycopg2.extras import RealDictCursor, execute_batch
from psycopg2.pool import ThreadedConnectionPool
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from datetime import datetime
import json
from auth.token_model import GSCAuthToken
from config.date_windows import GSC_LAG_DAYS, ANALYSIS_WINDOW_DAYS, INGESTION_WINDOW_DAYS

# Load environment variables
load_dotenv()

# -------------------------------------------------------------------------
# Global Connection Pool Manager
# -------------------------------------------------------------------------

_db_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = threading.Lock()

def init_db_pool(db_url: str, minconn: int = 1, maxconn: int = 10):
    """Initialize the global database connection pool once."""
    global _db_pool
    with _pool_lock:
        if _db_pool is None:
            print(f"[DB] Initializing connection pool (maxconn={maxconn})...")
            _db_pool = ThreadedConnectionPool(minconn, maxconn, db_url)
            print("[DB] ✓ Connection pool initialized")

def get_db_pool() -> ThreadedConnectionPool:
    """Get the global database connection pool."""
    if _db_pool is None:
        raise RuntimeError("Database connection pool not initialized. Call init_db_pool() first.")
    return _db_pool

def close_db_pool():
    """Close the global database connection pool."""
    global _db_pool
    if _db_pool:
        _db_pool.closeall()
        print("[DB] Connection pool closed")
        _db_pool = None


class DatabasePersistence:
    """Handles database operations for websites and properties"""

    def __init__(self):
        self.pool = get_db_pool()
        self.connection = None
        self.cursor = None
    
    def connect(self) -> None:
        """
        Borrow a database connection from the pool
        """
        try:
            # No more "Connecting to Supabase" spam per-request
            self.connection = self.pool.getconn()
            self.cursor = self.connection.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"[DB] ✗ Failed to get connection from pool: {e}")
            raise RuntimeError(f"Database connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Return database connection to the pool"""
        if self.cursor:
            try:
                self.cursor.close()
            except:
                pass
        if self.connection:
            try:
                self.pool.putconn(self.connection)
            except:
                pass
            self.connection = None
            self.cursor = None
    
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

    # ========================================
    # ACCOUNT & TOKEN MANAGEMENT
    # ========================================

    def upsert_account(self, email: str) -> str:
        """
        Create or update an account based on email.
        
        Args:
            email: Google account email
            
        Returns:
            UUID of the account
        """
        try:
            self.cursor.execute("""
                INSERT INTO accounts (google_email, created_at, updated_at)
                VALUES (%s, NOW(), NOW())
                ON CONFLICT (google_email) DO UPDATE SET
                    updated_at = NOW()
                RETURNING id
            """, (email,))
            
            result = self.cursor.fetchone()
            self.connection.commit()
            account_id = result['id']
            print(f"[DB] Account upserted: {email} (id: {account_id})")
            return account_id
        
        except Exception as e:
            self.connection.rollback()
            print(f"[DB ERROR] Failed to upsert account: {e}")
            raise

    def mark_account_data_initialized(self, account_id: str) -> None:
        """
        Mark account as having completed initial data sync.
        Called after successful pipeline run.
        
        Args:
            account_id: UUID of the account
        """
        try:
            self.cursor.execute("""
                UPDATE accounts
                SET data_initialized = TRUE, updated_at = NOW()
                WHERE id = %s
            """, (account_id,))
            self.connection.commit()
            print(f"[DB] Account {account_id} marked as data_initialized=TRUE")
        except Exception as e:
            self.connection.rollback()
            print(f"[DB ERROR] Failed to mark account as initialized: {e}")
            raise

    def is_account_data_initialized(self, account_id: str) -> bool:
        """
        Check if account has completed initial data sync.
        
        Args:
            account_id: UUID of the account
            
        Returns:
            True if data has been initialized, False otherwise
        """
        try:
            self.cursor.execute("""
                SELECT data_initialized
                FROM accounts
                WHERE id = %s
            """, (account_id,))
            result = self.cursor.fetchone()
            return result['data_initialized'] if result else False
        except Exception as e:
            print(f"[DB ERROR] Failed to check initialization status: {e}")
            return False

    def fetch_all_accounts(self) -> List[Dict[str, Any]]:
        """Fetch all accounts for the cron dispatcher."""
        try:
            self.cursor.execute("SELECT id, google_email FROM accounts ORDER BY google_email")
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch accounts: {e}")
            raise RuntimeError(f"Database error fetching accounts: {e}") from e

    def upsert_gsc_token(self, account_id: str, token: GSCAuthToken) -> None:
        """
        Store or update GSC tokens for an account using normalized columns.
        Uses the canonical GSCAuthToken model to prevent NULL access_token errors.
        
        Args:
            account_id: UUID of the account
            token: GSCAuthToken instance
        """
        if not token.access_token:
            print(f"[ERROR] Refusal to persist empty access_token for account {account_id}")
            raise RuntimeError(f"Refusing to persist empty access_token for account {account_id}")

        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")

        try:
            self.cursor.execute("""
                INSERT INTO gsc_tokens (
                    account_id, access_token, refresh_token, token_uri, 
                    client_id, client_secret, scopes, expiry, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (account_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_uri = EXCLUDED.token_uri,
                    client_id = EXCLUDED.client_id,
                    client_secret = EXCLUDED.client_secret,
                    scopes = EXCLUDED.scopes,
                    expiry = EXCLUDED.expiry,
                    updated_at = NOW()
            """, (
                account_id,
                token.access_token,
                token.refresh_token,
                token.token_uri,
                token.client_id,
                token.client_secret,
                token.scopes,
                token.expiry
            ))
            self.connection.commit()
            print(f"[DB] Token updated for account: {account_id}")
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to update token for {account_id}: {e}")
            raise RuntimeError(f"Database error updating token: {e}") from e

    def fetch_gsc_token(self, account_id: str) -> Optional[GSCAuthToken]:
        """
        Fetch GSC tokens for an account and return a canonical GSCAuthToken model.
        
        Args:
            account_id: UUID of the account
            
        Returns:
            GSCAuthToken instance, or None if not found
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")

        try:
            self.cursor.execute("""
                SELECT 
                    access_token, refresh_token, token_uri, 
                    client_id, client_secret, scopes, expiry 
                FROM gsc_tokens 
                WHERE account_id = %s
            """, (account_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
            
            return GSCAuthToken(
                access_token=row['access_token'],
                refresh_token=row['refresh_token'],
                token_uri=row['token_uri'],
                client_id=row['client_id'],
                client_secret=row['client_secret'],
                scopes=row['scopes'],
                expiry=row['expiry']
            )
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch token for {account_id}: {e}")
            raise RuntimeError(f"Database error fetching token: {e}") from e
    
    def check_needs_backfill(self, account_id: str, property_id: str) -> bool:
        """
        Check if a property has at least 14 days of data in all 3 metric tables.
        Validates precisely against the canonical ANALYSIS_WINDOW_DAYS.
        
        Args:
            account_id: UUID of the account
            property_id: UUID of the property
            
        Returns:
            True if backfill is needed, False otherwise
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")

        try:
            tables_to_check = [
                'property_daily_metrics',
                'page_daily_metrics',
                'device_daily_metrics'
            ]
            
            # Canonical check window (16 days = 14 analysis + 2 lag)
            check_interval = INGESTION_WINDOW_DAYS
            
            for table in tables_to_check:
                query = f"""
                    SELECT COUNT(DISTINCT m.date) as date_count
                    FROM {table} m
                    JOIN properties p ON m.property_id = p.id
                    WHERE m.property_id = %s
                      AND p.account_id = %s
                      AND m.date BETWEEN CURRENT_DATE - INTERVAL '%s days' 
                                   AND CURRENT_DATE - INTERVAL '%s days'
                """
                
                self.cursor.execute(query, (property_id, account_id, check_interval, GSC_LAG_DAYS))
                result = self.cursor.fetchone()
                count = result['date_count'] if result else 0
                
                if count < ANALYSIS_WINDOW_DAYS:
                    print(f"[BACKFILL CHECK] {table} incomplete: found {count}/{ANALYSIS_WINDOW_DAYS} days for property {property_id}")
                    return True
            
            print(f"[BACKFILL CHECK] Property {property_id} has sufficient data ({ANALYSIS_WINDOW_DAYS} days) in all tables.")
            return False
            
        except psycopg2.Error as e:
            print(f"[ERROR] check_needs_backfill failed for {property_id}: {e}")
            raise RuntimeError(f"Database error checking backfill needs: {e}") from e
        except Exception as e:
            print(f"[ERROR] Failed to check backfill status for {property_id}: {e}")
            return False

    def insert_website(self, account_id: str, base_domain: str) -> Optional[str]:
        """
        Insert a website into the database
        Uses ON CONFLICT DO NOTHING for idempotency
        
        Args:
            account_id: UUID of the account
            base_domain: The base domain (e.g., 'example.com')
        
        Returns:
            UUID of the website (existing or newly inserted)
        """
        try:
            # Attempt insert with ON CONFLICT DO NOTHING (account_id scoped)
            self.cursor.execute("""
                INSERT INTO websites (account_id, base_domain, display_name, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (account_id, base_domain) DO NOTHING
                RETURNING id
            """, (account_id, base_domain, base_domain))
            
            result = self.cursor.fetchone()
            
            if result:
                # New insert
                website_id = result['id']
                print(f"[INSERT] Website: {base_domain} (id: {website_id})")
                return website_id
            else:
                # Already exists, fetch existing ID for THIS account
                self.cursor.execute("""
                    SELECT id FROM websites 
                    WHERE account_id = %s AND base_domain = %s
                """, (account_id, base_domain))
                result = self.cursor.fetchone()
                
                if result:
                    website_id = result['id']
                    # print(f"[SKIP]   Website already exists: {base_domain} (id: {website_id})")
                    return website_id
                else:
                    raise RuntimeError(f"Failed to retrieve website ID for {base_domain}")
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to insert website '{base_domain}': {e}")
            raise RuntimeError(f"Database error inserting website: {e}") from e
    
    def insert_property(
        self, 
        account_id: str,
        website_id: str, 
        site_url: str, 
        property_type: str, 
        permission_level: str
    ) -> Optional[str]:
        """
        Insert a property into the database
        Uses ON CONFLICT DO NOTHING for idempotency
        
        Args:
            account_id: UUID of the account
            website_id: UUID of the parent website
            site_url: Full GSC property URL
            property_type: "sc_domain" or "url_prefix"
            permission_level: GSC permission level
        
        Returns:
            UUID of the property (existing or newly inserted)
        """
        try:
            # Attempt insert with ON CONFLICT DO NOTHING (account_id scoped)
            self.cursor.execute("""
                INSERT INTO properties (account_id, website_id, site_url, property_type, permission_level, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (account_id, site_url) DO NOTHING
                RETURNING id
            """, (account_id, website_id, site_url, property_type, permission_level))
            
            result = self.cursor.fetchone()
            
            if result:
                # New insert
                property_id = result['id']
                print(f"[INSERT] Property: {site_url} (id: {property_id})")
                return property_id
            else:
                # Already exists
                self.cursor.execute("""
                    SELECT id FROM properties 
                    WHERE account_id = %s AND site_url = %s
                """, (account_id, site_url))
                result = self.cursor.fetchone()
                
                if result:
                    property_id = result['id']
                    # print(f"[SKIP]   Property already exists: {site_url}")
                    return property_id
                else:
                    raise RuntimeError(f"Failed to retrieve property ID for {site_url}")
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to insert property '{site_url}': {e}")
            raise RuntimeError(f"Database error inserting property: {e}") from e
    
    def persist_grouped_properties(self, account_id: str, grouped_properties: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """
        Persist all grouped properties to database
        
        Args:
            account_id: UUID of the account
            grouped_properties: Dictionary mapping base_domain -> list of properties
        
        Returns:
            Dictionary with counts: {'websites': int, 'properties': int}
        """
        try:
            self.begin_transaction()
            
            print("\n" + "="*80)
            print(f"PERSISTING TO DATABASE for Account: {account_id}")
            print("="*80 + "\n")
            
            # Sort by base domain for consistent output
            for base_domain in sorted(grouped_properties.keys()):
                properties = grouped_properties[base_domain]
                
                # Insert website
                website_id = self.insert_website(account_id, base_domain)
                
                if not website_id:
                    raise RuntimeError(f"Failed to get website_id for {base_domain}")
                
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
                        account_id=account_id,
                        website_id=website_id,
                        site_url=site_url,
                        property_type=property_type,
                        permission_level=permission_level
                    )
                    
                    if not property_id:
                        raise RuntimeError(f"Failed to get property_id for {site_url}")
            
            # Commit transaction
            self.commit_transaction()
            
            # Get final counts for this account
            self.cursor.execute("SELECT COUNT(*) as count FROM websites WHERE account_id = %s", (account_id,))
            total_websites = self.cursor.fetchone()['count']
            
            self.cursor.execute("SELECT COUNT(*) as count FROM properties WHERE account_id = %s", (account_id,))
            total_properties = self.cursor.fetchone()['count']
            
            return {
                'websites': total_websites,
                'properties': total_properties
            }
        
        except Exception as e:
            print(f"\n[ERROR] Critical error during persistence: {e}")
            print("[DB] Rolling back transaction...")
            self.rollback_transaction()
            raise RuntimeError(f"Persistence failed: {e}") from e
    
    def persist_property_metrics(self, property_id: str, property_metrics: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Insert or update property-level metrics (site-wide aggregate).
        Aligns with schema: ON CONFLICT (property_id, date)
        
        Args:
            property_id: UUID of the property
            property_metrics: List of dicts with: date, clicks, impressions, ctr, position
        """
        if not property_metrics:
            return {'inserted': 0, 'updated': 0}
            
        inserted_count = 0
        updated_count = 0
        
        try:
            for metric in property_metrics:
                self.cursor.execute("""
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
                    metric['date'],
                    metric.get('clicks', 0),
                    metric.get('impressions', 0),
                    metric.get('ctr', 0.0),
                    metric.get('position', 0.0)
                ))
                
                result = self.cursor.fetchone()
                if result and result['inserted']:
                    inserted_count += 1
                else:
                    updated_count += 1
                    
            return {'inserted': inserted_count, 'updated': updated_count}
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to persist property metrics: {e}")
            raise RuntimeError(f"Database error persisting property metrics: {e}") from e

    def fetch_all_properties(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all properties for an account with their base domains
        
        Args:
            account_id: UUID of the account
            
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
                WHERE p.account_id = %s
                ORDER BY w.base_domain, p.site_url
            """, (account_id,))
            
            properties = self.cursor.fetchall()
            return [dict(prop) for prop in properties]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch properties for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching properties: {e}") from e

    def fetch_property_by_id(self, account_id: str, property_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single property with base_domain for analyzer usage.
        Strictly account scoped.
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")

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
                WHERE p.id = %s AND p.account_id = %s
            """, (property_id, account_id))

            row = self.cursor.fetchone()
            return dict(row) if row else None

        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch property {property_id} for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching property: {e}") from e
    
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
    
    def fetch_page_metrics_for_analysis(self, account_id: str, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch page impressions for V1 visibility analysis.
        Only fetches: page_url, date, impressions
        
        Uses MAX(date) lookback logic to handle GSC lag correctly,
    ensuring we always get complete analysis windows.
        
        Args:
            account_id: UUID of the account
            property_id: UUID of the property
        
        Returns:
            List of dicts with: page_url, date, impressions
        """
        try:
            self.cursor.execute("""
                SELECT 
                    m.page_url,
                    m.date,
                    m.impressions,
                    m.clicks
                FROM page_daily_metrics m
                JOIN properties p ON m.property_id = p.id
                WHERE m.property_id = %s
                  AND p.account_id = %s
                  AND m.date >= (
                      SELECT MAX(m2.date) - INTERVAL '13 days'
                      FROM page_daily_metrics m2
                      JOIN properties p2 ON m2.property_id = p2.id
                      WHERE m2.property_id = %s
                        AND p2.account_id = %s
                  )
                ORDER BY m.date DESC, m.page_url
            """, (property_id, account_id, property_id, account_id))
            
            metrics = self.cursor.fetchall()
            return [dict(metric) for metric in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch page metrics for prop {property_id}: {e}")
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
    
    def fetch_device_metrics_for_analysis(self, account_id: str, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch metrics required for device visibility analysis.
        Uses canonical ANALYSIS_WINDOW_DAYS anchored to MAX(date).
        
        Args:
            account_id: UUID of the account
            property_id: UUID of the property
        
        Returns:
            List of dicts with device, date, clicks, impressions, ctr, position
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            # We need precisely ANALYSIS_WINDOW_DAYS of historical data.
            # To handle GSC lag, we anchor the window to the latest available date.
            lookback_days = ANALYSIS_WINDOW_DAYS - 1
            
            self.cursor.execute(f"""
                SELECT 
                    m.device,
                    m.date,
                    m.clicks,
                    m.impressions,
                    m.ctr,
                    m.position
                FROM device_daily_metrics m
                JOIN properties p ON m.property_id = p.id
                WHERE m.property_id = %s
                  AND p.account_id = %s
                  AND m.date >= (
                      SELECT MAX(m2.date) - INTERVAL '%s days'
                      FROM device_daily_metrics m2
                      JOIN properties p2 ON m2.property_id = p2.id
                      WHERE m2.property_id = %s
                        AND p2.account_id = %s
                  )
                ORDER BY m.date DESC, m.device
            """, (property_id, account_id, lookback_days, property_id, account_id))
            
            metrics = self.cursor.fetchall()
            return [dict(row) for row in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch device metrics: {e}")
            raise RuntimeError(f"Database error fetching device metrics: {e}") from e







    # =========================================================================
    # DATA EXPLORATION METHODS (Frontend APIs)
    # =========================================================================

    def fetch_all_websites(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all websites for an account.
        
        Args:
            account_id: UUID of the account
            
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
                WHERE w.account_id = %s
                GROUP BY w.id, w.base_domain, w.created_at
                ORDER BY w.base_domain
            """, (account_id,))
            
            websites = self.cursor.fetchall()
            return [dict(row) for row in websites]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch websites for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching websites: {e}") from e


    def fetch_properties_by_website(self, account_id: str, website_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all properties for a specific website within an account.
        
        Args:
            account_id: UUID of the account
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
                WHERE account_id = %s AND website_id = %s
                ORDER BY site_url
            """, (account_id, website_id))
            
            properties = self.cursor.fetchall()
            return [dict(row) for row in properties]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch properties for website {website_id}: {e}")
            raise RuntimeError(f"Database error fetching properties: {e}") from e


    def fetch_property_daily_metrics_for_overview(self, account_id: str, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch precisely ANALYSIS_WINDOW_DAYS of property metrics anchored to MAX(date).
        
        Args:
            account_id: UUID of the account
            property_id: UUID of the property
        
        Returns:
            List of dicts with: date, clicks, impressions, ctr, position
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            lookback_days = ANALYSIS_WINDOW_DAYS - 1
            
            self.cursor.execute(f"""
                SELECT 
                    m.date,
                    m.clicks,
                    m.impressions,
                    m.ctr,
                    m.position
                FROM property_daily_metrics m
                JOIN properties p ON m.property_id = p.id
                WHERE m.property_id = %s AND p.account_id = %s
                  AND m.date >= (
                      SELECT MAX(date) - INTERVAL '%s days'
                      FROM property_daily_metrics
                      WHERE property_id = %s
                  )
                ORDER BY m.date DESC
            """, (property_id, account_id, lookback_days, property_id))
            
            metrics = self.cursor.fetchall()
            return [dict(row) for row in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch property metrics for prop {property_id}: {e}")
            raise RuntimeError(f"Database error fetching property metrics: {e}") from e


    def fetch_all_property_metrics_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Fetch metrics for ALL properties of an account in a single batch query.
        Uses a CTE to anchor MAX(date) per property for canonical window slicing.
        
        Args:
            account_id: UUID of the account
            
        Returns:
            List of dicts with: property_id, date, clicks, impressions, ctr, position
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            # We fetch ANALYSIS_WINDOW_DAYS of history per property
            lookback_days = ANALYSIS_WINDOW_DAYS - 1
            
            # 🔐 BATCH QUERY: Anchored MAX(date) per property
            self.cursor.execute(f"""
                WITH property_dates AS (
                    SELECT property_id, MAX(date) as max_date
                    FROM property_daily_metrics m
                    JOIN properties p ON m.property_id = p.id
                    WHERE p.account_id = %s
                    GROUP BY property_id
                )
                SELECT 
                    m.property_id,
                    m.date,
                    m.clicks,
                    m.impressions,
                    m.ctr,
                    m.position
                FROM property_daily_metrics m
                JOIN property_dates pd ON m.property_id = pd.property_id
                WHERE m.date >= (pd.max_date - (%s * INTERVAL '1 day'))
                ORDER BY m.property_id, m.date DESC
            """, (account_id, lookback_days))
            
            metrics = self.cursor.fetchall()
            return [dict(row) for row in metrics]
        
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to batch fetch property metrics for account {account_id}: {e}")
            raise RuntimeError(f"Database error batch fetching metrics: {e}") from e


    def fetch_recent_alert(
        self, 
        account_id: str, 
        property_id: str, 
        alert_type: str, 
        within_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a similar alert was triggered recently for deduplication.
        Uses multiplication for safe interval parameterization.
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
            
        try:
            self.cursor.execute("""
                SELECT id, triggered_at 
                FROM alerts 
                WHERE account_id = %s 
                  AND property_id = %s 
                  AND alert_type = %s 
                  AND triggered_at >= NOW() - (%s * INTERVAL '1 hour')
                LIMIT 1
            """, (account_id, property_id, alert_type, within_hours))
            
            return self.cursor.fetchone()
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch recent alert: {e}")
            raise RuntimeError(f"Database error fetching recent alert: {e}") from e


    # =========================================================================
    # ALERT METHODS (Email Alerting)
    # =========================================================================

    def insert_alert(
        self, 
        account_id: str,
        property_id: str, 
        alert_type: str,
        prev_7_impressions: int,
        last_7_impressions: int,
        delta_pct: float
    ) -> str:
        """
        Insert a scoped alert into the alerts table.
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                INSERT INTO alerts 
                    (account_id, property_id, alert_type, prev_7_impressions, last_7_impressions, 
                     delta_pct, triggered_at, email_sent)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), false)
                RETURNING id
            """, (account_id, property_id, alert_type, prev_7_impressions, last_7_impressions, delta_pct))
            
            result = self.cursor.fetchone()
            self.connection.commit()
            return result['id']
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to insert alert: {e}")
            raise RuntimeError(f"Database error inserting alert: {e}") from e

    def fetch_alert_recipients(self, account_id: str) -> List[str]:
        """Fetch alert recipients for a specific account."""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT email
                FROM alert_recipients
                WHERE account_id = %s
                ORDER BY created_at
            """, (account_id,))
            
            recipients = self.cursor.fetchall()
            return [row['email'] for row in recipients]
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch recipients for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching alert recipients: {e}") from e

    def add_alert_recipient(self, account_id: str, email: str) -> None:
        """Add a new alert recipient for an account."""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                INSERT INTO alert_recipients (account_id, email)
                VALUES (%s, %s)
                ON CONFLICT (account_id, email) DO NOTHING
            """, (account_id, email))
            self.connection.commit()
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to add recipient {email} for account {account_id}: {e}")
            raise RuntimeError(f"Database error adding alert recipient: {e}") from e

    def remove_alert_recipient(self, account_id: str, email: str) -> None:
        """Remove an alert recipient for an account."""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                DELETE FROM alert_recipients
                WHERE account_id = %s AND email = %s
            """, (account_id, email))
            self.connection.commit()
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to remove recipient {email} for account {account_id}: {e}")
            raise RuntimeError(f"Database error removing alert recipient: {e}") from e


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


    def fetch_alert_details(self, account_id: str, alert_id: str) -> Dict[str, Any]:
        """
        Fetch alert details including property URL.
        Strictly checked for account ownership.
        
        Args:
            account_id: UUID of the account
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
                    a.id as alert_id, a.property_id, p.site_url, a.alert_type, 
                    a.prev_7_impressions, a.last_7_impressions, a.delta_pct,
                    a.triggered_at
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                WHERE a.id = %s AND a.account_id = %s
            """, (alert_id, account_id))
            
            result = self.cursor.fetchone()
            
            if not result:
                raise ValueError(f"Alert {alert_id} not found for account {account_id}")
            
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


    def fetch_pending_alerts(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all alerts where email_sent = false.
        Optional account_id scoping.
        """
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            query = """
                SELECT 
                    a.id, a.account_id, a.property_id, a.alert_type,
                    a.prev_7_impressions, a.last_7_impressions, a.delta_pct,
                    a.triggered_at, p.site_url
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                WHERE a.email_sent = false
            """
            params = []
            if account_id:
                query += " AND a.account_id = %s"
                params.append(account_id)
            
            query += " ORDER BY a.triggered_at ASC"
            
            self.cursor.execute(query, tuple(params))
            alerts = self.cursor.fetchall()
            return [dict(row) for row in alerts]
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch pending alerts: {e}")
            raise RuntimeError(f"Database error fetching pending alerts: {e}") from e


    def fetch_recent_alerts(self, account_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent alerts for a specific account."""
        if not self.connection or not self.cursor:
            raise RuntimeError("Database connection not established")
        
        try:
            self.cursor.execute("""
                SELECT 
                    a.id, a.property_id, a.alert_type,
                    a.prev_7_impressions, a.last_7_impressions, a.delta_pct,
                    a.triggered_at, a.email_sent, p.site_url
                FROM alerts a
                JOIN properties p ON a.property_id = p.id
                WHERE a.account_id = %s
                ORDER BY a.triggered_at DESC
                LIMIT %s
            """, (account_id, limit))
            
            alerts = self.cursor.fetchall()
            return [dict(row) for row in alerts]
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch recent alerts for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching recent alerts: {e}") from e


    # ========================================================================
    # PIPELINE STATE MANAGEMENT
    # ========================================================================

    # ==========================
    # PIPELINE STATE MANAGEMENT
    # ==========================

    def cleanup_stale_runs(self, account_id: str) -> None:
        """
        Detect and terminate any runs that have been 'is_running' for too long.
        This provides deterministic recovery from server crashes or interruptions.
        
        Dual-tier policy:
        1. Soft Timeout (20m): No heartbeat (updated_at) for 20 minutes.
        2. Hard Timeout (2h): Total runtime (started_at) exceeds 2 hours.
        """
        try:
            self.cursor.execute("""
                UPDATE pipeline_runs
                SET is_running = false,
                    error = CASE 
                        WHEN started_at < NOW() - INTERVAL '2 hours' THEN 'Hard timeout exceeded (2h)'
                        ELSE 'Stale run auto-terminated (no heartbeat)'
                    END,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE account_id = %s 
                  AND is_running = true 
                  AND (
                      updated_at < NOW() - INTERVAL '20 minutes' 
                      OR started_at < NOW() - INTERVAL '2 hours'
                  )
            """, (account_id,))
            if self.cursor.rowcount > 0:
                print(f"[DB] Auto-terminated {self.cursor.rowcount} stale run(s) for account {account_id}")
                self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to cleanup stale runs for {account_id}: {e}")

    def fetch_pipeline_state(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest pipeline run state for an account."""
        try:
            self.cleanup_stale_runs(account_id)
            self.cursor.execute("""
                SELECT 
                    id, is_running, current_step,
                    progress_current, progress_total,
                    error, started_at, completed_at, updated_at
                FROM pipeline_runs
                WHERE account_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (account_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return {
                    "is_running": False,
                    "current_step": None,
                    "progress_current": 0,
                    "progress_total": 0,
                    "error": None,
                    "started_at": None,
                    "completed_at": None
                }
            
            return {
                "is_running": row['is_running'],
                "current_step": row['current_step'],
                "progress_current": row['progress_current'] or 0,
                "progress_total": row['progress_total'] or 0,
                "error": row['error'],
                "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                "completed_at": row['completed_at'].isoformat() if row['completed_at'] else None
            }
        except psycopg2.Error as e:
            print(f"[ERROR] Failed to fetch pipeline state for account {account_id}: {e}")
            raise RuntimeError(f"Database error fetching pipeline state: {e}") from e

    def start_pipeline_run(self, account_id: str) -> str:
        """
        Start a new pipeline run for an account.
        Relies on the unique index 'one_running_pipeline_per_account' for safety.
        """
        self.cleanup_stale_runs(account_id)
        try:
            self.cursor.execute("""
                INSERT INTO pipeline_runs (account_id, is_running, started_at, updated_at)
                VALUES (%s, true, NOW(), NOW())
                RETURNING id
            """, (account_id,))
            
            run_id = self.cursor.fetchone()['id']
            self.connection.commit()
            return run_id
        except psycopg2.IntegrityError:
            self.connection.rollback()
            raise RuntimeError("Pipeline is already running for this account")
        except Exception as e:
            self.connection.rollback()
            raise e

    def is_run_active(self, account_id: str, run_id: str) -> bool:
        """
        Check if a specific run is still active.
        Used by threads to self-terminate if they've been marked stale externally.
        """
        try:
            self.cursor.execute("""
                SELECT is_running FROM pipeline_runs
                WHERE id = %s AND account_id = %s
            """, (run_id, account_id))
            row = self.cursor.fetchone()
            return bool(row and row['is_running'])
        except Exception as e:
            print(f"[ERROR] Failed to check if run {run_id} is active: {e}")
            return False

    def update_pipeline_state(
        self,
        account_id: str,
        run_id: str,
        is_running: Optional[bool] = None,
        current_step: Optional[str] = None,
        progress_current: Optional[int] = None,
        progress_total: Optional[int] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """
        Update an existing pipeline run state.
        Strictly enforced atomic update: only updates if is_running is true.
        """
        try:
            updates = []
            params = []
            
            if is_running is not None:
                updates.append("is_running = %s")
                params.append(is_running)
            if current_step is not None:
                updates.append("current_step = %s")
                params.append(current_step)
            if progress_current is not None:
                updates.append("progress_current = %s")
                params.append(progress_current)
            if progress_total is not None:
                updates.append("progress_total = %s")
                params.append(progress_total)
            if error is not None:
                updates.append("error = %s")
                params.append(error)
            if completed_at is not None:
                updates.append("completed_at = %s")
                params.append(completed_at)
            
            updates.append("updated_at = now()")
            
            # ATOMIC GUARD: Only update if the run is still marked as running in the DB
            query = f"""
                UPDATE pipeline_runs 
                SET {', '.join(updates)}
                WHERE id = %s 
                  AND account_id = %s 
                  AND is_running = true
            """
            params.extend([run_id, account_id])
            
            self.cursor.execute(query, tuple(params))
            
            if self.cursor.rowcount == 0:
                # This indicates either the run_id doesn't exist or it was already terminated
                print(f"[WARNING] Pipeline update failed for run {run_id}: Run is no longer active.")
                
            self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"[ERROR] Failed to update pipeline state: {e}")
            raise RuntimeError(f"Database error updating pipeline state: {e}") from e

