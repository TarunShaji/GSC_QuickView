"""
Test script to validate property grouping logic without GSC API calls
"""

from property_grouper import PropertyGrouper


def test_grouping_logic():
    """Test the base domain extraction and grouping logic"""
    
    print("\n" + "="*80)
    print("TESTING PROPERTY GROUPING LOGIC")
    print("="*80 + "\n")
    
    # Test cases covering various scenarios
    test_properties = [
        # Example.com group (www, non-www, sc-domain)
        {'siteUrl': 'https://example.com', 'permissionLevel': 'siteOwner'},
        {'siteUrl': 'https://www.example.com', 'permissionLevel': 'siteFullUser'},
        {'siteUrl': 'sc-domain:example.com', 'permissionLevel': 'siteOwner'},
        
        # Blog subdomain group
        {'siteUrl': 'https://blog.example.com', 'permissionLevel': 'siteOwner'},
        {'siteUrl': 'https://www.blog.example.com', 'permissionLevel': 'siteFullUser'},
        {'siteUrl': 'sc-domain:blog.example.com', 'permissionLevel': 'siteOwner'},
        
        # Multi-part TLD test
        {'siteUrl': 'https://example.co.uk', 'permissionLevel': 'siteOwner'},
        {'siteUrl': 'https://www.example.co.uk', 'permissionLevel': 'siteFullUser'},
        
        # Port and path test (should be ignored)
        {'siteUrl': 'https://test.com:8080', 'permissionLevel': 'siteOwner'},
        {'siteUrl': 'https://test.com/subpath/', 'permissionLevel': 'siteOwner'},
    ]
    
    print("Test Properties:")
    for i, prop in enumerate(test_properties, 1):
        print(f"  {i}. {prop['siteUrl']} [{prop['permissionLevel']}]")
    
    print("\n" + "-"*80 + "\n")
    
    # Test base domain extraction
    print("Base Domain Extraction:")
    for prop in test_properties:
        site_url = prop['siteUrl']
        base_domain = PropertyGrouper.extract_base_domain(site_url)
        print(f"  {site_url:45} → {base_domain}")
    
    print("\n" + "-"*80 + "\n")
    
    # Test grouping
    grouper = PropertyGrouper()
    grouped = grouper.group_properties(test_properties)
    
    print("Grouped Results:")
    grouper.print_grouped_properties(grouped)
    
    # Validate expected groupings
    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80 + "\n")
    
    expected_groups = {
        'example.com': 3,
        'blog.example.com': 3,
        'example.co.uk': 2,
        'test.com': 2,
    }
    
    all_valid = True
    for base_domain, expected_count in expected_groups.items():
        actual_count = len(grouped.get(base_domain, []))
        status = "✓" if actual_count == expected_count else "✗"
        print(f"{status} {base_domain}: Expected {expected_count}, Got {actual_count}")
        if actual_count != expected_count:
            all_valid = False
    
    print("\n" + "="*80)
    if all_valid:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*80 + "\n")


if __name__ == '__main__':
    test_grouping_logic()
