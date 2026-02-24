from __future__ import annotations
import os
from contextlib import asynccontextmanager
from collections import defaultdict
from fastapi import FastAPI, HTTPException, APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from src.config.date_windows import ANALYSIS_WINDOW_DAYS, HALF_ANALYSIS_WINDOW
from datetime import datetime
from decimal import Decimal
from uuid import UUID
import base64
import json

from fastapi.middleware.cors import CORSMiddleware
from src.settings import settings
from src.auth.supabase_auth import get_current_user_id

# Import internal modules
from src.main import run_pipeline
from src.gsc_client import AuthError
from src.auth_handler import GoogleAuthHandler
from src.db_persistence import DatabasePersistence, init_db_pool, close_db_pool, get_db
from concurrent.futures import ThreadPoolExecutor
from src.page_visibility_analyzer import PageVisibilityAnalyzer
from src.device_visibility_analyzer import DeviceVisibilityAnalyzer
from src.utils.metrics import safe_delta_pct
from src.utils.windows import get_most_recent_date, split_rows_by_window, aggregate_metrics


# -------------------------------------------------------------------------
# Lifespan
# -------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection pool and threading lifecycle."""
    # Initialize global pool using centralized settings
    # maxconn=10: Supabase session-mode pooler hard-limits concurrent sessions.
    # Use transaction mode (port 6543) on Supabase for higher concurrency.
    init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=10)
    
    # Initialize global thread pool for long-running ingestion tasks
    # Capped at 4 concurrent runs as per requirements
    app.state.executor = ThreadPoolExecutor(max_workers=4)
    
    yield
    
    # --- GRACEFUL SHUTDOWN ---
    # 1. Mark runs active on THIS instance as interrupted before we die
    if instance_active_runs:
        print(f"[SHUTDOWN] Marking {len(instance_active_runs)} local run(s) as interrupted...")
        db = DatabasePersistence()
        db.connect()
        try:
            for acc_id, run_id in list(instance_active_runs):
                db.update_pipeline_state(
                    acc_id, run_id, 
                    is_running=False, 
                    error="Interrupted (Worker Shutdown)",
                    completed_at=datetime.now()
                )
        finally:
            db.disconnect()
            
    # 2. Shutdown thread pool
    app.state.executor.shutdown(wait=False) # Don't wait forever, we already marked state
    close_db_pool()


# Initialize FastAPI app
app = FastAPI(
    title="GSC Radar API",
    description="Professional SEO performance monitoring and anomaly detection.",
    version="2.0.0",
    lifespan=lifespan
)

# Initialize APIRouter for versioned/prefixed data endpoints
api_router = APIRouter(prefix="/api")

# -------------------------------------------------------------------------
# CORS Configuration
# -------------------------------------------------------------------------
print("\n[STARTUP] Loading CORS settings...")
print(f"[STARTUP] FRONTEND_URL: {settings.FRONTEND_URL}")
print(f"[STARTUP] BACKEND_URL: {settings.BACKEND_URL}")
print(f"[STARTUP] ALLOWED_ORIGINS_STR: {settings.ALLOWED_ORIGINS_STR}")
print(f"[STARTUP] Parsed ALLOWED_ORIGINS from settings: {settings.ALLOWED_ORIGINS}")

allowed_origins = settings.ALLOWED_ORIGINS

# Fallback for local development if empty
if not allowed_origins:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]
    print(f"[STARTUP] ALLOWED_ORIGINS empty, falling back to localhost defaults: {allowed_origins}")

print(f"[STARTUP] Final allowed_origins for CORS: {allowed_origins}\n")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registry for runs active on THIS worker instance (for horizontal safety)
instance_active_runs = set() # Set of (account_id, run_id)


# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------

# CallbackRequest removed since we use GET redirect from Google now

class RecipientRequest(BaseModel):
    account_id: str
    email: str

class SubscriptionRequest(BaseModel):
    account_id: str
    email: str
    property_id: str

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def validate_account_id(account_id: str, db: DatabasePersistence) -> None:
    """
    Validate that an account_id is a valid UUID and exists in the DB.
    Raises HTTPException 400 if malformed, 404 if missing.
    """
    try:
        UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid account_id format")

    if not db.account_exists(account_id):
        raise HTTPException(status_code=404, detail="Account not found")


def validate_account_ownership(account_id: str, user_id: str, db: DatabasePersistence) -> None:
    """
    Verify that the authenticated user owns the requested account.
    Raises 403 Forbidden if ownership check fails.
    Called after validate_account_id so we know the account exists.
    This does NOT change pipeline logic — pipelines always run by account_id.
    """
    if not db.verify_account_ownership(account_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied: account does not belong to your user")


def serialize_for_json(obj):
    """Convert Decimal and datetime objects for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, 'isoformat'):  # date objects
        return obj.isoformat()
    return obj


def serialize_row(row: dict) -> dict:
    """Serialize a database row for JSON response"""
    if not row: return {}
    return {k: serialize_for_json(v) for k, v in row.items()}


# -------------------------
# Health
# -------------------------

@app.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "ok"}


# -------------------------------------------------------------------------
# Authentication (OAuth 2.0 Web Flow)
# -------------------------------------------------------------------------

@api_router.get("/auth/google/url")
def get_auth_url(user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """
    Generate the Google OAuth authorization URL for connecting a GSC account.
    Requires: authenticated Supabase user (Bearer JWT).
    """
    try:
        handler = GoogleAuthHandler(db)
        url = handler.get_authorization_url(user_id=user_id)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/auth/google/callback")
def auth_callback(code: str, state: str = ""):
    """
    Handle the OAuth 2.0 callback from Google.
    Uses a dedicated context-managed DB connection so it's never left open.
    """
    db = DatabasePersistence()
    db.connect()
    try:
        linked_user_id: Optional[str] = None
        if state:
            try:
                state_data = json.loads(base64.urlsafe_b64decode(state + "==").decode())
                linked_user_id = state_data.get("user_id")
            except Exception:
                pass

        handler = GoogleAuthHandler(db)
        account_id, email = handler.handle_callback(code, user_id=linked_user_id)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?account_id={account_id}&email={email}")
    except Exception as e:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error={str(e)}")
    finally:
        db.disconnect()


@api_router.get("/auth/google/reauth")
def force_reauth():
    """Clear session logic simplified: redirect to home with clear flag"""
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/logout")


# -------------------------------------------------------------------------
# Pipeline Control (Namespaced)
# -------------------------------------------------------------------------

def run_pipeline_wrapper(account_id: str, run_id: str):
    """Wrapper to track active runs on this instance for graceful shutdown."""
    instance_active_runs.add((account_id, run_id))
    try:
        run_pipeline(account_id, run_id)
    finally:
        instance_active_runs.discard((account_id, run_id))

@api_router.post("/pipeline/run")
def run_pipeline_endpoint(account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Execute the full GSC analytics pipeline for a specific account."""
    try:
        validate_account_id(account_id, db)
        validate_account_ownership(account_id, user_id, db)
        run_id = db.start_pipeline_run(account_id)
        app.state.executor.submit(run_pipeline_wrapper, account_id, run_id)
        return {"status": "started", "account_id": account_id, "run_id": run_id}
    except RuntimeError as e:
        if "already running" in str(e).lower():
            raise HTTPException(status_code=409, detail="Pipeline is already running for this account")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to dispatch pipeline for {account_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during pipeline dispatch")

@api_router.get("/pipeline/status")
def get_pipeline_status(account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get current pipeline execution status for an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    state = db.fetch_pipeline_state(account_id)
    if not state:
        return {"is_running": False, "account_id": account_id}
    return serialize_row(state)


# -------------------------------------------------------------------------
# Data Exploration (Account Scoped, Namespaced)
# -------------------------------------------------------------------------

@api_router.get("/websites")
def get_websites(account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get all websites for an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    websites = db.fetch_all_websites(account_id)
    return [serialize_row(w) for w in websites]

@api_router.get("/websites/{website_id}/properties")
def get_properties_by_website(website_id: str, account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get all properties for a website within an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    properties = db.fetch_properties_by_website(account_id, website_id)
    return [serialize_row(p) for p in properties]

@api_router.get("/properties/{property_id}/overview")
def get_property_overview(property_id: str, account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get property overview with 7v7 comparison including CTR and Position."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    # Fetch property metadata to get site_url (property_name)
    prop = db.fetch_property_by_id(account_id, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    property_name = prop['site_url']

    metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
    if not metrics:
        return {
            "property_id": property_id,
            "property_name": property_name,
            "initialized": False,
            "last_7_days": {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": 0.0, "days_with_data": 0},
            "prev_7_days": {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": 0.0, "days_with_data": 0},
            "deltas": {"clicks": 0, "impressions": 0, "clicks_pct": 0.0, "impressions_pct": 0.0, "ctr": 0.0, "ctr_pct": 0.0, "avg_position": 0.0},
            "computed_at": None
        }

    most_recent_date = get_most_recent_date(metrics)
    last_rows, prev_rows = split_rows_by_window(metrics, most_recent_date)
    last_7 = aggregate_metrics(last_rows)
    prev_7 = aggregate_metrics(prev_rows)

    clicks_pct = safe_delta_pct(last_7["clicks"], prev_7["clicks"])
    impressions_pct = safe_delta_pct(last_7["impressions"], prev_7["impressions"])
    ctr_pct = safe_delta_pct(last_7["ctr"], prev_7["ctr"])
    position_delta = last_7["avg_position"] - prev_7["avg_position"]

    print(f"\n[OVERVIEW] Property ID: {property_id}")
    print(f"[OVERVIEW] Most Recent Date: {most_recent_date}")

    return {
        "property_id": property_id,
        "property_name": property_name,
        "initialized": True,
        "last_7_days": {
            "clicks": last_7["clicks"],
            "impressions": last_7["impressions"],
            "ctr": round(last_7["ctr"], 4),
            "avg_position": round(last_7["avg_position"], 2),
            "days_with_data": last_7["days_with_data"]
        },
        "prev_7_days": {
            "clicks": prev_7["clicks"],
            "impressions": prev_7["impressions"],
            "ctr": round(prev_7["ctr"], 4),
            "avg_position": round(prev_7["avg_position"], 2),
            "days_with_data": prev_7["days_with_data"]
        },
        "deltas": {
            "clicks": last_7["clicks"] - prev_7["clicks"],
            "impressions": last_7["impressions"] - prev_7["impressions"],
            "clicks_pct": clicks_pct,
            "impressions_pct": impressions_pct,
            "ctr": round(last_7["ctr"] - prev_7["ctr"], 4),
            "ctr_pct": ctr_pct,
            "avg_position": round(position_delta, 2)
        },
        "computed_at": most_recent_date.isoformat()
    }

def classify_property_health(
    impressions_last_7: int,
    impressions_prev_7: int,
    clicks_last_7: int,
    clicks_prev_7: int
) -> str:
    """
    Simple, robust property health classification.
    Returns: 'critical', 'warning', 'healthy', 'insufficient_data'
    """
    MIN_TOTAL_IMPRESSIONS = 500
    total_impressions = impressions_last_7 + impressions_prev_7
    
    if total_impressions < MIN_TOTAL_IMPRESSIONS:
        return "insufficient_data"
    
    if impressions_prev_7 == 0:
        return "insufficient_data"
    
    impressions_delta_pct = (
        (impressions_last_7 - impressions_prev_7) / impressions_prev_7
    ) * 100
    
    clicks_delta_pct = 0
    if clicks_prev_7 > 0:
        clicks_delta_pct = (
            (clicks_last_7 - clicks_prev_7) / clicks_prev_7
        ) * 100
    
    # Catastrophic single-metric drop
    if impressions_delta_pct <= -50 or clicks_delta_pct <= -50:
        return "critical"
    
    # Both metrics significantly down
    if impressions_delta_pct <= -25 and clicks_delta_pct <= -25:
        return "critical"
    
    # Either metric moderately down
    if impressions_delta_pct <= -12 or clicks_delta_pct <= -12:
        return "warning"
    
    # CTR issue: impressions up, clicks down
    if impressions_delta_pct >= 15 and clicks_delta_pct <= -15:
        return "warning"
    
    return "healthy"

@api_router.get("/dashboard-summary")
def get_dashboard_summary(account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get dashboard summary with website-grouped property health status."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    # Check if account data has been initialized
    if not db.is_account_data_initialized(account_id):
        return {
            "status": "not_initialized",
            "message": "Data has not been initialized. Please run the pipeline to sync your properties.",
            "websites": []
        }

    # Fetch all websites for this account
    websites = db.fetch_all_websites(account_id)

    # Batch fetch metrics for ALL properties at once
    all_metrics = db.fetch_all_property_metrics_for_account(account_id)

    # Group metrics by property_id in Python
    metrics_by_prop = defaultdict(list)
    for row in all_metrics:
        metrics_by_prop[row['property_id']].append(row)

    result = {"websites": []}

    for website in websites:
        website_data = {
            "website_id": website['id'],
            "website_domain": website['base_domain'],
            "properties": []
        }

        properties = db.fetch_properties_by_website(account_id, website['id'])

        for prop in properties:
            property_id = prop['id']
            prop_metrics = metrics_by_prop.get(property_id)

            if not prop_metrics:
                continue

            most_recent_date = get_most_recent_date(prop_metrics)
            last_rows, prev_rows = split_rows_by_window(prop_metrics, most_recent_date)
            last_7 = aggregate_metrics(last_rows)
            prev_7 = aggregate_metrics(prev_rows)

            status = classify_property_health(
                last_7["impressions"],
                prev_7["impressions"],
                last_7["clicks"],
                prev_7["clicks"]
            )

            website_data["properties"].append({
                "property_id": property_id,
                "property_name": prop['site_url'],
                "status": status,
                "data_through": most_recent_date.isoformat(),
                "last_7": {"impressions": last_7["impressions"], "clicks": last_7["clicks"]},
                "prev_7": {"impressions": prev_7["impressions"], "clicks": prev_7["clicks"]},
                "delta_pct": {
                    "impressions": safe_delta_pct(last_7["impressions"], prev_7["impressions"]),
                    "clicks": safe_delta_pct(last_7["clicks"], prev_7["clicks"])
                }
            })

        if website_data["properties"]:
            result["websites"].append(website_data)

    return result

@api_router.get("/properties/{property_id}/pages")
def get_page_visibility(property_id: str, account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get page visibility analysis for a property."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    property_data = db.fetch_property_by_id(account_id, property_id)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")

    analyzer = PageVisibilityAnalyzer(db)
    result = analyzer.analyze_property(account_id, property_data)

    if result.get("insufficient_data"):
        return {
            "property_id": property_id,
            "pages": {"new": [], "lost": [], "drop": [], "gain": []},
            "totals": {"new": 0, "lost": 0, "drop": 0, "gain": 0}
        }

    mapped = {
        "new": result["new_pages"],
        "lost": result["lost_pages"],
        "drop": result["drops"],
        "gain": result["gains"],
    }
    totals = {k: len(v) for k, v in mapped.items()}
    return {"property_id": property_id, "pages": mapped, "totals": totals}

@api_router.get("/properties/{property_id}/devices")
def get_device_visibility(property_id: str, account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get device visibility analysis for a property."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    property_data = db.fetch_property_by_id(account_id, property_id)
    if not property_data:
        raise HTTPException(status_code=404, detail="Property not found")

    analyzer = DeviceVisibilityAnalyzer(db)
    result = analyzer.analyze_property(account_id, property_data)

    if result.get("insufficient_data"):
        return {"property_id": property_id, "devices": {}}

    return {"property_id": property_id, "devices": result["details"]}

@api_router.get("/alerts")
def get_alerts(account_id: str, limit: int = 20, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get recent alerts for an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    alerts = db.fetch_recent_alerts(account_id, limit)
    return [serialize_row(a) for a in alerts]

# ── Alert Recipients ──────────────────────────────────────────────────────────

@api_router.get("/alert-recipients")
def get_alert_recipients(account_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get all alert recipients for an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    recipients = db.fetch_alert_recipients(account_id)
    return {"account_id": account_id, "recipients": recipients}

@api_router.post("/alert-recipients")
def add_alert_recipient(request: RecipientRequest, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Add a new alert recipient."""
    validate_account_id(request.account_id, db)
    validate_account_ownership(request.account_id, user_id, db)
    db.add_alert_recipient(request.account_id, request.email)
    return {"status": "success"}

@api_router.delete("/alert-recipients")
def remove_alert_recipient(account_id: str, email: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Remove an alert recipient."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    db.remove_alert_recipient(account_id, email)
    return {"status": "success"}


# ── Alert Subscriptions ───────────────────────────────────────────────────────

@api_router.get("/alert-subscriptions")
def get_alert_subscriptions(account_id: str, email: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Get all property_ids this email is subscribed to for an account."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    property_ids = db.fetch_alert_subscriptions(account_id, email)
    return {"account_id": account_id, "email": email, "property_ids": property_ids}

@api_router.post("/alert-subscriptions")
def add_alert_subscription(request: SubscriptionRequest, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Subscribe an email to alerts for a specific property."""
    validate_account_id(request.account_id, db)
    validate_account_ownership(request.account_id, user_id, db)
    db.add_alert_subscription(request.account_id, request.email, request.property_id)
    return {"status": "success"}

@api_router.delete("/alert-subscriptions")
def remove_alert_subscription(account_id: str, email: str, property_id: str, user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """Unsubscribe an email from alerts for a specific property."""
    validate_account_id(account_id, db)
    validate_account_ownership(account_id, user_id, db)
    db.remove_alert_subscription(account_id, email, property_id)
    return {"status": "success"}


@api_router.get("/accounts")
def get_accounts_for_user(user_id: str = Depends(get_current_user_id), db: DatabasePersistence = Depends(get_db)):
    """
    Return accounts belonging to the authenticated Supabase user.
    Scoped by user_id — users only see their own accounts.
    """
    accounts = db.fetch_accounts_for_user(user_id)
    return [
        {
            "id": str(a["id"]),
            "google_email": a["google_email"],
            "data_initialized": bool(a.get("data_initialized", False))
        }
        for a in accounts
    ]


@app.get("/")
def root():
    return {"status": "ok", "service": "gsc_quickview"}

# -------------------------------------------------------------------------
# Register Routers
# -------------------------------------------------------------------------
app.include_router(api_router)
