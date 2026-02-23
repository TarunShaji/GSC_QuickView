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
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-50">
                <p className="text-red-500 font-medium">{error}</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4 py-16">
            {/* Header */}
            <div className="mb-12 text-center">
                <h1 className="text-3xl font-black text-gray-900 uppercase tracking-tight">
                    GSC RADAR
                </h1>
                <p className="mt-2 text-xs font-bold text-gray-400 uppercase tracking-[0.2em]">
                    Select an SEO account to manage
                </p>
            </div>

            {/* Account Cards Grid */}
            {accounts.length === 0 ? (
                <div className="text-center text-gray-500 text-sm">
                    No accounts found in the database.
                </div>
            ) : (
                <div className="w-full max-w-2xl grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {accounts.map((account) => (
                        <button
                            key={account.id}
                            onClick={() => handleSelect(account)}
                            className="group text-left bg-white border border-gray-200 rounded-lg px-6 py-5 shadow-sm hover:shadow-md hover:border-gray-400 transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
                        >
                            {/* Email */}
                            <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-black">
                                {account.google_email}
                            </p>

                            {/* Status badge */}
                            <div className="mt-3 flex items-center gap-2">
                                {account.data_initialized ? (
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded">
                                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                                        Data Ready
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-yellow-700 bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded">
                                        <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 inline-block" />
                                        Needs Pipeline
                                    </span>
                                )}
                            </div>

                            {/* CTA arrow */}
                            <div className="mt-4 flex items-center justify-between">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
                                    Open Dashboard
                                </span>
                                <span className="text-gray-300 group-hover:text-gray-700 group-hover:translate-x-1 transition-all text-sm">
                                    →
                                </span>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
