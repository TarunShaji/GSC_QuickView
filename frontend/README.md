# GSC Radar Frontend 🛰️

The GSC Radar frontend is a professional-grade React SPA designed for SEO performance monitoring. It provides a highly interactive dashboard for visualizing GSC metrics and managing anomaly alerts.

---

## 🏗️ Architecture & Flow

### 1. SPA Routing & Fallbacks
The frontend is built as a Single Page Application (SPA) using client-side routing.
- **Production Note**: When deploying to a CDN or static host (Vercel, Netlify, Cloudflare), you **must** configure the server to catch-all and redirect all requested paths to `index.html`. This ensures that deep links to property pages (e.g., `/property/<uuid>`) resolve correctly after a page refresh.

### 2. OAuth & Session Flow
Authentication is managed via an account-scoped query parameter model:
1. User clicks "Login with Google."
2. Backend initiates OAuth flow and redirects back to the frontend.
3. Frontend captures `account_id` and `email` from the URL.
4. These identifiers are persisted in `LocalStorage` and managed via `AuthContext.tsx`.
5. All subsequent API calls automatically inject the `account_id` as a query parameter.

---

## 🛠️ Configuration & Deployment

### Environment Injection
The frontend requires the backend API base URL at build time. This must be a professional, absolute URL (HTTPS recommended).

```env
# Create in frontend/.env
VITE_API_URL=https://api.yourdomain.com/api/v1
```

### Build Pipeline
1. **Target**: ESNext / Modern Browsers.
2. **Build Tool**: Vite.
3. **Command**: `npm run build`.
4. **Output**: `dist/` - This directory contains the static production artifacts.

---

## 📂 Data Ownership & Components

- **`src/components/DashboardSummary.tsx`**: High-level portfolio overview. Handles the global "Sync" trigger.
- **`src/components/PropertyDashboard.tsx`**: Deep-dive into specific properties with URL-level visibility tables.
- **`src/lib/apiClient.ts`**: Centralized, robust wrapper for all `fetch` requests with built-in error handling and account-id injection.
- **`src/types.ts`**: Strict TypeScript definitions aligned with backend model responses.

---

## � Known Architectural Limitations

- **State Persistence**: The application relies on URL parameters for initial session hydration and `LocalStorage` for continuity. There is no server-side session (JWT/Session Cookie) management in this architectural version.
- **Real-time Pipeline Status**: The "Pipeline in Progress" state is polled via the API. There is no WebSocket or Server-Sent Events (SSE) implementation.
- **Static Assets**: All branding assets (Radar icon, logos) are SVGs embedded in the component layer for zero-latency rendering.
