import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import PipelineBanner from './PipelineBanner';
import type { DashboardSummaryResponse, WebsiteSummary, PropertySummary } from '../types';

export default function DashboardSummary() {
    const { accountId } = useAuth();
    const navigate = useNavigate();
    const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isStarting, setIsStarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [expandedWebsites, setExpandedWebsites] = useState<Set<string>>(new Set());
    const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());

    const fetchSummary = useCallback(async (isInitial = false) => {
        if (!accountId) return;
        if (isInitial) setIsLoading(true);
        setError(null);
        try {
            const data = await api.dashboard.getSummary(accountId);
            setSummary(data);
            // Auto-expand first website if no websites are currently expanded
            if (data.websites && data.websites.length > 0) {
                setExpandedWebsites(prev => prev.size === 0 ? new Set([data.websites[0].website_id]) : prev);
            }
        } catch (err) {
            console.error('Failed to fetch dashboard summary:', err);
            setError('Failed to load dashboard data');
        } finally {
            if (isInitial) setIsLoading(false);
        }
    }, [accountId]);

    useEffect(() => {
        fetchSummary(true);
    }, [fetchSummary]);

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

    const toggleWebsite = (websiteId: string) => {
        setExpandedWebsites(prev => {
            const next = new Set(prev);
            if (next.has(websiteId)) {
                next.delete(websiteId);
            } else {
                next.add(websiteId);
            }
            return next;
        });
    };

    const toggleProperty = (propertyId: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setExpandedProperties(prev => {
            const next = new Set(prev);
            if (next.has(propertyId)) {
                next.delete(propertyId);
            } else {
                next.add(propertyId);
            }
            return next;
        });
    };

    const getStatusBadge = (status: PropertySummary['status']) => {
        const badges = {
            healthy: { icon: '🟢', text: 'Healthy', color: 'text-green-400 bg-green-900/30 border-green-800' },
            warning: { icon: '🟡', text: 'Warning', color: 'text-yellow-400 bg-yellow-900/30 border-yellow-800' },
            critical: { icon: '🔴', text: 'Critical', color: 'text-red-400 bg-red-900/30 border-red-800' },
            insufficient_data: { icon: '⚪', text: 'Insufficient Data', color: 'text-slate-400 bg-slate-700/30 border-slate-600' }
        };
        const badge = badges[status];
        return (
            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs border ${badge.color}`}>
                <span>{badge.icon}</span>
                <span>{badge.text}</span>
            </span>
        );
    };

    const formatNumber = (num: number): string => {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        return num.toString();
    };

    const formatDelta = (pct: number): string => {
        const sign = pct > 0 ? '+' : '';
        return `${sign}${pct.toFixed(1)}%`;
    };

    const formatDate = (dateStr: string): string => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    };

    const getDeltaColor = (delta: number, metric: 'impressions' | 'clicks' | 'ctr' | 'position'): string => {
        if (metric === 'position') {
            // For position, negative is better (lower rank)
            return delta < 0 ? 'text-green-400' : delta > 0 ? 'text-red-400' : 'text-slate-400';
        }
        // For other metrics, positive is better
        return delta > 0 ? 'text-green-400' : delta < 0 ? 'text-red-400' : 'text-slate-400';
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
                <PipelineBanner onSuccess={fetchSummary} />
                <div className="space-y-4">
                    <div className="flex justify-between items-center mb-6">
                        <div className="flex items-center gap-6">
                            <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                            <nav className="flex gap-4">
                                <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg">
                                    Dashboard
                                </button>
                                <button
                                    onClick={() => navigate('/alerts')}
                                    className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                                >
                                    Alerts
                                </button>
                                <button
                                    onClick={() => navigate('/settings')}
                                    className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                                >
                                    Settings
                                </button>
                            </nav>
                        </div>
                    </div>

                    <div className="text-center py-20">
                        <div className="bg-slate-800 rounded-2xl p-12 max-w-xl mx-auto border border-slate-700 shadow-2xl">
                            <div className="text-7xl mb-6 animate-bounce">🚀</div>
                            <h2 className="text-3xl font-bold text-white mb-4">
                                Welcome to GSC Quick View
                            </h2>
                            <p className="text-lg text-slate-400 mb-10 leading-relaxed">
                                {summary.message || 'Your account is connected. Now let\'s fetch and analyze your Search Console data to build your first dashboard.'}
                            </p>

                            {error && (
                                <div className="mb-6 px-4 py-3 bg-red-900/30 border border-red-500/50 text-red-200 rounded-lg text-sm">
                                    {error}
                                </div>
                            )}

                            <button
                                onClick={handleRunPipeline}
                                disabled={isStarting}
                                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-bold py-4 px-8 rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center gap-3 shadow-lg shadow-blue-900/20"
                            >
                                {isStarting ? (
                                    <>
                                        <div className="animate-spin rounded-full h-5 w-5 border-2 border-white/30 border-t-white"></div>
                                        Starting...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Run Initial Pipeline
                                    </>
                                )}
                            </button>

                            <p className="mt-6 text-slate-500 text-sm">
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
        <>
            <PipelineBanner onSuccess={fetchSummary} />
            <div className="space-y-4">
                <div className="flex justify-between items-center mb-6">
                    <div className="flex items-center gap-6">
                        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
                        <nav className="flex gap-4">
                            <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg">
                                Dashboard
                            </button>
                            <button
                                onClick={() => navigate('/alerts')}
                                className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                            >
                                Alerts
                            </button>
                            <button
                                onClick={() => navigate('/settings')}
                                className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                            >
                                Settings
                            </button>
                        </nav>
                    </div>

                    <button
                        onClick={handleRunPipeline}
                        disabled={isStarting}
                        className="bg-slate-800 hover:bg-slate-700 text-white text-sm py-2 px-4 rounded-lg border border-slate-700 transition-colors flex items-center gap-2 group"
                    >
                        <svg className={`w-4 h-4 transition-transform ${isStarting ? 'animate-spin' : 'group-hover:rotate-180'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Refresh Data
                    </button>
                </div>

                {summary.websites.map((website: WebsiteSummary) => (
                    <div key={website.website_id} className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700">
                        {/* Website Header */}
                        <button
                            onClick={() => toggleWebsite(website.website_id)}
                            className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <span className="text-2xl">
                                    {expandedWebsites.has(website.website_id) ? '▼' : '▶'}
                                </span>
                                <h2 className="text-lg font-semibold text-white">{website.website_domain}</h2>
                                <span className="text-sm text-slate-400">
                                    ({website.properties.length} {website.properties.length === 1 ? 'property' : 'properties'})
                                </span>
                            </div>
                        </button>

                        {/* Property Table */}
                        {expandedWebsites.has(website.website_id) && (
                            <div className="border-t border-slate-700">
                                <div className="overflow-x-auto">
                                    <table className="w-full">
                                        <thead className="bg-slate-700/50">
                                            <tr>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                                                    Property
                                                </th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                                                    Status
                                                </th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                                                    Impressions (7D Avg)
                                                </th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                                                    Clicks (7D Avg)
                                                </th>
                                                <th className="px-6 py-3 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
                                                    Data Through
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700">
                                            {website.properties.map((property: PropertySummary) => (
                                                <>
                                                    {/* Property Row */}
                                                    <tr
                                                        key={property.property_id}
                                                        onClick={(e) => toggleProperty(property.property_id, e)}
                                                        className="hover:bg-slate-700/30 cursor-pointer transition-colors"
                                                    >
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-white">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-slate-400">
                                                                    {expandedProperties.has(property.property_id) ? '▼' : '▶'}
                                                                </span>
                                                                {property.property_name}
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            {getStatusBadge(property.status)}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-white font-medium">
                                                                    {formatNumber(property.last_7?.impressions ?? 0)}
                                                                </span>
                                                                <span className={getDeltaColor(property.delta_pct?.impressions ?? 0, 'impressions')}>
                                                                    {formatDelta(property.delta_pct?.impressions ?? 0)}
                                                                </span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-white font-medium">
                                                                    {formatNumber(property.last_7?.clicks ?? 0)}
                                                                </span>
                                                                <span className={getDeltaColor(property.delta_pct?.clicks ?? 0, 'clicks')}>
                                                                    {formatDelta(property.delta_pct?.clicks ?? 0)}
                                                                </span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                                                            {formatDate(property.data_through)}
                                                        </td>
                                                    </tr>

                                                    {/* Expanded Metrics Row */}
                                                    {expandedProperties.has(property.property_id) && (
                                                        <tr key={`${property.property_id}-metrics`}>
                                                            <td colSpan={5} className="px-6 py-6 bg-slate-900/50">
                                                                {/* 2 Metric Cards in a Row */}
                                                                <div className="grid grid-cols-2 gap-4 mb-4">
                                                                    {/* Impressions Card */}
                                                                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                                                                        <div className="text-xs text-slate-400 mb-2">Impressions</div>
                                                                        <div className="text-2xl font-bold text-white mb-1">
                                                                            {formatNumber(property.last_7?.impressions ?? 0)}
                                                                        </div>
                                                                        <div className="text-sm text-slate-400">
                                                                            Last 7d
                                                                        </div>
                                                                        <div className="text-sm text-slate-500 mt-2">
                                                                            {formatNumber(property.prev_7?.impressions ?? 0)} (Prev 7d)
                                                                        </div>
                                                                        <div className={`text-sm font-medium mt-1 ${getDeltaColor(property.delta_pct?.impressions ?? 0, 'impressions')}`}>
                                                                            {formatDelta(property.delta_pct?.impressions ?? 0)}
                                                                        </div>
                                                                    </div>

                                                                    {/* Clicks Card */}
                                                                    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                                                                        <div className="text-xs text-slate-400 mb-2">Clicks</div>
                                                                        <div className="text-2xl font-bold text-white mb-1">
                                                                            {formatNumber(property.last_7?.clicks ?? 0)}
                                                                        </div>
                                                                        <div className="text-sm text-slate-400">
                                                                            Last 7d
                                                                        </div>
                                                                        <div className="text-sm text-slate-500 mt-2">
                                                                            {formatNumber(property.prev_7?.clicks ?? 0)} (Prev 7d)
                                                                        </div>
                                                                        <div className={`text-sm font-medium mt-1 ${getDeltaColor(property.delta_pct?.clicks ?? 0, 'clicks')}`}>
                                                                            {formatDelta(property.delta_pct?.clicks ?? 0)}
                                                                        </div>
                                                                    </div>
                                                                </div>

                                                                {/* View Full Overview Button */}
                                                                <div className="flex justify-end">
                                                                    <button
                                                                        onClick={(e) => {
                                                                            e.stopPropagation();
                                                                            navigate(`/property/${property.property_id}`);
                                                                        }}
                                                                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
                                                                    >
                                                                        View Full Overview →
                                                                    </button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    )}
                                                </>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </>
    );
}
