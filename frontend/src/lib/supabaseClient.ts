import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnonKey) {
    console.error(
        '[Supabase] Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY env vars. ' +
        'Add them to frontend/.env'
    );
}

/**
 * Supabase JS client — singleton instance for this app.
 *
 * Usage:
 *   import { supabase } from '../lib/supabaseClient';
 *   const { data, error } = await supabase.auth.signInWithPassword({ email, password });
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
        persistSession: true,       // persist to localStorage automatically
        autoRefreshToken: true,     // silently refresh expiring tokens
        detectSessionInUrl: true,   // pick up #access_token from OAuth redirects
    },
});
