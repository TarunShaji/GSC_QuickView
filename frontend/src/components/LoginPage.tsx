import { useState } from 'react';
import { supabase } from '../lib/supabaseClient';

interface LoginPageProps {
    onLoginSuccess?: () => void;
}

/**
 * LOGIN PAGE
 *
 * Authenticates the operator via Supabase Auth (email + password).
 * This is app-level identity — not the Google OAuth GSC connection.
 *
 * On success: Supabase stores the session automatically.
 * SessionProvider picks it up on the next render via onAuthStateChange.
 */
export default function LoginPage({ onLoginSuccess }: LoginPageProps) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });

        if (authError) {
            setError(authError.message);
            setIsLoading(false);
            return;
        }

        onLoginSuccess?.();
    };

    return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-10 w-full max-w-sm">
                {/* Logo mark */}
                <div className="text-center mb-10">
                    <div className="w-12 h-12 bg-gray-900 rounded-xl flex items-center justify-center mx-auto mb-5">
                        <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l9 4.5v9L12 21l-9-4.5v-9L12 3z" />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-black text-gray-900 tracking-tight">GSC Radar</h1>
                    <p className="text-gray-400 text-sm font-medium mt-1">Sign in to your account</p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 text-xs font-bold px-4 py-3 rounded-lg mb-6 uppercase tracking-wider">
                        {error}
                    </div>
                )}

                <form onSubmit={handleLogin} className="space-y-4">
                    <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">
                            Email
                        </label>
                        <input
                            id="login-email"
                            type="email"
                            required
                            autoComplete="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            className="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-900 font-medium focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all"
                            placeholder="you@company.com"
                        />
                    </div>
                    <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">
                            Password
                        </label>
                        <input
                            id="login-password"
                            type="password"
                            required
                            autoComplete="current-password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            className="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-900 font-medium focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all"
                            placeholder="••••••••"
                        />
                    </div>

                    <button
                        id="login-submit"
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-gray-900 hover:bg-black disabled:opacity-50 text-white text-xs font-black uppercase tracking-widest py-4 rounded-lg transition-all mt-2"
                    >
                        {isLoading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>

                <p className="text-center text-gray-400 text-[10px] font-bold uppercase tracking-widest mt-8">
                    GSC Radar — Internal Access Only
                </p>
            </div>
        </div>
    );
}
