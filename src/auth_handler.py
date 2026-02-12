import os
import json
from typing import Dict, Any, Tuple
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
from db_persistence import DatabasePersistence

from auth.token_model import GSCAuthToken


# Scopes required for GSC and Identity
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email'
]

CLIENT_SECRET_FILE = os.path.join(
    os.path.dirname(__file__), 
    'client_secret_693853074888-05e5d3qemmtdlonmhkl0hlk8lrr07r38.apps.googleusercontent.com.json'
)

# FIXED: Redirect URI must exactly match Google Cloud Console registration
# and must be consistent across URL generation and token exchange.
REDIRECT_URI = "http://localhost:8000/auth/google/callback"

class GoogleAuthHandler:
    """Handles OAuth 2.0 web flow for multiple accounts"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
        if not os.path.exists(CLIENT_SECRET_FILE):
            raise FileNotFoundError(f"Missing client secret file: {CLIENT_SECRET_FILE}")

    def get_authorization_url(self) -> str:
        """
        Generate the Google OAuth authorization URL using the hardcoded backend redirect.
        
        Returns:
            The authorization URL
        """
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # access_type='offline' ensures we get a refresh_token
        # prompt='consent' forces full consent screen every time
        # include_granted_scopes='false' prevents scope merging issues
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='false',
            prompt='consent'
        )
        
        return authorization_url

    def handle_callback(self, code: str) -> Tuple[str, str]:
        """
        Exchange authorization code for tokens and upsert account.
        Uses the hardcoded REDIRECT_URI.
        
        Args:
            code: The authorization code from Google
            
        Returns:
            Tuple of (account_id, email)
        """
        try:
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRET_FILE,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
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
                flow.client_config['client_id']
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
