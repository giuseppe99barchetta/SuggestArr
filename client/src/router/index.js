import { createRouter, createWebHistory } from "vue-router";
import axios from "axios";
import { useAuth, setAuthRouter, initializeAuthReady, markAuthReady, waitForAuthReady } from "@/composables/useAuth";
import { readStorage, removeStorage } from "@/utils/storage.js";

// Lazy load components for code splitting
const ConfigWizard = () => import("@/components/ConfigWizard.vue");
const DashboardPage = () => import("@/components/DashboardPage.vue");
const LoginPage = () => import("@/components/LoginPage.vue");
const ApiDocsPage = () => import("@/components/ApiDocsPage.vue");

function readSubpathFromMeta() {
  const metaTag = document.querySelector('meta[name="suggestarr-subpath"]');
  return metaTag ? metaTag.getAttribute("content") || "" : "";
}

function configureAxiosSubpath(subpath) {
  if (import.meta.env.DEV) {
    axios.defaults.baseURL = "http://localhost:5000" + subpath;
  } else {
    axios.defaults.baseURL = subpath || "/";
  }
}

let _statusCache = null;
let _statusCacheTimestamp = 0;
let _statusPromise = null;
const STATUS_CACHE_TTL = 1000; // 1 second cache

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
      // Unknown, not "setup incomplete": a failed probe must not push a configured install to the wizard.
      return { setup_completed: false, is_complete: false, unknown: true };
    })
    .finally(() => {
      _statusPromise = null;
    });

  return _statusPromise;
}

export async function createAppRouter() {
  const subpath = readSubpathFromMeta();
  configureAxiosSubpath(subpath);

  const auth = useAuth();

  // Older versions stored the whole configuration (API keys, tokens, DB password) in the browser.
  removeStorage("suggestarr_config");

  // Initialize the auth-ready signal so components can wait for auth setup
  initializeAuthReady();

  // Set up axios interceptors before any API calls (router ref added after creation)
  auth.setupInterceptors();

  try {
    // Check auth status — public endpoint, always works
    const authStatus = await auth.getAuthStatus();

    // If an admin account exists, try refreshing the session from the cookie.
    const hadSessionHint = readStorage("suggestarr_had_session") === "1";
    if (authStatus.auth_setup_complete && hadSessionHint) {
      await auth.tryRefresh();
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
      redirect: (to) => ({ name: "DashboardTab", params: { tab: "requests" }, query: to.query }),
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
    {
      path: `/docs`,
      name: "ApiDocs",
      component: ApiDocsPage,
      meta: { public: true },
    },
    // Redirect legacy routes
    {
      path: `/wizard`,
      redirect: "/setup",
    },
    // Unknown paths land on the dashboard instead of an empty page.
    {
      path: "/:pathMatch(.*)*",
      redirect: "/dashboard",
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
    if (to.meta.public) return;
    // Wait for initial auth setup to complete before allowing navigation
    // This ensures the access token is set and any refresh has completed
    await waitForAuthReady();

    // For development, we might want to skip setup checks
    if (import.meta.env.DEV && to.query.skipSetup) {
      return;
    }

    let statusAuth;
    try {
      const status = await auth.getAuthStatus();
      statusAuth = {
        authenticated: !!status?.authenticated,
        bypass: !!status?.bypass,
      };
    } catch {
      if (to.name !== "Login") return { name: "Login", query: { redirect: to.fullPath } };
      return;
    }
    const currentStatus = await checkSetupStatus();

    // Disabled, local-bypass and trusted-header modes all report themselves as `bypass` here.
    const isBypassAuthenticated = statusAuth.authenticated && statusAuth.bypass;
    const isAuthenticated = !!auth.accessToken.value || isBypassAuthenticated;

    // First-run flow:
    // - No auth users yet: force all routes to Login (setup-admin form lives there).
    // - Auth exists + app setup incomplete: keep Login out of the way and use /setup wizard.
    const setupKnown = !currentStatus.unknown;
    if (setupKnown && !currentStatus.setup_completed) {
      if (!isAuthenticated && to.name !== "Login") {
        return { name: "Login", query: { redirect: to.fullPath } };
      }
      if (isAuthenticated && to.name === "Login") {
        return "/setup";
      }
    }

    // If setup is not completed and route requires setup, redirect to setup
    if (setupKnown && to.meta.requiresSetup && !currentStatus.setup_completed) {
      return "/setup";
    }

    // If setup is completed and route is setup-only, redirect to settings
    if (setupKnown && to.meta.setupOnly && currentStatus.setup_completed) {
      return "/dashboard";
    }

    // Auth guard — only enforce when an admin account exists
    if (auth.authSetupComplete.value) {
      if (to.name === "Login") {
        // Already authenticated → skip login page
        if (isAuthenticated) return "/dashboard";
        return;
      }
      if (!isAuthenticated) {
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
