import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "./",
  plugins: [vue()],
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || "unknown"),
  },
});
