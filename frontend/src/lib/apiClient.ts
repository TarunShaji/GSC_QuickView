const RAW_BASE = import.meta.env.VITE_API_BASE_URL

if (!RAW_BASE) {
    console.warn("VITE_API_BASE_URL is not defined. API requests may fail.")
}

/**
 * Normalize base URL
 * - Remove trailing slash
 * - Ensure no double slashes
 */
function normalizeBase(url: string): string {
    return (url || "").replace(/\/+$/, "")
}

/**
 * Always ensure /api prefix
 */
function buildUrl(path: string): string {
    const base = normalizeBase(RAW_BASE)

    let cleanedPath = path.trim()

    if (!cleanedPath.startsWith("/")) {
        cleanedPath = "/" + cleanedPath
    }

    // Only prepend /api if it doesn't already start with it
    if (!cleanedPath.startsWith("/api")) {
        cleanedPath = "/api" + cleanedPath
    }

    return `${base}${cleanedPath}`
}

async function request<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const url = buildUrl(path)

    console.log("[API REQUEST]", url)

    const response = await fetch(url, {
        // credentials: "include", // Removed for now as we don't use cookies for auth yet, but keeping commented for future
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    })

    // Handle 401 specifically for session clearing if implemented
    if (response.status === 401) {
        localStorage.removeItem('gsc_account_id');
        localStorage.removeItem('gsc_email');
        window.location.reload();
        return null as any;
    }

    if (!response.ok) {
        const text = await response.text()
        console.error("[API ERROR]", response.status, text)
        throw new Error(`API Error ${response.status}: ${text}`)
    }

    return response.json()
}

export const apiClient = {
    get: <T>(path: string) => request<T>(path),
    post: <T>(path: string, body?: any) =>
        request<T>(path, {
            method: "POST",
            body: body ? JSON.stringify(body) : undefined
        }),
    delete: <T>(path: string) =>
        request<T>(path, {
            method: "DELETE"
        })
}
