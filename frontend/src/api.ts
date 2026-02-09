/**
 * API client for GSC Quick View backend
 * 
 * All requests go through /api proxy (configured in vite.config.ts)
 * which forwards to http://localhost:8000
 */

import type {
    AuthStatus,
    PipelineStatus,
    Website,
    Property,
    PropertyOverview,
    PageVisibilityResponse,
    DeviceVisibilityResponse
} from './types';

const API_BASE = '/api';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${url}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
        ...options,
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(error || `Request failed: ${response.status}`);
    }

    return response.json();
}

// Authentication
export const api = {
    auth: {
        getStatus: () => fetchJson<AuthStatus>('/auth/status'),
        login: () => fetchJson<{ status: string }>('/auth/login', { method: 'POST' }),
    },

    pipeline: {
        getStatus: () => fetchJson<PipelineStatus>('/pipeline/status'),
        run: () => fetchJson<{ status: string }>('/pipeline/run', { method: 'POST' }),
    },

    websites: {
        getAll: () => fetchJson<Website[]>('/websites'),
        getProperties: (websiteId: string) =>
            fetchJson<Property[]>(`/websites/${websiteId}/properties`),
    },

    properties: {
        getOverview: (propertyId: string) =>
            fetchJson<PropertyOverview>(`/properties/${propertyId}/overview`),
        getPages: (propertyId: string) =>
            fetchJson<PageVisibilityResponse>(`/properties/${propertyId}/pages`),
        getDevices: (propertyId: string) =>
            fetchJson<DeviceVisibilityResponse>(`/properties/${propertyId}/devices`),
    },
};

export default api;
