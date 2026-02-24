/**
 * API CLIENT
 *
 * All requests to the backend automatically include the Supabase JWT token
 * as `Authorization: Bearer <token>`. The token is fetched from the Supabase
 * client on every call (it handles auto-refresh transparently).
 *
 * VITE_API_BASE_URL must be set in frontend/.env:
 *   VITE_API_BASE_URL=http://localhost:8000
 */
import { supabase } from '../lib/supabaseClient';

const RAW_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined;

if (!RAW_BASE) {
    console.warn('[API] VITE_API_BASE_URL is not defined. Falling back to same-origin.');
}

function normalizeBase(url?: string): string {
    return (url || '').replace(/\/+$/, '');
}

function buildUrl(path: string): string {
    const base = normalizeBase(RAW_BASE);
    let cleanedPath = path.trim();
    if (!cleanedPath.startsWith('/')) cleanedPath = '/' + cleanedPath;
    if (!cleanedPath.startsWith('/api')) cleanedPath = '/api' + cleanedPath;
    return `${base}${cleanedPath}`;
}

/**
 * Get the current Supabase access token for use in API requests.
 * Returns null if no session is active.
 */
async function getAccessToken(): Promise<string | null> {
    const { data: { session } } = await supabase.auth.getSession();
    return session?.access_token ?? null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = buildUrl(path);
    const token = await getAccessToken();

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string> || {}),
    };

    // Attach Bearer JWT for all requests
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }


    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
        // Session is invalid — sign out and redirect to app root
        await supabase.auth.signOut();
        window.location.href = '/';
        return null as any;
    }

    if (response.status === 403) {
        console.error('[API] 403 Forbidden: account does not belong to this user');
        throw new Error('Access denied: this account does not belong to your user.');
    }

    if (!response.ok) {
        const text = await response.text();
        console.error('[API ERROR]', response.status, text);
        throw new Error(`API Error ${response.status}: ${text}`);
    }

    return response.json();
}

export const apiClient = {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body?: unknown) =>
        request<T>(path, {
            method: 'POST',
            body: body ? JSON.stringify(body) : undefined,
        }),
    delete: <T>(path: string) =>
        request<T>(path, { method: 'DELETE' }),
};