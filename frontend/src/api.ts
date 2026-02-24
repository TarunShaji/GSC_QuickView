/**
 * API client for GSC Radar backend
 * Multi-Account Aware
 */

import type {
    Account,
    PipelineStatus,
    Website,
    Property,
    PropertyOverview,
    PageVisibilityResponse,
    DeviceVisibilityResponse,
    RecipientsResponse,
    SubscriptionsResponse,
    DashboardSummaryResponse,
    Alert
} from './types';

import { apiClient } from './lib/apiClient';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const method = options?.method?.toUpperCase() || 'GET';

    if (method === 'POST') {
        const body = options?.body ? JSON.parse(options.body as string) : undefined;
        return apiClient.post<T>(url, body);
    }

    if (method === 'DELETE') {
        return apiClient.delete<T>(url);
    }

    return apiClient.get<T>(url);
}

export const api = {
    accounts: {
        getAll: () =>
            fetchJson<Account[]>(`/accounts`),
    },

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

    dashboard: {
        getSummary: (accountId: string) =>
            fetchJson<DashboardSummaryResponse>(`/dashboard-summary?account_id=${accountId}`),
    },

    properties: {
        getOverview: (accountId: string, propertyId: string) =>
            fetchJson<PropertyOverview>(`/properties/${propertyId}/overview?account_id=${accountId}`),
        getPages: (accountId: string, propertyId: string) =>
            fetchJson<PageVisibilityResponse>(`/properties/${propertyId}/pages?account_id=${accountId}`),
        getDevices: (accountId: string, propertyId: string) =>
            fetchJson<DeviceVisibilityResponse>(`/properties/${propertyId}/devices?account_id=${accountId}`),
        /**
         * Aggregated endpoint for PropertyDashboard.
         * Replaces Promise.all([getOverview, getPages, getDevices]) = 3 simultaneous requests.
         * Returns all three in 1 HTTP request, 1 DB connection.
         */
        getAllData: (accountId: string, propertyId: string) =>
            fetchJson<{
                overview: PropertyOverview;
                pages: PageVisibilityResponse;
                devices: DeviceVisibilityResponse;
            }>(`/properties/${propertyId}/all-data?account_id=${accountId}`),
    },

    alerts: {
        getAll: (accountId: string, limit: number = 20) =>
            fetchJson<Alert[]>(`/alerts?account_id=${accountId}&limit=${limit}`),
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
        // Property-level subscriptions
        getSubscriptions: (accountId: string, email: string) =>
            fetchJson<SubscriptionsResponse>(`/alert-subscriptions?account_id=${accountId}&email=${encodeURIComponent(email)}`),
        addSubscription: (accountId: string, email: string, propertyId: string) =>
            fetchJson<{ status: string }>(`/alert-subscriptions`, {
                method: 'POST',
                body: JSON.stringify({ account_id: accountId, email, property_id: propertyId })
            }),
        removeSubscription: (accountId: string, email: string, propertyId: string) =>
            fetchJson<{ status: string }>(`/alert-subscriptions?account_id=${accountId}&email=${encodeURIComponent(email)}&property_id=${propertyId}`, {
                method: 'DELETE'
            }),
        /**
         * Aggregated load for AlertConfig page.
         * Replaces: GET /websites → N×GET /websites/{id}/properties +
         *           GET /alert-recipients → M×GET /alert-subscriptions
         * With: exactly 1 HTTP request.
         */
        getAlertConfigData: (accountId: string) =>
            fetchJson<{
                account_id: string;
                websites: Array<{
                    base_domain: string;
                    properties: Array<{ id: string; site_url: string }>;
                }>;
                recipients: string[];
                subscriptions: Record<string, string[]>;
            }>(`/alert-config-data?account_id=${accountId}`),
    },
};

export default api;
