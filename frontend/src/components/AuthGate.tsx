import type { ReactNode } from 'react';
import { useState, useEffect } from 'react';
import { useAuth } from '../AuthContext';
import api from '../api';
import type { Account } from '../types';

interface AuthGateProps {
    children: ReactNode;
}

export default function AuthGate({ children }: AuthGateProps) {
    const { isLoading: authLoading, login, error } = useAuth();

    // Check if any SEO accounts exist in the database
    const [accountsChecked, setAccountsChecked] = useState(false);
    const [hasAccounts, setHasAccounts] = useState(false);
    const [checkLoading, setCheckLoading] = useState(true);

    useEffect(() => {
        api.accounts.getAll()
            .then((accounts: Account[]) => {
                setHasAccounts(accounts.length > 0);
            })
            .catch(() => {
                // On error (e.g. network failure), fall back to login screen
                setHasAccounts(false);
            })
            .finally(() => {
                setAccountsChecked(true);
                setCheckLoading(false);
            });
    }, []);

    // Loading — wait for both auth context and accounts check
    if (authLoading || checkLoading || !accountsChecked) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="text-center">
                    <div className="inline-block w-8 h-8 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin mb-4" />
                    <p className="text-gray-500 font-medium tracking-tight">Loading...</p>
                </div>
            </div>
        );
    }

    // Accounts exist in DB → show the app (selector page or dashboard)
    if (hasAccounts) {
        return <>{children}</>;
    }

    // No accounts in DB → show Google login to add the first account
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="bg-white rounded-xl p-10 max-w-md w-full mx-4 shadow-sm border border-gray-200">
                <div className="text-center mb-10">
                    <div className="w-14 h-14 bg-green-500 rounded-xl flex items-center justify-center mx-auto mb-6 shadow-sm shadow-green-100">
                        <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" strokeOpacity="0.2" />
                            <path d="M12 18C15.3137 18 18 15.3137 18 12C18 8.68629 15.3137 6 12 6C8.68629 6 6 8.68629 6 12C6 15.3137 8.68629 18 12 18Z" strokeOpacity="0.4" />
                            <path d="M12 12L19 5" strokeLinecap="round" />
                            <circle cx="12" cy="12" r="2" fill="currentColor" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-black text-gray-900 mb-2 tracking-tight">GSC Radar</h1>
                    <p className="text-gray-500 font-medium">
                        Multi-account operational SEO analysis
                    </p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-8 text-xs font-bold uppercase tracking-wider">
                        {error}
                    </div>
                )}

                <button
                    onClick={login}
                    className="w-full bg-gray-900 hover:bg-black text-white text-xs font-bold uppercase tracking-widest py-4 px-6 rounded-lg transition-all flex items-center justify-center gap-3 shadow-sm"
                >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                    </svg>
                    Sign in with Google
                </button>

                <p className="text-gray-400 text-[10px] font-bold uppercase tracking-widest text-center mt-8">
                    Secure OAuth 2.0 Authentication
                </p>
            </div>
        </div>
    );
}
