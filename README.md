# GSC Quick View

**Production-grade Google Search Console analytics tool**

A modern SEO analytics dashboard that ingests GSC data, computes visibility changes, and displays actionable insights.

![Architecture](docs/architecture.png)

## Features

- 📊 **7-Day Comparisons** - Track clicks/impressions week-over-week
- 📱 **Device Analysis** - Mobile, desktop, tablet performance
- 📄 **Page Visibility** - New pages, lost pages, gainers, droppers
- 🔄 **Background Pipeline** - Reliable sequential ingestion + parallel analysis
- 🎨 **Modern UI** - Clean React dashboard with dark theme

## Project Structure

```
gsc_quickview/
├── src/                     # Python backend
│   ├── api.py               # FastAPI server
│   ├── main.py              # Pipeline orchestration
│   ├── db_persistence.py    # Database operations
│   └── ...                  # Ingestors & analyzers
├── frontend/                # React frontend
│   ├── src/components/      # UI components
│   └── ...
├── backfills/               # Data backfill scripts
└── outputs/                 # Debug JSON outputs
```

## Quick Start

### 1. Backend

```bash
cd src
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

# Set up .env with SUPABASE_DB_URL
uvicorn api:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Open App

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

## Tech Stack

**Backend:**
- Python 3.10+
- FastAPI
- PostgreSQL (Supabase)
- Google Search Console API

**Frontend:**
- React 18 + TypeScript
- Vite
- Tailwind CSS

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   React Frontend │────▶│  FastAPI Backend │
│   (port 5173)    │     │   (port 8000)    │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐           ┌───────▼───────┐
              │   GSC API  │           │   Supabase    │
              │  (Google)  │           │  (PostgreSQL) │
              └───────────┘           └───────────────┘
```

## License

MIT
