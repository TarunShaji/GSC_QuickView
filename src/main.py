"""
GSC Quick View - Phase 2: Property Discovery & Database Persistence

This script:
1. Authenticates with Google Search Console API
2. Fetches all accessible properties
3. Filters to Owner/Full User only
4. Groups properties by base domain
5. Persists websites and properties to Supabase
6. Prints grouped results for validation

NO metrics collection yet, NO UI
"""

from gsc_client import GSCClient
from property_grouper import PropertyGrouper
from db_persistence import DatabasePersistence


def main():
    """
    Phase 2 entry point: GSC property discovery, grouping, and persistence
    """
    print("\n" + "="*80)
    print("GSC QUICK VIEW - PHASE 2: PROPERTY DISCOVERY & PERSISTENCE")
    print("="*80 + "\n")
    
    db = None
    
    try:
        # Step 1: Authenticate
        print("Step 1: Authenticating with Google Search Console API...")
        client = GSCClient()
        client.authenticate()
        print()
        
        # Step 2: Fetch properties
        print("Step 2: Fetching GSC properties...")
        all_properties = client.fetch_properties()
        print()
        
        # Step 3: Filter properties
        print("Step 3: Filtering properties (Owner/Full User only)...")
        filtered_properties = client.filter_properties(all_properties)
        print()
        
        # Step 4: Group properties
        print("Step 4: Grouping properties by base domain...")
        grouper = PropertyGrouper()
        grouped_properties = grouper.group_properties(filtered_properties)
        print(f"✓ Grouped into {len(grouped_properties)} websites")
        
        # Step 5: Display grouped results
        grouper.print_grouped_properties(grouped_properties)
        
        # Step 6: Persist to database
        print("Step 5: Persisting to database...")
        db = DatabasePersistence()
        db.connect()
        
        counts = db.persist_grouped_properties(grouped_properties)
        
        print("✓ Phase 2 complete - property discovery, grouping, and persistence successful\n")
    
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        print("Exiting with error.\n")
        raise
    
    finally:
        # Always close database connection
        if db:
            db.disconnect()


if __name__ == '__main__':
    main()
