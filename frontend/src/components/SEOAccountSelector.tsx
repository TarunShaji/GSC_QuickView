import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import type { Account } from '../types';

export default function SEOAccountSelector() {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();

    useEffect(() => {
        api.accounts.getAll()
            .then(setAccounts)
            .catch(() => setError('Failed to load accounts'))
            .finally(() => setIsLoading(false));
    }, []);

    const handleSelect = (account: Account) => {
        localStorage.setItem('gsc_account_id', account.id);
        localStorage.setItem('gsc_email', account.google_email);
        navigate(`/dashboard/${account.id}`);
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-white">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-white">
                <p className="text-red-500 font-medium">{error}</p>
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

            {/* Account Cards Grid */}
            <div className="w-full max-w-6xl mx-auto">
                {accounts.length === 0 ? (
                    <div className="text-center text-gray-500 font-medium py-20 bg-white rounded-2xl border border-gray-100 shadow-sm">
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
                                <div className="w-full mb-12">
                                    <h3 className="text-xl font-bold text-gray-900 truncate tracking-tight">
                                        {account.google_email}
                                    </h3>
                                    <p className="mt-1 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                                        Active Portfolio
                                    </p>
                                </div>

                                {/* Multi-Account Action */}
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
