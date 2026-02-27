import axios from 'axios'
import { ref } from 'vue'

// Module-level singleton — shared across all composable instances
const accessToken = ref(null)
const currentUser = ref(null)  // { username, role }
const authSetupComplete = ref(false)

let _refreshPromise = null
let _interceptorsSetup = false
let _router = null
let _refreshFailed = false  // Once true, no further refresh attempts until login

/**
 * Decode a JWT and check whether it has already expired.
 * Does NOT verify the signature — used only for client-side timing decisions.
 * Returns true if the token is absent, unparseable, or past its `exp` claim.
 */
function isTokenExpired(token) {
    if (!token) return true
    try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        return Date.now() >= payload.exp * 1000
    } catch {
        return true  // Treat unreadable tokens as expired
    }
}

export function setAuthRouter(router) {
    _router = router
}

export function useAuth() {
    /**
     * Try to get a fresh access token using the httpOnly refresh cookie.
     * Deduplicates concurrent calls so only one refresh request is in-flight.
     */
    async function tryRefresh() {
        // If a previous refresh already failed this session, don't attempt again
        if (_refreshFailed) return false
        if (_refreshPromise) return _refreshPromise
        _refreshPromise = axios
            .post('/api/auth/refresh', {}, { _skipAuth: true })
            .then(res => {
                accessToken.value = res.data.access_token
                return true
            })
            .catch(() => {
                accessToken.value = null
                _refreshFailed = true  // Block further refresh attempts until next login
                return false
            })
            .finally(() => {
                _refreshPromise = null
            })
        return _refreshPromise
    }

    async function login(username, password) {
        const res = await axios.post('/api/auth/login', { username, password }, { _skipAuth: true })
        accessToken.value = res.data.access_token
        currentUser.value = { username: res.data.username, role: res.data.role }
        _refreshFailed = false  // Allow refresh attempts again after a fresh login
        return res.data
    }

    async function logout() {
        try {
            // _skipAuth: true prevents the 401 interceptor from re-entering this path
            await axios.post('/api/auth/logout', {}, { _skipAuth: true })
        } finally {
            accessToken.value = null
            currentUser.value = null
            _refreshFailed = false  // Allow refresh after the user logs in again
        }
    }

    async function setupAdmin(username, password) {
        await axios.post('/api/auth/setup', { username, password }, { _skipAuth: true })
    }

    async function getAuthStatus() {
        const res = await axios.get('/api/auth/status', { _skipAuth: true })
        authSetupComplete.value = res.data.auth_setup_complete
        return res.data
    }

    /**
     * Register axios interceptors. Safe to call multiple times — only registers once.
     */
    function setupInterceptors() {
        if (_interceptorsSetup) return
        _interceptorsSetup = true

        // Inject Bearer token on every request (unless explicitly skipped)
        axios.interceptors.request.use(config => {
            if (accessToken.value && !config._skipAuth) {
                config.headers = config.headers || {}
                config.headers.Authorization = `Bearer ${accessToken.value}`
            }
            return config
        })

        // On 401: attempt one token refresh then retry; otherwise logout + redirect to login
        axios.interceptors.response.use(
            res => res,
            async error => {
                const original = error.config
                const isRefreshEndpoint = original?.url?.includes('/api/auth/refresh')

                // Conditions that must ALL be true before we attempt a token refresh:
                //  1. The response was 401
                //  2. This request hasn't already been retried (prevents per-request loops)
                //  3. The failing request is not /auth/refresh itself
                //  4. The request was not explicitly marked as public (_skipAuth)
                //     — public requests (login, setup, status) should never trigger refresh
                //  5. The current token is absent or actually expired
                //     — a fresh token returned by login() that the server rejects cannot
                //       be fixed by refreshing; only refresh when expiry is the likely cause
                const tokenAbsentOrExpired = !accessToken.value || isTokenExpired(accessToken.value)

                if (
                    error.response?.status === 401 &&
                    !original?._retry &&
                    !isRefreshEndpoint &&
                    !original?._skipAuth &&
                    tokenAbsentOrExpired
                ) {
                    original._retry = true
                    const refreshed = await tryRefresh()
                    if (refreshed) {
                        original.headers = original.headers || {}
                        original.headers.Authorization = `Bearer ${accessToken.value}`
                        return axios(original)
                    }

                    // Refresh failed — log out (clears currentUser + calls backend to
                    // revoke the refresh cookie) then redirect to login
                    if (currentUser.value) {
                        await logout()
                    } else {
                        // Not authenticated at all; just clear any stale state
                        accessToken.value = null
                        currentUser.value = null
                    }

                    if (_router && _router.currentRoute.value.name !== 'Login') {
                        _router.push({
                            name: 'Login',
                            query: { redirect: _router.currentRoute.value.fullPath },
                        })
                    }
                }
                return Promise.reject(error)
            }
        )
    }

    return {
        accessToken,
        currentUser,
        authSetupComplete,
        login,
        logout,
        tryRefresh,
        setupAdmin,
        getAuthStatus,
        setupInterceptors,
    }
}
