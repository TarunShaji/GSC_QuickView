# GSC Quick View - Frontend

This is the React-based frontend for the Google Search Console (GSC) Quick View tool. It provides a premium, responsive dashboard for viewing SEO analytics across multiple accounts.

## 🛠️ Tech Stack

- **Framework**: React 18 (Vite)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: React Context (AuthContext)
- **Icons**: Heroicons / Lucide (SVG-based)

## 🚀 Getting Started

### 1. Install Dependencies
Navigate to the frontend directory and install the required npm packages:
```bash
cd frontend
npm install
```

### 2. Configure Proxy
The frontend uses a proxy configured in `vite.config.ts` to route `/api/*` requests to the local backend server (usually `http://localhost:8000`). Ensure the backend is running before using the dashboard.

### 3. Run Development Server
```bash
npm run dev
```
The app will be available at `http://localhost:5173`.

## 📂 Project Structure

- `src/components/`: Modular React components (Dashboard, Alerts, Settings).
- `src/AuthContext.tsx`: Manages the account-level session (account_id, email).
- `src/api.ts`: Centralized API client using `fetch`.
- `src/types.ts`: TypeScript interfaces for backend responses.

## 🔑 Key Features

- **Multi-Account Dashboard**: Switch between different GSC accounts seamlessly.
- **Visual Analytics**: Interactive cards and tables showing impression deltas.
- **Alert Management**: A dedicated settings page to manage email recipients for SEO alerts.
- **Responsive Design**: Clean, dark-mode focused UI built with Tailwind CSS.
