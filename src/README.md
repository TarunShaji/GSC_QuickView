# GSC Quick View - Backend

FastAPI backend for Google Search Console analytics pipeline.

## Tech Stack

- **Python 3.10+**
- **FastAPI** for HTTP API
- **PostgreSQL** (Supabase)
- **Google Search Console API**

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Supabase credentials

# Run the server
uvicorn api:app --reload
```

## Environment Variables

Create `.env` in the `src/` folder:

```env
SUPABASE_DB_URL=postgresql://user:password@host:port/database
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/status` | Check GSC authentication |
| POST | `/auth/login` | Trigger Google OAuth |

### Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/pipeline/status` | Get pipeline execution status |
| POST | `/pipeline/run` | Execute the full pipeline |

### Data Exploration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/websites` | List all websites |
| GET | `/websites/{id}/properties` | Properties for website |
| GET | `/properties/{id}/overview` | 7v7 comparison (computed) |
| GET | `/properties/{id}/pages` | Page visibility analysis |
| GET | `/properties/{id}/devices` | Device visibility analysis |

## Pipeline Architecture

```
Phase 0 (Sequential): Auth + Property Sync
    ↓
Phase 1 (Sequential): Property/Page/Device Ingestion
    ↓                  (GSC API is NOT thread-safe)
Phase 2 (Parallel): Page/Device Visibility Analysis
    ↓                (DB operations are thread-safe)
Complete
```

## Database Schema

Key tables:
- `websites` - Base domains
- `properties` - GSC properties (sites)
- `property_daily_metrics` - Daily aggregates
- `page_daily_metrics` - Per-page metrics
- `device_daily_metrics` - Per-device metrics
- `page_visibility_analysis` - Computed page changes
- `device_visibility_analysis` - Computed device changes
