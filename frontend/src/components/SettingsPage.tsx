import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface FlatProperty {
    id: string;
    name: string;
}

// For each recipient, track which property_ids they are subscribed to
type SubscriptionMap = Record<string, Set<string>>; // email → Set<property_id>

// Track in-flight toggle calls to show a per-toggle loading spinner
type TogglingMap = Record<string, boolean>; // `${email}__${propertyId}` → bool

// ─── Component ───────────────────────────────────────────────────────────────

export default function SettingsPage() {
    const { accountId } = useParams<{ accountId: string }>();
    // Derive the display email from localStorage (set when account was selected from the portfolio selector)
    const accountEmail = localStorage.getItem('selected_account_email') ?? accountId ?? '';
    const navigate = useNavigate();

    // Recipients list
    const [recipients, setRecipients] = useState<string[]>([]);
    const [newEmail, setNewEmail] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Properties list (flat, loaded once)
    const [properties, setProperties] = useState<FlatProperty[]>([]);

    // subscription state: email → Set<property_id>
    const [subscriptions, setSubscriptions] = useState<SubscriptionMap>({});

    // Track which (email, propertyId) combos are currently toggling
    const [toggling, setToggling] = useState<TogglingMap>({});

    // Which recipient rows are expanded to show property toggles
    const [expanded, setExpanded] = useState<Set<string>>(new Set());


    // ── Load all page data in ONE request ─────────────────────────────────────
    // Old pattern fired simultaneously:
    //   GET /dashboard-summary (heavy, full metrics — just to get property names!)
    //   + GET /alert-recipients
    //   + Promise.all(N × GET /alert-subscriptions)
    // = 1 heavy endpoint + 1 + N simultaneous requests → pool exhaustion.
    //
    // Now: 1 request, 1 DB connection, released immediately.
    const loadPageData = useCallback(async () => {
        if (!accountId) return;
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.alerts.getAlertConfigData(accountId);

            // Flatten properties from websites
            const flat: FlatProperty[] = data.websites.flatMap((w) =>
                w.properties.map((p: { id: string; site_url: string }) => ({ id: p.id, name: p.site_url }))
            );
            setProperties(flat);
            setRecipients(data.recipients);

            // Subscriptions pre-loaded for all recipients — no per-recipient follow-up queries
            const subMap: SubscriptionMap = {};
            for (const [email, ids] of Object.entries(data.subscriptions)) {
                subMap[email] = new Set(ids as string[]);
            }
            setSubscriptions(subMap);
        } catch (err) {
            console.error('Failed to load page data:', err);
            setError('Failed to load recipients');
        } finally {
            setIsLoading(false);
        }
    }, [accountId]);

    useEffect(() => {
        if (accountId) loadPageData();
    }, [accountId, loadPageData]);


    // ── Recipient management ──────────────────────────────────────────────────

    const handleAddRecipient = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newEmail || !accountId) return;
        if (!newEmail.includes('@')) {
            setError('Invalid email address');
            return;
        }
        try {
            setIsSubmitting(true);
            setError(null);
            await api.alerts.addRecipient(accountId, newEmail);
            setNewEmail('');
            // Optimistic add — no need to reload all data
            setRecipients((prev) => [...prev, newEmail]);
            setSubscriptions((prev) => ({ ...prev, [newEmail]: new Set() }));
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
            setRecipients((prev) => prev.filter((e) => e !== emailToDelete));
            setSubscriptions((prev) => {
                const next = { ...prev };
                delete next[emailToDelete];
                return next;
            });
            setExpanded((prev) => {
                const next = new Set(prev);
                next.delete(emailToDelete);
                return next;
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to remove recipient');
        }
    };


    // ── Subscription toggles ──────────────────────────────────────────────────

    const toggleKey = (email: string, propertyId: string) => `${email}__${propertyId}`;

    const handleToggleSubscription = async (email: string, propertyId: string) => {
        if (!accountId) return;
        const key = toggleKey(email, propertyId);

        // Debounce: ignore click if already toggling
        if (toggling[key]) return;

        const isCurrentlySubscribed = subscriptions[email]?.has(propertyId) ?? false;

        try {
            setToggling((prev) => ({ ...prev, [key]: true }));

            // Optimistic update
            setSubscriptions((prev) => {
                const emailSet = new Set(prev[email] ?? []);
                if (isCurrentlySubscribed) {
                    emailSet.delete(propertyId);
                } else {
                    emailSet.add(propertyId);
                }
                return { ...prev, [email]: emailSet };
            });

            if (isCurrentlySubscribed) {
                await api.alerts.removeSubscription(accountId, email, propertyId);
            } else {
                await api.alerts.addSubscription(accountId, email, propertyId);
            }
        } catch (err) {
            // Revert optimistic update on failure
            setSubscriptions((prev) => {
                const emailSet = new Set(prev[email] ?? []);
                if (isCurrentlySubscribed) {
                    emailSet.add(propertyId);
                } else {
                    emailSet.delete(propertyId);
                }
                return { ...prev, [email]: emailSet };
            });
            setError(err instanceof Error ? err.message : 'Failed to update subscription');
        } finally {
            setToggling((prev) => ({ ...prev, [key]: false }));
        }
    };

    const toggleExpanded = (email: string) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(email)) {
                next.delete(email);
            } else {
                next.add(email);
            }
            return next;
        });
    };


    // ── Render ────────────────────────────────────────────────────────────────

    if (isLoading) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="text-center">
                    <div className="inline-block w-8 h-8 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin mb-4"></div>
                    <p className="text-gray-500 font-medium">Loading settings...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Header */}
            <div className="flex justify-between items-end border-b border-gray-200 pb-8">
                <div className="space-y-4">
                    <button
                        onClick={() => navigate(`/dashboard/${accountId}`)}
                        className="px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-gray-500 hover:text-gray-900 transition-colors flex items-center gap-2 group"
                    >
                        <span className="group-hover:-translate-x-1 transition-transform">←</span>
                        Portfolio Overview
                    </button>
                    <div>
                        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">Alert Settings</h1>
                        <p className="text-gray-500 text-sm font-medium mt-1">
                            {accountEmail}
                        </p>
                    </div>
                </div>
            </div>

            {/* Error banner */}
            {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <p className="text-red-600 font-medium text-sm">❌ {error}</p>
                </div>
            )}

            {/* Recipients section */}
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-6 py-5 border-b border-gray-100">
                    <h2 className="text-[10px] font-black uppercase tracking-widest text-gray-500">
                        Alert Recipients
                    </h2>
                    <p className="text-xs text-gray-400 font-medium mt-1">
                        Emails that receive alert notifications for this account. Expand a recipient to configure their property subscriptions.
                    </p>
                </div>

                {/* Add recipient form */}
                <div className="px-6 py-5 border-b border-gray-100">
                    <form onSubmit={handleAddRecipient} className="flex gap-3">
                        <input
                            id="settings-email-input"
                            type="email"
                            value={newEmail}
                            onChange={(e) => setNewEmail(e.target.value)}
                            placeholder="recipient@company.com"
                            disabled={isSubmitting}
                            className="flex-1 bg-gray-50 border border-gray-200 text-gray-900 text-sm font-medium rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all placeholder:text-gray-300 disabled:opacity-50"
                        />
                        <button
                            id="settings-add-btn"
                            type="submit"
                            disabled={isSubmitting || !newEmail}
                            className="bg-gray-900 hover:bg-black disabled:opacity-40 text-white text-[10px] font-black uppercase tracking-widest px-5 py-2.5 rounded-lg transition-all"
                        >
                            {isSubmitting ? '…' : 'Add'}
                        </button>
                    </form>
                </div>

                {/* Recipients list */}
                {recipients.length === 0 ? (
                    <div className="px-6 py-12 text-center">
                        <p className="text-gray-400 text-sm font-medium">No recipients configured for this account.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {recipients.map((email) => {
                            const isExpanded = expanded.has(email);
                            const subCount = subscriptions[email]?.size ?? 0;

                            return (
                                <div key={email}>
                                    {/* Recipient row */}
                                    <div className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
                                        <button
                                            onClick={() => toggleExpanded(email)}
                                            className="flex items-center gap-3 min-w-0 flex-1 text-left"
                                        >
                                            <div className={`w-2 h-2 rounded-full shrink-0 transition-colors ${isExpanded ? 'bg-gray-900' : 'bg-gray-200'}`} />
                                            <span className="text-sm font-semibold text-gray-900 truncate">{email}</span>
                                            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                                                {subCount} subscribed
                                            </span>
                                            <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">
                                                {isExpanded ? '▲' : '▼'}
                                            </span>
                                        </button>
                                        <button
                                            onClick={() => handleDeleteRecipient(email)}
                                            className="text-gray-300 hover:text-red-500 p-1.5 rounded transition-colors ml-3 shrink-0"
                                            title="Remove recipient"
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                            </svg>
                                        </button>
                                    </div>

                                    {/* Property subscriptions panel */}
                                    {isExpanded && (
                                        <div className="bg-gray-50 border-t border-gray-100 px-6 pb-4 pt-3">
                                            {properties.length === 0 ? (
                                                <p className="text-xs text-gray-400 font-medium py-4 text-center">
                                                    No properties found — run the pipeline first.
                                                </p>
                                            ) : (
                                                <div className="space-y-1 pt-2">
                                                    <p className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-3">
                                                        Property Subscriptions — auto-saves on toggle
                                                    </p>
                                                    {properties.map((prop) => {
                                                        const isSubscribed = subscriptions[email]?.has(prop.id) ?? false;
                                                        const key = toggleKey(email, prop.id);
                                                        const isToggling = toggling[key] ?? false;

                                                        return (
                                                            <div
                                                                key={prop.id}
                                                                className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-white transition-colors"
                                                            >
                                                                <span className="text-sm text-gray-700 font-medium truncate pr-4">{prop.name}</span>
                                                                {isToggling ? (
                                                                    <div className="w-3 h-3 border-2 border-gray-200 border-t-gray-700 rounded-full animate-spin shrink-0" />
                                                                ) : (
                                                                    <button
                                                                        onClick={() => handleToggleSubscription(email, prop.id)}
                                                                        role="switch"
                                                                        aria-checked={isSubscribed}
                                                                        className={[
                                                                            'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
                                                                            'transition-colors duration-150 ease-in-out focus:outline-none',
                                                                            isSubscribed ? 'bg-gray-900' : 'bg-gray-200',
                                                                        ].join(' ')}
                                                                    >
                                                                        <span
                                                                            className={[
                                                                                'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow',
                                                                                'transform transition duration-150 ease-in-out',
                                                                                isSubscribed ? 'translate-x-4' : 'translate-x-0',
                                                                            ].join(' ')}
                                                                        />
                                                                    </button>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
