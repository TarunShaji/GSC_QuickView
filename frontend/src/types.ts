/**
 * TypeScript types for GSC Quick View API responses
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
    phase: 'idle' | 'ingestion' | 'analysis' | 'completed' | 'failed';
    current_step: string | null;
    progress: PipelineProgress;
    completed_steps: string[];
    error: string | null;
    started_at: string | null;
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
    created_at: string;
    // New metric columns
    clicks_last_7: number;
    clicks_prev_7: number;
    ctr_last_7: number;
    ctr_prev_7: number;
    avg_position_last_7: number;
    avg_position_prev_7: number;
    // Health flags
    title_optimization: boolean;
    ranking_push: boolean;
    zero_click: boolean;
    low_ctr_pos_1_3: boolean;
    strong_gainer: boolean;
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
    delta: number;
    delta_pct: number;
    classification: string;
    created_at: string;
}

export interface DeviceVisibilityResponse {
    property_id: string;
    devices: Record<string, DeviceVisibility>;
}

export interface RecipientsResponse {
    account_id: string;
    recipients: string[];
}
