from __future__ import annotations
"""
Alert Dispatcher Module
Rebranded as GSC Radar
Transactional Email via SendGrid API
"""

import os
import time
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# SendGrid SDK
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Windows/Metrics Utilities
from src.utils.windows import get_most_recent_date

from src.settings import settings

# ─── Cooldown Configuration ─────────────────────────────────────────────────
# Recipients will not receive more than one real email per property within this
# many days. Cooldown is measured from sent_at (actual send time), not from
# the alert's triggered_at, so cron delays don't erode the window.
COOLDOWN_DAYS = 3


def log_dispatcher(message: str, account_email: Optional[str] = None):
    """Log dispatcher messages with timestamp and account context"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    account_prefix = f" [ACCOUNT: {account_email}]" if account_email else ""
    print(f"[{timestamp}] [DISPATCHER]{account_prefix} {message}")


def generate_plain_text(ctx: Dict[str, Any]) -> str:
    """Generate plain text version of the alert email."""
    return f"""Critical anomaly detected for {ctx['snapshot_date']}. Immediate investigation recommended.

ALERT: {ctx['property_name']} - {abs(ctx['delta_pct']):.1f}% Drop in Impressions

Property: {ctx['property_name']}

Metric: Impressions
Last Week ({ctx['last_week_range']}): {ctx['last_7_impressions']:,}
Previous Week ({ctx['prev_week_range']}): {ctx['prev_7_impressions']:,}

Change: {ctx['delta_pct']:+.1f}% (Threshold: 10%)

Open in GSC Radar: {settings.FRONTEND_URL}

This alert was generated automatically by GSC Radar.
"""


def generate_html_email(ctx: Dict[str, Any]) -> str:
    """Generate professional SaaS-style HTML email."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #111827; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ margin-bottom: 32px; }}
        .alert-badge {{ display: inline-block; padding: 4px 12px; background: #FEF2F2; color: #DC2626; border-radius: 9999px; font-weight: 600; font-size: 14px; margin-bottom: 16px; border: 1px solid #FEE2E2; }}
        .title {{ font-size: 24px; font-weight: 800; margin: 0 0 8px 0; letter-spacing: -0.025em; color: #111827; }}
        .subtitle {{ font-size: 16px; color: #4B5563; margin: 0; }}
        .card {{ background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 12px; padding: 24px; margin: 32px 0; }}
        .card-title {{ font-size: 12px; font-weight: 700; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 20px; }}
        .metric-row {{ margin-bottom: 12px; overflow: hidden; }}
        .metric-label {{ color: #4B5563; font-size: 15px; float: left; }}
        .metric-value {{ font-weight: 600; color: #111827; float: right; }}
        .deviation {{ font-size: 28px; font-weight: 800; color: #DC2626; margin-top: 24px; letter-spacing: -0.02em; }}
        .threshold {{ font-size: 14px; color: #6B7280; font-weight: 400; }}
        .snapshot {{ font-size: 13px; color: #9CA3AF; margin-bottom: 32px; }}
        .button {{ display: inline-block; background: #111827; color: #ffffff !important; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; }}
        .footer {{ margin-top: 48px; padding-top: 24px; border-top: 1px solid #E5E7EB; font-size: 13px; color: #6B7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="alert-badge">🚨 Traffic Anomaly Detected</div>
            <h1 class="title">Anomaly Detected</h1>
            <p class="subtitle">A significant drop in impressions has been detected for <strong>{ctx['property_name']}</strong>.</p>
        </div>

        <div class="card">
            <div class="card-title">Metric: Impressions</div>
            <div class="metric-row">
                <span class="metric-label">Last Week ({ctx['last_week_range']})</span>
                <span class="metric-value">{ctx['last_7_impressions']:,}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Previous Week ({ctx['prev_week_range']})</span>
                <span class="metric-value">{ctx['prev_7_impressions']:,}</span>
            </div>
            <div class="deviation">
                {ctx['delta_pct']:+.1f}% <span class="threshold">(Threshold: 10%)</span>
            </div>
        </div>

        <div class="snapshot">
            Data Snapshot: {ctx['snapshot_date']}
        </div>

        <a href="{settings.FRONTEND_URL}" class="button">Open in GSC Radar →</a>

        <div class="footer">
            This alert was generated automatically by GSC Radar.<br>
            If this drop is expected, no action is required.
        </div>
    </div>
</body>
</html>
"""


def create_sendgrid_message(ctx: Dict[str, Any], recipients: List[str]) -> Mail:
    """Create multi-part SendGrid Mail object for an alert"""
    subject = f"ALERT: {ctx['property_name']} - {abs(ctx['delta_pct']):.1f}% Drop in Impressions"
    plain_text = generate_plain_text(ctx)
    html_content = generate_html_email(ctx)
    
    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=recipients,
        subject=subject,
        plain_text_content=plain_text,
        html_content=html_content
    )
    return message


def dispatch_pending_alerts(db) -> Dict[str, int]:
    """
    Dispatcher - Iterates through all accounts and sends pending alerts via SendGrid API.
    
    Flow per alert:
      1. Fetch property-level subscribers
      2. Zero-subscriber guard: mark email_sent=True and skip
      3. Insert delivery rows (idempotent)
      4. Fetch unsent deliveries (authoritative list, FOR UPDATE SKIP LOCKED)
      5. For each unsent delivery:
         a. Check per-recipient 3-day cooldown → suppress if in cooldown
         b. Send via SendGrid on 202 → mark sent
         c. Leave unsent on failure → cron retries
      6. Close alert if all deliveries sent or suppressed
    """
    log_dispatcher("Starting multi-account alert dispatcher (SendGrid Mode)")
    
    # 1. Fetch all accounts
    accounts = db.fetch_all_accounts()
    if not accounts:
        log_dispatcher("No accounts found in database")
        return {'sent': 0, 'failed': 0, 'suppressed': 0}

    sent_count = 0
    failed_count = 0
    suppressed_count = 0

    try:
        # Initialize SendGrid Client
        log_dispatcher("[SENDGRID] Initializing client...")
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)

        for acc in accounts:
            account_id = acc['id']
            account_email = acc['google_email']
            
            # Fetch pending alerts for this account (email_sent=false, within 7 days)
            pending = db.fetch_pending_alerts(account_id)
            if not pending:
                continue

            log_dispatcher(f"Found {len(pending)} pending alert(s) to dispatch", account_email)

            for alert in pending:
                alert_id = alert['id']
                property_id = alert['property_id']

                try:
                    # ── STEP 1: Fetch property-level subscribers ──────────────────
                    subscribers = db.fetch_property_subscribers(account_id, property_id)

                    # ── STEP 2: Zero-subscriber guard ─────────────────────────────
                    # If no one is subscribed, mark alert complete immediately.
                    # Without this guard, email_sent stays false forever → cron loop.
                    if not subscribers:
                        log_dispatcher(
                            f"No subscribers for property {alert.get('site_url', property_id)} "
                            f"(alert_id={alert_id}) — marking complete (no email sent)",
                            account_email
                        )
                        db.mark_alert_email_sent(alert_id)
                        continue

                    # ── STEP 3: Data enrichment ───────────────────────────────────
                    property_meta = db.fetch_property_by_id(account_id, property_id)
                    property_name = property_meta.get('property_name') if property_meta else alert['site_url']
                    if not property_name:
                        property_name = alert['site_url'].replace("https://", "").replace("http://", "").rstrip("/")

                    # Fetch raw metrics for precise week ranges
                    metrics = db.fetch_property_daily_metrics_for_overview(account_id, property_id)
                    most_recent_date = get_most_recent_date(metrics)
                    
                    last_7_start = most_recent_date - timedelta(days=6)
                    prev_7_start = most_recent_date - timedelta(days=13)
                    prev_7_end = most_recent_date - timedelta(days=7)
                    
                    last_week_range = f"{last_7_start.strftime('%b %-d')} – {most_recent_date.strftime('%b %-d')}"
                    prev_week_range = f"{prev_7_start.strftime('%b %-d')} – {prev_7_end.strftime('%b %-d')}"
                    snapshot_date = most_recent_date.strftime("%B %-d, %Y")

                    ctx = {
                        "property_id": property_id,
                        "property_name": property_name,
                        "prev_7_impressions": alert['prev_7_impressions'],
                        "last_7_impressions": alert['last_7_impressions'],
                        "delta_pct": alert['delta_pct'],
                        "last_week_range": last_week_range,
                        "prev_week_range": prev_week_range,
                        "snapshot_date": snapshot_date
                    }

                    # ── STEP 4: Insert all delivery rows BEFORE sending ───────────
                    # Idempotent: ON CONFLICT (alert_id, email) DO NOTHING
                    for email in subscribers:
                        db.insert_alert_delivery(alert_id, account_id, email)

                    # ── STEP 5: Fetch the authoritative unsent delivery list ───────
                    # Uses FOR UPDATE SKIP LOCKED — safe under concurrent cron runs.
                    unsent = db.fetch_unsent_deliveries(alert_id)
                    if not unsent:
                        # All deliveries already sent/suppressed from a prior cron run
                        log_dispatcher(f"All deliveries already closed for alert {alert_id}", account_email)
                        db.mark_alert_email_sent(alert_id)
                        continue

                    log_dispatcher(
                        f"Sending alert for '{property_name}' to {len(unsent)} recipient(s)",
                        account_email
                    )

                    # ── STEP 6: Send one email per delivery (cooldown-aware) ───────
                    for delivery in unsent:
                        delivery_id = delivery['id']
                        recipient_email = delivery['email']
                        try:
                            # Per-recipient cooldown check.
                            # If this recipient received a real email for this property
                            # within the last COOLDOWN_DAYS, suppress (don't send).
                            # mark_delivery_suppressed() sets sent=true so closure works.
                            if db.is_recipient_in_cooldown(
                                alert_id, recipient_email, account_id, property_id, COOLDOWN_DAYS
                            ):
                                db.mark_delivery_suppressed(delivery_id)
                                suppressed_count += 1
                                log_dispatcher(
                                    f"⏭  Suppressed ({COOLDOWN_DAYS}-day cooldown) "
                                    f"→ {recipient_email} [delivery: {delivery_id}]",
                                    account_email
                                )
                                continue

                            mail = create_sendgrid_message(ctx, [recipient_email])
                            response = sg.send(mail)

                            if response.status_code == 202:
                                # Success: mark this delivery as sent
                                db.mark_delivery_sent(delivery_id)
                                sent_count += 1
                                log_dispatcher(f"✅ [SENDGRID] 202 → {recipient_email}", account_email)
                            else:
                                # Failure: leave sent=false, cron will retry
                                log_dispatcher(
                                    f"❌ [SENDGRID] {response.status_code} → {recipient_email}",
                                    account_email
                                )
                                failed_count += 1

                            time.sleep(0.5)  # API rate limit throttle

                        except Exception:
                            log_dispatcher(f"❌ [SENDGRID] Exception sending to {recipient_email}", account_email)
                            log_dispatcher(traceback.format_exc())
                            failed_count += 1

                    # ── STEP 7: Close alert if all deliveries complete ────────────
                    if db.check_if_alert_fully_delivered(alert_id):
                        db.mark_alert_email_sent(alert_id)
                        log_dispatcher(f"✅ Alert {alert_id} fully delivered — marked complete", account_email)
                    else:
                        log_dispatcher(f"⏳ Alert {alert_id} partially delivered — will retry", account_email)

                except Exception:
                    log_dispatcher(f"❌ Error processing alert {alert_id}", account_email)
                    log_dispatcher(traceback.format_exc())
                    failed_count += 1

    except Exception:
        log_dispatcher("❌ [SENDGRID] Fatal SendGrid error occurred")
        log_dispatcher(traceback.format_exc())
        return {'sent': sent_count, 'failed': failed_count + 1, 'suppressed': suppressed_count}

    log_dispatcher(
        f"Dispatcher finished: {sent_count} sent, {suppressed_count} suppressed, {failed_count} failed"
    )
    return {'sent': sent_count, 'failed': failed_count, 'suppressed': suppressed_count}


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
        log_dispatcher(
            f"Summary: {result['sent']} sent, "
            f"{result['suppressed']} suppressed (cooldown), "
            f"{result['failed']} failed"
        )
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
