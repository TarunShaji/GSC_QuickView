"""
Alert Dispatcher Module

Dedicated system for dispatching email alerts independently from the pipeline.

Responsibilities:
- Fetch pending alerts (email_sent = false)
- Send SMTP emails
- Mark alerts as sent on success
- Comprehensive logging
- Never crash or block pipeline
"""

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def log_dispatcher(message: str):
    """Log dispatcher messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [DISPATCHER] {message}")


def fetch_seo_health_summary(property_id: str, db) -> Dict[str, Any]:
    """
    Fetch SEO health summary from page visibility analysis.
    
    Args:
        property_id: UUID of the property
        db: DatabasePersistence instance
    
    Returns:
        Dict with: new_count, lost_count, drop_count, gain_count, lost_pages
    """
    # Fetch page visibility analysis
    pages_data = db.fetch_page_visibility_analysis(property_id)
    
    # Group by category
    categories = {
        "new": [],
        "lost": [],
        "drop": [],
        "gain": []
    }
    
    for page in pages_data:
        category = page.get("category", "new")
        if category in categories:
            categories[category].append(page)
    
    # Get lost pages for email body (limit to 10)
    lost_pages = [page["page_url"] for page in categories["lost"][:10]]
    
    return {
        "new_count": len(categories["new"]),
        "lost_count": len(categories["lost"]),
        "drop_count": len(categories["drop"]),
        "gain_count": len(categories["gain"]),
        "lost_pages": lost_pages
    }


def generate_email_body(alert: Dict[str, Any], db) -> str:
    """
    Generate email body with SEO health summary.
    
    Args:
        alert: Alert dict with property_id, site_url, metrics
        db: DatabasePersistence instance
    
    Returns:
        Plain text email body
    """
    property_id = alert["property_id"]
    site_url = alert["site_url"]
    prev_7 = alert["prev_7_impressions"]
    last_7 = alert["last_7_impressions"]
    delta_pct = alert["delta_pct"]
    
    # Fetch SEO health summary
    seo_health = fetch_seo_health_summary(property_id, db)
    
    # Build email body
    body = f"""SEO Alert: Impressions Drop Detected

Property:
{site_url}

Sitewide Impressions (7-day comparison):
Previous 7 days: {prev_7:,}
Last 7 days: {last_7:,}
Change: {delta_pct:+.1f}%

SEO Health Summary:
- New pages detected: {seo_health['new_count']}
- Lost pages detected: {seo_health['lost_count']}
- Significant page drops (>50%): {seo_health['drop_count']}
- Significant page gains (>50%): {seo_health['gain_count']}
"""
    
    # Add lost pages if any
    if seo_health['lost_pages']:
        body += "\nLost Pages (no impressions in last 7 days):\n"
        for page_url in seo_health['lost_pages']:
            # Strip domain for cleaner display
            path = page_url.replace(site_url.rstrip('/'), '')
            if not path:
                path = "/"
            body += f"- {path}\n"
    
    body += "\nThis alert was generated automatically after the latest pipeline run.\n"
    
    return body


def send_alert_email(alert: Dict[str, Any], recipients: List[str], db) -> bool:
    """
    Send alert email via SMTP.
    
    Args:
        alert: Alert dict with all necessary data
        recipients: List of email addresses
        db: DatabasePersistence instance
    
    Returns:
        True if email sent successfully, False otherwise
    """
    # Load SMTP configuration
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from = os.getenv('SMTP_FROM_EMAIL')
    
    # Validate configuration
    if not all([smtp_host, smtp_user, smtp_password, smtp_from]):
        log_dispatcher("❌ SMTP configuration incomplete (check .env)")
        return False
    
    # Generate email content
    delta_pct = abs(alert["delta_pct"])
    subject = f"[SEO Alert] Impressions dropped by {delta_pct:.1f}%"
    body = generate_email_body(alert, db)
    
    # Create email message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_from
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)
    
    # Send email
    try:
        log_dispatcher(f"Sending alert {alert['id'][:8]}... to {len(recipients)} recipient(s)")
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        # Log each recipient
        for recipient in recipients:
            log_dispatcher(f"  → Sent to {recipient}")
        
        log_dispatcher(f"✅ Alert {alert['id'][:8]}... sent successfully")
        return True
    
    except Exception as e:
        log_dispatcher(f"❌ Failed to send alert {alert['id'][:8]}...: {e}")
        return False


def dispatch_pending_alerts(db) -> Dict[str, int]:
    """
    Main dispatcher function - fetches and sends all pending alerts.
    
    This function:
    1. Fetches all alerts where email_sent = false
    2. Fetches all recipients
    3. Sends email for each alert
    4. Marks alert as sent on success
    5. Logs everything
    6. Never raises exceptions
    
    Args:
        db: DatabasePersistence instance (must be connected)
    
    Returns:
        Dict with counts: {'pending': N, 'sent': M, 'failed': K}
    """
    log_dispatcher("Starting alert dispatcher")
    
    try:
        # Fetch pending alerts
        pending_alerts = db.fetch_pending_alerts()
        
        if not pending_alerts:
            log_dispatcher("No pending alerts to send")
            return {'pending': 0, 'sent': 0, 'failed': 0}
        
        log_dispatcher(f"Found {len(pending_alerts)} pending alert(s)")
        
        # Fetch recipients
        recipients = db.fetch_alert_recipients()
        
        if not recipients:
            log_dispatcher("⚠️  No alert recipients configured")
            log_dispatcher("Alerts will remain pending until recipients are added")
            return {'pending': len(pending_alerts), 'sent': 0, 'failed': 0}
        
        log_dispatcher(f"Sending to {len(recipients)} recipient(s): {', '.join(recipients)}")
        
        # Send each alert
        sent_count = 0
        failed_count = 0
        
        for alert in pending_alerts:
            alert_id = alert["id"]
            site_url = alert["site_url"]
            
            log_dispatcher(f"Processing alert for {site_url}")
            
            # Attempt to send email
            success = send_alert_email(alert, recipients, db)
            
            if success:
                # Mark as sent in database
                try:
                    db.mark_alert_email_sent(alert_id)
                    sent_count += 1
                except Exception as e:
                    log_dispatcher(f"⚠️  Email sent but failed to mark as sent: {e}")
                    failed_count += 1
            else:
                failed_count += 1
        
        # Summary
        log_dispatcher("=" * 60)
        log_dispatcher(f"Dispatcher complete: {sent_count} sent, {failed_count} failed")
        log_dispatcher("=" * 60)
        
        return {
            'pending': len(pending_alerts),
            'sent': sent_count,
            'failed': failed_count
        }
    
    except Exception as e:
        log_dispatcher(f"❌ Dispatcher error: {e}")
        log_dispatcher("Dispatcher failed but pipeline is unaffected")
        return {'pending': 0, 'sent': 0, 'failed': 0}
