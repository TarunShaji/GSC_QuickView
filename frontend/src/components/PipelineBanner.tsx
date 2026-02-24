import { useState, useEffect, useRef, useCallback } from 'react';
import api from '../api';
import { useSession } from '../SessionContext';
import type { PipelineStatus } from '../types';

interface PipelineBannerProps {
    onSuccess?: () => void;
}

export default function PipelineBanner({ onSuccess }: PipelineBannerProps) {
    const { accountId } = useSession();
    const [status, setStatus] = useState<PipelineStatus | null>(null);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const wasRunning = useRef(false);
    const [stuckInfo, setStuckInfo] = useState(false);
    const onSuccessRef = useRef(onSuccess);
    const forcePolling = useRef(false);
    const forceStartTimestamp = useRef<number | null>(null);

    useEffect(() => {
        onSuccessRef.current = onSuccess;
    }, [onSuccess]);

    const stopPolling = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
    }, []);

    // Define fetchStatus first so it can be used in startPolling
    // We'll use a functional update pattern or just rely on the fact that startPolling 
    // will be recreated when fetchStatus changes.
    const fetchStatus = useCallback(async () => {
        if (!accountId) return;
        try {
            const data = await api.pipeline.getStatus(accountId);
            setStatus(data);

            // 1. Handle transitions from running to finished
            if (wasRunning.current && !data.is_running && !data.error) {
                if (onSuccessRef.current) onSuccessRef.current();
            }
            wasRunning.current = data.is_running;

            // 2. Control polling based on state
            if (data.is_running) {
                // startPolling will be defined below, but we can call it here 
                // because of how useCallback works inside the component scope.
                // However, to satisfy the linter/TS, we'll defined it properly.
                _startPolling();
                forcePolling.current = false;
                forceStartTimestamp.current = null;
            } else if (data.error) {
                stopPolling();
                forcePolling.current = false;
                forceStartTimestamp.current = null;
            } else if (forcePolling.current && forceStartTimestamp.current) {
                const elapsed = Date.now() - forceStartTimestamp.current;
                if (elapsed > 60000) {
                    console.warn('[PIPELINE] Force polling timed out - no run detected.');
                    forcePolling.current = false;
                    forceStartTimestamp.current = null;
                    stopPolling();
                }
            } else {
                stopPolling();
            }

            // 3. Stuck detection
            if (data.is_running && data.started_at) {
                const startTime = new Date(data.started_at).getTime();
                if (Date.now() - startTime > 3600000) {
                    setStuckInfo(true);
                } else {
                    setStuckInfo(false);
                }
            } else {
                setStuckInfo(false);
            }
        } catch (err) {
            console.error('Failed to fetch pipeline status:', err);
            stopPolling();
        }
    }, [accountId, stopPolling]);
    // Note: _startPolling is added to deps later via a separate reference if needed, 
    // but here we can just use the internal one.

    function _startPolling() {
        if (intervalRef.current) return;
        intervalRef.current = setInterval(() => {
            fetchStatus();
        }, 15000);
    }

    const startPolling = useCallback(_startPolling, [fetchStatus]);

    // Update fetchStatus to include startPolling in its scope properly
    // This is a bit of a dance to avoid circular deps in the hook itself.
    useEffect(() => {
        if (!accountId) {
            stopPolling();
            return;
        }
        stopPolling();
        wasRunning.current = false;
        forcePolling.current = false;
        forceStartTimestamp.current = null;
        setStatus(null);
        fetchStatus();
    }, [accountId, fetchStatus, stopPolling]);

    useEffect(() => {
        const handleStarted = () => {
            console.log('[PIPELINE] Detected pipeline-started event. Waking up banner...');
            forcePolling.current = true;
            forceStartTimestamp.current = Date.now();
            fetchStatus();
            startPolling();
        };

        window.addEventListener('pipeline-started', handleStarted);
        return () => {
            window.removeEventListener('pipeline-started', handleStarted);
            stopPolling();
        };
    }, [fetchStatus, startPolling, stopPolling]);

    // Don't show if nothing is running or no error
    if (!status || (!status.is_running && !status.error)) return null;

    const progress = status.progress_total > 0
        ? Math.round((status.progress_current / status.progress_total) * 100)
        : 0;

    return (
        <div className="px-6 py-4">
            <div className={`rounded-lg border px-5 py-4 flex flex-col sm:flex-row items-center justify-between gap-4 transition-all ${status.is_running
                ? 'bg-white border-gray-200 shadow-sm'
                : status.error
                    ? 'bg-red-50 border-red-200'
                    : 'bg-green-50 border-green-200'
                }`}>
                <div className="flex items-center gap-4 flex-1">
                    <div className="flex-shrink-0">
                        {status.is_running ? (
                            <div className="w-10 h-10 bg-gray-50 flex items-center justify-center rounded-md border border-gray-200">
                                <div className="w-5 h-5 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin" />
                            </div>
                        ) : status.error ? (
                            <div className="w-10 h-10 rounded-md bg-red-100 flex items-center justify-center text-red-600">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                            </div>
                        ) : (
                            <div className="w-10 h-10 rounded-md bg-green-100 flex items-center justify-center text-green-600">
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            </div>
                        )}
                    </div>

                    <div className="space-y-1">
                        <h3 className={`text-xs font-bold uppercase tracking-wider ${status.is_running ? 'text-gray-900' : status.error ? 'text-red-900' : 'text-green-900'
                            }`}>
                            {status.is_running ? 'Pipeline in Progress' : status.error ? 'Pipeline Halted' : 'Sync Successful'}
                        </h3>
                        {status.is_running ? (
                            <div className="flex items-center gap-2">
                                <p className="text-sm text-gray-500 font-medium">{status.current_step}</p>
                                {status.progress_total > 0 && (
                                    <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">
                                        {status.progress_current}/{status.progress_total}
                                    </span>
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-gray-600 font-medium">
                                {status.error ? status.error : `Database synced: ${new Date(status.completed_at!).toLocaleTimeString()}`}
                            </p>
                        )}
                    </div>
                </div>

                {!status.error && status.is_running && (
                    <div className="w-full sm:w-64">
                        <div className="flex justify-between items-center mb-1.5">
                            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest leading-relaxed">Progress</span>
                            <span className="text-xs font-black text-gray-900">{progress}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden border border-gray-200 shadow-inner">
                            <div
                                className="h-full bg-gray-900 transition-all duration-1000 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                    </div>
                )}

                {status.error && (
                    <button
                        onClick={() => window.location.reload()}
                        className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-bold uppercase tracking-widest rounded transition-colors shadow-sm"
                    >
                        Retry Check
                    </button>
                )}
            </div>

            {stuckInfo && status.is_running && (
                <div className="mt-3 px-5 py-3 bg-white border border-gray-200 rounded-lg shadow-sm flex items-start gap-3">
                    <span className="text-lg">ℹ️</span>
                </div>
            )}
        </div>
    );
}
