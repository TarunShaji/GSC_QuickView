import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../AuthContext';
import type { Alert } from '../types';


export default function AlertsPage() {
    const { accountId } = useAuth();
    const navigate = useNavigate();
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAlerts = useCallback(async () => {
        if (!accountId) return;
        try {
            setError(null);
            const data = await api.alerts.getAll(accountId);
            setAlerts(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
        } finally {
            setLoading(false);
        }
    }, [accountId]);

    useEffect(() => {
        fetchAlerts();

        // Auto-refresh every 5 seconds to show real-time email status changes
        const interval = setInterval(fetchAlerts, 5000);
        return () => clearInterval(interval);
    }, [fetchAlerts]);

    const formatDate = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <div className="inline-block w-8 h-8 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin mb-4"></div>
                    <p className="text-gray-500 font-medium">Loading alerts...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                <p className="text-red-600 font-medium">❌ {error}</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-end border-b border-gray-200 pb-8">
                <div className="space-y-4">
                    <button
                        onClick={() => navigate('/')}
                        className="px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-gray-500 hover:text-gray-900 transition-colors flex items-center gap-2 group"
                    >
                        <span className="group-hover:-translate-x-1 transition-transform">←</span> Portfolio Overview
                    </button>
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">System Alerts</h1>
                        <p className="text-gray-500 text-sm font-medium mt-1">
                            Operational monitoring for performance anomalies
                        </p>
                    </div>
                </div>
                <button
                    onClick={fetchAlerts}
                    className="px-4 py-2 bg-white border border-gray-200 text-gray-900 text-sm font-bold uppercase tracking-widest rounded hover:bg-gray-50 transition-colors shadow-sm"
                >
                    Refresh
                </button>
            </div>

            {alerts.length === 0 ? (
                <div className="bg-white border border-gray-200 rounded-lg p-20 text-center shadow-sm">
                    <div className="text-5xl mb-6">✅</div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">Systems Nominal</h3>
                    <p className="text-gray-500 font-medium italic">No performance anomalies detected across tracked properties.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg overflow-hidden border border-gray-200 shadow-sm">
                    <table className="w-full">
                        <thead className="bg-gray-50 border-b border-gray-200">
                            <tr>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Property
                                </th>
                                <th className="px-6 py-4 text-left text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Type
                                </th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Previous 7D
                                </th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Last 7D
                                </th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Change
                                </th>
                                <th className="px-6 py-4 text-right text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Triggered
                                </th>
                                <th className="px-6 py-4 text-center text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                                    Email
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {alerts.map((alert) => (
                                <tr key={alert.id} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                        {alert.site_url}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${alert.alert_type === 'critical'
                                            ? 'bg-red-50 text-red-700 border-red-100'
                                            : 'bg-yellow-50 text-yellow-700 border-yellow-100'
                                            }`}>
                                            {alert.alert_type}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500 font-medium">
                                        {alert.prev_7_impressions.toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-900 font-bold">
                                        {alert.last_7_impressions.toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-red-600">
                                        {alert.delta_pct.toFixed(1)}%
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500 font-medium italic">
                                        {formatDate(alert.triggered_at)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        {alert.email_sent ? (
                                            <span className="text-[10px] font-bold text-green-600 uppercase tracking-tighter">✓ Dispatched</span>
                                        ) : (
                                            <span className="text-[10px] font-bold text-yellow-600 uppercase tracking-tighter">⏳ Queued</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
