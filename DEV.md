# GSC Quick View - Developer Flow Documentation

## Technical Flow: User Actions → Frontend → Backend API Calls

This document provides a detailed technical walkthrough of how user interactions trigger API calls throughout the GSC Quick View application.

---

## Architecture Overview

```
User Browser (React)
    ↓
Frontend (Vite + React + TypeScript)
    ↓ /api/* proxy
Backend (FastAPI @ localhost:8000)
    ↓
Supabase PostgreSQL Database
```

**API Proxy Configuration:**
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- All `/api/*` requests are proxied to backend (configured in `vite.config.ts`)

---

## Flow 1: Initial Application Load

### User Action: Opens `http://localhost:5173` in browser

#### Step 1: Authentication Check

**Component:** `AuthGate.tsx`

**Trigger:** `useEffect()` on component mount

**API Call:**
```http
GET /api/auth/status
→ Proxied to: GET http://localhost:8000/auth/status
```

**Backend Handler:** `api.py:auth_status()`

**Backend Logic:**
```python
client = GSCClient()
return {"authenticated": client.is_authenticated()}
# Checks if token.json exists
```

**Response:**
```json
{
  "authenticated": true
}
```

**Frontend State Update:**
```typescript
setIsAuthenticated(true)
```

**UI Result:**
- If `authenticated: true` → Render children (PipelineGate)
- If `authenticated: false` → Show "Connect Google Search Console" button

---

### Step 2: Pipeline Status Check

**Component:** `PipelineGate.tsx`

**Trigger:** `useEffect()` on component mount (only if authenticated)

**API Call:**
```http
GET /api/pipeline/status
→ Proxied to: GET http://localhost:8000/pipeline/status
```

**Backend Handler:** `api.py:pipeline_status()`

**Backend Logic:**
```python
from main import PIPELINE_STATE
return PIPELINE_STATE
```

**Response (Idle State):**
```json
{
  "is_running": false,
  "phase": "idle",
  "current_step": null,
  "progress": {"current": 0, "total": 0},
  "completed_steps": [],
  "error": null,
  "started_at": null
}
```

**Frontend State Update:**
```typescript
setStatus(data)
```

**UI Result:**
- If `phase: "idle"` → Show "Run Pipeline" button
- If `phase: "completed"` → Render children (DataExplorer)
- If `is_running: true` → Show progress UI with polling

---

## Flow 2: User Not Authenticated

### User Action: Clicks "Connect Google Search Console"

**Component:** `AuthGate.tsx`

**Trigger:** `handleLogin()` function

**API Call:**
```http
POST /api/auth/login
→ Proxied to: POST http://localhost:8000/auth/login
```

**Backend Handler:** `api.py:auth_login()`

**Backend Logic:**
```python
client = GSCClient()
client.authenticate()  # Opens browser OAuth flow
return {"status": "authenticated"}
```

**Side Effect:**
- Opens browser window for Google OAuth
- User grants permissions
- Backend saves `token.json`

**Frontend Action After Response:**
```typescript
await api.auth.login()
await checkAuth()  // Re-check auth status
```

**Re-checks Authentication:**
```http
GET /api/auth/status
```

**Response:**
```json
{
  "authenticated": true
}
```

**UI Result:** Proceeds to PipelineGate

---

## Flow 3: Running the Pipeline

### User Action: Clicks "Run Pipeline" button

**Component:** `PipelineGate.tsx`

**Trigger:** `handleRunPipeline()` function

**API Call:**
```http
POST /api/pipeline/run
→ Proxied to: POST http://localhost:8000/pipeline/run
```

**Backend Handler:** `api.py:run_pipeline_endpoint()`

**Backend Logic:**
```python
# Check authentication
if not client.is_authenticated():
    raise HTTPException(status_code=401)

# Run pipeline synchronously (blocking)
run_pipeline()  # From main.py

return {"status": "completed"}
```

**Pipeline Execution (Backend):**
```
Phase 0: Setup
  - Auth check
  - Fetch GSC properties
  - Group by domain
  - Persist to DB

Phase 1: Sequential Ingestion
  - Property metrics (for each property)
  - Page metrics (for each property)
  - Device metrics (for each property)

Phase 2: Parallel Analysis
  - Page visibility analysis
  - Device visibility analysis

Phase 3: Alert Detection & Email Sending
  - Detect impression drops
  - Send SMTP emails

Pipeline Completed
```

**Frontend Polling (During Execution):**

**Trigger:** `useEffect()` when `status.is_running === true`

**Polling Interval:** Every 1500ms (1.5 seconds)

**API Call (Repeated):**
```http
GET /api/pipeline/status
```

**Response (During Ingestion):**
```json
{
  "is_running": true,
  "phase": "ingestion",
  "current_step": "Page metrics [12/26]: https://example.com/",
  "progress": {"current": 36, "total": 78},
  "completed_steps": ["auth_check", "properties_sync"],
  "error": null,
  "started_at": "2026-02-10T13:00:00.123456"
}
```

**Response (During Analysis):**
```json
{
  "is_running": true,
  "phase": "analysis",
  "current_step": "Running parallel visibility analysis",
  "progress": {"current": 78, "total": 78},
  "completed_steps": ["auth_check", "properties_sync", "ingestion"],
  "error": null,
  "started_at": "2026-02-10T13:00:00.123456"
}
```

**Response (Completed):**
```json
{
  "is_running": false,
  "phase": "completed",
  "current_step": "Pipeline completed",
  "progress": {"current": 78, "total": 78},
  "completed_steps": [
    "auth_check",
    "properties_sync",
    "ingestion",
    "page_visibility",
    "device_visibility",
    "alert_detection"
  ],
  "error": null,
  "started_at": "2026-02-10T13:00:00.123456"
}
```

**UI Updates:**
- Progress bar updates based on `progress.current / progress.total`
- Current step text updates
- Completed steps badges appear
- When `phase: "completed"` → Renders DataExplorer

---

## Flow 4: Viewing Analytics Data

### User Action: Pipeline completes, DataExplorer loads

**Component:** `DataExplorer.tsx`

#### Step 1: Fetch All Websites

**Trigger:** `useEffect()` on component mount

**API Call:**
```http
GET /api/websites
→ Proxied to: GET http://localhost:8000/websites
```

**Backend Handler:** `api.py:get_websites()`

**Backend Logic:**
```python
db = DatabasePersistence()
db.connect()
websites = db.fetch_all_websites()
return [serialize_row(w) for w in websites]
```

**SQL Query:**
```sql
SELECT 
    w.id,
    w.base_domain,
    w.created_at,
    COUNT(p.id) as property_count
FROM websites w
LEFT JOIN properties p ON w.id = p.website_id
GROUP BY w.id, w.base_domain, w.created_at
ORDER BY w.base_domain
```

**Response:**
```json
[
  {
    "id": "4b6d1f7e-9e17-4054-b5a6-f4456ccdba7e",
    "base_domain": "amouage.com",
    "created_at": "2026-02-05T14:09:50.813830+00:00",
    "property_count": 1
  },
  {
    "id": "a216fa45-4584-4708-8965-3a245cf6841b",
    "base_domain": "monq.com",
    "created_at": "2026-02-05T14:09:50.813830+00:00",
    "property_count": 1
  }
]
```

**Frontend State Update:**
```typescript
setWebsites(data)
setSelectedWebsite(data[0])  // Auto-select first
```

---

#### Step 2: Fetch Properties for Selected Website

**Trigger:** `useEffect()` when `selectedWebsite` changes

**API Call:**
```http
GET /api/websites/{website_id}/properties
→ Example: GET http://localhost:8000/websites/4b6d1f7e-9e17-4054-b5a6-f4456ccdba7e/properties
```

**Backend Handler:** `api.py:get_properties_by_website(website_id)`

**Backend Logic:**
```python
db = DatabasePersistence()
db.connect()
properties = db.fetch_properties_by_website(website_id)
return [serialize_row(p) for p in properties]
```

**SQL Query:**
```sql
SELECT 
    id,
    site_url,
    property_type,
    permission_level,
    created_at
FROM properties
WHERE website_id = %s
ORDER BY site_url
```

**Response:**
```json
[
  {
    "id": "436344b7-1ce0-449e-82e8-d164b359ecf0",
    "site_url": "https://amouage.com/",
    "property_type": "url_prefix",
    "permission_level": "siteFullUser",
    "created_at": "2026-02-05T14:09:50.813830+00:00"
  }
]
```

**Frontend State Update:**
```typescript
setProperties(data)
setSelectedProperty(data[0])  // Auto-select first
```

---

### User Action: Property selected, PropertyDashboard loads

**Component:** `PropertyDashboard.tsx`

**Trigger:** `useEffect()` when `property` prop changes

**Parallel API Calls (3 simultaneous requests):**

#### Call 1: Property Overview (7v7 Comparison)

```http
GET /api/properties/{property_id}/overview
→ Example: GET http://localhost:8000/properties/436344b7-1ce0-449e-82e8-d164b359ecf0/overview
```

**Backend Handler:** `api.py:get_property_overview(property_id)`

**Backend Logic:**
```python
db = DatabasePersistence()
db.connect()
metrics = db.fetch_property_daily_metrics_for_overview(property_id)

# Compute 7v7 comparison on-demand
today = datetime.now().date()
last_7 = {"clicks": 0, "impressions": 0, "days": 0}
prev_7 = {"clicks": 0, "impressions": 0, "days": 0}

for row in metrics:
    days_ago = (today - row['date']).days
    if 1 <= days_ago <= 7:
        last_7["clicks"] += row['clicks'] or 0
        last_7["impressions"] += row['impressions'] or 0
        last_7["days"] += 1
    elif 8 <= days_ago <= 14:
        prev_7["clicks"] += row['clicks'] or 0
        prev_7["impressions"] += row['impressions'] or 0
        prev_7["days"] += 1

# Calculate deltas
clicks_delta = last_7["clicks"] - prev_7["clicks"]
impressions_delta = last_7["impressions"] - prev_7["impressions"]
clicks_pct = (clicks_delta / prev_7["clicks"] * 100) if prev_7["clicks"] > 0 else 0
impressions_pct = (impressions_delta / prev_7["impressions"] * 100) if prev_7["impressions"] > 0 else 0

return {
    "property_id": property_id,
    "last_7_days": {...},
    "prev_7_days": {...},
    "deltas": {...}
}
```

**SQL Query:**
```sql
SELECT date, clicks, impressions, ctr, position
FROM property_daily_metrics
WHERE property_id = %s
ORDER BY date DESC
LIMIT 14
```

**Response:**
```json
{
  "property_id": "436344b7-1ce0-449e-82e8-d164b359ecf0",
  "last_7_days": {
    "clicks": 24129,
    "impressions": 520141,
    "days_with_data": 6
  },
  "prev_7_days": {
    "clicks": 29742,
    "impressions": 627055,
    "days_with_data": 7
  },
  "deltas": {
    "clicks": -5613,
    "impressions": -106914,
    "clicks_pct": -18.87,
    "impressions_pct": -17.05
  },
  "computed_at": "2026-02-10T13:16:41.795808"
}
```

---

#### Call 2: Page Visibility Analysis

```http
GET /api/properties/{property_id}/pages
→ Example: GET http://localhost:8000/properties/436344b7-1ce0-449e-82e8-d164b359ecf0/pages
```

**Backend Handler:** `api.py:get_page_visibility(property_id)`

**Backend Logic:**
```python
db = DatabasePersistence()
db.connect()
pages = db.fetch_page_visibility_analysis(property_id)

# Group by category
result = {"new": [], "lost": [], "drop": [], "gain": []}
for page in pages:
    category = page.get("category", "new")
    if category in result:
        result[category].append(serialize_row(page))

return {
    "property_id": property_id,
    "pages": result,
    "totals": {
        "new": len(result["new"]),
        "lost": len(result["lost"]),
        "drop": len(result["drop"]),
        "gain": len(result["gain"])
    }
}
```

**SQL Query:**
```sql
SELECT 
    category,
    page_url,
    impressions_last_7,
    impressions_prev_7,
    delta,
    delta_pct,
    created_at
FROM page_visibility_analysis
WHERE property_id = %s
ORDER BY category, delta DESC
```

**Response:**
```json
{
  "property_id": "436344b7-1ce0-449e-82e8-d164b359ecf0",
  "pages": {
    "new": [
      {
        "category": "new",
        "page_url": "https://amouage.com/en-us/products/new-product",
        "impressions_last_7": 150,
        "impressions_prev_7": 0,
        "delta": 150,
        "delta_pct": 0.0,
        "created_at": "2026-02-09T14:17:45.843905+00:00"
      }
    ],
    "lost": [...],
    "drop": [...],
    "gain": [...]
  },
  "totals": {
    "new": 202,
    "lost": 132,
    "drop": 49,
    "gain": 124
  }
}
```

---

#### Call 3: Device Visibility Analysis

```http
GET /api/properties/{property_id}/devices
→ Example: GET http://localhost:8000/properties/436344b7-1ce0-449e-82e8-d164b359ecf0/devices
```

**Backend Handler:** `api.py:get_device_visibility(property_id)`

**Backend Logic:**
```python
db = DatabasePersistence()
db.connect()
devices = db.fetch_device_visibility_analysis(property_id)

# Structure by device
result = {}
for device in devices:
    device_name = device.get("device", "unknown")
    result[device_name] = serialize_row(device)

return {
    "property_id": property_id,
    "devices": result
}
```

**SQL Query:**
```sql
SELECT 
    device,
    last_7_impressions,
    prev_7_impressions,
    delta,
    delta_pct,
    classification,
    created_at
FROM device_visibility_analysis
WHERE property_id = %s
ORDER BY device
```

**Response:**
```json
{
  "property_id": "436344b7-1ce0-449e-82e8-d164b359ecf0",
  "devices": {
    "desktop": {
      "device": "desktop",
      "last_7_impressions": 157047,
      "prev_7_impressions": 172387,
      "delta": 0,
      "delta_pct": -8.9,
      "classification": "flat",
      "created_at": "2026-02-09T14:17:45.794678+00:00"
    },
    "mobile": {
      "device": "mobile",
      "last_7_impressions": 446706,
      "prev_7_impressions": 450500,
      "delta": 0,
      "delta_pct": -0.8,
      "classification": "flat",
      "created_at": "2026-02-09T14:17:45.794678+00:00"
    },
    "tablet": {
      "device": "tablet",
      "last_7_impressions": 5782,
      "prev_7_impressions": 5487,
      "delta": 0,
      "delta_pct": 5.4,
      "classification": "flat",
      "created_at": "2026-02-09T14:17:45.794678+00:00"
    }
  }
}
```

**Frontend State Update:**
```typescript
const [overviewData, pagesData, devicesData] = await Promise.all([...])
setOverview(overviewData)
setPages(pagesData)
setDevices(devicesData)
```

**UI Result:** Dashboard renders with all 3 panels populated

---

## Flow 5: User Changes Property Selection

### User Action: Selects different property from dropdown

**Component:** `DataExplorer.tsx`

**Trigger:** `onChange` event on property `<select>`

**Frontend Action:**
```typescript
const property = properties.find((p) => p.id === e.target.value)
setSelectedProperty(property || null)
```

**Cascade Effect:**
- `PropertyDashboard` receives new `property` prop
- `useEffect()` in `PropertyDashboard` triggers
- **Repeats Flow 4** with new `property_id`
- Makes 3 parallel API calls again

---

## Flow 6: User Refreshes Data

### User Action: Clicks "Refresh Data" button (in header)

**Component:** `PipelineGate.tsx`

**Trigger:** `handleRunPipeline()` function

**API Call:**
```http
POST /api/pipeline/run
```

**Result:** **Repeats Flow 3** (entire pipeline execution)

---

## Summary: Complete API Call Sequence

### Initial Load (Authenticated, Pipeline Completed)
```
1. GET /api/auth/status
2. GET /api/pipeline/status
3. GET /api/websites
4. GET /api/websites/{website_id}/properties
5. GET /api/properties/{property_id}/overview
6. GET /api/properties/{property_id}/pages
7. GET /api/properties/{property_id}/devices
```

### Pipeline Execution
```
1. POST /api/pipeline/run (triggers backend pipeline)
2. GET /api/pipeline/status (polled every 1.5s until completed)
```

### Property Change
```
1. GET /api/properties/{new_property_id}/overview
2. GET /api/properties/{new_property_id}/pages
3. GET /api/properties/{new_property_id}/devices
```

---

## API Endpoint Reference

| Endpoint | Method | Purpose | Component |
|----------|--------|---------|-----------|
| `/auth/status` | GET | Check GSC authentication | AuthGate |
| `/auth/login` | POST | Trigger OAuth flow | AuthGate |
| `/pipeline/status` | GET | Get pipeline state | PipelineGate |
| `/pipeline/run` | POST | Execute pipeline | PipelineGate |
| `/websites` | GET | List all websites | DataExplorer |
| `/websites/{id}/properties` | GET | List properties for website | DataExplorer |
| `/properties/{id}/overview` | GET | Get 7v7 comparison | PropertyDashboard |
| `/properties/{id}/pages` | GET | Get page visibility | PropertyDashboard |
| `/properties/{id}/devices` | GET | Get device visibility | PropertyDashboard |

---

## State Management Flow

```
AuthGate State:
  isAuthenticated: boolean | null
  isLoading: boolean
  error: string | null

PipelineGate State:
  status: PipelineStatus | null
  error: string | null
  isStarting: boolean

DataExplorer State:
  websites: Website[]
  selectedWebsite: Website | null
  properties: Property[]
  selectedProperty: Property | null
  isLoading: boolean
  error: string | null

PropertyDashboard State:
  overview: PropertyOverview | null
  pages: PageVisibilityResponse | null
  devices: DeviceVisibilityResponse | null
  isLoading: boolean
```

---

## Error Handling

### Authentication Error (401)
```typescript
// Backend returns 401 if not authenticated
catch (err) {
  setError("Not authenticated with Google Search Console")
  // Shows login button
}
```

### Pipeline Error
```typescript
// Backend updates PIPELINE_STATE.error
{
  "phase": "failed",
  "error": "Database connection failed"
}
// Frontend shows error UI with retry button
```

### Data Fetch Error
```typescript
catch (err) {
  setError(err.message)
  // Shows error banner
}
```

---

## Performance Optimizations

1. **Parallel Requests:** PropertyDashboard fetches overview, pages, and devices simultaneously
2. **Polling Throttle:** Pipeline status polled every 1.5s (not too aggressive)
3. **Auto-selection:** First website/property auto-selected to minimize clicks
4. **Proxy Configuration:** Vite dev proxy eliminates CORS issues

---

## Development URLs

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8000
- **Backend Docs:** http://localhost:8000/docs (FastAPI auto-generated)

---

## Testing the Flow

### 1. Start Backend
```bash
cd /Users/tarunshaji/gsc_quickview/src
uvicorn api:app --reload
```

### 2. Start Frontend
```bash
cd /Users/tarunshaji/gsc_quickview/frontend
npm run dev
```

### 3. Monitor Network Tab
- Open browser DevTools → Network tab
- Filter by "Fetch/XHR"
- Watch API calls in real-time as you interact with the UI

### 4. Monitor Backend Logs
- Watch terminal running uvicorn
- See incoming requests and responses
- Check for errors

---

## Debugging Tips

### Frontend Not Connecting to Backend
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check proxy configuration
cat frontend/vite.config.ts
```

### Authentication Issues
```bash
# Check if token exists
ls -la src/token.json

# Test auth endpoint directly
curl http://localhost:8000/auth/status
```

### Pipeline Not Running
```bash
# Check pipeline status
curl http://localhost:8000/pipeline/status

# Run pipeline manually
curl -X POST http://localhost:8000/pipeline/run
```

---

**Last Updated:** 2026-02-10
