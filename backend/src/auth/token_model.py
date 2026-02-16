from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class GSCAuthToken:
    """
    Canonical token model for the entire system.
    Eliminates ambiguity between 'token' and 'access_token'.
    """
    access_token: str
    refresh_token: Optional[str]
    token_uri: str
    client_id: str
    client_secret: str
    scopes: List[str]
    expiry: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dict for google-auth Credentials compatibility if needed"""
        return {
            'token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_uri': self.token_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': self.scopes,
            'expiry': self.expiry
        }
