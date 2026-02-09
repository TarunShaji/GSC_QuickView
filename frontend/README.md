# GSC Quick View - Frontend

Modern React frontend for Google Search Console analytics.

## Tech Stack

- **React 18** + TypeScript
- **Vite** for fast development
- **Tailwind CSS** for styling

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server (localhost:5173)
npm run dev
```

## Project Structure

```
src/
├── components/
│   ├── AuthGate.tsx         # Google OAuth authentication
│   ├── PipelineGate.tsx     # Pipeline execution & progress
│   ├── DataExplorer.tsx     # Website/property selectors
│   └── PropertyDashboard.tsx # Analytics panels
├── api.ts                   # API client
├── types.ts                 # TypeScript types
├── App.tsx                  # Root component
└── index.css                # Tailwind imports
```

## Component Flow

```
AuthGate
  └─ PipelineGate
       └─ DataExplorer
            └─ PropertyDashboard
```

## API Endpoints Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/status` | Check authentication |
| POST | `/auth/login` | Trigger Google OAuth |
| GET | `/pipeline/status` | Poll pipeline progress |
| POST | `/pipeline/run` | Start pipeline |
| GET | `/websites` | List all websites |
| GET | `/websites/{id}/properties` | Properties for website |
| GET | `/properties/{id}/overview` | 7v7 comparison |
| GET | `/properties/{id}/pages` | Page visibility |
| GET | `/properties/{id}/devices` | Device visibility |

## Development

The dev server proxies `/api/*` to `http://localhost:8000` (backend).

Make sure the backend is running:
```bash
cd ../src
uvicorn api:app --reload
```
