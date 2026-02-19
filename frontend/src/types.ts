/**
 * TypeScript types for GSC Radar API responses
 */

// Authentication
export interface AuthStatus {
    authenticated: boolean;
}

// Pipeline
export interface PipelineProgress {
    current: number;
    total: number;
}

export interface PipelineStatus {
    is_running: boolean;
    current_step: string | null;
    progress_current: number;
    progress_total: number;
    error: string | null;
    started_at: string | null;
    completed_at: string | null;
}

// Data Types
export interface Website {
    id: string;
    base_domain: string;
    created_at: string;
    property_count: number;
}

export interface Property {
    id: string;
    site_url: string;
    property_type: string;
    permission_level: string;
    created_at: string;
}

export interface PropertyOverview {
    property_id: string;
    property_name: string;
    initialized?: boolean;
    last_7_days: {
        clicks: number;
        impressions: number;
        ctr: number;
        avg_position: number;
        days_with_data: number;
    };
    prev_7_days: {
        clicks: number;
        impressions: number;
        ctr: number;
        avg_position: number;
        days_with_data: number;
    };
    deltas: {
        clicks: number;
        impressions: number;
        clicks_pct: number;
        impressions_pct: number;
        ctr: number;
        ctr_pct: number;
        avg_position: number;
    };
    computed_at: string;
}

export interface PageVisibilityItem {
    category: string;
    page_url: string;
    impressions_last_7: number;
    impressions_prev_7: number;
    delta: number;
    delta_pct: number;
    clicks_last_7: number;
    clicks_prev_7: number;
    clicks_delta: number;
    clicks_delta_pct: number;
}

export interface PageVisibilityResponse {
    property_id: string;
    pages: {
        new: PageVisibilityItem[];
        lost: PageVisibilityItem[];
        drop: PageVisibilityItem[];
        gain: PageVisibilityItem[];
    };
    totals: {
        new: number;
        lost: number;
        drop: number;
        gain: number;
    };
}

export interface DeviceVisibility {
    device: string;
    last_7_impressions: number;
    prev_7_impressions: number;
    impressions_delta_pct: number;
    last_7_clicks: number;
    prev_7_clicks: number;
    clicks_delta_pct: number;
    last_7_ctr: number;
    prev_7_ctr: number;
    ctr_delta_pct: number;
}

export interface DeviceVisibilityResponse {
    property_id: string;
    devices: Record<string, DeviceVisibility>;
}

export interface RecipientsResponse {
    account_id: string;
    recipients: string[];
}

export interface SubscriptionsResponse {
    account_id: string;
    email: string;
    property_ids: string[];
}

export interface PropertySummary {
    property_id: string;
    property_name: string;
    status: 'healthy' | 'warning' | 'critical' | 'insufficient_data';
    data_through: string;
    last_7: {
        impressions: number;
        clicks: number;
    };
    prev_7: {
        impressions: number;
        clicks: number;
    };
    delta_pct: {
        impressions: number;
        clicks: number;
    };
}

export interface WebsiteSummary {
    website_id: string;
    website_domain: string;
    properties: PropertySummary[];
}

export interface DashboardSummaryResponse {
    status?: 'not_initialized';
    message?: string;
    websites: WebsiteSummary[];
}
export interface Alert {
    id: string;
    property_id: string;
    site_url: string;
    alert_type: string;
    prev_7_impressions: number;
    last_7_impressions: number;
    delta_pct: number;
    triggered_at: string;
    email_sent: boolean;
}
