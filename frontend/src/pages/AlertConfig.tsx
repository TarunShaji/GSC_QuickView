import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import type { Account, Website, Property } from '../types';

// ─── Types ─────────────────────────────────────────────────────────────────────

interface FlatProperty {
    id: string;
    name: string;
    websiteDomain: string;
}

// email → Set<property_id>
type SubscriptionMap = Record<string, Set<string>>;
// `${email}__${propertyId}` → bool
type TogglingMap = Record<string, boolean>;

// ─── Small sub-components ────────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
    return (
        <h2 className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-4">
            {children}
        </h2>
    );
}

function InlineError({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-xs font-bold uppercase tracking-tight mb-6">
            {message}
        </div>
    );
}

function Spinner({ small }: { small?: boolean }) {
    return (
        <div
            className={[
                'border-2 border-gray-200 border-t-gray-700 rounded-full animate-spin',
                small ? 'w-3 h-3' : 'w-6 h-6',
            ].join(' ')}
        />
    );
}

// ─── Toggle Switch ────────────────────────────────────────────────────────────

function ToggleSwitch({
    checked,
    disabled,
    onChange,
}: {
    checked: boolean;
    disabled: boolean;
    onChange: () => void;
}) {
    return (
        <button
            onClick={onChange}
            disabled={disabled}
            role="switch"
            aria-checked={checked}
            className={[
                'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
                'transition-colors duration-150 ease-in-out focus:outline-none',
                'disabled:opacity-40 disabled:cursor-not-allowed',
                checked ? 'bg-gray-900' : 'bg-gray-200',
            ].join(' ')}
        >
            <span
                className={[
                    'pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow',
                    'transform transition duration-150 ease-in-out',
                    checked ? 'translate-x-4' : 'translate-x-0',
                ].join(' ')}
            />
        </button>
    );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AlertConfig() {
    const navigate = useNavigate();

    // Account selection
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [selectedAccountId, setSelectedAccountId] = useState<string>('');
    const [accountsLoading, setAccountsLoading] = useState(true);

    // Recipients
    const [recipients, setRecipients] = useState<string[]>([]);
    const [selectedEmail, setSelectedEmail] = useState<string | null>(null);
    const [newEmail, setNewEmail] = useState('');
    const [recipientsLoading, setRecipientsLoading] = useState(false);
    const [isAdding, setIsAdding] = useState(false);
    const [recipientError, setRecipientError] = useState<string | null>(null);

    // Properties (flat, grouped by website for display)
    const [properties, setProperties] = useState<FlatProperty[]>([]);
    const [propertiesLoading, setPropertiesLoading] = useState(false);

    // Subscriptions for the selected recipient
    const [subscriptions, setSubscriptions] = useState<SubscriptionMap>({});
    const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
    const [toggling, setToggling] = useState<TogglingMap>({});
    const [subscriptionError, setSubscriptionError] = useState<string | null>(null);

    // ── Load accounts on mount ───────────────────────────────────────────────
    useEffect(() => {
        api.accounts.getAll()
            .then((data) => {
                setAccounts(data);
                if (data.length > 0) {
                    setSelectedAccountId(data[0].id);
                }
            })
            .catch(() => { /* handled below by empty state */ })
            .finally(() => setAccountsLoading(false));
    }, []);

    // ── Load properties when account changes ─────────────────────────────────
    const fetchProperties = useCallback(async (accountId: string) => {
        if (!accountId) return;
        setPropertiesLoading(true);
        try {
            const websites: Website[] = await api.websites.getAll(accountId);
            const propertyLists = await Promise.all(
                websites.map((w) =>
                    api.websites.getProperties(accountId, w.id).then(
                        (props: Property[]) =>
                            props.map((p) => ({
                                id: p.id,
                                name: p.site_url,
                                websiteDomain: w.base_domain,
                            }))
                    ).catch(() => [] as FlatProperty[])
                )
            );
            setProperties(propertyLists.flat());
        } catch {
            setProperties([]);
        } finally {
            setPropertiesLoading(false);
        }
    }, []);

    // ── Load recipients when account changes ─────────────────────────────────
    const fetchRecipients = useCallback(async (accountId: string) => {
        if (!accountId) return;
        setRecipientsLoading(true);
        setRecipientError(null);
        setSelectedEmail(null);
        setSubscriptions({});
        try {
            const data = await api.alerts.getRecipients(accountId);
            setRecipients(data.recipients);
        } catch {
            setRecipientError('Failed to load recipients.');
        } finally {
            setRecipientsLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!selectedAccountId) return;
        fetchRecipients(selectedAccountId);
        fetchProperties(selectedAccountId);
    }, [selectedAccountId, fetchRecipients, fetchProperties]);

    // ── Load subscriptions when a recipient is selected ───────────────────────
    const fetchSubscriptions = useCallback(async (accountId: string, email: string) => {
        setSubscriptionsLoading(true);
        setSubscriptionError(null);
        try {
            const data = await api.alerts.getSubscriptions(accountId, email);
            setSubscriptions((prev) => ({
                ...prev,
                [email]: new Set(data.property_ids),
            }));
        } catch {
            setSubscriptions((prev) => ({ ...prev, [email]: new Set() }));
        } finally {
            setSubscriptionsLoading(false);
        }
    }, []);

    const handleSelectEmail = (email: string) => {
        if (selectedEmail === email) {
            setSelectedEmail(null);
            return;
        }
        setSelectedEmail(email);
        if (!subscriptions[email]) {
            fetchSubscriptions(selectedAccountId, email);
        }
    };

    // ── Add recipient ─────────────────────────────────────────────────────────
    const handleAddRecipient = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newEmail || !selectedAccountId) return;
        if (!newEmail.includes('@')) {
            setRecipientError('Enter a valid email address.');
            return;
        }
        setIsAdding(true);
        setRecipientError(null);
        try {
            await api.alerts.addRecipient(selectedAccountId, newEmail);
            setNewEmail('');
            await fetchRecipients(selectedAccountId);
        } catch (err) {
            const msg = err instanceof Error ? err.message : '';
            if (msg.includes('409') || msg.includes('duplicate') || msg.includes('already')) {
                setRecipientError('This email is already a recipient for this account.');
            } else {
                setRecipientError('Failed to add recipient.');
            }
        } finally {
            setIsAdding(false);
        }
    };

    // ── Delete recipient ──────────────────────────────────────────────────────
    const handleDeleteRecipient = async (email: string) => {
        if (!selectedAccountId) return;
        setRecipientError(null);
        try {
            await api.alerts.removeRecipient(selectedAccountId, email);
            setRecipients((prev) => prev.filter((e) => e !== email));
            setSubscriptions((prev) => {
                const next = { ...prev };
                delete next[email];
                return next;
            });
            if (selectedEmail === email) setSelectedEmail(null);
        } catch {
            setRecipientError('Failed to remove recipient.');
        }
    };

    // ── Toggle subscription ───────────────────────────────────────────────────
    const toggleKey = (email: string, propertyId: string) => `${email}__${propertyId}`;

    const handleToggle = async (email: string, propertyId: string) => {
        if (!selectedAccountId) return;
        const key = toggleKey(email, propertyId);
        if (toggling[key]) return;

        const isSubscribed = subscriptions[email]?.has(propertyId) ?? false;
        setToggling((prev) => ({ ...prev, [key]: true }));
        // Optimistic update
        setSubscriptions((prev) => {
            const s = new Set(prev[email] ?? []);
            isSubscribed ? s.delete(propertyId) : s.add(propertyId);
            return { ...prev, [email]: s };
        });

        try {
            if (isSubscribed) {
                await api.alerts.removeSubscription(selectedAccountId, email, propertyId);
            } else {
                await api.alerts.addSubscription(selectedAccountId, email, propertyId);
            }
        } catch {
            // Revert on failure
            setSubscriptions((prev) => {
                const s = new Set(prev[email] ?? []);
                isSubscribed ? s.add(propertyId) : s.delete(propertyId);
                return { ...prev, [email]: s };
            });
            setSubscriptionError('Failed to update subscription. Please try again.');
        } finally {
            setToggling((prev) => ({ ...prev, [key]: false }));
        }
    };

    // ── Group properties by website domain ────────────────────────────────────
    const propertiesByDomain = properties.reduce<Record<string, FlatProperty[]>>(
        (acc, p) => {
            const key = p.websiteDomain;
            acc[key] = acc[key] ? [...acc[key], p] : [p];
            return acc;
        },
        {}
    );

    // ── Render ────────────────────────────────────────────────────────────────
    if (accountsLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <Spinner />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Top bar */}
            <div className="bg-white border-b border-gray-100 px-6 py-5 flex items-center gap-4">
                <button
                    onClick={() => navigate('/')}
                    className="text-[10px] font-black uppercase tracking-widest text-gray-400 hover:text-gray-900 transition-colors flex items-center gap-2 group"
                >
                    <span className="group-hover:-translate-x-1 transition-transform inline-block">←</span>
                    All Accounts
                </button>
                <span className="text-gray-200">|</span>
                <h1 className="text-sm font-black uppercase tracking-widest text-gray-900">Alert Config</h1>
            </div>

            <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">

                {/* Account selector */}
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                    <SectionLabel>Account</SectionLabel>
                    {accounts.length === 0 ? (
                        <p className="text-sm text-gray-400 font-medium">No accounts found.</p>
                    ) : (
                        <select
                            id="alert-config-account-select"
                            value={selectedAccountId}
                            onChange={(e) => setSelectedAccountId(e.target.value)}
                            className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-sm font-semibold text-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all"
                        >
                            {accounts.map((a) => (
                                <option key={a.id} value={a.id}>{a.google_email}</option>
                            ))}
                        </select>
                    )}
                </div>

                {/* Recipients section */}
                <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
                    <SectionLabel>Alert Recipients</SectionLabel>
                    <p className="text-xs font-medium text-gray-400 mb-6">
                        Add emails that should receive alert notifications for this account. Click a recipient to configure their property subscriptions.
                    </p>

                    <InlineError message={recipientError} />

                    {/* Add recipient form */}
                    <form onSubmit={handleAddRecipient} className="flex gap-3 mb-8">
                        <input
                            id="alert-config-email-input"
                            type="email"
                            value={newEmail}
                            onChange={(e) => setNewEmail(e.target.value)}
                            placeholder="recipient@company.com"
                            disabled={!selectedAccountId || isAdding}
                            className="flex-1 bg-gray-50 border border-gray-200 text-gray-900 text-sm font-medium rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all placeholder:text-gray-300 disabled:opacity-50"
                        />
                        <button
                            id="alert-config-add-btn"
                            type="submit"
                            disabled={!selectedAccountId || isAdding || !newEmail}
                            className="bg-gray-900 hover:bg-black disabled:opacity-40 text-white text-[10px] font-black uppercase tracking-widest px-6 py-3 rounded-lg transition-all flex items-center gap-2"
                        >
                            {isAdding ? <Spinner small /> : null}
                            Add
                        </button>
                    </form>

                    {/* Recipients list */}
                    {recipientsLoading ? (
                        <div className="flex justify-center py-8"><Spinner /></div>
                    ) : recipients.length === 0 ? (
                        <div className="text-center py-12 border border-dashed border-gray-200 rounded-xl text-gray-400 text-sm font-medium">
                            No recipients configured for this account.
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {recipients.map((email) => {
                                const isSelected = selectedEmail === email;
                                const subCount = subscriptions[email]?.size ?? 0;
                                return (
                                    <div
                                        key={email}
                                        className={[
                                            'rounded-xl border transition-all duration-150',
                                            isSelected
                                                ? 'border-gray-900 bg-gray-50'
                                                : 'border-gray-100 bg-white hover:border-gray-200',
                                        ].join(' ')}
                                    >
                                        <div
                                            className="flex items-center justify-between px-4 py-3 cursor-pointer"
                                            onClick={() => handleSelectEmail(email)}
                                        >
                                            <div className="flex items-center gap-3 min-w-0">
                                                <div
                                                    className={[
                                                        'w-2 h-2 rounded-full shrink-0 transition-colors',
                                                        isSelected ? 'bg-gray-900' : 'bg-gray-200',
                                                    ].join(' ')}
                                                />
                                                <span className="text-sm font-semibold text-gray-900 truncate">
                                                    {email}
                                                </span>
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider whitespace-nowrap">
                                                    {subCount} subscribed
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 ml-3 shrink-0">
                                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                                                    {isSelected ? '▲ close' : '▼ configure'}
                                                </span>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteRecipient(email);
                                                    }}
                                                    className="text-gray-300 hover:text-red-500 p-1.5 rounded transition-colors ml-1"
                                                    title="Remove recipient"
                                                >
                                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                                        <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                                                    </svg>
                                                </button>
                                            </div>
                                        </div>

                                        {/* Property subscriptions panel */}
                                        {isSelected && (
                                            <div className="border-t border-gray-100 px-4 pb-4 pt-3">
                                                <InlineError message={subscriptionError} />

                                                {subscriptionsLoading ? (
                                                    <div className="flex justify-center py-6"><Spinner /></div>
                                                ) : propertiesLoading ? (
                                                    <div className="flex justify-center py-6"><Spinner /></div>
                                                ) : properties.length === 0 ? (
                                                    <p className="text-xs text-gray-400 font-medium py-4 text-center">
                                                        No properties found — run the pipeline first.
                                                    </p>
                                                ) : (
                                                    <div className="space-y-4">
                                                        <p className="text-[10px] font-black uppercase tracking-widest text-gray-400">
                                                            Property Subscriptions — auto-saves on toggle
                                                        </p>
                                                        {Object.entries(propertiesByDomain).map(([domain, props]) => (
                                                            <div key={domain}>
                                                                <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2 pl-1 border-l-2 border-gray-200">
                                                                    {domain}
                                                                </p>
                                                                <div className="space-y-1">
                                                                    {props.map((prop) => {
                                                                        const isSubscribed = subscriptions[email]?.has(prop.id) ?? false;
                                                                        const key = toggleKey(email, prop.id);
                                                                        const isToggling = toggling[key] ?? false;
                                                                        return (
                                                                            <div
                                                                                key={prop.id}
                                                                                className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-gray-50 transition-colors"
                                                                            >
                                                                                <span className="text-sm text-gray-700 font-medium truncate pr-4">
                                                                                    {prop.name}
                                                                                </span>
                                                                                {isToggling ? (
                                                                                    <Spinner small />
                                                                                ) : (
                                                                                    <ToggleSwitch
                                                                                        checked={isSubscribed}
                                                                                        disabled={isToggling}
                                                                                        onChange={() => handleToggle(email, prop.id)}
                                                                                    />
                                                                                )}
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </div>
                                                            </div>
                                                        ))}
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
        </div>
    );
}
