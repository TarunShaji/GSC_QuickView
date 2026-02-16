# GSC Radar – Backend 🛰️

The GSC Radar backend is a high-performance SEO data orchestration service. It manages multi-account Google Search Console (GSC) ingestion, anomaly detection, and transactional alert dispatching using a strictly decoupled, database-driven architecture.

---

## 🏗️ System Architecture

The backend is built as a set of stateless services connected by a shared PostgreSQL state layer.

### 1. File Registry & Module Responsibilities

| File | Responsibility |
| :--- | :--- |
| **`api.py`** | **FastAPI Entry Point**: Defines REST endpoints, CORS configuration, and orchestrates dashboard request flows. |
| **`main.py`** | **Pipeline Orchestrator**: Manages the sequential "Discovery → Ingest → Analyze" pipeline execution. |
| **`db_persistence.py`** | **State Management**: Handles all PostgreSQL interactions, connection pooling, and account-scoped data isolation. |
| **`alert_detector.py`** | **Detection Engine**: Implements the 7v7 sliding window logic to identify significant traffic anomalies. |
| **`alert_dispatcher.py`** | **Transactional Worker**: Standalone process for building and sending SaaS-style alerts via SendGrid. |
| **`settings.py`** | **Environment Layer**: Pydantic-based config that validates `.env` variables and derives dynamic URIs. |
| **`gsc_client.py`** | **Google API Wrapper**: Thread-safe client for communicating with the GSC API with built-in error handling. |
| **`auth_handler.py`** | **OAuth Orchestrator**: Manages the Google OAuth 2.0 lifecycle including token exchange and persistence. |
| **`config/`** | **Global Constants**: Defines canonical windows (e.g., 14-day analysis) and GSC data lag constants. |
| **`utils/`** | **Shared Utilities**: Common logic for metric calculations and URL/domain normalization. |

---

## 🔄 The Ingestion Pipeline (`main.py`)

The pipeline handles data movement from Google to your database. It is designed to be **idempotent** and **self-healing**.

### Self-Healing Ingestion Logic
The system automatically chooses between two modes per property based on local data density:
- **Daily Mode (1 Day)**: If the DB has ≥14 days of recent data, it fetches only the most recent available day (usually `today - 2 days`) to slide the analysis window forward.
- **Backfill Mode (14 Days)**: If a "hole" is detected in the data (e.g., the server was down), it fetches the full 14-day history in one pass to repair the analyzer's buffer.

### Sequential Processing Phases
1.  **Discovery**: Fetches all verified properties matched to the `account_id`.
2.  **Metrics Ingestion**:
    - **Property Level**: Aggregated clicks/impressions/CTR/position.
    - **Page Level**: Top URLs (filtered by impressions > 0).
    - **Device Level**: Breakdown by Mobile/Desktop/Tablet.
3.  **Analysis**: Executes the detection engine immediately after ingestion to ensure alerts are generated with fresh data.

---

## 🧠 Anomaly Detection Engine (`alert_detector.py`)

GSC Radar uses a **7-vs-7 day sliding window** comparison to identify traffic anomalies.

### Detection Criteria
- **Segment A**: Current 7-day window (ending `today - 2 days`).
- **Segment B**: Previous 7-day window (preceding Segment A).
- **Trigger Formula**: `((Impressions_A - Impressions_B) / Impressions_B) <= -10%`.
- **Significance Filter**: The previous window must have at least 100 impressions to avoid alerting on low-volume noise.
- **Persistence**: Alerts are committed to the `alerts` table with `email_sent = false`.

---

## 📧 Alert Dispatcher (`alert_dispatcher.py`)

The dispatcher is a **decoupled worker process** that should run via system Cron every 5 minutes.

- **Isolation**: Being separate from the pipeline ensures that mail delivery latency or SendGrid API timeouts do not block data ingestion.
- **Atomicity**: The dispatcher only marks an alert as `email_sent = true` upon receiving a `202 Accepted` status from SendGrid.
- **Rich Templates**: Generates multi-part emails (Plain Text + SaaS-style HTML) with dynamic date ranges and deep-links to the property dashboard.

---

## 📊 Database Schema Summary

| Table | Purpose |
| :--- | :--- |
| `accounts` | Stores the primary UUID for all data scoping and Google Email. |
| `gsc_tokens` | Secure storage of Access/Refresh tokens per account. |
| `properties` | Metadata for GSC sites (URL, permissions). |
| `property_daily_metrics` | Historical sitewide performance. |
| `page_daily_metrics` | URL-level performance (Page, Date, Clicks, Impressions). |
| `alerts` | Log of detected anomalies and their notification status. |
| `alert_recipients` | List of emails authorized to receive alerts per account. |

**Important**: Every query is strictly filtered by `account_id`. The frontend cannot access data without a valid UID matched in the state layer.

---

## 🛠️ Operational Guide

### Environment Setup
Required in `backend/src/.env`:
```env
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require
GOOGLE_CLIENT_ID=<id>
GOOGLE_CLIENT_SECRET=<secret>
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google/callback
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=alerts@yourdomain.com
FRONTEND_URL=https://dashboard.yourdomain.com
```

### Running in Production
1.  **API Service**: `uvicorn src.api:app --host 0.0.0.0 --port $PORT`
2.  **Pipeline**: Triggered via API or `python -m src.main` (can be cron-driven).
3.  **Dispatcher**: Run `python -m src.alert_dispatcher` via Cron every 5 minutes.

### Failure Recovery
- **Pipeline Fail**: Safe to restart immediately. It uses `ON CONFLICT` updates and will simply overwrite/repair missing data.
- **Dispatcher Fail**: Safe to restart. It only processes unsent alerts (idempotent).

---

## 🛡️ Implementation Realities (No-Fluff)

- **Execution**: Uses `ThreadPoolExecutor` for parallel ingestion; no external task brokers (Celery/Redis).
- **Auth**: Stateless session hydration via `account_id` in query parameters.
- **Caching**: No Redis/Memcached; direct-to-DB query architecture.
- **Real-time**: Alerts are polling-based; notification speed depends on the Cron frequency.
