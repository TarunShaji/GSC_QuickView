# GSC Quick View

**Internal SEO monitoring and pre-client-call dashboard built on top of Google Search Console**

---

## Project Status: Phase 4 Complete

### Phase 4: Metrics Aggregation & 7v7 Comparison ✅

**Implemented:**
- Google Search Console API authentication (OAuth 2.0)
- Property discovery via `sites.list`
- Permission filtering (Owner/Full User only)
- Base domain grouping logic
- Database persistence to Supabase
- Search Analytics metrics ingestion
- Daily metrics storage (clicks, impressions, CTR, position)
- Property-scoped API requests
- **7-day vs 7-day comparison logic**
- **Deterministic 14-day data retrieval (ORDER BY date DESC LIMIT 14)**
- **Correct aggregation rules (SUM clicks/impressions, computed CTR, AVG position)**
- **Delta computation with percentage changes**
- **JSON output for frontend consumption**
- Idempotent inserts (safe to re-run)
- Extensive logging for debugging

**NOT Implemented (future phases):**
- Website-level aggregation (rollup across properties)
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

### 5. Run Phase 4

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
- Metrics will be fetched for last ~30 days and persisted
- **7v7 comparisons will be computed and saved to JSON**

**Subsequent runs:**
- Uses saved token (auto-refreshes if expired)
- Safe to re-run (idempotent inserts - no duplicates)
- Only new metrics are inserted (existing dates skipped)
- **Comparisons are recomputed with latest data**

---

## Phase 4 Output

The script will:
1. Authenticate with GSC API
2. Fetch all accessible properties
3. Filter to Owner/Full User permissions only
4. Group properties by base domain
5. Persist websites and properties to Supabase
6. Fetch Search Analytics metrics for all properties
7. Persist daily metrics to Supabase
8. **Compute 7-day vs 7-day comparisons for each property**
9. **Save comparison results to `outputs/property_7v7_comparisons.json`**
10. Print detailed results and summary to console

**Example console output:**
```
[PROPERTY] blackbrookcase.com
  Site URL: https://blackbrookcase.com/
  [DATA] Retrieved 14 days of metrics (2026-01-22 → 2026-02-04)

  [WINDOW] Last 7 days (2026-01-29 → 2026-02-04):
    Dates: 2026-02-04, 2026-02-03, 2026-02-02, 2026-02-01, 2026-01-31, 2026-01-30, 2026-01-29
    Clicks: 903 (sum)
    Impressions: 127,853 (sum)
    CTR: 0.0071 (903/127853)
    Avg Position: 10.94

  [WINDOW] Previous 7 days (2026-01-22 → 2026-01-28):
    Dates: 2026-01-28, 2026-01-27, 2026-01-26, 2026-01-25, 2026-01-24, 2026-01-23, 2026-01-22
    Clicks: 910 (sum)
    Impressions: 225,901 (sum)
    CTR: 0.0040 (910/225901)
    Avg Position: 9.94

  [DELTA] Comparison (Last 7 vs Previous 7):
    Clicks: -7 (-0.8%)
    Impressions: -98,048 (-43.4%)
    CTR: +0.0030 (+75.3%)
    Position: +1.00 (declined)

  Last updated: 2 days ago (2026-02-04)

================================================================================
AGGREGATION SUMMARY
================================================================================
✓ Properties analyzed: 26
✓ Properties with sufficient data (≥14 days): 26
================================================================================

[OUTPUT] JSON saved to: /Users/tarunshaji/gsc_quickview/outputs/property_7v7_comparisons.json
```

**JSON Output Structure:**
```json
{
  "generated_at": "2026-02-06T13:07:50.090821",
  "total_properties": 26,
  "properties_with_data": 26,
  "properties_insufficient_data": 0,
  "comparisons": [
    {
      "property_id": "...",
      "site_url": "https://example.com/",
      "base_domain": "example.com",
      "insufficient_data": false,
      "last_7_days": {
        "start_date": "2026-01-29",
        "end_date": "2026-02-04",
        "clicks": 1000,
        "impressions": 50000,
        "ctr": 0.02,
        "avg_position": 10.5
      },
      "previous_7_days": {
        "start_date": "2026-01-22",
        "end_date": "2026-01-28",
        "clicks": 900,
        "impressions": 45000,
        "ctr": 0.02,
        "avg_position": 11.2
      },
      "deltas": {
        "clicks": {"absolute": 100, "percentage": 11.1},
        "impressions": {"absolute": 5000, "percentage": 11.1},
        "ctr": {"absolute": 0.0, "percentage": 0.0},
        "position": {"absolute": -0.7, "improved": true}
      },
      "last_updated": {
        "date": "2026-02-04",
        "days_ago": 2
      }
    }
  ]
}
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
│   ├── gsc_client.py           # GSC API client
│   ├── property_grouper.py     # Grouping logic
│   ├── db_persistence.py       # Database persistence layer
│   ├── gsc_metrics_ingestor.py # Metrics ingestion
│   ├── metrics_aggregator.py   # 7v7 comparison logic
│   ├── main.py                 # Entry point
│   ├── test_grouping.py        # Validation tests
│   ├── .env                    # Database credentials (gitignored)
│   └── .env.example            # Example env file
├── outputs/                    # Generated JSON outputs
│   └── property_7v7_comparisons.json
├── venv/                       # Virtual environment (gitignored)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
└── client_secret_*.json        # OAuth credentials (gitignored)
```

---

## Next Phases (Not Yet Implemented)

- **Phase 5:** Website-level aggregation (rollup across properties)
- **Phase 6:** Daily automation (cron jobs)
- **Phase 7:** Dashboard UI
- **Phase 8:** Alerting

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
- Compute derived data at read-time (7v7 comparisons, deltas)
- Never overwrite historical data
- Append-only storage model

**Phase 4 Implementation:**
- Deterministic 14-day retrieval: `ORDER BY date DESC LIMIT 14`
- Window splitting: Last 7 days [0:7], Previous 7 days [7:14]
- Correct aggregation: SUM clicks/impressions, computed CTR (NOT AVG), AVG position
- Delta computation: absolute + percentage changes
- Insufficient data handling: Require ≥14 days, mark as insufficient otherwise
- JSON output: Frontend-ready structure in `outputs/property_7v7_comparisons.json`

**Current Scope:**
- Phase 4 complete: discovery, grouping, persistence, metrics ingestion, and 7v7 comparisons
- Websites, properties, and daily metrics stored in Supabase
- Metrics fetched for last ~30 days (today - 32 to today - 2)
- Comparisons computed for latest 14 days (7v7 split)
- Idempotent inserts (safe to re-run)
- No website-level aggregation yet
- No UI
