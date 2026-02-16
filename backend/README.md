# GSC Radar Backend 🛰️

The GSC Radar backend is a high-performance FastAPI application designed for SEO data orchestration. It implements a robust, multi-phase ingestion and analysis pipeline with decoupled alert dispatching.

---

## 🏗️ Service Architecture

The backend consists of three primary, logically separated services that share a common state layer (PostgreSQL).

### 1. API Service (`src/api.py`)
- **Responsibility**: HTTP interface for the React dashboard.
- **Key Functions**: Account management, individual property data retrieval, and Google OAuth 2.0 flow control.
- **Failure Mode**: Process crash only affects UI availability and OAuth flows; ingestion and dispatching remain unaffected.

### 2. Ingestion Pipeline (`src/main.py`)
- **Responsibility**: Sequential data synchronization from GSC and anomaly detection.
- **Workflow**: 
    1. Synchronizes account-level property lists.
    2. Performs 14-day metrics ingestion (daily or backfill).
    3. Executes the `alert_detector` engine.
    4. Commits pending alerts to the database.
- **Concurrency**: Managed via `ThreadPoolExecutor` for multi-property ingestion.
- **Failure Mode**: Interruption during a run will mark the property as "unsafe" for the current cycle; the next run will automatically perform a "Repair Backfill."

### 3. Alert Dispatcher (`src/alert_dispatcher.py`)
- **Responsibility**: Transactional email delivery via SendGrid API.
- **Design**: Decoupled from the pipeline to ensure no blocking on external network latency.
- **Operational Model**: Scans `alerts` table for pending records, builds SaaS HTML payloads, and dispatches.
- **Failure Mode**: If SendGrid is down, the dispatcher logs the error and exits; alerts remain in the `email_sent = false` state and are retried in the next 5-minute cycle.

---

## 🛠️ Operational Configuration

The backend is configured via environment variables. For production, ensure `sslmode=require` for the database connection.

```env
# Database (PostgreSQL)
DATABASE_URL=posgresql://<user>:<password>@<host>:<port>/<dbname>?sslmode=require

# Google Cloud OAuth 2.0
GOOGLE_CLIENT_ID=<id>
GOOGLE_CLIENT_SECRET=<secret>
GOOGLE_REDIRECT_URI=https://api.yourdomain.com/api/v1/auth/google/callback

# SendGrid API (Transactional)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=alerts@your-verified-domain.com

# CORS / Auth Redirects
FRONTEND_URL=https://dashboard.yourdomain.com
```

---

## 📈 Data Persistence Model

- **Data Isolation**: All entries in `accounts`, `properties`, `metrics`, and `alerts` tables are keyed by `account_id` (UUID). There is no cross-account data leakage.
- **Idempotency**: Ingestion logic uses `ON CONFLICT (property_id, page_url, date) DO UPDATE` to ensure runs are safely retryable.
- **Time Windowing**: A canonical 14-day analysis window is enforced globally via `src/config/date_windows.py`.

---

## 🔍 Known Architectural Limitations

- **Process-Bound Tasks**: The system uses `FastAPI` background tasks and `ThreadPoolExecutor`. For enterprise-scale loads, a distributed task queue (e.g., Celery + Redis) would be required.
- **Auth Layer**: Stateless query-parameter based session management. No built-in RBAC or JWT signing at this stage.
- **Scaling**: While services are stateless, horizontal scaling of the Ingestion Pipeline requires external locking (e.g., Redis locks) to prevent race conditions on property ingestion.
