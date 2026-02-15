import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { DashboardSummaryResponse, WebsiteSummary, PropertySummary } from '../types';

export default function DashboardSummary() {
    const { accountId } = useAuth();
    const navigate = useNavigate();
    const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [expandedWebsites, setExpandedWebsites] = useState<Set<string>>(new Set());
    const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());

    useEffect(() => {
        if (!accountId) return;

        const fetchSummary = async () => {
            setIsLoading(true);
            try {
                const data = await api.dashboard.getSummary(accountId);
                setSummary(data);
                // Auto-expand first website
                if (data.websites.length > 0) {
                    setExpandedWebsites(new Set([data.websites[0].website_id]));
                }
            } catch (err) {
                console.error('Failed to fetch dashboard summary:', err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchSummary();
    }, [accountId]);

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

                <div className="text-center py-12">
                    <div className="bg-slate-800 rounded-xl p-8 max-w-md mx-auto border border-slate-700">
                        <div className="text-6xl mb-4">🚀</div>
                        <h2 className="text-xl font-bold text-white mb-4">
                            Welcome to GSC Quick View
                        </h2>
                        <p className="text-slate-300 mb-6">
                            {summary.message || 'Data has not been initialized. Please run the pipeline to sync your properties.'}
                        </p>
                        <div className="text-center py-12">
                            <div className="bg-slate-800 rounded-xl p-8 max-w-md mx-auto border border-slate-700">
                                <div className="text-6xl mb-4">🚀</div>
                                <h2 className="text-xl font-bold text-white mb-4">
                                    Welcome to GSC Quick View
                                </h2>
                                <p className="text-slate-300 mb-6">
                                    {summary.message || 'Wait while we prepare your dashboard...'}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
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
    );
}
