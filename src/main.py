"""
GSC Quick View - Phase 1: Property Discovery & Grouping

This script:
1. Authenticates with Google Search Console API
2. Fetches all accessible properties
3. Filters to Owner/Full User only
4. Groups properties by base domain
5. Prints grouped results for validation

NO database writes, NO metrics collection, NO UI
"""

from gsc_client import GSCClient
from property_grouper import PropertyGrouper


def main():
    """
    Phase 1 entry point: GSC property discovery and grouping
    """
    print("\n" + "="*80)
    print("GSC QUICK VIEW - PHASE 1: PROPERTY DISCOVERY & GROUPING")
    print("="*80 + "\n")
    
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
    
    # Step 5: Display results
    grouper.print_grouped_properties(grouped_properties)
    
    print("✓ Phase 1 complete - property discovery and grouping successful\n")


if __name__ == '__main__':
    main()
