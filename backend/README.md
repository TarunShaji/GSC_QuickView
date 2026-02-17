# GSC Radar – Backend 🛰️

The GSC Radar backend is a stateless, multi-tenant Google Search Console (GSC) ingestion and anomaly detection service.

**It performs:**
- Secure OAuth authentication (server-side only)
- Daily GSC metric ingestion
- 7v7 anomaly detection
- Transactional email alert dispatch
- Multi-account isolation via strict UUID scoping

The system is designed for stateless deployment, cron-driven orchestration, and database-enforced concurrency control.

---

## 🏗️ Production Architecture

### Current Deployment Topology

#### Frontend
- **Hosted on**: Vercel
- **Type**: Static React SPA
- **Auth hydration**: via query params → `localStorage`

#### Backend (Railway – 3 Separate Services)
1. **API Service**
   - FastAPI server
   - Handles OAuth callbacks
   - Dashboard endpoints
   - Manual pipeline trigger
2. **Alert Dispatcher Service**
   - Runs every 5 minutes
   - Executes `alert_dispatcher.py`
   - Sends emails via SendGrid
   - Marks `email_sent = true` only on 202 response
3. **Daily Ingestion Cron Service**
   - Runs every day at 7:00 AM
   - Executes `daily_pipeline_cron.py`
   - Sequentially ingests all accounts

#### Database
- **Supabase (PostgreSQL 17.6)**
- **SSL enforced**
- **Connection pooling**: via `ThreadedConnectionPool`

---

## 🔐 OAuth 2.0 Architecture

**Model**: Server-Side Web Flow

> [!IMPORTANT]
> Tokens never reach the browser. All GSC API calls originate: **Backend → Google API**. Never: **Browser → Google API**.

### 🔄 7-Step Authentication Flow

1. **Initiation** (`GET /api/auth/google/url`)
   - Parameters: `access_type='offline'`, `prompt='consent'`
   - Scopes: `webmasters.readonly`, `openid`, `userinfo.email`
   - Guarantees refresh token on first login.

2. **Google Authorization**
   - User grants permission via hosted Google page.

3. **Token Exchange** (`GET /api/auth/google/callback?code=...`)
   - Backend calls `flow.fetch_token(code=...)`
   - Receives: `access_token`, `refresh_token`, `id_token`, `expiry` (All server-side).

4. **Identity + Scope Validation**
   - Verifies `id_token` and extracts verified email.
   - Confirms `webmasters.readonly` granted. If not → aborts.

5. **Persistence**
   - Upserts email into `accounts`.
   - Generates permanent `account_id` (UUID).
   - Stores tokens in `gsc_tokens`.
   - **Note**: Frontend never receives tokens.

6. **Frontend Handshake**
   - Redirect: `https://frontend/?account_id=...&email=...`
   - Frontend saves to `localStorage` and immediately wipes URL via `replaceState`.

7. **Self-Healing Token Refresh**
   - Every `GSCClient` instance checks `credentials.expired`.
   - If expired: Uses `refresh_token` to get new `access_token` and syncs to DB.
   - Supports: Daily cron, Alert dispatcher, Multi-worker safety.

---

## 🗄️ Database Architecture

- **Provider**: Supabase
- **Version**: PostgreSQL 17.6
- **Schema**: `public`

### Core Tables
| Table | Description |
| :--- | :--- |
| **`accounts`** | `id (UUID PK)`, `google_email (unique)`, `data_initialized (bool)` |
| **`gsc_tokens`** | `account_id (FK)`, `access_token`, `refresh_token`, `expiry` |
| **`websites`** | `id`, `base_domain`, `account_id` |
| **`properties`** | `id`, `site_url`, `property_type`, `account_id` |
| **`pipeline_runs`** | **Concurrency lock table**: `id`, `account_id`, `is_running`, `phase`, `progress`, `error`, `times` |

### Metrics Tables
- **`property_daily_metrics`**: `UNIQUE(property_id, date)`
- **`page_daily_metrics`**: `UNIQUE(property_id, page_url, date)`
- **`device_daily_metrics`**: `UNIQUE(property_id, device, date)`, `CHECK device IN ('desktop','mobile','tablet')`

### Alerts Layer
- **`alerts`**: `property_id`, `delta_pct`, `prev_7_impressions`, `last_7_impressions`, `email_sent`, `triggered_at`
- **`alert_recipients`**: `email`, `account_id`

### Ingestion Guarantees
All writes use `ON CONFLICT (...) DO UPDATE`.
- **Guarantees**: Idempotent, Safe restart, Handles GSC revisions, No duplicate rows.

---

## 🗄️ Database Schema & Setup

The authoritative database schema for GSC Radar is stored as a schema snapshot in:
`backend/database/current_schema.sql`

This file is a schema-only export from the production PostgreSQL instance.

### What This File Contains
- All table definitions, primary keys, and foreign keys.
- Unique constraints, check constraints, and indexes.
- Custom types and enum definitions.

### 🚀 Initializing a New Database
To provision a fresh PostgreSQL instance for GSC Radar:
```bash
psql "<NEW_DATABASE_URL>" < backend/database/current_schema.sql
```
This will create all required tables, constraints, and indexes, preparing the database for ingestion and runtime usage.

### 🔄 Schema Update Workflow
GSC Radar uses a **snapshot-based schema strategy** (not Alembic).
1. Apply changes directly to your database instance.
2. Regenerate the schema snapshot using `pg_dump`:
   ```bash
   pg_dump --schema-only --no-owner --no-privileges "<DATABASE_URL>" > backend/database/current_schema.sql
   ```
3. Commit the updated `current_schema.sql` file.

### 🔐 Environment Requirement
The backend requires a `DATABASE_URL` with SSL enabled:
`DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require`

---

## 🔄 Ingestion Pipeline Deep-Dive

The pipeline (`main.py`) is the core engine responsible for data synchronicity, analytical repair, and anomaly detection. It is designed for absolute **idempotency** and follows a "Sync-then-Analyze" pattern.

### 📅 Data Windows & Temporal Logic
Controlled by `src/config/date_windows.py`.
- **GSC Data Lag**: **2 Days** (`GSC_LAG_DAYS`). Google Search Console data stabilizes accurately after ~48 hours. The system treats `today - 2` as the latest valid date.
- **Analysis Window**: **14 Days** (`ANALYSIS_WINDOW_DAYS`). The system compares the current 7-day period against the preceding 7-day period.
- **Ingestion Buffer**: **16 Days** (`INGESTION_WINDOW_DAYS`). Covers the 14-day analysis requirement + 2-day stabilization lag.

### 🛠️ Ingestion Modes
The system automatically selects the ingestion window per property by checking data density in the database:

| Mode | Window | Trigger |
| :--- | :--- | :--- |
| **Daily Sync** | **1 Day** (`today - 2`) | DB already has a healthy 14-day history. Incremental update. |
| **Backfill** | **16 Days** | **Bootstrap**: First-time sync for a new account. <br> **Repair**: A "hole" or discontinuity is detected in recent history. |

### 🧬 Pipeline Components & Responsibilities
The pipeline executes sequentially per account to respect GSC API quotas (`main.py`):

1. **Discovery Phase**: `client.fetch_properties()` retrieves all verified sites and filters them (Impressions > 0).
2. **Ingestion Layer (Sequential)**:
   - **Property Metrics**: `property_metrics_daily_ingestor.py` - Sitewide clicks, imps, CTR, and position.
   - **Page Metrics**: `page_metrics_daily_ingestor.py` - Fetched via paginated GSC calls if exceeds >25000.
   - **Device Metrics**: `device_daily_metrics_ingestor.py` - Breakdown by Desktop, Mobile, and Tablet.
3. **Analysis Layer (Parallel)**:
   - **Sitewide Detection**: `alert_detector.py` - Computes the 7v7 delta for properties.
   - **Visibility Shifts**: `page_visibility_analyzer.py` - Set-logic processing of URL impressions.
   - **Device Shifts**: `device_visibility_analyzer.py` - Monitoring shifts in device share.

### 🚨 Thresholds & Classifications

#### Sitewide Anomalies
- **Property Alert**: **-10%** drop in impressions between current week and previous week.
- **Noise Floor**: Minimum **100 impressions** in the previous week window to trigger an alert.
- **Property Health Floor**: **500 total impressions** (combined 14d) required for a "Healthy/Warning/Critical" status. Properties below this are marked `insufficient_data`.

#### Visibility & Shifts
- **Significant Shift**: **±40%** change in impressions for a specific page or device.
- **New/Lost Pages**: Uses set intersection logic (`P_last` vs `P_prev`) to identify URLs that entered or exited the search index entirely within the 14-day window.

> [!NOTE]
> Every property ingestion is wrapped in a database transaction (`commit` only after aggregate, page, and device metrics succeed). If any part fails, the entire property sync rolls back to prevent partial data corruption.

---

---

## 📧 Alert Dispatcher (`alert_dispatcher.py`)

**Runs every 5 minutes.**

1. Fetch alerts where `email_sent = false`.
2. Generate HTML + Plain text.
3. Send via SendGrid API.
4. If status `202 Accepted` → mark `email_sent = true`.

---

## ⏰ Daily Pipeline Cron (`daily_pipeline_cron.py`)

**Runs at 7 AM.**

1. Fetch all accounts.
2. Attempt `db.start_pipeline_run(account_id)`.
3. If already running → skip.
4. Else run full pipeline.

**Exit Codes:**
- `0` → all success
- `1` → at least one failure
- `2` → skipped accounts (lock active)

Logs prefixed: `[CRON-PIPELINE]`

---

## 🌐 CORS Configuration

**Environment variable**: `ALLOWED_ORIGINS_STR=https://frontend-domain.com`

Parsed into `settings.ALLOWED_ORIGINS` and applied via FastAPI `CORSMiddleware`. Must include production and staging URLs.

---

## 🔧 Environment Variables

**Required in `backend/src/.env`:**

| Variable | Value / Example |
| :--- | :--- |
| `DATABASE_URL` | `postgresql://<user>:<password>@<host>:5432/postgres?sslmode=require` |
| `GOOGLE_CLIENT_ID` | `...` |
| `GOOGLE_CLIENT_SECRET` | `...` |
| `GOOGLE_REDIRECT_URI` | `https://api.domain.com/api/auth/google/callback` |
| `SENDGRID_API_KEY` | `SG....` |
| `SENDGRID_FROM_EMAIL` | `alerts@yourdomain.com` |
| `FRONTEND_URL` | `https://frontend.domain.com` |
| `ALLOWED_ORIGINS_STR` | `https://frontend.domain.com` |

---

## 🚀 Running in Production

### API Service (Railway)
`uvicorn src.api:app --host 0.0.0.0 --port $PORT`

### Alert Dispatcher Service
Railway Cron: `*/5 * * * *`
Command: `python -m src.alert_dispatcher`

### Daily Pipeline Cron
Railway Cron: `0 7 * * *`
Command: `python -m src.daily_pipeline_cron`

---

## 🛡️ Operational Guarantees
- Idempotent ingestion
- Concurrency lock via `pipeline_runs`
- Cron-safe & Restart-safe
- Multi-tenant isolation
- Token auto-refresh (No token exposure to client)
- No cross-account queries

---

## ⚠️ Failure Modes
- **Pipeline crash**: Safe restart.
- **Dispatcher crash**: Safe restart (unsent alerts persist).
- **OAuth token expiry**: Auto-refresh via refresh token.
- **DB outage**: Service fails cleanly; no partial writes.

---

## 📈 Implementation Realities
- No Redis / No Celery / No partitioning / No materialized views.
- Direct DB reads for dashboard.
- Sequential ingestion to respect GSC quotas.

---

## 🧭 Trust Boundary

```text
Browser → Backend → Google API
                ↓
              Database
```
**Tokens never leave backend.**

---

## Summary
Stateless, autonomous daily ingestion engine supporting server-side OAuth, multi-tenant isolation, and cron-based alerting.
