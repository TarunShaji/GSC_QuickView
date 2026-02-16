# Alert Dispatcher Operational Guide (GSC Radar)

The **Alert Dispatcher** is a decoupled, transactional worker responsible for converting raw anomaly data into professional SaaS-style HTML communications. It is designed for high reliability, idempotency, and minimal operational overhead.

---

## ⚙️ Operational Workflow

The dispatcher operates on a "Fetch-Enrich-Send" cycle, completely independent of the data ingestion pipeline.

```bash
1. Scan `alerts` where `email_sent = false`
2. Enrich property metadata from DB
3. Calculate dynamic 7v7 date windows from `metrics` table
4. Generate Multi-Part (HTML + Plain Text) payload
5. Dispatch via SendGrid API (HTTPS/443)
6. Atomic COMMIT: Update `alerts` set `email_sent = true`
```

---

## 🚀 Deployment & Cron

### Manual Verification
Execute via the module interface to ensure correct path resolution:
```bash
python -m src.alert_dispatcher
```

### Production Cron Setup
For high-signal alerting, recommended execution is every **5 to 15 minutes**.

```cron
# Example crontab entry (*/5)
*/5 * * * * cd /path/to/project/backend && ./venv/bin/python -m src.alert_dispatcher >> logs/dispatcher.log 2>&1
```

---

## 🛡️ Reliability & Resilience

### 1. Idempotency Guarantee
The dispatcher uses a strict **State-First Update** model. Records are only marked as `email_sent = true` upon a 202 "Accepted" response from the SendGrid API. If a crash occurs mid-execution, unsent alerts remain pending and will be picked up by the next run, ensuring zero lost alerts.

### 2. Failure Modes & Retries
- **API Connectivity Loss**: If the SendGrid API is unreachable, the dispatcher exits with a non-zero code. No state is mutated in the DB, allowing for a clean retry on the next cron cycle.
- **Database Latency**: The dispatcher uses short-lived connections to prevent holding locks during long API wait times.

### 3. Concurrency Safety
The dispatcher is safe to run concurrently across multiple instances (e.g. if a previous cron job hangs). The database handles row-level locking or atomic updates to prevent duplicate dispatches for the same alert ID.

---

## 🔍 Troubleshooting

### Monitoring Output
Successful runs will produce high-signal logs:
- `[SENDGRID] Sending HTML alert for property: <name>`
- `[DISPATCHER] ✅ [SENDGRID] Status code: 202 (Success)`

### Error Inspection
Search for the ❌ emoji in your log files to identify dispatch failures:
```bash
grep "❌" backend/logs/dispatcher.log
```

---

## 🔍 Known Architectural Limitations

- **Polling-Based**: Delivery latency is bound by the manual cron interval. There is no real-time push mechanism for alerts immediately after ingestion.
- **In-Memory Payloads**: HTML templates are generated in-memory. For extremely large recipient lists per property (>50), the SendGrid `batch` API would be a required upgrade.
- **No Webhook Feedback**: The system confirms handover to SendGrid but does not currently poll SendGrid webhooks for "Open" or "Bounce" events.
