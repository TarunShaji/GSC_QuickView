/**
 * API Base URL
 * Must be defined in frontend/.env as:
 * VITE_API_BASE_URL=http://localhost:8000
 */
const RAW_BASE = import.meta.env.VITE_API_BASE_URL as string | undefined

if (!RAW_BASE) {
    console.warn(
        "VITE_API_BASE_URL is not defined. Falling back to same-origin (may fail in dev)."
    )
}

/**
 * Normalize base URL
 * - Remove trailing slash
 */
function normalizeBase(url?: string): string {
    return (url || "").replace(/\/+$/, "")
}

/**
 * Build full API URL
 * - Ensures leading slash
 * - Ensures /api prefix
 */
function buildUrl(path: string): string {
    const base = normalizeBase(RAW_BASE)

    let cleanedPath = path.trim()

    if (!cleanedPath.startsWith("/")) {
        cleanedPath = "/" + cleanedPath
    }

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
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        },
        ...options
    })

    if (response.status === 401) {
        localStorage.removeItem("gsc_account_id")
        localStorage.removeItem("gsc_email")
        window.location.reload()
        return null as any
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