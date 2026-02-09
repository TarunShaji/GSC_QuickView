"""
GSC Quick View - Phase 6: Full Pipeline with Device-Level Visibility

This script:
1. Authenticates with Google Search Console API
2. Fetches all accessible properties
3. Filters to Owner/Full User only
4. Groups properties by base domain
5. Persists websites and properties to Supabase
6. Fetches Search Analytics property-level metrics
7. Persists daily property metrics to Supabase
8. Computes 7-day vs 7-day property comparisons
9. Ingests daily page-level metrics (today-2)
10. Analyzes page visibility (new/lost/continuing pages)
11. Ingests daily device-level metrics (today-2)
12. Analyzes device visibility (desktop/mobile/tablet)
13. Outputs JSON for frontend consumption

NO UI, NO alerts yet
"""

from gsc_client import GSCClient
from property_grouper import PropertyGrouper
from db_persistence import DatabasePersistence
from property_metrics_daily_ingestor import PropertyMetricsDailyIngestor
from metrics_aggregator import MetricsAggregator
from page_metrics_daily_ingestor import PageMetricsDailyIngestor
from page_visibility_analyzer import PageVisibilityAnalyzer
from device_metrics_daily_ingestor import DeviceMetricsDailyIngestor
from device_visibility_analyzer import DeviceVisibilityAnalyzer


def main():
    """
    Phase 6 entry point: Full pipeline with device-level visibility analysis
    """
    print("\n" + "="*80)
    print("GSC QUICK VIEW - PHASE 6: FULL PIPELINE WITH DEVICE VISIBILITY")
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
        
        # Step 9: Ingest property-level daily metrics (today-2)
        print("Step 8: Ingesting property-level daily metrics...")
        property_ingestor = PropertyMetricsDailyIngestor(client.service, db)
        property_ingestor.ingest_all_properties(db_properties)
        
        # Step 10: Compute 7v7 property comparisons
        print("Step 9: Computing 7-day vs 7-day property comparisons...")
        aggregator = MetricsAggregator(db)
        comparison_results = aggregator.aggregate_all_properties(db_properties)
        
        # Step 11: Ingest daily page metrics (today-2)
        print("Step 10: Ingesting daily page metrics...")
        page_ingestor = PageMetricsDailyIngestor(client.service, db)
        page_ingestor.ingest_all_properties(db_properties)
        
        # Step 12: Analyze page visibility
        print("Step 11: Analyzing page visibility...")
        visibility_analyzer = PageVisibilityAnalyzer(db)
        visibility_results = visibility_analyzer.analyze_all_properties(db_properties)
        
        # Step 13: Ingest daily device metrics
        print("Step 12: Ingesting daily device metrics...")
        device_ingestor = DeviceMetricsDailyIngestor(client.service, db)
        device_ingestor.ingest_all_properties(db_properties)
        
        # Step 14: Analyze device visibility
        print("Step 13: Analyzing device visibility...")
        device_analyzer = DeviceVisibilityAnalyzer(db)
        device_analyzer.analyze_all_properties(db_properties)
        
        print("✓ Phase 6 complete - full pipeline with device visibility analysis successful\n")
    
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
