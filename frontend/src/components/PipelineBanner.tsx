import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { PipelineStatus } from '../types';

interface PipelineBannerProps {
    onSuccess?: () => void;
}

export default function PipelineBanner({ onSuccess }: PipelineBannerProps) {
    const { accountId } = useAuth();
    const [status, setStatus] = useState<PipelineStatus | null>(null);
    const wasRunning = useRef(false);
    const [stuckInfo, setStuckInfo] = useState(false);
    const onSuccessRef = useRef(onSuccess);
    useEffect(() => {
        onSuccessRef.current = onSuccess;
    }, [onSuccess]);

    const fetchStatus = useCallback(async () => {
        if (!accountId) return;
        try {
            const data = await api.pipeline.getStatus(accountId);
            setStatus(data);

            // Handle transition from running to finished
            if (wasRunning.current && !data.is_running && !data.error) {
                if (onSuccessRef.current) onSuccessRef.current();
            }
            wasRunning.current = data.is_running;

            // Check if run appears stuck (> 60m)
            if (data.is_running && data.started_at) {
                const startTime = new Date(data.started_at).getTime();
                const now = Date.now();
                if (now - startTime > 3600000) {
                    setStuckInfo(true);
                } else {
                    setStuckInfo(false);
                }
            } else {
                setStuckInfo(false);
            }
        } catch (err) {
            console.error('Failed to fetch pipeline status:', err);
        }
    }, [accountId]);

    useEffect(() => {
        if (!accountId) return;

        // Initial fetch
        fetchStatus();

        // Strictly controlled interval polling (5 seconds)
        const interval = setInterval(() => {
            fetchStatus();
        }, 5000);

        return () => {
            clearInterval(interval);
        };
    }, [accountId, fetchStatus]);

    // Don't show if nothing is running or no error
    if (!status || (!status.is_running && !status.error)) return null;

    const progress = status.progress_total > 0
        ? Math.round((status.progress_current / status.progress_total) * 100)
        : 0;

    return (
        <div
            className={`fixed top-0 left-0 right-0 z-[60] px-6 py-3 border-b transition-all duration-700 animate-in slide-in-from-top fade-in duration-500 ${status.error
                ? 'bg-red-950/80 border-red-500/30 text-red-100 shadow-[0_4px_20px_rgba(239,68,68,0.2)]'
                : 'bg-slate-900/60 border-slate-700/50 text-white shadow-[0_4px_20px_rgba(30,41,59,0.5)]'
                } backdrop-blur-xl`}
        >
            <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-4 flex-1">
                    <div className="flex-shrink-0">
                        {status.error ? (
                            <div className="p-2 bg-red-500/20 rounded-lg border border-red-500/40">
                                <span className="text-xl">⚠️</span>
                            </div>
                        ) : (
                            <div className="relative">
                                <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20">
                                    <span className="text-xl">🚀</span>
                                </div>
                                <div className="absolute -top-1 -right-1 flex h-3 w-3">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-black uppercase tracking-widest opacity-60">
                                {status.error ? 'Pipeline Halted' : 'Pipeline in Progress'}
                            </span>
                            {stuckInfo && (
                                <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-300 text-[10px] font-bold rounded-full border border-yellow-500/30 animate-pulse">
                                    Run appears stuck
                                </span>
                            )}
                        </div>
                        <p className="text-sm font-semibold tracking-tight">
                            {status.error ? status.error : (status.current_step || 'Processing analytics...')}
                        </p>
                    </div>
                </div>

                {!status.error && (
                    <div className="flex items-center gap-6 w-full md:w-auto">
                        <div className="flex-1 md:w-64">
                            <div className="flex justify-between items-end mb-1.5">
                                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Global Progress</span>
                                <span className="text-sm font-black text-blue-400">{progress}%</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-800/50 rounded-full overflow-hidden border border-slate-700/30">
                                <div
                                    className="h-full bg-gradient-to-r from-blue-600 to-sky-400 transition-all duration-1000 ease-out"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                        </div>
                        <div className="hidden md:block text-right">
                            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Started At</p>
                            <p className="text-xs font-medium text-slate-300">
                                {status.started_at ? new Date(status.started_at).toLocaleTimeString() : 'Initializing...'}
                            </p>
                        </div>
                    </div>
                )}

                {status.error && (
                    <button
                        onClick={() => window.location.reload()}
                        className="px-4 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-lg text-xs font-bold transition-all"
                    >
                        Dismiss & Refresh
                    </button>
                )}
            </div>

            {stuckInfo && !status.error && (
                <div className="mt-2 text-center">
                    <p className="text-[10px] text-yellow-400/80 italic">
                        This run has been active for over an hour. If progress is not moving, try refreshing the page.
                    </p>
                </div>
            )}
        </div>
    );
}
