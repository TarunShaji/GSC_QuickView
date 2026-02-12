import { useState, useEffect } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { Property, PropertyOverview, PageVisibilityResponse, DeviceVisibilityResponse, PageVisibilityItem } from '../types';

interface PropertyDashboardProps {
    property: Property;
}

export default function PropertyDashboard({ property }: PropertyDashboardProps) {
    const { accountId } = useAuth();
    const [overview, setOverview] = useState<PropertyOverview | null>(null);
    const [pages, setPages] = useState<PageVisibilityResponse | null>(null);
    const [devices, setDevices] = useState<DeviceVisibilityResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [activeInsightFilter, setActiveInsightFilter] = useState<string | null>(null);

    useEffect(() => {
        if (!property.id || !accountId) return;

        const fetchAll = async () => {
            setIsLoading(true);
            try {
                const [overviewData, pagesData, devicesData] = await Promise.all([
                    api.properties.getOverview(accountId, property.id),
                    api.properties.getPages(accountId, property.id),
                    api.properties.getDevices(accountId, property.id),
                ]);
                setOverview(overviewData);
                setPages(pagesData);
                setDevices(devicesData);
            } catch (err) {
                console.error('Failed to fetch property data:', err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchAll();
    }, [property.id, accountId]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    // Fixed delta formatting - no more "+-" or "+0" bugs
    const formatDelta = (pct: number) => {
        let sign = '';
        let color = 'text-slate-400';

        if (pct > 0) {
            sign = '+';
            color = 'text-green-400';
        } else if (pct < 0) {
            color = 'text-red-400';
        }

        return (
            <span className={color}>
                {sign}{pct.toFixed(1)}%
            </span>
        );
    };

    // Position delta formatter (inverse metric: lower is better)
    const formatPositionDelta = (delta: number) => {
        let sign = '';
        let color = 'text-slate-400';

        if (delta < 0) {
            sign = '';
            color = 'text-green-400'; // Improvement
        } else if (delta > 0) {
            sign = '+';
            color = 'text-red-400'; // Worse
        }

        return (
            <span className={color}>
                {sign}{delta.toFixed(1)}
            </span>
        );
    };

    // Get all pages across all categories for insight filtering
    const getAllPages = (): PageVisibilityItem[] => {
        if (!pages) return [];
        return [
            ...pages.pages.new,
            ...pages.pages.lost,
            ...pages.pages.drop,
            ...pages.pages.gain,
        ];
    };

    // Compute insight counts
    const getInsightCounts = () => {
        const allPages = getAllPages();
        return {
            title_optimization: allPages.filter(p => p.title_optimization).length,
            ranking_push: allPages.filter(p => p.ranking_push).length,
            zero_click: allPages.filter(p => p.zero_click).length,
            low_ctr_pos_1_3: allPages.filter(p => p.low_ctr_pos_1_3).length,
            strong_gainer: allPages.filter(p => p.strong_gainer).length,
        };
    };

    // Get filtered pages based on active insight
    const getFilteredPages = (): PageVisibilityItem[] => {
        const allPages = getAllPages();
        if (!activeInsightFilter) return [];

        switch (activeInsightFilter) {
            case 'title_optimization':
                return allPages.filter(p => p.title_optimization);
            case 'ranking_push':
                return allPages.filter(p => p.ranking_push);
            case 'zero_click':
                return allPages.filter(p => p.zero_click);
            case 'low_ctr_pos_1_3':
                return allPages.filter(p => p.low_ctr_pos_1_3);
            case 'strong_gainer':
                return allPages.filter(p => p.strong_gainer);
            default:
                return [];
        }
    };

    const insightCounts = pages ? getInsightCounts() : null;
    const filteredPages = activeInsightFilter ? getFilteredPages() : [];

    return (
        <div className="space-y-6">
            {/* Property Overview */}
            {overview && (
                <div className="bg-slate-800 rounded-xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4">7-Day Overview</h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">Clicks (Last 7)</p>
                            <p className="text-2xl font-bold text-white">{overview.last_7_days.clicks.toLocaleString()}</p>
                            <p className="text-sm">{formatDelta(overview.deltas.clicks_pct)}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">Impressions (Last 7)</p>
                            <p className="text-2xl font-bold text-white">{overview.last_7_days.impressions.toLocaleString()}</p>
                            <p className="text-sm">{formatDelta(overview.deltas.impressions_pct)}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">CTR (Last 7)</p>
                            <p className="text-2xl font-bold text-white">{(overview.last_7_days.ctr * 100).toFixed(2)}%</p>
                            <p className="text-sm">{formatDelta(overview.deltas.ctr_pct)}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">Avg Position (Last 7)</p>
                            <p className="text-2xl font-bold text-white">{overview.last_7_days.avg_position.toFixed(1)}</p>
                            <p className="text-sm">{formatPositionDelta(overview.deltas.avg_position)}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">Clicks (Prev 7)</p>
                            <p className="text-2xl font-bold text-slate-300">{overview.prev_7_days.clicks.toLocaleString()}</p>
                        </div>
                        <div className="bg-slate-700/50 rounded-lg p-4">
                            <p className="text-sm text-slate-400">Impressions (Prev 7)</p>
                            <p className="text-2xl font-bold text-slate-300">{overview.prev_7_days.impressions.toLocaleString()}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Device Visibility */}
            {devices && (
                <div className="bg-slate-800 rounded-xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4">Device Performance</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {['mobile', 'desktop', 'tablet'].map((deviceName) => {
                            const device = devices.devices ? devices.devices[deviceName] : null;
                            if (!device) return null;

                            const classColor = {
                                significant_gain: 'border-green-500 bg-green-900/20',
                                significant_drop: 'border-red-500 bg-red-900/20',
                                flat: 'border-slate-600 bg-slate-700/50',
                                insufficient_data: 'border-slate-700 bg-slate-800',
                            }[device.classification] || 'border-slate-600';

                            return (
                                <div key={deviceName} className={`border-l-4 rounded-lg p-4 ${classColor}`}>
                                    <p className="text-sm text-slate-400 capitalize">{deviceName}</p>
                                    <p className="text-xl font-bold text-white">
                                        {device.last_7_impressions?.toLocaleString() || 0} impressions
                                    </p>
                                    <p className="text-sm">
                                        {device.classification === 'insufficient_data' ? (
                                            <span className="text-slate-500">Insufficient data</span>
                                        ) : (
                                            formatDelta(device.delta_pct || 0)
                                        )}
                                    </p>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* Page Visibility */}
            {pages && (
                <div className="bg-slate-800 rounded-xl p-6">
                    <h2 className="text-lg font-semibold text-white mb-4">Page Visibility</h2>

                    {/* Summary tabs */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
                        <div className="bg-green-900/30 border border-green-800 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-green-400">{pages.totals?.new || 0}</p>
                            <p className="text-xs text-green-300">New Pages</p>
                        </div>
                        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-red-400">{pages.totals?.lost || 0}</p>
                            <p className="text-xs text-red-300">Lost Pages</p>
                        </div>
                        <div className="bg-green-900/30 border border-green-800 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-green-400">{pages.totals?.gain || 0}</p>
                            <p className="text-xs text-green-300">Gaining</p>
                        </div>
                        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-center">
                            <p className="text-2xl font-bold text-red-400">{pages.totals?.drop || 0}</p>
                            <p className="text-xs text-red-300">Dropping</p>
                        </div>
                    </div>

                    {/* Page Insights Section */}
                    {insightCounts && (
                        <div className="mt-6 mb-6">
                            <h3 className="text-md font-semibold text-white mb-3">Page Insights</h3>
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                                <button
                                    onClick={() => setActiveInsightFilter(activeInsightFilter === 'title_optimization' ? null : 'title_optimization')}
                                    className={`border rounded-lg p-3 text-center transition-all ${activeInsightFilter === 'title_optimization'
                                        ? 'bg-yellow-900/40 border-yellow-600'
                                        : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50'
                                        }`}
                                >
                                    <p className="text-xl font-bold text-yellow-400">{insightCounts.title_optimization}</p>
                                    <p className="text-xs text-slate-300">⚠️ Title Optimization</p>
                                </button>
                                <button
                                    onClick={() => setActiveInsightFilter(activeInsightFilter === 'ranking_push' ? null : 'ranking_push')}
                                    className={`border rounded-lg p-3 text-center transition-all ${activeInsightFilter === 'ranking_push'
                                        ? 'bg-blue-900/40 border-blue-600'
                                        : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50'
                                        }`}
                                >
                                    <p className="text-xl font-bold text-blue-400">{insightCounts.ranking_push}</p>
                                    <p className="text-xs text-slate-300">🚀 Ranking Push</p>
                                </button>
                                <button
                                    onClick={() => setActiveInsightFilter(activeInsightFilter === 'zero_click' ? null : 'zero_click')}
                                    className={`border rounded-lg p-3 text-center transition-all ${activeInsightFilter === 'zero_click'
                                        ? 'bg-orange-900/40 border-orange-600'
                                        : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50'
                                        }`}
                                >
                                    <p className="text-xl font-bold text-orange-400">{insightCounts.zero_click}</p>
                                    <p className="text-xs text-slate-300">🔍 Zero Click</p>
                                </button>
                                <button
                                    onClick={() => setActiveInsightFilter(activeInsightFilter === 'low_ctr_pos_1_3' ? null : 'low_ctr_pos_1_3')}
                                    className={`border rounded-lg p-3 text-center transition-all ${activeInsightFilter === 'low_ctr_pos_1_3'
                                        ? 'bg-purple-900/40 border-purple-600'
                                        : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50'
                                        }`}
                                >
                                    <p className="text-xl font-bold text-purple-400">{insightCounts.low_ctr_pos_1_3}</p>
                                    <p className="text-xs text-slate-300">🎯 Low CTR (Top 3)</p>
                                </button>
                                <button
                                    onClick={() => setActiveInsightFilter(activeInsightFilter === 'strong_gainer' ? null : 'strong_gainer')}
                                    className={`border rounded-lg p-3 text-center transition-all ${activeInsightFilter === 'strong_gainer'
                                        ? 'bg-green-900/40 border-green-600'
                                        : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50'
                                        }`}
                                >
                                    <p className="text-xl font-bold text-green-400">{insightCounts.strong_gainer}</p>
                                    <p className="text-xs text-slate-300">🔥 Strong Gainers</p>
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Filtered Insight Pages */}
                    {activeInsightFilter && filteredPages.length > 0 && (
                        <div className="mt-4 mb-6">
                            <h3 className="text-sm font-medium text-white mb-2">
                                {activeInsightFilter === 'title_optimization' && '⚠️ Title Optimization Opportunities'}
                                {activeInsightFilter === 'ranking_push' && '🚀 Ranking Push Opportunities'}
                                {activeInsightFilter === 'zero_click' && '🔍 Zero Click Pages'}
                                {activeInsightFilter === 'low_ctr_pos_1_3' && '🎯 Low CTR in Top 3'}
                                {activeInsightFilter === 'strong_gainer' && '🔥 Strong Gainers'}
                            </h3>
                            <div className="space-y-1 max-h-64 overflow-y-auto">
                                {filteredPages.map((page, i) => (
                                    <div key={i} className="flex justify-between items-center bg-slate-700/50 rounded px-3 py-2 text-sm">
                                        <span className="text-slate-300 truncate max-w-md" title={page.page_url}>
                                            {page.page_url.replace(/^https?:\/\/[^/]+/, '')}
                                        </span>
                                        <div className="flex gap-3 ml-2 whitespace-nowrap text-xs">
                                            <span className="text-slate-400">
                                                {page.impressions_last_7} imp
                                            </span>
                                            {page.avg_position_last_7 > 0 && (
                                                <span className="text-slate-400">
                                                    pos {page.avg_position_last_7.toFixed(1)}
                                                </span>
                                            )}
                                            {page.clicks_last_7 > 0 && (
                                                <span className="text-slate-400">
                                                    {page.clicks_last_7} clicks
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Page lists */}
                    <div className="mt-6 space-y-4">
                        {/* Significant Drops */}
                        {pages.pages.drop.length > 0 && (
                            <div>
                                <h3 className="text-sm font-medium text-red-400 mb-2">📉 Significant Drops</h3>
                                <div className="space-y-1 max-h-48 overflow-y-auto">
                                    {pages.pages.drop.slice(0, 10).map((page, i) => (
                                        <div key={i} className="flex justify-between items-center bg-slate-700/50 rounded px-3 py-2 text-sm">
                                            <span className="text-slate-300 truncate max-w-md" title={page.page_url}>
                                                {page.page_url.replace(/^https?:\/\/[^/]+/, '')}
                                            </span>
                                            <span className="text-red-400 ml-2 whitespace-nowrap">
                                                {formatDelta(page.delta_pct || 0)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Significant Gains */}
                        {pages.pages.gain.length > 0 && (
                            <div>
                                <h3 className="text-sm font-medium text-green-400 mb-2">📈 Significant Gains</h3>
                                <div className="space-y-1 max-h-48 overflow-y-auto">
                                    {pages.pages.gain.slice(0, 10).map((page, i) => (
                                        <div key={i} className="flex justify-between items-center bg-slate-700/50 rounded px-3 py-2 text-sm">
                                            <span className="text-slate-300 truncate max-w-md" title={page.page_url}>
                                                {page.page_url.replace(/^https?:\/\/[^/]+/, '')}
                                            </span>
                                            <span className="text-green-400 ml-2 whitespace-nowrap">
                                                {formatDelta(page.delta_pct || 0)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* New Pages */}
                        {pages.pages.new.length > 0 && (
                            <div>
                                <h3 className="text-sm font-medium text-blue-400 mb-2">✨ New Pages</h3>
                                <div className="space-y-1 max-h-48 overflow-y-auto">
                                    {pages.pages.new.slice(0, 10).map((page, i) => (
                                        <div key={i} className="flex justify-between items-center bg-slate-700/50 rounded px-3 py-2 text-sm">
                                            <span className="text-slate-300 truncate max-w-md" title={page.page_url}>
                                                {page.page_url.replace(/^https?:\/\/[^/]+/, '')}
                                            </span>
                                            <span className="text-blue-400 ml-2 whitespace-nowrap">
                                                {page.impressions_last_7} impressions
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
