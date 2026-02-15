import os
from contextlib import asynccontextmanager
from collections import defaultdict
from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from config.date_windows import ANALYSIS_WINDOW_DAYS, HALF_ANALYSIS_WINDOW
from datetime import datetime
from decimal import Decimal

from fastapi.middleware.cors import CORSMiddleware
from settings import settings

# Import internal modules
from main import run_pipeline
from gsc_client import AuthError
from auth_handler import GoogleAuthHandler
from db_persistence import DatabasePersistence, init_db_pool, close_db_pool
from page_visibility_analyzer import PageVisibilityAnalyzer
from device_visibility_analyzer import DeviceVisibilityAnalyzer
from utils.metrics import safe_delta_pct
from utils.windows import get_most_recent_date, split_rows_by_window, aggregate_metrics


# -------------------------------------------------------------------------
# Lifespan
# -------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection pool lifecycle."""
    # Initialize global pool using centralized settings
    init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=10)
    
    yield
    
    # Clean shutdown
    close_db_pool()


# Initialize FastAPI app
app = FastAPI(
    title="GSC Quick View API",
    description="HTTP wrapper for multi-account Google Search Console analytics pipeline",
    version="2.0.0",
    lifespan=lifespan
)

# Initialize APIRouter for versioned/prefixed data endpoints
api_router = APIRouter(prefix="/api")

# Add CORS Middleware for production portability
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------

# CallbackRequest removed since we use GET redirect from Google now

class RecipientRequest(BaseModel):
    account_id: str
    email: str

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

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

@app.get("/auth/google/url")
def get_auth_url():
    """
    Generate the Google OAuth authorization URL.
    The redirect_uri is controlled by the backend (auth_handler.py).
    """
    db = DatabasePersistence()
    try:
        handler = GoogleAuthHandler(db)
        url = handler.get_authorization_url()
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/google/callback")
def auth_callback(code: str):
    """
    Handle the OAuth 2.0 callback DIRECTLY from Google.
    Exchanges code for tokens, stores in DB, and redirects to frontend.
    """
    db = DatabasePersistence()
    db.connect()
    try:
        handler = GoogleAuthHandler(db)
        account_id, email = handler.handle_callback(code)
        db.disconnect()
        
        # 🔗 Use dynamic frontend URL from settings
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?account_id={account_id}&email={email}")
    except Exception as e:
        db.disconnect()
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/?error={str(e)}")


@app.get("/auth/google/reauth")
def force_reauth():
    """Clear session logic simplified: redirect to home with clear flag"""
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/logout")


# -------------------------------------------------------------------------
# Pipeline Control (Namespaced)
# -------------------------------------------------------------------------

@api_router.post("/pipeline/run")
def run_pipeline_endpoint(account_id: str, background_tasks: BackgroundTasks):
    """
    Execute the full GSC analytics pipeline for a specific account.
    Runs in the background.
    """
    db = DatabasePersistence()
    db.connect()
    try:
        # Check if already running (optional but good for UX)
        state = db.fetch_pipeline_state(account_id)
        if state and state.get('is_running'):
            return {"status": "already_running", "account_id": account_id}
            
        # Trigger background task
        background_tasks.add_task(run_pipeline, account_id)
        return {"status": "started", "account_id": account_id}
    finally:
        db.disconnect()

@api_router.get("/pipeline/status")
def get_pipeline_status(account_id: str):
    """
    Get current pipeline execution status for an account from the database.
    """
    db = DatabasePersistence()
    db.connect()
    try:
        state = db.fetch_pipeline_state(account_id)
        if not state:
            return {"is_running": False, "phase": "idle", "account_id": account_id}
        return serialize_row(state)
    finally:
        db.disconnect()


# -------------------------------------------------------------------------
# Data Exploration (Account Scoped, Namespaced)
# -------------------------------------------------------------------------

@api_router.get("/websites")
def get_websites(account_id: str):
    """Get all websites for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        websites = db.fetch_all_websites(account_id)
        return [serialize_row(w) for w in websites]
    finally:
        db.disconnect()

@api_router.get("/websites/{website_id}/properties")
def get_properties_by_website(website_id: str, account_id: str):
    """Get all properties for a website within an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        properties = db.fetch_properties_by_website(account_id, website_id)
        return [serialize_row(p) for p in properties]
    finally:
        db.disconnect()

@api_router.get("/properties/{property_id}/overview")
def get_property_overview(property_id: str, account_id: str):
    """Get property overview with 7v7 comparison including CTR and Position"""
    db = DatabasePersistence()
    db.connect()
    try:
        metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
        if not metrics:
            return {
                "property_id": property_id,
                "initialized": False,
                "last_7_days": {
                    "clicks": 0,
                    "impressions": 0,
                    "ctr": 0.0,
                    "avg_position": 0.0,
                    "days_with_data": 0
                },
                "prev_7_days": {
                    "clicks": 0,
                    "impressions": 0,
                    "ctr": 0.0,
                    "avg_position": 0.0,
                    "days_with_data": 0
                },
                "deltas": {
                    "clicks": 0,
                    "impressions": 0,
                    "clicks_pct": 0.0,
                    "impressions_pct": 0.0,
                    "ctr": 0.0,
                    "ctr_pct": 0.0,
                    "avg_position": 0.0
                },
                "computed_at": None
            }
        
        # 🟢 Use Centralized Window Logic
        most_recent_date = get_most_recent_date(metrics)
        last_rows, prev_rows = split_rows_by_window(metrics, most_recent_date)
        
        # 🟢 Use Centralized Aggregation
        last_7 = aggregate_metrics(last_rows)
        prev_7 = aggregate_metrics(prev_rows)
        
        # Compute deltas using safe_delta_pct
        clicks_pct = safe_delta_pct(last_7["clicks"], prev_7["clicks"])
        impressions_pct = safe_delta_pct(last_7["impressions"], prev_7["impressions"])
        ctr_pct = safe_delta_pct(last_7["ctr"], prev_7["ctr"])
        
        # Position delta (raw diff)
        position_delta = last_7["avg_position"] - prev_7["avg_position"]
        
        # Structured logging (preserved for visibility)
        print(f"\n[OVERVIEW] Property ID: {property_id}")
        print(f"[OVERVIEW] Most Recent Date: {most_recent_date}")
        
        return {
            "property_id": property_id,
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
    finally:
        db.disconnect()

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
def get_dashboard_summary(account_id: str):
    """
    Get dashboard summary with website-grouped property health status.
    Computes 7v7 health metrics for all properties.
    """
    db = DatabasePersistence()
    db.connect()
    try:
        # Check if account data has been initialized
        if not db.is_account_data_initialized(account_id):
            return {
                "status": "not_initialized",
                "message": "Data has not been initialized. Please run the pipeline to sync your properties.",
                "websites": []
            }
        
        # Fetch all websites for this account
        websites = db.fetch_all_websites(account_id)
        
        # 🔐 BATCH FETCH metrics for ALL properties at once
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
            
            # Fetch all properties for this website
            properties = db.fetch_properties_by_website(account_id, website['id'])
            
            for prop in properties:
                property_id = prop['id']
                prop_metrics = metrics_by_prop.get(property_id)
                
                if not prop_metrics:
                    continue
                
                # 🟢 Use Centralized Window logic
                most_recent_date = get_most_recent_date(prop_metrics)
                last_rows, prev_rows = split_rows_by_window(prop_metrics, most_recent_date)
                
                # 🟢 Use Centralized Aggregation
                last_7 = aggregate_metrics(last_rows)
                prev_7 = aggregate_metrics(prev_rows)
                
                # Use robust health classification
                status = classify_property_health(
                    last_7["impressions"],
                    prev_7["impressions"],
                    last_7["clicks"],
                    prev_7["clicks"]
                )
                
                # Add property summary with structured metrics
                website_data["properties"].append({
                    "property_id": property_id,
                    "property_name": prop['site_url'],
                    "status": status,
                    "data_through": most_recent_date.isoformat(),
                    "last_7": {
                        "impressions": last_7["impressions"],
                        "clicks": last_7["clicks"]
                    },
                    "prev_7": {
                        "impressions": prev_7["impressions"],
                        "clicks": prev_7["clicks"]
                    },
                    "delta_pct": {
                        "impressions": safe_delta_pct(last_7["impressions"], prev_7["impressions"]),
                        "clicks": safe_delta_pct(last_7["clicks"], prev_7["clicks"])
                    }
                })
            
            # Only include websites that have properties with data
            if website_data["properties"]:
                result["websites"].append(website_data)
        
        return result
    finally:
        db.disconnect()

@api_router.get("/properties/{property_id}/pages")
def get_page_visibility(property_id: str, account_id: str):
    """Get page visibility analysis for a property (Dynamic Computation)"""
    db = DatabasePersistence()
    db.connect()
    try:
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

        totals = {
            "new": len(mapped["new"]),
            "lost": len(mapped["lost"]),
            "drop": len(mapped["drop"]),
            "gain": len(mapped["gain"]),
        }

        return {
            "property_id": property_id,
            "pages": mapped,
            "totals": totals
        }
    finally:
        db.disconnect()

@api_router.get("/properties/{property_id}/devices")
def get_device_visibility(property_id: str, account_id: str):
    """Get device visibility analysis for a property (Dynamic Computation)"""
    db = DatabasePersistence()
    db.connect()
    try:
        property_data = db.fetch_property_by_id(account_id, property_id)
        if not property_data:
            raise HTTPException(status_code=404, detail="Property not found")

        analyzer = DeviceVisibilityAnalyzer(db)
        result = analyzer.analyze_property(account_id, property_data)

        if result.get("insufficient_data"):
            return {
                "property_id": property_id,
                "devices": {}
            }

        return {
            "property_id": property_id,
            "devices": result["details"]
        }
    finally:
        db.disconnect()

@api_router.get("/alerts")
def get_alerts(account_id: str, limit: int = 20):
    """Get recent alerts for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        alerts = db.fetch_recent_alerts(account_id, limit)
        return [serialize_row(a) for a in alerts]
    finally:
        db.disconnect()
# -------------------------
# Alert Recipients (Namespaced)
# -------------------------

@api_router.get("/alert-recipients")
def get_alert_recipients(account_id: str):
    """Get all alert recipients for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        recipients = db.fetch_alert_recipients(account_id)
        return {"account_id": account_id, "recipients": recipients}
    finally:
        db.disconnect()

@api_router.post("/alert-recipients")
def add_alert_recipient(request: RecipientRequest):
    """Add a new alert recipient"""
    db = DatabasePersistence()
    db.connect()
    try:
        db.add_alert_recipient(request.account_id, request.email)
        return {"status": "success"}
    finally:
        db.disconnect()

@api_router.delete("/alert-recipients")
def remove_alert_recipient(account_id: str, email: str):
    """Remove an alert recipient"""
    db = DatabasePersistence()
    db.connect()
    try:
        db.remove_alert_recipient(account_id, email)
        return {"status": "success"}
    finally:
        db.disconnect()


# -------------------------------------------------------------------------
# Register Routers
# -------------------------------------------------------------------------
app.include_router(api_router)
