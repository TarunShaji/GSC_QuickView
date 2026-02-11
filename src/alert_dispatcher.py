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
import time
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


def create_email_message(alert: Dict[str, Any], recipients: List[str], smtp_from: str, db) -> EmailMessage:
    """
    Create email message for an alert.
    
    Args:
        alert: Alert dict with all necessary data
        recipients: List of email addresses
        smtp_from: From email address
        db: DatabasePersistence instance
    
    Returns:
        EmailMessage object ready to send
    """
    delta_pct = abs(alert["delta_pct"])
    subject = f"[SEO Alert] Impressions dropped by {delta_pct:.1f}%"
    body = generate_email_body(alert, db)
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_from
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)
    
    return msg


def dispatch_pending_alerts(db) -> Dict[str, int]:
    """
    Main dispatcher function - fetches and sends all pending alerts.
    
    This function:
    1. Fetches all alerts where email_sent = false
    2. Fetches all recipients
    3. Opens ONE SMTP connection (reused for all alerts)
    4. Sends email for each alert through the same connection
    5. Marks alert as sent on success
    6. Throttles sends to prevent Gmail rate limiting
    7. Logs everything
    8. Never raises exceptions
    
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
        
        # Load SMTP configuration
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USER')
        smtp_password = os.getenv('SMTP_PASSWORD')
        smtp_from = os.getenv('SMTP_FROM_EMAIL')
        
        # Validate configuration
        if not all([smtp_host, smtp_user, smtp_password, smtp_from]):
            log_dispatcher("❌ SMTP configuration incomplete (check .env)")
            return {'pending': len(pending_alerts), 'sent': 0, 'failed': len(pending_alerts)}
        
        # Open ONE SMTP connection for all alerts
        sent_count = 0
        failed_count = 0
        
        try:
            log_dispatcher(f"Opening SMTP connection to {smtp_host}:{smtp_port}")
            
            # Create SMTP connection with timeout
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()
            server.login(smtp_user, smtp_password)
            
            log_dispatcher("✅ SMTP connection established and authenticated")
            
            # Send each alert through the SAME connection
            for i, alert in enumerate(pending_alerts):
                alert_id = alert["id"]
                site_url = alert["site_url"]
                
                log_dispatcher(f"Processing alert {i+1}/{len(pending_alerts)} for {site_url}")
                
                try:
                    # Create email message
                    msg = create_email_message(alert, recipients, smtp_from, db)
                    
                    # Send through existing connection
                    server.send_message(msg)
                    
                    # Log recipients
                    for recipient in recipients:
                        log_dispatcher(f"  → Sent to {recipient}")
                    
                    # Mark as sent in database
                    db.mark_alert_email_sent(alert_id)
                    sent_count += 1
                    
                    log_dispatcher(f"✅ Alert {alert_id[:8]}... sent successfully")
                    
                    # Throttle to prevent Gmail rate limiting
                    # Sleep between emails (except after last one)
                    if i < len(pending_alerts) - 1:
                        time.sleep(1.5)
                
                except Exception as e:
                    log_dispatcher(f"❌ Failed to send alert {alert_id[:8]}...: {e}")
                    failed_count += 1
            
            # Close SMTP connection
            server.quit()
            log_dispatcher("SMTP connection closed")
        
        except Exception as e:
            log_dispatcher(f"❌ SMTP connection error: {e}")
            failed_count = len(pending_alerts) - sent_count
        
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


def main():
    """
    Main entry point for standalone dispatcher execution.
    
    This function is called when running:
        python alert_dispatcher.py
    
    Designed to be run as a cron job every 5 minutes.
    
    Architecture:
    - Pipeline inserts alerts with email_sent = false
    - Cron job runs this script every 5 minutes
    - Script fetches pending alerts and sends emails
    - Marks email_sent = true on success
    - Never crashes; logs all errors
    """
    log_dispatcher("=" * 60)
    log_dispatcher("Alert Dispatcher Started (Cron Mode)")
    log_dispatcher("=" * 60)
    
    db = None
    
    try:
        # Import and connect to database
        from db_persistence import DatabasePersistence
        
        db = DatabasePersistence()
        db.connect()
        
        log_dispatcher("Database connection established")
        
        # Dispatch pending alerts
        result = dispatch_pending_alerts(db)
        
        # Log summary
        log_dispatcher("=" * 60)
        log_dispatcher(f"Summary: {result['sent']} sent, {result['failed']} failed, {result['pending']} total")
        log_dispatcher("=" * 60)
        
        # Exit code based on result
        if result['failed'] > 0:
            log_dispatcher("Exiting with warnings (some emails failed)")
            exit_code = 1
        else:
            log_dispatcher("Exiting successfully")
            exit_code = 0
    
    except Exception as e:
        log_dispatcher(f"❌ Fatal error: {e}")
        log_dispatcher("Dispatcher will retry on next cron run")
        exit_code = 2
    
    finally:
        # Always disconnect database
        if db:
            try:
                db.disconnect()
                log_dispatcher("Database connection closed")
            except Exception as e:
                log_dispatcher(f"Error disconnecting: {e}")
    
    return exit_code


if __name__ == "__main__":
    """
    Standalone execution entry point.
    
    Usage:
        python alert_dispatcher.py
    
    Cron setup:
        */5 * * * * cd /Users/tarunshaji/gsc_quickview && source venv/bin/activate && python src/alert_dispatcher.py >> logs/dispatcher.log 2>&1
    """
    import sys
    exit_code = main()
    sys.exit(exit_code)
