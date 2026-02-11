"""
FastAPI wrapper for GSC Quick View pipeline.
Multi-Account Aware
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

# Import internal modules
from main import run_pipeline
from gsc_client import AuthError
from auth_handler import GoogleAuthHandler
from db_persistence import DatabasePersistence


# Initialize FastAPI app
app = FastAPI(
    title="GSC Quick View API",
    description="HTTP wrapper for multi-account Google Search Console analytics pipeline",
    version="2.0.0"
)


# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------

# CallbackRequest removed since we use GET redirect from Google now

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
        
        # After success, we MUST redirect the browser back to the frontend app.
        # The user mentioned port 5174 in their request.
        frontend_url = "http://localhost:5173"
        return RedirectResponse(url=f"{frontend_url}/?account_id={account_id}&email={email}")
        
    except Exception as e:
        print(f"[API ERROR] Auth callback failed: {e}")
        # On error, redirect back to frontend with error param so UX can show it
        frontend_url = "http://localhost:5173"
        return RedirectResponse(url=f"{frontend_url}/?auth_error={str(e)}")
    finally:
        db.disconnect()


# -------------------------------------------------------------------------
# Pipeline Control
# -------------------------------------------------------------------------

@app.post("/pipeline/run")
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

@app.get("/pipeline/status")
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
# Data Exploration (Account Scoped)
# -------------------------------------------------------------------------

@app.get("/websites")
def get_websites(account_id: str):
    """Get all websites for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        websites = db.fetch_all_websites(account_id)
        return [serialize_row(w) for w in websites]
    finally:
        db.disconnect()

@app.get("/websites/{website_id}/properties")
def get_properties_by_website(website_id: str, account_id: str):
    """Get all properties for a website within an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        properties = db.fetch_properties_by_website(account_id, website_id)
        return [serialize_row(p) for p in properties]
    finally:
        db.disconnect()

@app.get("/properties/{property_id}/overview")
def get_property_overview(property_id: str, account_id: str):
    """Get property overview with 7v7 comparison"""
    db = DatabasePersistence()
    db.connect()
    try:
        metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="No metrics found for this property")
            
        today = datetime.now().date()
        last_7 = {"clicks": 0, "impressions": 0}
        prev_7 = {"clicks": 0, "impressions": 0}
        
        for row in metrics:
            row_date = row['date']
            days_ago = (today - row_date).days
            if 1 <= days_ago <= 7:
                last_7["clicks"] += row['clicks'] or 0
                last_7["impressions"] += row['impressions'] or 0
            elif 8 <= days_ago <= 14:
                prev_7["clicks"] += row['clicks'] or 0
                prev_7["impressions"] += row['impressions'] or 0
                
        c_delta = last_7["clicks"] - prev_7["clicks"]
        i_delta = last_7["impressions"] - prev_7["impressions"]
        
        return {
            "property_id": property_id,
            "last_7_days": last_7,
            "prev_7_days": prev_7,
            "deltas": {
                "clicks": c_delta,
                "impressions": i_delta,
                "clicks_pct": round((c_delta / prev_7["clicks"] * 100) if prev_7["clicks"] > 0 else 0, 2),
                "impressions_pct": round((i_delta / prev_7["impressions"] * 100) if prev_7["impressions"] > 0 else 0, 2)
            }
        }
    finally:
        db.disconnect()

@app.get("/properties/{property_id}/pages")
def get_page_visibility(property_id: str, account_id: str):
    """Get page visibility analysis for a property"""
    db = DatabasePersistence()
    db.connect()
    try:
        pages = db.fetch_page_visibility_analysis(account_id, property_id)
        result = {"new": [], "lost": [], "drop": [], "gain": []}
        totals = {"new": 0, "lost": 0, "drop": 0, "gain": 0}
        
        for page in pages:
            cat = page.get("category", "new")
            if cat in result:
                result[cat].append(serialize_row(page))
                totals[cat] += 1
                
        return {
            "property_id": property_id, 
            "pages": result,
            "totals": totals
        }
    finally:
        db.disconnect()

@app.get("/properties/{property_id}/devices")
def get_device_visibility(property_id: str, account_id: str):
    """Get device visibility analysis for a property"""
    db = DatabasePersistence()
    db.connect()
    try:
        devices = db.fetch_device_visibility_analysis(account_id, property_id)
        result = {d.get("device", "unknown"): serialize_row(d) for d in devices}
        return {"property_id": property_id, "devices": result}
    finally:
        db.disconnect()

@app.get("/alerts")
def get_alerts(account_id: str, limit: int = 20):
    """Get recent alerts for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        alerts = db.fetch_recent_alerts(account_id, limit)
        return [serialize_row(a) for a in alerts]
    finally:
        db.disconnect()
