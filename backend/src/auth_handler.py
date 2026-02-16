import os
import json
from typing import Dict, Any, Tuple
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from src.db_persistence import DatabasePersistence

from src.settings import settings
from src.auth.token_model import GSCAuthToken


# Scopes required for GSC and Identity
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email'
]

class GoogleAuthHandler:
    """Handles OAuth 2.0 web flow for multiple accounts"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
        # 🔗 Use centralized client configuration from settings
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }

    def get_authorization_url(self) -> str:
        """
        Generate the Google OAuth authorization URL.
        
        Returns:
            The authorization URL
        """
        flow = Flow.from_client_config(
            self.client_config,
            scopes=SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        # access_type='offline' ensures we get a refresh_token
        # prompt='consent' forces full consent screen every time
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='false',
            prompt='consent'
        )
        print("REDIRECT URI BEING SENT:", settings.GOOGLE_REDIRECT_URI)
        return authorization_url

    def handle_callback(self, code: str) -> Tuple[str, str]:
        """
        Exchange authorization code for tokens and upsert account.
        
        Args:
            code: The authorization code from Google
            
        Returns:
            Tuple of (account_id, email)
        """
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=SCOPES,
                redirect_uri=settings.GOOGLE_REDIRECT_URI
            )
            
            # Exchange code for tokens
            flow.fetch_token(code=code)
            credentials = flow.credentials
            
            # Validate that required scope was granted
            REQUIRED_SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'
            if not credentials.scopes or REQUIRED_SCOPE not in credentials.scopes:
                raise RuntimeError(
                    "Search Console permission (webmasters.readonly) was not granted. "
                    "Please approve all requested permissions during login."
                )
            
            # Extract email from ID token
            token_info = id_token.verify_oauth2_token(
                credentials.id_token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            email = token_info.get('email')
            
            if not email:
                raise ValueError("Could not extract email from Google ID token")
            
            # 1. Upsert account to get account_id
            account_id = self.db.upsert_account(email)
            
            # 2. Store tokens in DB using canonical model
            token_obj = GSCAuthToken(
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=credentials.scopes,
                expiry=credentials.expiry
            )
            self.db.upsert_gsc_token(account_id, token_obj)
            
            print(f"[AUTH] Successfully handled login for: {email}")
            return account_id, email
            
        except Exception as e:
            print(f"[AUTH ERROR] Callback failed: {e}")
            raise RuntimeError(f"Authentication failed: {e}") from e
