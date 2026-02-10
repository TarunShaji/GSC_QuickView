import { useState, useEffect } from 'react';
import { api } from '../api';

interface Alert {
    id: string;
    property_id: string;
    site_url: string;
    alert_type: string;
    prev_7_impressions: number;
    last_7_impressions: number;
    delta_pct: number;
    triggered_at: string;
    email_sent: boolean;
}

export default function AlertsPage() {
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAlerts = async () => {
        try {
            setError(null);
            const data = await api.alerts.getAll();
            setAlerts(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch alerts');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();

        // Auto-refresh every 5 seconds to show real-time email status changes
        const interval = setInterval(fetchAlerts, 5000);
        return () => clearInterval(interval);
    }, []);

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
                    <div className="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
                    <p className="text-slate-400">Loading alerts...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
                <p className="text-red-400">❌ {error}</p>
            </div>
        );
    }

    if (alerts.length === 0) {
        return (
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-12 text-center">
                <div className="text-6xl mb-4">✅</div>
                <h3 className="text-xl font-semibold text-white mb-2">No Alerts</h3>
                <p className="text-slate-400">No impression drops detected in recent pipeline runs.</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-white">Recent Alerts</h2>
                <p className="text-sm text-slate-400">
                    Auto-refreshing every 5s • {alerts.length} total
                </p>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
                <table className="w-full">
                    <thead className="bg-slate-900 border-b border-slate-700">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                Property
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                Alert Type
                            </th>
                            <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                                Δ %
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                                Triggered At
                            </th>
                            <th className="px-6 py-3 text-center text-xs font-medium text-slate-400 uppercase tracking-wider">
                                Email Status
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {alerts.map((alert) => (
                            <tr key={alert.id} className="hover:bg-slate-700/50 transition-colors">
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="text-sm font-medium text-white">
                                        {alert.site_url}
                                    </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-500/10 text-orange-400 border border-orange-500/20">
                                        {alert.alert_type.replace('_', ' ')}
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-right">
                                    <span className="text-sm font-semibold text-red-400">
                                        {alert.delta_pct.toFixed(1)}%
                                    </span>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <div className="text-sm text-slate-300">
                                        {formatDate(alert.triggered_at)}
                                    </div>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-center">
                                    {alert.email_sent ? (
                                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                                            ✅ Sent
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 animate-pulse">
                                            ⏳ Pending
                                        </span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="text-xs text-slate-500 text-center">
                Showing top {alerts.length} most recent alerts
            </div>
        </div>
    );
}
