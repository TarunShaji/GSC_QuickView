# GSC Radar – Frontend 🛰️

The GSC Radar frontend is a React-based Single Page Application (SPA) designed for high-performance visualization of Google Search Console analytics. It is a strictly client-side, stateless consumer of the GSC Radar Backend.

---

## 🏗️ Technical Architecture

### 1. File Registry & Module Responsibilities

| File / Directory | Responsibility |
| :--- | :--- |
| **`App.tsx`** | **Core Router**: Manages the top-level application layout, routing logic (using React Router), and the main dashboard views. |
| **`AuthProvider.tsx`** | **Session Orchestrator**: Manages the `AuthContext` state. It handles the extraction of `account_id` from URL params and maintains the reactive session state. |
| **`AuthGate.tsx`** | **Security Interceptor**: A wrapper component that enforces authentication. It captures UUIDs from the onboarding redirect and commits them to `LocalStorage`. |
| **`api.ts`** | **Service Layer**: Contains typed fetch implementations for all backend entities (Properties, Pages, Alerts, Pipeline). |
| **`lib/apiClient.ts`** | **Base Client**: Configures the root `fetch` behavior, including base URL injection and automatic `account_id` parameter appending. |
| **`types.ts`** | **Contract Registry**: Centralized TypeScript interfaces that exactly mirror the backend's Pydantic models to ensure type safety. |
| **`components/`** | **View Layer**: Reusable UI components including `DashboardSummary`, `PropertyTable`, and `AlertList`. |
| **`App.css` / `index.css`** | **Design System**: Global Tailwind CSS imports and curated HSL-based dark mode tokens. |

---

## 🔄 Session & State Model

GSC Radar uses a **Stateless Hydration** model instead of traditional JWT or persistent Cookie-based login.

### The `account_id` Lifecycle
1.  **Handshake**: Upon successful Google login, the backend redirects to the frontend with `?account_id=UUID&email=user@domain.com`.
2.  **Hydration**: The `AuthGate` component intercepts these parameters, validates the UUID format, and saves them to `LocalStorage`.
3.  **Context Injection**: The `AuthProvider` reads from storage and populates the `AuthContext`.
4.  **Request Decoration**: Every call in `api.ts` passes through `apiClient.ts`, which silently appends the `account_id` to the query string:
    - `fetch('/api/properties')` -> `GET /api/properties?account_id=...`

---

## 🔌 Data Consumption Patterns

### Resilience & Polling
- **Pipeline Sync**: Because ingestion is long-running, the frontend uses a polling strategy on the `/api/pipeline/status` endpoint to update the UI progress bar.
- **Dynamic Sorting**: To maintain a zero-fluff frontend, sorting and filtering are performed on the Backend/DB. The frontend simply re-fetches with new parameters.

---

## 🚀 Deployment & Build

### Environment Configuration
Required in `frontend/.env`:
```env
# The absolute URL of your production backend API v1 root
VITE_API_URL=https://api.yourdomain.com/api/v1
```

### Production Workflow
```bash
npm install
npm run build
```
The resulting `dist/` directory is a purely static bundle.

### ⚠️ Critical: SPA Catch-All
Since this application uses client-side routing, your hosting provider (Vercel, Netlify, Nginx) **MUST** be configured with a catch-all redirect to `index.html`.
- **Nginx Example**: `try_files $uri /index.html;`
- **Vercel Example**: Defined in `vercel.json` rewrites.

---

## 🛡️ Implementation Realities (No-Fluff)

- **Execution**: Strictly stateless. Clearing your browser cache/LocalStorage is equivalent to a "Logout".
- **Design**: Built with a "Mobile-First" responsive layout using Tailwind's layout engine.
- **Dependencies**: Zero-dependency iconography using inline SVGs to minimize bundle size.
- **Limitations**: No built-in Multi-Factor Auth (MFA) or RBAC (scoping is locked at the `account_id` layer).
