import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from './lib/supabaseClient';
import api from './api';
import { SessionContext } from './SessionContext';

/**
 * SESSION PROVIDER
 *
 * Manages two independent layers of state:
 *
 * 1. SUPABASE AUTH SESSION (App Identity):
 *    - Listens to onAuthStateChange for real-time session updates.
 *    - Exposes isLoggedIn, supabaseUser, supabaseSession.
 *    - signIn/signOut delegate to Supabase Auth.
 *
 * 2. PORTFOLIO SELECTION (UI State):
 *    - Reads selected_account_id/selected_account_email from localStorage.
 *    - Also picks up account_id + email from URL params (OAuth bootstrap redirect).
 *    - connectGoogleAccount() initiates the GSC OAuth bootstrap flow.
 *    - deselectAccount() clears the selection.
 */
export function SessionProvider({ children }: { children: ReactNode }) {
    // ── Supabase Auth State ────────────────────────────────────────
    const [supabaseSession, setSupabaseSession] = useState<Session | null>(null);
    const [supabaseUser, setSupabaseUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // ── Portfolio Selection State ──────────────────────────────────
    const [accountId, setAccountId] = useState<string | null>(
        localStorage.getItem('selected_account_id')
    );
    const [email, setEmail] = useState<string | null>(
        localStorage.getItem('selected_account_email')
    );
    const [error, setError] = useState<string | null>(null);

    // ── Initialize Supabase session on mount ──────────────────────
    useEffect(() => {
        // Get the current session (if any exists from a previous visit)
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSupabaseSession(session);
            setSupabaseUser(session?.user ?? null);
        });

        // Listen for session changes (login, logout, token refresh)
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            (_event, session) => {
                setSupabaseSession(session);
                setSupabaseUser(session?.user ?? null);
                setIsLoading(false);
            }
        );

        return () => subscription.unsubscribe();
    }, []);

    // ── Handle backend OAuth redirect params (GSC bootstrap flow) ─
    useEffect(() => {
        const handleRedirectParams = () => {
            const params = new URLSearchParams(window.location.search);
            const redirectAccountId = params.get('account_id');
            const redirectEmail = params.get('email');
            const oauthError = params.get('auth_error');

            if (oauthError) {
                setError(oauthError);
                window.history.replaceState({}, document.title, window.location.pathname);
                setIsLoading(false);
                return;
            }

            if (params.get('logout') === 'true') {
                deselectAccount();
                window.history.replaceState({}, document.title, window.location.pathname);
                return;
            }

            if (redirectAccountId && redirectEmail) {
                // A new GSC account was just connected via OAuth bootstrap.
                localStorage.setItem('selected_account_id', redirectAccountId);
                localStorage.setItem('selected_account_email', redirectEmail);
                setAccountId(redirectAccountId);
                setEmail(redirectEmail);
                window.history.replaceState({}, document.title, window.location.pathname);
            }

            setIsLoading(false);
        };

        handleRedirectParams();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── Cross-tab sync: if another tab deselects the account ─────
    useEffect(() => {
        const handleStorage = (e: StorageEvent) => {
            if (e.key === 'selected_account_id' && !e.newValue) {
                setAccountId(null);
                setEmail(null);
            }
        };
        window.addEventListener('storage', handleStorage);
        return () => window.removeEventListener('storage', handleStorage);
    }, []);

    // ── Supabase Auth Actions ─────────────────────────────────────
    const signIn = async (emailInput: string, passwordInput: string) => {
        const { error: authError } = await supabase.auth.signInWithPassword({
            email: emailInput,
            password: passwordInput,
        });
        if (authError) throw authError;
    };

    const signOut = async () => {
        // Clears Supabase session only — DB data is untouched.
        await supabase.auth.signOut();
        deselectAccount(); // Also clear portfolio selection on logout
    };

    // ── Portfolio Selection Actions ───────────────────────────────
    /**
     * Initiate Google OAuth to connect a new GSC account to the system.
     * This is BOOTSTRAP, not user auth. Requires the user to be logged in
     * so the backend can link the GSC account to the correct Supabase user.
     */
    const connectGoogleAccount = async () => {
        try {
            setIsLoading(true);
            const { url } = await api.auth.getAuthUrl();
            window.location.href = url;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to start Google account connection');
            setIsLoading(false);
        }
    };

    /**
     * Clear the currently selected portfolio from this browser session.
     * This is a UI deselection — not a security logout.
     */
    const deselectAccount = () => {
        localStorage.removeItem('selected_account_id');
        localStorage.removeItem('selected_account_email');
        setAccountId(null);
        setEmail(null);
    };

    return (
        <SessionContext.Provider value={{
            // App Identity
            isLoggedIn: !!supabaseSession,
            supabaseUser,
            supabaseSession,
            signIn,
            signOut,
            // Portfolio Selection
            accountId,
            email,
            hasSelectedAccount: !!accountId,
            isLoading,
            error,
            connectGoogleAccount,
            deselectAccount,
        }}>
            {children}
        </SessionContext.Provider>
    );
}
