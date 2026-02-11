"""
FastAPI wrapper for GSC Quick View pipeline.

This is a minimal HTTP interface that exposes the existing pipeline
via authentication and execution endpoints.

Endpoints:
  - GET  /health        → Health check
  - GET  /auth/status   → Check GSC authentication status
  - POST /auth/login    → Trigger Google OAuth (opens browser)
  - POST /pipeline/run  → Execute the full pipeline (blocking)

Usage:
    uvicorn api:app --reload
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Import pipeline + GSC client
from main import run_pipeline
from gsc_client import GSCClient


# Initialize FastAPI app
app = FastAPI(
    title="GSC Quick View API",
    description="HTTP wrapper for Google Search Console analytics pipeline",
    version="1.0.0"
)


# -------------------------
# Health
# -------------------------

@app.get("/health")
def health_check():
    """Basic health check"""
    return {"status": "ok"}


# -------------------------
# Authentication
# -------------------------

@app.get("/auth/status")
def auth_status():
    """
    Check whether backend is authenticated with Google Search Console.
    """
    client = GSCClient()
    return {
        "authenticated": client.is_authenticated()
    }


@app.post("/auth/login")
def auth_login():
    """
    Trigger Google OAuth flow.

    This will:
    - Open a browser
    - Ask the user to log in and grant permissions
    - Store token.json on the backend
    """
    client = GSCClient()
    client.authenticate()  # Opens browser
    return {"status": "authenticated"}


# -------------------------
# Pipeline
# -------------------------

@app.get("/pipeline/status")
def pipeline_status():
    """
    Get current pipeline execution status.
    
    Returns real-time state for frontend polling:
    - is_running: boolean
    - phase: "idle" | "ingestion" | "analysis" | "completed" | "failed"
    - current_step: description of current operation
    - progress: {"current": int, "total": int} for progress bar
    - completed_steps: list of completed step names
    - error: error message if failed, else null
    - started_at: ISO timestamp when pipeline started
    """
    from main import PIPELINE_STATE
    return PIPELINE_STATE

@app.post("/pipeline/run")
def run_pipeline_endpoint():
    """
    Execute the full GSC analytics pipeline.

    Requirements:
    - Backend must already be authenticated
    
    The pipeline runs synchronously and returns immediately after Phase 3.
    Alert detection writes to database.
    Email dispatching is handled by independent cron job.
    """
    client = GSCClient()

    if not client.is_authenticated():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with Google Search Console. Run /auth/login first."
        )

    # Run the pipeline synchronously (blocking)
    run_pipeline()

    return {"status": "completed"}


# NOTE: Email dispatching is now handled by a separate cron job
# Run: python alert_dispatcher.py (scheduled via cron every 5 minutes)
# This ensures email sending never blocks the pipeline or UI


def _deprecated_dispatch_alerts_background():
    """
    Background task to dispatch pending email alerts.
    Runs after pipeline completes, doesn't block HTTP response.
    """
    try:
        from db_persistence import DatabasePersistence
        import alert_dispatcher
        
        db = DatabasePersistence()
        db.connect()
        
        result = alert_dispatcher.dispatch_pending_alerts(db)
        
        print(f"[BACKGROUND] Alert dispatcher: {result['sent']} sent, {result['failed']} failed")
        
        db.disconnect()
    except Exception as e:
        print(f"[BACKGROUND] Alert dispatcher failed: {e}")


# -------------------------
# Data Exploration (Frontend APIs)
# -------------------------

from db_persistence import DatabasePersistence
from datetime import datetime, timedelta
from decimal import Decimal


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
    return {k: serialize_for_json(v) for k, v in row.items()}


@app.get("/websites")
def get_websites():
    """
    Get all websites.
    
    Returns:
        List of websites with: id, base_domain, created_at, property_count
    """
    db = DatabasePersistence()
    db.connect()
    try:
        websites = db.fetch_all_websites()
        return [serialize_row(w) for w in websites]
    finally:
        db.disconnect()


@app.get("/websites/{website_id}/properties")
def get_properties_by_website(website_id: str):
    """
    Get all properties for a website.
    
    Args:
        website_id: UUID of the website
    
    Returns:
        List of properties with: id, site_url, property_type, permission_level
    """
    db = DatabasePersistence()
    db.connect()
    try:
        properties = db.fetch_properties_by_website(website_id)
        if not properties:
            raise HTTPException(status_code=404, detail="Website not found or has no properties")
        return [serialize_row(p) for p in properties]
    finally:
        db.disconnect()


@app.get("/properties/{property_id}/overview")
def get_property_overview(property_id: str):
    """
    Get property overview with 7v7 comparison (computed on-demand).
    
    This endpoint computes the 7-day vs previous 7-day comparison
    dynamically from stored metrics data.
    
    Args:
        property_id: UUID of the property
    
    Returns:
        Overview with: last_7_days, prev_7_days, deltas, percentages
    """
    db = DatabasePersistence()
    db.connect()
    try:
        metrics = db.fetch_property_daily_metrics_for_overview(property_id)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Property not found or no metrics available")
        
        # Compute 7v7 comparison on-demand
        today = datetime.now().date()
        
        # Last 7 days aggregation
        last_7 = {"clicks": 0, "impressions": 0, "days": 0}
        prev_7 = {"clicks": 0, "impressions": 0, "days": 0}
        
        for row in metrics:
            row_date = row['date']
            days_ago = (today - row_date).days
            
            if 1 <= days_ago <= 7:
                last_7["clicks"] += row['clicks'] or 0
                last_7["impressions"] += row['impressions'] or 0
                last_7["days"] += 1
            elif 8 <= days_ago <= 14:
                prev_7["clicks"] += row['clicks'] or 0
                prev_7["impressions"] += row['impressions'] or 0
                prev_7["days"] += 1
        
        # Calculate deltas
        clicks_delta = last_7["clicks"] - prev_7["clicks"]
        impressions_delta = last_7["impressions"] - prev_7["impressions"]
        
        clicks_pct = round((clicks_delta / prev_7["clicks"] * 100) if prev_7["clicks"] > 0 else 0, 2)
        impressions_pct = round((impressions_delta / prev_7["impressions"] * 100) if prev_7["impressions"] > 0 else 0, 2)
        
        return {
            "property_id": property_id,
            "last_7_days": {
                "clicks": last_7["clicks"],
                "impressions": last_7["impressions"],
                "days_with_data": last_7["days"]
            },
            "prev_7_days": {
                "clicks": prev_7["clicks"],
                "impressions": prev_7["impressions"],
                "days_with_data": prev_7["days"]
            },
            "deltas": {
                "clicks": clicks_delta,
                "impressions": impressions_delta,
                "clicks_pct": clicks_pct,
                "impressions_pct": impressions_pct
            },
            "computed_at": datetime.now().isoformat()
        }
    finally:
        db.disconnect()


@app.get("/properties/{property_id}/pages")
def get_page_visibility(property_id: str):
    """
    Get page visibility analysis for a property.
    
    Returns precomputed page visibility data:
    - new: Pages that appeared in last 7 days
    - lost: Pages that disappeared in last 7 days
    - drop: Pages with significant impression drops
    - gain: Pages with significant impression gains
    """
    db = DatabasePersistence()
    db.connect()
    try:
        pages = db.fetch_page_visibility_analysis(property_id)
        
        # Group by category
        result = {
            "new": [],
            "lost": [],
            "drop": [],
            "gain": []
        }
        
        for page in pages:
            category = page.get("category", "new")
            if category in result:
                result[category].append(serialize_row(page))
        
        return {
            "property_id": property_id,
            "pages": result,
            "totals": {
                "new": len(result["new"]),
                "lost": len(result["lost"]),
                "drop": len(result["drop"]),
                "gain": len(result["gain"])
            }
        }
    finally:
        db.disconnect()


@app.get("/properties/{property_id}/devices")
def get_device_visibility(property_id: str):
    """
    Get device visibility analysis for a property.
    
    Returns precomputed device visibility data for:
    - mobile
    - desktop
    - tablet
    """
    db = DatabasePersistence()
    db.connect()
    try:
        devices = db.fetch_device_visibility_analysis(property_id)
        
        # Structure by device
        result = {}
        for device in devices:
            device_name = device.get("device", "unknown")
            result[device_name] = serialize_row(device)
        
        return {
            "property_id": property_id,
            "devices": result
        }
    finally:
        db.disconnect()

# -------------------------
# Alerts
# -------------------------

@app.get("/alerts")
def get_alerts(limit: int = 20):
    """
    Get recent alerts with email status.
    
    Query params:
        limit: Maximum number of alerts to return (default: 20)
    
    Returns:
        List of alerts with property info and email status
    """
    db = DatabasePersistence()
    db.connect()
    try:
        alerts = db.fetch_recent_alerts(limit)
        return [serialize_row(alert) for alert in alerts]
    finally:
        db.disconnect()
