import axios from "axios";
import { ref } from "vue";

// Module-level singleton — shared across all composable instances
const accessToken = ref(null);
const currentUser = ref(null); // { username, role }
const authSetupComplete = ref(false);
const authBypass = ref(false);
const SESSION_HINT_KEY = "suggestarr_had_session";

let _refreshPromise = null;
let _interceptorsSetup = false;
let _router = null;
let _refreshFailed = false; // Once true, no further refresh attempts until login
let _refreshTransient = false; // The last refresh failed for a recoverable reason (backend down, timeout)

// Auth initialization tracking — ensures app doesn't make protected API calls
// until auth is fully set up and any required refresh is complete.
let _authInitReadyPromise = null;
let _authInitResolve = null;

/**
 * The Authorization header a request was sent with (axios keeps it on a plain object or on AxiosHeaders).
 * @param {import('axios').AxiosRequestConfig} config - Request config of the failed call.
 * @returns {string|null} The header value, or null when the request carried none.
 */
function sentAuthorization(config) {
  const headers = config?.headers;
  if (!headers) return null;
  return headers.Authorization || (typeof headers.get === "function" ? headers.get("Authorization") : null) || null;
}

/**
 * Decode JWT payload for client-side identity state.
 * Signature is verified server-side only; here we use it to keep UI state in sync.
 */
function decodeTokenPayload(token) {
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split(".")[1]));
  } catch {
    return null;
  }
}

/**
 * Keep access token + current user aligned from a single source of truth (JWT).
 */
function setSessionFromAccessToken(token) {
  accessToken.value = token || null;
  const payload = decodeTokenPayload(token);
  if (!payload) {
    currentUser.value = null;
    return;
  }

  currentUser.value = {
    id: payload.sub ? Number(payload.sub) : undefined,
    username: payload.username || "",
    role: payload.role || "user",
  };
}

export function setAuthRouter(router) {
  _router = router;
}

/**
 * Initialize the auth-ready promise. Called once during app startup
 * to allow waitForAuthReady() to resolve when auth setup is complete.
 */
export function initializeAuthReady() {
  if (!_authInitReadyPromise) {
    _authInitReadyPromise = new Promise((resolve) => {
      _authInitResolve = resolve;
    });
  }
  return _authInitReadyPromise;
}

/**
 * Mark auth as fully initialized and ready for protected API calls.
 * Called after setup checks and refresh attempts are complete.
 */
export function markAuthReady() {
  if (_authInitResolve) {
    _authInitResolve();
  }
}

/**
 * Wait for auth initialization to complete.
 * Safe to call multiple times — returns the same promise.
 * @returns {Promise<void>} Resolves when auth is ready for protected API calls.
 */
export async function waitForAuthReady() {
  if (!_authInitReadyPromise) {
    initializeAuthReady();
  }
  return _authInitReadyPromise;
}

export function useAuth() {
  /**
   * Try to get a fresh access token using the httpOnly refresh cookie.
   * Deduplicates concurrent calls so only one refresh request is in-flight.
   */
  async function tryRefresh() {
    // If a previous refresh already failed this session, don't attempt again
    if (_refreshFailed) return false;
    if (_refreshPromise) return _refreshPromise;
    _refreshPromise = axios
      .post("/api/auth/refresh", {}, { _skipAuth: true })
      .then((res) => {
        setSessionFromAccessToken(res.data.access_token);
        localStorage.setItem(SESSION_HINT_KEY, "1");
        return true;
      })
      .catch((error) => {
        // Only a real refusal ends the session. A backend restarting (5xx), a network drop or a
        // timeout must stay recoverable: keep the session and let the next request try again.
        const status = error?.response?.status;
        _refreshTransient = !(status === 401 || status === 403);
        if (!_refreshTransient) {
          setSessionFromAccessToken(null);
          _refreshFailed = true; // Block further refresh attempts until next login
          localStorage.removeItem(SESSION_HINT_KEY);
        }
        return false;
      })
      .finally(() => {
        _refreshPromise = null;
      });
    return _refreshPromise;
  }

  async function login(username, password) {
    const res = await axios.post(
      "/api/auth/login",
      { username, password },
      { _skipAuth: true },
    );
    setSessionFromAccessToken(res.data.access_token);
    authBypass.value = false;
    _refreshFailed = false; // Allow refresh attempts again after a fresh login
    localStorage.setItem(SESSION_HINT_KEY, "1");
    return res.data;
  }

  async function logout() {
    try {
      // _skipAuth: true prevents the 401 interceptor from re-entering this path
      await axios.post("/api/auth/logout", {}, { _skipAuth: true });
    } finally {
      setSessionFromAccessToken(null);
      authBypass.value = false;
      _refreshFailed = false; // Allow refresh after the user logs in again
      localStorage.removeItem(SESSION_HINT_KEY);
      try {
        localStorage.removeItem("suggestarr_config"); // legacy cache of the full configuration
      } catch {
        // Storage can be unavailable.
      }
    }
  }

  async function setupAdmin(username, password) {
    await axios.post(
      "/api/auth/setup",
      { username, password },
      { _skipAuth: true },
    );
  }

  async function getAuthStatus() {
    const res = await axios.get("/api/auth/status", { _skipAuth: true });
    authSetupComplete.value = res.data.auth_setup_complete;
    authBypass.value = !!res.data.bypass;
    return res.data;
  }

  /**
   * Register axios interceptors. Safe to call multiple times — only registers once.
   */
  function setupInterceptors() {
    if (_interceptorsSetup) return;
    _interceptorsSetup = true;

    // Inject Bearer token on internal requests (unless explicitly skipped)
    axios.interceptors.request.use((config) => {
      const isInternal =
        config.url &&
        (config.url.startsWith("/api/") || !config.url.startsWith("http"));
      if (accessToken.value && !config._skipAuth && isInternal) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${accessToken.value}`;
      }
      return config;
    });

    // On 401: attempt one token refresh then retry; otherwise logout + redirect to login
    axios.interceptors.response.use(
      (res) => res,
      async (error) => {
        const original = error.config;
        const isRefreshEndpoint = original?.url?.includes("/api/auth/refresh");

        // Conditions that must ALL be true before we attempt a token refresh:
        //  1. The response was 401
        //  2. This request hasn't already been retried (prevents per-request loops)
        //  3. The failing request is not /auth/refresh itself
        //  4. The request was not explicitly marked as public (_skipAuth)
        //     — public requests (login, setup, status) should never trigger refresh
        // A 401 on a token that has not expired is possible too (the account was deactivated or
        // demoted), and refreshing is how the session finds out and ends cleanly.
        if (
          error.response?.status === 401 &&
          !original?._retry &&
          !isRefreshEndpoint &&
          !original?._skipAuth
        ) {
          original._retry = true;
          // Concurrent requests share one expired token: when another request already replaced it, this
          // one only needs to be sent again with the current token, not to refresh a second time.
          const sent = sentAuthorization(original);
          const current = accessToken.value ? `Bearer ${accessToken.value}` : null;
          if (sent && current && sent !== current) {
            original.headers = original.headers || {};
            original.headers.Authorization = current;
            return axios(original);
          }
          const refreshed = await tryRefresh();
          if (refreshed) {
            original.headers = original.headers || {};
            original.headers.Authorization = `Bearer ${accessToken.value}`;
            return axios(original);
          }
          // The backend could not be reached to refresh: this is not a logout. Fail this request only;
          // the next one tries again once the backend is back.
          if (_refreshTransient) return Promise.reject(error);

          // Refresh failed — log out (clears currentUser + calls backend to
          // revoke the refresh cookie) then redirect to login
          if (currentUser.value) {
            await logout();
          } else {
            // Not authenticated at all; just clear any stale state
            setSessionFromAccessToken(null);
          }

          if (_router && _router.currentRoute.value.name !== "Login") {
            _router.push({
              name: "Login",
              query: { redirect: _router.currentRoute.value.fullPath },
            });
          }
        }
        return Promise.reject(error);
      },
    );
  }

  return {
    accessToken,
    currentUser,
    authSetupComplete,
    authBypass,
    login,
    logout,
    tryRefresh,
    setupAdmin,
    getAuthStatus,
    setupInterceptors,
    markAuthReady,
  };
}
