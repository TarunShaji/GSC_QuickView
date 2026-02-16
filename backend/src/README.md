# GSC Radar - Backend API & Pipeline

This is the backend for the GSC Radar tool. It handles OAuth 2.0 authentication, Google Search Console data ingestion, visibility analysis, and automated email alerting.

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- PostgreSQL (or Supabase)
- Google Cloud Console Project with Search Console API enabled.

### 2. Environment Configuration
Create a `.env` file in the `src` directory with the following variables:
```env
# Database
DATABASE_URL=your_postgresql_connection_string

# Google OAuth
GOOGLE_CLIENT_ID=your_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_secret

# Alerting (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
```

### 3. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Run API Server
Start the FastAPI server from the `backend/` directory:
```bash
cd backend
python3 -m uvicorn src.api:app --reload
```
The API documentation will be available at `https://api.yourdomain.com/docs`.

## ⚙️ Background Processes

### Alert Dispatcher (Cron)
The tool uses a background dispatcher to send emails. It's recommended to run this via `cron` every 5 minutes:
```bash
*/5 * * * * cd /path/to/backend && /path/to/venv/bin/python3 src/alert_dispatcher.py >> logs/dispatcher.log 2>&1
```

## 📂 Core Modules

- `main.py`: The central pipeline runner (Sync -> Ingest -> Analyze).
- `auth_handler.py`: Manages OAuth flows and token persistence.
- `gsc_client.py`: Thread-safe wrapper for the Google GSC API.
- `db_persistence.py`: All SQL logic, strictly scoped by `account_id`.
- `alert_detector.py`: Logic for identifying significant impression drops.
- `alert_dispatcher.py`: Background worker for sending emails to account-level recipients.

## 📡 API Endpoints

- `GET /auth/google/url`: Get the Google Login URL.
- `POST /pipeline/run`: Trigger a data sync for an account.
- `GET /websites`: List grouped domains for the account.
- `GET /alert-recipients`: Manage email notification settings.
- `GET /properties/{id}/overview`: Get 7v7 performance deltas.
