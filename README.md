# GSC Quick View

**Internal SEO monitoring and pre-client-call dashboard built on top of Google Search Console**

---

## Project Status: Phase 2 Complete

### Phase 2: Database Persistence ✅

**Implemented:**
- Google Search Console API authentication (OAuth 2.0)
- Property discovery via `sites.list`
- Permission filtering (Owner/Full User only)
- Base domain grouping logic
- **Database persistence to Supabase**
- **Idempotent inserts (safe to re-run)**
- **Explicit logging for debugging**
- Console output for validation

**NOT Implemented (future phases):**
- Metrics collection (clicks, impressions)
- Scheduling/cron jobs
- UI/dashboard
- Alerting

---

## Setup Instructions

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. OAuth Credentials

The OAuth client secret file is already present:
```
client_secret_693853074888-05e5d3qemmtdlonmhkl0hlk8lrr07r38.apps.googleusercontent.com.json
```

**Note:** This file is gitignored for security.

### 4. Configure Database Connection

Create `/src/.env` file with your Supabase connection string:

```bash
cd src
cp .env.example .env
```

Then edit `.env` and add your actual Supabase connection string:

```
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

**Note:** The `.env` file is gitignored to protect your credentials.

### 5. Run Phase 2

**Important:** Make sure virtual environment is activated first:

```bash
source venv/bin/activate
```

Then run:

```bash
cd src
python main.py
```

**First run:**
- Browser will open for Google OAuth consent
- Authorize the application
- Token will be saved to `token.json` for future use
- Properties will be fetched, grouped, and persisted to database

**Subsequent runs:**
- Uses saved token (auto-refreshes if expired)
- Safe to re-run (idempotent inserts - no duplicates)

---

## Phase 2 Output

The script will:
1. Authenticate with GSC API
2. Fetch all accessible properties
3. Filter to Owner/Full User permissions only
4. Group properties by base domain
5. **Persist websites and properties to Supabase**
6. Print grouped results and database summary to console

**Example output:**
```
Website: example.com
  Properties (3):
    • sc-domain:example.com [siteOwner]
    • https://example.com [siteOwner]
    • https://www.example.com [siteFullUser]

[INSERT] Website: example.com (id: abc-123)
[INSERT] Property: sc-domain:example.com (type: sc_domain, permission: siteOwner)
[INSERT] Property: https://example.com (type: url_prefix, permission: siteOwner)
[SKIP]   Property already exists: https://www.example.com

✓ Total websites in database: 24
✓ Total properties in database: 26
```

---

## Grouping Logic

**Base domain extraction:**
- `https://example.com` → `example.com`
- `https://www.example.com` → `example.com`
- `sc-domain:example.com` → `example.com`
- `https://blog.example.com` → `blog.example.com`
- `https://www.blog.example.com` → `blog.example.com`

**Rules:**
- `www` prefix is removed
- Ports and paths are ignored
- Multi-part TLDs handled correctly (e.g., `.co.uk`)
- Subdomains are separate websites
- Only groups properties user has access to (no inference)

---

## Project Structure

```
gsc_quickview/
├── src/
│   ├── gsc_client.py          # GSC API client
│   ├── property_grouper.py    # Grouping logic
│   ├── db_persistence.py      # Database persistence layer
│   ├── main.py                # Entry point
│   ├── test_grouping.py       # Validation tests
│   ├── .env                   # Database credentials (gitignored)
│   └── .env.example           # Example env file
├── venv/                      # Virtual environment (gitignored)
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
└── client_secret_*.json       # OAuth credentials (gitignored)
```

---

## Next Phases (Not Yet Implemented)

- **Phase 3:** Metrics collection (clicks, impressions, CTR, position)
- **Phase 4:** Daily automation
- **Phase 5:** Dashboard UI
- **Phase 6:** Alerting

---

## Security Notes

- OAuth tokens stored in `token.json` (gitignored)
- Client secrets gitignored
- Read-only GSC API access
- Multi-user support (each user authenticates separately)

---

## Developer Notes

**Data Philosophy:**
- Store FACTS only (raw daily metrics)
- Compute derived data at read-time (7d averages, deltas, alerts)
- Never overwrite historical data
- Append-only storage model

**Current Scope:**
- Phase 2 complete: discovery, grouping, and database persistence
- Websites and properties stored in Supabase
- Idempotent inserts (safe to re-run)
- No metrics collection yet
- No UI
