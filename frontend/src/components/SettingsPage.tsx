import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../AuthContext';
import type { PropertySummary } from '../types';

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
    const { accountId, email: accountEmail } = useAuth();
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


    // ── Data fetching ─────────────────────────────────────────────────────────

    const fetchProperties = useCallback(async () => {
        if (!accountId) return;
        try {
            const data = await api.dashboard.getSummary(accountId);
            if (data.websites) {
                const flat = data.websites.flatMap((w) =>
                    w.properties.map((p: PropertySummary) => ({
                        id: p.property_id,
                        name: p.property_name || p.property_id,
                    }))
                );
                setProperties(flat);
            }
        } catch {
            // Properties unavailable is non-fatal — toggles just won't render
        }
    }, [accountId]);

    const fetchSubscriptionsForEmail = useCallback(async (email: string) => {
        if (!accountId) return;
        try {
            const data = await api.alerts.getSubscriptions(accountId, email);
            setSubscriptions((prev) => ({
                ...prev,
                [email]: new Set(data.property_ids),
            }));
        } catch {
            setSubscriptions((prev) => ({ ...prev, [email]: new Set() }));
        }
    }, [accountId]);

    const fetchRecipients = useCallback(async () => {
        if (!accountId) return;
        try {
            setIsLoading(true);
            const data = await api.alerts.getRecipients(accountId);
            setRecipients(data.recipients);
            // Load subscriptions for all recipients in parallel
            await Promise.all(data.recipients.map(fetchSubscriptionsForEmail));
        } catch (err) {
            console.error('Failed to fetch recipients:', err);
            setError('Failed to load recipients');
        } finally {
            setIsLoading(false);
        }
    }, [accountId, fetchSubscriptionsForEmail]);

    useEffect(() => {
        if (accountId) {
            fetchProperties();
            fetchRecipients();
        }
    }, [accountId, fetchProperties, fetchRecipients]);


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
            <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-2 border-gray-200 border-t-gray-900 rounded-full animate-spin"></div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            {/* Header */}
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

            {/* Authentication card */}
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

            {/* Alert Notifications card */}
            <div className="bg-white rounded-lg p-8 border border-gray-200 shadow-sm">
                <h2 className="text-xs font-bold text-gray-500 uppercase tracking-widest mb-2">Alert Notifications</h2>
                <p className="text-gray-500 text-sm font-medium mb-8">
                    Add recipients and configure which properties each recipient monitors.
                </p>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-md mb-8 text-xs font-bold uppercase tracking-tight">
                        {error}
                    </div>
                )}

                {/* Add recipient form */}
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

                {/* Recipients list */}
                <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-4 leading-relaxed">
                    Distribution List
                </h3>
                <div className="space-y-3">
                    {recipients.length === 0 ? (
                        <div className="text-center py-12 border border-gray-100 rounded-lg text-gray-500 font-medium italic text-sm">
                            No recipients configured.
                        </div>
                    ) : (
                        recipients.map((email) => {
                            const subscribedIds = subscriptions[email] ?? new Set();
                            const isExpanded = expanded.has(email);
                            const subscribedCount = subscribedIds.size;

                            return (
                                <div
                                    key={email}
                                    className="border border-gray-200 rounded-md shadow-sm overflow-hidden"
                                >
                                    {/* Recipient row header */}
                                    <div className="flex items-center justify-between bg-gray-50 px-4 py-3">
                                        <div className="flex items-center gap-3 min-w-0">
                                            <span className="text-sm font-semibold text-gray-900 truncate">{email}</span>
                                            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                                                {subscribedCount} / {properties.length} propert{properties.length === 1 ? 'y' : 'ies'}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-2 ml-3 shrink-0">
                                            {/* Expand/collapse property toggles */}
                                            {properties.length > 0 && (
                                                <button
                                                    onClick={() => toggleExpanded(email)}
                                                    className="text-xs font-bold text-gray-500 hover:text-gray-900 uppercase tracking-widest px-3 py-1.5 rounded border border-gray-200 hover:border-gray-400 transition-all"
                                                >
                                                    {isExpanded ? 'Confirm' : 'Configure'}
                                                </button>
                                            )}
                                            {/* Delete recipient */}
                                            <button
                                                onClick={() => handleDeleteRecipient(email)}
                                                className="text-gray-400 hover:text-red-600 p-2 rounded transition-colors"
                                                title="Remove recipient"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                    <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>

                                    {/* Expandable property toggles */}
                                    {isExpanded && properties.length > 0 && (
                                        <div className="border-t border-gray-200 bg-white divide-y divide-gray-100">
                                            {properties.map((prop) => {
                                                const isSubscribed = subscribedIds.has(prop.id);
                                                const key = toggleKey(email, prop.id);
                                                const isToggling = toggling[key] ?? false;

                                                return (
                                                    <div
                                                        key={prop.id}
                                                        className="flex items-center justify-between px-4 py-3"
                                                    >
                                                        <span className="text-sm text-gray-700 font-medium truncate pr-4">
                                                            {prop.name}
                                                        </span>
                                                        <button
                                                            onClick={() => handleToggleSubscription(email, prop.id)}
                                                            disabled={isToggling}
                                                            className={[
                                                                'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
                                                                'transition-colors duration-150 ease-in-out focus:outline-none',
                                                                'disabled:opacity-50 disabled:cursor-not-allowed',
                                                                isSubscribed ? 'bg-gray-900' : 'bg-gray-200',
                                                            ].join(' ')}
                                                            role="switch"
                                                            aria-checked={isSubscribed}
                                                            title={isSubscribed ? 'Unsubscribe' : 'Subscribe'}
                                                        >
                                                            <span
                                                                className={[
                                                                    'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow',
                                                                    'transform transition duration-150 ease-in-out',
                                                                    isSubscribed ? 'translate-x-4' : 'translate-x-0',
                                                                ].join(' ')}
                                                            />
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
