import { createRouter, createWebHistory } from "vue-router";
import axios from "axios";
import { createApp } from "vue";
import App from "../App.vue";
import "vue-toast-notification/dist/theme-bootstrap.css";
import ToastPlugin from "vue-toast-notification";
import { useAuth, setAuthRouter } from "@/composables/useAuth";

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
      return { setup_completed: false, is_complete: false };
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

  // Set up axios interceptors before any API calls (router ref added after creation)
  auth.setupInterceptors();

  // Check auth status — public endpoint, always works
  const authStatus = await auth
    .getAuthStatus()
    .catch(() => ({ auth_setup_complete: false, app_setup_complete: false }));

  // If an admin account exists, try refreshing the session from the cookie.
  const hadSessionHint = localStorage.getItem("suggestarr_had_session") === "1";
  if (authStatus.auth_setup_complete && hadSessionHint) {
    await auth.tryRefresh();
  }

  // Only call /fetch if we now have an access token or if the system is in setup mode.
  // This avoids a noisy console 401 when the app is initialized without a session.
  if (!authStatus.auth_setup_complete || auth.accessToken.value) {
    await loadConfig().catch(() => {});
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
    // For development, we might want to skip setup checks
    if (process.env.NODE_ENV === "development" && to.query.skipSetup) {
      return;
    }

    const currentStatus = await checkSetupStatus();
    const isAuthenticated = !!auth.accessToken.value;

    // First-run flow:
    // - No auth users yet: force all routes to Login (setup-admin form lives there).
    // - Auth exists + app setup incomplete: keep Login out of the way and use /setup wizard.
    if (!currentStatus.setup_completed) {
      if (!isAuthenticated && to.name !== "Login") {
        return { name: "Login", query: { redirect: to.fullPath } };
      }
      if (isAuthenticated && to.name === "Login") {
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
        if (auth.accessToken.value) return "/dashboard";
        return;
      }
      if (!auth.accessToken.value) {
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
