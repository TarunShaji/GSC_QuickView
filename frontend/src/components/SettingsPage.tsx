import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';

export default function SettingsPage() {
    const { accountId, email: accountEmail } = useAuth();
    const navigate = useNavigate();
    const [recipients, setRecipients] = useState<string[]>([]);
    const [newEmail, setNewEmail] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchRecipients = useCallback(async () => {
        try {
            setIsLoading(true);
            const data = await api.alerts.getRecipients(accountId!);
            setRecipients(data.recipients);
        } catch (err) {
            console.error('Failed to fetch recipients:', err);
            setError('Failed to load recipients');
        } finally {
            setIsLoading(false);
        }
    }, [accountId]);

    useEffect(() => {
        if (accountId) {
            fetchRecipients();
        }
    }, [accountId, fetchRecipients]);

    const handleAddRecipient = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newEmail || !accountId) return;

        // Basic email validation
        if (!newEmail.includes('@')) {
            setError('Invalid email address');
            return;
        }

        try {
            setIsSubmitting(true);
            setError(null);
            await api.alerts.addRecipient(accountId, newEmail);
            setNewEmail('');
            await fetchRecipients();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add recipient');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleDeleteRecipient = async (emailToDelete: string) => {
        if (!accountId) return;

        try {
            setError(null);
            await api.alerts.removeRecipient(accountId, emailToDelete);
            await fetchRecipients();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to remove recipient');
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin"></div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <div className="flex justify-between items-end border-b border-gray-200 pb-8">
                <div className="space-y-4">
                    <button
                        onClick={() => navigate('/')}
                        className="px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-gray-500 hover:text-gray-900 transition-colors flex items-center gap-2 group"
                    >
                        <span className="group-hover:-translate-x-1 transition-transform">←</span> Portfolio Overview
                    </button>
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Account Settings</h1>
                        <p className="text-gray-500 text-sm font-medium mt-1">
                            Manage notifications and system preferences
                        </p>
                    </div>
                </div>
            </div>

            <div className="bg-white rounded-lg p-8 border border-gray-200 shadow-sm">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-4">Authentication</h2>
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-gray-50 border border-gray-200 flex items-center justify-center">
                        <span className="text-gray-400">👤</span>
                    </div>
                    <div>
                        <p className="text-sm font-bold text-gray-900">{accountEmail}</p>
                        <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Active Search Console session</p>
                    </div>
                </div>
            </div>

            <div className="bg-white rounded-lg p-8 border border-gray-200 shadow-sm">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Alert Notifications</h2>
                <p className="text-gray-500 text-sm font-medium mb-8">
                    Specify recipients for automated performance anomaly reports.
                </p>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md mb-8 text-xs font-bold uppercase tracking-tight">
                        {error}
                    </div>
                )}

                {/* Add Form */}
                <form onSubmit={handleAddRecipient} className="flex gap-3 mb-10">
                    <input
                        type="email"
                        value={newEmail}
                        onChange={(e) => setNewEmail(e.target.value)}
                        placeholder="recipient@enterprise.com"
                        className="flex-1 bg-gray-50 border border-gray-200 text-gray-900 text-sm font-medium rounded-md px-4 py-2.5 outline-none focus:ring-1 focus:ring-gray-300 transition-all placeholder:text-gray-300"
                        required
                    />
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="bg-gray-900 hover:bg-black disabled:bg-gray-400 text-white text-xs font-bold uppercase tracking-widest px-6 py-2.5 rounded transition-colors shadow-sm"
                    >
                        {isSubmitting ? 'Adding...' : 'Add Recipient'}
                    </button>
                </form>

                <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-4 leading-relaxed">Current Distribution List</h3>
                <div className="space-y-3">
                    {recipients.length === 0 ? (
                        <div className="text-center py-12 border border-gray-100 rounded-lg text-gray-500 font-medium italic text-sm">
                            No recipients configured.
                        </div>
                    ) : (
                        recipients.map((email) => (
                            <div
                                key={email}
                                className="flex items-center justify-between bg-gray-50 p-4 rounded-md border border-gray-200 shadow-sm"
                            >
                                <span className="text-sm font-semibold text-gray-900">{email}</span>
                                <button
                                    onClick={() => handleDeleteRecipient(email)}
                                    className="text-gray-400 hover:text-red-600 p-2 rounded transition-colors"
                                    title="Delete"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                    </svg>
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
