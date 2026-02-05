# GSC Quick View

**Internal SEO monitoring and pre-client-call dashboard built on top of Google Search Console**

---

## Project Status: Phase 1 Complete

### Phase 1: Property Discovery & Grouping ✅

**Implemented:**
- Google Search Console API authentication (OAuth 2.0)
- Property discovery via `sites.list`
- Permission filtering (Owner/Full User only)
- Base domain grouping logic
- Console output for validation

**NOT Implemented (future phases):**
- Database schema or writes
- Metrics collection
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

### 4. Run Phase 1

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

**Subsequent runs:**
- Uses saved token (auto-refreshes if expired)

---

## Phase 1 Output

The script will:
1. Authenticate with GSC API
2. Fetch all accessible properties
3. Filter to Owner/Full User permissions only
4. Group properties by base domain
5. Print grouped results to console

**Example output:**
```
Website: example.com
  Properties (3):
    • sc-domain:example.com [siteOwner]
    • https://example.com [siteOwner]
    • https://www.example.com [siteFullUser]

Website: blog.example.com
  Properties (1):
    • https://blog.example.com [siteOwner]
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
│   └── main.py                # Entry point
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore rules
├── README.md                  # This file
└── client_secret_*.json       # OAuth credentials (gitignored)
```

---

## Next Phases (Not Yet Implemented)

- **Phase 2:** Database schema design and storage
- **Phase 3:** Metrics collection (clicks, impressions)
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
- Phase 1 is discovery and grouping ONLY
- No database writes
- No metrics collection
- No UI
