from __future__ import annotations
"""
Alert Dispatcher Module
Rebranded as GSC Radar
Migrated from SMTP to SendGrid API
"""

import os
import time
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

# SendGrid SDK
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from src.page_visibility_analyzer import PageVisibilityAnalyzer
from src.settings import settings


def log_dispatcher(message: str, account_email: Optional[str] = None):
    """Log dispatcher messages with timestamp and account context"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    account_prefix = f" [ACCOUNT: {account_email}]" if account_email else ""
    print(f"[{timestamp}] [DISPATCHER]{account_prefix} {message}")


def fetch_seo_health_summary(account_id: str, property_id: str, db) -> Dict[str, Any]:
    """
    Fetch SEO health summary for a property using dynamic computation.
    """
    # 🟢 Use Isolated Analyzer
    analyzer = PageVisibilityAnalyzer(db)
    property_meta = db.fetch_property_by_id(account_id, property_id)
    
    if not property_meta:
        return {
            "new_count": 0,
            "lost_count": 0,
            "drop_count": 0,
            "gain_count": 0,
            "lost_pages": []
        }
    
    # Analyze one property only
    result = analyzer.analyze_property(account_id, property_meta)
    
    if result.get("insufficient_data"):
        return {
            "new_count": 0,
            "lost_count": 0,
            "drop_count": 0,
            "gain_count": 0,
            "lost_pages": []
        }
    
    return {
        "new_count": len(result["new_pages"]),
        "lost_count": len(result["lost_pages"]),
        "drop_count": len(result["drops"]),
        "gain_count": len(result["gains"]),
        "lost_pages": [p["page_url"] for p in result["lost_pages"][:10]]
    }


def generate_email_body(account_id: str, alert: Dict[str, Any], db) -> str:
    """
    Generate email body with SEO health summary.
    """
    property_id = alert["property_id"]
    site_url = alert["site_url"]
    prev_7 = alert["prev_7_impressions"]
    last_7 = alert["last_7_impressions"]
    delta_pct = alert["delta_pct"]
    
    seo_health = fetch_seo_health_summary(account_id, property_id, db)
    
    body = f"""SEO Alert: Impressions Drop Detected

Property:
{site_url}

Sitewide Impressions (7-day comparison):
Previous 7 days: {prev_7:,}
Last 7 days: {last_7:,}
Change: {delta_pct:+.1f}%

SEO Health Summary:
- New pages: {seo_health['new_count']}
- Lost pages: {seo_health['lost_count']}
- Page drops (>50%): {seo_health['drop_count']}
- Page gains (>50%): {seo_health['gain_count']}
"""
    if seo_health['lost_pages']:
        body += "\nLost Pages (top 10):\n"
        for url in seo_health['lost_pages']:
            body += f"- {url.replace(site_url.rstrip('/'), '') or '/'}\n"
    
    body += "\nThis alert was generated automatically by GSC Radar.\n"
    return body


def create_sendgrid_message(account_id: str, alert: Dict[str, Any], recipients: List[str], db) -> Mail:
    """Create SendGrid Mail object for an alert"""
    subject = f"[GSC Radar Alert] Impressions dropped by {abs(alert['delta_pct']):.1f}%"
    body = generate_email_body(account_id, alert, db)
    
    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=recipients,
        subject=subject,
        plain_text_content=body
    )
    return message


def dispatch_pending_alerts(db) -> Dict[str, int]:
    """
    Dispatcher - Iterates through all accounts and sends pending alerts via SendGrid API.
    """
    log_dispatcher("Starting multi-account alert dispatcher (SendGrid Mode)")
    
    # 1. Fetch all accounts
    accounts = db.fetch_all_accounts()
    if not accounts:
        log_dispatcher("No accounts found in database")
        return {'sent': 0, 'failed': 0}

    sent_count = 0
    failed_count = 0

    try:
        # Initialize SendGrid Client
        log_dispatcher("[SENDGRID] Initializing client...")
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

        for acc in accounts:
            account_id = acc['id']
            account_email = acc['google_email']
            
            # 4. Fetch pending alerts for this account
            pending = db.fetch_pending_alerts(account_id)
            if not pending:
                continue
                
            # 5. Fetch recipients for this account
            recipients = db.fetch_alert_recipients(account_id)
            if not recipients:
                log_dispatcher(f"No recipients configured", account_email)
                continue

            log_dispatcher(f"Found {len(pending)} pending alerts for {len(recipients)} recipients", account_email)

            for alert in pending:
                try:
                    mail = create_sendgrid_message(account_id, alert, recipients, db)
                    log_dispatcher(f"[SENDGRID] Sending email for property: {alert['site_url']}", account_email)
                    
                    response = sg.send(mail)
                    
                    # SendGrid returns 202 Accepted on success
                    if response.status_code == 202:
                        db.mark_alert_email_sent(alert['id'])
                        sent_count += 1
                        log_dispatcher(f"✅ [SENDGRID] Status code: 202 (Success)", account_email)
                    else:
                        log_dispatcher(f"❌ [SENDGRID] FAILED with status: {response.status_code}", account_email)
                        log_dispatcher(f"Response Body: {response.body}", account_email)
                        failed_count += 1
                        
                    time.sleep(0.5) # Slight throttle for API rate limits
                except Exception:
                    log_dispatcher(f"❌ [SENDGRID] Incident error occurred for {alert['site_url']}", account_email)
                    log_dispatcher(traceback.format_exc())
                    failed_count += 1

    except Exception:
        log_dispatcher(f"❌ [SENDGRID] Fatal SendGrid error occurred")
        log_dispatcher(traceback.format_exc())
        return {'sent': sent_count, 'failed': failed_count + 1}

    log_dispatcher(f"Dispatcher finished: {sent_count} sent, {failed_count} failed")
    return {'sent': sent_count, 'failed': failed_count}


def main():
    """CLI Entrypoint for cron"""
    log_dispatcher("=" * 60)
    log_dispatcher("GSC Radar Alert Dispatcher Started (SendGrid API)")
    log_dispatcher("=" * 60)
    
    db = None
    
    try:
        # Import and connect to database
        from src.db_persistence import DatabasePersistence, init_db_pool, close_db_pool
        
        # Initialize pool for Cron process using centralized settings
        init_db_pool(settings.DATABASE_URL, minconn=1, maxconn=5)
        
        db = DatabasePersistence()
        db.connect()
        
        log_dispatcher("Database connection established")
        
        # Dispatch pending alerts
        result = dispatch_pending_alerts(db)
        
        # Log summary
        log_dispatcher("=" * 60)
        log_dispatcher(f"Summary: {result['sent']} sent, {result['failed']} failed")
        log_dispatcher("=" * 60)
        
    except Exception as e:
        log_dispatcher(f"❌ Fatal error: {e}")
        log_dispatcher("Dispatcher will retry on next cron run")
    
    finally:
        # Always disconnect database
        if db:
            try:
                db.disconnect()
                # Close pool for Cron process
                close_db_pool()
                log_dispatcher("Database connection and pool closed")
            except Exception as e:
                log_dispatcher(f"Error disconnecting: {e}")


if __name__ == "__main__":
    main()
