import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: [".e2b.app", "localhost", "127.0.0.1"],
    watch: {
      usePolling: true,
    },
    proxy: {
      // Relative /api from the browser; the dev server proxies to the backend.
      // Local dev targets localhost; docker compose sets API_PROXY_TARGET=http://api:8000.
      "/api": { target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.ts"],
    css: false,
  },
} as ReturnType<typeof defineConfig>);
