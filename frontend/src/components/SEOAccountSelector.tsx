import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../SessionContext';
import api from '../api';
import type { Account } from '../types';

export default function SEOAccountSelector() {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [isLoadingAccounts, setIsLoadingAccounts] = useState(true);
    const [loadError, setLoadError] = useState<string | null>(null);
    const { connectGoogleAccount, isLoading: isConnecting, error: connectError } = useSession();
    const navigate = useNavigate();

    useEffect(() => {
        api.accounts.getAll()
            .then(setAccounts)
            .catch(() => setLoadError('Failed to load accounts'))
            .finally(() => setIsLoadingAccounts(false));
    }, []);

    const handleSelect = (account: Account) => {
        localStorage.setItem('selected_account_id', account.id);
        localStorage.setItem('selected_account_email', account.google_email);
        navigate(`/dashboard/${account.id}`);
    };

    if (isLoadingAccounts) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-white">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
        );
    }

    if (loadError) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-white">
                <p className="text-red-500 font-medium">{loadError}</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center px-4 py-24">
            {/* Header */}
            <div className="mb-20 text-center max-w-2xl px-4">
                <h1 className="text-4xl font-black text-gray-900 tracking-tight sm:text-5xl">
                    GSC Radar
                </h1>
                <p className="mt-4 text-sm font-bold text-gray-400 uppercase tracking-[0.2em]">
                    Choose an account to monitor SEO health
                </p>
            </div>

            {/* Account Grid Area */}
            <div className="w-full max-w-6xl mx-auto">
                {/* Multi-Account Actions Bar */}
                <div className="flex flex-col sm:flex-row justify-between items-center mb-8 gap-4 px-2">
                    <h2 className="text-xs font-black uppercase tracking-widest text-gray-400">
                        {accounts.length} Connected {accounts.length === 1 ? 'Account' : 'Accounts'}
                    </h2>

                    <div className="flex items-center gap-3">
                        {/* Alert Config navigation */}
                        <button
                            onClick={() => navigate('/alert-config')}
                            className="border border-gray-200 hover:border-gray-400 text-gray-600 hover:text-gray-900 text-[10px] font-black uppercase tracking-widest py-3 px-5 rounded-xl transition-all flex items-center gap-2"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                            </svg>
                            Alert Config
                        </button>

                        {/* Connect new GSC account */}
                        <div className="flex flex-col items-end gap-2">
                            <button
                                onClick={connectGoogleAccount}
                                disabled={isConnecting}
                                className="bg-gray-900 hover:bg-black disabled:opacity-50 text-white text-[10px] font-black uppercase tracking-widest py-3 px-6 rounded-xl transition-all shadow-sm hover:shadow-md flex items-center gap-2"
                            >
                                {isConnecting ? (
                                    <div className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                                ) : (
                                    <span className="text-lg leading-none mt-[-2px]">+</span>
                                )}
                                Connect Google Search Console
                            </button>

                            {connectError && (
                                <p className="text-[10px] font-bold text-red-500 uppercase tracking-wider">
                                    {connectError}
                                </p>
                            )}
                        </div>
                    </div>
                </div>

                {accounts.length === 0 ? (
                    <div className="text-center text-gray-500 font-medium py-20 bg-white rounded-3xl border border-gray-100 shadow-sm">
                        No active portfolios found.
                    </div>
                ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
                        {accounts.map((account) => (
                            <button
                                key={account.id}
                                onClick={() => handleSelect(account)}
                                className="group relative flex flex-col items-start bg-white border border-gray-100 rounded-3xl p-8 shadow-sm transition-all duration-200 hover:scale-[1.01] hover:shadow-xl hover:border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
                            >
                                {/* Decorative line */}
                                <div className="w-8 h-1 bg-gray-900 mb-6 rounded-full group-hover:w-12 transition-all duration-300" />

                                {/* Email/Portfolio Name */}
                                <div className="w-full mb-12 text-left">
                                    <h3 className="text-xl font-bold text-gray-900 truncate tracking-tight">
                                        {account.google_email}
                                    </h3>
                                    <p className="mt-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                                        Active Portfolio
                                    </p>
                                </div>

                                {/* Action Area */}
                                <div className="mt-auto w-full flex items-center justify-between pt-6 border-t border-gray-50">
                                    <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 group-hover:text-gray-900 transition-colors">
                                        View Dashboard
                                    </span>
                                    <span className="text-lg text-gray-300 group-hover:text-gray-900 group-hover:translate-x-1 transition-all">
                                        →
                                    </span>
                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
