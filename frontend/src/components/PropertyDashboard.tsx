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
    const [activeTab, setActiveTab] = useState<'drop' | 'gain' | 'new' | 'lost'>('drop');
    const [isLoading, setIsLoading] = useState(true);

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
                <div className="bg-slate-800/40 rounded-xl p-6 border border-slate-800/60 backdrop-blur-sm">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 items-center border border-slate-700/30 rounded-lg p-6 bg-slate-900/40">
                        {/* Impressions */}
                        <div className="text-center md:text-left">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Impressions</p>
                            <p className="text-3xl font-bold text-white mb-1">
                                {overview.last_7_days.impressions.toLocaleString()}
                            </p>
                            <div className="flex flex-col text-sm">
                                {formatDelta(overview.deltas.impressions_pct)}
                                <span className="text-slate-500 font-mono text-[10px] mt-0.5">
                                    {overview.prev_7_days.impressions.toLocaleString()} → {overview.last_7_days.impressions.toLocaleString()}
                                </span>
                            </div>
                        </div>

                        {/* Clicks */}
                        <div className="text-center md:text-left border-t md:border-t-0 md:border-l border-slate-700/30 pt-6 md:pt-0 md:pl-8">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Clicks</p>
                            <p className="text-3xl font-bold text-white mb-1">
                                {overview.last_7_days.clicks.toLocaleString()}
                            </p>
                            <div className="flex flex-col text-sm">
                                {formatDelta(overview.deltas.clicks_pct)}
                                <span className="text-slate-500 font-mono text-[10px] mt-0.5">
                                    {overview.prev_7_days.clicks.toLocaleString()} → {overview.last_7_days.clicks.toLocaleString()}
                                </span>
                            </div>
                        </div>

                        {/* CTR */}
                        <div className="text-center md:text-left border-t md:border-t-0 md:border-l border-slate-700/30 pt-6 md:pt-0 md:pl-8">
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">CTR</p>
                            <p className="text-3xl font-bold text-white mb-1">
                                {(overview.last_7_days.ctr * 100).toFixed(2)}%
                            </p>
                            <div className="flex flex-col text-sm">
                                {formatDelta(overview.deltas.ctr_pct)}
                                <span className="text-slate-500 font-mono text-[10px] mt-0.5">
                                    {((overview.prev_7_days.ctr * 100).toFixed(2))}% → {((overview.last_7_days.ctr * 100).toFixed(2))}%
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="mt-6 pt-5 border-t border-slate-700/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Average Rank Position</p>
                            <div className="flex items-baseline gap-3">
                                <span className="text-2xl font-bold text-sky-400">
                                    {overview.last_7_days.avg_position.toFixed(1)}
                                </span>
                                <span className="text-sm">
                                    {formatPositionDelta(overview.deltas.avg_position)}
                                    <span className="text-slate-500 ml-1 text-xs">
                                        {overview.deltas.avg_position < 0 ? 'improvement' : overview.deltas.avg_position > 0 ? 'decline' : ''}
                                    </span>
                                </span>
                            </div>
                        </div>
                        <div className="text-[10px] text-slate-500 md:text-right italic">
                            Lower is better. Position 1 = top of search results.
                        </div>
                    </div>
                </div>
            )}

            {/* Device Performance */}
            {devices && (
                <div className="bg-slate-800/40 rounded-xl p-6 border border-slate-800/60 backdrop-blur-sm">
                    <h2 className="text-lg font-semibold text-white mb-6">
                        Device Performance
                    </h2>

                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-slate-500 border-b border-slate-700/30">
                                    <th className="text-left py-3">Device</th>
                                    <th className="text-right py-3">Impressions</th>
                                    <th className="text-right py-3">Clicks</th>
                                    <th className="text-right py-3">CTR</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/20">
                                {['mobile', 'desktop', 'tablet'].map(deviceKey => {
                                    const device = devices.devices ? devices.devices[deviceKey] : null;
                                    if (!device) return null;

                                    const formatInlineDelta = (val: number) => {
                                        if (val > 0) return <span className="text-green-400 font-medium">+{val.toFixed(1)}%</span>;
                                        if (val < 0) return <span className="text-red-400 font-medium">{val.toFixed(1)}%</span>;
                                        return <span className="text-slate-400 font-medium">0.0%</span>;
                                    };

                                    return (
                                        <tr key={deviceKey} className="hover:bg-slate-800/10 transition-colors">
                                            <td className="py-4 capitalize text-slate-300 font-medium">
                                                {deviceKey}
                                            </td>

                                            <td className="py-4 text-right">
                                                <div className="text-white font-semibold">
                                                    {device.last_7_impressions.toLocaleString()}
                                                </div>
                                                <div className="text-[11px] mt-0.5">
                                                    {formatInlineDelta(device.impressions_delta_pct)}
                                                </div>
                                            </td>

                                            <td className="py-4 text-right">
                                                <div className="text-white font-semibold">
                                                    {device.last_7_clicks.toLocaleString()}
                                                </div>
                                                <div className="text-[11px] mt-0.5">
                                                    {formatInlineDelta(device.clicks_delta_pct)}
                                                </div>
                                            </td>

                                            <td className="py-4 text-right">
                                                <div className="text-white font-semibold">
                                                    {(device.last_7_ctr * 100).toFixed(1)}%
                                                </div>
                                                <div className="text-[11px] mt-0.5">
                                                    {formatInlineDelta(device.ctr_delta_pct)}
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Page Movements */}
            {pages && (
                <div className="bg-slate-800/40 rounded-xl p-6 border border-slate-800/60 backdrop-blur-sm">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                        <h2 className="text-lg font-semibold text-white">Page Movements</h2>
                        <div className="flex bg-slate-950/40 rounded-lg p-1 border border-slate-800/40 w-fit overflow-x-auto">
                            {[
                                { id: 'drop', label: 'Dropping' },
                                { id: 'gain', label: 'Gaining' },
                                { id: 'new', label: 'New' },
                                { id: 'lost', label: 'Lost' }
                            ].map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id as any)}
                                    className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all whitespace-nowrap ${activeTab === tab.id
                                        ? 'bg-slate-700 text-white shadow-lg shadow-black/20'
                                        : 'text-slate-500 hover:text-slate-300'
                                        }`}
                                >
                                    {tab.label}
                                    <span className={`ml-2 px-1.5 py-0.5 rounded-full text-[10px] ${pages.totals[tab.id as keyof typeof pages.totals] > 0
                                        ? (tab.id === 'gain' || tab.id === 'new' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-rose-900/30 text-rose-400')
                                        : 'bg-slate-900/50 text-slate-600'
                                        }`}>
                                        {pages.totals[tab.id as keyof typeof pages.totals]}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="bg-slate-950/20 rounded-lg border border-slate-800/30 overflow-hidden">
                        <div className="max-h-[400px] overflow-y-auto custom-scrollbar">
                            {pages.pages[activeTab].length > 0 ? (
                                <table className="w-full text-sm">
                                    <tbody className="divide-y divide-slate-800/10">
                                        {pages.pages[activeTab].map((item: PageVisibilityItem, i: number) => (
                                            <tr key={i} className="hover:bg-slate-800/10 transition-colors group">
                                                <td className="px-5 py-4 max-w-[400px]">
                                                    <div className="truncate text-slate-400 group-hover:text-slate-200 transition-colors font-medium" title={item.page_url}>
                                                        {item.page_url.replace(/^https?:\/\/[^/]+/, '') || '/'}
                                                    </div>
                                                </td>
                                                <td className="px-5 py-4 text-right">
                                                    {activeTab === 'new' ? (
                                                        <span className="text-emerald-400 font-bold">{item.impressions_last_7.toLocaleString()} imps</span>
                                                    ) : activeTab === 'lost' ? (
                                                        <span className="text-rose-500/80 font-bold">0 impressions</span>
                                                    ) : (
                                                        <span className={`font-bold ${activeTab === 'gain' ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                            {formatDelta(item.delta_pct)}
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="py-20 text-center text-slate-600 font-medium text-sm">
                                    No pages found in this category
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
