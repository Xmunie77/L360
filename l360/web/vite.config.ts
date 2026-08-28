import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api and /health to the FastAPI backend on :8000 so the
// SPA and API share an origin during development (matches production).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/vitest.setup.ts"],
  },
});
