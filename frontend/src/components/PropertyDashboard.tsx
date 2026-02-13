import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { PropertyOverview, PageVisibilityResponse, DeviceVisibilityResponse, PageVisibilityItem } from '../types';

export default function PropertyDashboard() {
    const { propertyId } = useParams<{ propertyId: string }>();
    const { accountId } = useAuth();
    const navigate = useNavigate();
    const [overview, setOverview] = useState<PropertyOverview | null>(null);
    const [pages, setPages] = useState<PageVisibilityResponse | null>(null);
    const [devices, setDevices] = useState<DeviceVisibilityResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    // V1: Removed activeInsightFilter state

    useEffect(() => {
        if (!propertyId || !accountId) return;

        const fetchAll = async () => {
            setIsLoading(true);
            try {
                const [overviewData, pagesData, devicesData] = await Promise.all([
                    api.properties.getOverview(accountId, propertyId),
                    api.properties.getPages(accountId, propertyId),
                    api.properties.getDevices(accountId, propertyId),
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
    }, [propertyId, accountId]);

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

    // V1: No health flag filtering - removed getAllPages(), getInsightCounts() and getFilteredPages()
    // V1: Removed insightCounts and filteredPages variables

    return (
        <div className="space-y-6">
            {/* Header with Back Button */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => navigate('/')}
                    className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors flex items-center gap-2"
                >
                    ← Back to Dashboard
                </button>
                <h1 className="text-2xl font-bold text-white">{overview?.property_name || 'Property Analytics'}</h1>
            </div>
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

                    {/* V1: Page Insights section removed - no health flags */}
                    {/* V1: Filtered insight pages section removed - no health flags */}

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
