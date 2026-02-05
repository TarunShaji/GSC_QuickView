"""
Property Grouping Logic
Groups GSC properties by base domain
"""

from typing import List, Dict, Any
from urllib.parse import urlparse
import re


class PropertyGrouper:
    """Groups GSC properties into logical websites by base domain"""
    
    @staticmethod
    def extract_base_domain(site_url: str) -> str:
        """
        Extract base domain from a GSC property URL
        
        Handles:
        - URL-prefix properties: https://example.com, https://www.example.com
        - Domain properties: sc-domain:example.com
        - Multi-part TLDs: example.co.uk
        - Ports and paths (ignored)
        
        Args:
            site_url: GSC property URL
        
        Returns:
            Base domain (e.g., 'example.com', 'blog.example.com')
        """
        # Handle sc-domain properties
        if site_url.startswith('sc-domain:'):
            domain = site_url.replace('sc-domain:', '')
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        
        # Handle URL-prefix properties
        parsed = urlparse(site_url)
        domain = parsed.netloc or parsed.path  # netloc for URLs, path for edge cases
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    
    @staticmethod
    def group_properties(properties: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group properties by base domain
        
        Grouping rules:
        - https://example.com, https://www.example.com, sc-domain:example.com → example.com
        - https://blog.example.com, https://www.blog.example.com → blog.example.com
        - Only groups properties that actually exist (no inference)
        
        Args:
            properties: List of filtered GSC properties
        
        Returns:
            Dictionary mapping base_domain -> list of properties
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        
        for prop in properties:
            site_url = prop.get('siteUrl', '')
            base_domain = PropertyGrouper.extract_base_domain(site_url)
            
            if base_domain not in grouped:
                grouped[base_domain] = []
            
            grouped[base_domain].append(prop)
        
        return grouped
    
    @staticmethod
    def print_grouped_properties(grouped: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Print grouped properties in human-readable format
        
        Args:
            grouped: Dictionary of base_domain -> properties
        """
        print("\n" + "="*80)
        print("GROUPED PROPERTIES BY WEBSITE")
        print("="*80 + "\n")
        
        # Sort by base domain for consistent output
        for base_domain in sorted(grouped.keys()):
            properties = grouped[base_domain]
            
            print(f"Website: {base_domain}")
            print(f"  Properties ({len(properties)}):")
            
            for prop in properties:
                site_url = prop.get('siteUrl', '')
                permission = prop.get('permissionLevel', 'unknown')
                print(f"    • {site_url} [{permission}]")
            
            print()  # Blank line between websites
        
        print("="*80)
        print(f"Total websites: {len(grouped)}")
        print(f"Total properties: {sum(len(props) for props in grouped.values())}")
        print("="*80 + "\n")
