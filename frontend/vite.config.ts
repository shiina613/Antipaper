import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Same-origin backend proxy — replaces the Next.js `rewrites()` in the old
// next.config.ts. Frontend calls relative `/api/v1/...`; Vite forwards to the
// backend so the browser never sees a cross-origin request.
const backendUrl = (process.env.ANTIPAPER_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    proxy: {
      "/api/v1": {
        target: backendUrl,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
