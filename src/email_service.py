"""
Email Service Module

Sends SMTP email alerts with SEO health summaries.

Features:
- SMTP email sending via standard library
- SEO health summary from page visibility analysis
- Plain text email format
- Graceful error handling
"""

import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def log_email(message: str):
    """Log email-related messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [EMAIL] {message}")


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


def generate_email_body(alert_id: str, db) -> str:
    """
    Generate email body with SEO health summary.
    
    Args:
        alert_id: UUID of the alert
        db: DatabasePersistence instance
    
    Returns:
        Plain text email body
    """
    # Fetch alert details
    alert = db.fetch_alert_details(alert_id)
    
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


def send_alert_email(alert_id: str, recipients: List[str], db) -> bool:
    """
    Send alert email via SMTP.
    
    Args:
        alert_id: UUID of the alert
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
        log_email("❌ SMTP configuration incomplete (check .env)")
        return False
    
    # Fetch alert details for subject
    alert = db.fetch_alert_details(alert_id)
    delta_pct = abs(alert["delta_pct"])
    
    # Generate email content
    subject = f"[SEO Alert] Impressions dropped by {delta_pct:.1f}%"
    body = generate_email_body(alert_id, db)
    
    # Create email message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = smtp_from
    msg['To'] = ', '.join(recipients)
    msg.set_content(body)
    
    # Send email
    try:
        log_email(f"Sending alert to {len(recipients)} recipient(s)")
        
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        # Log each recipient
        for recipient in recipients:
            log_email(f"Sent to {recipient}")
        
        log_email("✅ Alert email sent successfully")
        
        # Mark email as sent in database
        db.mark_alert_email_sent(alert_id)
        
        return True
    
    except Exception as e:
        log_email(f"❌ Failed to send email: {e}")
        return False


def send_all_alert_emails(triggered_alerts: List[Dict[str, Any]], db) -> None:
    """
    Send emails for all triggered alerts.
    
    Args:
        triggered_alerts: List of alert dicts with alert_id
        db: DatabasePersistence instance
    """
    if not triggered_alerts:
        log_email("No alerts to send")
        return
    
    # Fetch recipients
    recipients = db.fetch_alert_recipients()
    
    if not recipients:
        log_email("⚠️  No alert recipients configured")
        return
    
    log_email(f"Sending {len(triggered_alerts)} alert(s) to {len(recipients)} recipient(s)")
    
    success_count = 0
    fail_count = 0
    
    for alert in triggered_alerts:
        alert_id = alert["alert_id"]
        
        if send_alert_email(alert_id, recipients, db):
            success_count += 1
        else:
            fail_count += 1
    
    log_email(f"Email sending complete: {success_count} sent, {fail_count} failed")
