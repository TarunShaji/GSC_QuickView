"""
Google Search Console API Client
Handles authentication and property discovery
"""

import os
import json
from typing import List, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# GSC API requires the webmasters scope
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# Path to OAuth client secret
CLIENT_SECRET_FILE = 'client_secret_693853074888-05e5d3qemmtdlonmhkl0hlk8lrr07r38.apps.googleusercontent.com.json'
TOKEN_FILE = 'token.json'


class GSCClient:
    """Client for interacting with Google Search Console API"""
    
    def __init__(self):
        self.credentials = None
        self.service = None
    
    def is_authenticated(self) -> bool:
        """
        Check if GSC authentication exists and is valid.
        
        Returns True if:
        - token.json exists AND
        - credentials are valid OR refreshable
        
        Does NOT run OAuth flow.
        Does NOT open a browser.
        Does NOT modify state.
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        # Check if token file exists
        if not os.path.exists(TOKEN_FILE):
            return False
        
        try:
            # Load credentials from token file
            credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            
            # Check if credentials are valid or can be refreshed
            if credentials and credentials.valid:
                return True
            
            if credentials and credentials.expired and credentials.refresh_token:
                # Has refresh token, can be refreshed
                return True
            
            # Credentials exist but are invalid and cannot be refreshed
            return False
        
        except Exception:
            # Token file is corrupted or invalid
            return False
    
    def authenticate(self) -> None:
        """
        Authenticate with Google Search Console API.
        Uses OAuth 2.0 flow with local token storage.
        
        This is the ONLY method that triggers OAuth flow.
        Call this method explicitly to run authentication.
        """
        # Check if we have existing valid credentials
        if os.path.exists(TOKEN_FILE):
            self.credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        
        # If credentials don't exist or are invalid, run OAuth flow
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                # Refresh expired credentials
                self.credentials.refresh(Request())
            else:
                # Run OAuth flow (opens browser)
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRET_FILE, SCOPES
                )
                self.credentials = flow.run_local_server(port=8000)
            
            # Save credentials for future use
            with open(TOKEN_FILE, 'w') as token:
                token.write(self.credentials.to_json())
        
        # Build the service
        self.service = build('searchconsole', 'v1', credentials=self.credentials)
        print("✓ Successfully authenticated with Google Search Console API")

    
    def fetch_properties(self) -> List[Dict[str, Any]]:
        """
        Fetch all GSC properties accessible to the authenticated user
        
        Returns:
            List of property dictionaries with 'siteUrl' and 'permissionLevel'
        """
        if not self.service:
            raise RuntimeError("Must authenticate before fetching properties")
        
        # Call sites.list API
        sites_list = self.service.sites().list().execute()
        
        # Extract site entries
        properties = sites_list.get('siteEntry', [])
        
        print(f"✓ Fetched {len(properties)} total properties from GSC")
        
        return properties
    
    def filter_properties(self, properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter properties to include only Owner and Full User permissions
        
        Args:
            properties: List of property dictionaries
        
        Returns:
            Filtered list containing only siteOwner and siteFullUser properties
        """
        allowed_permissions = {'siteOwner', 'siteFullUser'}
        
        filtered = [
            prop for prop in properties
            if prop.get('permissionLevel') in allowed_permissions
        ]
        
        excluded_count = len(properties) - len(filtered)
        
        print(f"✓ Filtered to {len(filtered)} properties (excluded {excluded_count} restricted/unverified)")
        
        return filtered
