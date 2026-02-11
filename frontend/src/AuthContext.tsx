import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import api from './api';

interface AuthContextType {
    accountId: string | null;
    email: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: () => void;
    logout: () => void;
    error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [accountId, setAccountId] = useState<string | null>(localStorage.getItem('gsc_account_id'));
    const [email, setEmail] = useState<string | null>(localStorage.getItem('gsc_email'));
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const checkUrlParams = () => {
            const params = new URLSearchParams(window.location.search);
            const urlAccountId = params.get('account_id');
            const urlEmail = params.get('email');
            const authError = params.get('auth_error');

            if (authError) {
                setError(authError);
                setIsLoading(false);
                window.history.replaceState({}, document.title, window.location.pathname);
                return;
            }

            if (urlAccountId && urlEmail) {
                localStorage.setItem('gsc_account_id', urlAccountId);
                localStorage.setItem('gsc_email', urlEmail);

                setAccountId(urlAccountId);
                setEmail(urlEmail);

                // Clear URL params
                window.history.replaceState({}, document.title, window.location.pathname);
                setIsLoading(false);
            } else {
                setIsLoading(false);
            }
        };

        checkUrlParams();
    }, []);

    const login = async () => {
        try {
            setIsLoading(true);
            const { url } = await api.auth.getAuthUrl();
            window.location.href = url;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to start login flow');
            setIsLoading(false);
        }
    };

    const logout = () => {
        localStorage.removeItem('gsc_account_id');
        localStorage.removeItem('gsc_email');
        setAccountId(null);
        setEmail(null);
    };

    return (
        <AuthContext.Provider value={{
            accountId,
            email,
            isAuthenticated: !!accountId,
            isLoading,
            login,
            logout,
            error
        }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
