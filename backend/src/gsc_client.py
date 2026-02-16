from __future__ import annotations
"""
Google Search Console API Client
Handles authentication and property discovery for multiple accounts
"""

import datetime
from datetime import timezone
from typing import List, Dict, Any
from src.db_persistence import DatabasePersistence
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from src.settings import settings
from src.auth.token_model import GSCAuthToken


class AuthError(Exception):
    """Raised when authentication is invalid or expired and cannot be refreshed"""
    pass


class GSCClient:
    """Client for interacting with Google Search Console API for a specific account"""

    def __init__(self, db: DatabasePersistence, account_id: str):
        self.db = db
        self.account_id = account_id
        self.credentials = self._load_credentials()
        self.service = self._init_service()

    def _load_credentials(self) -> Credentials:
        """
        Load credentials from the database for this account.
        Normalizes expiry to naive UTC to satisfy google-auth library internals.
        """
        token_obj = self.db.fetch_gsc_token(self.account_id)

        if not token_obj:
            raise AuthError(
                f"No authentication tokens found for account: {self.account_id}"
            )

        expiry = token_obj.expiry

        # Normalize expiry to Naive UTC for google-auth library compatibility
        if expiry and isinstance(expiry, datetime.datetime):
            if expiry.tzinfo is not None:
                # Convert aware to UTC first
                expiry = expiry.astimezone(datetime.timezone.utc)
            # Strip tzinfo to make it naive UTC
            expiry = expiry.replace(tzinfo=None)

        return Credentials(
            token=token_obj.access_token,
            refresh_token=token_obj.refresh_token,
            token_uri=token_obj.token_uri,
            client_id=token_obj.client_id,
            client_secret=settings.GOOGLE_CLIENT_SECRET, # 🔐 Use settings instead of DB
            scopes=token_obj.scopes,
            expiry=expiry,
        )

    # ============================================================
    # 🔁 TOKEN REFRESH
    # ============================================================

    def _init_service(self):
        self._refresh_if_expired()
        return build("searchconsole", "v1", credentials=self.credentials)

    def _refresh_if_expired(self) -> None:
        if not self.credentials:
            return

        # Normalized naive UTC expiry now compatible with internal _helpers.utcnow()
        if self.credentials.expired:
            print(f"[AUTH] [ACCOUNT: {self.account_id}] Token expired, refreshing...")

            try:
                # 1️⃣ BEFORE refresh diagnostics
                print("[AUTH DEBUG] BEFORE REFRESH")
                print(f"  expired: {self.credentials.expired}")
                print(f"  valid: {self.credentials.valid}")
                print(f"  expiry: {self.credentials.expiry}")
                print(f"  token present: {self.credentials.token is not None}")
                print(f"  refresh_token present: {self.credentials.refresh_token is not None}")

                self.credentials.refresh(Request())

                # 2️⃣ AFTER refresh diagnostics
                print("[AUTH DEBUG] AFTER REFRESH")
                print(f"  token present: {self.credentials.token is not None}")
                print(f"  token preview: {self.credentials.token[:10] + '...' if self.credentials.token else None}")
                print(f"  refresh_token present: {self.credentials.refresh_token is not None}")
                print(f"  expiry: {self.credentials.expiry}")
                print(f"  valid: {self.credentials.valid}")
                print(f"  expired: {self.credentials.expired}")

                # Build canonical token model
                new_token = GSCAuthToken(
                    access_token=self.credentials.token,
                    refresh_token=self.credentials.refresh_token,
                    token_uri=self.credentials.token_uri,
                    client_id=self.credentials.client_id,
                    client_secret=self.credentials.client_secret,
                    scopes=self.credentials.scopes,
                    expiry=self.credentials.expiry
                )

                # 3️⃣ BEFORE persistence diagnostics
                print("[AUTH DEBUG] PERSISTING TOKEN DATA")
                print({
                    "access_token_present": new_token.access_token is not None,
                    "refresh_token_present": new_token.refresh_token is not None,
                    "expiry": new_token.expiry,
                })

                self.db.upsert_gsc_token(self.account_id, new_token)

                print(
                    f"[AUTH] [ACCOUNT: {self.account_id}] Token refreshed and persisted"
                )

            except Exception as e:
                # 4️⃣ EXCEPTION diagnostics
                print("[AUTH ERROR] Refresh failed")
                print(f"  Exception type: {type(e)}")
                print(f"  Exception message: {e}")
                print(f"  token present at failure: {self.credentials.token is not None}")
                print(f"  refresh_token present at failure: {self.credentials.refresh_token is not None}")
                raise AuthError(f"Failed to refresh Google OAuth token: {e}")

    # ============================================================
    # 📊 GSC API METHODS
    # ============================================================

    def fetch_properties(self) -> List[Dict[str, Any]]:
        self._refresh_if_expired()

        try:
            sites_list = self.service.sites().list().execute()
            properties = sites_list.get("siteEntry", [])

            print(
                f"[GSC] [ACCOUNT: {self.account_id}] Fetched {len(properties)} properties"
            )

            return properties

        except Exception as e:
            print(f"[GSC ERROR] [ACCOUNT: {self.account_id}] Fetch failed: {e}")
            raise

    def filter_properties(
        self, properties: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        allowed_permissions = {"siteOwner", "siteFullUser"}

        filtered = [
            prop
            for prop in properties
            if prop.get("permissionLevel") in allowed_permissions
        ]

        excluded_count = len(properties) - len(filtered)

        print(
            f"[GSC] [ACCOUNT: {self.account_id}] "
            f"Filtered to {len(filtered)} properties "
            f"(excluded {excluded_count})"
        )

        return filtered