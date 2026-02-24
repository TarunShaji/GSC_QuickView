import { createContext, useContext } from 'react';
import type { Session, User } from '@supabase/supabase-js';

/**
 * SESSION CONTEXT
 *
 * This context manages TWO separate concepts:
 *
 * 1. APP IDENTITY (Supabase Auth):
 *    - `isLoggedIn`: Whether a Supabase user session exists.
 *    - `supabaseUser`: The authenticated Supabase user object.
 *    - `supabaseSession`: Full session including access_token (JWT) for API calls.
 *    - `signIn/signOut`: App-level login/logout via Supabase Auth.
 *
 * 2. PORTFOLIO SELECTION (UI state):
 *    - `accountId`: The currently selected GSC account UUID.
 *    - `hasSelectedAccount`: Whether an account has been selected.
 *    - `connectGoogleAccount()`: Bootstrap — initiate Google OAuth to link a GSC account.
 *    - `deselectAccount()`: Clear the current portfolio selection.
 *
 * These two layers are independent:
 *   - A user can be logged in but not have selected a portfolio yet.
 *   - A user can log out while keeping the DB data intact.
 */

export interface SessionContextType {
    // ── App Identity (Supabase Auth) ──────────────────────────────
    /** True if a valid Supabase session exists. */
    isLoggedIn: boolean;
    /** The authenticated Supabase user, or null. */
    supabaseUser: User | null;
    /** Full Supabase session including access_token JWT. */
    supabaseSession: Session | null;
    /** Sign in with email + password via Supabase Auth. */
    signIn: (email: string, password: string) => Promise<void>;
    /** Sign out — clears Supabase session only, does not touch DB. */
    signOut: () => Promise<void>;

    // ── Portfolio Selection (UI state) ────────────────────────────
    /** The currently selected GSC account UUID. Comes from localStorage. */
    accountId: string | null;
    /** Email for the currently selected account. */
    email: string | null;
    /** True if an account has been selected in this session. */
    hasSelectedAccount: boolean;
    /** True while the provider is initializing (checking session + URL params). */
    isLoading: boolean;
    /** Error message from OAuth bootstrap or session initialization. */
    error: string | null;
    /** Initiate the Google OAuth flow to connect a new GSC account (bootstrap, not auth). */
    connectGoogleAccount: () => void;
    /** Clear the portfolio selection from this session. */
    deselectAccount: () => void;
}

export const SessionContext = createContext<SessionContextType | undefined>(undefined);

export function useSession() {
    const context = useContext(SessionContext);
    if (!context) {
        throw new Error('useSession must be used within a SessionProvider');
    }
    return context;
}
