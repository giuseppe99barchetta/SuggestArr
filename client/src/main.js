import { createApp } from "vue";
import App from "./App.vue";
import ToastPlugin from "vue-toast-notification";
import "vue-toast-notification/dist/theme-bootstrap.css";
import "@/assets/styles/toast-custom.css";
import axios from "axios";
import { createAppRouter } from "./router";
import { TOAST_OPTIONS } from "./toastOptions";
import "@/assets/main.css";
import { initTheme } from "@/utils/theme.js";
import { registerServiceWorker } from "@/utils/pwa.js";

initTheme();
registerServiceWorker();

async function initApp() {
  axios.defaults.withCredentials = true;

  // Configure base URL for development
  if (import.meta.env.DEV) {
    axios.defaults.baseURL = "http://localhost:5000";
  }

  // Await the router creation (checks auth, subpath, etc.)
  const router = await createAppRouter().catch((err) => {
    console.error("Router creation failed:", err);
    return null; // Fallback or handle appropriately
  });

  if (!router) return;

  const app = createApp(App);

  app.use(router);
  app.use(ToastPlugin, TOAST_OPTIONS);

  app.mount("#app");
}

initApp().catch((err) => {
  console.error("Critical error during application initialization:", err);
});
