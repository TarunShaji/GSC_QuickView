import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { PipelineStatus } from '../types';

interface PipelineGateProps {
    children: ReactNode;
}

export default function PipelineGate({ children }: PipelineGateProps) {
    const { accountId } = useAuth();
    const [status, setStatus] = useState<PipelineStatus | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isStarting, setIsStarting] = useState(false);

    const pollStatus = async () => {
        if (!accountId) return;
        try {
            const data = await api.pipeline.getStatus(accountId);
            setStatus(data);
            return data;
        } finally {
            setIsLoading(false);
            return null;
        }
    };

    useEffect(() => {
        pollStatus();
    }, [accountId]);

    // Poll while running or starting
    useEffect(() => {
        if (!accountId) return;

        // Stop polling if we are in a terminal state (completed or failed)
        // AND not currently running
        if (!status?.is_running && (status?.phase === 'completed' || status?.phase === 'failed')) {
            return;
        }

        // If running or idle (to detect remote start), poll
        // But poll faster if running, slower if idle
        const intervalTime = status?.is_running ? 1500 : 5000;
        const interval = setInterval(pollStatus, intervalTime);
        return () => clearInterval(interval);
    }, [status?.is_running, status?.phase, accountId]);

    const handleRunPipeline = async () => {
        if (!accountId) return;
        try {
            setIsStarting(true);
            setError(null);
            await api.pipeline.run(accountId);
            // Poll immediately after starting
            await pollStatus();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to start pipeline');
        } finally {
            setIsStarting(false);
        }
    };

    const getPhaseLabel = (phase: string) => {
        switch (phase) {
            case 'idle': return 'Ready';
            case 'ingestion': return 'Ingesting Data';
            case 'analysis': return 'Analyzing';
            case 'completed': return 'Completed';
            case 'failed': return 'Failed';
            default: return phase;
        }
    };

    const getProgressPercent = () => {
        if (!status?.progress) return 0;
        if (status.progress.total === 0) return 0;
        return Math.round((status.progress.current / status.progress.total) * 100);
    };

    // Pipeline is running - show progress UI
    if (status?.is_running) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-900">
                <div className="bg-slate-800 rounded-xl p-8 max-w-lg w-full mx-4 shadow-2xl">
                    <div className="text-center mb-6">
                        <h1 className="text-2xl font-bold text-white mb-2">Pipeline Running</h1>
                        <p className="text-slate-400">{getPhaseLabel(status.phase)}</p>
                    </div>

                    {/* Progress bar */}
                    <div className="mb-6">
                        <div className="flex justify-between text-sm text-slate-400 mb-2">
                            <span>{status.current_step || 'Initializing...'}</span>
                            <span>{getProgressPercent()}%</span>
                        </div>
                        <div className="w-full bg-slate-700 rounded-full h-3">
                            <div
                                className="bg-blue-500 h-3 rounded-full transition-all duration-300"
                                style={{ width: `${getProgressPercent()}%` }}
                            ></div>
                        </div>
                    </div>

                    {/* Completed steps */}
                    {status.completed_steps.length > 0 && (
                        <div className="space-y-2">
                            <p className="text-sm text-slate-500">Completed:</p>
                            <div className="flex flex-wrap gap-2">
                                {status.completed_steps.map((step) => (
                                    <span
                                        key={step}
                                        className="text-xs bg-green-900/50 text-green-300 px-2 py-1 rounded"
                                    >
                                        ✓ {step}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Initial loading
    if (isLoading && !status) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-900">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    // Pipeline failed - show error
    if (status?.phase === 'failed') {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-900">
                <div className="bg-slate-800 rounded-xl p-8 max-w-lg w-full mx-4 shadow-2xl">
                    <div className="text-center mb-6">
                        <div className="w-16 h-16 bg-red-900/50 rounded-full flex items-center justify-center mx-auto mb-4">
                            <span className="text-3xl">❌</span>
                        </div>
                        <h1 className="text-2xl font-bold text-white mb-2">Pipeline Failed</h1>
                        <p className="text-red-400">{status.error || 'Unknown error'}</p>
                    </div>

                    <button
                        onClick={handleRunPipeline}
                        disabled={isStarting}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
                    >
                        {isStarting ? 'Starting...' : 'Retry Pipeline'}
                    </button>
                </div>
            </div>
        );
    }

    // Pipeline completed - show children (data explorer)
    if (status?.phase === 'completed') {
        return (
            <div className="min-h-screen bg-slate-900">
                {/* Header */}
                <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
                    <div className="flex justify-between items-center max-w-7xl mx-auto">
                        <h1 className="text-xl font-bold text-white">GSC Quick View</h1>
                        <button
                            onClick={handleRunPipeline}
                            disabled={isStarting}
                            className="bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 px-4 rounded-lg transition-colors flex items-center gap-2"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                            Refresh Data
                        </button>
                    </div>
                </header>

                {/* Content */}
                <main className="p-6 max-w-7xl mx-auto">
                    {children}
                </main>
            </div>
        );
    }

    // Idle - show run pipeline button
    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-900">
            <div className="bg-slate-800 rounded-xl p-8 max-w-md w-full mx-4 shadow-2xl">
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-bold text-white mb-2">GSC Quick View</h1>
                    <p className="text-slate-400">
                        Run the pipeline to fetch and analyze your Google Search Console data
                    </p>
                </div>

                {error && (
                    <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-6">
                        {error}
                    </div>
                )}

                <button
                    onClick={handleRunPipeline}
                    disabled={isStarting}
                    className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                    {isStarting ? (
                        <>
                            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                            Starting...
                        </>
                    ) : (
                        <>
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Run Pipeline
                        </>
                    )}
                </button>

                <p className="text-slate-500 text-sm text-center mt-6">
                    This may take a few minutes depending on your data volume
                </p>
            </div>
        </div>
    );
}
