import { useState, useEffect } from 'react';
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

    useEffect(() => {
        if (accountId) {
            fetchRecipients();
        }
    }, [accountId]);

    const fetchRecipients = async () => {
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
    };

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
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <div className="flex items-center gap-6 mb-6">
                <h1 className="text-2xl font-bold text-white">Settings</h1>
                <nav className="flex gap-4">
                    <button
                        onClick={() => navigate('/')}
                        className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                    >
                        Dashboard
                    </button>
                    <button
                        onClick={() => navigate('/alerts')}
                        className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                    >
                        Alerts
                    </button>
                    <button className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg">
                        Settings
                    </button>
                </nav>
            </div>
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-xl font-semibold text-white mb-2">Account Settings</h2>
                <p className="text-slate-400 text-sm">
                    Logged in as <span className="text-blue-400 font-medium">{accountEmail}</span>
                </p>
            </div>

            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
                <h2 className="text-xl font-semibold text-white mb-4">Alert Recipients</h2>
                <p className="text-slate-400 text-sm mb-6">
                    Add email addresses that should receive SEO alerts for this account.
                </p>

                {error && (
                    <div className="bg-red-900/40 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-6 text-sm">
                        {error}
                    </div>
                )}

                {/* Add Form */}
                <form onSubmit={handleAddRecipient} className="flex gap-3 mb-8">
                    <input
                        type="email"
                        value={newEmail}
                        onChange={(e) => setNewEmail(e.target.value)}
                        placeholder="email@example.com"
                        className="flex-1 bg-slate-900 border border-slate-700 text-white rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-600"
                        required
                    />
                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-2 px-6 rounded-lg transition-colors"
                    >
                        {isSubmitting ? 'Adding...' : 'Add Recipient'}
                    </button>
                </form>

                {/* Recipient List */}
                <div className="space-y-3">
                    {recipients.length === 0 ? (
                        <div className="text-center py-8 border-2 border-dashed border-slate-700 rounded-lg text-slate-500">
                            No recipients added yet.
                        </div>
                    ) : (
                        recipients.map((email) => (
                            <div
                                key={email}
                                className="flex items-center justify-between bg-slate-900/50 p-4 rounded-lg border border-slate-700 group hover:border-slate-600 transition-all"
                            >
                                <span className="text-slate-200">{email}</span>
                                <button
                                    onClick={() => handleDeleteRecipient(email)}
                                    className="text-slate-500 hover:text-red-400 p-1 rounded-md hover:bg-red-400/10 transition-all"
                                    title="Delete"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
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
