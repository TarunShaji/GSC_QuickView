import { useState, useEffect, ReactNode } from 'react';
import api from '../api';

interface AuthGateProps {
    children: ReactNode;
}

export default function AuthGate({ children }: AuthGateProps) {
    const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const checkAuth = async () => {
        try {
            setIsLoading(true);
            setError(null);
            const status = await api.auth.getStatus();
            setIsAuthenticated(status.authenticated);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to check auth status');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        checkAuth();
    }, []);

    const handleLogin = async () => {
        try {
            setIsLoading(true);
            setError(null);
            await api.auth.login();
            // Re-check auth after login
            await checkAuth();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed');
            setIsLoading(false);
        }
    };

    // Loading state
    if (isLoading && isAuthenticated === null) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-900">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                    <p className="text-slate-400">Checking authentication...</p>
                </div>
            </div>
        );
    }

    // Not authenticated - show login
    if (!isAuthenticated) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-900">
                <div className="bg-slate-800 rounded-xl p-8 max-w-md w-full mx-4 shadow-2xl">
                    <div className="text-center mb-8">
                        <h1 className="text-3xl font-bold text-white mb-2">GSC Quick View</h1>
                        <p className="text-slate-400">
                            Connect your Google Search Console to get started
                        </p>
                    </div>

                    {error && (
                        <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-6">
                            {error}
                        </div>
                    )}

                    <button
                        onClick={handleLogin}
                        disabled={isLoading}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-semibold py-3 px-6 rounded-lg transition-colors flex items-center justify-center gap-2"
                    >
                        {isLoading ? (
                            <>
                                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                                Connecting...
                            </>
                        ) : (
                            <>
                                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                                </svg>
                                Connect Google Search Console
                            </>
                        )}
                    </button>

                    <p className="text-slate-500 text-sm text-center mt-6">
                        This will open a Google authentication window
                    </p>
                </div>
            </div>
        );
    }

    // Authenticated - render children
    return <>{children}</>;
}
