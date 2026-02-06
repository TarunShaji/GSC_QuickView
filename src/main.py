"""
GSC Quick View - Phase 3: Property Discovery, Persistence & Metrics Ingestion

This script:
1. Authenticates with Google Search Console API
2. Fetches all accessible properties
3. Filters to Owner/Full User only
4. Groups properties by base domain
5. Persists websites and properties to Supabase
6. Fetches Search Analytics metrics for all properties
7. Persists daily metrics to Supabase
8. Prints results for validation

NO UI, NO alerts yet
"""

from gsc_client import GSCClient
from property_grouper import PropertyGrouper
from db_persistence import DatabasePersistence
from gsc_metrics_ingestor import GSCMetricsIngestor


def main():
    """
    Phase 3 entry point: GSC property discovery, grouping, persistence, and metrics ingestion
    """
    print("\n" + "="*80)
    print("GSC QUICK VIEW - PHASE 3: DISCOVERY, PERSISTENCE & METRICS")
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
        
        # Step 6: Connect to database
        print("Step 5: Connecting to database...")
        db = DatabasePersistence()
        db.connect()
        print()
        
        # Step 7: Persist websites and properties
        print("Step 6: Persisting websites and properties...")
        counts = db.persist_grouped_properties(grouped_properties)
        
        # Step 8: Fetch all properties from database (for metrics ingestion)
        print("Step 7: Fetching properties from database...")
        db_properties = db.fetch_all_properties()
        print(f"✓ Retrieved {len(db_properties)} properties from database\n")
        
        # Step 9: Ingest Search Analytics metrics
        print("Step 8: Ingesting Search Analytics metrics...")
        ingestor = GSCMetricsIngestor(client.service, db)
        metrics_summary = ingestor.ingest_all_properties(db_properties)
        
        print("✓ Phase 3 complete - discovery, persistence, and metrics ingestion successful\n")
    
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
