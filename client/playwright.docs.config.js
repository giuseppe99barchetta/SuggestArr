import { defineConfig } from "@playwright/test";
import base from "./playwright.config.js";

// Generates the documentation screenshots in docs/assets/screenshots (npm run screenshots).
// Kept out of the e2e suite so CI never rewrites them.
export default defineConfig({
  ...base,
  testDir: "./docs-screenshots",
  retries: 0,
  timeout: 60_000,
  use: { ...base.use, viewport: { width: 1440, height: 900 }, colorScheme: "dark" },
});
