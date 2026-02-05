"""
Database Persistence Layer
Handles insertion of websites and properties into Supabase
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
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
