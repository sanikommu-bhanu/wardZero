import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api and /ws to the real FastAPI backend (uvicorn apps.api.main:app) so the
// frontend never needs CORS workarounds or a hardcoded absolute URL. In production, set
// VITE_API_BASE_URL / VITE_WS_URL (see .env.example in this folder) instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.WZ_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/ws": {
        target: process.env.WZ_API_PROXY_TARGET || "http://localhost:8000",
        ws: true,
        rewrite: (path) => path.replace(/^\/ws/, "/ws"),
      },
    },
  },
});
