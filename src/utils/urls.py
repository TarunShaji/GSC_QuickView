"""
URL Utilities for GSC Property Handling
"""
from urllib.parse import urlparse

def extract_base_domain(site_url: str) -> str:
    """
    Extract base domain from a GSC property URL
    
    Handles:
    - URL-prefix properties: https://example.com, https://www.example.com
    - Domain properties: sc-domain:example.com
    - Multi-part TLDs: example.co.uk
    
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
