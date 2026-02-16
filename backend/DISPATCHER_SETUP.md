# Alert Dispatcher Cron Setup Guide

## Overview

The alert dispatcher is now a **completely independent process** that runs separately from the pipeline via cron.

**Architecture:**
```
Pipeline → Detect alerts → INSERT alerts (email_sent=false) → Exit fast

(5 minutes later)

Cron → alert_dispatcher.py → Send emails → UPDATE (email_sent=true)
```

---

## 1. Test Standalone Execution

First, verify the dispatcher works independently:

```bash
cd /Users/tarunshaji/gsc_quickview/backend
source venv/bin/activate
python src/alert_dispatcher.py
```

**Expected output:**
```
[21:30:00] [DISPATCHER] ============================================================
[21:30:00] [DISPATCHER] Alert Dispatcher Started (Cron Mode)
[21:30:00] [DISPATCHER] ============================================================
[21:30:00] [DISPATCHER] Database connection established
[21:30:00] [DISPATCHER] Starting alert dispatcher
[21:30:00] [DISPATCHER] Found 3 pending alert(s)
[21:30:00] [DISPATCHER] Opening SMTP connection to smtp.gmail.com:587
[21:30:01] [DISPATCHER] ✅ SMTP connection established and authenticated
[21:30:01] [DISPATCHER] Processing alert 1/3 for amouage.com
[21:30:01] [DISPATCHER]   → Sent to user@example.com
[21:30:01] [DISPATCHER] ✅ Alert abc123... sent successfully
...
[21:30:10] [DISPATCHER] SMTP connection closed
[21:30:10] [DISPATCHER] ============================================================
[21:30:10] [DISPATCHER] Dispatcher complete: 3 sent, 0 failed
[21:30:10] [DISPATCHER] ============================================================
[21:30:10] [DISPATCHER] Summary: 3 sent, 0 failed, 3 total
[21:30:10] [DISPATCHER] ============================================================
[21:30:10] [DISPATCHER] Exiting successfully
[21:30:10] [DISPATCHER] Database connection closed
```

---

## 2. Create Logs Directory

```bash
cd /Users/tarunshaji/gsc_quickview/backend
mkdir -p logs
```

---

## 3. Set Up Cron Job

### Edit crontab

```bash
crontab -e
```

### Add this line:

```cron
*/5 * * * * cd /Users/tarunshaji/gsc_quickview/backend && source venv/bin/activate && python src/alert_dispatcher.py >> logs/dispatcher.log 2>&1
```

**What this does:**
- `*/5 * * * *` - Run every 5 minutes
- `cd /Users/tarunshaji/gsc_quickview/backend` - Change to backend directory
- `source venv/bin/activate` - Activate virtual environment
- `python src/alert_dispatcher.py` - Run dispatcher
- `>> logs/dispatcher.log 2>&1` - Append all output to log file

### Save and exit

- **Vim**: Press `Esc`, then `:wq`, then `Enter`
- **Nano**: Press `Ctrl+X`, then `Y`, then `Enter`

---

## 4. Verify Cron Job

Check if cron job was added:

```bash
crontab -l
```

You should see your dispatcher line.

---

## 5. Monitor Dispatcher

### View real-time logs:

```bash
tail -f /Users/tarunshaji/gsc_quickview/backend/logs/dispatcher.log
```

### Check recent runs:

```bash
tail -50 /Users/tarunshaji/gsc_quickview/backend/logs/dispatcher.log
```

### Filter for errors:

```bash
grep "❌" /Users/tarunshaji/gsc_quickview/backend/logs/dispatcher.log
```

---

## 6. Troubleshooting

### Cron not running?

Check cron service status (macOS):

```bash
# macOS uses launchd, not traditional cron
# Verify permissions in System Settings > Privacy & Security > Full Disk Access
```

### Emails not sending?

1. Check SMTP config in `.env`:
```bash
cat src/.env | grep SMTP
```

2. Test dispatcher manually:
```bash
cd /Users/tarunshaji/gsc_quickview/backend
source venv/bin/activate
python src/alert_dispatcher.py
```

3. Check database for pending alerts:
```sql
SELECT id, site_url, email_sent, triggered_at
FROM alerts
ORDER BY triggered_at DESC
LIMIT 10;
```

### Path issues?

Use absolute paths in crontab:

```cron
*/5 * * * * /Users/tarunshaji/gsc_quickview/backend/venv/bin/python /Users/tarunshaji/gsc_quickview/backend/src/alert_dispatcher.py >> /Users/tarunshaji/gsc_quickview/backend/logs/dispatcher.log 2>&1
```

---

## 7. Stopping the Cron Job

To disable:

```bash
crontab -e
# Comment out the line with #
# */5 * * * * cd /Users/...
```

Or remove completely:

```bash
crontab -r  # WARNING: Removes ALL cron jobs
```

---

## Architecture Benefits

✅ **Pipeline never blocks on email**  
✅ **UI unlocks immediately after Phase 3**  
✅ **SMTP failures don't affect pipeline**  
✅ **Automatic retry every 5 minutes**  
✅ **Independent scaling and monitoring**  
✅ **Can restart dispatcher without touching pipeline**  

---

## Exit Codes

- `0` - Success (all emails sent)
- `1` - Partial failure (some emails failed)
- `2` - Fatal error (will retry on next cron run)

---

## Production Checklist

- [ ] Dispatcher runs successfully standalone
- [ ] Cron job added and verified
- [ ] Logs directory created
- [ ] SMTP credentials configured in `.env`
- [ ] Recipients added to `alert_recipients` table
- [ ] Pipeline no longer blocks on emails
- [ ] UI unlocks immediately after pipeline
- [ ] Alerts page shows real-time status updates
