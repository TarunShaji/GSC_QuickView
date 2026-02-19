import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { Download } from 'lucide-react';
import api from '../api';
import { useAuth } from '../AuthContext';
import PipelineBanner from './PipelineBanner';
import type { PropertyOverview, PageVisibilityResponse, DeviceVisibilityResponse, PageVisibilityItem } from '../types';

/**
 * Enterprise Trend Indicator (↗, ↘, –)
 */
const TrendIndicator = ({ pct, showLabel = true }: { pct: number, showLabel?: boolean }) => {
    let sign = '';
    let color = 'text-gray-400';
    let Icon = '–';

    if (pct > 0) {
        sign = '+';
        color = 'text-green-600';
        Icon = '↑';
    } else if (pct < 0) {
        color = 'text-red-600';
        Icon = '↓';
    }

    return (
        <span className={`${color} flex items-center gap-1 font-semibold`}>
            <span className="text-sm">{Icon}</span>
            {showLabel && <span className="text-xs">{sign}{(pct ?? 0).toFixed(1)}%</span>}
        </span>
    );
};

const KPICard = ({ label, current, prev, delta, isPercentage = false }: {
    label: string,
    current: number,
    prev: number,
    delta: number,
    isPercentage?: boolean
}) => (
    <div className="bg-white p-6 rounded-lg border border-gray-200 transition-shadow hover:shadow-sm group">
        <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-3 leading-relaxed py-1">
            {label}
        </p>
        <div className="flex items-baseline justify-between">
            <p className="text-3xl font-bold text-gray-900 tracking-tight">
                {isPercentage ? `${((current ?? 0) * 100).toFixed(1)}%` : (current ?? 0).toLocaleString()}
            </p>
            <TrendIndicator pct={delta ?? 0} />
        </div>
        <div className="mt-3 pt-3 border-t border-gray-50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">Previous week</span>
            <span className="text-xs text-gray-500 font-medium">
                {isPercentage ? `${((prev ?? 0) * 100).toFixed(1)}%` : (prev ?? 0).toLocaleString()}
            </span>
        </div>
    </div>
);

const MetricCell = ({ primary, secondary, delta }: { primary: string | number, secondary: string | number, delta: number }) => (
    <div className="flex flex-col items-end">
        <span className="text-sm font-semibold text-gray-900 tracking-tight">
            {(primary ?? 0).toLocaleString()}
        </span>
        <div className="flex items-center gap-2 mt-1">
            <span className="text-[10px] text-gray-500 font-medium italic">vs. {(secondary ?? 0).toLocaleString()}</span>
            <TrendIndicator pct={delta ?? 0} showLabel={false} />
        </div>
    </div>
);

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
            className={`px-5 py-4 font-bold text-gray-500 uppercase tracking-widest text-[10px] cursor-pointer hover:text-gray-900 transition-colors leading-relaxed ${align === 'right' ? 'text-right' : 'text-left'}`}
            onClick={() => onSort(sortKey)}
        >
            <div className={`flex items-center gap-1.5 ${align === 'right' ? 'justify-end' : 'justify-start'}`}>
                {label}
                <span className={`transition-transform ${isActive ? 'text-gray-900' : 'text-gray-300'}`}>
                    {isActive ? (currentSort.dir === 'asc' ? '↑' : '↓') : '↑'}
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
    const [searchQuery, setSearchQuery] = useState('');

    const handleExportXLSX = () => {
        if (!overview || !pages || !devices) return;

        const wb = XLSX.utils.book_new();

        // Sheet 1: Overview
        const overviewRows = [
            { Metric: 'Impressions', 'Last 7 Days': overview.last_7_days.impressions, 'Previous 7 Days': overview.prev_7_days.impressions, 'Delta %': overview.deltas.impressions_pct },
            { Metric: 'Clicks', 'Last 7 Days': overview.last_7_days.clicks, 'Previous 7 Days': overview.prev_7_days.clicks, 'Delta %': overview.deltas.clicks_pct },
            { Metric: 'CTR', 'Last 7 Days': `${(overview.last_7_days.ctr * 100).toFixed(2)}%`, 'Previous 7 Days': `${(overview.prev_7_days.ctr * 100).toFixed(2)}%`, 'Delta %': overview.deltas.ctr_pct },
            { Metric: 'Avg Position', 'Last 7 Days': overview.last_7_days.avg_position, 'Previous 7 Days': overview.prev_7_days.avg_position, 'Delta %': -overview.deltas.avg_position },
        ];
        const wsOverview = XLSX.utils.json_to_sheet(overviewRows);
        wsOverview['!cols'] = [
            { wch: 25 }, // Metric
            { wch: 18 }, // Last 7 Days
            { wch: 18 }, // Previous 7 Days
            { wch: 18 }, // Delta %
        ];
        XLSX.utils.book_append_sheet(wb, wsOverview, 'Overview');

        // Sheets 2–5: Page Visibility (all tabs, unfiltered)
        const pageSheets: { key: keyof typeof pages.pages; name: string }[] = [
            { key: 'drop', name: 'Visibility - Declining' },
            { key: 'gain', name: 'Visibility - Rising' },
            { key: 'new', name: 'Visibility - Emerged' },
            { key: 'lost', name: 'Visibility - Lost' },
        ];
        for (const { key, name } of pageSheets) {
            const rows = pages.pages[key].map((item: PageVisibilityItem) => ({
                'Page URL': item.page_url,
                'Impressions (L7)': item.impressions_last_7,
                'Impressions (P7)': item.impressions_prev_7,
                'Impr Δ%': item.delta_pct,
                'Clicks (L7)': item.clicks_last_7,
                'Clicks (P7)': item.clicks_prev_7,
                'Click Δ%': item.clicks_delta_pct,
            }));
            const wsPage = XLSX.utils.json_to_sheet(rows);
            wsPage['!cols'] = [
                { wch: 60 }, // Page URL
                { wch: 15 }, // Impressions (L7)
                { wch: 15 }, // Impressions (P7)
                { wch: 12 }, // Impr Δ%
                { wch: 15 }, // Clicks (L7)
                { wch: 15 }, // Clicks (P7)
                { wch: 12 }, // Click Δ%
            ];
            XLSX.utils.book_append_sheet(wb, wsPage, name);
        }

        // Sheet 6: Device Breakdown
        const deviceRows = Object.entries(devices.devices).map(([device, d]) => ({
            Device: device.charAt(0).toUpperCase() + device.slice(1),
            'Impressions (L7)': d.last_7_impressions,
            'Impressions (P7)': d.prev_7_impressions,
            'Impr Δ%': d.impressions_delta_pct,
            'Clicks (L7)': d.last_7_clicks,
            'Clicks (P7)': d.prev_7_clicks,
            'Click Δ%': d.clicks_delta_pct,
            'CTR (L7)': `${(d.last_7_ctr * 100).toFixed(2)}%`,
            'CTR (P7)': `${(d.prev_7_ctr * 100).toFixed(2)}%`,
        }));
        const wsDevice = XLSX.utils.json_to_sheet(deviceRows);
        wsDevice['!cols'] = [
            { wch: 20 }, // Device
            { wch: 18 }, // Impressions (L7)
            { wch: 18 }, // Impressions (P7)
            { wch: 15 }, // Impr Δ%
            { wch: 18 }, // Clicks (L7)
            { wch: 18 }, // Clicks (P7)
            { wch: 15 }, // Click Δ%
            { wch: 15 }, // CTR (L7)
            { wch: 15 }, // CTR (P7)
        ];
        XLSX.utils.book_append_sheet(wb, wsDevice, 'Device Breakdown');

        // Build filename: <property-name>_seo_report_<YYYY-MM-DD>.xlsx
        const safeName = (overview.property_name ?? overview.property_id)
            .replace(/[^a-z0-9]/gi, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '')
            .toLowerCase();
        const dateStr = overview.computed_at
            ? new Date(overview.computed_at).toISOString().split('T')[0]
            : new Date().toISOString().split('T')[0];
        // XLSX.writeFile uses Node.js `fs` and fails silently in browsers.
        // Instead, write to a buffer and trigger a browser download via Blob.
        const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
        const blob = new Blob([wbout], { type: 'application/octet-stream' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${safeName}_seo_report_${dateStr}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const fetchAll = useCallback(async (isInitial = false) => {
        if (!propertyId || !accountId) return;
        if (isInitial) setIsLoading(true);
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
            if (isInitial) setIsLoading(false);
        }
    }, [propertyId, accountId]);

    useEffect(() => {
        fetchAll(true);
    }, [fetchAll]);

    // Filtering Logic: filter ONLY the active tab, frontend-only
    const filteredPages = useMemo(() => {
        if (!pages) return [];
        const tabPages = pages.pages[activeTab];
        const q = searchQuery.trim().toLowerCase();
        if (!q) return tabPages;
        return tabPages.filter((item: PageVisibilityItem) =>
            item.page_url.toLowerCase().includes(q)
        );
    }, [pages, activeTab, searchQuery]);

    // Sorting Logic: sort handler + memo derived from filteredPages
    const handleSort = (key: 'impressions' | 'clicks') => {
        setSortConfig(prev => ({
            key,
            dir: prev.key === key && prev.dir === 'desc' ? 'asc' : 'desc'
        }));
    };

    const sortedPages = useMemo(() => {
        return [...filteredPages].sort((a, b) => {
            const valA = sortConfig.key === 'impressions' ? a.impressions_last_7 : a.clicks_last_7;
            const valB = sortConfig.key === 'impressions' ? b.impressions_last_7 : b.clicks_last_7;
            return sortConfig.dir === 'desc' ? valB - valA : valA - valB;
        });
    }, [filteredPages, sortConfig]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-20">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500/80"></div>
            </div>
        );
    }

    return (
        <>
            <PipelineBanner onSuccess={fetchAll} />
            {overview && overview.initialized === false ? (
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
            ) : (
                <div className="space-y-8">
                    {/* Header: Title & Navigation */}
                    <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-gray-200 pb-8">
                        <div className="space-y-4">
                            <button
                                onClick={() => navigate('/')}
                                className="px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-gray-500 hover:text-gray-900 transition-colors flex items-center gap-2 group"
                            >
                                <span className="group-hover:-translate-x-1 transition-transform">←</span> Property Overview
                            </button>
                            <div>
                                <h1 className="text-3xl font-black text-gray-900 uppercase tracking-tight">
                                    WEEKLY PERFORMANCE
                                </h1>
                            </div>
                        </div>

                        <div className="flex flex-col items-end gap-3">
                            <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                                <span>Date range:</span>
                                <span className="text-gray-600 font-bold bg-gray-50 px-2 py-0.5 rounded border border-gray-200">
                                    {(() => {
                                        if (!overview?.computed_at) return 'N/A';
                                        const endDate = new Date(overview.computed_at);
                                        const startDate = new Date(endDate);
                                        startDate.setDate(endDate.getDate() - 6);
                                        const f = (d: Date) => d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
                                        return `${f(startDate)}-${f(endDate)}`;
                                    })()}
                                </span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="flex items-center gap-3 bg-white p-1 rounded-md border border-gray-200 shadow-sm">
                                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-3">Device Filter</span>
                                    <select
                                        value={selectedDevice}
                                        onChange={(e) => setSelectedDevice(e.target.value as 'all' | 'mobile' | 'desktop' | 'tablet')}
                                        className="bg-transparent text-gray-900 text-xs font-bold py-1.5 px-3 rounded focus:outline-none cursor-pointer hover:bg-gray-50 transition-all appearance-none pr-8 relative"
                                        style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 24 24\' stroke=\'%236b7280\'%3E%3Cpath stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'2\' d=\'M19 9l-7 7-7-7\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.5rem center', backgroundSize: '1rem' }}
                                    >
                                        <option value="all">All Devices</option>
                                        <option value="mobile">Mobile Only</option>
                                        <option value="desktop">Desktop Only</option>
                                        <option value="tablet">Tablet Only</option>
                                    </select>
                                </div>
                                <button
                                    onClick={handleExportXLSX}
                                    disabled={!overview || !pages || !devices}
                                    className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-widest rounded-md hover:bg-gray-700 transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                    <Download size={12} strokeWidth={2.5} />
                                    Export XLSX
                                </button>
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
                                            label="IMPRESSIONS"
                                            current={deviceData ? deviceData.last_7_impressions : overview.last_7_days.impressions}
                                            prev={deviceData ? deviceData.prev_7_impressions : overview.prev_7_days.impressions}
                                            delta={deviceData ? deviceData.impressions_delta_pct : overview.deltas.impressions_pct}
                                        />
                                        <KPICard
                                            label="CLICKS"
                                            current={deviceData ? deviceData.last_7_clicks : overview.last_7_days.clicks}
                                            prev={deviceData ? deviceData.prev_7_clicks : overview.prev_7_days.clicks}
                                            delta={deviceData ? deviceData.clicks_delta_pct : overview.deltas.clicks_pct}
                                        />
                                        <KPICard
                                            label="CTR"
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
                        <div className="bg-white p-8 rounded-lg border border-gray-200 flex flex-col md:flex-row md:items-center justify-between gap-8 shadow-sm">
                            <div className="space-y-4">
                                <div className="flex items-center gap-4">
                                    <div>
                                        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-widest">Global Rank Position</h3>
                                        <div className="flex items-baseline gap-6 mt-1">
                                            <span className="text-5xl font-black text-gray-900 tracking-tighter">
                                                {(overview.last_7_days?.avg_position ?? 0).toFixed(1)}
                                            </span>
                                            <div className="flex flex-col">
                                                <TrendIndicator pct={-(overview.deltas?.avg_position ?? 0) * 10} showLabel={false} />
                                                <span className={`text-[10px] font-bold uppercase tracking-tighter ${(overview.deltas?.avg_position ?? 0) < 0 ? 'text-green-600' : (overview.deltas?.avg_position ?? 0) > 0 ? 'text-red-600' : 'text-gray-400'}`}>
                                                    {(overview.deltas?.avg_position ?? 0) < 0 ? 'Improvement' : (overview.deltas?.avg_position ?? 0) > 0 ? 'Decline' : 'Stable'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="max-w-xs text-gray-500 text-xs font-medium leading-relaxed border-l border-gray-100 pl-8">
                                Global average position across all queries. A figure closer to 1.0 represents high dominance in search result pages.
                            </div>
                        </div>
                    )}

                    {/* SECTION 3: Page-Level Movements */}
                    {pages && (
                        <div className="space-y-6">
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-gray-200 pb-2">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-sm font-bold text-gray-900 tracking-widest uppercase flex items-center gap-3">
                                        Visibility Changes
                                    </h2>
                                    {/* Search Filter — filters only the active tab, frontend-only */}
                                    <div className="relative">
                                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs pointer-events-none select-none">⌕</span>
                                        <input
                                            type="text"
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            placeholder="Filter by URL"
                                            className="pl-7 pr-3 py-1.5 text-xs font-semibold text-gray-800 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-gray-500 focus:border-gray-500 transition-all w-44 placeholder-gray-400"
                                        />
                                    </div>
                                </div>

                                {/* Tab Bar */}
                                <div className="flex gap-6">
                                    {[
                                        { id: 'drop', label: 'Declining' },
                                        { id: 'gain', label: 'Rising' },
                                        { id: 'new', label: 'Emerged' },
                                        { id: 'lost', label: 'Lost' }
                                    ].map((tab) => {
                                        const isActive = activeTab === tab.id;
                                        const count = pages.totals[tab.id as keyof typeof pages.totals];
                                        return (
                                            <button
                                                key={tab.id}
                                                onClick={() => {
                                                    setActiveTab(tab.id as 'drop' | 'gain' | 'new' | 'lost');
                                                    setSearchQuery('');
                                                }}
                                                className={`pb-4 px-1 relative flex items-center gap-2 transition-all text-xs font-bold uppercase tracking-widest ${isActive ? 'text-gray-900' : 'text-gray-400 hover:text-gray-600'}`}
                                            >
                                                {tab.label}
                                                <span className={`text-[10px] px-2 py-0.5 rounded-md border ${isActive ? 'bg-gray-100 border-gray-200 text-gray-900' : 'bg-transparent border-gray-100 text-gray-400'}`}>
                                                    {count}
                                                </span>
                                                {isActive && (
                                                    <div className="absolute bottom-[-1px] left-0 right-0 h-[2px] bg-gray-900" />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden shadow-sm">
                                <div className="max-h-[600px] overflow-y-auto">
                                    {sortedPages.length > 0 ? (
                                        <table className="w-full text-sm table-fixed">
                                            <thead className="sticky top-0 bg-gray-50 border-b border-gray-200 z-10">
                                                <tr>
                                                    <th className="px-8 py-3 text-left font-bold text-gray-500 uppercase tracking-widest text-[10px] w-1/2">Page URL</th>
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
                                            <tbody className="divide-y divide-gray-100">
                                                {sortedPages.map((item: PageVisibilityItem, i: number) => (
                                                    <tr key={i} className="hover:bg-gray-50 transition-colors group align-top">
                                                        <td className="px-8 py-4 overflow-hidden">
                                                            <a
                                                                href={item.page_url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className="block truncate text-gray-500 group-hover:text-gray-900 transition-colors font-medium"
                                                                title={item.page_url}
                                                            >
                                                                {item.page_url.replace(/^https?:\/\/[^/]+/, '') || '/'}
                                                            </a>
                                                        </td>
                                                        <td className="px-5 py-4 text-right">
                                                            <MetricCell
                                                                primary={item.impressions_last_7}
                                                                secondary={item.impressions_prev_7}
                                                                delta={item.delta_pct}
                                                            />
                                                        </td>
                                                        <td className="px-5 py-4 text-right">
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
                                        <div className="py-24 flex flex-col items-center justify-center text-center space-y-3 bg-white">
                                            <div className="text-gray-100 text-6xl">∅</div>
                                            <div className="space-y-1">
                                                <p className="text-gray-400 font-bold uppercase tracking-widest text-[10px]">
                                                    {searchQuery.trim()
                                                        ? `No pages matching "${searchQuery.trim()}"`
                                                        : activeTab === 'drop' ? 'No significant declines'
                                                            : activeTab === 'gain' ? 'No significant gains'
                                                                : 'No data found'}
                                                </p>
                                                <p className="text-gray-300 text-[10px] font-medium italic">
                                                    {searchQuery.trim() ? 'Try a different search term.' : 'Operating within normal parameters.'}
                                                </p>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </>
    );
}
