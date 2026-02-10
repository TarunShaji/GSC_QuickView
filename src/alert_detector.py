"""
Alert Detection Module

Detects sitewide impression drops ≥10% for email alerting.

Logic:
- Computes 7v7 comparison (last 7 days vs previous 7 days)
- Applies noise filtering: prev_7_impressions >= 100
- Triggers alert if delta_pct <= -10%
- Logs explicit decisions for each property
"""

from datetime import datetime
from typing import List, Dict, Any, Optional


def log_alert(message: str):
    """Log alert detection messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [ALERT] {message}")


def compute_7v7_comparison(property_id: str, db) -> Optional[Dict[str, Any]]:
    """
    Compute 7-day vs previous 7-day comparison for a property.
    
    Reuses the same logic as the /properties/{id}/overview endpoint.
    
    Args:
        property_id: UUID of the property
        db: DatabasePersistence instance
    
    Returns:
        Dict with: property_id, site_url, prev_7_impressions, last_7_impressions, delta_pct
        None if no metrics available
    """
    metrics = db.fetch_property_daily_metrics_for_overview(property_id)
    
    if not metrics:
        return None
    
    # Get property URL for logging
    site_url = db.fetch_property_url(property_id)
    
    # Compute 7v7 comparison (same logic as api.py)
    today = datetime.now().date()
    
    last_7 = {"impressions": 0, "days": 0}
    prev_7 = {"impressions": 0, "days": 0}
    
    for row in metrics:
        row_date = row['date']
        days_ago = (today - row_date).days
        
        if 1 <= days_ago <= 7:
            last_7["impressions"] += row['impressions'] or 0
            last_7["days"] += 1
        elif 8 <= days_ago <= 14:
            prev_7["impressions"] += row['impressions'] or 0
            prev_7["days"] += 1
    
    # Calculate delta percentage
    if prev_7["impressions"] > 0:
        delta_pct = ((last_7["impressions"] - prev_7["impressions"]) / prev_7["impressions"]) * 100
    else:
        delta_pct = 0
    
    return {
        "property_id": property_id,
        "site_url": site_url,
        "prev_7_impressions": prev_7["impressions"],
        "last_7_impressions": last_7["impressions"],
        "delta_pct": round(delta_pct, 1)
    }


def should_trigger_alert(comparison: Dict[str, Any]) -> bool:
    """
    Determine if an alert should be triggered.
    
    Rules:
    1. Noise filtering: prev_7_impressions >= 100
    2. Threshold: delta_pct <= -10%
    
    Args:
        comparison: 7v7 comparison dict
    
    Returns:
        True if alert should trigger, False otherwise
    """
    prev_7 = comparison["prev_7_impressions"]
    delta_pct = comparison["delta_pct"]
    
    # Noise filtering
    if prev_7 < 100:
        return False
    
    # Threshold check
    if delta_pct <= -10:
        return True
    
    return False


def detect_alert_for_property(property_id: str, db) -> Optional[str]:
    """
    Detect alert for a single property with explicit logging.
    
    Args:
        property_id: UUID of the property
        db: DatabasePersistence instance
    
    Returns:
        Alert UUID if triggered, None otherwise
    """
    # Compute 7v7 comparison
    comparison = compute_7v7_comparison(property_id, db)
    
    if not comparison:
        return None
    
    site_url = comparison["site_url"]
    prev_7 = comparison["prev_7_impressions"]
    last_7 = comparison["last_7_impressions"]
    delta_pct = comparison["delta_pct"]
    
    # Extract base domain for cleaner logging
    base_domain = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    
    # Log evaluation
    log_alert(f"Evaluating property: {base_domain}")
    log_alert(f"prev_7={prev_7:,} last_7={last_7:,} delta={delta_pct:+.1f}%")
    
    # Check if alert should trigger
    if should_trigger_alert(comparison):
        log_alert(f"✅ Triggered (delta={delta_pct:+.1f}%)")
        
        # Insert alert into database
        alert_id = db.insert_alert(
            property_id=property_id,
            alert_type="impression_drop",
            prev_7_impressions=prev_7,
            last_7_impressions=last_7,
            delta_pct=delta_pct
        )
        
        return alert_id
    else:
        # Determine why it didn't trigger
        if prev_7 < 100:
            log_alert(f"❌ Skipped (baseline too low: {prev_7} < 100)")
        else:
            log_alert(f"❌ Threshold not met")
        
        return None


def detect_alerts_for_all_properties(db) -> List[Dict[str, Any]]:
    """
    Detect alerts for all properties in the database.
    
    Args:
        db: DatabasePersistence instance
    
    Returns:
        List of triggered alerts with: alert_id, property_id, site_url, delta_pct
    """
    log_alert("Starting alert detection for all properties")
    
    # Fetch all properties
    properties = db.fetch_all_properties()
    log_alert(f"Evaluating {len(properties)} properties")
    
    triggered_alerts = []
    
    for prop in properties:
        property_id = prop['id']
        
        # Detect alert for this property
        alert_id = detect_alert_for_property(property_id, db)
        
        if alert_id:
            triggered_alerts.append({
                "alert_id": alert_id,
                "property_id": property_id,
                "site_url": prop['site_url']
            })
    
    log_alert(f"Alert detection complete: {len(triggered_alerts)} alerts triggered")
    
    return triggered_alerts
