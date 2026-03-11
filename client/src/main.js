import { createApp } from "vue";
import App from "./App.vue";
import ToastPlugin from "vue-toast-notification";
import "vue-toast-notification/dist/theme-bootstrap.css";
import "@/assets/styles/toast-custom.css";
import axios from "axios";
import { createAppRouter } from "./router";
import "@/assets/styles/theme.css";
import "@/assets/styles/global.css";

async function initApp() {
  axios.defaults.withCredentials = true;

  // Configure base URL for development
  if (process.env.NODE_ENV === "development") {
    axios.defaults.baseURL = "http://localhost:5000";
  }

  // Await the router creation (checks auth, subpath, etc.)
  const router = await createAppRouter().catch((err) => {
    console.error("Router creation failed:", err);
    return null; // Fallback or handle appropriately
  });

  if (!router) return;

  const app = createApp(App);

  // Standard toast options
  const options = {
    position: "top-right",
    duration: 5000,
    dismissible: true,
    pauseOnHover: true,
    queue: true,
  };

  app.use(router);
  app.use(ToastPlugin, options);

  app.mount("#app");
}

initApp().catch((err) => {
  console.error("Critical error during application initialization:", err);
});
