/**
 * API client for GSC Quick View backend
 * Multi-Account Aware
 */

import type {
    PipelineStatus,
    Website,
    Property,
    PropertyOverview,
    PageVisibilityResponse,
    DeviceVisibilityResponse,
    RecipientsResponse
} from './types';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
        headers: {
            'Content-Type': 'application/json',
            ...(options?.headers || {}),
        },
        ...options,
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(error || `Request failed: ${response.status}`);
    }

    return response.json();
}

export const api = {
    auth: {
        // New Web-based OAuth methods
        // Backend now controls the redirect_uri hardcoded to its own callback
        getAuthUrl: () =>
            fetchJson<{ url: string }>(`/auth/google/url`),

        // handleCallback removed: backend now handles the redirect directly 
        // and sends user back to frontend with account info in URL params.
    },

    pipeline: {
        getStatus: (accountId: string) =>
            fetchJson<PipelineStatus>(`/pipeline/status?account_id=${accountId}`),
        run: (accountId: string) =>
            fetchJson<{ status: string }>(`/pipeline/run?account_id=${accountId}`, { method: 'POST' }),
    },

    websites: {
        getAll: (accountId: string) =>
            fetchJson<Website[]>(`/websites?account_id=${accountId}`),
        getProperties: (accountId: string, websiteId: string) =>
            fetchJson<Property[]>(`/websites/${websiteId}/properties?account_id=${accountId}`),
    },

    properties: {
        getOverview: (accountId: string, propertyId: string) =>
            fetchJson<PropertyOverview>(`/properties/${propertyId}/overview?account_id=${accountId}`),
        getPages: (accountId: string, propertyId: string) =>
            fetchJson<PageVisibilityResponse>(`/properties/${propertyId}/pages?account_id=${accountId}`),
        getDevices: (accountId: string, propertyId: string) =>
            fetchJson<DeviceVisibilityResponse>(`/properties/${propertyId}/devices?account_id=${accountId}`),
    },

    alerts: {
        getAll: (accountId: string, limit: number = 20) =>
            fetchJson<any[]>(`/alerts?account_id=${accountId}&limit=${limit}`),
        getRecipients: (accountId: string) =>
            fetchJson<RecipientsResponse>(`/alert-recipients?account_id=${accountId}`),
        addRecipient: (accountId: string, email: string) =>
            fetchJson<{ status: string }>(`/alert-recipients`, {
                method: 'POST',
                body: JSON.stringify({ account_id: accountId, email })
            }),
        removeRecipient: (accountId: string, email: string) =>
            fetchJson<{ status: string }>(`/alert-recipients?account_id=${accountId}&email=${email}`, {
                method: 'DELETE'
            }),
    },
};

export default api;
