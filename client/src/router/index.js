import { createRouter, createWebHistory } from "vue-router";
import axios from "axios";
import "vue-toast-notification/dist/theme-bootstrap.css";
import { useAuth, setAuthRouter, initializeAuthReady, markAuthReady, waitForAuthReady } from "@/composables/useAuth";

// Lazy load components for code splitting
const RequestsPage = () => import("@/components/RequestsPage.vue");
const ConfigWizard = () => import("@/components/ConfigWizard.vue");
const DashboardPage = () => import("@/components/DashboardPage.vue");
const LoginPage = () => import("@/components/LoginPage.vue");

function readSubpathFromMeta() {
  const metaTag = document.querySelector('meta[name="suggestarr-subpath"]');
  return metaTag ? metaTag.getAttribute("content") || "" : "";
}

function configureAxiosSubpath(subpath) {
  if (process.env.NODE_ENV === "development") {
    axios.defaults.baseURL = "http://localhost:5000" + subpath;
  } else {
    axios.defaults.baseURL = subpath || "/";
  }
}

let _configPromise = null;

/**
 * Load config without requiring authentication (setup mode).
 * Uses `_skipAuth: true` so public endpoints work during setup.
 */
async function loadConfig() {
  if (_configPromise) return _configPromise;

  _configPromise = axios
    .get("/api/config/fetch", {
      _skipAuth: true,
      timeout: 10000,
    })
    .then((response) => {
      localStorage.setItem("suggestarr_config", JSON.stringify(response.data));
      return response.data.SUBPATH || "";
    })
    .catch((error) => {
      // If we're not logged in, fetch will return 401 — that's expected.
      if (error.response?.status !== 401) {
        console.warn(
          "Unable to load initial configuration file:",
          error.message,
        );
      }
      return ""; // Fallback to root subpath
    })
    .finally(() => {
      _configPromise = null;
    });

  return _configPromise;
}

let _authConfigPromise = null;

/**
 * Load config with authentication (after token is set).
 * Does NOT use `_skipAuth`, so the Authorization header IS added by the interceptor.
 * This ensures the backend receives the Bearer token for protected endpoints.
 */
async function loadAuthenticatedConfig() {
  if (_authConfigPromise) return _authConfigPromise;

  _authConfigPromise = axios
    .get("/api/config/fetch", {
      timeout: 10000,
      // NOTE: NO _skipAuth - the request interceptor WILL add Authorization header
    })
    .then((response) => {
      localStorage.setItem("suggestarr_config", JSON.stringify(response.data));
      return response.data.SUBPATH || "";
    })
    .catch((error) => {
      console.warn(
        "Failed to load authenticated configuration:",
        error.message,
      );
      return ""; // Fallback to root subpath
    })
    .finally(() => {
      _authConfigPromise = null;
    });

  return _authConfigPromise;
}

let _statusCache = null;
let _statusCacheTimestamp = 0;
let _statusPromise = null;
const STATUS_CACHE_TTL = 1000; // 1 second cache
let _authModeCache = null;

function isAbortLikeError(error) {
  const code = error?.code || error?.message?.code;
  if (code === "ECONNABORTED" || code === "ERR_CANCELED") return true;
  if (error?.name === "CanceledError") return true;

  const rawMessage =
    typeof error?.message === "string"
      ? error.message
      : typeof error?.message?.message === "string"
        ? error.message.message
        : "";
  const message = rawMessage.toLowerCase();
  return message.includes("aborted") || message.includes("canceled");
}

async function checkSetupStatus() {
  const now = Date.now();
  if (_statusCache && now - _statusCacheTimestamp < STATUS_CACHE_TTL) {
    return _statusCache;
  }

  // Deduplicate concurrent calls during boot/navigation
  if (_statusPromise) return _statusPromise;

  _statusPromise = axios
    .get("/api/config/status", {
      _skipAuth: true,
      timeout: 10000,
    })
    .then((response) => {
      _statusCache = response.data;
      _statusCacheTimestamp = now;
      return response.data;
    })
    .catch((error) => {
      // Don't report abortions (often due to navigation redirects) as noisy errors
      if (!isAbortLikeError(error)) {
        console.error("Error checking setup status:", error.message);
      }
      return { setup_completed: false, is_complete: false };
    })
    .finally(() => {
      _statusPromise = null;
    });

  return _statusPromise;
}

async function getAuthMode() {
  if (_authModeCache) return _authModeCache;

  try {
    const cachedConfig = localStorage.getItem("suggestarr_config");
    if (cachedConfig) {
      const parsedConfig = JSON.parse(cachedConfig);
      const cachedMode = (parsedConfig?.AUTH_MODE || "enabled").toString().toLowerCase();
      if (["enabled", "local_bypass", "disabled"].includes(cachedMode)) {
        _authModeCache = cachedMode;
        return _authModeCache;
      }
    }
  } catch {
    // Ignore cache parse errors and fetch from API.
  }

  try {
    const response = await axios.get("/api/config/fetch", { _skipAuth: true, timeout: 10000 });
    const mode = (response.data?.AUTH_MODE || "enabled").toString().toLowerCase();
    _authModeCache = ["enabled", "local_bypass", "disabled"].includes(mode) ? mode : "enabled";
    return _authModeCache;
  } catch {
    _authModeCache = "enabled";
    return _authModeCache;
  }
}

export async function createAppRouter() {
  const subpath = readSubpathFromMeta();
  configureAxiosSubpath(subpath);

  const auth = useAuth();

  // Initialize the auth-ready signal so components can wait for auth setup
  initializeAuthReady();

  // Set up axios interceptors before any API calls (router ref added after creation)
  auth.setupInterceptors();

  let authStatus = { auth_setup_complete: false, app_setup_complete: false };

  try {
    // Check auth status — public endpoint, always works
    authStatus = await auth.getAuthStatus();

    // If an admin account exists, try refreshing the session from the cookie.
    const hadSessionHint = localStorage.getItem("suggestarr_had_session") === "1";
    if (authStatus.auth_setup_complete && hadSessionHint) {
      await auth.tryRefresh();
    }

    // Load config based on auth state:
    // - If NOT in setup mode and we have a token (either already or just refreshed),
    //   use authenticated config loading (WITHOUT _skipAuth, so Authorization header is added)
    // - If in setup mode, use public config loading (with _skipAuth: true)
    if (authStatus.auth_setup_complete && auth.accessToken.value) {
      // Authenticated case: we have a token, so fetch config WITH auth header
      await loadAuthenticatedConfig().catch(() => {});
    } else if (!authStatus.auth_setup_complete) {
      // Setup mode: no auth required yet, fetch with _skipAuth
      await loadConfig().catch(() => {});
    }
  } catch (error) {
    console.warn("Auth initialization failed, continuing in logged-out state", error);
  } finally {
    // Always resolve auth-ready waiters, even when refresh/bootstrap fails.
    markAuthReady();
  }

  // No need to call checkSetupStatus here; it will be handled by the first navigation to the app.

  const routes = [
    {
      path: `/requests`,
      name: "RequestsPage",
      component: RequestsPage,
      meta: { requiresSetup: true },
    },
    {
      path: `/`,
      name: "Home",
      component: DashboardPage,
      meta: { requiresSetup: true },
    },
    {
      path: `/setup`,
      name: "Setup",
      component: ConfigWizard,
      meta: { setupOnly: true },
    },
    {
      path: `/dashboard`,
      name: "Dashboard",
      component: DashboardPage,
      meta: { requiresSetup: true },
    },
    {
      path: `/dashboard/:tab?`,
      name: "DashboardTab",
      component: DashboardPage,
      meta: { requiresSetup: true },
    },
    {
      path: `/login`,
      name: "Login",
      component: LoginPage,
    },
    // Redirect legacy routes
    {
      path: `/wizard`,
      redirect: "/setup",
    },
  ];

  const router = createRouter({
    history: createWebHistory(subpath || "/"),
    routes,
  });

  // Give the auth module a router reference for 401 redirects
  setAuthRouter(router);

  // Add navigation guards
  router.beforeEach(async (to) => {
    // Wait for initial auth setup to complete before allowing navigation
    // This ensures the access token is set and any refresh has completed
    await waitForAuthReady();

    // For development, we might want to skip setup checks
    if (process.env.NODE_ENV === "development" && to.query.skipSetup) {
      return;
    }

    const currentStatus = await checkSetupStatus();
    const authMode = await getAuthMode();
    const isAuthDisabled = authMode === "disabled";
    let statusAuth = { authenticated: false, bypass: false };
    try {
      const status = await auth.getAuthStatus();
      statusAuth = {
        authenticated: !!status?.authenticated,
        bypass: !!status?.bypass,
      };
    } catch {
      // Keep default unauthenticated status when the probe fails.
    }

    const isBypassAuthenticated = statusAuth.authenticated && statusAuth.bypass;
    const isAuthenticated = !!auth.accessToken.value || isBypassAuthenticated;

    // First-run flow:
    // - No auth users yet: force all routes to Login (setup-admin form lives there).
    // - Auth exists + app setup incomplete: keep Login out of the way and use /setup wizard.
    if (!currentStatus.setup_completed) {
      if (!isAuthenticated && !isAuthDisabled && to.name !== "Login") {
        return { name: "Login", query: { redirect: to.fullPath } };
      }
      if ((isAuthenticated || isAuthDisabled) && to.name === "Login") {
        return "/setup";
      }
    }

    // If setup is not completed and route requires setup, redirect to setup
    if (to.meta.requiresSetup && !currentStatus.setup_completed) {
      return "/setup";
    }

    // If setup is completed and route is setup-only, redirect to settings
    if (to.meta.setupOnly && currentStatus.setup_completed) {
      return "/dashboard";
    }

    // Auth guard — only enforce when an admin account exists
    if (auth.authSetupComplete.value) {
      if (to.name === "Login") {
        // Already authenticated → skip login page
        if (isAuthenticated || isAuthDisabled) return "/dashboard";
        return;
      }
      if (!isAuthenticated && !isAuthDisabled) {
        return { name: "Login", query: { redirect: to.fullPath } };
      }
    }
  });

  return router;
}

// Redirect if on a subpath, as before
const _earlySubpath = readSubpathFromMeta();
if (_earlySubpath && !window.location.pathname.startsWith(_earlySubpath)) {
  window.location.replace(_earlySubpath + "/");
}
