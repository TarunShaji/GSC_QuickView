# Developer Documentation: GSC Quick View

Welcome to the technical guide for the GSC Quick View tool. This document explains the system architecture, data flows, and internal logic to help you understand how the tool works "under the hood".

## 🏗️ System Architecture

The system is built with a decoupled architecture to ensure scalability and multi-account safety:

1.  **Frontend**: React + Vite + TypeScript + Tailwind CSS.
2.  **Backend API**: FastAPI (Python) serving as the orchestration layer.
3.  **Database**: PostgreSQL (Supabase) for long-term storage of metrics, tokens, and alerts.
4.  **Worker Logic**: A Python-based ingestion and analysis pipeline.
5.  **Alert Dispatcher**: A standalone cron-driven background process for email notifications.

---

## 🔐 Multi-Account OAuth 2.0 Flow

This is the most critical workflow as it enables secure access to Google Search Console data.

### Step-by-Step Flow:
1.  **Initiation**: The user clicks "Login with Google" on the Frontend.
2.  **Auth URL**: Frontend calls `GET /api/auth/google/url`. Backend uses `GoogleAuthHandler` to generate a Google Authorization URL with the required scopes (`searchconsole.readonly`, `userinfo.email`).
3.  **Google Interaction**: User is redirected to Google, signs in, and approves permissions.
4.  **Callback**: Google redirects the user back to the Backend's callback endpoint: `http://localhost:8000/auth/google/callback?code=...`.
5.  **Code Exchange**: 
    *   `auth_handler.py` takes the temporary `code` and exchanges it with Google for permanent **Access** and **Refresh** tokens.
    *   It parses the `id_token` to get the user's Google email.
6.  **Account Registration**: 
    *   The backend checks the `accounts` table. If the email is new, it creates a new `account_id` (UUID).
    *   Tokens are stored securely in the `gsc_tokens` table, linked to the `account_id`.
7.  **frontend Redirect**: The backend redirects the browser back to the Frontend: `http://localhost:5173/?account_id={uuid}&email={email}`.
8.  **Session Start**: The Frontend `AuthGate` intercepts these URL params, saves them to `localStorage`, and initializes the `AuthContext`.

---

## 🚀 Data Pipeline Workflow

Once authenticated, the user can trigger a "Pipeline Run".

### Phase 0: Property Sync
The `GSCClient` fetches the list of all properties the user has access to. These are grouped by base domain (e.g., `example.com`) and stored in the `websites` and `properties` tables.

### Phase 1: Ingestion
The pipeline runs sequentially for each property to avoid rate limiting:
1.  **Daily Ingestor**: Fetches the last 3 days of metrics for Property, Page, and Device levels.
2.  **Backfill**: If a property is new or has gaps, the system automatically fetches 16 days of historical data to ensure immediate 7v7 analysis availability.

### Phase 2: Analysis
Once data is ingested, the Analyzers run in parallel using a `ThreadPoolExecutor`:
*   **PageVisibilityAnalyzer**: Compares the last 7 days of impressions against the previous 7 days per URL.
*   **DeviceVisibilityAnalyzer**: Checks performance shifts across Mobile, Desktop, and Tablet.
*   **Classification**: Changes are categorized as `significant_drop`, `significant_gain`, or `flat` based on a ±10% threshold.

---

## 🔔 Alerting System

The alerting system is split into two parts: **Detection** and **Dispatching**.

### 1. Detection (Inside the Pipeline)
At the end of a pipeline run, `alert_detector.py` scans the latest 7v7 results. If a property-level impression drop exceeds 10%, a row is inserted into the `alerts` table with `email_sent = false`.

### 2. Dispatching (Standalone Cron)
The `alert_dispatcher.py` runs every 5 minutes (configured via Crontab):
1.  **Multi-Account Sweep**: It fetches all accounts from the database.
2.  **Pending Alerts**: For each account, it looks for alerts where `email_sent = false`.
3.  **Recipients**: It pulls email addresses from the `alert_recipients` table (managed by the user in the "Settings" tab).
4.  **Delivery**: It summarizes the alerts into a HTML email and sends them via SMTP.
5.  **Completion**: Once sent, it marks the alert as `email_sent = true`.

---

## 📊 Database Schema Highlights

*   **`accounts`**: Primary user records.
*   **`gsc_tokens`**: Encrypted-at-rest (or at least scoped) OAuth credentials.
*   **`websites` / `properties`**: The hierarchy of Search Console assets.
*   **`property_daily_metrics`**: Aggregate clicks/impressions.
*   **`page_daily_metrics`**: Granular performance data for every URL.
*   **`alerts`**: History of all detected performance drops.
*   **`alert_recipients`**: Mapping of emails to receive alerts per account.
