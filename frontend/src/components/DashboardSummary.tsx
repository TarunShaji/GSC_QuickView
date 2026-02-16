import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import PipelineBanner from './PipelineBanner';
import type { DashboardSummaryResponse, WebsiteSummary, PropertySummary, PipelineStatus } from '../types';

export default function DashboardSummary() {
    const { accountId } = useAuth();
    const navigate = useNavigate();
    const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);

    const fetchSummary = useCallback(async (isInitial = false) => {
        if (!accountId) return;
        if (isInitial) setIsLoading(true);
        setError(null);
        try {
            const data = await api.dashboard.getSummary(accountId);
            setSummary(data);

            // If not initialized, also fetch pipeline status once
            if (data.status === 'not_initialized') {
                const pStatus = await api.pipeline.getStatus(accountId);
                setPipelineStatus(pStatus);
            }

            // Summary fetched
        } catch (err) {
            console.error('Failed to fetch dashboard summary:', err);
            setError('Failed to load dashboard data');
        } finally {
            if (isInitial) setIsLoading(false);
        }
    }, [accountId]);

    const fetchPipelineStatus = useCallback(async () => {
        if (!accountId) return;
        try {
            const data = await api.pipeline.getStatus(accountId);
            setPipelineStatus(data);

            // If pipeline just finished, refresh summary
            if (pipelineStatus?.is_running && !data.is_running && !data.error) {
                fetchSummary();
            }
        } catch (err) {
            console.error('Failed to fetch pipeline status:', err);
        }
    }, [accountId, pipelineStatus, fetchSummary]);

    useEffect(() => {
        fetchSummary(true);
    }, [fetchSummary]);

    // Poll pipeline status if not initialized
    useEffect(() => {
        if (!accountId || summary?.status !== 'not_initialized') return;

        const interval = setInterval(fetchPipelineStatus, 5000);
        return () => clearInterval(interval);
    }, [accountId, summary, fetchPipelineStatus]);

    const handleRunPipeline = async () => {
        if (!accountId) return;
        setIsStarting(true);
        setError(null);
        try {
            await api.pipeline.run(accountId);
            // The banner will pick up the 'is_running' state automatically
        } catch (err: any) {
            if (err.response?.status === 409) {
                // Already running, ignore
            } else {
                setError(err instanceof Error ? err.message : 'Failed to start pipeline');
            }
        } finally {
            setIsStarting(false);
        }
    };



    const getStatusBadge = (status: PropertySummary['status']) => {
        const badges = {
            healthy: { icon: '🟢', text: 'Healthy', color: 'text-green-700 bg-green-50 border-green-200' },
            warning: { icon: '🟡', text: 'Warning', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
            critical: { icon: '🔴', text: 'Critical', color: 'text-red-700 bg-red-50 border-red-200' },
            insufficient_data: { icon: '⚪', text: 'No Data', color: 'text-gray-600 bg-gray-50 border-gray-200' }
        };
        const badge = badges[status];
        return (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${badge.color}`}>
                <span>{badge.icon}</span>
                <span>{badge.text}</span>
            </span>
        );
    };

    const formatNumber = (num: number): string => {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)} M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)} K`;
        return num.toString();
    };

    const formatDelta = (pct: number): string => {
        const sign = pct > 0 ? '+' : '';
        return `${sign}${pct.toFixed(1)}% `;
    };

    const formatDate = (dateStr: string): string => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const getDeltaColor = (delta: number, metric: 'impressions' | 'clicks' | 'ctr' | 'position'): string => {
        if (metric === 'position') {
            // For position, negative is better (lower rank)
            return delta < 0 ? 'text-green-600' : delta > 0 ? 'text-red-600' : 'text-gray-500';
        }
        // For other metrics, positive is better
        return delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-500';
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    // Handle uninitialized state
    if (summary?.status === 'not_initialized') {
        return (
            <>
                <div className="space-y-6">
                    <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-6">
                        <div className="flex items-center gap-6">
                            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Property Overview</h1>
                            <nav className="flex gap-1">
                                <button className="px-4 py-2 text-sm font-semibold text-gray-900 border-b-2 border-gray-900">
                                    Dashboard
                                </button>
                                <button
                                    onClick={() => navigate('/alerts')}
                                    className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 rounded-md transition-colors"
                                >
                                    Alerts
                                </button>
                                <button
                                    onClick={() => navigate('/settings')}
                                    className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 rounded-md transition-colors"
                                >
                                    Settings
                                </button>
                            </nav>
                        </div>
                    </header>

                    <PipelineBanner />

                    <div className="text-center py-20">
                        <div className="bg-white rounded-lg p-12 max-w-xl mx-auto border border-gray-200 shadow-sm">
                            <div className={`text-6xl mb-8 ${pipelineStatus?.is_running ? 'animate-spin' : 'animate-pulse'}`}>
                                {pipelineStatus?.is_running ? '🌀' : '⚙️'}
                            </div>
                            <h2 className="text-2xl font-bold text-gray-900 mb-4 tracking-tight">
                                {pipelineStatus?.is_running ? 'Sync in Progress' : 'Welcome to GSC Radar'}
                            </h2>
                            <p className="text-base text-gray-500 mb-10 leading-relaxed font-medium">
                                {pipelineStatus?.is_running
                                    ? `Step: ${pipelineStatus.current_step}...`
                                    : summary.message || 'Connected to Search Console. Press start to fetch and analyze your property data.'}
                            </p>

                            {error && (
                                <div className="mb-6 px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs font-bold uppercase tracking-widest">
                                    {error}
                                </div>
                            )}

                            {pipelineStatus?.is_running ? (
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center mb-1.5">
                                        <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest leading-relaxed">System Progress</span>
                                        <span className="text-xs font-black text-gray-900">
                                            {pipelineStatus.progress_total > 0
                                                ? Math.round((pipelineStatus.progress_current / pipelineStatus.progress_total) * 100)
                                                : 0}%
                                        </span>
                                    </div>
                                    <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden border border-gray-200">
                                        <div
                                            className="h-full bg-gray-900 transition-all duration-1000 ease-out"
                                            style={{
                                                width: `${pipelineStatus.progress_total > 0
                                                    ? (pipelineStatus.progress_current / pipelineStatus.progress_total) * 100
                                                    : 0
                                                    }% `
                                            }}
                                        />
                                    </div>
                                    <button
                                        disabled
                                        className="w-full bg-gray-100 text-gray-400 font-bold py-4 px-8 rounded-lg flex items-center justify-center gap-3 text-xs uppercase tracking-[0.2em]"
                                    >
                                        Pipeline Running...
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={handleRunPipeline}
                                    disabled={isStarting}
                                    className="w-full bg-gray-900 hover:bg-black disabled:bg-gray-400 text-white font-bold py-4 px-8 rounded-lg transition-all flex items-center justify-center gap-3 shadow-sm text-xs uppercase tracking-[0.2em]"
                                >
                                    {isStarting ? (
                                        <>
                                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white/20 border-t-white"></div>
                                            Initiating Sync...
                                        </>
                                    ) : (
                                        <>
                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            Run Initial Pipeline
                                        </>
                                    )}
                                </button>
                            )}

                            <p className="mt-8 text-gray-400 text-[10px] font-bold uppercase tracking-widest leading-relaxed">
                                This will sync your properties and analyze the last 14 days of data.
                            </p>
                        </div>
                    </div>
                </div>
            </>
        );
    }

    if (!summary || summary.websites.length === 0) {
        return (
            <div className="text-center py-12">
                <p className="text-slate-400">No properties found. Run the pipeline to fetch data.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-6">
                <div className="flex items-center gap-6">
                    <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Property Overview</h1>
                    <nav className="flex gap-1">
                        <button className="px-4 py-2 text-sm font-semibold text-gray-900 border-b-2 border-gray-900">
                            Dashboard
                        </button>
                        <button
                            onClick={() => navigate('/alerts')}
                            className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 rounded-md transition-colors"
                        >
                            Alerts
                        </button>
                        <button
                            onClick={() => navigate('/settings')}
                            className="px-4 py-2 text-sm font-medium text-gray-500 hover:text-gray-900 rounded-md transition-colors"
                        >
                            Settings
                        </button>
                    </nav>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={handleRunPipeline}
                        disabled={isStarting}
                        className="inline-flex items-center gap-2 bg-gray-900 hover:bg-gray-800 text-white text-sm font-medium py-2 px-4 rounded-md transition-all shadow-sm"
                    >
                        {isStarting ? (
                            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white/30 border-t-white"></div>
                        ) : (
                            <svg className="w-4 h-4 transition-transform group-hover:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                        )}
                        Refresh Data
                    </button>
                </div>
            </header>

            <PipelineBanner onSuccess={fetchSummary} />

            <div className="space-y-4">
                {summary.websites.map((website: WebsiteSummary) => (
                    <div key={website.website_id} className="bg-white rounded-lg overflow-hidden border border-gray-200 shadow-sm">
                        {/* Website Header */}
                        <div className="w-full px-6 py-4 flex items-center justify-between border-b border-gray-100 bg-gray-50/30">
                            <div className="flex items-center gap-3">
                                <h2 className="text-sm font-bold text-gray-900 uppercase tracking-wider leading-relaxed">{website.website_domain}</h2>
                                <span className="text-xs text-gray-500 font-medium tracking-tight">
                                    {website.properties.length} {website.properties.length === 1 ? 'property' : 'properties'}
                                </span>
                            </div>
                        </div>

                        {/* Property Table */}
                        <div className="border-t border-gray-200">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">
                                                Property
                                            </th>
                                            <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">
                                                Status
                                            </th>
                                            <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">
                                                Imps (7D)
                                            </th>
                                            <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">
                                                Clicks (7D)
                                            </th>
                                            <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">
                                                Updated
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100">
                                        {website.properties.map((property: PropertySummary) => (
                                            <React.Fragment key={property.property_id}>
                                                <tr
                                                    onClick={() => navigate(`/property/${property.property_id}`)}
                                                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                                                >
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-medium tracking-tight">{property.property_name}</span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        {getStatusBadge(property.status)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-gray-900 font-semibold">
                                                                {formatNumber(property.last_7?.impressions ?? 0)}
                                                            </span>
                                                            <span className={`text-xs font-medium ${getDeltaColor(property.delta_pct?.impressions ?? 0, 'impressions')}`}>
                                                                {formatDelta(property.delta_pct?.impressions ?? 0)}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-gray-900 font-semibold">
                                                                {formatNumber(property.last_7?.clicks ?? 0)}
                                                            </span>
                                                            <span className={`text-xs font-medium ${getDeltaColor(property.delta_pct?.clicks ?? 0, 'clicks')}`}>
                                                                {formatDelta(property.delta_pct?.clicks ?? 0)}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-[10px] font-bold text-gray-900">
                                                        {formatDate(property.data_through)}
                                                    </td>
                                                </tr>

                                            </React.Fragment>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
