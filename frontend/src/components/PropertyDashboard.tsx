import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { PropertyOverview, PageVisibilityResponse, DeviceVisibilityResponse, PageVisibilityItem } from '../types';

/**
 * Enterprise Trend Indicator (↗, ↘, –)
 */
const TrendIndicator = ({ pct, showLabel = true }: { pct: number, showLabel?: boolean }) => {
    let sign = '';
    let color = 'text-slate-400';
    let Icon = '–';

    if (pct > 0) {
        sign = '+';
        color = 'text-green-400';
        Icon = '↗';
    } else if (pct < 0) {
        color = 'text-red-400';
        Icon = '↘';
    }

    return (
        <span className={`${color} flex items-center gap-1 font-semibold`}>
            <span className="text-sm">{Icon}</span>
            {showLabel && <span className="text-xs">{sign}{(pct ?? 0).toFixed(1)}%</span>}
        </span>
    );
};

/**
 * Reusable KPI Card for Enterprise Layout
 */
const KPICard = ({ label, current, prev, delta, isPercentage = false }: {
    label: string,
    current: number,
    prev: number,
    delta: number,
    isPercentage?: boolean
}) => (
    <div className="bg-slate-900/40 p-6 rounded-xl border border-slate-700/30 transition-all hover:bg-slate-800/30 hover:shadow-xl hover:shadow-black/20 group">
        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 group-hover:text-slate-400 transition-colors">
            {label}
        </p>
        <p className="text-4xl font-bold text-white mb-3 tracking-tight">
            {isPercentage ? `${((current ?? 0) * 100).toFixed(1)}%` : (current ?? 0).toLocaleString()}
        </p>
        <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-medium">
                {isPercentage ? `${((prev ?? 0) * 100).toFixed(1)}%` : (prev ?? 0).toLocaleString()}
            </span>
            <TrendIndicator pct={delta ?? 0} />
        </div>
    </div>
);

/**
 * Standardized Metric Cell for Tables
 */
const MetricCell = ({ primary, secondary, delta }: { primary: string | number, secondary: string | number, delta: number }) => (
    <div className="flex flex-col items-end">
        <span className="text-base font-semibold text-white tracking-tight">
            {(primary ?? 0).toLocaleString()}
        </span>
        <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-slate-500 font-medium">{(secondary ?? 0).toLocaleString()}</span>
            <TrendIndicator pct={delta ?? 0} />
        </div>
    </div>
);

/**
 * Sortable Table Header
 */
const SortableHeader = ({ label, sortKey, currentSort, onSort, align = 'right' }: {
    label: string,
    sortKey: 'impressions' | 'clicks',
    currentSort: { key: 'impressions' | 'clicks', dir: 'asc' | 'desc' },
    onSort: (key: 'impressions' | 'clicks') => void,
    align?: 'left' | 'right'
}) => {
    const isActive = currentSort.key === sortKey;
    return (
        <th
            className={`px-5 py-4 font-bold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-white transition-colors ${align === 'right' ? 'text-right' : 'text-left'}`}
            onClick={() => onSort(sortKey)}
        >
            <div className={`flex items-center gap-1.5 ${align === 'right' ? 'justify-end' : 'justify-start'}`}>
                {label}
                <span className={`text-[10px] transition-transform ${isActive ? 'text-blue-400' : 'text-slate-700'}`}>
                    {isActive ? (currentSort.dir === 'asc' ? '▲' : '▼') : '▲'}
                </span>
            </div>
        </th>
    );
};

export default function PropertyDashboard() {
    const { propertyId } = useParams<{ propertyId: string }>();
    const { accountId } = useAuth();
    const navigate = useNavigate();

    // Core State
    const [overview, setOverview] = useState<PropertyOverview | null>(null);
    const [pages, setPages] = useState<PageVisibilityResponse | null>(null);
    const [devices, setDevices] = useState<DeviceVisibilityResponse | null>(null);

    // UI State
    const [activeTab, setActiveTab] = useState<'drop' | 'gain' | 'new' | 'lost'>('drop');
    const [selectedDevice, setSelectedDevice] = useState<'all' | 'mobile' | 'desktop' | 'tablet'>('all');
    const [isLoading, setIsLoading] = useState(true);
    const [sortConfig, setSortConfig] = useState<{ key: 'impressions' | 'clicks', dir: 'asc' | 'desc' }>({ key: 'impressions', dir: 'desc' });

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

    // Sorting Logic
    const handleSort = (key: 'impressions' | 'clicks') => {
        setSortConfig(prev => ({
            key,
            dir: prev.key === key && prev.dir === 'desc' ? 'asc' : 'desc'
        }));
    };

    const sortedPages = useMemo(() => {
        if (!pages) return [];
        const currentPages = [...pages.pages[activeTab]];
        return currentPages.sort((a, b) => {
            const valA = sortConfig.key === 'impressions' ? a.impressions_last_7 : a.clicks_last_7;
            const valB = sortConfig.key === 'impressions' ? b.impressions_last_7 : b.clicks_last_7;
            return sortConfig.dir === 'desc' ? valB - valA : valA - valB;
        });
    }, [pages, activeTab, sortConfig]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500/80"></div>
            </div>
        );
    }

    // Uninitialized guard
    if (overview && overview.initialized === false) {
        return (
            <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-6 text-center">
                <div className="mb-6 text-6xl">⏳</div>
                <h1 className="text-2xl font-bold text-white mb-2">Initializing Data...</h1>
                <p className="text-slate-400 max-w-md mb-8">
                    We haven't finished computing visibility analysis for this property yet.
                    Please wait a few minutes or run the pipeline.
                </p>
                <button
                    onClick={() => navigate('/')}
                    className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors border border-slate-700"
                >
                    Back to Dashboard
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-12 animate-in fade-in slide-in-from-bottom-2 duration-700">
            {/* Header: Title & Navigation */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-slate-800/40 pb-8">
                <div className="space-y-4">
                    <button
                        onClick={() => navigate('/')}
                        className="px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-slate-500 hover:text-white transition-colors flex items-center gap-2 group"
                    >
                        <span className="group-hover:-translate-x-1 transition-transform">←</span> Back to Dashboard
                    </button>
                    <div>
                        <h1 className="text-3xl font-black text-white tracking-tight">
                            {overview?.property_name || 'Property Analytics'}
                            {selectedDevice !== 'all' && (
                                <span className="text-blue-500/80 ml-3 font-medium text-2xl uppercase tracking-tighter opacity-80">
                                    · {selectedDevice}
                                </span>
                            )}
                        </h1>
                        <p className="text-slate-500 text-sm font-medium mt-1">
                            Enterprise Search Performance Analytics & Trend Tracking
                        </p>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-3">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-600 uppercase tracking-widest">
                        <span>Data through:</span>
                        <span className="text-slate-400 bg-slate-800/40 px-2 py-0.5 rounded border border-slate-700/20 italic">
                            {overview?.computed_at ? new Date(overview.computed_at).toLocaleDateString() : 'N/A'}
                        </span>
                    </div>
                    <div className="flex items-center gap-3 bg-slate-800/30 p-1.5 rounded-xl border border-slate-700/20 shadow-inner">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-3">Filter</span>
                        <select
                            value={selectedDevice}
                            onChange={(e) => setSelectedDevice(e.target.value as 'all' | 'mobile' | 'desktop' | 'tablet')}
                            className="bg-slate-900 text-white text-xs font-bold py-2 px-4 rounded-lg border border-slate-700/50 focus:outline-none focus:ring-2 focus:ring-blue-500/20 appearance-none cursor-pointer hover:bg-slate-950 transition-all shadow-xl"
                        >
                            <option value="all">All Devices</option>
                            <option value="mobile">Mobile</option>
                            <option value="desktop">Desktop</option>
                            <option value="tablet">Tablet</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* SECTION 1: Master KPIs */}
            {overview && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {(() => {
                        const deviceData = selectedDevice === 'all' ? null : devices?.devices[selectedDevice];

                        return (
                            <>
                                <KPICard
                                    label="Gross Impressions"
                                    current={deviceData ? deviceData.last_7_impressions : overview.last_7_days.impressions}
                                    prev={deviceData ? deviceData.prev_7_impressions : overview.prev_7_days.impressions}
                                    delta={deviceData ? deviceData.impressions_delta_pct : overview.deltas.impressions_pct}
                                />
                                <KPICard
                                    label="Total Clicks"
                                    current={deviceData ? deviceData.last_7_clicks : overview.last_7_days.clicks}
                                    prev={deviceData ? deviceData.prev_7_clicks : overview.prev_7_days.clicks}
                                    delta={deviceData ? deviceData.clicks_delta_pct : overview.deltas.clicks_pct}
                                />
                                <KPICard
                                    label="Click-Through Rate"
                                    current={deviceData ? deviceData.last_7_ctr : overview.last_7_days.ctr}
                                    prev={deviceData ? deviceData.prev_7_ctr : overview.prev_7_days.ctr}
                                    delta={deviceData ? deviceData.ctr_delta_pct : overview.deltas.ctr_pct}
                                    isPercentage
                                />
                            </>
                        );
                    })()}
                </div>
            )}

            {/* SECTION 2: Rank Positioning */}
            {selectedDevice === 'all' && overview && (
                <div className="bg-slate-800/20 p-8 rounded-2xl border border-slate-700/20 flex flex-col md:flex-row md:items-center justify-between gap-8 group transition-all hover:bg-slate-800/30">
                    <div className="space-y-4">
                        <div className="flex items-center gap-3">
                            <div className="p-3 bg-sky-500/10 rounded-xl border border-sky-500/20">
                                <span className="text-xl">📊</span>
                            </div>
                            <div>
                                <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest">Average Rank Position</h3>
                                <div className="flex items-baseline gap-4 mt-1">
                                    <span className="text-5xl font-black text-sky-400 tracking-tighter">
                                        {(overview.last_7_days?.avg_position ?? 0).toFixed(1)}
                                    </span>
                                    <div className="flex flex-col">
                                        <TrendIndicator pct={-(overview.deltas?.avg_position ?? 0) * 10} showLabel={false} />
                                        <span className={`text-[10px] font-bold uppercase tracking-tighter ${(overview.deltas?.avg_position ?? 0) < 0 ? 'text-green-500' : (overview.deltas?.avg_position ?? 0) > 0 ? 'text-red-500' : 'text-slate-500'}`}>
                                            {(overview.deltas?.avg_position ?? 0) < 0 ? 'Improvement' : (overview.deltas?.avg_position ?? 0) > 0 ? 'Decline' : 'Stable'}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="max-w-md text-slate-500 text-xs font-medium leading-relaxed italic border-l border-slate-700/30 pl-8">
                        Global average position across all tracked queries. A figure closer to 1.0 represents dominance in the primary search engine result pages (SERPs).
                    </div>
                </div>
            )}

            {/* SECTION 3: Page-Level Movements */}
            {pages && (
                <div className="space-y-6">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-slate-800/40 pb-4">
                        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-3">
                            <span className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20 text-sm">📄</span>
                            Page-Level Movements
                        </h2>

                        {/* Enterprise Tab Bar */}
                        <div className="flex gap-8 overflow-x-auto no-scrollbar">
                            {[
                                { id: 'drop', label: 'Declining', color: 'rose' },
                                { id: 'gain', label: 'Rising', color: 'emerald' },
                                { id: 'new', label: 'Emerged', color: 'blue' },
                                { id: 'lost', label: 'Lost', color: 'slate' }
                            ].map((tab) => {
                                const isActive = activeTab === tab.id;
                                const count = pages.totals[tab.id as keyof typeof pages.totals];
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id as 'drop' | 'gain' | 'new' | 'lost')}
                                        className={`pb-4 px-1 relative flex items-center gap-2.5 transition-all text-sm font-bold uppercase tracking-widest ${isActive ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}
                                    >
                                        {tab.label}
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border ${isActive ? 'bg-slate-800 border-slate-700 text-white' : 'bg-slate-900/50 border-slate-800 text-slate-600'}`}>
                                            {count}
                                        </span>
                                        {isActive && (
                                            <div className="absolute bottom-[-1px] left-0 right-0 h-[2px] bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" />
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="bg-slate-900/20 rounded-2xl border border-slate-800/40 overflow-hidden shadow-2xl backdrop-blur-sm">
                        <div className="max-h-[600px] overflow-y-auto custom-scrollbar">
                            {sortedPages.length > 0 ? (
                                <table className="w-full text-sm table-fixed">
                                    <thead className="sticky top-0 bg-slate-900 border-b border-slate-800/60 z-10 shadow-sm">
                                        <tr>
                                            <th className="px-8 py-4 text-left font-bold text-slate-500 uppercase tracking-widest text-[10px] w-1/2">Page Discovery Anchor</th>
                                            <SortableHeader
                                                label="Impressions"
                                                sortKey="impressions"
                                                currentSort={sortConfig}
                                                onSort={handleSort}
                                            />
                                            <SortableHeader
                                                label="Clicks"
                                                sortKey="clicks"
                                                currentSort={sortConfig}
                                                onSort={handleSort}
                                            />
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/20">
                                        {sortedPages.map((item: PageVisibilityItem, i: number) => (
                                            <tr key={i} className="hover:bg-slate-800/10 transition-all group align-top">
                                                <td className="px-8 py-5 overflow-hidden">
                                                    <a
                                                        href={item.page_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="block truncate text-slate-400 group-hover:text-blue-400 transition-colors font-medium border-b border-transparent group-hover:border-blue-500/30"
                                                        title={item.page_url}
                                                    >
                                                        {item.page_url.replace(/^https?:\/\/[^/]+/, '') || '/'}
                                                    </a>
                                                </td>
                                                <td className="px-5 py-5 text-right">
                                                    <MetricCell
                                                        primary={item.impressions_last_7}
                                                        secondary={item.impressions_prev_7}
                                                        delta={item.delta_pct}
                                                    />
                                                </td>
                                                <td className="px-5 py-5 text-right">
                                                    <MetricCell
                                                        primary={item.clicks_last_7}
                                                        secondary={item.clicks_prev_7}
                                                        delta={item.clicks_delta_pct}
                                                    />
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : (
                                <div className="py-32 flex flex-col items-center justify-center text-center space-y-4">
                                    <div className="text-4xl grayscale opacity-30">
                                        {activeTab === 'drop' ? '📉' : activeTab === 'gain' ? '📈' : '✨'}
                                    </div>
                                    <div className="space-y-1">
                                        <p className="text-slate-500 font-bold uppercase tracking-widest text-sm">
                                            {activeTab === 'drop' ? 'No significant declines detected' :
                                                activeTab === 'gain' ? 'No rising pages this week 🎉' :
                                                    'No pages found in this category'}
                                        </p>
                                        <p className="text-slate-600 text-xs italic">
                                            All systems within normal operating parameters.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
