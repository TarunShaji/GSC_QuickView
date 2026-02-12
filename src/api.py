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
    """Get property overview with 7v7 comparison including CTR and Position"""
    db = DatabasePersistence()
    db.connect()
    try:
        metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
        if not metrics:
            raise HTTPException(status_code=404, detail="No metrics found for this property")
        
        # Use most_recent_date instead of datetime.now() for GSC lag safety
        most_recent_date = max(row['date'] for row in metrics)
        
        # Initialize aggregation windows
        last_7 = {
            "clicks": 0,
            "impressions": 0,
            "position_sum": 0.0,
            "position_days": 0,
            "days_with_data": 0
        }
        prev_7 = {
            "clicks": 0,
            "impressions": 0,
            "position_sum": 0.0,
            "position_days": 0,
            "days_with_data": 0
        }
        
        # Aggregate metrics into 7-day windows
        for row in metrics:
            row_date = row['date']
            days_ago = (most_recent_date - row_date).days
            
            # Last 7 days: 0-6 days ago from most_recent_date
            if 0 <= days_ago <= 6:
                last_7["clicks"] += row['clicks'] or 0
                last_7["impressions"] += row['impressions'] or 0
                if row.get('position'):
                    last_7["position_sum"] += float(row['position'])
                    last_7["position_days"] += 1
                last_7["days_with_data"] += 1
            # Previous 7 days: 7-13 days ago from most_recent_date
            elif 7 <= days_ago <= 13:
                prev_7["clicks"] += row['clicks'] or 0
                prev_7["impressions"] += row['impressions'] or 0
                if row.get('position'):
                    prev_7["position_sum"] += float(row['position'])
                    prev_7["position_days"] += 1
                prev_7["days_with_data"] += 1
        
        # Compute CTR (NOT averaged - total clicks / total impressions)
        last_7_ctr = (last_7["clicks"] / last_7["impressions"]) if last_7["impressions"] > 0 else 0.0
        prev_7_ctr = (prev_7["clicks"] / prev_7["impressions"]) if prev_7["impressions"] > 0 else 0.0
        
        # Compute Average Position
        last_7_position = (last_7["position_sum"] / last_7["position_days"]) if last_7["position_days"] > 0 else 0.0
        prev_7_position = (prev_7["position_sum"] / prev_7["position_days"]) if prev_7["position_days"] > 0 else 0.0
        
        # Compute deltas
        c_delta = last_7["clicks"] - prev_7["clicks"]
        i_delta = last_7["impressions"] - prev_7["impressions"]
        ctr_delta = last_7_ctr - prev_7_ctr
        position_delta = last_7_position - prev_7_position
        
        # Compute percentage deltas
        clicks_pct = round((c_delta / prev_7["clicks"] * 100) if prev_7["clicks"] > 0 else 0, 2)
        impressions_pct = round((i_delta / prev_7["impressions"] * 100) if prev_7["impressions"] > 0 else 0, 2)
        ctr_pct = round((ctr_delta / prev_7_ctr * 100) if prev_7_ctr > 0 else 0, 2)
        
        # Structured logging
        print(f"\n[OVERVIEW] Property ID: {property_id}")
        print(f"[OVERVIEW] Most Recent Date: {most_recent_date}")
        print(f"[OVERVIEW] Last 7 Days:")
        print(f"  Clicks: {last_7['clicks']:,}")
        print(f"  Impressions: {last_7['impressions']:,}")
        print(f"  CTR: {last_7_ctr*100:.2f}%")
        print(f"  Avg Position: {last_7_position:.1f}")
        print(f"[OVERVIEW] Prev 7 Days:")
        print(f"  Clicks: {prev_7['clicks']:,}")
        print(f"  Impressions: {prev_7['impressions']:,}")
        print(f"  CTR: {prev_7_ctr*100:.2f}%")
        print(f"  Avg Position: {prev_7_position:.1f}")
        print(f"[OVERVIEW] Deltas:")
        print(f"  Clicks: {'+' if c_delta >= 0 else ''}{c_delta:,} ({'+' if clicks_pct >= 0 else ''}{clicks_pct}%)")
        print(f"  Impressions: {'+' if i_delta >= 0 else ''}{i_delta:,} ({'+' if impressions_pct >= 0 else ''}{impressions_pct}%)")
        print(f"  CTR: {'+' if ctr_delta >= 0 else ''}{ctr_delta*100:.2f}% ({'+' if ctr_pct >= 0 else ''}{ctr_pct}%)")
        print(f"  Position: {'+' if position_delta >= 0 else ''}{position_delta:.1f} ({'worse' if position_delta > 0 else 'improvement' if position_delta < 0 else 'unchanged'})")
        
        return {
            "property_id": property_id,
            "last_7_days": {
                "clicks": last_7["clicks"],
                "impressions": last_7["impressions"],
                "ctr": round(last_7_ctr, 4),
                "avg_position": round(last_7_position, 2),
                "days_with_data": last_7["days_with_data"]
            },
            "prev_7_days": {
                "clicks": prev_7["clicks"],
                "impressions": prev_7["impressions"],
                "ctr": round(prev_7_ctr, 4),
                "avg_position": round(prev_7_position, 2),
                "days_with_data": prev_7["days_with_data"]
            },
            "deltas": {
                "clicks": c_delta,
                "impressions": i_delta,
                "clicks_pct": clicks_pct,
                "impressions_pct": impressions_pct,
                "ctr": round(ctr_delta, 4),
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

@app.get("/dashboard-summary")
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
                
                # Fetch metrics for this property
                metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
                
                if not metrics:
                    # Skip properties with no data
                    continue
                
                # Find most recent date
                most_recent_date = max(row['date'] for row in metrics)
                
                # Initialize 7v7 windows (days 1-7 vs days 8-14)
                last_7 = {"clicks": 0, "impressions": 0}
                prev_7 = {"clicks": 0, "impressions": 0}
                
                for row in metrics:
                    row_date = row['date']
                    days_ago = (most_recent_date - row_date).days
                    
                    # Last 7 days: 0-6 days ago
                    if 0 <= days_ago <= 6:
                        last_7["clicks"] += row['clicks'] or 0
                        last_7["impressions"] += row['impressions'] or 0
                    # Previous 7 days: 7-13 days ago
                    elif 7 <= days_ago <= 13:
                        prev_7["clicks"] += row['clicks'] or 0
                        prev_7["impressions"] += row['impressions'] or 0
                
                # Compute delta percentages
                impressions_delta_pct = round(
                    ((last_7["impressions"] - prev_7["impressions"]) / prev_7["impressions"] * 100)
                    if prev_7["impressions"] > 0 else 0,
                    1
                )
                clicks_delta_pct = round(
                    ((last_7["clicks"] - prev_7["clicks"]) / prev_7["clicks"] * 100)
                    if prev_7["clicks"] > 0 else 0,
                    1
                )
                
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
                        "impressions": impressions_delta_pct,
                        "clicks": clicks_delta_pct
                    }
                })
            
            # Only include websites that have properties with data
            if website_data["properties"]:
                result["websites"].append(website_data)
        
        return result
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
# -------------------------
# Alert Recipients
# -------------------------

@app.get("/alert-recipients")
def get_alert_recipients(account_id: str):
    """Get all alert recipients for an account"""
    db = DatabasePersistence()
    db.connect()
    try:
        recipients = db.fetch_alert_recipients(account_id)
        return {"account_id": account_id, "recipients": recipients}
    finally:
        db.disconnect()

@app.post("/alert-recipients")
def add_alert_recipient(request: RecipientRequest):
    """Add a new alert recipient"""
    db = DatabasePersistence()
    db.connect()
    try:
        db.add_alert_recipient(request.account_id, request.email)
        return {"status": "success"}
    finally:
        db.disconnect()

@app.delete("/alert-recipients")
def remove_alert_recipient(account_id: str, email: str):
    """Remove an alert recipient"""
    db = DatabasePersistence()
    db.connect()
    try:
        db.remove_alert_recipient(account_id, email)
        return {"status": "success"}
    finally:
        db.disconnect()
